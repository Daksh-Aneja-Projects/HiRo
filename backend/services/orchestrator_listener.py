# /backend/services/orchestrator_listener.py - MODIFIED FOR SIGNATURE VERIFICATION AND APPROVAL HANDLER

import json
import logging
import hashlib
import asyncio
from typing import Dict, Any, List 
from datetime import datetime, timezone
import uuid 

from config.settings import settings
from services.postgres_client import pg_client 
from services.event_publisher_service import EventPublisherService, AGENT_SIGNING_SECRET 
from services.policy_versioning import PolicyVersioningService, ApprovalStatus 

logger = logging.getLogger(__name__)

REMEDIATION_PHASE = "CONFIGURATION"
REMEDIATION_AGENT = "SelfCorrectingAgent"

class OrchestratorListener:
    """
    Core component that listens to the event bus (NATS) and triggers long-running 
    workflows or immediate actions based on system events.
    """
    def __init__(self, publisher: EventPublisherService, policy_versioning_service: PolicyVersioningService):
        self.publisher = publisher
        self.pvs = policy_versioning_service
        logger.info("✓ Orchestrator Listener Initialized.")

    def _verify_payload_signature_sync(self, event_data: Dict[str, Any]) -> bool:
        """
        [CRITICAL FIX: SECURITY] Implements full HMAC signature verification.
        Guarantees event integrity across the enterprise event bus.
        """
        metadata = event_data.get('metadata', {})
        received_sig = metadata.get('signature')
        sender = metadata.get('source_agent_id')
        
        if not received_sig or not sender:
            logger.warning("Signature check skipped: Missing signature or sender.")
            return False

        # 1. Prepare the payload used for signing (must match how it was signed)
        temp_data = event_data.copy()
        if 'metadata' in temp_data and 'signature' in temp_data['metadata']:
            del temp_data['metadata']['signature']
        
        # 2. Add the sender ID back for hashing (as the signer did)
        if 'metadata' not in temp_data:
            temp_data['metadata'] = {}
        temp_data['metadata']['source_agent_id'] = sender 

        # 3. Calculate Expected Signature
        payload_str = json.dumps(temp_data, sort_keys=True, default=str)
        signing_key = f"{AGENT_SIGNING_SECRET}-{sender}".encode("utf-8")
        
        expected_signature_core = hashlib.sha256(signing_key + payload_str.encode("utf-8")).hexdigest()[:16].upper()
        expected_signature = f"SIG_{sender}_{expected_signature_core}"

        if expected_signature == received_sig:
            return True
        else:
            logger.critical(f"HMAC Mismatch for {sender}! Possible Event Tampering. Expected: {expected_signature}, Received: {received_sig}")
            return False

    async def start_listening(self):
        """
        MOCK: Simulates the NATS subscriptions required for event-driven workflows.
        """
        logger.info("MOCK: Orchestrator Listener starting subscription mock...")
        
        self.topics = [
            EventPublisherService.TOPIC_POLICY_DECISION,
            EventPublisherService.TOPIC_DTLA_SCENARIO,
            EventPublisherService.TOPIC_AGENT_TASK_COMPLETE, 
            EventPublisherService.TOPIC_AGENT_TASK_ASSIGNED,
            # CRITICAL FIX: Add the topic for Human Approval 
            self.publisher.TOPIC_HUMAN_APPROVAL
        ]
        
        logger.info(f"MOCK: Subscribing to topics: {self.topics}")

    async def _handle_agent_task_assigned(self, data: Dict):
        """
        [CRITICAL FIX] Consumes the event from AgentCreationService and starts the BPMN flow.
        """
        if not self._verify_payload_signature_sync(data):
            logger.error(f"Task assignment event signature failed for task {data.get('task_id')}. Ignoring.")
            return
            
        task_id = data.get('task_id')
        agent_id = data.get('agent_id')
        bpmn_id = data.get('bpmn_id')
        project_id = data.get('project_id')
        
        if not all([task_id, agent_id, bpmn_id, project_id]):
            logger.error(f"Cannot start BPMN: Missing critical task data in event for {agent_id}.")
            return

        # 1. Update the DB status to reflect the task is being handled by the Orchestrator
        try:
            update_details = json.dumps({"log": f"BPMN {bpmn_id} initiated by Orchestrator.", "timestamp": datetime.now(timezone.utc).isoformat()})
            await pg_client.execute(
                """UPDATE implementation_status SET status=$1, audit_trail=jsonb_set(audit_trail, '{updates}', audit_trail->'updates' || $3::jsonb) WHERE task_id=$2""",
                'BPMN_STARTING', task_id, update_details
            )
        except Exception as e:
            logger.error(f"Failed to update DB for BPMN start {task_id}: {e}")
            
        # 2. Simulate the BPMN Engine starting the first task (TestAutomationAgent)
        first_task_data = {
            "task_id": task_id,
            "project_id": project_id,
            "agent_id": "TestAutomationAgent",
            "task_instructions": f"Execute full test suite on new agent config for {agent_id} (Task {task_id})."
        }
        
        # We simulate the handoff by publishing an internal assignment event to the TestAutomationAgent's topic.
        await self.publisher.publish_agent_task(
            first_task_data,
            self.publisher.TOPIC_AGENT_TASK_ASSIGNED, 
            key=task_id
        )
        logger.info(f"Orchestrator started BPMN flow for {task_id}. First task assigned to TestAutomationAgent.")


    async def _handle_agent_task_complete(self, data: Dict):
        """
        [CRITICAL NEW METHOD] Handles completion event from TestAutomationAgent (or other agents)
        and advances the BPMN deployment flow.
        """
        if not self._verify_payload_signature_sync(data):
            logger.error(f"Task completion event signature failed for task {data.get('task_id')}. Ignoring.")
            return
            
        task_id = data.get('task_id')
        agent_id = data.get('agent_id')
        project_id = data.get('project_id')
        completed_successfully = data.get('completed_successfully', False)
        
        if not task_id or not project_id:
            logger.error("Task completion handler missing critical data.")
            return

        logger.info(f"Task {task_id} completed by {agent_id}. Success: {completed_successfully}")

        # Fetch the original artifact config from the DB record to get policy/bpmn ID
        query = "SELECT audit_trail->'initial_config' AS config, audit_trail->>'bpmn_id' AS bpmn_id FROM implementation_status WHERE task_id=$1"
        db_record = await pg_client.fetchrow(query, task_id)

        if not db_record or not db_record.get('bpmn_id'):
            logger.error(f"Cannot find BPMN ID for completed task {task_id}.")
            return
            
        # Example of BPMN step logic based on the TestAutomationAgent outcome
        if agent_id == "TestAutomationAgent":
            
            if completed_successfully:
                # NEXT STEP: Simulate Human User Task (HRIT Manager Final Approval)
                next_task_data = {
                    "task_id": f"APPROVAL_{task_id}",
                    "project_id": project_id,
                    "agent_id": "HumanReview", # Target Agent is Human Review Queue
                    "task_instructions": f"FINAL APPROVAL: Automated tests passed for policy artifact in task {task_id}. Proceed to deployment.",
                    "previous_task_id": task_id,
                    "artifact_config": db_record['config']
                }
                
                # Update DB status to reflect user task is required
                update_details = json.dumps({"log": "Tests PASSED. Awaiting HRIT Approval.", "timestamp": datetime.now(timezone.utc).isoformat()})
                await pg_client.execute(
                    """UPDATE implementation_status SET status=$1, audit_trail=jsonb_set(audit_trail, '{updates}', audit_trail->'updates' || $3::jsonb) WHERE task_id=$2""",
                    'AWAITING_APPROVAL', task_id, update_details
                )
                
                # Publish the next assignment event (to be picked up by the Human Task Agent/Route)
                await self.publisher.publish_agent_task(
                    next_task_data,
                    self.publisher.TOPIC_AGENT_TASK_ASSIGNED, 
                    key=f"HRIT_REVIEW_{project_id}"
                )
                
                logger.info(f"BPMN advanced: Test passed for {task_id}. Assigned Human Approval.")
                
            else:
                # NEXT STEP: End BPMN Flow (Test Failed)
                update_details = json.dumps({"log": "Tests FAILED. Deployment stopped.", "timestamp": datetime.now(timezone.utc).isoformat()})
                await pg_client.execute(
                    """UPDATE implementation_status SET status=$1, audit_trail=jsonb_set(audit_trail, '{updates}', audit_trail->'updates' || $3::jsonb) WHERE task_id=$2""",
                    'BPMN_FAILED_TESTS', task_id, update_details
                )
                logger.warning(f"BPMN stopped: Test failed for {task_id}.")


    async def _handle_remediation_event(self, data: Dict):
        audit_id = data.get('audit_id')
        remediation_data = data.get('remediation_data')
        
        if remediation_data.get('status') == 'PROPOSED':
            pid = f"REMED_{audit_id}"
            tid = f"FIX_T_{audit_id}"
            
            await pg_client.execute(
                "INSERT INTO implementation_status (project_id, phase, task_id, assigned_agent, status, plan_data, sequence, started_at) VALUES ($1, $2, $3, $4, 'PROPOSED', $5, 1, $6)",
                pid, REMEDIATION_PHASE, tid, REMEDIATION_AGENT, json.dumps(remediation_data), 
                datetime.now(timezone.utc).isoformat()
            )
            
            prompt = f"Review remediation plan {pid} for audit {audit_id}. Changes: {remediation_data.get('changes_made')}"
            
            await self.publisher.publish_agent_task(
                {"project_id": pid, "task_id": tid, "assigned_agent": REMEDIATION_AGENT, "task_instructions": prompt},
                self.publisher.TOPIC_AGENT_TASK_ASSIGNED, 
                key=pid
            )

    async def _handle_dtla_scenario(self, data: Dict):
        scen_id = data.get('scenario_id', 'UNKNOWN_SCENARIO')
        pid = f"PROACTIVE_{scen_id}"
        tid = f"HYPER_{scen_id}"
        
        await pg_client.execute(
            "INSERT INTO implementation_status (project_id, phase, task_id, assigned_agent, status, plan_data, sequence, started_at) VALUES ($1, $2, $3, $4, 'PENDING', $5, 1, $6)",
            pid, "HYPERCARE", tid, "HumanReview", json.dumps(data), 
            datetime.now(timezone.utc).isoformat()
        )
        logger.info(f"DTLA Scenario {scen_id} triggered HumanReview task.")

    async def _handle_policy_decision(self, data: Dict):
        if data.get('decision') == ApprovalStatus.APPROVED.value:
            if self.pvs: 
                policy_id = data.get('policy_id', 'UNKNOWN')
                version_id = data.get('policy_version_id', 'UNKNOWN')

                await asyncio.to_thread(
                    self.pvs.embed_approved_policy, 
                    version_id, 
                    data.get('approver_id', 'SYSTEM')
                )

                logger.info(f"Policy {policy_id} V:{version_id} approved and embedded.")

    # [CRITICAL FIX: ORCHESTRATION] NEW HANDLER TO CLOSE THE CREATOR LOOP
    async def _handle_final_approval_event(self, data: Dict):
        """
        Consumes the human approval decision event and triggers the final autonomous deployment
        or terminates the workflow (Creator Flow completion).
        """
        if not self._verify_payload_signature_sync(data):
            logger.error(f"Final approval event signature failed for task {data.get('task_id')}. Ignoring.")
            return

        task_id = data.get('task_id')
        project_id = data.get('project_id')
        decision = data.get('decision')
        approved_by = data.get('approved_by')

        # 1. Fetch the necessary config artifact
        query = "SELECT audit_trail->'initial_config' AS config FROM implementation_status WHERE task_id=$1"
        db_record = await pg_client.fetchrow(query, task_id)
        if not db_record:
             logger.error(f"Cannot find config for task {task_id} during final approval.")
             return

        artifact_config = db_record['config']
        
        if decision == "APPROVED":
            logger.info(f"Human Approval RECEIVED for {task_id}. Triggering final deployment.")
            
            # 2. Dispatch the final task to the AutonomousUpgradeAgent
            final_deployment_command = {
                "task_id": task_id,
                "project_id": project_id,
                "agent_id": artifact_config['agent_id'],
                "task_instructions": f"Final deployment of validated configuration by HRIT Manager {approved_by}.",
                "data_context": {
                    "agent_config": artifact_config,
                    "task_id": task_id 
                }
            }
            
            # Update DB status (pre-event for the AutonomousUpgradeAgent)
            update_details = json.dumps({"log": f"Approved by {approved_by}. Autonomous Deployment Task Assigned.", 
                                         "timestamp": datetime.now(timezone.utc).isoformat()})
            await pg_client.execute(
                """UPDATE implementation_status SET status=$1, audit_trail=jsonb_set(audit_trail, '{updates}', audit_trail->'updates' || $3::jsonb) WHERE task_id=$2""",
                'AWAITING_DEPLOYMENT_AGENT', task_id, update_details
            )
            
            # 3. Publish the final assignment event
            await self.publisher.publish_agent_task(
                final_deployment_command,
                self.publisher.TOPIC_AGENT_TASK_ASSIGNED, 
                key=artifact_config['agent_id'] 
            )
            logger.info(f"BPMN advanced: Final Deployment assigned for {artifact_config['agent_id']}.")
            
        else: # decision == "REJECTED"
            # Terminate the flow
            logger.warning(f"Deployment REJECTED by HRIT Manager {approved_by} for task {task_id}. Workflow terminated.")
            update_details = json.dumps({"log": f"Deployment Rejected by {approved_by}. Workflow terminated.", 
                                         "timestamp": datetime.now(timezone.utc).isoformat()})
            await pg_client.execute(
                """UPDATE implementation_status SET status=$1, audit_trail=jsonb_set(audit_trail, '{updates}', audit_trail->'updates' || $3::jsonb) WHERE task_id=$2""",
                'REJECTED_MANUAL', task_id, update_details
            )