# /backend/services/configuration_agent.py - REPLACEMENT (Final Integration)
import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone 
import asyncio
from services.schemas.models import ConfigurationUpdate
from services.event_publisher_service import EventPublisherService 

logger = logging.getLogger(__name__)

class ConfigurationAgent:
    """
    Core agent for processing and deploying critical configurations and BPCL policies.
    This acts as the bridge between the self-correction AI (BPCL generation) and the 
    Policy Versioning/Deployment system (BPEL/Orchestrator).
    """
    def __init__(self, ai_service=None, publisher: Optional[EventPublisherService]=None, policy_versioning_service=None, vv_compiler=None):
        self.name = "ConfigurationAgent"
        self.ai_service = ai_service
        self.publisher = publisher
        self.policy_versioning_service = policy_versioning_service
        self.vv_compiler = vv_compiler
        logger.info(f"{self.name} Initialized with dependencies.")

    async def apply_update(self, update: ConfigurationUpdate) -> bool:
        """Applies simple key-value config updates."""
        logger.info(f"Applying config update: {update.key} = {update.value} (by {update.applied_by})")
        if self.publisher:
            await self.publisher.publish_event(
                "Config_Update",
                {"key": update.key, "value": update.value, "user": update.applied_by, "timestamp": datetime.now(timezone.utc).isoformat()},
            )
        return True

    async def get_config(self, key: str) -> Optional[Any]:
        return None

    async def process_bpcl_deployment_request(self, 
                                            bpcl_content: Dict[str, Any], 
                                            policy_id: str, 
                                            requester_id: str) -> Dict[str, Any]:
        """
        [CRITICAL IP CORE METHOD]
        Validates the raw BPCL, submits it to Policy Versioning (DRAFT), 
        and triggers the deployment/approval workflow.
        """
        if not self.vv_compiler or not self.policy_versioning_service or not self.publisher:
            raise RuntimeError("CRITICAL: Required services (VV Compiler, PVS, or Publisher) are missing, blocking deployment flow.")

        logger.info(f"Starting BPCL processing for policy: {policy_id} by {requester_id}.")

        # 1. Verification & Validation (VV Compiler Check)
        vv_result = await self.vv_compiler.validate_bpcl(policy_id, bpcl_content)

        if not vv_result['is_valid']:
            logger.error(f"BPCL Validation FAILED for {policy_id}: {vv_result['type']} errors.")
            return {
                "status": "VALIDATION_BLOCKED",
                "policy_id": policy_id,
                "validation_report": vv_result
            }

        # 2. Submit to Policy Versioning Service (PVS) as DRAFT
        try:
            new_version = await asyncio.to_thread(
                self.policy_versioning_service.create_policy_version,
                policy_id,
                bpcl_content,
                requester_id,
                changelog="Auto-generated/corrected via Self-Correcting Agent prompt."
            )
            
            # 3. Publish Event for Orchestrator/BPEL Agent Handover (Triggers the BPMN flow)
            await self.publisher.publish_event(
                "BPCL_VALIDATED_DRAFTED",
                {"policy_id": policy_id, "version_id": new_version.version_id, "deployment_target": "BPELAgent"},
                key=policy_id
            )

            return {
                "status": "DEPLOYMENT_TRIGGERED",
                "policy_id": policy_id,
                "version_id": new_version.version_id,
                "vv_status": "PASSED",
                "message": "BPCL validated, versioned, and deployment request published to Orchestrator."
            }

        except Exception as e:
            logger.critical(f"PVS/Deployment Handover Failed for {policy_id}: {e}")
            return {"status": "CRITICAL_FAILURE", "error": str(e)}


def generate_configuration_from_prompt(prompt: str) -> Dict[str, Any]:
    """
    Legacy method for simple config updates, maintained for Orchestrator compatibility.
    """
    logger.info(f"Generating configuration from prompt: {prompt}")
    config_updates = {}
    if "threshold" in prompt.lower() and "0.8" in prompt:
        config_updates["DTLA_RISK_THRESHOLD"] = 0.8
    elif "timeout" in prompt.lower():
        config_updates["EXTERNAL_API_TIMEOUT_SECONDS"] = 60.0
    return {"detected_intent": "update_configuration", "suggested_changes": config_updates}

async def execute_gen_ui_command(command: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Generates dynamic UI definition from a prompt (used by Orchestrator).
    """
    logger.info(f"Executing GenUI command: {command}")
    ui_type = "card"
    cmd = command.lower()
    if "table" in cmd:
        ui_type = "table"
    elif "form" in cmd:
        ui_type = "form"
    return {
        "status": "success",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ui_definition": {
            "type": ui_type,
            "title": f"Dynamic {ui_type.capitalize()} Component",
            "source_command": command,
            "data_binding": context.get("data_source", "default_api") if context else "default_api",
        },
    }