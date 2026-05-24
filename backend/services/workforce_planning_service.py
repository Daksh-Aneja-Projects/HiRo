# services/workforce_planning_service.py - REPLACEMENT (Scenario Simulation Robustness)
"""Workforce Planning Service: AI-Driven Attrition and Scenario Modeling."""
import asyncio
import logging
from typing import Dict, Any, List
from datetime import datetime, timezone
from services.event_publisher_service import EventPublisherService 

logger = logging.getLogger(__name__)

class WorkforcePlanningService:
    def __init__(self, publisher: EventPublisherService):
        self.publisher = publisher
        logger.info("WorkforcePlanningService Initialized")

    async def get_current_projections(self) -> Dict[str, Any]:
        """Fetches current workforce state and skill gap projections (Mocked DB call)."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "current_state": {
                "total_employees": 15000,
                "critical_roles": 1200,
                "average_tenure_months": 36,
                "global_compliance_index": 0.985,
                "average_performance_score": 3.8, 
                "open_requisitions": 45
            },
            "skill_gaps": {"LLM_Ops": "HIGH", "Cyber_Security": "MEDIUM", "Leadership": "LOW"}
        }

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