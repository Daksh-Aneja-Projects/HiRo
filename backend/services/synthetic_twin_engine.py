import logging
import numpy as np
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from services.postgres_client import pg_client
class DigitalTwinAgent:
    # NOTE: This placeholder class is only used here to prevent circular imports if necessary,
    # but the runtime uses the injected instance from server.py.
    async def execute_dtla_command(self, command: Dict):
        return {"risk_score": 0.5, "recommendation": "Mocked DTLA result.", "attrition_probability": 0.25}

logger = logging.getLogger(__name__)

def _num(value, default: float) -> float:
    """A number, treating a real zero as a real zero.

    `float(x or default)` reads 0.0 as missing, because zero is falsy. That
    turned a scenario strong enough to drive risk down to zero into one that
    reported risk *rising* to the 0.5 default: the strongest retention package
    the product could model came back recommending caution.
    """
    return float(default if value is None else value)



class SyntheticTwinEngine:
    # The employee signals the confidence heuristic scores. Each is a real column
    # the baseline lookup either found or did not; nothing here is inferred.
    CONFIDENCE_SIGNALS = ("tenure_months", "performance_rating", "risk_score",
                          "compensation", "department")

    def __init__(self, dt_agent: DigitalTwinAgent, ai_service: Any = None):
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
        lever_risk = round(_num(synthetic_state.get("current_risk_score"), 0.5), 4)
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
            "confidence_score": impact_analysis["confidence"],
            # Says in plain English what the confidence number is measuring, so
            # nothing has to guess that it is a data-completeness heuristic.
            "confidence_basis": impact_analysis["confidence_basis"],
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
            # Which real signals backed this baseline. Drives the confidence
            # heuristic, so a scenario run on a thin record says so.
            "data_signals_present": [],
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
            "data_signals_present": [
                name for name, found in (
                    ("tenure_months", row.get("tenure_months") is not None),
                    ("performance_rating", rating is not None),
                    ("risk_score", row.get("dtla_risk_score") is not None),
                    ("compensation", compensation > 0),
                    ("department", bool(row.get("department"))),
                ) if found
            ],
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
        risk = _num(state.get("current_risk_score"), 0.5)
        engagement = _num(state.get("engagement_score"), 0.5)
        engagement_before = engagement
        applied: Dict[str, Any] = {}
        clipped: List[str] = []

        for key, value in adjustments.items():
            if not isinstance(value, (int, float)):
                state[key] = value
                continue

            spec = self.LEVERS.get(key)
            if spec:
                risk_per_unit, eng_per_unit, cap = spec
                effective = max(-cap, min(float(value), cap))  # diminishing returns
                if effective != float(value):
                    # The request pushed past the range the lever was calibrated
                    # on, so the modelled effect is an extrapolation.
                    clipped.append(key)
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
        base_productivity = _num(state.get("productivity_score"), 0.0)
        # Engagement gains carry into productivity at a damped rate.
        engagement_gain = state["engagement_score"] - float(engagement_before)
        state["productivity_score"] = round(max(0.0, min(1.0, base_productivity + engagement_gain * 0.5)), 3)

        base_salary = _num(state.get("compensation"), 0.0)
        pay_rise_pct = float(applied.get("salary_increase_pct", 0) or 0)
        promotion_pct = 8.0 * float(applied.get("promotion", 0) or 0)  # a promotion carries a band uplift
        extra_cash = float(applied.get("compensation", 0) or 0)
        state["compensation"] = round(base_salary * (1 + (pay_rise_pct + promotion_pct) / 100.0) + extra_cash, 2)

        state["levers_applied"] = applied
        state["levers_clipped"] = clipped
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

        confidence, basis = self._estimate_confidence(base_state, synthetic_state)

        return {
            "risk_score_delta": risk_delta,
            "attrition_change": attrition_change,
            "productivity_impact": productivity_impact,
            "cost_implication": cost_implication,
            "confidence": confidence,
            "confidence_basis": basis,
        }

    def _estimate_confidence(
        self,
        base_state: Dict[str, Any],
        synthetic_state: Dict[str, Any],
    ) -> tuple:
        """A deterministic heuristic confidence, and a plain-English basis for it.

        This is NOT a model-derived probability. It answers one question: how
        much of this employee's real record did the simulation actually have,
        and did the requested levers stay inside the range they were calibrated
        on. It replaces a call to an AIService method that never existed, whose
        AttributeError was swallowed so every simulation reported exactly 0.5.

        Formula:
            completeness = (real signals found) / (signals scored)
                           over tenure, performance rating, risk score,
                           compensation and department
            confidence   = 0.30 + 0.55 * completeness
                           -> 0.30 with no record at all, 0.85 with a full one
            extrapolation = (levers clipped to their calibrated cap) / (levers used)
            confidence   = confidence * (1 - 0.40 * extrapolation)

        So a thin record always scores below a complete one, and pushing a lever
        far outside observed ranges lowers confidence rather than hiding it.
        """
        signals = base_state.get("data_signals_present") or []
        completeness = len(signals) / len(self.CONFIDENCE_SIGNALS)
        confidence = 0.30 + 0.55 * completeness

        applied = synthetic_state.get("levers_applied") or {}
        clipped = synthetic_state.get("levers_clipped") or []
        extrapolation = (len(clipped) / len(applied)) if applied else 0.0
        confidence *= (1 - 0.40 * extrapolation)

        missing = [s for s in self.CONFIDENCE_SIGNALS if s not in signals]
        parts = [f"{len(signals)} of {len(self.CONFIDENCE_SIGNALS)} employee data points were available"]
        if missing:
            parts.append("missing " + ", ".join(m.replace("_", " ") for m in missing))
        if clipped:
            parts.append("and " + ", ".join(c.replace("_", " ") for c in clipped)
                         + " was pushed beyond the range this model was calibrated on")
        basis = "Heuristic confidence: " + "; ".join(parts) + "."

        return round(max(0.0, min(1.0, confidence)), 3), basis

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
                "message": (f"{impact_analysis['confidence_basis']} "
                            f"Schedule a 1:1 to validate the impact of the simulated changes."),
            }
        )

        return recommendations