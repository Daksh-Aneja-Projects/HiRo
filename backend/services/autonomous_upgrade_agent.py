# /backend/services/autonomous_upgrade_agent.py - REPLACEMENT (Transactional Deployment Logic - FINAL)
import logging
import asyncio
import json
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import random 
import uuid 

try:
    import httpx
except ImportError:
    httpx = None

from config.settings import settings
from services.postgres_client import pg_client 
from services.event_publisher_service import EventPublisherService 

logger = logging.getLogger(__name__)

class SyntheticTwinEnginePlaceholder:
    async def run_simulation(self, employee_id, adjustments, simulation_type):
        await asyncio.sleep(0.01)
        return {"result": "mock"}

class AutonomousUpgradeAgent:
    """
    Agent responsible for monitoring health and executing final, validated deployments.
    Acts as the final stage of the CI/CD pipeline, publishing the successful deployment event.
    """
    def __init__(self, services: Dict[str, Any]):
        self.services = services
        self.ai_service = services.get('ai_service')
        self.publisher: Optional[EventPublisherService] = services.get('event_publisher')
        self.pg_client = services.get('pg_client', pg_client)
        self._http_client = httpx.AsyncClient(timeout=settings.EXTERNAL_API_TIMEOUT_SECONDS) if httpx else None
        
        # CRITICAL FIX: Ensure task complete topic exists for the final deployment signal
        if self.publisher and not hasattr(self.publisher, 'TOPIC_AGENT_TASK_COMPLETE'):
            self.publisher.TOPIC_AGENT_TASK_COMPLETE = "agent.task.complete"
            
        logger.info("✓ Autonomous Upgrade Agent Initialized.")

    # ... (run_environment_health_check, _check_ai_service, and trigger_autonomous_upgrade remain the same) ...

    async def deploy_validated_agent_config(self, agent_config: Dict[str, Any], task_id: str) -> Dict[str, Any]:
        """
        [DEPRECATED: LEGACY INTERFACE] Simulates final deployment. 
        Execution is now contained within execute_deployment_task for event-driven compatibility.
        """
        # This function serves only as a compatibility layer for the OrchestratorPlanner dispatch 
        # but the real work happens in the execution method below.
        
        # We assume this config came from the successful approval flow.
        task_data = {
            "task_id": task_id,
            "project_id": task_id, # Mock for simplicity
            "data_context": {
                "agent_config": agent_config,
                "task_id": task_id
            }
        }
        return await self.execute_deployment_task(task_data)

    async def execute_deployment_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        [CRITICAL ENTRY POINT] Executes the deployment task based on the Orchestrator's assignment event.
        This is the final, transactional deployment of the agent.
        """
        task_id = task_data.get('task_id')
        project_id = task_data.get('project_id')
        
        data_context = task_data.get('data_context', {})
        agent_config = data_context.get('agent_config', {})
        
        agent_id = agent_config.get('agent_id', 'UNKNOWN')
        agent_name = agent_config.get('agent_name', 'Unknown Agent')
        
        logger.warning(f"Final deployment triggered for validated Agent: {agent_id}. Simulating production rollout...")
        
        # 1. Simulate Deployment Time
        await asyncio.sleep(1.5)

        # 2. Prepare Data and Transaction
        current_time_iso = datetime.now(timezone.utc).isoformat()
        update_details = json.dumps({"log": "Agent successfully deployed to production.", "timestamp": current_time_iso})
        
        event_data = {
            "task_id": task_id, 
            "project_id": project_id,
            "completed_successfully": True, # Always True on successful transaction
            "agent_id": agent_id, 
            "status": "DEPLOYED", 
            "config_summary": {"name": agent_name}
        }
        
        try:
            # CRITICAL FIX: Use a transaction to ensure DB update and event publish are atomic.
            async with self.pg_client.transaction("AutonomousUpgradeAgent", "final_deploy_event") as conn:
                # A. Update DB Status (Marking the task as fully deployed)
                await conn.execute(
                    """UPDATE implementation_status SET status=$1, completed_at=$2, audit_trail=jsonb_set(audit_trail, '{deployment_result}', $3::jsonb) WHERE task_id=$4""",
                    'DEPLOYED', current_time_iso, update_details, task_id
                )
                
                # B. Publish final deployment event (The definitive signal of completion)
                if self.publisher:
                    await self.publisher.publish_agent_task(
                        task_data=event_data,
                        topic=self.publisher.TOPIC_AGENT_TASK_COMPLETE,
                        key=agent_id
                    )
            
            return {
                "status": "AGENT_ACTIVE",
                "agent_id": agent_id,
                "message": f"Agent {agent_id} successfully rolled out to production (Simulated)."
            }
            
        except Exception as e:
            logger.error(f"CRITICAL: Failed to finalize deployment transaction for {task_id}: {e}")
            
            # Publish a failure event for Orchestrator remediation if the transaction fails
            if self.publisher:
                await self.publisher.publish_agent_task(
                    task_data={**event_data, "completed_successfully": False, "failure_reason": str(e)},
                    topic=self.publisher.TOPIC_POLICY_VIOLATION, # Use violation topic for deployment failure
                    key=agent_id
                )
                
            raise RuntimeError(f"Deployment finalization failed: {e}")