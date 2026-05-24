# services/integration_agent.py - REPLACEMENT (Error and Event Handling and Transactional Integrity)
import logging
import json
from typing import Dict, Any
from services.postgres_client import pg_client
from services.external_api_connector import ExternalAPIConnector
from services.event_publisher_service import EventPublisherService
import asyncio 

logger = logging.getLogger(__name__)

class IntegrationAgent:
    """
    Prompt-to-Integration Agent: Manages persistence of external integration configuration 
    and triggers external API calls based on orchestrated commands.
    """
    def __init__(self, publisher: EventPublisherService, api_connector: ExternalAPIConnector):
        self.pub = publisher
        self.conn = api_connector
        if not hasattr(publisher, 'TOPIC_POLICY_VIOLATION'):
             publisher.TOPIC_POLICY_VIOLATION = "policy.violation"
        # CRITICAL FIX: Ensure completion topic is available
        if not hasattr(publisher, 'TOPIC_AGENT_TASK_COMPLETE'):
             publisher.TOPIC_AGENT_TASK_COMPLETE = "agent.task.complete"
             
        logger.info("✓ IntegrationAgent Initialized (Persistent Mode).")

    async def _update_state(self, integration_id: str, status: str, config: Dict):
        """Updates integration status in the Postgres configuration table transactionally."""
        query = """
            INSERT INTO integrations_config (integration_id, status, config, last_updated)
            VALUES ($1, $2, $3::jsonb, NOW())
            ON CONFLICT (integration_id) DO UPDATE 
            SET status = $2, config = $3::jsonb, last_updated = NOW()
        """
        # CRITICAL FIX: Execute within a transaction for integrity
        async with pg_client.transaction("IntegrationAgent", "state_update"):
            await pg_client.execute(query, integration_id, status, json.dumps(config))

    async def execute_integration_task(self, task_id: str, project_id: str, instr: Dict) -> Dict:
        """
        Idempotent integration handler.
        The prompt (via Orchestrator) translates to the action and config.
        """
        int_id = instr.get("integration_id")
        action = instr.get("action")
        
        if not int_id or not action:
            raise ValueError("Missing 'integration_id' or 'action' in instructions.")

        status = "UNKNOWN"
        success = False
        
        try:
            # 1. External Action (Simulate Prompt-Driven Connectivity)
            if action == "CREATE":
                # CRITICAL: Prompt-driven setup of a new connection
                res = await self.conn.setup_integration_connection(int_id, instr.get("config"))
                status = "ACTIVE" if res.get('success') else "FAILED"
            
            elif action == "SYNC":
                # CRITICAL: Prompt-driven sync initiation
                res = await self.conn.start_bidirectional_sync(int_id)
                status = "SYNCING" if res.get('success') else "ERROR"
            
            else:
                 raise ValueError(f"Unknown action: {action}")

            # 2. Persist State
            await self._update_state(int_id, status, instr.get("config", {}))
            
            success = status in ["ACTIVE", "SYNCING"]
            
            # 3. Notify Orchestrator (Success/Failure)
            topic = self.pub.TOPIC_AGENT_TASK_COMPLETE if success else self.pub.TOPIC_POLICY_VIOLATION
            
            await self.pub.publish_agent_task(
                {
                    "task_id": task_id, 
                    "project_id": project_id, 
                    "completed_successfully": success,
                    "final_status": status,
                    "integration_id": int_id,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                },
                topic,
                key=project_id
            )
            
            if not success:
                 raise RuntimeError(f"Integration failed for action {action}. Final status: {status}")
            
            return {"status": "SUCCESS", "state": status}

        except Exception as e:
            logger.error(f"Integration Failed: {type(e).__name__}: {e}")
            
            # CRITICAL FIX: Ensure failure event is published before raising
            failure_details = {
                "task_id": task_id, 
                "project_id": project_id, 
                "completed_successfully": False, 
                "failure_details": [str(e)],
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            await self.pub.publish_agent_task(
                failure_details,
                self.pub.TOPIC_POLICY_VIOLATION,
                key=project_id
            )
            raise RuntimeError(f"Integration Task Failed: {e}")