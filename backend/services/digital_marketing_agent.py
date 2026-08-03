# services/digital_marketing_agent.py
"""Digital Marketing Agent: Generates SEO-optimized recruitment content using AI.
Refactored to be fully asynchronous with complex generation."""
import logging
from typing import Dict, Any
from datetime import datetime, timezone
import uuid
import json
from services.ai_services import AIService
from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger(__name__)

# --- Structured Output Model for the Campaign ---
class RecruitmentContent(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    content_copy: str = Field(..., description="The main, engaging content body of the post.")
    title_headline: str = Field(..., description="A compelling, short headline.")
    estimated_seo_score: float = Field(..., ge=0.0, le=1.0, description="Predicted score for search engine visibility.")
    keywords_used: List[str] = Field(default_factory=list, description="Top 3 SEO keywords included.")
    call_to_action: str = Field(..., description="The specific action to encourage.")

class DMAgent:
    def __init__(self, ai_service: AIService):
        self.ai = ai_service
        logger.info(" ✓  DMAgent Initialized (Async Content Factory).")

    async def generate_campaign_content(self, job_title: str, platform: str) -> Dict[str, Any]:
        """
        Generates platform-specific recruitment content with deeper AI analysis.
        """
        campaign_id = f"CAMP_{uuid.uuid4().hex[:8].upper()}"

        # 1. Simulate a deeper, multi-step analysis (Competitor Check)
        market_insight = await self._get_market_insight(job_title)

        prompt = (
            f"Write a highly engaging and SEO-optimized recruitment post for a '{job_title}' targeting the "
            f"'{platform}' audience. Use insight: {market_insight.get('competitor_weakness', 'Fast pace is attractive')}. "
            f"Ensure the tone is professional but exciting. Output valid JSON strictly matching the RecruitmentContent schema."
        )

        try:
            # 2. Real AI Generation with Structured Output
            content_data = await self.ai.generate_json_response(
                prompt,
                response_schema=RecruitmentContent.model_json_schema(),
                task_type="creative_generation"
            )

            # 3. Validate and Structure the Result
            validated_content = RecruitmentContent(**content_data)
            
            return {
                "campaign_id": campaign_id,
                "job_title": job_title,
                "platform": platform,
                "content_copy": validated_content.content_copy,
                "title_headline": validated_content.title_headline,
                "seo_score": round(validated_content.estimated_seo_score, 3),
                "keywords": validated_content.keywords_used,
                "status": "READY",
                "generated_at": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            logger.error(f"Marketing generation failed: {e}")
            return {"status": "FAILED", "error": str(e), "fallback_content": f"Apply to the {job_title} role today!"}

    async def _get_market_insight(self, job_title: str) -> Dict[str, str]:
        """Mocks a dynamic market analysis step using AI for context."""
        insight_prompt = f"What is the top hiring weakness of competitors for a '{job_title}' role? Respond in one sentence."
        try:
            # Simple text generation for a single data point
            response = await self.ai.generate_text(insight_prompt, task_type="analysis")
            return {"competitor_weakness": response.strip()}
        except:
            return {"competitor_weakness": "Competitors offer lower sign-on bonuses."}