# services/total_talent_digital_twin_agent.py
"""Total Talent Digital Twin Agent (DTLA): Integrated with central AIService and Event Publisher for autonomous remediation."""
import asyncio
import logging
import json
import uuid
from typing import Dict, Any, Tuple, List
from datetime import datetime, timezone
from config.settings import settings
from services.ai_services import AIService 
from services.event_publisher_service import EventPublisherService
from services.workforce_planning_service import WorkforcePlanningService 
from services.talent_acquisition_service import TalentAcquisitionService 

logger = logging.getLogger(__name__)

DTLA_AGENT_ID = "DigitalTwinAgent"
SCENARIO_RUN_INTERVAL_SECONDS = getattr(settings, 'DTLA_SCENARIO_INTERVAL_SECONDS', 3600 * 12) 
CRITICAL_RISK_THRESHOLD = getattr(settings, 'DTLA_RISK_THRESHOLD', 0.8) 
DTLA_CRITICAL_RISK_TOPIC = getattr(settings, 'DTLA_CRITICAL_RISK_TOPIC', "dtla.critical_risk")

class DigitalTwinAgent:
    def __init__(self,                 
                 publisher: EventPublisherService,                 
                 ai_service: AIService,                 
                 wfp_service: WorkforcePlanningService,                 
                 ta_service: TalentAcquisitionService):
        self.publisher = publisher   
        self.ai_service = ai_service
        self.wfp_service = wfp_service
        self.ta_service = ta_service
        self.risk_threshold = CRITICAL_RISK_THRESHOLD
        
        if not hasattr(publisher, 'TOPIC_DTLA_SCENARIO'):             
             publisher.TOPIC_DTLA_SCENARIO = DTLA_CRITICAL_RISK_TOPIC 

        logger.info(f" ✓  DTLA Initialized (Risk Threshold: {self.risk_threshold}).")

    async def _fetch_digital_twin_state(self) -> Dict[str, Any]:
        """Fetches the composite state of the entire workforce DT by aggregating WFP and TA data."""
        
        # Fetch data from WFP
        wfp_data = await self.wfp_service.get_current_projections()
        
        # Fetch data from TA
        ta_snapshot = await self.ta_service.get_talent_pool_snapshot()

        return {
            "workforce_state": wfp_data.get("current_state", {}),
            "skill_gaps": wfp_data.get("skill_gaps", {}),
            "talent_pools": ta_snapshot.get("pools", {}),
            "open_requisitions": sum(p.get("size", 0) for p in ta_snapshot.get("pools", {}).values()),
            "overall_risk_factors": [
                {"factor": "skill_gaps", "severity": wfp_data['skill_gaps'].get('LLM_Ops')},
            ],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    async def generate_autonomous_scenario(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Uses AI to generate a plausible future scenario (e.g., skill obsolescence, market competition).
        """
        prompt = (
            f"Analyze the current total talent state (workforce and acquisition data): {json.dumps(state)} and generate a single, plausible "
            f"future scenario that could impact the combined workforce. Scenario should be critical. Output only JSON."
        )

        try:
            scenario = await self.ai_service.generate_json_response(
                prompt=prompt,
                response_schema={
                    "type": "object",
                    "properties": {
                        "scenario_id": {"type": "string"},
                        "scenario_description": {"type": "string"},
                        "impact_magnitude_score": {"type": "number", "minimum": 0.0, "maximum": 1.0}, # Enforce range
                        "drivers": {"type": "array", "items": {"type": "string"}}
                    }
                },
                task_type="simulation_generation"
            )
            scenario["scenario_id"] = f"AI_{uuid.uuid4().hex[:8].upper()}"
            return scenario
        except Exception as e:
            logger.error(f"AI Generation failed: {e}")
            return {
                "scenario_id": "FALLBACK",
                "scenario_description": "Standard market volatility and high-skill attrition risk.",
                "impact_magnitude_score": 0.8, # Default to high risk to force attention
                "drivers": ["market_competition", "unmitigated_attrition"]
            }  

    async def _simulate_scenario_impact(self, scenario: Dict[str, Any], state: Dict[str, Any]) -> Tuple[float, str]:
        """Runs the scenario through the deterministic WFP and TA engines for a combined risk score."""
        
        # Get individual risk scores
        wfp_risk = await self.wfp_service.simulate_workforce_scenario(scenario, state)
        ta_risk = await self.ta_service.simulate_talent_scenario(scenario, state)

        if wfp_risk is None or ta_risk is None:
            # No measured baseline means no risk figure. Returning a number here
            # would be inventing the one input the whole simulation rests on.
            return None, ("This could not be simulated: the workforce has no measured "
                          "baseline risk yet, so there is no starting point to model from.")

        # Weighted aggregation (giving more weight to WFP as it reflects current employees)
        total_risk = (wfp_risk * 0.6) + (ta_risk * 0.4)
        total_risk = max(0.0, min(1.0, total_risk)) # Cap between 0 and 1

        recommendation = "Monitor situation and execute low-cost retention strategies."
        if total_risk > self.risk_threshold:
            recommendation = (f"CRITICAL: Initiate immediate executive review and resource reallocation. "
                              f"Workforce Risk: {wfp_risk:.2f}, Talent Risk: {ta_risk:.2f}.")

        return total_risk, recommendation

    async def async_run_prescriptive_simulation(self, scenario_data: Dict[str, Any]) -> Dict[str, Any]:
        """Public endpoint for Orchestrator to run on-demand simulations."""
        state = await self._fetch_digital_twin_state() 
        risk, rec = await self._simulate_scenario_impact(scenario_data, state)

        # `risk is None` means the scenario was unanswerable, not that it was safe.
        if risk is not None and risk >= self.risk_threshold:
             await self.publisher.publish_event(
                topic=DTLA_CRITICAL_RISK_TOPIC,
                payload={
                    "alert_id": f"ALERT_{uuid.uuid4().hex[:8].upper()}",
                    "risk_score": risk,
                    "recommendation": rec,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                key=scenario_data.get('simulation_id', 'SYSTEM')
            )
        
        return { 
            "simulation_id": scenario_data.get('simulation_id', uuid.uuid4().hex),
            "risk_score": risk,
            "recommendation": rec,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "state_used_for_simulation": state # Return state for XAI analysis
        }

    async def monitor_and_act(self):
        """Background job for continuous monitoring and autonomous action."""
        # ... (Implementation remains the same as original to preserve background loop functionality)
        # Note: Need to copy/paste the original full monitor_and_act if required, but for brevity, 
        # acknowledging it should be retained. The placeholder version in the uploaded file is below:
        while True:
            await asyncio.sleep(SCENARIO_RUN_INTERVAL_SECONDS)
            try:
                state = await self._fetch_digital_twin_state()
                scenario = await self.generate_autonomous_scenario(state)
                risk, recommendation = await self._simulate_scenario_impact(scenario, state)

                if risk is None:
                    logger.info(f"DTLA Monitor: Scenario '{scenario['scenario_description'][:30]}' "
                                f"could not be scored: {recommendation}")
                    continue

                logger.info(f"DTLA Monitor: Scenario '{scenario['scenario_description'][:30]}' -> Risk: {risk:.2f}")

                if risk >= self.risk_threshold:
                    logger.warning(f"DTLA Critical Risk Detected: {risk:.2f}")
                    await self.publisher.publish_event(
                        topic=DTLA_CRITICAL_RISK_TOPIC,
                        payload={
                            "alert_id": f"ALERT_{uuid.uuid4().hex[:8].upper()}",
                            "risk_score": risk,
                            "recommendation": recommendation,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        },
                        key="CRITICAL_RISK"
                    )
            except Exception as e:
                logger.error(f"DTLA monitor failed: {e}")


# Note: Since services/digital_twin_agent.py is logically superseded by this file, 
# you should consider replacing it entirely with a simple re-export or a deprecated stub 
# if it is still being imported elsewhere.