import logging
import numpy as np
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
# FIX: Added placeholders for missing services
class DigitalTwinAgent:
    # NOTE: This placeholder class is only used here to prevent circular imports if necessary,
    # but the runtime uses the injected instance from server.py.
    async def execute_dtla_command(self, command: Dict):
        # CRITICAL FIX: Simulate a more realistic response structure
        return {"risk_score": 0.5, "recommendation": "Mocked DTLA result.", "attrition_probability": 0.25}

class AdvancedAIServices:
    async def estimate_simulation_confidence(self, *args):
        return 0.9

logger = logging.getLogger(__name__)

class SyntheticTwinEngine:
    def __init__(self, dt_agent: DigitalTwinAgent, ai_service: AdvancedAIServices):
        self.dt_agent = dt_agent
        self.ai_service = ai_service
        self.simulation_cache: Dict[str, Any] = {}

    async def run_simulation(
        self,
        employee_id: str,
        adjustments: Dict[str, Any],
        simulation_type: str = "what_if",
        base_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        logger.info(f"Running {simulation_type} simulation for {employee_id} with adjustments: {adjustments}")

        if not base_state:
            base_state = await self._get_employee_state(employee_id)

        synthetic_state = self._apply_adjustments(base_state.copy(), adjustments)

        scenario = await self._generate_synthetic_scenario(employee_id, synthetic_state, adjustments)

        simulation_result = {}
        if self.dt_agent:
            try:
                simulation_result = await self.dt_agent.execute_dtla_command(
                    {
                        "command_type": "RUN_SCENARIO",
                        "scenario": scenario,
                        "requester_id": "synthetic_twin_engine",
                    }
                )
            except Exception as e:
                logger.error(f"DTLA Agent failed: {e}. Using mock result.")
                # CRITICAL FIX: Use predictable mock fallback on failure
                simulation_result = {
                    "risk_score": synthetic_state["current_risk_score"] * 0.9,
                    "recommendation": "DTLA service failed. Results are derived from synthetic state.",
                    "attrition_probability": synthetic_state["attrition_probability"] * 0.95,
                }
        else:
             simulation_result = {
                "risk_score": synthetic_state["current_risk_score"] * 0.9,
                "recommendation": "Mocked successful simulation (No DTLA Agent).",
                "attrition_probability": synthetic_state["attrition_probability"] * 0.95,
            }

        # CRITICAL FIX: Update synthetic state with DTLA's predicted scores
        synthetic_state["current_risk_score"] = simulation_result.get("risk_score", synthetic_state["current_risk_score"])
        synthetic_state["attrition_probability"] = simulation_result.get("attrition_probability", synthetic_state["attrition_probability"])

        impact_analysis = await self._analyze_impact(base_state, synthetic_state, simulation_result)

        recommendations = await self._generate_recommendations(impact_analysis, adjustments)

        return {
            "simulation_id": f"SIM_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{employee_id}",
            "employee_id": employee_id,
            "base_state_snapshot": {k: v for k, v in base_state.items() if k not in ["skill_gaps", "engagement_score"]}, # Clean base state
            "synthetic_state_scores": {k: v for k, v in synthetic_state.items() if "score" in k or "probability" in k}, # Only return core scores
            "adjustments_applied": adjustments,
            "risk_score_delta": round(impact_analysis.get("risk_score_delta", 0), 4),
            "attrition_probability_change": round(impact_analysis.get("attrition_change", 0), 4),
            "productivity_impact": round(impact_analysis.get("productivity_impact", 0), 4),
            "cost_implication": round(impact_analysis.get("cost_implication", 0), 2),
            "recommendations": recommendations,
            "simulation_timestamp": datetime.now(timezone.utc).isoformat(),
            "confidence_score": round(impact_analysis.get("confidence", 0.85), 3),
        }

    async def _get_employee_state(self, employee_id: str) -> Dict[str, Any]:
        return {
            "employee_id": employee_id,
            "current_risk_score": 0.65,
            "attrition_probability": 0.3,
            "productivity_score": 0.8,
            "compensation": 85000.0,
            "tenure_months": 24,
            "skill_gaps": ["leadership", "technical_depth"],
            "engagement_score": 0.75,
        }

    def _apply_adjustments(self, state: Dict[str, Any], adjustments: Dict[str, Any]) -> Dict[str, Any]:
        for key, value in adjustments.items():
            if key in state:
                # CRITICAL FIX: Ensure safe numeric addition
                if isinstance(state[key], (int, float)) and isinstance(value, (int, float)):
                    state[key] += float(value)
                else:
                    state[key] = value
            else:
                state[key] = value

        # Deterministic impact simulation based on adjustments (for initial synthetic state)
        if "compensation" in adjustments:
            # Increase engagement by 10% of current or 0.1, whichever is smaller
            state["engagement_score"] = min(1.0, state.get("engagement_score", 0.7) + min(0.1, adjustments["compensation"]/100000.0))

        if "training_hours" in adjustments:
            # Simulate skill gap reduction
            state["skill_gaps"] = [g for g in state["skill_gaps"] if g != "technical_depth"]

        return state

    async def _generate_synthetic_scenario(
        self,
        employee_id: str,
        state: Dict[str, Any],
        adjustments: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "scenario_id": f"SYNTH_{employee_id}_{datetime.now(timezone.utc).timestamp()}",
            "scenario_description": ", ".join(f"{k}={v}" for k, v in adjustments.items()),
            "drivers": list(adjustments.keys()),
            "impact_magnitude_score": len(adjustments) * 0.2, # Simple magnitude score
            "synthetic_flag": True,
            "base_metrics": state,
        }

    async def _analyze_impact(
        self,
        base_state: Dict[str, Any],
        synthetic_state: Dict[str, Any],
        simulation_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        
        # Calculate deltas using the DTLA-updated synthetic_state
        risk_delta = synthetic_state.get("current_risk_score", 0) - base_state.get("current_risk_score", 0)
        attrition_change = synthetic_state.get("attrition_probability", 0) - base_state.get("attrition_probability", 0)
        productivity_impact = synthetic_state.get("productivity_score", 0) - base_state.get("productivity_score", 0)
        cost_implication = synthetic_state.get("compensation", 0) - base_state.get("compensation", 0)

        confidence = 0.85
        if self.ai_service:
            try:
                # Use the AI service for confidence estimation (complex analysis)
                confidence = await self.ai_service.estimate_simulation_confidence(
                    base_state, synthetic_state, simulation_result
                )
            except Exception as e:
                logger.warning(f"AI confidence estimation failed: {e}")
                confidence = 0.5 # Low confidence on failure

        return {
            "risk_score_delta": risk_delta,
            "attrition_change": attrition_change,
            "productivity_impact": productivity_impact,
            "cost_implication": cost_implication,
            "confidence": confidence,
        }

    async def _generate_recommendations(
        self,
        impact_analysis: Dict[str, Any],
        adjustments: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        recommendations: List[Dict[str, Any]] = []

        risk_delta = impact_analysis.get("risk_score_delta", 0)
        attrition_change = impact_analysis.get("attrition_change", 0)

        if risk_delta < -0.05 and attrition_change < -0.05:
            recommendations.append(
                {
                    "type": "ACTIONABLE_GREEN",
                    "message": "Simulation shows significant improvement in risk and retention. **Immediate pilot recommended.**",
                }
            )
        elif risk_delta < 0:
            recommendations.append(
                {
                    "type": "retention",
                    "message": "Simulation indicates lower risk; consider rolling out changes to similar profiles.",
                }
            )
        else:
            recommendations.append(
                {
                    "type": "caution",
                    "message": f"Risk increased/stagnated (Delta: {risk_delta:.4f}). Review compensation and learning opportunities.",
                }
            )

        if impact_analysis.get("cost_implication", 0) > 2000:
             recommendations.append(
                {
                    "type": "finance_alert",
                    "message": f"High cost implication detected: ${impact_analysis['cost_implication']:.2f}. Validate ROI."
                }
            )

        recommendations.append(
            {
                "type": "next_step",
                "message": f"Confidence score is {impact_analysis['confidence']:.3f}. Schedule a 1:1 to validate the impact of the simulated changes.",
            }
        )

        return recommendations