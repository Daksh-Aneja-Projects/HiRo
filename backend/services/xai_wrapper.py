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
            
    def _calculate_feature_contributions(self, employee_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculates deterministic feature contributions based on WFP heuristic logic.
        """
        # CRITICAL FIX: Safely retrieve and cast inputs
        tenure = float(employee_data.get('tenure_months', 0))
        ai_features = employee_data.get('UDM', {}).get('AI_Features', {})
        comp_percentile = float(ai_features.get('compensation_percentile', 50.0))
        perf_score = float(ai_features.get('satisfaction_score', 3.0))
        
        # Comma ratio calculation is simplified here for mock consistency
        compa_ratio = 0.8 + (comp_percentile / 100.0) * 0.4 
        
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
        
        # CRITICAL FIX: Base score is 0.5 (WFP logic) plus contributions
        base_score = 0.5
        total_impact = base_score + c_tenure + c_perf + c_comp
        
        # Generate Narrative
        sorted_factors = sorted(contributions, key=lambda x: x['impact'], reverse=True)
        primary = sorted_factors[0]
        
        summary = f"Risk Score {total_impact:.3f}. " 
        
        if primary['impact'] > 0.01: # Check for meaningful positive impact
            summary += f"Primary driver is {primary['feature']} (Contributing {primary['impact']:.3f})."
        elif sorted_factors[-1]['impact'] < -0.01: # Check for meaningful negative impact (mitigation)
             summary += f"Risk is mitigated primarily by {sorted_factors[-1]['feature']}."
        else:
             summary += "Risk is neutral; no single dominant driver detected."
            
        return {
            "model_type": "Heuristic_v2",
            "prediction_score": round(total_impact, 3),
            "human_summary": summary,
            "feature_contributions": contributions,
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
    
    async def get_feature_contributions(self, employee_data: Dict[str, Any]) -> Dict[str, Any]:
        """Async wrapper for feature calculation."""
        return self._calculate_feature_contributions(employee_data)
        
    # CRITICAL FIX: Adding synchronous method placeholder as required by Orchestrator
    def explain_prediction(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Synchronous method for the orchestration map, avoiding unsafe asyncio.run."""
        return self._calculate_feature_contributions(data)