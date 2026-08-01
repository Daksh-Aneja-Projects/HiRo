"""Performance review cycles: a staged workflow (self-assessment -> manager review ->
calibration -> signed off) layered on top of the existing point-in-time
`performance_reviews` table, which sign-off still writes into so the rest of the
product (attrition risk, analytics) keeps reading one place for a person's rating.

Postgres-backed; each function takes/returns plain dicts so it is unit-testable
against a fake `pg_client` (see tests/test_hrsd_persistence.py for the pattern
this follows).
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.postgres_client import pg_client
from services import notification_service as notify_svc

logger = logging.getLogger(__name__)

STAGES = ["self_assessment", "manager_review", "calibration", "signed_off"]


class StageError(Exception):
    """The action doesn't match the cycle's current stage. Maps to HTTP 409."""


def _next_stage(stage: str) -> Optional[str]:
    idx = STAGES.index(stage)
    return STAGES[idx + 1] if idx + 1 < len(STAGES) else None


_DDL = """
CREATE TABLE IF NOT EXISTS public.perf_cycles (
    cycle_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    stage VARCHAR(20) NOT NULL DEFAULT 'self_assessment',
    opens_at DATE,
    closes_at DATE,
    created_by VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS public.perf_cycle_entries (
    id SERIAL PRIMARY KEY,
    cycle_id VARCHAR(50) NOT NULL REFERENCES public.perf_cycles(cycle_id),
    employee_uuid VARCHAR(50) NOT NULL REFERENCES public.employee_pii(employee_uuid),
    self_assessment TEXT,
    self_rating NUMERIC(2,1),
    manager_rating NUMERIC(2,1),
    manager_comments TEXT,
    calibrated_rating NUMERIC(2,1),
    signed_off_by_employee BOOLEAN NOT NULL DEFAULT FALSE,
    signed_off_at TIMESTAMPTZ,
    UNIQUE (cycle_id, employee_uuid)
);
CREATE INDEX IF NOT EXISTS idx_perf_cycle_entries_employee ON public.perf_cycle_entries (employee_uuid);
"""
_schema_ready = False


async def _ensure_schema() -> None:
    global _schema_ready
    if _schema_ready:
        return
    try:
        await pg_client.execute(_DDL)
    except Exception as e:
        logger.warning(f"Could not prepare the performance-cycle tables: {e}")
    _schema_ready = True


def _row_to_cycle(r: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "cycle_id": r["cycle_id"], "name": r["name"], "stage": r["stage"],
        "opens_at": str(r["opens_at"]) if r.get("opens_at") else None,
        "closes_at": str(r["closes_at"]) if r.get("closes_at") else None,
        "created_by": r.get("created_by"),
    }


def _row_to_entry(r: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "cycle_id": r["cycle_id"], "employee_uuid": r["employee_uuid"],
        "self_assessment": r.get("self_assessment"),
        "self_rating": float(r["self_rating"]) if r.get("self_rating") is not None else None,
        "manager_rating": float(r["manager_rating"]) if r.get("manager_rating") is not None else None,
        "manager_comments": r.get("manager_comments"),
        "calibrated_rating": float(r["calibrated_rating"]) if r.get("calibrated_rating") is not None else None,
        "signed_off_by_employee": bool(r.get("signed_off_by_employee")),
        "signed_off_at": r["signed_off_at"].isoformat() if r.get("signed_off_at") and hasattr(r["signed_off_at"], "isoformat") else r.get("signed_off_at"),
    }


async def employees_in_department(department: str) -> List[str]:
    """Everyone currently in one department, or the whole organisation for "all".

    HR opens a cycle over a population, not over a list of uuids typed by hand.
    Resolving the population server-side from the live employee records is the
    same thing comp cycles already do, and it means a cycle opened today covers
    who actually works there today.
    """
    if department and department.lower() != "all":
        rows = await pg_client.fetch(
            "SELECT employee_uuid FROM employee_pii WHERE department = $1 ORDER BY employee_uuid",
            department,
        )
    else:
        rows = await pg_client.fetch("SELECT employee_uuid FROM employee_pii ORDER BY employee_uuid")
    return [r["employee_uuid"] for r in rows]


async def create_cycle(*, name: str, opens_at, closes_at, employee_uuids: List[str],
                       created_by: str) -> Dict[str, Any]:
    await _ensure_schema()
    name = (name or "").strip()
    if not name:
        raise ValueError("A performance cycle needs a name.")
    if not employee_uuids:
        raise ValueError("At least one employee must be included in the cycle.")
    cycle_id = f"CYC-{uuid.uuid4().hex[:10].upper()}"
    async with pg_client.transaction("PerformanceCycles", "create_cycle"):
        await pg_client.execute(
            """INSERT INTO perf_cycles (cycle_id, name, stage, opens_at, closes_at, created_by)
               VALUES ($1, $2, 'self_assessment', $3, $4, $5)""",
            cycle_id, name, opens_at, closes_at, created_by,
        )
        for emp in employee_uuids:
            await pg_client.execute(
                """INSERT INTO perf_cycle_entries (cycle_id, employee_uuid) VALUES ($1, $2)
                   ON CONFLICT (cycle_id, employee_uuid) DO NOTHING""",
                cycle_id, emp,
            )
    for emp in employee_uuids:
        await notify_svc.notify(
            emp, notify_svc.KIND_PERFORMANCE,
            "A new performance cycle has started",
            f'"{name}" is open for self-assessment.',
            link="/employee-portal?module=performance", related_id=cycle_id,
        )
    return {"cycle_id": cycle_id, "name": name, "stage": "self_assessment",
            "employee_count": len(employee_uuids)}


async def list_cycles() -> List[Dict[str, Any]]:
    await _ensure_schema()
    rows = await pg_client.fetch("SELECT * FROM perf_cycles ORDER BY created_at DESC")
    return [_row_to_cycle(r) for r in rows]


async def get_cycle(cycle_id: str) -> Optional[Dict[str, Any]]:
    await _ensure_schema()
    row = await pg_client.fetchrow("SELECT * FROM perf_cycles WHERE cycle_id = $1", cycle_id)
    return _row_to_cycle(row) if row else None


_STAGE_NOTICE = {
    "manager_review": "Self-assessments are closed. Managers can now review their reports.",
    "calibration": "Manager reviews are closed. HR is calibrating ratings.",
    "signed_off": "Ratings are calibrated. You can now sign off on your review.",
}


async def advance_cycle_stage(cycle_id: str, advanced_by: str) -> Dict[str, Any]:
    cycle = await get_cycle(cycle_id)
    if not cycle:
        raise ValueError(f"There is no performance cycle with the id {cycle_id}.")
    nxt = _next_stage(cycle["stage"])
    if not nxt:
        raise StageError(f'"{cycle["name"]}" is already at its final stage (signed_off) and cannot be advanced further.')
    await pg_client.execute("UPDATE perf_cycles SET stage = $1 WHERE cycle_id = $2", nxt, cycle_id)
    entries = await pg_client.fetch("SELECT employee_uuid FROM perf_cycle_entries WHERE cycle_id = $1", cycle_id)
    notice = _STAGE_NOTICE.get(nxt, f"This cycle has moved to the {nxt} stage.")
    for e in entries:
        await notify_svc.notify(
            e["employee_uuid"], notify_svc.KIND_PERFORMANCE,
            f'"{cycle["name"]}" moved to {nxt.replace("_", " ")}', notice,
            link="/employee-portal?module=performance", related_id=cycle_id,
        )
    return {**cycle, "stage": nxt}


def _require_stage(cycle: Dict[str, Any], expected: str, action: str) -> None:
    if cycle["stage"] != expected:
        raise StageError(
            f'"{cycle["name"]}" is in the {cycle["stage"]} stage; {action} can only happen '
            f'during the {expected} stage.'
        )


async def submit_self_assessment(*, cycle_id: str, employee_uuid: str, self_assessment: str,
                                 self_rating: float) -> Dict[str, Any]:
    await _ensure_schema()
    cycle = await get_cycle(cycle_id)
    if not cycle:
        raise ValueError(f"There is no performance cycle with the id {cycle_id}.")
    _require_stage(cycle, "self_assessment", "self-assessments")
    row = await pg_client.fetchrow(
        """INSERT INTO perf_cycle_entries (cycle_id, employee_uuid, self_assessment, self_rating)
           VALUES ($1, $2, $3, $4)
           ON CONFLICT (cycle_id, employee_uuid)
           DO UPDATE SET self_assessment = EXCLUDED.self_assessment, self_rating = EXCLUDED.self_rating
           RETURNING *""",
        cycle_id, employee_uuid, self_assessment, self_rating,
    )
    await notify_svc.notify_manager_of(
        employee_uuid, notify_svc.KIND_PERFORMANCE,
        "A self-assessment is ready for your review",
        f'Your report submitted their self-assessment for "{cycle["name"]}".',
        link="/manager-portal?module=performance", related_id=cycle_id,
    )
    return _row_to_entry(row)


async def submit_manager_review(*, cycle_id: str, employee_uuid: str, manager_rating: float,
                                manager_comments: str, manager_uuid: str) -> Dict[str, Any]:
    await _ensure_schema()
    cycle = await get_cycle(cycle_id)
    if not cycle:
        raise ValueError(f"There is no performance cycle with the id {cycle_id}.")
    _require_stage(cycle, "manager_review", "manager reviews")
    owns = await pg_client.fetchrow(
        "SELECT 1 AS ok FROM employee_pii WHERE employee_uuid = $1 AND manager_id = $2",
        employee_uuid, manager_uuid,
    )
    if not owns:
        raise PermissionError("You can only review your own direct reports.")
    row = await pg_client.fetchrow(
        """INSERT INTO perf_cycle_entries (cycle_id, employee_uuid, manager_rating, manager_comments)
           VALUES ($1, $2, $3, $4)
           ON CONFLICT (cycle_id, employee_uuid)
           DO UPDATE SET manager_rating = EXCLUDED.manager_rating, manager_comments = EXCLUDED.manager_comments
           RETURNING *""",
        cycle_id, employee_uuid, manager_rating, manager_comments,
    )
    await notify_svc.notify(
        employee_uuid, notify_svc.KIND_PERFORMANCE,
        "Your manager completed your performance review",
        f'Your review for "{cycle["name"]}" has a manager rating now.',
        link="/employee-portal?module=performance", related_id=cycle_id,
    )
    return _row_to_entry(row)


async def calibrate_entry(*, cycle_id: str, employee_uuid: str, calibrated_rating: float) -> Dict[str, Any]:
    await _ensure_schema()
    cycle = await get_cycle(cycle_id)
    if not cycle:
        raise ValueError(f"There is no performance cycle with the id {cycle_id}.")
    _require_stage(cycle, "calibration", "calibration")
    row = await pg_client.fetchrow(
        """UPDATE perf_cycle_entries SET calibrated_rating = $1
           WHERE cycle_id = $2 AND employee_uuid = $3 RETURNING *""",
        calibrated_rating, cycle_id, employee_uuid,
    )
    if not row:
        raise ValueError("That employee has no entry in this cycle.")
    await notify_svc.notify(
        employee_uuid, notify_svc.KIND_PERFORMANCE,
        "Your rating has been calibrated",
        f'Your rating for "{cycle["name"]}" has been calibrated.',
        link="/employee-portal?module=performance", related_id=cycle_id,
    )
    return _row_to_entry(row)


async def sign_off(*, cycle_id: str, employee_uuid: str) -> Dict[str, Any]:
    """Employee acknowledgement. Writes the final rating into performance_reviews so the
    rest of the product (attrition risk, analytics) reads one place for a rating."""
    await _ensure_schema()
    cycle = await get_cycle(cycle_id)
    if not cycle:
        raise ValueError(f"There is no performance cycle with the id {cycle_id}.")
    _require_stage(cycle, "signed_off", "sign-off")
    entry_row = await pg_client.fetchrow(
        "SELECT * FROM perf_cycle_entries WHERE cycle_id = $1 AND employee_uuid = $2", cycle_id, employee_uuid
    )
    if not entry_row:
        raise ValueError("You have no entry in this cycle.")
    entry = _row_to_entry(entry_row)
    final_rating = entry["calibrated_rating"] or entry["manager_rating"] or entry["self_rating"]
    if final_rating is None:
        raise ValueError("There is no rating recorded for you in this cycle yet, so there is nothing to sign off on.")

    async with pg_client.transaction("PerformanceCycles", "sign_off"):
        await pg_client.execute(
            """UPDATE perf_cycle_entries SET signed_off_by_employee = TRUE, signed_off_at = NOW()
               WHERE cycle_id = $1 AND employee_uuid = $2""",
            cycle_id, employee_uuid,
        )
        manager_row = await pg_client.fetchrow(
            "SELECT manager_id FROM employee_pii WHERE employee_uuid = $1", employee_uuid
        )
        await pg_client.execute(
            """INSERT INTO performance_reviews (employee_uuid, overall_rating, review_period_end, reviewer_id)
               VALUES ($1, $2, CURRENT_DATE, $3)""",
            employee_uuid, float(final_rating), (manager_row or {}).get("manager_id"),
        )
    await notify_svc.notify_manager_of(
        employee_uuid, notify_svc.KIND_PERFORMANCE,
        "A report signed off on their review",
        f'Your report signed off on "{cycle["name"]}" with a final rating of {float(final_rating):g}.',
        link="/manager-portal?module=performance", related_id=cycle_id,
    )
    return {"status": "SIGNED_OFF", "cycle_id": cycle_id, "employee_uuid": employee_uuid,
            "final_rating": float(final_rating)}


async def get_my_cycle_entries(employee_uuid: str) -> List[Dict[str, Any]]:
    """Read-back for the self-assessments/sign-offs an employee has submitted."""
    await _ensure_schema()
    rows = await pg_client.fetch(
        """SELECT e.*, c.name, c.stage FROM perf_cycle_entries e
           JOIN perf_cycles c ON c.cycle_id = e.cycle_id
           WHERE e.employee_uuid = $1 ORDER BY c.created_at DESC""",
        employee_uuid,
    )
    return [{**_row_to_entry(r), "cycle_name": r["name"], "cycle_stage": r["stage"]} for r in rows]


async def list_cycle_entries(cycle_id: str) -> List[Dict[str, Any]]:
    """Every entry in one cycle, for HR calibration.

    Calibration is HR's step and works one employee at a time, so without a way
    to read the whole cycle there was no way to know which employees to calibrate
    or how one rating compared with the rest. Each entry carries the person's
    name and department, because calibration is exactly the comparison across
    teams that raw uuids make impossible.
    """
    await _ensure_schema()
    # Names live encrypted in the PII vault, so department and job title come
    # from the join and the name comes back through the vault helper the
    # succession and comp screens already share.
    rows = await pg_client.fetch(
        """SELECT e.*, p.department, p.job_title
           FROM perf_cycle_entries e
           LEFT JOIN employee_pii p ON p.employee_uuid = e.employee_uuid
           WHERE e.cycle_id = $1
           ORDER BY p.department NULLS LAST, e.manager_rating DESC NULLS LAST""",
        cycle_id,
    )
    from services.talent_intelligence import names_for_uuids
    names = await names_for_uuids([r["employee_uuid"] for r in rows])
    return [{
        **_row_to_entry(r),
        # names_for_uuids falls back to the uuid; a name we could not decrypt is
        # reported as absent rather than as a uuid pretending to be a name.
        "full_name": names.get(r["employee_uuid"]) if names.get(r["employee_uuid"]) != r["employee_uuid"] else None,
        "department": r.get("department"),
        "job_title": r.get("job_title"),
    } for r in rows]


async def list_cycle_entries_for_manager(cycle_id: str, manager_uuid: str,
                                         goals_summary_fn=None) -> List[Dict[str, Any]]:
    """Entries for this manager's own reports in one cycle, each with a goals
    achieved/total summary when a summary function (people_lifecycle.goals_summary,
    bound to a Mongo db) is supplied."""
    await _ensure_schema()
    rows = await pg_client.fetch(
        """SELECT e.* FROM perf_cycle_entries e
           JOIN employee_pii p ON p.employee_uuid = e.employee_uuid
           WHERE e.cycle_id = $1 AND p.manager_id = $2""",
        cycle_id, manager_uuid,
    )
    out = []
    for r in rows:
        entry = _row_to_entry(r)
        if goals_summary_fn:
            try:
                entry["goals"] = await goals_summary_fn(entry["employee_uuid"])
            except Exception as e:
                logger.warning(f"goals summary failed for {entry['employee_uuid']}: {e}")
                entry["goals"] = None
        out.append(entry)
    return out
