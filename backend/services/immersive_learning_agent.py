# services/immersive_learning_agent.py - REPLACEMENT (AI Failure Handling)
import logging
import json
from services.ai_services import AIService
from services.event_publisher_service import EventPublisherService
from datetime import datetime, timezone # CRITICAL FIX: Add missing import

logger = logging.getLogger(__name__)

class ImmersiveLearningAgent:
    def __init__(self, pub: EventPublisherService, ai: AIService):
        self.pub = pub
        self.ai = ai
        logger.info("✓ Immersive Learning Agent Initialized (Curriculum Synthesizer).")


    async def synthesize_personalized_curriculum(self, employee_id: str, target_role: str = "future_role") -> dict:
        """
        Synthesizes a learning path based on employee ID and target role (Curriculum Synthesizer).
        """
        # NOTE: Mocking skill gaps for prompt
        gaps = {"leadership": 0.4, "cloud_ops": 0.7}
        
        prompt = f"Create a 4-module learning path for employee {employee_id} to achieve {target_role}, focusing on gaps: {gaps}. Output JSON."
        
        try:
            plan = await self.ai.generate_json_response(
                prompt, 
                response_schema={"type": "object", "properties": {"curriculum_name": {"type": "string"}, "modules": {"type": "array", "items": {"type": "object"}}}},
                task_type="complex_generation"
            )
            
            if not plan:
                raise ValueError("AI returned an empty or invalid curriculum plan.")
                
            # Publish Assignment Event
            await self.pub.publish_event(
                "Learning_Assigned", 
                {"employee_id": employee_id, "plan": plan, "target_role": target_role, "timestamp": datetime.now(timezone.utc).isoformat()}, 
                key=employee_id
            )
            
            return {
                "employee_id": employee_id,
                "target_role": target_role,
                "status": "ASSIGNED",
                "curriculum": plan
            }
        except Exception as e:
            logger.error(f"Curriculum generation failed for {employee_id}: {type(e).__name__}: {e}")
            return {
                "status": "FAILED", 
                "error": "AI Service Unavailable or Planning Error", 
                "details": str(e)
            }