# services/workforce_planning_service.py - REPLACEMENT (Scenario Simulation Robustness)
"""Workforce Planning Service: AI-Driven Attrition and Scenario Modeling."""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from services.event_publisher_service import EventPublisherService
from services.postgres_client import pg_client

logger = logging.getLogger(__name__)

# Roles considered business-critical for succession/continuity planning.
CRITICAL_ROLES = ('manager', 'hrit_manager', 'hrit_admin', 'hrbp')


class WorkforcePlanningService:
    def __init__(self, publisher: EventPublisherService):
        self.publisher = publisher
        logger.info("WorkforcePlanningService Initialized")

    async def list_departments(self) -> List[str]:
        """The departments that actually exist, for filter controls."""
        try:
            rows = await pg_client.fetch(
                "SELECT DISTINCT department FROM public.employee_pii "
                "WHERE department IS NOT NULL AND department <> '' ORDER BY department"
            )
        except Exception as e:
            logger.warning(f"department list query failed: {e}")
            return []
        return [r["department"] for r in rows]

    async def get_current_projections(self, department: Optional[str] = None) -> Dict[str, Any]:
        """Real workforce state aggregated from the employee UDM (Postgres).

        Optionally scoped to one department, so an analytics filter actually
        changes the numbers instead of being decorative.

        Feeds the digital-twin risk simulation, which reads current_state
        (notably overall_risk_score + average_performance_score) as its base.
        """
        dept_filter = "WHERE department = $1" if department else ""
        args = [department] if department else []

        row = await pg_client.fetchrow(
            f"""
            SELECT
              COUNT(*)                                              AS total_employees,
              COUNT(*) FILTER (WHERE role IN {CRITICAL_ROLES})      AS critical_roles,
              ROUND(AVG(tenure_months))                             AS average_tenure_months,
              ROUND(AVG(dtla_risk_score)::numeric, 3)               AS overall_risk_score
            FROM public.employee_pii
            {dept_filter}
            """,
            *args,
        ) or {}

        if department:
            perf = await pg_client.fetchrow(
                """SELECT ROUND(AVG(r.overall_rating)::numeric, 2) AS avg_perf
                     FROM public.performance_reviews r
                     JOIN public.employee_pii e ON e.employee_uuid = r.employee_uuid
                    WHERE e.department = $1""",
                department,
            ) or {}
        else:
            perf = await pg_client.fetchrow(
                "SELECT ROUND(AVG(overall_rating)::numeric, 2) AS avg_perf FROM public.performance_reviews"
            ) or {}

        total = int(row.get('total_employees') or 0)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "current_state": {
                "total_employees": total,
                "critical_roles": int(row.get('critical_roles') or 0),
                "average_tenure_months": int(row.get('average_tenure_months') or 0),
                "average_performance_score": float(perf.get('avg_perf') or 0.0),
                "overall_risk_score": float(row.get('overall_risk_score') or 0.0),
            },
            "skill_gaps": await self._derive_skill_gaps(total),
            # Echo the scope so the caller can show what the numbers cover.
            "scope": department or "All departments",
        }

    async def get_analytics_charts(self, scatter_limit: int = 200) -> Dict[str, Any]:
        """Real chart series aggregated from the employee UDM + performance reviews.

        Feeds the Advanced Analytics dashboards with live data instead of placeholders:
        headcount and average attrition-risk per department, plus a performance-vs-tenure
        scatter sampled across the workforce.
        """
        dept_rows = await pg_client.fetch(
            """
            SELECT department,
                   COUNT(*)                                   AS headcount,
                   ROUND(AVG(dtla_risk_score)::numeric, 3)    AS avg_risk
            FROM public.employee_pii
            GROUP BY department
            ORDER BY headcount DESC
            """
        ) or []
        headcount_by_department = [
            {"name": r.get("department") or "Unknown", "value": int(r.get("headcount") or 0)}
            for r in dept_rows
        ]
        attrition_by_department = [
            {"name": r.get("department") or "Unknown",
             "value": round(float(r.get("avg_risk") or 0.0) * 100, 1)}
            for r in dept_rows
        ]

        scatter_rows = await pg_client.fetch(
            """
            SELECT e.tenure_months AS tenure, p.overall_rating AS rating, e.department
            FROM public.employee_pii e
            JOIN public.performance_reviews p ON p.employee_uuid = e.employee_uuid
            WHERE e.tenure_months IS NOT NULL AND p.overall_rating IS NOT NULL
            ORDER BY random()
            LIMIT $1
            """,
            scatter_limit,
        ) or []
        perf_vs_tenure = [
            {"tenure": int(r.get("tenure") or 0),
             "rating": round(float(r.get("rating") or 0.0), 2),
             "department": r.get("department") or "Unknown"}
            for r in scatter_rows
        ]

        return {
            "headcount_by_department": headcount_by_department,
            "attrition_by_department": attrition_by_department,
            "perf_vs_tenure": perf_vs_tenure,
        }

    async def _derive_skill_gaps(self, total_employees: int) -> Dict[str, str]:
        """Derives skill-gap severity from real department under-representation.

        Departments below their fair share of headcount are flagged as higher gap.
        """
        if not total_employees:
            return {}
        rows = await pg_client.fetch(
            "SELECT department, COUNT(*) AS c FROM public.employee_pii GROUP BY department"
        )
        if not rows:
            return {}
        fair_share = total_employees / len(rows)
        gaps: Dict[str, str] = {}
        for r in rows:
            ratio = (r['c'] or 0) / fair_share
            gaps[r['department'] or 'Unknown'] = (
                "HIGH" if ratio < 0.75 else "MEDIUM" if ratio < 1.0 else "LOW"
            )
        return gaps

    async def _load_employee_features(self, employee_uuid: str) -> Dict[str, Any]:
        """Read this employee's real features from the UDM.

        Without this the model scored whatever the caller passed, so every
        employee came back with an identical risk. Explicit values supplied by a
        what-if simulation still win; anything absent is read from the record.
        """
        features: Dict[str, Any] = {}
        try:
            row = await pg_client.fetchrow(
                """SELECT e.tenure_months, e.dtla_risk_score, e.department, e.job_title,
                          (SELECT AVG(overall_rating) FROM performance_reviews r
                             WHERE r.employee_uuid = e.employee_uuid) AS avg_rating,
                          (SELECT MAX(effective_date) FROM comp_history c
                             WHERE c.employee_uuid = e.employee_uuid) AS last_raise
                     FROM employee_pii e WHERE e.employee_uuid = $1""",
                employee_uuid,
            )
        except Exception as e:
            logger.warning(f"attrition features lookup failed for {employee_uuid}: {e}")
            return features

        if not row:
            return features

        if row.get("tenure_months") is not None:
            features["tenure_months"] = int(row["tenure_months"])
        if row.get("avg_rating") is not None:
            features["satisfaction_score"] = float(row["avg_rating"])
        if row.get("dtla_risk_score") is not None:
            features["dtla_risk_score"] = float(row["dtla_risk_score"])
        if row.get("last_raise"):
            months = (datetime.now(timezone.utc).date() - row["last_raise"]).days / 30.44
            features["last_raise_months"] = max(0, int(months))
        features["department"] = row.get("department")
        features["job_title"] = row.get("job_title")
        return features

    async def predict_attrition_risk(self, employee_data: Dict[str, Any]) -> Dict[str, Any]:
        # Ground the prediction in the employee's real record; caller-supplied
        # values (a what-if scenario) override what is on file.
        employee_uuid = employee_data.get('employee_uuid') or employee_data.get('employee_id')
        if employee_uuid:
            on_file = await self._load_employee_features(employee_uuid)
            employee_data = {**on_file, **{k: v for k, v in employee_data.items() if v is not None}}

        tenure = employee_data.get('tenure_months', 12)
        perf_score = employee_data.get('satisfaction_score', 3.0)
        comp_percentile = employee_data.get('compensation_percentile', 50)
        remote_days = employee_data.get('remote_days_per_week', 5)
        last_raise_months = employee_data.get('last_raise_months', 18)
        
        compa_ratio = 0.8 + (comp_percentile / 100.0) * 0.4

        # Each adjustment is recorded as it is applied, so the explanation can
        # report exactly what this model did instead of recomputing it with
        # weights of its own. The two used to disagree by up to ten points, and
        # the panel still told the reader the factors added up to the score.
        BASELINE = 0.4
        risk = BASELINE
        drivers = []

        def apply(feature, delta, reason):
            nonlocal risk
            risk += delta
            if abs(delta) >= 0.001:
                drivers.append({"feature": feature, "impact": round(delta, 3), "reason": reason})

        if 12 < tenure <= 36:
            apply("Tenure_Months", 0.15 * (1 - (tenure - 12) / 24),
                  f"At {tenure:g} months they are still in the stretch where people most often move on.")
        elif tenure < 12:
            apply("Tenure_Months", 0.05,
                  f"{tenure:g} months in, they are new enough that leaving is still easy.")
        else:
            apply("Tenure_Months", 0.0,
                  f"{tenure:g} months of service puts them past the point where most people leave.")

        rating_delta = -0.10 * (perf_score - 3.0) / 2.0
        apply("Performance_Score", rating_delta,
              (f"A rating of {perf_score:.1f} is below the level where people usually stay engaged."
               if rating_delta > 0 else
               f"A rating of {perf_score:.1f} is above average, which tends to go with staying."))

        if employee_data.get('compensation_percentile') is not None:
            if compa_ratio < 0.9:
                apply("Compensation_Ratio", 0.20,
                      f"They are paid below the market rate for this role ({compa_ratio:.2f} of it).")
            elif compa_ratio > 1.1:
                apply("Compensation_Ratio", -0.05,
                      f"They are paid above the market rate for this role ({compa_ratio:.2f} of it).")

        if last_raise_months > 24:
            apply("Last_Raise_Months", 0.10 * (last_raise_months - 24) / 12,
                  f"It has been {last_raise_months:g} months since their pay last changed.")
        
        # dtla_risk_score is the same model, computed in bulk over the whole
        # workforce (see scripts/recompute_attrition_risk.py). Blending it in
        # here would count the same signals twice and halve the effect of any
        # what-if adjustment the caller made, which is what made simulations
        # look weaker than they were. It is only a fallback now, for an employee
        # whose features could not be read.
        if not employee_data.get('tenure_months') and employee_data.get('dtla_risk_score') is not None:
            risk = float(employee_data['dtla_risk_score'])

        final_risk = min(1.0, max(0.0, risk))
        
        if final_risk > 0.85:
            level = "CRITICAL"
        elif final_risk > 0.6:
            level = "HIGH"
        elif final_risk > 0.3:
            level = "MEDIUM"
        else:
            level = "LOW"
            
        return {
            "employee_uuid": employee_data.get('employee_uuid', employee_data.get('employee_id', 'unknown')),
            "risk_score": round(final_risk, 3),
            "risk_level": level,
            "baseline_risk": BASELINE,
            "drivers": drivers,
            "feature_vector_used": {
                "tenure_months": tenure,
                "performance_score": round(float(perf_score), 2),
                # compa_ratio is only meaningful when a pay percentile was
                # actually supplied; otherwise it is the default and the
                # explanation must not show it as a per-person factor.
                "compa_ratio": (round(compa_ratio, 3)
                                if employee_data.get('compensation_percentile') is not None else None),
                "last_raise_months": last_raise_months,
                "remote_days_per_week": remote_days,
                "observed_risk_signal": employee_data.get('dtla_risk_score'),
            },
            # Says plainly whether this was scored against the real record.
            "source": "employee record" if employee_data.get("job_title") else "supplied values only",
            "department": employee_data.get("department"),
            "job_title": employee_data.get("job_title"),
            "recommendation": self._get_recommendation(level, compa_ratio, perf_score, last_raise_months)
        }

    def _get_recommendation(self, level, compa_ratio, perf_score, last_raise_months) -> str:
        if level == "CRITICAL":
            return "URGENT: Initiate executive intervention and financial review immediately."
        if level == "HIGH":
            if compa_ratio < 0.9 and last_raise_months > 12:
                return "CRITICAL: Review compensation and accelerate raise."
            if perf_score < 3.0:
                return "Prioritize mentorship and skill development plan."
            return "Conduct stay interview immediately to understand friction points."
        return "Maintain regular check-ins and review next-level opportunities."

    async def simulate_workforce_scenario(self, scenario: Dict[str, Any], state: Dict[str, Any]) -> float:
        """Simulates the impact of a scenario on the overall workforce risk."""
        drivers = [d.lower() for d in scenario.get('drivers', [])]
        
        # CRITICAL FIX: Robustly derive base_risk if 'overall_risk_score' is missing
        base_risk = state.get('current_state', {}).get('overall_risk_score')
        if base_risk is None:
            # Fallback heuristic: Use average risk (0.4) if data is missing
            base_risk = 0.4
        
        impact = 0.0
        
        # Complex simulation logic based on scenario drivers
        if "burnout" in drivers and state.get('current_state', {}).get('average_performance_score', 5.0) < 4.0:
            impact += 0.35 # High impact if performance is already low
        if "market competition" in drivers:
            impact += 0.20
        if "regulatory" in drivers:
            impact += 0.05
        if "economic downturn" in drivers:
            impact -= 0.1 # Downturn can decrease attrition risk
            
        magnitude = scenario.get('impact_magnitude_score', 0.5)
        
        final_risk = min(1.0, max(0.0, base_risk + (impact * magnitude)))
        return final_risk