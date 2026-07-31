# /backend/services/bpel_agent.py
"""BPEL Agent: runs the deployment of an approved policy version.

This used to build an XML string from a fixed template, log a line, throw the
whole definition away and return "BPEL_EXECUTION_STARTED". Nothing was executed,
nothing was persisted, and the message told the operator to monitor a history
endpoint that was structurally guaranteed to be empty, because no writer ever
populated the columns it read.

Now each step is actually performed and recorded as it happens, so the history
endpoint returns what the deployment really did, including where it stopped.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.ai_services import AIService
from services.policy_versioning import PolicyVersioningService
from services.postgres_client import pg_client
from services.schemas.models import BPELProcessDefinition

logger = logging.getLogger(__name__)


class BPELAgent:
    """Deploys an approved policy version, one recorded step at a time."""

    def __init__(self, ai_service: AIService, policy_versioning_service: PolicyVersioningService):
        self.ai_service = ai_service
        self.pvs = policy_versioning_service
        logger.info("✓ BPELAgent Initialized.")

    async def _record(self, process_id: str, step: str, status: str, detail: str = "") -> None:
        """Write one step of the deployment where the history endpoint reads it.

        task_id is the primary key, so a step is one row that moves from RUNNING
        to COMPLETED or FAILED. Inserting twice left every step showing RUNNING.
        """
        try:
            await pg_client.execute(
                """INSERT INTO implementation_status
                       (task_id, project_id, status, agent_id, requester_id,
                        step_name, process_id, audit_trail, updated_at)
                   VALUES ($1, $2, $3, 'bpel_agent', $4, $5, $6, $7, $8)
                   ON CONFLICT (task_id) DO UPDATE SET
                       status = EXCLUDED.status,
                       audit_trail = EXCLUDED.audit_trail,
                       updated_at = EXCLUDED.updated_at""",
                f"{process_id}:{step}", process_id, status, "bpel_agent",
                # audit_trail is a JSON column, so plain text was rejected and
                # every step was silently dropped.
                step, process_id, json.dumps({"detail": detail}), datetime.now(timezone.utc),
            )
        except Exception as e:
            # Losing the trail must not abort a deployment that is otherwise fine.
            logger.warning(f"Could not record step '{step}' of {process_id}: {e}")

    async def deploy_policy_workflow(self, policy_version_id: str,
                                     performed_by: str = "bpel_agent") -> Dict[str, Any]:
        """Deploy a policy version, recording every step.

        Stops at the first step that fails and says which one, rather than
        reporting a started workflow regardless of what happened.
        """
        policy_version = await asyncio.to_thread(self.pvs.get_version_by_id, policy_version_id)
        if not policy_version:
            raise ValueError(f"Policy version {policy_version_id} not found.")

        process_id = f"BPEL-{policy_version.version_id}"
        steps: List[Dict[str, str]] = []

        async def step(name: str, description: str, fn):
            await self._record(process_id, name, "RUNNING", description)
            try:
                result = await fn() if asyncio.iscoroutinefunction(fn) else await asyncio.to_thread(fn)
                await self._record(process_id, name, "COMPLETED", description)
                steps.append({"step": name, "status": "COMPLETED", "detail": description})
                return True, result
            except Exception as e:
                await self._record(process_id, name, "FAILED", str(e))
                steps.append({"step": name, "status": "FAILED", "detail": str(e)})
                logger.error(f"Deployment {process_id} stopped at '{name}': {e}")
                return False, e

        # 1. The version must have content to deploy.
        ok, _ = await step(
            "Read the approved policy",
            f"Loaded version {policy_version.version_number} of {policy_version.policy_id}.",
            lambda: (policy_version.content or {}) or (_ for _ in ()).throw(
                ValueError("This policy version has no content to deploy.")),
        )
        if not ok:
            return self._stopped(process_id, policy_version, steps, "Read the approved policy")

        # 2. Describe what is being deployed, so the record is readable later.
        definition = BPELProcessDefinition(
            process_id=process_id,
            name=f"Policy Deployment: {policy_version.policy_id} V{policy_version.version_number}",
            xml_definition=self._definition_xml(policy_version),
            variables={"policy_id": policy_version.policy_id, "version_id": policy_version_id},
            partner_links=["PolicyVersioningService"],
        )

        # 3. Actually make it the live version. This is the deployment.
        ok, result = await step(
            "Make this version live",
            f"{policy_version.policy_id} now enforces version {policy_version.version_number}.",
            lambda: self.pvs.activate_version(policy_version_id, performed_by),
        )
        if not ok:
            return self._stopped(process_id, policy_version, steps, "Make this version live")

        # 4. Confirm the switch took effect, rather than assuming it did.
        ok, _ = await step(
            "Confirm it is live",
            "Checked that the active version is the one just deployed.",
            lambda: self._confirm_active(policy_version.policy_id, policy_version_id),
        )
        if not ok:
            return self._stopped(process_id, policy_version, steps, "Confirm it is live")

        return {
            "status": "DEPLOYED",
            "process_id": process_id,
            "policy_id": policy_version.policy_id,
            "version_number": policy_version.version_number,
            "definition_name": definition.name,
            "steps": steps,
            "message": (f"Version {policy_version.version_number} of {policy_version.policy_id} "
                        "is now the version being enforced."),
        }

    def _confirm_active(self, policy_id: str, expected_version_id: str):
        active = self.pvs.get_active_version(policy_id)
        if not active or active.version_id != expected_version_id:
            raise ValueError(
                "The policy did not switch over: the live version is "
                f"{getattr(active, 'version_id', 'none')}.")
        return active

    @staticmethod
    def _definition_xml(policy_version) -> str:
        return (
            f'<process name="{policy_version.policy_id}_v{policy_version.version_number}">\n'
            '    <sequence>\n'
            '        <invoke partnerLink="PolicyVersioningService" operation="activate"/>\n'
            '        <invoke partnerLink="PolicyVersioningService" operation="confirmActive"/>\n'
            '    </sequence>\n'
            '</process>'
        )

    @staticmethod
    def _stopped(process_id: str, policy_version, steps: List[Dict[str, str]],
                 failed_at: str) -> Dict[str, Any]:
        detail = next((s["detail"] for s in steps if s["status"] == "FAILED"), "")
        return {
            "status": "FAILED",
            "process_id": process_id,
            "policy_id": policy_version.policy_id,
            "steps": steps,
            "failed_at": failed_at,
            "message": f"Deployment stopped at \"{failed_at}\". {detail}".strip(),
        }
