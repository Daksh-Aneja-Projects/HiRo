# /backend/services/rlff_llm_fine_tuner.py - REPLACEMENT (Robustness)
# services/rlff_llm_fine_tuner.py
import asyncio 
import logging
from typing import Dict, Any, List
from datetime import datetime, timezone
from services.event_publisher_service import EventPublisherService
from services.ai_services import AIService

logger = logging.getLogger(__name__)

class RLFFLLMFineTuner:
    def __init__(self, ai_service: AIService, publisher: EventPublisherService):
        self.ai = ai_service
        self.publisher = publisher
        # CRITICAL FIX: Use a more robust queue structure for production
        self.feedback_queue: asyncio.Queue = asyncio.Queue() 
        self.is_running = False
        logger.info("✓ RLFFLLMFineTuner Initialized with AI Service.")

    async def execute_rlff_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes a command related to the RLFF fine-tuning process.
        """
        command_type = command.get('command_type', 'analyze')
        prompt = f"Analyze RLFF command for fine-tuning: {command.get('command')}"
        
        try:
            analysis = await self.ai.generate_text(prompt, system_instruction="Analyze and summarize the LLM fine-tuning command.")
        except Exception as e:
            analysis = f"AI Analysis failed: {type(e).__name__}"

        await self.publisher.publish_event(
            "rlff.command.executed",
            {"command": command.get('command'), "status": "Initiated", "type": command_type},
            key="RLFF_SYSTEM"
        )
        
        return {
            "status": "COMMAND_QUEUED",
            "details": analysis,
            "initiated_at": datetime.now(timezone.utc).isoformat()
        }

    async def submit_feedback(self, prompt: str, output: str, rating: float):
        """Ingests feedback into the asynchronous queue."""
        feedback_item = {
            "prompt": prompt, "output": output, "rating": rating, 
            "ts": datetime.now(timezone.utc).isoformat()
        }
        await self.feedback_queue.put(feedback_item)
        logger.debug(f"RLFF Feedback received. Queue size: {self.feedback_queue.qsize()}")

    async def monitor_and_tune_llm(self):
        """Background loop."""
        self.is_running = True
        batch_size = 10
        
        while self.is_running:
            if self.feedback_queue.qsize() >= batch_size:
                batch = []
                for _ in range(batch_size):
                    # CRITICAL FIX: Use get_nowait() to pull from the queue
                    try:
                        batch.append(self.feedback_queue.get_nowait())
                    except asyncio.QueueEmpty:
                        break # Should not happen if qsize >= batch_size
                
                logger.info(f"Tuning initiated on batch of {len(batch)} samples...")
                
                # CRITICAL FIX: Simulate the actual fine-tuning process (CPU-bound)
                await asyncio.to_thread(lambda: self._mock_tuning_process(batch)) 
                
                await self.publisher.publish_event(
                    "LLM_Update", {"version": f"new_v_{datetime.now().strftime('%H%M%S')}", "status": "DEPLOYED", "sample_count": len(batch)}, key="RLFF"
                )
                logger.info("LLM fine-tuning event published.")

            await asyncio.sleep(5)

    def _mock_tuning_process(self, batch: List[Dict]):
        """Synchronous mock for the CPU-bound fine-tuning task."""
        # In a real system, this would call a synchronous ML library
        import time
        time.sleep(1.0) # Simulate work
        # No return needed