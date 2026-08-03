# services/workforce_planning_service.py
"""Workforce Planning Service: AI-Driven Attrition and Scenario Modeling."""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from services.event_publisher_service import EventPublisherService
from services.postgres_client import pg_client
from services.skill_requirements import REQUIRED_SKILLS
from services.career_ladders import LADDERS
from config.settings import settings

logger = logging.getLogger(__name__)

# Roles considered business-critical for succession/continuity planning.
CRITICAL_ROLES = ('manager', 'hrit_manager', 'hrit_admin', 'hrbp')


class WorkforcePlanningService:
    def __init__(self, publisher: EventPublisherService, mongo_client=None):
        self.publisher = publisher
        # Skill profiles live in Mongo; without them the gap analysis has
        # nothing to measure and says so rather than inventing a severity.
        self.mongo_client = mongo_client
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
            # Named skills rather than a severity label, and real succession
            # cover rather than the same vector inverted.
            "skill_gap_detail": await self.skill_gap_detail(),
            "succession_readiness": await self.succession_readiness(),
            # Echo the scope so the caller can show what the numbers cover.
            "scope": department or "All departments",
        }

    async def get_analytics_charts(self, scatter_limit: int = 200,
                                   department: Optional[str] = None) -> Dict[str, Any]:
        """Real chart series aggregated from the employee UDM + performance reviews.

        Feeds the Advanced Analytics dashboards with live data instead of placeholders:
        headcount and average attrition-risk per department, plus a performance-vs-tenure
        scatter sampled across the workforce.
        """
        # The department filter used to change the four stat cards and leave
        # every chart below them company-wide, so filtering to a department of
        # one still showed a fourteen-bar chart of the whole organisation
        # presented as the filtered view.
        where = "WHERE department = $1" if department else ""
        args = [department] if department else []
        dept_rows = await pg_client.fetch(
            f"""
            SELECT department,
                   COUNT(*)                                   AS headcount,
                   ROUND(AVG(dtla_risk_score)::numeric, 3)    AS avg_risk
            FROM public.employee_pii
            {where}
            GROUP BY department
            ORDER BY headcount DESC
            """,
            *args,
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
              AND ($2::text IS NULL OR e.department = $2)
            -- A stable sample. ORDER BY random() returned a different set of
            -- points on every load, so the same chart never looked the same
            -- twice and nothing on it could be pointed at.
            ORDER BY md5(e.employee_uuid)
            LIMIT $1
            """,
            scatter_limit, department,
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
        """How much of what a department needs to be able to do it can actually do.

        This used to read `SELECT department, COUNT(*)` and call a department
        below its fair share of headcount a HIGH skills gap. No skills data was
        consulted at all, so a department with one person in it was reported as
        critically short of skills, and the succession chart beside it was the
        same headcount vector subtracted from four.

        A skill counts as covered when enough of the department holds it that
        losing one person would not remove it.
        """
        try:
            profiles = await self._skill_profiles()
        except Exception as e:
            logger.warning(f"skill profiles unavailable: {e}")
            return {}
        if not profiles:
            return {}

        gaps: Dict[str, str] = {}
        for department, (headcount, held_counts) in profiles.items():
            needed = REQUIRED_SKILLS.get(department)
            if not needed:
                continue
            threshold = max(1, headcount * 0.25)
            covered = sum(1 for skill in needed if held_counts.get(skill, 0) >= threshold)
            share = covered / len(needed)
            gaps[department] = "LOW" if share >= 0.7 else "MEDIUM" if share >= 0.45 else "HIGH"
        return gaps

    async def skill_gap_detail(self) -> List[Dict[str, Any]]:
        """Which skills each department is short of, by name.

        A severity label on its own tells an HRBP nothing they can act on.
        """
        profiles = await self._skill_profiles()
        detail: List[Dict[str, Any]] = []
        for department, (headcount, held_counts) in sorted(profiles.items()):
            needed = REQUIRED_SKILLS.get(department)
            if not needed:
                continue
            threshold = max(1, headcount * 0.25)
            missing = [s for s in needed if held_counts.get(s, 0) < threshold]
            detail.append({
                "department": department,
                "headcount": headcount,
                "skills_needed": len(needed),
                "skills_covered": len(needed) - len(missing),
                "missing_skills": missing,
                "summary": (f"{department} covers {len(needed) - len(missing)} of the "
                            f"{len(needed)} skills the work needs."
                            + (f" Short of: {', '.join(missing)}." if missing else "")),
            })
        return detail

    async def succession_readiness(self) -> Dict[str, Dict[str, Any]]:
        """Whether each department has anyone ready to step into its senior roles.

        The succession chart was the skills-gap vector subtracted from four, so
        the two charts on that screen were one number and its inverse, and
        neither had anything to do with succession.

        Someone counts as ready when they sit on a rung just below a senior role,
        have been here long enough to know the place, and are rated well enough
        to be trusted with the step up.

        Aggregated in the database rather than row by row: the first version
        pulled all 21,470 employees with a correlated subquery each and made the
        whole API time out.
        """
        cached = self._cached("succession")
        if cached is not None:
            return cached

        senior, ready = {}, {}
        for department, ladder in LADDERS.items():
            senior_from = max(1, len(ladder) - 2)
            senior[department] = ladder[senior_from:]
            ready[department] = ladder[max(0, senior_from - 2):senior_from]

        rows = await pg_client.fetch(
            """SELECT e.department, e.job_title,
                      COUNT(*) FILTER (WHERE e.tenure_months >= 24 AND r.rating >= 3.5) AS ready,
                      COUNT(*) AS people
               FROM employee_pii e
               LEFT JOIN (SELECT employee_uuid, AVG(overall_rating) AS rating
                          FROM performance_reviews GROUP BY employee_uuid) r
                 ON r.employee_uuid = e.employee_uuid
               WHERE e.department IS NOT NULL AND e.job_title IS NOT NULL
               GROUP BY e.department, e.job_title""")

        totals: Dict[str, Dict[str, int]] = {}
        for row in rows:
            department, title = row["department"], row["job_title"]
            bucket = totals.setdefault(department, {"senior_roles": 0, "ready": 0})
            if title in senior.get(department, []):
                bucket["senior_roles"] += int(row["people"])
            elif title in ready.get(department, []):
                bucket["ready"] += int(row["ready"])

        result: Dict[str, Dict[str, Any]] = {}
        for department, b in totals.items():
            if not b["senior_roles"]:
                continue
            result[department] = {
                "senior_roles": b["senior_roles"],
                "ready_successors": b["ready"],
                "readiness": round(min(1.0, b["ready"] / b["senior_roles"]), 3),
                "summary": (
                    f"{department} has {b['ready']} people ready for its "
                    f"{b['senior_roles']} senior {'role' if b['senior_roles'] == 1 else 'roles'}"
                    + (", comfortable cover." if b["ready"] >= b["senior_roles"]
                       else f", so {b['senior_roles'] - b['ready']} would have no obvious successor.")),
            }
        return self._cache("succession", result)

    # Workforce-wide aggregates change slowly and are read on every dashboard
    # load, so they are held briefly rather than recomputed per request.
    _CACHE_TTL_SECONDS = 120

    def _cached(self, key: str):
        entry = getattr(self, "_agg_cache", {}).get(key)
        if not entry:
            return None
        stamped, value = entry
        if (datetime.now(timezone.utc) - stamped).total_seconds() > self._CACHE_TTL_SECONDS:
            return None
        return value

    def _cache(self, key: str, value):
        if not hasattr(self, "_agg_cache"):
            self._agg_cache = {}
        self._agg_cache[key] = (datetime.now(timezone.utc), value)
        return value

    async def _skill_profiles(self):
        """Per department: headcount, and how many people hold each skill."""
        if self.mongo_client is None:
            return {}
        cached = self._cached("skills")
        if cached is not None:
            return cached
        counts = await pg_client.fetch(
            "SELECT department, COUNT(*) AS c FROM public.employee_pii GROUP BY department")
        headcounts = {r["department"]: int(r["c"] or 0) for r in counts if r["department"]}

        db = self.mongo_client[settings.MONGO_DB_NAME]
        cursor = db["employee_skills"].aggregate([
            {"$unwind": "$skills"},
            {"$group": {"_id": {"d": "$department", "s": "$skills"}, "n": {"$sum": 1}}},
        ])
        held: Dict[str, Dict[str, int]] = {}
        async for row in cursor:
            department = (row["_id"] or {}).get("d")
            skill = (row["_id"] or {}).get("s")
            if department and skill:
                held.setdefault(department, {})[skill] = int(row["n"])

        return self._cache("skills", {d: (headcounts.get(d, 0), held.get(d, {})) for d in headcounts})

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

    async def simulate_workforce_scenario(self, scenario: Dict[str, Any], state: Dict[str, Any]) -> Optional[float]:
        """Simulates the impact of a scenario on the overall workforce risk.

        Returns None when the workforce has no measured baseline risk. This used
        to silently substitute 0.4 -- an invented starting point that every
        downstream figure was then computed from, presented to the caller as a
        measurement. A scenario with no baseline is unanswerable, and saying so
        is the only honest result.
        """
        drivers = [d.lower() for d in scenario.get('drivers', [])]

        base_risk = state.get('current_state', {}).get('overall_risk_score')
        if base_risk is None:
            logger.warning("Workforce scenario has no measured baseline risk; returning None.")
            return None

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