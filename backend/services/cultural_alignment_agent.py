# services/cultural_alignment_agent.py
"""
Cultural Alignment Agent: Change Management via AI Sentiment Analysis.
"""
import logging
import json
from typing import Dict, Any
from datetime import datetime, timezone
from services.ai_services import AIService
from config.settings import settings

logger = logging.getLogger(__name__)

CA_RESISTANCE_THRESHOLD = getattr(settings, 'CA_RESISTANCE_THRESHOLD', 0.65)

class CAAgent:
    def __init__(self, ai_service: AIService):
        self.ai_service = ai_service
        logger.info("✓ CAAgent Initialized (AI Sentiment Analysis).")

    async def run_sentiment_analysis(self, change_initiative: str) -> Dict[str, Any]:
        """
        Uses AI to analyze the text of a change initiative and predict employee resistance.
        """
        prompt = (
            f"Analyze this corporate change initiative for potential employee resistance: '{change_initiative}'. "
            "Return JSON with keys: 'resistance_score' (0.0-1.0), 'primary_concern', and 'recommended_campaign' "
            "(TransparencyPush, ValueAlignment, or FutureVision)."
        )
        
        try:
            # Real AI Call
            analysis = await self.ai_service.generate_json_response(
                prompt,
                response_schema={
                    "type": "object", 
                    "properties": {
                        "resistance_score": {"type": "number"},
                        "primary_concern": {"type": "string"},
                        "recommended_campaign": {"type": "string"}
                    }
                },
                task_type="complex_generation"
            )
            
            score = analysis.get("resistance_score", 0.5)
            status = "HIGH_RESISTANCE" if score >= CA_RESISTANCE_THRESHOLD else "ALIGNED"
            action = "TRIGGER_OCM_CAMPAIGN" if status == "HIGH_RESISTANCE" else "MONITOR"

            return {
                "initiative": change_initiative,
                "resistance_score": score,
                "status": status,
                "action": action,
                "primary_concern": analysis.get("primary_concern"),
                "recommended_campaign": analysis.get("recommended_campaign"),
                "analyzed_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"CA Analysis failed: {e}")
            return {"error": "AI Analysis Failed", "initiative": change_initiative}