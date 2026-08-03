# backend/services/agent_creation_service.py
"""AI Agent Creation Service for HRIT Managers/Admins.
Translates structured input into an executable AI Agent Configuration and initiates
the BPMN deployment workflow."""
import uuid
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field, ConfigDict, ValidationError 
from services.ai_services import AIService 
from services.bpmn_generator import create_agent_deployment_bpmn_sync 
from services.postgres_client import pg_client 
from services.event_publisher_service import EventPublisherService 
from config.settings import settings

logger = logging.getLogger(__name__)

# --- Pydantic Models for Input ---

class MemoryConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    type: str = Field(..., description="Type of memory: 'short_term', 'long_term', 'vector_db'.")
    ttl_minutes: int = Field(120, description="Time-to-live for memory chunks.")

class AgentTool(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    name: str = Field(..., description="Internal function/tool name (e.g., 'timesheet_recon').")
    description: str = Field(..., description="Human readable description for LLM system prompt.")

class AgentConfiguration(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    agent_name: str = Field(..., description="Unique, human-readable name for the new agent.")
    instructions_prompt: str = Field(..., description="The LLM's system prompt (defines personality/goal).")
    
    tool_names: List[str] = Field(..., description="List of tool names the agent needs access to.")
    
    data_product_dependencies: List[str] = Field(
        default_factory=list,
        description="List of UDM data products this agent needs to access (e.g., 'EmployeePIIDataProduct')."
    )
    memory_config: Optional[MemoryConfig] = Field(
        None,
        description="Configuration for the agent's long-term and short-term memory system."
    )
    
    user_id: str = Field("SYSTEM", exclude=True)

class AgentCreationService:
    """Core logic for orchestrating the LLM-driven agent configuration and deployment.""" 
    
    def __init__(self, ai_service: AIService, publisher: EventPublisherService, pg_client_instance=pg_client):
        self.ai_service = ai_service
        self.publisher = publisher
        self.pg_client = pg_client_instance
        self.model_name = getattr(settings, 'LLM_MODEL_NAME', 'gemini-pro')
        
        if not hasattr(publisher, 'TOPIC_AGENT_TASK_ASSIGNED'):
             publisher.TOPIC_AGENT_TASK_ASSIGNED = "agent.task.assigned" 
             
        logger.info("✓ Agent Creation Service initialized.")
        
    async def _create_db_status_record(self, agent_id: str, user_id: str, config: Dict[str, Any], bpmn_id: str, project_id: str) -> str:
        """
        Creates the initial implementation_status record in Postgres to track the deployment flow.
        """
        task_id = f"TASK-{uuid.uuid4().hex[:10].upper()}"
        initial_audit_trail = json.dumps({
            "initial_config": config,
            "bpmn_id": bpmn_id,
            "updates": [{"log": "Agent creation request received.", "timestamp": datetime.now(timezone.utc).isoformat()}]
        })
        
        query = """
            INSERT INTO implementation_status (task_id, project_id, status, agent_id, requester_id, audit_trail)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb)
        """
        
        try:
            await self.pg_client.execute(query, task_id, project_id, 'DRAFTED', agent_id, user_id, initial_audit_trail)
            logger.info(f"Initial DB record created: {task_id}")
            return task_id
        except Exception as e:
            logger.critical(f"Failed to create initial DB record: {e}")
            raise RuntimeError(f"Database error during initial setup: {e}")

    async def create_and_deploy_agent(self, nl_intent: str, user_id: str) -> Dict[str, Any]:
        """
        [ADVANCED FUNCTION] Translates NL intent to structured config and triggers the full deployment cycle.
        """
        logger.info(f"Starting complex agent creation from NL intent by {user_id}: {nl_intent}")
        
        # --- 1. LLM Structuring: NL Intent to Structured Config ---
        try:
            structuring_prompt = (
                f"Based on the following HRIT manager request: '{nl_intent}', "
                f"propose a comprehensive AgentConfiguration JSON object. "
                f"Available tools: ['query_compensation_db', 'audit_policy_changes', 'notify_hrit_team', 'execute_bpel_command']."
            )
            
            raw_config_data = await self.ai_service.generate_json_response(
                prompt=structuring_prompt,
                response_schema=AgentConfiguration.model_json_schema(),
                task_type="complex_generation"
            )
            
            if not raw_config_data:
                raise ValueError("LLM returned an empty or unparsable configuration.")
                
            structured_config = AgentConfiguration(**raw_config_data, user_id=user_id)
            
        except ValidationError as ve:
            error_details = json.dumps(ve.errors())
            raise ValueError(f"LLM generated an invalid configuration structure: {error_details}")
        except Exception as e:
            raise RuntimeError(f"Could not convert intent to valid agent configuration: {e}")
            
        # --- 2. Final Config Generation and Unique IDs ---
        agent_id = f"AGNT_{uuid.uuid4().hex[:10].upper()}"
        project_id = f"PRJ_{uuid.uuid4().hex[:8].upper()}" 
        
        final_agent_config = {
            "agent_id": agent_id,
            "agent_name": structured_config.agent_name,
            "instructions_prompt": structured_config.instructions_prompt, 
            "model": self.model_name,
            "tools": [{"name": name} for name in structured_config.tool_names], 
            "created_by": user_id,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        # --- 3. Create Initial DB Status Record (Get the real task_id) ---
        task_id = await self._create_db_status_record(agent_id, user_id, final_agent_config, "MOCK_BPMN_ID", project_id)
        
        # --- 4. Generate BPMN Deployment Flow with real IDs ---
        try:
            bpmn_result = await asyncio.to_thread(
                create_agent_deployment_bpmn_sync, 
                final_agent_config,
                task_id, 
                project_id
            )
        except Exception as e:
            raise RuntimeError(f"BPMN Generation Failed: {e}")

        # --- 5. Publish Event to Orchestrator to Start BPMN ---
        orchestrator_payload = {
            "task_id": task_id,
            "project_id": project_id,
            "bpmn_id": bpmn_result["id"],
            "agent_id": agent_id,
            "triggered_by": user_id
        }
        
        await self.publisher.publish_agent_task(
            task_data=orchestrator_payload,
            topic=self.publisher.TOPIC_AGENT_TASK_ASSIGNED, # This topic kicks off the BPMN engine
            key=project_id,
        )
        logger.info(f"Deployment process published for agent {agent_id}. Task ID: {task_id}")
        
        return {
            "message": f"AI Agent Factory: '{structured_config.agent_name}' configured and full deployment cycle (Test -> Approve -> Deploy) triggered.",
            "agent_id": agent_id,
            "bpmn_id": bpmn_result["id"],
            "task_id": task_id,
            "final_agent_config": final_agent_config
        }