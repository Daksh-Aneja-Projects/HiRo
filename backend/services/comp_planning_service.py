"""Compensation review cycles (bulk merit planning) and headcount planning.

New service file (see COLLISION RULES). Does not edit hr_modules.py: it calls
HRModulesService.update_compensation for the actual pay change, the same path the
"a pay change is applied and recorded" workflow test exercises, so a finalized cycle
writes comp_history exactly the way a manual pay change already does. Function-based,
matching services/social_recognition.py's style rather than a new class.
"""
import logging
import uuid
from datetime import date
from typing import Any, Dict, List, Optional

from services.postgres_client import pg_client
from services.pii_vault import PIIVault
from services.talent_intelligence import names_for_uuids

logger = logging.getLogger(__name__)


class BudgetExceeded(Exception):
    """Raised when a cycle's proposed increases exceed its approved budget."""


# ---------------------------------------------------------------------------
# Compensation review cycles
# ---------------------------------------------------------------------------

def _suggested_merit_pct(rating: Optional[float], salary_cents: int, dept_salaries_cents: List[int],
                          risk_score: Optional[float]) -> float:
    """Suggested merit increase. A documented heuristic, not a measurement.

    Base 3.0%.
    Rating:       +2.0 if >=4.5, +1.0 if >=4.0, -1.5 if <3.0.
    Compa-position: HiRo has no external market-pay benchmark, so this uses the
        employee's position within their own department's salary distribution as a
        proxy: +1.0 if bottom quartile (catch-up), -0.5 if top quartile.
    Attrition risk (reuses workforce_planning_service's risk score): +1.5 if HIGH
        (>0.6), +2.5 if CRITICAL (>0.85) -- a retention lever, not a rating reward.
    Clamped to [0, 8].
    """
    pct = 3.0
    r = rating if rating is not None else 3.0
    if r >= 4.5:
        pct += 2.0
    elif r >= 4.0:
        pct += 1.0
    elif r < 3.0:
        pct -= 1.5

    if dept_salaries_cents:
        sorted_s = sorted(dept_salaries_cents)
        idx = sorted_s.index(salary_cents) if salary_cents in sorted_s else len(sorted_s) // 2
        percentile = idx / max(1, len(sorted_s) - 1)
        if percentile <= 0.25:
            pct += 1.0
        elif percentile >= 0.75:
            pct -= 0.5

    risk = risk_score or 0.0
    if risk > 0.85:
        pct += 2.5
    elif risk > 0.6:
        pct += 1.5

    return round(max(0.0, min(8.0, pct)), 2)


async def _populate_lines(cycle_id: str, department: str, created_by: str) -> int:
    # Pre-aggregated join, not a per-row correlated subquery over the whole department --
    # see workforce_planning_service.succession_readiness for the reason that matters.
    rows = await pg_client.fetch(
        """SELECT e.employee_uuid, e.base_salary_encrypted, e.dtla_risk_score, r.avg_rating
           FROM employee_pii e
           LEFT JOIN (SELECT employee_uuid, AVG(overall_rating) AS avg_rating
                      FROM performance_reviews GROUP BY employee_uuid) r
             ON r.employee_uuid = e.employee_uuid
           WHERE e.department = $1""",
        department,
    )
    if not rows:
        return 0

    vault = PIIVault.get_instance()
    # ponytail: synchronous PQC decrypt per employee, same pattern pii_vault.py already
    # uses. Bounded to one department and run only when a cycle is created (not a hot
    # path); move to a thread pool if a department this size starts blocking the loop.
    cents_by_uuid: Dict[str, int] = {}
    for r in rows:
        try:
            salary = float(vault.decrypt(r["base_salary_encrypted"])) if r.get("base_salary_encrypted") else 0.0
        except Exception:
            salary = 0.0
        cents_by_uuid[r["employee_uuid"]] = int(round(salary * 100))

    all_cents = list(cents_by_uuid.values())
    to_insert = []
    for r in rows:
        cents = cents_by_uuid[r["employee_uuid"]]
        rating = float(r["avg_rating"]) if r.get("avg_rating") is not None else None
        risk = float(r["dtla_risk_score"]) if r.get("dtla_risk_score") is not None else None
        pct = _suggested_merit_pct(rating, cents, all_cents, risk)
        to_insert.append((cycle_id, r["employee_uuid"], cents, pct, created_by))

    await pg_client.executemany_async(
        """INSERT INTO comp_cycle_lines (cycle_id, employee_uuid, current_comp_cents, proposed_pct, proposed_by)
           VALUES ($1,$2,$3,$4,$5)""",
        to_insert,
    )
    return len(to_insert)


async def create_cycle(department: Optional[str], name: Optional[str],
                        budget_pct: float, created_by: str) -> Dict[str, Any]:
    if not department:
        raise ValueError("department is required.")
    cycle_id = f"CYC-{uuid.uuid4().hex[:10].upper()}"
    await pg_client.execute(
        """INSERT INTO comp_cycles (cycle_id, name, department, status, budget_pct, created_by)
           VALUES ($1,$2,$3,'draft',$4,$5)""",
        cycle_id, name or f"{department} merit cycle", department, budget_pct, created_by,
    )
    lines_created = await _populate_lines(cycle_id, department, created_by)
    return {"cycle_id": cycle_id, "department": department, "status": "draft",
            "budget_pct": float(budget_pct), "lines_created": lines_created}


async def list_cycles() -> List[Dict[str, Any]]:
    return await pg_client.fetch("SELECT * FROM comp_cycles ORDER BY created_at DESC")


async def get_cycle(cycle_id: str) -> Dict[str, Any]:
    cycle = await pg_client.fetchrow("SELECT * FROM comp_cycles WHERE cycle_id = $1", cycle_id)
    if not cycle:
        raise ValueError(f"No comp cycle '{cycle_id}'.")
    lines = await pg_client.fetch("SELECT * FROM comp_cycle_lines WHERE cycle_id = $1 ORDER BY id", cycle_id)
    names = await names_for_uuids([l["employee_uuid"] for l in lines])

    line_out = []
    for l in lines:
        current = l["current_comp_cents"] / 100.0
        out = {k: v for k, v in l.items() if k != "current_comp_cents"}
        out["employee_name"] = names.get(l["employee_uuid"], l["employee_uuid"])
        out["current_comp"] = round(current, 2)
        out["proposed_new_comp"] = round(current * (1 + float(l["proposed_pct"]) / 100.0), 2)
        line_out.append(out)

    return {**cycle, "lines": line_out}


async def adjust_line(cycle_id: str, line_id: int, proposed_pct: float, by: str) -> Dict[str, Any]:
    row = await pg_client.fetchrow(
        """UPDATE comp_cycle_lines SET proposed_pct = $1, proposed_by = $2, status = 'adjusted'
           WHERE id = $3 AND cycle_id = $4 RETURNING *""",
        proposed_pct, by, line_id, cycle_id,
    )
    if not row:
        raise ValueError("No such line on this cycle.")
    return row


async def finalize_cycle(cycle_id: str, hr_modules_service, finalized_by: str) -> Dict[str, Any]:
    cycle = await pg_client.fetchrow("SELECT * FROM comp_cycles WHERE cycle_id = $1", cycle_id)
    if not cycle:
        raise ValueError(f"No comp cycle '{cycle_id}'.")
    if cycle["status"] == "finalized":
        raise ValueError("This cycle has already been finalized.")

    lines = await pg_client.fetch("SELECT * FROM comp_cycle_lines WHERE cycle_id = $1", cycle_id)
    if not lines:
        raise ValueError("This cycle has no lines to finalize.")

    total_current = sum(int(l["current_comp_cents"]) for l in lines)
    total_proposed_increase = sum(int(l["current_comp_cents"]) * float(l["proposed_pct"]) / 100.0 for l in lines)
    weighted_pct = (total_proposed_increase / total_current * 100.0) if total_current else 0.0
    budget_pct = float(cycle["budget_pct"])

    if weighted_pct > budget_pct + 1e-9:
        over_dollars = (total_proposed_increase - total_current * budget_pct / 100.0) / 100.0
        raise BudgetExceeded(
            f"Proposed increases average {weighted_pct:.2f}% of payroll "
            f"(${total_proposed_increase / 100:,.0f} of ${total_current / 100:,.0f} base pay), "
            f"which is above the {budget_pct:.2f}% budget by ${over_dollars:,.0f}. "
            f"Reduce proposed increases by that amount before finalizing."
        )

    applied, failed = 0, []
    for l in lines:
        if l["status"] == "applied":
            continue
        new_salary = (int(l["current_comp_cents"]) / 100.0) * (1 + float(l["proposed_pct"]) / 100.0)
        try:
            await hr_modules_service.update_compensation(
                employee_id=l["employee_uuid"], new_salary=round(new_salary, 2), new_grade=None,
                effective_date=date.today().isoformat(), updated_by=finalized_by,
            )
            await pg_client.execute("UPDATE comp_cycle_lines SET status = 'applied' WHERE id = $1", l["id"])
            applied += 1
        except Exception as e:
            logger.error(f"Comp cycle {cycle_id} line {l['id']} ({l['employee_uuid']}) failed to apply: {e}")
            failed.append(l["employee_uuid"])

    await pg_client.execute("UPDATE comp_cycles SET status = 'finalized' WHERE cycle_id = $1", cycle_id)
    return {"cycle_id": cycle_id, "status": "finalized", "lines_applied": applied,
            "lines_failed": failed, "weighted_increase_pct": round(weighted_pct, 2)}


# ---------------------------------------------------------------------------
# Headcount planning
# ---------------------------------------------------------------------------

async def create_headcount_plan(department: Optional[str], fiscal_label: Optional[str],
                                 planned_headcount: Optional[int], created_by: str) -> Dict[str, Any]:
    if not department or not fiscal_label or planned_headcount is None:
        raise ValueError("department, fiscal_label and planned_headcount are required.")
    plan_id = f"HCP-{uuid.uuid4().hex[:10].upper()}"
    await pg_client.execute(
        """INSERT INTO headcount_plans (plan_id, department, fiscal_label, planned_headcount, created_by)
           VALUES ($1,$2,$3,$4,$5)""",
        plan_id, department, fiscal_label, int(planned_headcount), created_by,
    )
    return {"plan_id": plan_id, "department": department, "fiscal_label": fiscal_label,
            "planned_headcount": int(planned_headcount)}


async def list_headcount_plans(department: Optional[str] = None) -> List[Dict[str, Any]]:
    if department:
        return await pg_client.fetch(
            "SELECT * FROM headcount_plans WHERE department = $1 ORDER BY created_at DESC", department)
    return await pg_client.fetch("SELECT * FROM headcount_plans ORDER BY created_at DESC")


async def update_headcount_plan(plan_id: str, planned_headcount: Optional[int],
                                 fiscal_label: Optional[str]) -> Dict[str, Any]:
    row = await pg_client.fetchrow("SELECT * FROM headcount_plans WHERE plan_id = $1", plan_id)
    if not row:
        raise ValueError(f"No headcount plan '{plan_id}'.")
    new_headcount = int(planned_headcount) if planned_headcount is not None else row["planned_headcount"]
    new_label = fiscal_label or row["fiscal_label"]
    await pg_client.execute(
        "UPDATE headcount_plans SET planned_headcount = $1, fiscal_label = $2 WHERE plan_id = $3",
        new_headcount, new_label, plan_id,
    )
    return {"plan_id": plan_id, "planned_headcount": new_headcount, "fiscal_label": new_label}


async def delete_headcount_plan(plan_id: str) -> None:
    result = await pg_client.execute("DELETE FROM headcount_plans WHERE plan_id = $1", plan_id)
    if result == "DELETE 0":
        raise ValueError(f"No headcount plan '{plan_id}'.")


async def headcount_variance() -> Dict[str, Any]:
    """Planned vs live actual headcount per department (latest plan per department)."""
    plans = await pg_client.fetch(
        """SELECT DISTINCT ON (department) department, plan_id, fiscal_label, planned_headcount, created_at
           FROM headcount_plans ORDER BY department, created_at DESC""")
    actuals = await pg_client.fetch("SELECT department, COUNT(*) AS actual FROM employee_pii GROUP BY department")
    actual_by_dept = {r["department"]: int(r["actual"]) for r in actuals}

    out = []
    for p in plans:
        actual = actual_by_dept.get(p["department"], 0)
        planned = int(p["planned_headcount"])
        variance = actual - planned
        pct = round(variance / planned * 100, 1) if planned else None
        out.append({
            "department": p["department"], "fiscal_label": p["fiscal_label"],
            "planned_headcount": planned, "actual_headcount": actual,
            "variance": variance, "variance_pct": pct,
            "summary": (f"{p['department']} is "
                        f"{'over' if variance > 0 else 'under' if variance < 0 else 'at'} plan by "
                        f"{abs(variance)} ({p['fiscal_label']}: planned {planned}, actual {actual})."),
        })
    return {"departments": out}
