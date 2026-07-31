# /backend/services/xai_wrapper.py - REPLACEMENT (Precision and Consistency)
# /backend/services/xai_wrapper.py
"""eXplainable AI (XAI) Wrapper: Provides mathematical explanations for the Heuristic Scoring Engine used in Workforce Planning."""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ===============================================
# CRITICAL FIX: MockPredictor Definition
# ===============================================
class MockPredictor:
    """A minimal mock object to hold feature names for XAI initialization."""
    def __init__(self, feature_names: List[str]):
        self.feature_names = feature_names
        
    def predict(self, data: List[Dict]) -> List[float]:
        """A dummy prediction function."""
        logger.warning("MockPredictor: Returning fixed risk score 0.6 for all data.")
        return [0.6] * len(data)

class XAIWrapper:
    """
    Generates feature contribution explanations. 
    Not a 'mock', but a Rule-Based Explainer synced with the WFP Heuristic Engine."""
    def __init__(self, predictor: Optional[MockPredictor] = None):
        self.predictor = predictor
        if predictor:
            logger.info(f"✓ XAI Wrapper Initialized with features: {predictor.feature_names} (Heuristic Explainer).")
        else:
            logger.info("✓ XAI Wrapper Initialized (Heuristic Explainer, no predictor context).")
            
    LABELS = {
        "Tenure_Months": "length of service",
        "Performance_Score": "performance rating",
        "Compensation_Ratio": "pay against the market",
        "Last_Raise_Months": "time since their last pay change",
        "Observed_Risk_Signal": "historic pattern for similar profiles",
    }

    def explain_drivers(self, prediction: Dict[str, Any]) -> Dict[str, Any]:
        """Render the adjustments the prediction actually made.

        This is the honest form of an explanation: the model records each
        adjustment as it applies it, and this reports them. The previous
        approach recomputed the score with the explainer's own weights, so the
        breakdown disagreed with the prediction by up to ten points while the
        panel told the reader the factors added up to it.
        """
        baseline = float(prediction.get("baseline_risk", 0.4))
        score = float(prediction.get("risk_score", baseline))
        drivers = list(prediction.get("drivers") or [])

        contributions = [
            {**d, "raw_value": d.get("impact"),
             "label": self.LABELS.get(d.get("feature"), str(d.get("feature", "")).replace("_", " ").lower())}
            for d in drivers
        ]

        pct = round(score * 100)
        raised = [c for c in contributions if c["impact"] > 0.005]
        lowered = [c for c in contributions if c["impact"] < -0.005]
        strongest_up = max(raised, key=lambda c: c["impact"], default=None)
        strongest_down = min(lowered, key=lambda c: c["impact"], default=None)

        # Which way the score actually went decides how this reads. It used to
        # announce "the biggest factor pushing that up" even for a score sitting
        # well below the baseline.
        if score > baseline + 0.005 and strongest_up:
            summary = (f"This person has an estimated {pct}% chance of leaving, above the "
                       f"{baseline:.0%} starting point. The largest reason is their {strongest_up['label']}.")
        elif score < baseline - 0.005 and strongest_down:
            summary = (f"This person has an estimated {pct}% chance of leaving, below the "
                       f"{baseline:.0%} starting point, held down mostly by their {strongest_down['label']}.")
        else:
            summary = (f"This person has an estimated {pct}% chance of leaving, "
                       f"about the {baseline:.0%} starting point, with nothing standing out.")

        total = round(baseline + sum(c["impact"] for c in contributions), 3)
        return {
            "model_type": "Heuristic_v2",
            "prediction_score": round(score, 3),
            "baseline_score": round(baseline, 3),
            "explained_from": "workforce planning model",
            "reconciliation": (
                f"Starting from {baseline:.0%}, these factors add up to {total:.0%}, "
                f"which is the score shown."
                if abs(total - score) < 0.01 else
                f"Starting from {baseline:.0%}, these factors reach {total:.0%}; the score was "
                f"capped at {score:.0%}."),
            "human_summary": summary,
            "feature_contributions": contributions,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _calculate_feature_contributions(self, employee_data: Dict[str, Any],
                                         predicted_score: Optional[float] = None) -> Dict[str, Any]:
        """Explain a workforce-planning prediction.

        `predicted_score`, when supplied, is the authoritative risk from the
        prediction model; the contributions below explain how it was reached.
        Without it this class computed its own competing number, so the same
        employee could be shown two different risks on one screen.
        """
        # Features arrive flat from the prediction's feature_vector_used; older
        # callers nested them under UDM.AI_Features. Accept both, otherwise every
        # explanation silently ran on defaults.
        ai_features = (employee_data.get('UDM', {}) or {}).get('AI_Features', {}) or {}

        def feat(name, default):
            for source in (employee_data, ai_features):
                if source.get(name) is not None:
                    return float(source[name])
            return float(default)

        tenure = feat('tenure_months', 0)
        perf_score = feat('performance_score', feat('satisfaction_score', 3.0))

        contributions: List[Dict[str, Any]] = []

        # Each reason has to follow the sign it is attached to. These were fixed
        # strings, so a factor pulling risk *down* was shown next to text saying
        # it pushed risk up, with an arrow pointing the other way again.
        c_tenure = (48 - tenure) / 48 * 0.2 if tenure < 48 else -0.05
        contributions.append(self._fmt_contrib(
            "Tenure_Months", c_tenure,
            (f"At {tenure:g} months they are still in the period when people are most "
             "likely to move on." if c_tenure > 0 else
             f"{tenure:g} months of service puts them past the point where most people leave.")))

        c_perf = (3.0 - perf_score) / 2.0 * 0.1
        contributions.append(self._fmt_contrib(
            "Performance_Score", c_perf,
            (f"A rating of {perf_score:.1f} is below where people usually stay engaged."
             if c_perf > 0 else
             f"A rating of {perf_score:.1f} is strong, which tends to go with staying.")))

        # Pay against the market was computed from a percentile nothing ever
        # supplies, so it came out as exactly 0.000 for every one of the 21,470
        # employees while still being rendered as a per-person row. It is only
        # included when there is a real pay comparison to make.
        compa_ratio = employee_data.get('compa_ratio')
        if compa_ratio is None and employee_data.get('compensation_percentile') is not None:
            compa_ratio = 0.8 + (float(employee_data['compensation_percentile']) / 100.0) * 0.4
        c_comp = 0.0
        if compa_ratio is not None:
            comp = float(compa_ratio)
            c_comp = 0.25 if comp < 0.85 else -0.2 if comp > 1.1 else (1.0 - comp) * 0.15
            contributions.append(self._fmt_contrib(
                "Compensation_Ratio", c_comp,
                (f"They are paid below the market rate for this role ({comp:.2f} of it)."
                 if c_comp > 0 else
                 f"They are paid at or above the market rate for this role ({comp:.2f} of it).")))

        # The workforce model carries the rest of the signal, so leaving it out
        # made the explanation name the wrong driver: the contributions could sum
        # to roughly zero against a 0.64 score.
        observed = employee_data.get('observed_risk_signal')
        c_observed = 0.0
        if observed is not None:
            c_observed = (float(observed) - 0.5) * 0.5
            contributions.append(self._fmt_contrib(
                "Observed_Risk_Signal", c_observed,
                ("People with this length of service and rating have tended to leave."
                 if c_observed > 0 else
                 "People with this length of service and rating have tended to stay.")))

        base_score = 0.5
        derived = base_score + c_tenure + c_perf + c_comp + c_observed
        # The prediction model is the source of truth when it gave us a score.
        score = float(predicted_score) if predicted_score is not None else derived

        # Plain-English factor names; raw identifiers should never reach a reader.
        LABELS = {
            "Tenure_Months": "length of service",
            "Performance_Score": "performance rating",
            "Compensation_Ratio": "pay against the market",
            "Observed_Risk_Signal": "historic pattern for similar profiles",
        }

        sorted_factors = sorted(contributions, key=lambda x: x['impact'], reverse=True)
        primary, weakest = sorted_factors[0], sorted_factors[-1]
        pct = round(score * 100)

        if primary['impact'] > 0.01:
            summary = (f"This person has an estimated {pct}% chance of leaving. "
                       f"The biggest factor pushing that up is their {LABELS.get(primary['feature'], primary['feature'].lower())}.")
        elif weakest['impact'] < -0.01:
            summary = (f"This person has an estimated {pct}% chance of leaving, "
                       f"held down mainly by their {LABELS.get(weakest['feature'], weakest['feature'].lower())}.")
        else:
            summary = (f"This person has an estimated {pct}% chance of leaving, "
                       "with no single factor standing out.")

        # The panel tells the reader that each factor below pushed the score up
        # or pulled it down, so the factors have to add up to the score. They
        # could not: the explainer derived one number and then reported the
        # model's, leaving a gap of several points with nothing to account for
        # it. The gap is now stated rather than hidden.
        unexplained = round(score - derived, 3)

        return {
            "model_type": "Heuristic_v2",
            "prediction_score": round(score, 3),
            "baseline_score": base_score,
            "explained_from": "workforce planning model" if predicted_score is not None else "explainer heuristic",
            "unexplained_difference": unexplained,
            "reconciliation": (
                f"Starting from a baseline of {base_score:.0%}, the factors below account for "
                f"{derived:.0%}." + (
                    f" The model's own figure is {score:.0%}; the {abs(unexplained):.0%} difference "
                    "comes from signals this breakdown does not cover."
                    if abs(unexplained) >= 0.01 else " That matches the model's figure.")
            ),
            "human_summary": summary,
            "feature_contributions": [
                {**c, "label": LABELS.get(c["feature"], c["feature"].replace("_", " ").lower())}
                for c in contributions
            ],
            "generated_at": datetime.now(timezone.utc).isoformat()
        }

    def _fmt_contrib(self, name: str, val: float, reason: str):
        return {
            "feature": name,
            # CRITICAL FIX: Round impact to 3 decimal places for consistency
            "impact": round(val, 3), 
            "raw_value": round(val, 5), 
            "reason": reason
        }
    
    async def get_feature_contributions(self, employee_data: Dict[str, Any],
                                        predicted_score: Optional[float] = None) -> Dict[str, Any]:
        """Async wrapper for feature calculation."""
        return self._calculate_feature_contributions(employee_data, predicted_score)
        
    # CRITICAL FIX: Adding synchronous method placeholder as required by Orchestrator
    def explain_prediction(self, data: Dict[str, Any], predicted_score: Optional[float] = None) -> Dict[str, Any]:
        """Explain a prediction. Pass the model's score so the explanation and the
        prediction always agree."""
        return self._calculate_feature_contributions(data, predicted_score)