# services/resource_prediction_agent.py
import asyncio
import logging
from typing import Dict, Any
from services.event_publisher_service import EventPublisherService 

class WorkforcePlanningService:
    async def get_current_projections(self):
        return {"skill_gaps": {"Engineering": 10, "Sales": 5}, "attrition_risk": 0.3}

logger = logging.getLogger(__name__)

class ResourcePredictionAgent:
    def __init__(self, publisher: EventPublisherService, wfp: WorkforcePlanningService):
        self.publisher = publisher
        self.wfp = wfp

    async def execute_prediction_task(self, task_data: Dict) -> Dict:
        """Adjusts forecast based on Risk Score."""
        
        try:
            risk = float(task_data.get('risk_score', 0.0))
        except (ValueError, TypeError):
             risk = 0.0
             logger.warning("Invalid risk_score provided. Defaulting to 0.0.")
        
        # 1. Fetch Current
        proj = await self.wfp.get_current_projections()
        
        try:
             current_gap = int(proj['skill_gaps'].get('Engineering', 10))
        except (ValueError, TypeError):
             current_gap = 10
             logger.warning("Invalid Engineering skill gap received. Defaulting to 10.")
        
        # 2. Adjust Multiplier (Heuristic)
        multiplier = 1.0
        if risk > 0.8: multiplier = 2.0
        elif risk > 0.6: multiplier = 1.5
        
        new_gap = int(current_gap * multiplier)
        delta_gap = new_gap - current_gap
        
        # 3. Action
        if delta_gap > 0:
            await self.publisher.publish_event(
                "Orchestrator_Command",
                {"target": "Hiring", "qty": delta_gap, "reason": f"High risk score {risk:.2f} triggered increased forecast."},
                key="RES_PRED"
            )
            logger.info(f"Hiring command published: {delta_gap} new engineers needed.")
        
        return {"status": "SUCCESS", "adjustment": new_gap, "delta_gap": delta_gap, "risk_score": risk}