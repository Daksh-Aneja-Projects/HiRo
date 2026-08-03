# backend/services/bpmn_generator.py

import uuid
from typing import Dict, Any, List
import logging
from datetime import datetime, timezone 
from config.settings import settings
import asyncio

logger = logging.getLogger(__name__)

# -- Configuration Constants --
DEFAULT_START_NAME = getattr(settings, 'BPMN_DEFAULT_START_NAME', "Start Process")
DEFAULT_POLICY_CHECK_NAME = getattr(settings, 'BPMN_DEFAULT_POLICY_CHECK_NAME', "Policy Check")
DEFAULT_DECISION_NAME = getattr(settings, 'BPMN_DEFAULT_DECISION_NAME', "Conditions Met?")
DEFAULT_FINAL_APPROVAL_NAME = getattr(settings, 'BPMN_DEFAULT_FINAL_APPROVAL_NAME', "Final Approval")
DEFAULT_END_NAME = getattr(settings, 'BPMN_DEFAULT_END_NAME', "Process Complete")
SYSTEM_ASSIGNEE = getattr(settings, 'BPMN_SYSTEM_ASSIGNEE', "SYSTEM")
MANAGER_ASSIGNEE = getattr(settings, 'BPMN_MANAGER_ASSIGNEE', "MANAGER")
POLICY_CHECK_CONDITION = getattr(settings, 'BPMN_POLICY_CHECK_CONDITION', "IF Conditions")
ADMIN_ASSIGNEE = getattr(settings, 'BPMN_ADMIN_ASSIGNEE', "ADMIN")

class BpmnGeneratorService:
    """Service class to handle the conversion of BPCL to BPMN structures."""

    def convert_bpcl_to_bpmn(self, bpcl_code: str) -> Dict[str, Any]:
        """[SYNCHRONOUS] Converts BPCL code to a mock BPMN structure."""
        bpmn_id = f"BPMN-{uuid.uuid4().hex[:8].upper()}"
        
        # Simple mock conversion logic
        return {
            "id": bpmn_id,
            "name": f"Workflow_{bpcl_code[:10]}",
            "steps": [
                {"id": "start", "type": "start", "name": DEFAULT_START_NAME, "next": "s1"},
                {"id": "s1", "type": "service_task", "name": "Parse BPCL", "next": "end",
                 "properties": {"bpcl_code_length": len(bpcl_code)}}, 
                {"id": "end", "type": "end", "name": DEFAULT_END_NAME}
            ]
        }
        
    def create_agent_deployment_bpmn(self, agent_config: Dict[str, Any], task_id: str, project_id: str) -> Dict[str, Any]:
        """
        Generates a standardized BPMN for agent deployment, linked to a specific task.
        """
        
        agent_id = agent_config.get('agent_id', uuid.uuid4().hex[:10].upper())
        agent_name = agent_config.get('agent_name', "Unknown Agent")
        
        bpmn = {
            "id": f"DEPLOY_{agent_id}",
            "name": f"Agent Deployment: {agent_name}",
            "steps": [
                {"id": "start", "type": "start", "name": DEFAULT_START_NAME, "next": "t1"},
                
                # T1: Validation and Verification (VV)
                {"id": "t1", "type": "service_task", "name": "VV Compiler Check (Syntax/Security)", "next": "t2",
                 "properties": {"service": "VVCompiler"}},
                 
                # T2: Test verification is a human step today; no automated test agent exists.
                {"id": "t2", "type": "user_task", "name": "Verify Test Results", "next": "g1",
                 "properties": {"assignee": ADMIN_ASSIGNEE, "task_id": task_id, "project_id": project_id}},
                
                # G1: Decision Gateway (Test Passed?)
                {"id": "g1", "type": "exclusive_gateway", "name": "Tests Passed?", "next": [
                    {"id": "t3", "condition": "tests_passed == true"}, 
                    {"id": "t4", "condition": "tests_passed == false"}
                ]},
                
                # T3: Manual HRIT Approval
                {"id": "t3", "type": "user_task", "name": "HRIT Manager Final Approval", "next": "t5",
                 "properties": {"assignee": ADMIN_ASSIGNEE, "condition": "tests_passed == true"}},
                 
                # T5: Deployment is a human step today; no autonomous deployment agent exists.
                {"id": "t5", "type": "user_task", "name": "Deploy Agent to Production", "next": "end",
                 "properties": {"assignee": ADMIN_ASSIGNEE, "agent_id": agent_id, "config": agent_config, "task_id": task_id}},
                 
                # T4: Failure End State
                {"id": "t4", "type": "end", "name": "Tests Failed - STOP",
                 "properties": {"condition": "tests_passed == false"}},
                 
                # End State
                {"id": "end", "type": "end", "name": DEFAULT_END_NAME}
            ],
            "metadata": {
                "source": "AGENT_GENERATOR", 
                "agent_config": agent_config,
                "generated_at": datetime.now(timezone.utc).isoformat() 
            }
        }
        
        logger.info(f"Agent Deployment BPMN generated with ID {bpmn['id']}")
        return bpmn

# Singleton
bpmn_generator = BpmnGeneratorService()

def convert_bpcl_to_bpmn_sync(bpcl_code: str) -> Dict[str, Any]:
    """Synchronous wrapper for external use."""
    return bpmn_generator.convert_bpcl_to_bpmn(bpcl_code)

def create_agent_deployment_bpmn_sync(agent_config: Dict[str, Any], task_id: str, project_id: str) -> Dict[str, Any]:
    """Synchronous wrapper for the agent deployment BPMN generation."""
    return bpmn_generator.create_agent_deployment_bpmn(agent_config, task_id, project_id)