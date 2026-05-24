# /backend/services/ultimate_orchestrator.py - REPLACEMENT (Integrating Test Automation & Autonomous Upgrade Agents)
import logging
import time
import json
import uuid
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timezone
from pydantic import BaseModel, Field, ConfigDict
import asyncio
import re
from config.settings import settings
from services.event_publisher_service import EventPublisherService
from services.enforcement_engine import runtime_enforcer
from services.workforce_planning_service import WorkforcePlanningService
from services.configuration_agent import ConfigurationAgent, generate_configuration_from_prompt, execute_gen_ui_command
from services.hr_modules import HRModulesService
from services.xai_wrapper import XAIWrapper
from services.ai_services import AIService
from services.total_talent_digital_twin_agent import DigitalTwinAgent
from services.utility_agents import TCOReductionAgent, QualityOrchestrationAgent
from services.policy_versioning import PolicyVersioningService, PolicyStatus
from services.postgres_client import pg_client
from services.ethical_agents import PLRAgent, SDFAgent, ESAgent, EOAgent, SPAgent
from services.bpel_agent import BPELAgent

# --- NEW AGENT IMPORTS ---
from services.vv_compiler import VVCompiler 
from services.test_automation_agent import TestAutomationAgent
from services.autonomous_upgrade_agent import AutonomousUpgradeAgent # NOTE: Requires a dict of services, not individual dependencies
# -------------------------

from utils.custom_exceptions import PolicyViolationError, ServiceUnavailableError, InvalidInputError, ResourceNotFoundError, DataProcessingError
from services.agent_spec_dsl import TriggerType
logger = logging.getLogger(__name__)
# Constants
PHASE_CONFIGURATION = "CONFIGURATION"
AGENT_CONFIGURATION = "ConfigurationAgent"

# --- Models ---
class PolicyImplementationCommand(BaseModel):
    version_id: str = Field(..., description="The version ID of the policy (must be in REVIEW or APPROVED status).")
    initiator_id: str = Field(..., description="The user initiating the deployment (HRIT Manager).")
    policy_id: str = Field(..., description="The core policy identifier.")

class FullAgentCommand(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    target_agent: str
    employee_id: Optional[str] = None
    prompt: Optional[str] = None
    data_context: Optional[Dict[str, Any]] = None

# --- Orchestrator Core Planner ---
class OrchestratorPlanner:
    def __init__(self, services: Dict[str, Any]):
        self.services = services
        self.agent_map = self._create_agent_map(services)
        self.pvs: PolicyVersioningService = services.get('policy_versioning_service')
        self.publisher: EventPublisherService = services.get('event_publisher')
        self.pg_client = services.get('pg_client', pg_client)
        logger.info(f"OrchestratorPlanner Initialized. Agents available: {list(self.agent_map.keys())}")

    def _create_agent_map(self, services: Dict[str, Any]) -> Dict[str, Any]:
        """Maps agent IDs to callable service instances."""

        ai_service = services.get('ai_service')
        policy_versioning_service = services.get('policy_versioning_service')
        event_publisher = services.get('event_publisher') 
        vv_compiler_service = services.get('vv_compiler_service') # Assumed to be configured externally

        return {
            "ultimate_orchestrator": self,
            "configuration_agent": services.get('configuration_agent'),
            "hr_modules": services.get('hr_modules_service'),
            "workforce_ai": services.get('wfp_service'),
            "digital_twin_agent": services.get('digital_twin_agent'),
            "policy_versioning": policy_versioning_service,
            "xai_explainer": services.get('xai_wrapper'),
            "bpel_agent": BPELAgent(ai_service=ai_service, policy_versioning_service=policy_versioning_service),
            
            # --- AGENTS ADDED FOR DEPLOYMENT WORKFLOW ---
            "test_automation_agent": TestAutomationAgent(
                publisher=event_publisher,
                vv=vv_compiler_service, # VVCompiler instance
                pg_client_instance=self.pg_client
            ), 
            "autonomous_upgrade_agent": AutonomousUpgradeAgent(
                services=services # AutonomousUpgradeAgent takes the full services dict
            ),
            # ---------------------------------------------
            
            "tco_agent": TCOReductionAgent(),
            "quality_agent": QualityOrchestrationAgent(),
            "plr_agent": PLRAgent(ai_service=ai_service),
            "sdf_agent": SDFAgent(ai_service=ai_service),
            "esa_agent": ESAgent(ai_service=ai_service),
            "eoa_agent": EOAgent(ai_service=ai_service),
            "spa_agent": SPAgent(ai_service=ai_service),
        }
    
    async def _execute_sync_agent_call(self, agent_id: str, method_name: str, *args, **kwargs) -> Dict[str, Any]:
        """
        Universal wrapper for executing synchronous agent methods in a thread.
        """
        agent = self.agent_map.get(agent_id)
        if not agent:
            raise ResourceNotFoundError(f"Agent '{agent_id}' not found in map.")

        method = getattr(agent, method_name, None)
        if not method or not callable(method):
            raise InvalidInputError(f"Method '{method_name}' not found on agent '{agent_id}'.")

        return await asyncio.to_thread(method, *args, **kwargs)

    async def dispatch_command(self, agent_command: FullAgentCommand) -> Dict[str, Any]:
        """Routes the command to the appropriate agent."""

        target = agent_command.target_agent.lower()
        prompt = agent_command.prompt or ""
        agent = self.agent_map.get(target) # Fetch agent instance early

        if target == "configuration_agent":
            if "gen ui command" in prompt.lower():
                return await execute_gen_ui_command(prompt, agent_command.data_context)
            if "generate bpcl" in prompt.lower():
                # CRITICAL FIX: Direct call to SelfCorrectingAgent sync method would be here, but falls back to simple logic
                return await asyncio.to_thread(generate_configuration_from_prompt, prompt)
        
        # --- NEW DISPATCH FOR DEPLOYMENT WORKFLOW AGENTS ---
        if target == "test_automation_agent":
             if 'task_data' in (agent_command.data_context or {}):
                if not agent: raise ServiceUnavailableError("Test Automation Agent is not initialized.")
                task_data = agent_command.data_context['task_data']
                return {"test_successful": await agent.execute_testing(task_data)}
             raise InvalidInputError("Test Automation Agent requires 'task_data' in data_context.")
             
        if target == "autonomous_upgrade_agent":
            if 'agent_config' in (agent_command.data_context or {}):
                if not agent: raise ServiceUnavailableError("Autonomous Upgrade Agent is not initialized.")
                return await agent.deploy_validated_agent_config(
                    agent_command.data_context['agent_config'],
                    agent_command.data_context.get('task_id')
                )
            raise InvalidInputError("Autonomous Upgrade Agent requires 'agent_config' in data_context.")
        # -----------------------------------------------------

        if target == "tco_agent":
            return await self._execute_sync_agent_call(
                agent_id="tco_agent",
                method_name="generate_cost_forecast",
                workload=prompt,
                current_cost=agent_command.data_context.get('current_cost', 1000.0)
            )

        if target in ["sdf_agent", "esa_agent", "eoa_agent", "spa_agent", "quality_agent", "plr_agent"]:
             if not agent: raise ResourceNotFoundError(f"Target agent '{target}' is not recognized or initialized.")
            
             # Handle direct calls for synchronous methods
             if target == "eoa_agent":
                 return await self._execute_sync_agent_call("eoa_agent", "get_semantic_mapping", prompt)
             if target == "spa_agent":
                 return await self._execute_sync_agent_call("spa_agent", "analyze_social_silos", prompt)
             if target == "quality_agent":
                 return await self._execute_sync_agent_call("quality_agent", "run_gate_check", prompt)
            
             # Handle asynchronous calls for ethical agents
             if target == 'plr_agent' and 'simulation' in prompt.lower():
                 method = getattr(agent, 'run_adversarial_simulation')
                 return await method(prompt) # PLRAgent takes prompt as scenario string

             # Fallback: Attempt to use generic context or prompt
             raise InvalidInputError(f"Agent '{target}' does not expose a recognized execution interface or command.")
                
        if target == "bpel_agent":
            if not agent: raise ServiceUnavailableError("BPEL Agent is not initialized.")
            policy_id = agent_command.data_context.get('policy_version_id')
            if policy_id:
                return await agent.deploy_policy_workflow(policy_id)
            else:
                raise InvalidInputError("BPEL Agent requires 'policy_version_id' in data_context.")
                
        # Handle predictive agents (WFP, DTLA)
        if target == 'workforce_ai' and 'attrition' in prompt.lower():
            method = getattr(self.agent_map.get(target), 'predict_attrition_risk')
            return await method(employee_data=agent_command.data_context)
        
        if target == 'digital_twin_agent' and 'simulation' in prompt.lower():
            method = getattr(self.agent_map.get(target), 'async_run_prescriptive_simulation')
            return await method(scenario_data=agent_command.data_context)
            
        raise InvalidInputError(f"Target agent '{target}' does not expose a recognized execution interface or command.")


    async def implement_policy_from_scraping(self, command: PolicyImplementationCommand) -> Dict[str, Any]:
        """
        [CRITICAL NEW METHOD] Triggers the full deployment/testing cycle for a policy that
        originated from the Scraping Agent and has been human-approved (or is ready to deploy).
        """
        version_id = command.version_id
        initiator_id = command.initiator_id
        policy_id = command.policy_id

        # 1. Verify policy status and existence
        version = await asyncio.to_thread(self.pvs.get_version_by_id, version_id)
        if not version:
            raise ResourceNotFoundError(f"Policy version {version_id} not found.")

        if version.status != PolicyStatus.REVIEW and version.status != PolicyStatus.APPROVED:
            raise InvalidInputError(f"Policy version {version_id} must be in REVIEW or APPROVED status to be implemented.")

        # 2. Extract policy content (the artifact)
        artifact_config = {
            "artifact_type": "BPCL_POLICY",
            "policy_id": policy_id,
            "version_id": version_id,
            "policy_content": version.content,
            "instructions_prompt": version.changelog or f"Regulatory update from {policy_id}.",
            "created_by": initiator_id
        }
        # 3. Create initial DB status record and trigger BPMN (Agent Factory Cycle)
        project_id = f"POL_{policy_id}_{uuid.uuid4().hex[:4].upper()}"

        # Mock BPMN generation for tracking purposes
        bpmn_id = f"DEPLOY_POL_{policy_id}_{version.version_number}"

        # Create the status record 
        task_id = f"TASK-{uuid.uuid4().hex[:10].upper()}"
        initial_audit_trail = json.dumps({
            "initial_config": artifact_config,
            "bpmn_id": bpmn_id,
            "updates": [{"log": "Policy implementation requested.", "timestamp": datetime.now(timezone.utc).isoformat()}]
        })

        try:
            await self.pg_client.execute(
                """INSERT INTO implementation_status (task_id, project_id, status, agent_id, requester_id, audit_trail)
                VALUES ($1, $2, $3, $4, $5, $6::jsonb)""",
                task_id, project_id, 'POLICY_DRAFTED', policy_id, initiator_id, initial_audit_trail
            )
        except Exception as e:
            raise RuntimeError(f"Database error during policy implementation setup: {e}")

        # 4. Publish Event to Orchestrator Listener to Start BPMN Flow
        orchestrator_payload = {
            "task_id": task_id,
            "project_id": project_id,
            "bpmn_id": bpmn_id,
            "agent_id": policy_id, # Policy ID acts as the system identifier
            "version_id": version_id,
            "triggered_by": initiator_id
        }

        # The Listener must consume this event and call the TestAutomationAgent
        await self.publisher.publish_agent_task(
            task_data=orchestrator_payload,
            topic=self.publisher.TOPIC_AGENT_TASK_ASSIGNED,
            key=project_id,
        )
        return {
            "status": "IMPLEMENTATION_TRIGGERED",
            "policy_id": policy_id,
            "version_id": version_id,
            "task_id": task_id,
            "message": f"Implementation flow for policy {policy_id} triggered. Awaiting test results."
        }


async def execute_orchestration(
    agent_command: Union[FullAgentCommand, PolicyImplementationCommand],
    services: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Main orchestration entry point.
    """
    start_ts = time.perf_counter()
    event_publisher: EventPublisherService = services['event_publisher']
    planner = OrchestratorPlanner(services)

    report = {
        "command": agent_command.model_dump(),
        "execution_trace": [f"[INFO] Command received: {agent_command.target_agent if hasattr(agent_command, 'target_agent') else agent_command.policy_id}"],
        "final_status": "PENDING",
        "cognitive_report": {},
    }

    try:
        # CRITICAL FIX: Determine if it's a policy implementation command or a regular agent command
        if isinstance(agent_command, PolicyImplementationCommand):
            try:
                # Direct call to the specific implementation handler
                agent_response = await planner.implement_policy_from_scraping(agent_command)
                report["cognitive_report"]["agent_response"] = agent_response
                report["final_status"] = "IMPLEMENTATION_TRIGGERED"
            except Exception as e:
                report["final_status"] = "POLICY_SETUP_FAILED"
                report["error"] = str(e)
                raise DataProcessingError(f"Policy implementation failed: {type(e).__name__}: {e}")

        else:
            # Regular FullAgentCommand execution flow
            try:
                # 1. PRE-ENFORCEMENT CHECK (Only for sensitive actions like Timesheets/Leave)
                if agent_command.target_agent.lower() == "hr_modules" and "submit" in (agent_command.prompt or "").lower():
                    report["execution_trace"].append("[PHASE] Running Pre-Enforcement Check...")

                    trigger_type = TriggerType.LEAVE_REQUEST_SUBMIT.value if 'leave' in (agent_command.prompt or "").lower() else TriggerType.TIME_CLOCK_IN.value

                    enforcement_result = await runtime_enforcer.execute_dsl_check(
                        trigger_type,
                        agent_command.data_context
                    )
                    report["cognitive_report"]["enforcement"] = enforcement_result
                    report["execution_trace"].append(f"[RESULT] Enforcement Decision: {enforcement_result['decision']}")
                    if enforcement_result['decision'] in ["STOP", "BLOCK"]:
                        await event_publisher.publish_event(
                            "policy.violation",
                            {"policy_id": enforcement_result.get('rule_id'), "reason": enforcement_result['reason']},
                            key=agent_command.employee_id
                        )
                        raise PolicyViolationError(detail=f"Policy Block: {enforcement_result['reason']}")
                
                # 2. DISPATCH COMMAND
                report["execution_trace"].append(f"[PHASE] Dispatching to agent: {agent_command.target_agent}")

                agent_response = await planner.dispatch_command(agent_command)

                report["cognitive_report"]["agent_response"] = agent_response
                report["final_status"] = agent_response.get("status", "COMPLETED")
                report["execution_trace"].append(f"[RESULT] Agent completed with status: {report['final_status']}")

                # 3. POST-ENFORCEMENT / RESPONSE ENRICHMENT
                if agent_command.target_agent.lower() == "configuration_agent" and "bpcl" in (agent_command.prompt or "").lower():
                    report["raw_bpcl_code"] = agent_response.get("bpcl_content", "")
                    report["final_status"] = "CONFIGURATION_GENERATED"

            except PolicyViolationError as e:
                report["final_status"] = "POLICY_VIOLATION"
                report["error"] = str(e)
                report["execution_trace"].append(f"[ERROR] Policy Block: {getattr(e, 'detail', str(e))}")
                raise e

            except ResourceNotFoundError as e:
                report["final_status"] = "RESOURCE_NOT_FOUND"
                report["error"] = str(e)
                report["execution_trace"].append(f"[ERROR] Resource Not Found: {str(e)}")
                raise e

            except ServiceUnavailableError as e:
                report["final_status"] = "SERVICE_UNAVAILABLE"
                report["error"] = str(e)
                report["execution_trace"].append(f"[ERROR] Service Unavailable: {str(e)}")
                raise e

            except Exception as e:
                logger.error(f"Orchestration Error: {e}", exc_info=True)

                report["final_status"] = "FAILED"
                report["error"] = str(e)
                report["execution_trace"].append(f"[FATAL] Unhandled Orchestration Error: {type(e).__name__} - {str(e)}")
                raise DataProcessingError(f"Orchestration failed: {type(e).__name__}: {e}")
    
    finally:
        report["total_execution_ms"] = (time.perf_counter() - start_ts) * 1000
        await event_publisher.publish_event(
            "orchestrator.execution.report",
            {"report": report, "timestamp": datetime.now(timezone.utc).isoformat()},
            key=agent_command.employee_id if hasattr(agent_command, 'employee_id') and agent_command.employee_id else (getattr(agent_command, 'policy_id', 'SYSTEM'))
        )
        # If it was a policy command, return the final report structure
        if isinstance(agent_command, PolicyImplementationCommand):
            return report
        # Otherwise, return the agent's response from the cognitive report
        return report["cognitive_report"].get("agent_response", report)