# services/workforce_planning_service.py - REPLACEMENT (Scenario Simulation Robustness)
"""Workforce Planning Service: AI-Driven Attrition and Scenario Modeling."""
import asyncio
import logging
from typing import Dict, Any, List
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

    async def get_current_projections(self) -> Dict[str, Any]:
        """Real workforce state aggregated from the employee UDM (Postgres).

        Feeds the digital-twin risk simulation, which reads current_state
        (notably overall_risk_score + average_performance_score) as its base.
        """
        row = await pg_client.fetchrow(
            f"""
            SELECT
              COUNT(*)                                              AS total_employees,
              COUNT(*) FILTER (WHERE role IN {CRITICAL_ROLES})      AS critical_roles,
              ROUND(AVG(tenure_months))                             AS average_tenure_months,
              ROUND(AVG(dtla_risk_score)::numeric, 3)               AS overall_risk_score
            FROM public.employee_pii
            """
        ) or {}
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

    async def predict_attrition_risk(self, employee_data: Dict[str, Any]) -> Dict[str, Any]:
        tenure = employee_data.get('tenure_months', 12)
        perf_score = employee_data.get('satisfaction_score', 3.0)
        comp_percentile = employee_data.get('compensation_percentile', 50)
        remote_days = employee_data.get('remote_days_per_week', 5)
        last_raise_months = employee_data.get('last_raise_months', 18)
        
        compa_ratio = 0.8 + (comp_percentile / 100.0) * 0.4
        
        risk = 0.4 
        
        if 12 < tenure <= 36:
            risk += 0.15 * (1 - (tenure - 12) / 24)
        elif tenure < 12:
            risk += 0.05
        
        risk -= 0.10 * (perf_score - 3.0) / 2.0
        
        if compa_ratio < 0.9:
            risk += 0.20
        elif compa_ratio > 1.1:
            risk -= 0.05
            
        if last_raise_months > 24:
            risk += 0.10 * (last_raise_months - 24) / 12
        
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
            "feature_vector_used": {
                "tenure_months": tenure,
                "performance_score": perf_score,
                "compa_ratio": round(compa_ratio, 3),
                "last_raise_months": last_raise_months,
                "remote_days_per_week": remote_days
            },
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