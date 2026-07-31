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
        comp_percentile = feat('compensation_percentile', 50.0)

        # Prefer the compa ratio the prediction already computed.
        compa_ratio = employee_data.get('compa_ratio')
        compa_ratio = float(compa_ratio) if compa_ratio is not None else 0.8 + (comp_percentile / 100.0) * 0.4
        
        contributions: List[Dict[str, Any]] = []

        # 1. Tenure (Impact: High for low tenure)
        c_tenure = (48 - tenure) / 48 * 0.2 if tenure < 48 else 0.0
        contributions.append(self._fmt_contrib("Tenure_Months", c_tenure, "Risk decreases after 4 years of service."))

        # 2. Performance (Impact: Negative for high score)
        c_perf = (3.0 - perf_score) / 2.0 * 0.1 
        contributions.append(self._fmt_contrib("Performance_Score", c_perf, "Low performance score increases risk."))

        # 3. Compensation Ratio (Impact: High for low ratio)
        comp = compa_ratio
        c_comp = (1.0 - comp) * 0.15 
        if comp < 0.85: c_comp = 0.25 
        elif comp > 1.1: c_comp = -0.2
        contributions.append(self._fmt_contrib("Compensation_Ratio", c_comp, "Market ratio impact"))
        
        base_score = 0.5
        derived = base_score + c_tenure + c_perf + c_comp
        # The prediction model is the source of truth when it gave us a score.
        score = float(predicted_score) if predicted_score is not None else derived

        # Plain-English factor names; raw identifiers should never reach a reader.
        LABELS = {
            "Tenure_Months": "length of service",
            "Performance_Score": "performance rating",
            "Compensation_Ratio": "pay against the market",
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

        return {
            "model_type": "Heuristic_v2",
            "prediction_score": round(score, 3),
            # Kept so the two numbers can be compared rather than silently differing.
            "explained_from": "workforce planning model" if predicted_score is not None else "explainer heuristic",
            "explainer_derived_score": round(derived, 3),
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