import logging
import numpy as np
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from services.postgres_client import pg_client
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

        # The scenario risk is the employee's own baseline with the levers applied.
        #
        # We deliberately do NOT blend in the agent's score: DigitalTwinAgent
        # returns an ORG-LEVEL state, so blending dragged every employee toward
        # the organisational mean. That made a simulation with NO adjustments
        # report a large risk change (down for people above the mean, up for
        # people below it), which is the worst possible failure for a control a
        # manager might act on. A no-op must read as no change.
        lever_risk = round(float(synthetic_state.get("current_risk_score", 0.5) or 0.5), 4)
        synthetic_state["current_risk_score"] = lever_risk
        # One quantity, one number: attrition probability tracked risk separately
        # and could report "no change" beside a 24-point risk move.
        synthetic_state["attrition_probability"] = lever_risk
        # Kept for context, clearly labelled as the org-wide comparison.
        synthetic_state["organisation_baseline_risk"] = simulation_result.get("risk_score")

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
        """The employee's real baseline from the UDM.

        This used to return one hardcoded state for every employee, so every
        simulation produced the same numbers no matter who or what was modelled.
        """
        # Numeric fields must stay numeric: downstream impact analysis does
        # arithmetic on them. `source` reports whether these are real readings
        # or the neutral baseline used when the employee has no record.
        state: Dict[str, Any] = {
            "employee_id": employee_id,
            "current_risk_score": 0.5,
            "attrition_probability": 0.5,
            "productivity_score": 0.6,
            "compensation": 0.0,
            "tenure_months": 0,
            "engagement_score": 0.5,
            "source": "no record found; neutral baseline",
        }
        try:
            row = await pg_client.fetchrow(
                """SELECT e.tenure_months, e.dtla_risk_score, e.department, e.job_title,
                          (SELECT AVG(overall_rating) FROM performance_reviews r
                             WHERE r.employee_uuid = e.employee_uuid) AS avg_rating
                     FROM employee_pii e WHERE e.employee_uuid = $1""",
                employee_id,
            )
        except Exception as e:
            logger.warning(f"twin baseline lookup failed for {employee_id}: {e}")
            return state

        if not row:
            return state

        risk = float(row["dtla_risk_score"]) if row.get("dtla_risk_score") is not None else 0.5
        rating = float(row["avg_rating"]) if row.get("avg_rating") is not None else None

        # Real salary via the PII vault, so a pay lever can report an actual cost
        # instead of always reporting zero.
        compensation = 0.0
        try:
            from services.pii_vault import PIIVault
            comp_rows = await PIIVault.get_instance().execute_pii_query(
                "SELECT base_salary_encrypted FROM employee_pii WHERE employee_uuid = $1",
                "employee_pii", "SyntheticTwinEngine", None, employee_id,
            )
            if comp_rows:
                compensation = float(comp_rows[0].get("base_salary") or 0.0)
        except Exception as e:
            logger.warning(f"twin salary lookup failed for {employee_id}: {e}")

        state.update({
            "current_risk_score": round(risk, 3),
            "attrition_probability": round(risk, 3),
            # Performance rating (0-5) mapped onto a 0-1 productivity index.
            "productivity_score": round(rating / 5.0, 3) if rating is not None else 0.6,
            "compensation": compensation,
            "tenure_months": int(row["tenure_months"]) if row.get("tenure_months") is not None else 0,
            # Engagement is inferred from rating and risk; both are real signals.
            "engagement_score": round(max(0.0, min(1.0, (rating / 5.0 if rating else 0.5) * (1 - risk) + 0.2)), 3),
            "department": row.get("department"),
            "job_title": row.get("job_title"),
            "source": "employee record",
        })
        return state

    # What each retention lever does to the modelled state. Values are per unit
    # of the lever and are applied against the employee's real baseline, so the
    # same lever moves different people by different amounts.
    LEVERS = {
        # lever name: (risk delta per unit, engagement delta per unit, cap)
        "salary_increase_pct":  (-0.012, 0.010, 20),   # diminishing past ~20%
        "compensation":         (-0.000002, 0.000002, 50000),
        "training_sessions":    (-0.015, 0.020, 8),
        "training_hours":       (-0.002, 0.003, 60),
        "remote_work_days":     (-0.020, 0.025, 5),
        "remote_days_per_week": (-0.020, 0.025, 5),
        "promotion":            (-0.120, 0.150, 1),
        "manager_change":       (-0.060, 0.080, 1),
    }

    def _apply_adjustments(self, state: Dict[str, Any], adjustments: Dict[str, Any]) -> Dict[str, Any]:
        """Apply retention levers to the employee's real baseline.

        Previously only keys that already existed on the state were applied, so
        the levers the UI actually sends (salary_increase_pct, training_sessions,
        remote_work_days) were ignored and every scenario returned the same
        number regardless of how aggressive it was.
        """
        risk = float(state.get("current_risk_score", 0.5) or 0.5)
        engagement = float(state.get("engagement_score", 0.5) or 0.5)
        engagement_before = engagement
        applied: Dict[str, Any] = {}

        for key, value in adjustments.items():
            if not isinstance(value, (int, float)):
                state[key] = value
                continue

            spec = self.LEVERS.get(key)
            if spec:
                risk_per_unit, eng_per_unit, cap = spec
                effective = max(-cap, min(float(value), cap))  # diminishing returns
                risk += risk_per_unit * effective
                engagement += eng_per_unit * effective
                applied[key] = effective
            elif key in state and isinstance(state[key], (int, float)):
                state[key] += float(value)
            else:
                state[key] = value

        state["current_risk_score"] = round(max(0.0, min(1.0, risk)), 3)
        state["attrition_probability"] = state["current_risk_score"]
        state["engagement_score"] = round(max(0.0, min(1.0, engagement)), 3)

        # Productivity and cost were structurally dead: no lever wrote them, so a
        # 20% pay rise reported zero cost and zero productivity effect.
        base_productivity = float(state.get("productivity_score") or 0.0)
        # Engagement gains carry into productivity at a damped rate.
        engagement_gain = state["engagement_score"] - float(engagement_before)
        state["productivity_score"] = round(max(0.0, min(1.0, base_productivity + engagement_gain * 0.5)), 3)

        base_salary = float(state.get("compensation") or 0.0)
        pay_rise_pct = float(applied.get("salary_increase_pct", 0) or 0)
        promotion_pct = 8.0 * float(applied.get("promotion", 0) or 0)  # a promotion carries a band uplift
        extra_cash = float(applied.get("compensation", 0) or 0)
        state["compensation"] = round(base_salary * (1 + (pay_rise_pct + promotion_pct) / 100.0) + extra_cash, 2)

        state["levers_applied"] = applied
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