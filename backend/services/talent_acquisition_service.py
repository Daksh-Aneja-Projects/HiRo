# services/talent_acquisition_service.py
"""Talent Acquisition Service: Advanced Pipeline Risk Modeling and Simulation."""
import asyncio
import logging
from typing import Dict, Any, List
from datetime import datetime, timezone
from services.event_publisher_service import EventPublisherService 

logger = logging.getLogger(__name__)

class TalentAcquisitionService:
    def __init__(self, publisher: EventPublisherService):
        self.publisher = publisher
        logger.info(" ✓  TalentAcquisitionService Initialized (Advanced Scoring Engine).")

    async def get_talent_pool_snapshot(self) -> Dict[str, Any]:
        """Fetches live metrics (Mocked as DB retrieval)."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pools": {
                "Engineering": {"size": 420, "ttc_days": 85, "acceptance_rate": 0.68, "open_reqs": 15}, # Added open_reqs
                "Sales": {"size": 800, "ttc_days": 40, "acceptance_rate": 0.92, "open_reqs": 3}
            }
        }

    async def simulate_talent_scenario(self, scenario: Dict[str, Any], state: Dict[str, Any]) -> float:
        """ 
        Calculates TA Risk based on Time-to-Commit (TTC), Offer Acceptance Rate (OAR), and Open Requisitions.
        Algorithm: Risk = (TTC / 120) * 0.4 + (1 - OAR) * 0.4 + (OpenReqs / 50) * 0.2
        """
        # 1. Extract Base Metrics
        # Assuming we focus the simulation on the Engineering pool for this mock
        eng_pool = state.get('talent_pools', {}).get('Engineering', {})
        base_ttc = eng_pool.get('ttc_days', 60)
        base_oar = eng_pool.get('acceptance_rate', 0.8)
        base_open_reqs = eng_pool.get('open_reqs', 10) 

        # 2. Apply Scenario Modifiers
        scenario_text = scenario.get('scenario_description', '').lower()
        ttc_modifier = 0
        oar_modifier = 0.0
        req_modifier = 0 # Modifier for open reqs

        if "competition" in scenario_text or "poaching" in scenario_text:
            ttc_modifier = 45 # Takes 45 days longer
            oar_modifier = -0.20 # 20% fewer accepts
            req_modifier = 5 # Need 5 more reqs open to match demand
        elif "reputation" in scenario_text:
            oar_modifier = -0.40
        elif "hiring freeze" in scenario_text:
            req_modifier = -5 # Reduces open reqs
            ttc_modifier = 10 # Longer TTC due to internal friction

        # 3. Calculate Final Scores
        final_ttc = base_ttc + ttc_modifier
        final_oar = max(0.0, base_oar + oar_modifier)
        final_reqs = max(0, base_open_reqs + req_modifier)

        # 4. Normalize Risk (Weights sum to 1.0)
        # TTC Risk: 120 days is 100% risk for this factor (Weight 0.4)
        ttc_risk_score = min(1.0, final_ttc / 120.0) * 0.4
        
        # OAR Risk: Lower acceptance = Higher risk (Weight 0.4)
        oar_risk_score = (1.0 - final_oar) * 0.4 
        
        # Open Reqs Risk: 50 open reqs is considered high risk (Weight 0.2)
        req_risk_score = min(1.0, final_reqs / 50.0) * 0.2
        
        # Weighted Total
        total_risk = ttc_risk_score + oar_risk_score + req_risk_score

        return max(0.0, min(1.0, total_risk))