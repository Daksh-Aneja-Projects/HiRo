# services/digital_twin_agent.py
import asyncio
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone
import json
import uuid
from config.settings import settings
from services.ai_services import AIService
from services.event_publisher_service import EventPublisherService
from services.workforce_planning_service import WorkforcePlanningService
from services.talent_acquisition_service import TalentAcquisitionService

logger = logging.getLogger(__name__)

DTLA_AGENT_ID = "DigitalTwinAgent"
SCENARIO_RUN_INTERVAL_SECONDS = getattr(settings, 'DTLA_SCENARIO_INTERVAL_SECONDS', 3600 * 12)
CRITICAL_RISK_THRESHOLD = getattr(settings, 'DTLA_RISK_THRESHOLD', 0.8)


class DigitalTwinAgent:
    def __init__(
        self,
        publisher: EventPublisherService,
        ai_service: AIService,
        wfm_service: WorkforcePlanningService, 
        ta_service: TalentAcquisitionService
    ):
        self.publisher = publisher
        self.ai_service = ai_service
        self.wfm_service = wfm_service
        self.ta_service = ta_service
        self.is_running = False
        self.active_twins: Dict[str, Any] = {}
        self._monitor_task: Optional[asyncio.Task] = None
        
        if not hasattr(publisher, 'TOPIC_DTLA_SCENARIO'):
             publisher.TOPIC_DTLA_SCENARIO = "dtla.scenario.generated"
             
        logger.info(f"{DTLA_AGENT_ID} Initialized")

    async def _fetch_digital_twin_state(self) -> Dict[str, Any]:
        workforce_state = {}
        skill_inventory = {}
        talent_pools = {}

        try:
            try:
                wfp_projections = await self.wfm_service.get_current_projections()
                workforce_state = wfp_projections.get('current_state', {})
                skill_inventory = wfp_projections.get('skill_gaps', {})
            except Exception as e:
                logger.warning(f"WFM service failed during state fetch: {e}")

            try:
                talent_pool_snapshot = await self.ta_service.get_talent_pool_snapshot()
                talent_pools = talent_pool_snapshot.get('pools', {})
            except Exception as e:
                logger.warning(f"Talent service failed during state fetch: {e}")

        except Exception as e:
            logger.error(f"Error fetching digital twin state: {e}")

        return {
            "workforce_state": workforce_state,
            "skill_inventory": skill_inventory,
            "talent_pools": talent_pools,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    async def _generate_risk_scenario(self, workforce_state: Dict[str, Any]) -> Dict[str, Any]:
        scenario_prompt = f"""
        Act as a Futurist Analyst. Based on workforce data:
        {json.dumps(workforce_state, indent=2)}
        Generate one high-impact scenario. Return JSON:
        scenario_description, drivers, impact_magnitude_score, time_horizon.
        """

        try:
            scenario_json = await self.ai_service.generate_json_response(
                prompt=scenario_prompt,
                task_type="structured_generation",
                response_schema={
                    "type": "object",
                    "properties": {
                        "scenario_description": {"type": "string"},
                        "drivers": {"type": "array", "items": {"type": "string"}},
                        "impact_magnitude_score": {"type": "number", "minimum": 0, "maximum": 1},
                        "time_horizon": {"type": "string"}
                    }
                }
            )

            if scenario_json and 'impact_magnitude_score' in scenario_json:
                scenario_json['scenario_id'] = await asyncio.to_thread(
                    lambda: f"SCENARIO_{uuid.uuid4().hex[:8].upper()}"
                )
                return scenario_json

            raise ValueError("LLM returned unusable structure")

        except Exception as e:
            # This used to return a scenario with an invented 0.3 impact and the
            # drivers "market" and "burnout", which reached the screen looking
            # exactly like a real one. A scenario nobody generated must not be
            # presented as a scenario.
            logger.error(f"LLM Scenario Generation failed: {e}")
            return {
                "scenario_id": None,
                "scenario_description": "No scenario could be generated: the model was unavailable.",
                "impact_magnitude_score": None,
                "drivers": [],
                "time_horizon": None,
                "available": False,
            }
            
    async def _simulate_scenario_impact(
        self, scenario: Dict[str, Any], state: Dict[str, Any]
    ) -> Tuple[float, str]:

        wfm_risk_score = 0.3
        ta_risk_score = 0.3

        try:
            wfm_risk_score = await self.wfm_service.simulate_workforce_scenario(
                scenario, state
            )

            ta_risk_score = await self.ta_service.simulate_talent_scenario(
                scenario, state
            )

            if wfm_risk_score is None or ta_risk_score is None:
                # One of the engines had no measured baseline to work from.
                # Aggregating around the gap would manufacture a risk figure.
                return None, ("This could not be simulated: the workforce has no measured "
                              "baseline risk yet, so there is no starting point to model from.")

            aggregated_risk = (wfm_risk_score * 0.6) + (ta_risk_score * 0.4)
            mitigation_recommendation = self._generate_mitigation_recommendation(
                aggregated_risk,
                scenario.get('drivers', []),
                wfm_risk_score,
                ta_risk_score
            )

            return aggregated_risk, mitigation_recommendation

        except Exception as e:
            # 0.3 was a made-up risk figure presented as a computed one.
            logger.error(f"Scenario simulation failed: {e}")
            return None, "This could not be simulated, so there is no risk figure to show."

    def _generate_mitigation_recommendation(
        self,
        aggregated_risk: float,
        drivers: List[str],
        wfm_score: float,
        ta_score: float
    ) -> str:
        recommendations = []

        if aggregated_risk >= CRITICAL_RISK_THRESHOLD:
            recommendations.append("CRITICAL: Activate emergency protocol")

        if wfm_score >= 0.7:
            recommendations.append("High workforce risk: Review capacity planning")

        if ta_score >= 0.7:
            recommendations.append("High talent risk: Accelerate hiring & retention")

        if "attrition" in [d.lower() for d in drivers]:
            recommendations.append("Attrition risk: Implement retention actions")

        if "skill" in [d.lower() for d in drivers]:
            recommendations.append("Skill gap: Launch upskilling programs")

        if not recommendations:
            recommendations.append("Monitor metrics")

        return " | ".join(recommendations)

    async def monitor_and_proactively_remediate(self):
        if self.is_running:
            logger.warning("Digital Twin Agent already running.")
            return

        self.is_running = True
        logger.info("DTLA monitoring task started.")

        try:
            while self.is_running:
                try:
                    start_time = datetime.now(timezone.utc)

                    current_state = await self._fetch_digital_twin_state()
                    scenario = await self._generate_risk_scenario(current_state)

                    risk_score, mitigation_prompt = await self._simulate_scenario_impact(
                        scenario, current_state
                    )

                    if risk_score is not None and risk_score >= CRITICAL_RISK_THRESHOLD:
                        if self.publisher and hasattr(self.publisher, 'publish_event'):
                            await self.publisher.publish_event(
                                topic=self.publisher.TOPIC_DTLA_SCENARIO, 
                                payload={
                                    "event_type": "PROACTIVE_RISK_DETECTED",
                                    "scenario_id": scenario['scenario_id'],
                                    "impact_magnitude": risk_score,
                                    "mitigation_prompt": mitigation_prompt,
                                    "scenario_details": scenario,
                                    "detected_at": datetime.now(timezone.utc).isoformat()
                                },
                                key=scenario['scenario_id']
                            )

                    elapsed_time = (datetime.now(timezone.utc) - start_time).total_seconds()
                    sleep_time = max(60, SCENARIO_RUN_INTERVAL_SECONDS - elapsed_time)

                    await asyncio.sleep(sleep_time)

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in DTLA cycle: {e}")
                    await asyncio.sleep(300)

        except asyncio.CancelledError:
            pass
        finally:
            self.is_running = False
            logger.info("DTLA monitoring stopped.")

    async def start_monitoring(self):
        if not self.is_running:
            self._monitor_task = asyncio.create_task(self.monitor_and_proactively_remediate())

    async def stop_monitoring(self):
        self.is_running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None

    async def execute_dtla_command(self, data: Dict[str, Any]) -> Dict[str, Any]:
        command_type = data.get("command_type")
        requester_id = data.get("requester_id", "ANONYMOUS")

        if command_type == "RUN_SCENARIO":
            user_scenario = data.get("scenario", {})
            if not isinstance(user_scenario, dict):
                raise ValueError("Scenario must be a dictionary")

            current_state = await self._fetch_digital_twin_state()
            risk_score, recommendation = await self._simulate_scenario_impact(
                user_scenario, current_state
            )

            if risk_score is None:
                return {
                    "status": "UNAVAILABLE",
                    "risk_score": None,
                    "recommendation": recommendation,
                    "message": "This scenario could not be simulated, so there is no result to show.",
                    "requester": requester_id,
                    "scenario_id": user_scenario.get('scenario_id', 'USER_SCENARIO'),
                }
            return {
                "status": "SUCCESS",
                "risk_score": risk_score,
                "recommendation": recommendation,
                "message": "Scenario simulation complete",
                "requester": requester_id,
                "scenario_id": user_scenario.get('scenario_id', 'USER_SCENARIO')
            }

        elif command_type == "GET_STATE":
            state = await self._fetch_digital_twin_state()
            return {
                "status": "SUCCESS",
                "current_state": state,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

        elif command_type == "create_twin":
            twin_id = data.get("twin_id", "default_org_twin")

            if twin_id in self.active_twins:
                return {
                    "status": "SUCCESS",
                    "twin_id": twin_id,
                    "message": "Twin already active."
                }

            self.active_twins[twin_id] = {
                "id": twin_id,
                "status": "active",
                "created_by": requester_id,
                "created_at": datetime.now(timezone.utc).isoformat()
            }

            return {
                "status": "SUCCESS",
                "twin_id": twin_id,
                "message": "Digital Twin created."
            }

        elif command_type == "GET_MONITORING_STATUS":
            return {
                "status": "SUCCESS",
                "is_running": self.is_running,
                "active_twins": len(self.active_twins),
                "last_cycle": datetime.now(timezone.utc).isoformat() if self.is_running else "Not running"
            }

        else:
            return {"status": "ERROR", "message": f"Unknown DTLA command: {command_type}"}

    def __del__(self):
        if self.is_running:
            pass