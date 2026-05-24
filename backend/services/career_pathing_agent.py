# services/career_pathing_agent.py
"""Career Pathing Agent: AI-Driven Next Best Action based on Skill Gaps."""
import logging
from typing import Dict, Any, List
from datetime import datetime, timezone
from services.ai_services import AIService # CRITICAL FIX: Import AI Service

logger = logging.getLogger(__name__)

class CareerPathingAgent:
    def __init__(self, ai_service: AIService): # CRITICAL FIX: Inject AI Service
        self.ai_service = ai_service
        logger.info(" ✓  Career Pathing Agent Initialized (AI-Driven Logic).")

    async def predict_next_best_action(self, employee_id: str, profile: Dict[str, Any]) -> Dict[str, Any]:
        """[ASYNCHRONOUS] Determines retention action based on skill gaps using AI analysis."""
        
        # Extract skills and gaps from the profile (assuming complex structure)
        skill_gaps = profile.get('skill_gaps', [])
        current_role = profile.get('current_role', 'Software Engineer')

        # Robust AI Prompt for pathing/action
        prompt = f"""
        Analyze the profile for employee {employee_id} in role '{current_role}'.
        Identified skill gaps: {skill_gaps}.
        Synthesize the single best career development action (e.g., 'Executive Mentorship', 'High-Visibility Project', 'Certification Bootcamp') and estimate the 'retention_utility' (0.0-1.0).
        Output JSON: {{"optimal_action": str, "action_type": str, "predicted_retention_utility": float}}
        """

        try:
            # CRITICAL FIX: Use AI service for complex reasoning
            analysis = await self.ai_service.generate_json_response(
                prompt,
                response_schema={
                    "type": "object",
                    "properties": {
                        "optimal_action": {"type": "string"},
                        "action_type": {"type": "string", "enum": ["mentorship", "project", "development", "transfer"]},
                        "predicted_retention_utility": {"type": "number", "minimum": 0.0, "maximum": 1.0}
                    }
                },
                task_type="strategic_analysis"
            )
            
            if not analysis:
                raise ValueError("AI returned empty analysis.")

            action_type = analysis.get("action_type", "development")
            recommendation = analysis.get("optimal_action", "Manual Review Required")
            utility = analysis.get("predicted_retention_utility", 0.5)

        except Exception as e:
            logger.error(f"AI Pathing failed, falling back: {e}")
            # Fallback deterministic logic
            action_type = "development"
            recommendation = f"System fallback: Enroll in 'General Upskilling' for {current_role}."
            utility = 0.5

        return {
            "employee_id": employee_id,
            "optimal_action": recommendation,
            "action_type": action_type,
            "predicted_retention_utility": round(utility, 2),
            "generated_at": datetime.now(timezone.utc).isoformat()
        }

# Global instance (assuming a separate setup injects the AI service)
# The old deterministic instance is removed. The Orchestrator/Server startup must inject dependencies.