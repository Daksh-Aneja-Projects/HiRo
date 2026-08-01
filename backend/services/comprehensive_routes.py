# /backend/services/comprehensive_routes.py - REPLACEMENT (Final Stable Version)
"""Comprehensive Router: Aggregates all high-level API endpoints for management,
policy governance, XAI, PII encryption, and agent administration."""
import logging
from typing import Dict, Any, List, Optional, Union
from fastapi import APIRouter, Request, HTTPException, Depends, UploadFile, File, WebSocket, WebSocketDisconnect, Body, Form, Query 
from fastapi.responses import StreamingResponse, Response 
from pydantic import BaseModel
import asyncio
from services import notification_service
import json
import hashlib
import re
import uuid
from datetime import datetime, timezone, timedelta
import random
import psutil
from services import social_recognition
from config.settings import settings
from services.postgres_client import pg_client

# CRITICAL FIX 1: Initialize logger immediately after import
logger = logging.getLogger(__name__)

# CRITICAL FIX: Import dependency stubs/placeholders
# CRITICAL FIX: Importing actual JWT RBAC dependencies instead of using mocks
from services.auth_deps import (
    policy_admin_role_required,
    hrit_admin_role_required,
    manager_role_required,
    employee_role_required,
    get_auth_payload
)

# Real service imports. These are hard dependencies — if any fails to import,
# the app must fail loudly at boot, not silently swap in mock classes that
# return fabricated data. (The former `except ImportError` fallback masked
# every wrong-method bug in this file; it was verified dead and removed.)
from services.policy_versioning import PolicyVersioningService
from services.multi_agent_hrsd import MultiAgentHRSDSystem
from services.digital_twin_agent import DigitalTwinAgent
from services.xai_wrapper import XAIWrapper
from services.pqc_pii_layer import PQCEncryptionWrapper
from services.agent_creation_service import AgentCreationService
from services.bpel_agent import BPELAgent
from services.hr_modules import HRModulesService
from services.ess_service import ESSService
from services.mss_service import MSSService
from services.rlff_llm_fine_tuner import RLFFLLMFineTuner
from services.talent_acquisition_service import TalentAcquisitionService
from services.immersive_learning_agent import ImmersiveLearningAgent
from services.workforce_planning_service import WorkforcePlanningService as WFMService
from services.ai_services import AIService
from services.admin_service import AdminService
from services.self_correcting_agent import SelfCorrectingAgent
from services.synthetic_twin_engine import SyntheticTwinEngine
from services.cognitive_remediation_agent import CognitiveRemediationAgent
from routes.streaming_routes import manager as websocket_manager
from services.enforcement_engine import runtime_enforcer


# --- Data Models (from schemas/models.py) ---
class PolicyUpdateRequest(BaseModel):
    content: Dict[str, Any]
    changelog: str = ""

class ApprovalActionRequest(BaseModel):
    approved: bool
    comments: str = ""

class AgentCreationRequest(BaseModel):
    intent: str

class CompensationUpdateRequest(BaseModel):
    employee_id: str
    new_salary: float
    new_grade: str
    effective_date: str

class LeaveRequestSubmit(BaseModel):
    start_date: str
    end_date: str
    hours: int

class JobDescriptionRequest(BaseModel):
    role_title: str
    skills: List[str]

class WorkflowGenRequest(BaseModel):
    description: str

class PolicyScanRequest(BaseModel):
    policy_content: Dict[str, Any]
    version_id: str

# --- SI INTEGRATION: NEW DATA MODELS ---
class SimulationRequest(BaseModel):
    employee_id: str
    synthetic_adjustments: Dict[str, Any] 
    simulation_type: str = "what_if"
    include_recommendations: bool = True

class RemediationRequest(BaseModel):
    audit_id: str
    failed_transaction: Dict[str, Any] 
    policy_text: str 
    auto_apply: bool = False

class AgentStreamRequest(BaseModel):
    nl_prompt: str
    context: Optional[Dict[str, Any]] = None

# --- Router Definitions ---
policy_router = APIRouter(prefix="/policy", tags=["Policy Governance"])
hrsd_router = APIRouter(prefix="/hrsd", tags=["HRSD & Tickets"])
admin_router = APIRouter(prefix="/admin", tags=["System Admin & Agents"])
data_router = APIRouter(prefix="/data", tags=["Data & XAI"])
dev_router = APIRouter(prefix="/dev", tags=["DevOps & Encryption Tools"])
hr_router = APIRouter(prefix="/hr", tags=["HR Modules"])
ess_router = APIRouter(prefix="/ess", tags=["ESS"])
mss_router = APIRouter(prefix="/mss", tags=["MSS"])
wfp_router = APIRouter(prefix="/wfp", tags=["Workforce Planning"])
ta_router = APIRouter(prefix="/ta", tags=["Talent Acquisition"])
talent_content_router = APIRouter(prefix="/talent", tags=["Talent Content"])
ai_router = APIRouter(prefix="/ai", tags=["Legacy AI & Workflow"])
ingestion_router = APIRouter(prefix="/ingestion", tags=["Data Ingestion"])
pii_router = APIRouter(prefix="/pii", tags=["PII Utilities"])
analytics_router = APIRouter(prefix="/advanced-analytics", tags=["Analytics"])
talent_exp_router = APIRouter(prefix="/talent-exp", tags=["Talent Experience"])
# --- SI INTEGRATION: NEW ROUTERS ---
streaming_router = APIRouter(prefix="/streaming", tags=["Streaming & Real-time"])
simulation_router = APIRouter(prefix="/simulation", tags=["Simulation & What-If"])
remediation_router = APIRouter(prefix="/remediation", tags=["Cognitive Remediation"])
telemetry_router = APIRouter(prefix="/telemetry", tags=["Telemetry & Monitoring"])
# Additional Routers needed for full 404 coverage (from previous fix)
dao_router = APIRouter(prefix="/dao", tags=["DAO & Governance"])
compliance_router = APIRouter(prefix="/compliance", tags=["Compliance"])
social_router = APIRouter(prefix="/social", tags=["Social Feed"])
innovation_router = APIRouter(prefix="/innovation", tags=["Innovation"])
orchestrator_router = APIRouter(prefix="/orchestrator", tags=["Orchestrator"])
command_router = APIRouter(prefix="/command", tags=["Command Execution"])

# FIX START: Define the new recognition router to match the root path in api.js
recognition_router = APIRouter(prefix="/recognition", tags=["Recognition"])
notifications_router = APIRouter(prefix="/notifications", tags=["Notifications"])
# FIX END


# ======================================
# 1. POLICY GOVERNANCE ROUTER (Fixed/Complete)
# ======================================
# Declared before /{policy_id}/... so "list" is not captured as a policy id.
@policy_router.get("/list")
async def list_policies(req: Request, payload: Dict = Depends(policy_admin_role_required)):
    """Every policy the versioning service knows about, with its live version.
    Without this the UI had no way to discover existing policy ids."""
    pvs = getattr(req.app.state, 'policy_versioning_service', None)
    if not pvs:
        raise HTTPException(status_code=503, detail="Policy Versioning Service unavailable.")
    active = getattr(pvs, "active_versions", {}) or {}
    versions = getattr(pvs, "versions", {}) or {}
    by_policy: Dict[str, Dict[str, Any]] = {}
    for v in versions.values():
        pid = getattr(v, "policy_id", None)
        if not pid:
            continue
        entry = by_policy.setdefault(pid, {"policy_id": pid, "version_count": 0, "active_version_id": active.get(pid)})
        entry["version_count"] += 1
        entry["latest_version_number"] = getattr(v, "version_number", None)
    return {"policies": sorted(by_policy.values(), key=lambda p: p["policy_id"]), "count": len(by_policy)}

@policy_router.get("/{policy_id}/active")
async def get_active_policy(req: Request, policy_id: str):
    pvs: PolicyVersioningService = getattr(req.app.state, 'policy_versioning_service', None)
    if not pvs: raise HTTPException(status_code=503, detail="Policy Versioning Service unavailable.")
    return pvs.get_active_version(policy_id)

@policy_router.get("/{policy_id}/history")
async def get_policy_history(req: Request, policy_id: str):
    pvs: PolicyVersioningService = getattr(req.app.state, 'policy_versioning_service', None)
    if not pvs: raise HTTPException(status_code=503, detail="Policy Versioning Service unavailable.")
    return await asyncio.to_thread(pvs.get_version_history, policy_id)

def _pvs(req: Request) -> PolicyVersioningService:
    svc = getattr(req.app.state, 'policy_versioning_service', None)
    if not svc:
        raise HTTPException(status_code=503, detail="Policy Versioning Service unavailable.")
    return svc

async def _policy_call(fn, *args):
    """Run a policy-versioning call, turning its rule violations into 400s.

    The service raises ValueError for legitimate refusals ("you are not an
    approver on this request", "only APPROVED versions can be activated"). Those
    are client errors, not server faults, and the caller needs to see the reason.
    """
    try:
        return await asyncio.to_thread(fn, *args)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=f"Not found: {e}")

@policy_router.post("/{policy_id}/versions")
async def create_policy_draft(req: Request, policy_id: str, data: PolicyUpdateRequest, payload: Dict=Depends(policy_admin_role_required)):
    pvs = _pvs(req)
    active_version = getattr(pvs, 'active_versions', {}).get(policy_id)
    draft = await _policy_call(pvs.create_policy_version, policy_id, data.content, payload['sub'], data.changelog, active_version)
    return {"version_id": draft.version_id, "version_number": draft.version_number}

@policy_router.put("/versions/{version_id}/content")
async def update_policy_draft_content(req: Request, version_id: str, data: PolicyUpdateRequest, payload: Dict=Depends(policy_admin_role_required)):
    await _policy_call(_pvs(req).update_version_content, version_id, data.content, payload['sub'], data.changelog)
    return {"status": "Updated"}

@policy_router.post("/versions/{version_id}/submit")
async def submit_policy(req: Request, version_id: str,
                      approvers: List[str] = Body(..., embed=True), payload: Dict=Depends(policy_admin_role_required)):
    req_obj = await _policy_call(_pvs(req).submit_for_approval, version_id, payload['sub'], approvers)
    return {"request_id": req_obj.request_id}

@policy_router.post("/approvals/{request_id}")
async def process_policy_approval(req: Request, request_id: str, action: ApprovalActionRequest, payload: Dict=Depends(policy_admin_role_required)):
    await _policy_call(_pvs(req).approve_policy, request_id, payload['sub'], action.approved, action.comments)
    return {"status": "Processed"}

@policy_router.post("/versions/{version_id}/activate")
async def activate_policy(req: Request, version_id: str, payload: Dict=Depends(policy_admin_role_required)):
    await _policy_call(_pvs(req).activate_version, version_id, payload['sub'])
    return {"status": "Activated"}

@policy_router.post("/{policy_id}/rollback")
async def rollback_policy(req: Request, policy_id: str, target_version_id: str = Body(..., embed=True), payload: Dict=Depends(policy_admin_role_required)):
    await _policy_call(_pvs(req).rollback_to_version, policy_id, target_version_id, payload['sub'])
    return {"status": "Rollback Success"}

@policy_router.post("/ledger/commit")
async def commit_to_ledger(req: Request, data: Dict[str, Any], auth_payload: Dict = Depends(policy_admin_role_required)):
    """Append a content-addressed record to the policy ledger (Mongo). Each block's
    hash chains the previous block's hash, so tampering is detectable."""
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        raise HTTPException(status_code=503, detail="Ledger store unavailable.")
    ledger = mongo_client[settings.MONGO_DB_NAME]["policy_ledger"]

    prev = await ledger.find_one(sort=[("index", -1)])
    prev_hash = prev["block_hash"] if prev else "0" * 64
    index = (prev["index"] + 1) if prev else 0
    timestamp = data.get("timestamp") or datetime.now(timezone.utc).isoformat()

    payload_str = json.dumps(data, sort_keys=True, default=str)
    block_hash = hashlib.sha256(f"{index}{prev_hash}{payload_str}{timestamp}".encode()).hexdigest()

    await ledger.insert_one({
        "index": index,
        "prev_hash": prev_hash,
        "block_hash": block_hash,
        "payload": data,
        "committed_by": auth_payload.get("sub"),
        "timestamp": timestamp,
    })
    return {"status": "COMMITTED", "block_hash": block_hash, "index": index, "timestamp": timestamp}

@policy_router.post("/scan-policy-for-deployment")
async def scan_policy_for_deployment(req: Request, data: PolicyScanRequest, payload: Dict=Depends(policy_admin_role_required)):
    # runtime_enforcer is the module-level async function execute_dsl_check(trigger, context_data).
    scan_result = await runtime_enforcer("pre_deployment_scan", {
        "PolicyVersion": data.version_id,
        "PolicyContent": data.policy_content,
    })

    decision = (scan_result.get("decision") or "").upper()
    if decision in ("DENY", "STOP", "BLOCK"):
        raise HTTPException(status_code=400, detail=f"Scan failed: {scan_result.get('reason', 'policy denied')}")

    return {
        "status": "SECURE",
        "decision": decision or "PASS",
        "vulnerabilities": [],
        "audit_id": scan_result.get("audit_id"),
        "trace": scan_result.get("xai_trace", "Policy passed syntax and enforcement checks."),
    }

@policy_router.post("/deploy-bpcl-from-prompt/{policy_id}")
async def deploy_bpcl_from_prompt(req: Request, policy_id: str, nl_prompt: str = Body(..., embed=True), payload: Dict=Depends(policy_admin_role_required)):
    """Turn a written instruction into a draft policy rule, and show it back.

    This used to spend seven seconds of real inference, write the result into a
    Mongo collection nothing ever reads, discard it from the response, and tell
    the operator "Deployment Initiated". Nothing was deployed and the generated
    rule was never seen by anyone. If the model failed it said the same thing.

    A written instruction becomes a draft that a person reads and approves; it
    does not become live policy on its own. The response now says which of those
    happened, and carries the draft.
    """
    ai_service: AIService = getattr(req.app.state, "ai_service", None)
    if not ai_service:
        raise HTTPException(status_code=503, detail="AI Service unavailable.")

    schema = {
        "type": "object",
        "properties": {
            "rule_name": {"type": "string"},
            "condition": {"type": "string"},
            "action": {"type": "string"},
            "plain_english": {"type": "string"},
        },
        "required": ["rule_name", "condition", "action", "plain_english"],
    }
    try:
        draft = await ai_service.generate_json_response(
            f"Turn this HR policy instruction into one rule.\n\nInstruction: {nl_prompt}\n\n"
            "condition: when the rule applies. action: what happens then, one of BLOCK, FLAG or LOG. "
            "plain_english: one sentence an employee would understand.",
            schema, task_type="policy_drafting")
    except Exception as e:
        logger.warning(f"policy drafting failed for {policy_id}: {e}")
        raise HTTPException(
            status_code=502,
            detail="The model could not turn that instruction into a rule. Try rewording it.")

    if not draft or not draft.get("condition"):
        raise HTTPException(
            status_code=502,
            detail="The model did not produce a usable rule from that instruction.")

    task_id = f"DRAFT-{random.getrandbits(48):012x}"
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if mongo_client:
        await mongo_client[settings.MONGO_DB_NAME]["policy_deployments"].insert_one({
            "task_id": task_id, "policy_id": policy_id, "prompt": nl_prompt,
            "draft": draft, "status": "AWAITING_REVIEW",
            "requested_by": payload.get("sub"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    return {
        "status": "AWAITING_REVIEW",
        "policy_id": policy_id,
        "task_id": task_id,
        "draft": draft,
        "message": ("This is a draft, not live policy. Review it and submit it through "
                    "the policy approval process to put it into effect."),
    }


@policy_router.get("/drafts/{policy_id}")
async def list_policy_drafts(req: Request, policy_id: str, limit: int = Query(20),
                             payload: Dict = Depends(policy_admin_role_required)):
    """Drafts written from an instruction and still waiting for review.

    Drafts were written to a collection that nothing read, so once the response
    was discarded there was no way to find them again.
    """
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        return {"policy_id": policy_id, "drafts": []}
    cursor = mongo_client[settings.MONGO_DB_NAME]["policy_deployments"].find(
        {"policy_id": policy_id}, {"_id": 0}
    ).sort("created_at", -1).limit(max(1, min(int(limit or 20), 100)))
    return {"policy_id": policy_id, "drafts": await cursor.to_list(length=100)}


# ======================================
# 2. HRSD & TICKETS ROUTER (Fixed/Complete)
# ======================================
@hrsd_router.get("/tickets")
async def list_tickets(req: Request, employee_id: Optional[str] = Query(None), limit: Optional[int] = Query(None), offset: Optional[int] = Query(None), payload: Dict=Depends(manager_role_required)):
    """FIX: Added GET endpoint to list tickets (needed by frontend dashboard)."""
    hrsd_system: MultiAgentHRSDSystem = getattr(req.app.state, "hrsd_system", None)
    if not hrsd_system:
        raise HTTPException(status_code=503, detail="HRSD system unavailable.")
    # limit and offset were accepted and then never forwarded, so the case list
    # and both its charts covered the newest 50 of 808 while the monitoring
    # panel on the same screen reported 605 open.
    return await hrsd_system.list_tickets(employee_id, limit=limit, offset=offset)

@hrsd_router.post("/tickets")
async def create_ticket(req: Request, subject: str = Body(...), description: str = Body(...), employee_id: str = Body(...), payload: Dict=Depends(employee_role_required)):
    hrsd_system: MultiAgentHRSDSystem = getattr(req.app.state, "hrsd_system", None)
    if not hrsd_system: raise HTTPException(status_code=503, detail="HRSD System unavailable.")
    
    ticket = await hrsd_system.create_ticket(employee_id, subject, description)

    # Actually triage it. This route reported "Triage Initiated" while calling
    # nothing: triage_ticket had no caller anywhere in the codebase, so every
    # case sat at NEW with no owner until a person happened to notice it.
    try:
        ticket = await hrsd_system.triage_ticket(ticket.ticket_id)
        routed = ticket.assigned_agent
    except Exception as e:
        logger.warning(f"Could not triage {ticket.ticket_id}: {e}")
        routed = None

    return {
        "ticket_id": ticket.ticket_id,
        "status": ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status),
        "priority": ticket.priority.value if hasattr(ticket.priority, "value") else str(ticket.priority),
        "assigned_to": routed,
        "message": (f"Your case was raised and passed to the {_readable_agent(routed)}."
                    if routed and routed != "TriageAgent"
                    else "Your case was raised and is waiting for someone to pick it up."),
    }


def _readable_agent(agent: Optional[str]) -> str:
    """Nobody outside the system should be shown a class name like PayrollAgent."""
    return {
        "PayrollAgent": "payroll team",
        "BenefitsAgent": "benefits team",
        "TimeOffAgent": "time off team",
        "ITSupportAgent": "IT support team",
        "ProjectFollowupAgent": "project team",
        "TriageAgent": "HR service desk",
    }.get(str(agent or ""), "HR service desk")

@hrsd_router.put("/tickets/{ticket_id}/resolve")
async def resolve_ticket(req: Request, ticket_id: str, resolution_summary: str = Body(..., embed=True), payload: Dict=Depends(manager_role_required)):
    hrsd_system: MultiAgentHRSDSystem = getattr(req.app.state, "hrsd_system", None)
    if not hrsd_system: raise HTTPException(status_code=503, detail="HRSD System unavailable.")
    await hrsd_system.resolve_ticket_by_agent(ticket_id,
                                            resolution_summary, payload['sub'])
    return {"status": "Resolved"}

@hrsd_router.put("/tickets/{ticket_id}/assign")
async def assign_ticket(req: Request, ticket_id: str, assignee: str = Body(..., embed=True), payload: Dict=Depends(manager_role_required)):
    """Assign a case to an owner. The UI rendered assigned_to but nothing could set it."""
    try:
        result = await pg_client.execute(
            "UPDATE hrsd_tickets SET assigned_agent = $1 WHERE ticket_id = $2",
            assignee, ticket_id,
        )
    except Exception as e:
        logger.error(f"assign ticket failed: {e}")
        raise HTTPException(status_code=500, detail="Could not assign the case.")
    if isinstance(result, str) and result.endswith("0"):
        raise HTTPException(status_code=404, detail="Ticket not found.")
    return {"status": "Assigned", "ticket_id": ticket_id, "assigned_agent": assignee}

@hrsd_router.get("/monitoring/overview")
async def get_hrsd_overview(req: Request, payload: Dict=Depends(manager_role_required)):
    hrsd_system: MultiAgentHRSDSystem = getattr(req.app.state, "hrsd_system", None)
    if not hrsd_system:
        raise HTTPException(status_code=503, detail="HRSD System unavailable.")
    return await hrsd_system.get_overview()

@hrsd_router.post("/integrations/snow/sync")
async def sync_servicenow(req: Request, payload: Dict=Depends(policy_admin_role_required)):
    """Record a ServiceNow sync attempt. There is no live ServiceNow tenant wired up,
    so this persists a local sync-log record (clearly marked as local) rather than
    fabricating an external ServiceNow id."""
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        raise HTTPException(status_code=503, detail="Sync log store unavailable.")
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "local_record_id": f"LOCAL-SNOWSYNC-{random.getrandbits(48):012x}",
        "source": "local",
        "external_system": "servicenow",
        "external_configured": False,
        "status": "RECORDED_LOCAL",
        "triggered_by": payload.get("sub"),
        "synced_at": now,
    }
    await mongo_client[settings.MONGO_DB_NAME]["servicenow_sync_log"].insert_one(dict(record))
    return {"status": "Sync Recorded (local)", "details": record}

# ======================================
# 3. SYSTEM ADMIN & AGENTS ROUTER (Fixed/Complete)
# ======================================
@admin_router.get("/health")
async def get_system_health(req: Request, payload: Dict=Depends(hrit_admin_role_required)):
    """Probe each dependency for real. This previously returned a hardcoded
    all-green literal, so the console reported NATS as UP on a server where the
    message bus was demonstrably disconnected."""
    checks: Dict[str, str] = {}

    try:
        await pg_client.fetchrow("SELECT 1")
        checks["postgres"] = "UP"
    except Exception as e:
        logger.warning(f"health: postgres down: {e}")
        checks["postgres"] = "DOWN"

    mongo_client = getattr(req.app.state, "mongo_client", None)
    try:
        if mongo_client:
            await mongo_client.admin.command("ping")
            checks["mongodb"] = "UP"
        else:
            checks["mongodb"] = "DOWN"
    except Exception:
        checks["mongodb"] = "DOWN"

    publisher = getattr(req.app.state, "event_publisher", None)
    checks["nats"] = "UP" if getattr(getattr(publisher, "nc", None), "is_connected", False) else "DOWN"

    redis_client = getattr(req.app.state, "redis_client", None)
    if redis_client:
        try:
            await redis_client.ping()
            checks["redis"] = "UP"
        except Exception:
            checks["redis"] = "DOWN"

    ai_service = getattr(req.app.state, "ai_service", None)
    try:
        models = await ai_service.get_ai_models() if ai_service else []
        checks["ai_primary"] = "UP" if models else "DOWN"
    except Exception:
        checks["ai_primary"] = "DOWN"

    # A green tick beside a row reading "message bus: down" is worse than no
    # tick at all. Anything that is down is reflected in the headline, with the
    # difference between "nothing works" and "something is missing" kept.
    essential = ("postgres", "mongodb", "ai_primary")
    down = [name for name, state in checks.items() if state == "DOWN"]
    essential_down = [name for name in essential if checks.get(name) == "DOWN"]

    READABLE = {
        "postgres": "the employee database",
        "mongodb": "the document store",
        "redis": "the cache",
        "nats": "the agent message bus",
        "ai_primary": "the language model",
    }
    if essential_down:
        status = "DOWN"
        summary = ("HiRo cannot run right now: "
                   + ", ".join(READABLE.get(n, n) for n in essential_down) + " is unavailable.")
    elif down:
        status = "DEGRADED"
        summary = ("HiRo is running, but "
                   + ", ".join(READABLE.get(n, n) for n in down)
                   + (" is" if len(down) == 1 else " are") + " unavailable.")
    else:
        status = "HEALTHY"
        summary = "Everything HiRo depends on is responding."

    return {
        "status": status,
        "summary": summary,
        "checks": checks,
        "degraded": down,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

@admin_router.post("/agent/create")
async def create_agent(req: Request, data: AgentCreationRequest, payload: Dict=Depends(hrit_admin_role_required)):
    agent_creation_service: AgentCreationService = getattr(req.app.state, "agent_creation_service", None)
    if not agent_creation_service: raise HTTPException(status_code=503, detail="Agent Creation Service unavailable.")
    return await agent_creation_service.create_and_deploy_agent(data.intent, payload['sub'])

@admin_router.post("/agent/deploy/final-approval")
async def process_agent_final_approval(req: Request, task_id: str = Body(...), project_id: str = Body(...), approved: bool = Body(...), comments: Optional[str] = Body(None), payload: Dict=Depends(hrit_admin_role_required)):
    """FIX: Added endpoint for HRIT Manager's final approval on agent deployment/config update."""
    decision = "APPROVED" if approved else "REJECTED"
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "task_id": task_id, "project_id": project_id, "decision": decision,
        "approved_by": payload.get("sub"), "comments": comments, "decided_at": now,
    }

    mongo_client = getattr(req.app.state, "mongo_client", None)
    if mongo_client:
        await mongo_client[settings.MONGO_DB_NAME]["agent_deployments"].update_one(
            {"task_id": task_id}, {"$set": record}, upsert=True,
        )

    published = False
    if approved:
        publisher = getattr(req.app.state, "event_publisher", None)
        if publisher:
            await publisher.publish_event(
                publisher.TOPIC_HUMAN_APPROVAL,
                {"type": "AGENT_DEPLOYMENT_APPROVED", "task_id": task_id,
                 "project_id": project_id, "approved_by": payload.get("sub")},
                key=task_id,
            )
            published = True

    return {
        "status": "DEPLOYMENT_TRIGGERED" if approved else "REJECTED",
        "task_id": task_id, "decision": decision, "event_published": published,
    }


@admin_router.post("/rlff/command")
async def rlff_command(req: Request, command: str = Body(..., embed=True), payload: Dict=Depends(hrit_admin_role_required)):
    rlff_llm_fine_tuner: RLFFLLMFineTuner = getattr(req.app.state, "rlff_llm_fine_tuner", None)
    if not rlff_llm_fine_tuner:
        raise HTTPException(status_code=503, detail="RLFF fine-tuner unavailable.")
    return await rlff_llm_fine_tuner.execute_rlff_command({"command": command, "command_type": "analyze"})

@admin_router.get("/dashboard")
async def get_admin_dashboard(req: Request, payload: Dict=Depends(hrit_admin_role_required)):
    """Real system + governance health for the admin console."""
    from services.enforcement_engine import get_compliance_overview

    # If the compliance aggregate fails we must NOT report a perfect score:
    # this previously fell back to 1.0 and rendered "100.0 integrity" on failure.
    compliance = None
    try:
        compliance = await get_compliance_overview()
    except Exception as e:
        logger.warning(f"Admin dashboard: compliance aggregate failed: {e}")

    # Field name kept (frontend contract). It counts AES-256 data-encryption keys
    # in use; nothing in HiRo is post-quantum, and the label beside it should say
    # "encryption keys", not "PQC keys".
    pqc = getattr(req.app.state, "pqc_wrapper", None)
    active_pqc_keys = 1 if pqc and getattr(pqc, "master_key_bytes", None) else 0

    try:
        # Host memory utilisation. This was previously labelled "cache
        # utilisation", which it never was.
        memory_util_pct = round(psutil.virtual_memory().percent, 1)
    except Exception:
        memory_util_pct = None

    return {
        # Null when the aggregate failed OR when no policy decision has ever been
        # recorded. Both are "we do not know", and neither is 100.
        "integrity_score": (round(compliance["score"] * 100, 1)
                            if compliance and compliance.get("score") is not None else None),
        "integrity_available": bool(compliance and compliance.get("score") is not None),
        "integrity_note": (compliance.get("score_note") if compliance
                           else "The compliance aggregate could not be read."),
        "active_pqc_keys": active_pqc_keys,
        # Says plainly what that key actually is, so no dashboard has to guess.
        "encryption_algorithm": "AES-256 (Fernet)",
        "post_quantum": False,
        # This is host memory, and it used to be served under the alias
        # cache_util_pct as well, which the admin console rendered as "Cache in
        # use ... percent full". The alias is gone so it cannot be mislabelled
        # again by anything reading this response.
        "memory_util_pct": memory_util_pct,
        "critical_alerts": compliance["high_severity_violations"] if compliance else None,
    }

def _require_admin_service(req: Request) -> AdminService:
    svc = getattr(req.app.state, "admin_service", None)
    if not svc:
        raise HTTPException(status_code=503, detail="Admin service unavailable.")
    return svc

@admin_router.get("/users")
async def get_admin_users(req: Request, limit: int = Query(200), offset: int = Query(0), auth=Depends(hrit_admin_role_required)):
    users = await _require_admin_service(req).get_all_users(limit=limit, offset=offset)
    return {"users": users, "count": len(users)}

@admin_router.post("/users/create")
async def admin_create_user(req: Request, data: Dict[str, Any], auth=Depends(hrit_admin_role_required)):
    try:
        return await _require_admin_service(req).create_user(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@admin_router.put("/users/{username}/role")
async def admin_update_role(req: Request, username: str, data: Dict[str, Any], auth=Depends(hrit_admin_role_required)):
    try:
        return await _require_admin_service(req).update_role(username, data.get("role"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@admin_router.delete("/users/{username}")
async def admin_delete_user(req: Request, username: str, auth=Depends(hrit_admin_role_required)):
    try:
        return await _require_admin_service(req).delete_user(username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@admin_router.post("/system/integrity-check")
async def integrity_check(req: Request, service: str = Body(..., embed=True), payload: Dict=Depends(hrit_admin_role_required)):
    """Live integrity probe: confirms the named subsystem is reachable right now."""
    service = (service or "").lower()
    ok, detail = True, "Reachable"
    try:
        if service in ("postgres", "db", "database"):
            pg = getattr(req.app.state, "pg_client", None)
            ok = pg is not None
            detail = "Postgres pool active" if ok else "Postgres client not initialized"
        elif service in ("redis", "cache"):
            r = getattr(req.app.state, "redis_client", None)
            if r:
                await r.ping()
                detail = "Redis PONG"
            else:
                ok, detail = False, "Redis not connected"
        elif service in ("mongo", "mongodb"):
            m = getattr(req.app.state, "mongo_client", None)
            if m:
                await m.admin.command("ping")
                detail = "MongoDB ping ok"
            else:
                ok, detail = False, "Mongo client not initialized"
        else:
            detail = "No specific probe; process is live"
    except Exception as e:
        ok, detail = False, f"{type(e).__name__}: {e}"
    return {"service": service, "status": "INTEGRITY_VERIFIED" if ok else "INTEGRITY_FAILED", "detail": detail}

@admin_router.get("/announcement")
async def get_announcements(req: Request, limit: int = Query(50), offset: int = Query(0), payload: Dict=Depends(employee_role_required)):
    """Anyone signed in can read announcements; only admins publish them.

    This was admin-only, so a broadcast the console described as visible to
    everyone in fact reached other admins alone.
    """
    items = await _require_admin_service(req).get_announcements(limit=limit, offset=offset)
    return {"announcements": items, "count": len(items)}

@admin_router.post("/announcement")
async def create_announcement(req: Request, data: Dict[str, Any], payload: Dict=Depends(hrit_admin_role_required)):
    try:
        return await _require_admin_service(req).create_announcement(data, author=payload.get("sub", "system"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@admin_router.post("/system/cache/clear")
async def clear_cache(req: Request, payload: Dict=Depends(hrit_admin_role_required)):
    if hasattr(req.app.state, 'redis_client') and req.app.state.redis_client:
        await req.app.state.redis_client.flushdb()
    return {"status": "Cache Cleared"}

@admin_router.get("/system/message-bus/status")
async def bus_status(req: Request, payload: Dict=Depends(hrit_admin_role_required)):
    """Message-bus liveness, plus the outcome of the last publish attempt.

    pending_messages used to be hardcoded to 0, which read as "nothing is stuck"
    on a box where NATS was not even running. Nothing here measures a queue
    depth, so the field is null with a note saying so.
    """
    publisher = getattr(req.app.state, "event_publisher", None)
    connected = bool(getattr(getattr(publisher, "nc", None), "is_connected", False)) if publisher else False
    last = getattr(publisher, "last_publish", None) if publisher else None
    return {
        "status": "Connected" if connected else "Disconnected",
        # No queue-depth reading is available from this client, so no number is
        # invented. Null means "not measured", which is not the same as zero.
        "pending_messages": None,
        "pending_messages_note": ("Queue depth is not reported by the publisher client, "
                                  "so it is not measured here."),
        "last_publish": last,
    }

@admin_router.post("/security/rotate-keys")
async def rotate_keys(req: Request, payload: Dict=Depends(hrit_admin_role_required)):
    """Key rotation is refused, not faked.

    This used to call a routine that swapped the in-memory encryption key for an
    unpersisted random one without re-encrypting a single stored row, and then
    reported "Keys Rotated". Every encrypted employee record became unreadable.
    """
    pqc_wrapper: PQCEncryptionWrapper = getattr(req.app.state, "pqc_wrapper", None)
    if not pqc_wrapper:
        raise HTTPException(status_code=503, detail="Encryption service unavailable.")
    result = await pqc_wrapper.rotate_keys()
    if not result.get("rotated"):
        raise HTTPException(status_code=409, detail=result["message"])
    return result

@admin_router.post("/system/reset-all-data")
async def reset_all_data(req: Request, payload: Dict=Depends(hrit_admin_role_required)):
    admin_service: AdminService = getattr(req.app.state, "admin_service", None)
    if not admin_service: raise HTTPException(status_code=503, detail="Admin Service unavailable.")
    
    result = await admin_service.hard_purge_system_data(payload['sub'])
    return result 

@admin_router.get("/hrit/system/reset-data")
async def get_hrit_portal_data(req: Request, payload: Dict=Depends(hrit_admin_role_required)):
    return await get_admin_dashboard(req, payload)

async def _admin_audit(req: Request, action: str, detail: Dict[str, Any], payload: Dict) -> Dict[str, Any]:
    """Persist a fire-and-forget admin operation request to the Mongo audit log
    and return a real acknowledgement with the stored record id."""
    op_id = f"ADMINOP-{random.getrandbits(48):012x}"
    now = datetime.now(timezone.utc).isoformat()
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        raise HTTPException(status_code=503, detail="Admin audit store unavailable.")
    await mongo_client[settings.MONGO_DB_NAME]["admin_operations_log"].insert_one({
        "op_id": op_id, "action": action, "detail": detail,
        "requested_by": payload.get("sub"), "status": "ACCEPTED", "requested_at": now,
    })
    return {"op_id": op_id, "action": action, "status": "ACCEPTED", "requested_at": now}

@admin_router.post("/hrit/system/reset-data")
async def reset_hrit_data(req: Request, payload: Dict=Depends(hrit_admin_role_required)):
    """Record an HRIT data-reset request (fire-and-forget). Actual destructive purge
    is handled by /admin/system/reset-all-data; this records the operator intent."""
    return await _admin_audit(req, "hrit_reset_data", {}, payload)

@admin_router.post("/data/migrate-legacy-chunk")
async def trigger_legacy_data_migration(req: Request, instructions: Dict[str, Any], payload: Dict=Depends(hrit_admin_role_required)):
    return await _admin_audit(req, "migrate_legacy_chunk", {"instructions": instructions}, payload)

# ======================================
# 4. DATA & XAI ROUTER (Fixed/Complete)
# ======================================
@data_router.post("/xai/explain")
async def explain_prediction(req: Request, model_name: str = Body(...), prediction_input: Dict = Body(...), payload: Dict=Depends(manager_role_required)):
    wfm_service = getattr(req.app.state, "wfm_service", None)
    xai: XAIWrapper = getattr(req.app.state, "xai_wrapper", None) 
    if not wfm_service or not xai: raise HTTPException(status_code=503, detail="WFM or XAI Service unavailable.")
    
    prediction = await wfm_service.predict_attrition_risk(prediction_input)
    feature_vector = prediction.get('feature_vector_used', prediction_input)
    # Report the adjustments the model actually made. Recomputing them with the
    # explainer's own weights produced a breakdown that disagreed with the score
    # it was explaining. Older predictions without a driver list fall back.
    explanation = (xai.explain_drivers(prediction) if prediction.get("drivers")
                   else xai.explain_prediction(feature_vector, prediction.get('risk_score')))
    return {
        **explanation,
        "risk_level": prediction.get("risk_level"),
        "recommendation": prediction.get("recommendation"),
        "employee_uuid": prediction.get("employee_uuid"),
    }

@data_router.get("/xai/audit/{model_name}")
async def get_model_audit_log(req: Request, model_name: str, limit: int = Query(10), payload: Dict=Depends(hrit_admin_role_required)):
    """Decisions the policy engine made, optionally narrowed to one trigger.

    This used to select every row in policy_audit_log unfiltered and stamp the
    name from the URL onto each one, so /xai/audit/anything_at_all returned the
    same rows labelled with whatever was asked for. They are policy decisions,
    not model inferences, and they are now labelled as such.
    """
    lim = max(1, min(int(limit or 10), 500))
    # The path segment names a decision trigger (for example time_clock_in).
    # "all" or an unknown name returns everything rather than pretending to filter.
    trigger = None if model_name.lower() in ("all", "any", "*") else model_name.lower()
    try:
        if trigger:
            rows = await pg_client.fetch(
                """SELECT audit_id, decision_timestamp, policy_version, trigger_type, decision, reason
                   FROM policy_audit_log WHERE lower(trigger_type) = $1
                   ORDER BY decision_timestamp DESC LIMIT $2""",
                trigger, lim,
            )
            if not rows:
                # Nothing matched, so this was not a trigger name. Say so rather
                # than returning unrelated rows under that heading.
                known = await pg_client.fetch(
                    "SELECT DISTINCT trigger_type FROM policy_audit_log ORDER BY trigger_type")
                return {
                    "decisions": [],
                    "decision_type": model_name,
                    "message": (f"No decisions have been recorded for '{model_name}'. "
                                f"Recorded decision types: "
                                f"{', '.join(humanise(r['trigger_type']) for r in known) or 'none yet'}."),
                }
        else:
            rows = await pg_client.fetch(
                """SELECT audit_id, decision_timestamp, policy_version, trigger_type, decision, reason
                   FROM policy_audit_log ORDER BY decision_timestamp DESC LIMIT $1""",
                lim,
            )
    except Exception as e:
        logger.warning(f"policy decision audit query failed: {e}")
        return {"decisions": [], "decision_type": model_name, "message": "The decision log could not be read."}

    return {
        "decisions": [
            {"audit_id": r["audit_id"], "timestamp": str(r["decision_timestamp"]),
             "policy_version": r["policy_version"], "action": r["trigger_type"],
             "action_label": humanise(r["trigger_type"]),
             "decision": r["decision"], "reason": r.get("reason"),
             "decided_by": "policy engine"}
            for r in rows
        ],
        "decision_type": model_name,
    }


def _audit_detail(value) -> str:
    """The readable line out of an audit_trail JSON value."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return value
    return (value or {}).get("detail", "") if isinstance(value, dict) else str(value or "")


def humanise(value: Optional[str]) -> str:
    """time_clock_in -> Time clock in. Raw identifiers should not reach a reader."""
    text = str(value or "").replace("_", " ").strip()
    return text[:1].upper() + text[1:] if text else "Unknown"

@data_router.post("/correction/{data_id}")
async def submit_data_correction(req: Request, data_id: str, corrections: Dict[str, Any] = Body(..., embed=True), payload: Dict=Depends(hrit_admin_role_required)):
    """Persist a data-correction request to Mongo for review/replay."""
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        raise HTTPException(status_code=503, detail="Correction store unavailable.")
    correction_id = f"CORR-{random.getrandbits(48):012x}"
    await mongo_client[settings.MONGO_DB_NAME]["data_corrections"].insert_one({
        "correction_id": correction_id, "data_id": data_id, "corrections": corrections,
        "submitted_by": payload.get("sub"), "status": "PENDING_REVIEW",
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"status": "Correction Submitted", "correction_id": correction_id,
            "data_id": data_id, "fields": list(corrections.keys())}


@data_router.post("/dtla/command")
async def dtla_command(req: Request, command_type: str = Body(...), data: Dict = Body(...), payload: Dict=Depends(manager_role_required)):
    dtla: DigitalTwinAgent = getattr(req.app.state, "digital_twin_agent", None) 
    if not dtla: raise HTTPException(status_code=503, detail="Digital Twin Agent unavailable.")
    
    data["command_type"] = command_type
    data["requester_id"] = payload['sub']
    return await dtla.execute_dtla_command(data)

# ======================================
# 5. DEV & ENCRYPTION ROUTER (AES-256-Fernet; classical, not post-quantum)
# ======================================
@dev_router.post("/pqc/encrypt")
async def test_pqc_encrypt(req: Request, plaintext: str = Body(..., embed=True), payload: Dict=Depends(hrit_admin_role_required)):
    pqc_wrapper: PQCEncryptionWrapper = getattr(req.app.state, "pqc_wrapper", None)
    if not pqc_wrapper: raise HTTPException(status_code=503, detail="Encryption service unavailable.")
    # encrypt() returns (ciphertext_str, metadata_dict)
    ciphertext, metadata = pqc_wrapper.encrypt(plaintext)
    return {"ciphertext": ciphertext, "metadata": metadata}

@dev_router.post("/pqc/decrypt")
async def test_pqc_decrypt(req: Request, ciphertext: str = Body(..., embed=True), payload: Dict=Depends(hrit_admin_role_required)):
    pqc_wrapper: PQCEncryptionWrapper = getattr(req.app.state, "pqc_wrapper", None)
    if not pqc_wrapper: raise HTTPException(status_code=503, detail="Encryption service unavailable.")
    try:
        return {"plaintext": pqc_wrapper.decrypt(ciphertext)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@dev_router.post("/policy/generate_tree")
async def generate_policy_execution_tree(req: Request, policy_version_id: str = Body(..., embed=True), payload: Dict=Depends(hrit_admin_role_required)):
    """Build a real execution tree from the stored policy version's content."""
    pvs: PolicyVersioningService = getattr(req.app.state, "policy_versioning_service", None)
    if not pvs:
        raise HTTPException(status_code=503, detail="Policy Versioning Service unavailable.")
    version = await asyncio.to_thread(pvs.get_version_by_id, policy_version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Policy version not found.")

    def _node(key: str, value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return {"id": key, "type": "branch", "children": [_node(k, v) for k, v in value.items()]}
        if isinstance(value, list):
            return {"id": key, "type": "list", "children": [_node(f"{key}[{i}]", v) for i, v in enumerate(value)]}
        return {"id": key, "type": "leaf", "value": value, "children": []}

    content = version.content or {}
    tree = {
        "id": "root",
        "version": policy_version_id,
        "version_number": version.version_number,
        "status": getattr(version.status, "value", str(version.status)),
        "children": [_node(k, v) for k, v in content.items()],
    }
    return {"tree": tree}

async def _dev_persist(req: Request, collection: str, action: str, data: Dict, payload: Dict) -> Dict[str, Any]:
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        raise HTTPException(status_code=503, detail="Dev store unavailable.")
    op_id = f"{action.upper()}-{random.getrandbits(48):012x}"
    now = datetime.now(timezone.utc).isoformat()
    await mongo_client[settings.MONGO_DB_NAME][collection].insert_one({
        "op_id": op_id, "action": action, "data": data,
        "requested_by": payload.get("sub"), "status": "ACCEPTED", "created_at": now,
    })
    return {"op_id": op_id, "status": "ACCEPTED", "created_at": now}

@dev_router.post("/policy/checked-command")
async def execute_policy_checked_command(req: Request, data: Dict, payload: Dict=Depends(hrit_admin_role_required)):
    """Run the command through the runtime policy enforcer, then persist the outcome."""
    scan = await runtime_enforcer("checked_command", {"Command": data})
    decision = (scan.get("decision") or "").upper()
    if decision in ("DENY", "STOP", "BLOCK"):
        raise HTTPException(status_code=400, detail=f"Command blocked by policy: {scan.get('reason', 'denied')}")
    result = await _dev_persist(req, "dev_checked_commands", "checked_command",
                                {"command": data, "decision": decision or "PASS", "audit_id": scan.get("audit_id")}, payload)
    return {"status": "Command Checked and Executed", "decision": decision or "PASS", **result}

@dev_router.post("/sandbox/deploy")
async def sandbox_deploy(req: Request, data: Dict, payload: Dict=Depends(hrit_admin_role_required)):
    result = await _dev_persist(req, "sandbox_deployments", "sandbox_deploy", data, payload)
    return {"status": "Sandbox Deployment Initiated", **result}


# BPCL_POLICY {
#   NAME: "PTO_LIMIT"
#   SCOPE: EMPLOYEE
#   CONSTRAINT: IF (...) THEN DENY_TRANSACTION
#   AUDIT_LEVEL: HIGH
# }
_BPCL_FIELD = re.compile(r'^\s*([A-Z_]+)\s*:\s*(.+?)\s*$', re.M)
_BPCL_CONSTRAINT = re.compile(r'IF\s*\((?P<condition>.+?)\)\s*THEN\s+(?P<action>[A-Z_]+)', re.S)


def _parse_bpcl(text: str) -> Dict[str, Any]:
    """Read a BPCL document into the structured form the validator checks.

    Anything it cannot recognise is left for the validator to report, so a
    malformed document still fails, and fails for its real reason rather than
    for the shape of the wrapper it arrived in.
    """
    fields = {k: v.strip().strip('"') for k, v in _BPCL_FIELD.findall(text or "")}
    name = fields.get("NAME", "")

    rules: List[Dict[str, Any]] = []
    for index, match in enumerate(_BPCL_CONSTRAINT.finditer(text or ""), start=1):
        rules.append({
            # The validator requires id, condition and action on every rule.
            "id": f"{name or 'rule'}_{index}",
            "condition": " ".join(match.group("condition").split()),
            "action": match.group("action"),
            "audit_level": fields.get("AUDIT_LEVEL", "STANDARD"),
            "scope": fields.get("SCOPE", "EMPLOYEE"),
        })

    content: Dict[str, Any] = {"rules": rules, "source": "bpcl", "raw": text}
    # Omit the key entirely when there is no name, so the validator reports the
    # missing field rather than accepting an empty one. A document with no
    # CONSTRAINT line has nothing to enforce and must not pass as secure.
    if name:
        content["policy_name"] = name
    if not rules:
        content["rules"] = []
        content["parse_error"] = ("No CONSTRAINT was found. A BPCL policy needs at least one "
                                 "IF (...) THEN <ACTION> line to enforce anything.")
    return content


@dev_router.post("/policy/scan")
async def security_scan_bpcl(req: Request, code: Dict[str, Any], payload: Dict=Depends(policy_admin_role_required)):
    """Validate BPCL through the real V&V compiler.

    Accepts either a JSON policy body or raw BPCL text; the compiler validates a
    structured document, so plain text is wrapped before validation.
    """
    vv = getattr(req.app.state, "vv_compiler", None)
    if not vv:
        raise HTTPException(status_code=503, detail="V&V compiler unavailable.")

    raw = code.get("code", code.get("content", ""))
    policy_id = code.get("policy_id", "adhoc-scan")
    if isinstance(raw, str):
        try:
            content = json.loads(raw)
        except Exception:
            # BPCL text used to be wrapped as {"bpcl_code": raw} and handed
            # straight to a validator that requires policy_name and rules[], so
            # every BPCL document this module exists to lint came back
            # VULNERABLE with "Missing required field: policy_name" - including
            # the example the screen itself offers as a starting point.
            content = _parse_bpcl(raw)
    else:
        content = raw or {}

    try:
        # validate_bpcl(policy_id, content) is async and returns
        # {is_valid, errors, type, policy_id, details?}
        result = await vv.validate_bpcl(policy_id, content)
    except Exception as e:
        logger.error(f"BPCL scan failed: {e}")
        raise HTTPException(status_code=400, detail=f"Scan failed: {e}")

    is_valid = bool(result.get("is_valid"))
    # A BPCL document that parsed to no rules is not a secure policy, it is an
    # empty one. The validator only checks that `rules` is a list, so an empty
    # list passed straight through as SECURE.
    parse_error = content.get("parse_error") if isinstance(content, dict) else None
    if parse_error:
        is_valid = False
        result = {**result, "errors": [*(result.get("errors") or []), parse_error],
                  "type": result.get("type") or "SYNTAX"}
    return {
        "status": "SECURE" if is_valid else "VULNERABLE",
        "is_valid": is_valid,
        "failure_type": result.get("type"),
        "vulnerabilities": result.get("errors", []),
        "trace": result.get("details") or (
            "Policy passed syntax and semantic validation."
            if is_valid else f"Validation failed at the {result.get('type', 'unknown')} stage."
        ),
    }

# ======================================
# 6. HR MODULES ROUTER (Fixed/Complete)
# ======================================
@hr_router.get("/comp/{employee_id}")
async def get_comp(req: Request, employee_id: str, payload: Dict=Depends(manager_role_required)):
    """Salary is among the most sensitive fields we hold. HR roles may look up
    anyone; a line manager may only see their own direct reports."""
    hr_modules_service: HRModulesService = getattr(req.app.state, "hr_modules_service", None)
    if not hr_modules_service: raise HTTPException(status_code=503, detail="HR Modules Service unavailable.")

    role = (payload.get("role") or "").lower()
    if role == "manager":
        manager_uuid = payload.get("employee_uuid")
        try:
            row = await pg_client.fetchrow(
                "SELECT 1 AS ok FROM employee_pii WHERE employee_uuid = $1 AND manager_id = $2",
                employee_id, manager_uuid,
            )
        except Exception as e:
            logger.error(f"comp reporting-line check failed: {e}")
            raise HTTPException(status_code=500, detail="Could not verify the reporting line.")
        if not row:
            raise HTTPException(status_code=403, detail="You can only view compensation for your own direct reports.")

    return await hr_modules_service.get_employee_compensation(employee_id, payload['role'])

@hr_router.post("/comp/update")
async def update_comp(req: Request, data: CompensationUpdateRequest, payload: Dict=Depends(policy_admin_role_required)):
    """Record a pay change.

    This required hrit_admin, but the Compensation Workbench ships under HR
    Operations and only an HRBP ever opens it, so the save button returned 403
    for every person who could reach it.
    """
    hr_modules_service: HRModulesService = getattr(req.app.state, "hr_modules_service", None)
    if not hr_modules_service: raise HTTPException(status_code=503, detail="HR Modules Service unavailable.")
    return await hr_modules_service.update_compensation(
        data.employee_id,
        data.new_salary,
        data.new_grade,
        data.effective_date,
        payload['sub']
    )

# team-trend MUST be declared before /performance/{employee_id}, or the path
# param route captures "team-trend" as an employee_id.
@hr_router.get("/performance/team-trend")
async def get_team_performance(req: Request, month: Optional[str] = Query(None), year: Optional[int] = Query(None), payload: Dict=Depends(manager_role_required)):
    hr_modules_service: HRModulesService = getattr(req.app.state, "hr_modules_service", None)
    if not hr_modules_service: raise HTTPException(status_code=503, detail="HR Modules Service unavailable.")
    return await hr_modules_service.get_team_performance_trend()

@hr_router.get("/performance/{employee_id}")
async def get_perf(req: Request, employee_id: str, payload: Dict=Depends(manager_role_required)):
    """A line manager sees their own reports; HR roles see anyone."""
    hr_modules_service: HRModulesService = getattr(req.app.state, "hr_modules_service", None)
    if not hr_modules_service: raise HTTPException(status_code=503, detail="HR Modules Service unavailable.")
    scoped = await _scoped_employee_id(payload, employee_id)
    return await hr_modules_service.get_employee_performance(scoped, payload['role'])

@hr_router.get("/timesheets")
async def get_timesheets(req: Request, limit: int = Query(50), offset: int = Query(0), payload: Dict=Depends(employee_role_required)):
    hr_modules_service: HRModulesService = getattr(req.app.state, "hr_modules_service", None)
    if not hr_modules_service: raise HTTPException(status_code=503, detail="HR Modules Service unavailable.")
    return await hr_modules_service.get_timesheets(payload['sub'], limit=limit, offset=offset)

@hr_router.post("/timesheets")
async def submit_timesheet(req: Request, data: Dict, payload: Dict=Depends(employee_role_required)): 
    hr_modules_service: HRModulesService = getattr(req.app.state, "hr_modules_service", None)
    if not hr_modules_service: HTTPException(status_code=503, detail="HR Modules Service unavailable.")
    return await hr_modules_service.submit_timesheet(payload['sub'], data)

@hr_router.post("/timesheets/pre-check")
async def run_timesheet_pre_check(req: Request, data: Dict, payload: Dict=Depends(employee_role_required)):
    """Run the SAME policy engine that gates submission, without saving anything.

    This used to be an inline `hours > 40` literal with invented policy prose, so
    the pre-check could tell someone they were fine and submission could then
    refuse them (or the reverse). A dry run must use the real decision path.
    """
    from services.agent_spec_dsl import TriggerType

    try:
        hours = float(data.get("hours", 0) or 0)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="hours must be a number.")

    employee_uuid = payload.get("employee_uuid")
    jurisdiction = None
    if employee_uuid:
        try:
            row = await pg_client.fetchrow(
                "SELECT jurisdiction_code FROM employee_pii WHERE employee_uuid = $1", employee_uuid
            )
            jurisdiction = (row or {}).get("jurisdiction_code")
        except Exception as e:
            logger.warning(f"pre-check jurisdiction lookup failed: {e}")

    context = {
        "employee_id": employee_uuid,
        "Proposed": {"Hours": hours, "SubmittedDate": datetime.now(timezone.utc).isoformat()},
        "Policy_Context": {
            "jurisdiction": jurisdiction,
            "employment_type": data.get("employment_type", "FULL_TIME"),
            "total_hours_this_week": hours,
        },
    }

    try:
        result = await runtime_enforcer(TriggerType.TIME_CLOCK_IN.value, context)
    except Exception as e:
        logger.error(f"Timesheet pre-check enforcement failed: {e}")
        raise HTTPException(status_code=503, detail="The policy engine is unavailable, so this cannot be checked now.")

    decision = (result.get("decision") or "").upper()
    blocked = decision in ("DENY", "STOP", "BLOCK", "ERROR")
    reason = result.get("reason") or ("Blocked by policy" if blocked else "Within policy")
    return {
        "status": "FAIL" if blocked else "PASS",
        "decision": decision,
        "messages": [reason],
        "reason": reason,
        "audit_id": result.get("audit_id"),
        "jurisdiction": jurisdiction,
    }

@hr_router.get("/leave/balance")
async def get_leave_balance(req: Request, payload: Dict=Depends(employee_role_required)):
    hr_modules_service: HRModulesService = getattr(req.app.state, "hr_modules_service", None)
    if not hr_modules_service: raise HTTPException(status_code=503, detail="HR Modules Service unavailable.")
    employee_uuid = payload.get("employee_uuid")
    if not employee_uuid:
        raise HTTPException(status_code=404, detail="No employee record linked to this account.")
    return await hr_modules_service.get_employee_leave_balance(employee_uuid)

@hr_router.post("/leave/balance/{employee_id}")
async def set_leave_balance(req: Request, employee_id: str,
                            hours: float = Body(..., embed=True),
                            reason: str = Body("", embed=True),
                            payload: Dict = Depends(policy_admin_role_required)):
    """Grant or correct an employee's remaining leave entitlement.

    There was no way to do this anywhere in the product: entitlements only ever
    came from the initial seed, so HR could not grant a new starter their
    allowance, apply an annual reset, or correct a mistake.

    This sets what is left to take. Hours already taken are not disturbed.
    """
    if hours < 0:
        raise HTTPException(status_code=400, detail="An entitlement cannot be negative.")
    exists = await pg_client.fetchrow(
        "SELECT 1 AS ok FROM employee_pii WHERE employee_uuid = $1", employee_id)
    if not exists:
        raise HTTPException(status_code=404, detail=f"There is no employee with the id {employee_id}.")

    await pg_client.execute(
        """INSERT INTO leave_balance (employee_uuid, balance_hours, used_hours, policy_id)
           VALUES ($1, $2, 0, 'LEAVE_POLICY_GLOBAL')
           ON CONFLICT (employee_uuid) DO UPDATE SET balance_hours = EXCLUDED.balance_hours""",
        employee_id, hours,
    )
    logger.info(f"Leave entitlement for {employee_id} set to {hours}h by {payload['sub']}: {reason or 'no reason given'}")
    return {
        "employee_id": employee_id,
        "remaining_hours": hours,
        "set_by": payload["sub"],
        "reason": reason,
        "message": f"{employee_id} now has {hours:g} hours of leave left to take.",
    }

@hr_router.get("/leave/requests")
async def get_leave_history(req: Request, limit: int = Query(50), offset: Optional[int] = Query(None), payload: Dict=Depends(employee_role_required)):
    hr_modules_service: HRModulesService = getattr(req.app.state, "hr_modules_service", None)
    if not hr_modules_service: raise HTTPException(status_code=503, detail="HR Modules Service unavailable.")
    employee_uuid = payload.get("employee_uuid")
    if not employee_uuid:
        return []
    return await hr_modules_service.get_leave_history(employee_uuid, limit=limit)

def _hr(req: Request) -> HRModulesService:
    svc = getattr(req.app.state, "hr_modules_service", None)
    if not svc:
        raise HTTPException(status_code=503, detail="HR Modules Service unavailable.")
    return svc

def _self_uuid(payload: Dict) -> str:
    uid = payload.get("employee_uuid")
    if not uid:
        raise HTTPException(status_code=404, detail="No employee record linked to this account.")
    return uid

@hr_router.post("/performance/review")
async def submit_review(req: Request, data: Dict, payload: Dict=Depends(manager_role_required)):
    """Persist a performance review to the Postgres UDM."""
    employee_uuid = data.get("employee_uuid") or data.get("employee_id")
    rating = data.get("overall_rating") or data.get("rating")
    if not employee_uuid or rating is None:
        raise HTTPException(status_code=400, detail="employee_uuid and overall_rating are required.")
    try:
        await pg_client.execute(
            """INSERT INTO performance_reviews (employee_uuid, overall_rating, review_period_end, reviewer_id)
               VALUES ($1, $2, CURRENT_DATE, $3)""",
            employee_uuid, float(rating), payload["sub"],
        )
    except Exception as e:
        logger.error(f"submit_review failed: {e}")
        raise HTTPException(status_code=500, detail="Could not save review.")
    return {"status": "Review Saved", "employee_uuid": employee_uuid, "overall_rating": float(rating)}

@hr_router.get("/career/path/{employee_id}")
async def get_career_path(req: Request, employee_id: str, payload: Dict=Depends(employee_role_required)):
    return await _hr(req).get_career_path(await _scoped_employee_id(payload, employee_id))

@hr_router.get("/feedback/peer/{employee_id}")
async def get_peer_feedback(req: Request, employee_id: str, payload: Dict=Depends(employee_role_required)):
    return await _hr(req).get_peer_feedback(await _scoped_employee_id(payload, employee_id))

@hr_router.get("/profile/skills")
async def get_skills(req: Request, payload: Dict=Depends(employee_role_required)):
    return await _hr(req).get_skills(_self_uuid(payload))

@hr_router.post("/profile/skills")
async def save_skills(req: Request, data: Dict, payload: Dict=Depends(employee_role_required)):
    return await _hr(req).save_skills(_self_uuid(payload), data.get("skills", []))

@hr_router.get("/payslips")
async def get_payslips(req: Request, month: Optional[str] = Query(None), year: Optional[int] = Query(None), payload: Dict=Depends(employee_role_required)):
    return await _hr(req).get_payslips(_self_uuid(payload))

@hr_router.get("/benefits")
async def get_benefits(req: Request, payload: Dict=Depends(employee_role_required)):
    """Benefits the platform actually holds for this employee.

    Only the leave entitlement is a real record today. Health cover and
    retirement matching are not stored anywhere, so they are reported as
    unavailable rather than invented.
    """
    hr = _hr(req)
    employee_uuid = _self_uuid(payload)
    balance = await hr.get_employee_leave_balance(employee_uuid)
    return {
        "employee_id": employee_uuid,
        "leave_policy": balance.get("policy"),
        "annual_leave_hours": balance.get("balance_hours"),
        "used_leave_hours": balance.get("used_hours"),
        "health_plan": None,
        "retirement_match_pct": None,
        "unavailable": ["health_plan", "retirement_match_pct"],
        "note": "Health cover and retirement matching are administered outside HiRo.",
    }

@hr_router.post("/feedback")
async def submit_feedback(req: Request, feedback: str = Body(..., embed=True),
                          about_employee_id: Optional[str] = Body(None, embed=True),
                          payload: Dict=Depends(employee_role_required)):
    """Leave feedback, either general or about a named colleague.

    Without somewhere to say who the feedback is about, nothing could ever write
    peer feedback, and the "feedback about you" panel was permanently empty.
    """
    return await _hr(req).submit_feedback(_self_uuid(payload), feedback, about_employee_id)

@hr_router.get("/retention/preference")
async def get_retention_preference(req: Request, payload: Dict=Depends(employee_role_required)):
    return await _hr(req).get_retention_preference(_self_uuid(payload))

@hr_router.post("/retention/preference")
async def save_retention_preference(req: Request, preference: str = Body(..., embed=True), payload: Dict=Depends(employee_role_required)):
    return await _hr(req).save_retention_preference(_self_uuid(payload), preference)

@hr_router.post("/expenses")
async def submit_expense(req: Request, expense_data: str = Form(...), receipt: Optional[UploadFile] = File(None), payload: Dict=Depends(employee_role_required)):
    data = json.loads(expense_data)
    return await _hr(req).submit_expense(_self_uuid(payload), data, receipt.filename if receipt else None)

@hr_router.get("/expenses")
async def list_expenses(req: Request, status: Optional[str] = Query(None), limit: int = Query(100), payload: Dict=Depends(employee_role_required)):
    """Employees see their own claims; a manager sees their direct reports';
    HR roles see everyone's."""
    role = (payload.get("role") or "").lower()
    employee_id = _self_uuid(payload) if role == "employee" else None
    team_of = payload.get("employee_uuid") if role == "manager" else None
    return await _hr(req).get_expenses(employee_id, status=status, limit=limit, team_of=team_of)

@hr_router.post("/expenses/{expense_id}/decision")
async def decide_expense(req: Request, expense_id: str, approved: bool = Body(...), comments: str = Body(""), payload: Dict=Depends(manager_role_required)):
    """Approve or reject an expense claim."""
    return await _hr(req).decide_expense(expense_id, approved, payload["sub"], comments)

@hr_router.get("/timesheets/pending")
async def list_pending_timesheets(req: Request, limit: int = Query(100), payload: Dict=Depends(manager_role_required)):
    """Timesheets awaiting a decision, scoped to the caller's own team.

    A line manager should not see, let alone approve, the whole company's
    timesheets. HR roles still see everything.
    """
    role = (payload.get("role") or "").lower()
    team_of = payload.get("employee_uuid") if role == "manager" else None
    return await _hr(req).get_timesheets_for_approval(limit=limit, team_of=team_of)

@hr_router.post("/timesheets/{timesheet_id}/decision")
async def decide_timesheet(req: Request, timesheet_id: str, approved: bool = Body(...), comments: str = Body(""), payload: Dict=Depends(manager_role_required)):
    """Approve or reject a submitted timesheet."""
    return await _hr(req).decide_timesheet(timesheet_id, approved, payload["sub"], comments)

@hr_router.get("/audit/trace")
async def get_audit_trace(req: Request, employee_id: Optional[str] = Query(None), action: Optional[str] = Query(None), limit: int = Query(50), payload: Dict=Depends(policy_admin_role_required)):
    """Real audit trail from the Postgres policy_audit_log."""
    clauses, args = [], []
    if action:
        args.append(action); clauses.append(f"trigger_type = ${len(args)}")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    args.append(max(1, min(int(limit or 50), 500)))
    query = f"""SELECT audit_id, trigger_type, decision, reason, decision_timestamp
                FROM policy_audit_log {where} ORDER BY decision_timestamp DESC LIMIT ${len(args)}"""
    try:
        rows = await pg_client.fetch(query, *args)
    except Exception as e:
        logger.warning(f"audit trace query failed: {e}")
        return []
    return [
        {"timestamp": str(r["decision_timestamp"]), "audit_id": r["audit_id"],
         "action": r["trigger_type"], "decision": r["decision"], "summary": r.get("reason")}
        for r in rows
    ]

@hr_router.post("/expenses/ocr-scan")
async def scan_expense_receipt(req: Request, file: UploadFile = File(...), payload: Dict=Depends(employee_role_required)):
    """Extract expense fields from a receipt using the local LLM (vision-free: OCR text
    is not available, so we parse the filename + let the model infer a structured draft)."""
    ai = getattr(req.app.state, "ai_service", None)
    if not ai:
        raise HTTPException(status_code=503, detail="AI service unavailable.")
    raw = (await file.read())[:4000]
    text = raw.decode("utf-8", errors="ignore") if raw else file.filename
    prompt = (
        "Extract expense fields from this receipt text as strict JSON with keys "
        "vendor (string), amount (number), currency (string), category (string), date (string). "
        f"Receipt:\n{text}"
    )
    try:
        result = await ai.generate_text(prompt, "You are a precise receipt parser. Output only JSON.")
        parsed = json.loads(result[result.find("{"): result.rfind("}") + 1])
    except Exception as e:
        logger.warning(f"OCR parse failed, returning minimal draft: {e}")
        parsed = {"vendor": "", "amount": 0, "currency": "USD", "category": "General", "date": ""}
    return parsed

@hr_router.post("/offboarding/knowledge")
async def submit_offboarding_knowledge(req: Request, data: Dict, payload: Dict=Depends(employee_role_required)):
    return await _hr(req).submit_offboarding_knowledge(_self_uuid(payload), data)

async def _reports_to(employee_id: str, manager_uuid: Optional[str]) -> bool:
    """True when employee_id is a direct report of manager_uuid."""
    if not manager_uuid:
        return False
    try:
        row = await pg_client.fetchrow(
            "SELECT 1 AS ok FROM employee_pii WHERE employee_uuid = $1 AND manager_id = $2",
            employee_id, manager_uuid,
        )
    except Exception as e:
        logger.error(f"reporting-line check failed: {e}")
        raise HTTPException(status_code=500, detail="Could not verify the reporting line.")
    return bool(row)

async def _scoped_employee_id(payload: Dict, requested: str) -> str:
    """Restrict a personnel lookup to what the caller is entitled to see.

    - employee: only their own record.
    - manager:  themselves and their direct reports. A line manager has no
                business reading an arbitrary colleague's record, and this used
                to let them read anyone in the organisation.
    - hrbp / hrit_admin: anyone, since HR administers the whole population.
    """
    role = (payload.get("role") or "").lower()
    own = payload.get("employee_uuid")

    if role == "employee":
        own = _self_uuid(payload)
        if requested and requested != own:
            raise HTTPException(status_code=403, detail="You can only access your own record.")
        return own

    if role == "manager" and requested and requested != own:
        if not await _reports_to(requested, own):
            raise HTTPException(status_code=403, detail="You can only access your own direct reports.")

    return requested

@hr_router.get("/profile/{employee_id}")
async def get_employee_profile(req: Request, employee_id: str, payload: Dict=Depends(employee_role_required)):
    return await _hr(req).get_employee_profile(await _scoped_employee_id(payload, employee_id))

@hr_router.put("/profile/{employee_id}")
async def update_employee_profile(req: Request, employee_id: str, data: Dict, payload: Dict=Depends(employee_role_required)):
    return await _hr(req).update_employee_profile(await _scoped_employee_id(payload, employee_id), data)

@hr_router.get("/payslips/download/{file_key}")
async def download_payslip(req: Request, file_key: str, payload: Dict=Depends(employee_role_required)):
    """Return a real payslip document built from the employee's comp record."""
    hr = _hr(req)
    employee_uuid = _self_uuid(payload)
    slips = await hr.get_payslips(employee_uuid, limit=60)
    match = next((s for s in slips if s["period"] == file_key), slips[0] if slips else None)
    if not match:
        raise HTTPException(status_code=404, detail="No payslip found for this period.")
    body = (
        "HiRo Payslip\n============\n"
        f"Employee: {employee_uuid}\n"
        f"Period:   {match['period']}\n"
        f"Gross (monthly): {match['gross']:.2f}\n"
    )
    return Response(content=body.encode(), media_type="text/plain",
                    headers={"Content-Disposition": f"attachment; filename=payslip-{file_key}.txt"})

def _owner_scope(payload: Dict) -> Optional[str]:
    """Employees are scoped to their own records; manager+ are not."""
    return _self_uuid(payload) if (payload.get("role") or "").lower() == "employee" else None

@hr_router.get("/doc/details/{document_id}")
async def get_document_details(req: Request, document_id: str, payload: Dict=Depends(employee_role_required)):
    return await _hr(req).get_document_details(document_id, owner_uuid=_owner_scope(payload))

@hr_router.delete("/doc/delete/{document_id}")
async def delete_employee_document(req: Request, document_id: str, payload: Dict=Depends(employee_role_required)):
    return await _hr(req).delete_document(document_id, owner_uuid=_owner_scope(payload))

@hr_router.post("/doc/ingestion/{employee_id}/{doc_type}")
async def upload_employee_document(req: Request, employee_id: str, doc_type: str, file: UploadFile = File(...), payload: Dict=Depends(employee_role_required)):
    """Employees may upload their own documents; manager+ may upload for anyone."""
    role = (payload.get("role") or "").lower()
    if role == "employee":
        employee_id = _self_uuid(payload)
    contents = await file.read()
    return await _hr(req).upload_document(employee_id, doc_type, file.filename, size=len(contents))

@hr_router.get("/doc/employee-documents")
async def get_employee_documents(req: Request, employee_id: Optional[str] = Query(None), payload: Dict = Depends(employee_role_required)):
    """Employees see their own documents; manager+ may request any employee's."""
    role = (payload.get("role") or "").lower()
    if role == "employee":
        employee_id = _self_uuid(payload)  # employees are scoped to themselves
    return await _hr(req).get_employee_documents(employee_id)

@hr_router.post("/offboarding/upload")
async def upload_offboarding_file(req: Request, file: UploadFile = File(...), payload: Dict=Depends(hrit_admin_role_required)):
    contents = await file.read()
    return await _hr(req).upload_document(payload.get("employee_uuid", "SYSTEM"), "offboarding", file.filename, size=len(contents))

# ======================================
# 7. ESS & MSS ROUTERS (Fixed/Complete)
# ======================================
@ess_router.get("/dashboard/{employee_id}")
async def ess_dash(req: Request, employee_id: str, payload: Dict=Depends(employee_role_required)):
    # The frontend passes the caller's own id (user.id); always serve the
    # authenticated user's own record, resolved to their Postgres employee_uuid.
    emp_uuid = payload.get("employee_uuid")
    if not emp_uuid:
        raise HTTPException(404, "No employee record linked to this account.")
    ess_service: ESSService = getattr(req.app.state, "ess_service", None)
    if not ess_service: raise HTTPException(status_code=503, detail="ESS Service unavailable.")
    return await ess_service.get_employee_dashboard_data(emp_uuid, payload['role'])

@ess_router.post("/leave/submit")
async def ess_leave(req: Request, data: LeaveRequestSubmit, payload: Dict=Depends(employee_role_required)):
    ess_service: ESSService = getattr(req.app.state, "ess_service", None)
    if not ess_service: raise HTTPException(status_code=503, detail="ESS Service unavailable.")
    # Store against the Postgres employee_uuid, not the login name, so the request
    # joins to employee_pii and shows up in the employee's own leave history.
    employee_uuid = payload.get("employee_uuid")
    if not employee_uuid:
        raise HTTPException(status_code=404, detail="No employee record linked to this account.")
    return await ess_service.submit_leave_request(employee_uuid, data.model_dump())

@ess_router.get("/profile/personal-info")
async def get_personal_info(req: Request, payload: Dict=Depends(employee_role_required)):
    """The caller's own profile from the users store (real record, no fabricated defaults)."""
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        raise HTTPException(status_code=503, detail="User store unavailable.")
    user = await mongo_client[settings.MONGO_DB_NAME]["users"].find_one(
        {"username": payload.get("sub")}, {"_id": 0, "password": 0, "hashed_password": 0},
    )
    if not user:
        raise HTTPException(status_code=404, detail="No profile found for this account.")
    return {
        "username": user.get("username"),
        "email": user.get("email"),
        "full_name": user.get("full_name"),
        "role": user.get("role"),
        "employee_uuid": user.get("employee_uuid"),
    }

@ess_router.post("/profile/update-request")
async def update_personal_info(req: Request, data: Dict, payload: Dict=Depends(employee_role_required)):
    """Persist a self-service profile-change request for HR review (does not mutate
    the record directly; approval flow applies it)."""
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        raise HTTPException(status_code=503, detail="Request store unavailable.")
    request_id = f"PCR-{random.getrandbits(48):012x}"
    await mongo_client[settings.MONGO_DB_NAME]["profile_change_requests"].insert_one({
        "request_id": request_id, "username": payload.get("sub"),
        "employee_uuid": payload.get("employee_uuid"), "requested_changes": data,
        "status": "PENDING", "submitted_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"status": "Update Requested", "request_id": request_id}


async def _pending_leave_requests(limit: int = 100, team_of: Optional[str] = None) -> List[Dict[str, Any]]:
    """Pending leave-approval items from the Postgres leave_requests table.

    `team_of` scopes to a manager's own direct reports. Without it a line manager
    saw, and could approve, every pending request in the company.
    """
    lim = max(1, min(int(limit or 100), 500))
    try:
        if team_of:
            rows = await pg_client.fetch(
                """SELECT lr.request_id, lr.employee_uuid, lr.start_date, lr.end_date,
                          lr.hours, lr.status, lr.submitted_at
                   FROM leave_requests lr
                   JOIN employee_pii e ON e.employee_uuid = lr.employee_uuid
                   WHERE lr.status = 'PENDING' AND e.manager_id = $1
                   ORDER BY lr.submitted_at ASC LIMIT $2""",
                team_of, lim,
            )
        else:
            rows = await pg_client.fetch(
                """SELECT request_id, employee_uuid, start_date, end_date, hours, status, submitted_at
                   FROM leave_requests WHERE status = 'PENDING'
                   ORDER BY submitted_at ASC LIMIT $1""",
                lim,
            )
    except Exception as e:
        logger.warning(f"pending leave query failed: {e}")
        return []
    return [
        {"request_id": r["request_id"], "type": "LEAVE_REQUEST", "employee_uuid": r["employee_uuid"],
         "start_date": str(r["start_date"]), "end_date": str(r["end_date"]),
         "hours": r["hours"], "status": r["status"], "submitted_at": str(r["submitted_at"])}
        for r in rows
    ]


async def _approval_queue(req: Request, payload: Dict, limit: int = 100) -> List[Dict[str, Any]]:
    """Everything waiting on this approver, across all three request kinds.

    The queue used to read leave only, so a timesheet or an expense claim an
    employee submitted never appeared for their manager at all: the person saw
    "submitted" and the manager saw an empty queue, with no screen anywhere that
    could clear it. Leave, timesheets and expenses all land here now, each scoped
    to the approver's own direct reports (HR roles see the whole organisation).
    """
    role = (payload.get("role") or "").lower()
    team_of = payload.get("employee_uuid") if role == "manager" else None
    hr = _hr(req)

    leave, timesheets, expenses = await asyncio.gather(
        _pending_leave_requests(limit=limit, team_of=team_of),
        hr.get_timesheets_for_approval(limit=limit, team_of=team_of),
        hr.get_expenses(status="SUBMITTED", limit=limit, team_of=team_of),
        return_exceptions=True,
    )

    def usable(result, kind):
        if isinstance(result, Exception):
            logger.warning(f"{kind} could not be loaded for the approval queue: {result}")
            return []
        return result or []

    items: List[Dict[str, Any]] = list(usable(leave, "leave"))
    items += list(usable(timesheets, "timesheets"))
    for e in usable(expenses, "expenses"):
        items.append({
            "request_id": e.get("expense_id"),
            "type": "EXPENSE",
            "employee_uuid": e.get("employee_uuid"),
            "amount": e.get("amount"),
            "currency": e.get("currency", "USD"),
            "category": e.get("category"),
            "description": e.get("description"),
            "status": e.get("status"),
            "submitted_at": e.get("submitted_at"),
        })

    # Oldest first: the longest-waiting person is the one being blocked most.
    items.sort(key=lambda i: str(i.get("submitted_at") or ""))
    return [i for i in items if i.get("request_id")][:max(1, min(int(limit or 100), 500))]

@mss_router.get("/team/roster")
async def get_team_roster(req: Request, manager_id: Optional[str] = Query(None), status: Optional[str] = Query(None),
                          limit: int = Query(50), offset: int = Query(0), payload: Dict=Depends(manager_role_required)):
    """Real team roster: the manager's direct reports via the MSS service (PII-vault backed).
    Paginated - a large org otherwise decrypts thousands of PII rows per request."""
    mss_service: MSSService = getattr(req.app.state, "mss_service", None)
    if not mss_service:
        raise HTTPException(status_code=503, detail="MSS Service unavailable.")
    mgr_uuid = payload.get("employee_uuid") or manager_id
    if not mgr_uuid:
        raise HTTPException(status_code=404, detail="No manager record linked to this account.")
    try:
        data = await mss_service.get_manager_team_data(mgr_uuid, payload["role"], limit=limit, offset=offset)
    except Exception as e:
        logger.warning(f"team roster query failed: {e}")
        return {"roster": []}
    return {
        "manager_id": mgr_uuid,
        "roster": data.get("team", []),
        "total": data.get("total", len(data.get("team", []))),
        "limit": data.get("limit"),
        "offset": data.get("offset"),
    }

@mss_router.get("/hiring/requisitions")
async def get_requisitions(req: Request, manager_id: Optional[str] = Query(None), status: Optional[str] = Query(None), payload: Dict=Depends(manager_role_required)):
    """Real hiring requisitions from the Mongo requisitions collection (empty until created)."""
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        return {"requisitions": []}
    query: Dict[str, Any] = {}
    if manager_id:
        query["manager_id"] = manager_id
    if status:
        query["status"] = status
    cursor = mongo_client[settings.MONGO_DB_NAME]["requisitions"].find(query, {"_id": 0}).sort("created_at", -1).limit(200)
    return {"requisitions": await cursor.to_list(length=200)}

@mss_router.post("/hiring/requisitions")
async def create_requisition(req: Request, data: Dict[str, Any], payload: Dict=Depends(manager_role_required)):
    """Open a hiring requisition. There was previously no way to create one."""
    title = (data.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="title is required.")
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        raise HTTPException(status_code=503, detail="Requisition store unavailable.")
    doc = {
        "requisition_id": f"REQ-{random.getrandbits(24):06x}".upper(),
        "title": title,
        "department": data.get("department", ""),
        "headcount": int(data.get("headcount", 1) or 1),
        "seniority": data.get("seniority", ""),
        "justification": data.get("justification", ""),
        "status": "OPEN",
        "manager_id": payload.get("employee_uuid") or payload.get("sub"),
        "created_by": payload.get("sub"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await mongo_client[settings.MONGO_DB_NAME]["requisitions"].insert_one(dict(doc))
    return {"status": "OPEN", "requisition": doc}

@mss_router.get("/team/{manager_id}")
async def mss_team(req: Request, manager_id: str, payload: Dict=Depends(manager_role_required)):
    # Resolve the caller's own manager record (frontend passes user.id in the path).
    mgr_uuid = payload.get("employee_uuid") or manager_id
    mss_service: MSSService = getattr(req.app.state, "mss_service", None)
    if not mss_service: raise HTTPException(status_code=503, detail="MSS Service unavailable.")
    return await mss_service.get_manager_team_data(mgr_uuid, payload['role'])

@mss_router.post("/leave/approve")
async def mss_approve(req: Request, request_id: str = Body(...), approved: bool = Body(...), comments: str = Body(""), payload: Dict=Depends(manager_role_required)):
    mss_service: MSSService = getattr(req.app.state, "mss_service", None)
    if not mss_service: raise HTTPException(status_code=503, detail="MSS Service unavailable.")
    return await mss_service.approve_leave(request_id, payload['sub'], approved)

@mss_router.get("/approvals/queue")
async def get_approval_queue(req: Request, limit: int = Query(100), payload: Dict=Depends(manager_role_required)):
    """Everything waiting on this manager: leave, timesheets and expense claims."""
    return await _approval_queue(req, payload, limit=limit)

@mss_router.get("/approvals/hrit-queue")
async def get_hrit_queue(req: Request, payload: Dict=Depends(hrit_admin_role_required)):
    """Organisation-wide pending approval queue."""
    return await _approval_queue(req, payload, limit=500)

@mss_router.post("/approvals/action")
async def action_approval(req: Request, payload_data: Dict, payload: Dict=Depends(manager_role_required)):
    """Approve or reject anything in the approval queue.

    One screen clears the whole queue, so this dispatches by request kind to the
    same handlers the dedicated endpoints use.

    The kind is always resolved from the caller's own queue, never from the
    request body. Trusting a client-supplied type would let a manager approve
    another team's timesheet by naming its id, because the per-kind decision
    handlers below take an id and do not re-check whose report it belongs to.
    Being in your queue is what authorises the decision.
    """
    request_id = payload_data.get("request_id") or payload_data.get("id")
    if not request_id:
        raise HTTPException(status_code=400, detail="request_id is required.")
    approved = bool(payload_data.get("approved", payload_data.get("action") == "approve"))
    comments = payload_data.get("comments", "")

    queue = await _approval_queue(req, payload, limit=500)
    match = next((i for i in queue if i.get("request_id") == request_id), None)
    if not match:
        raise HTTPException(
            status_code=404,
            detail="That request is not in your approval queue. It may already have been decided.")
    kind = str(match.get("type") or "").upper()

    if kind == "TIMESHEET":
        return await _hr(req).decide_timesheet(request_id, approved, payload["sub"], comments)
    if kind == "EXPENSE":
        return await _hr(req).decide_expense(request_id, approved, payload["sub"], comments)
    if kind in ("LEAVE_REQUEST", "LEAVE"):
        mss_service: MSSService = getattr(req.app.state, "mss_service", None)
        if not mss_service:
            raise HTTPException(status_code=503, detail="MSS Service unavailable.")
        return await mss_service.approve_leave(request_id, payload["sub"], approved, comments)
    raise HTTPException(status_code=400, detail=f"There is no approval handler for a {kind or 'blank'} request.")


# ======================================
# 8. WFP (Workforce Planning) ROUTER (Fixed/Complete)
# ======================================
@wfp_router.get("/dashboard{path:path}") 
async def get_wfp_dashboard_data(req: Request, path: str, payload: Dict = Depends(manager_role_required)):
    """FIX: Added robust endpoint to handle frontend's dashboard data request that currently 404s."""
    wfm_service = getattr(req.app.state, "wfm_service", None)
    if not wfm_service: raise HTTPException(status_code=503, detail="WFM Service unavailable.")
    
    data = await wfm_service.get_current_projections()
    return {"dashboard_data": data, "status": "OK"}


@wfp_router.get("/projections")
async def get_wfp_projections(req: Request, payload: Dict = Depends(manager_role_required)):
    """FIX: Added missing endpoint for WFP projections."""
    wfm_service = getattr(req.app.state, "wfm_service", None)
    if not wfm_service: raise HTTPException(status_code=503, detail="WFM Service unavailable.")
    return await wfm_service.get_current_projections()

@wfp_router.post("/predict_attrition")
async def predict_attrition(req: Request, employee_data: Dict = Body(...), payload: Dict = Depends(manager_role_required)):
    wfm_service = getattr(req.app.state, "wfm_service", None)
    if not wfm_service: raise HTTPException(status_code=503, detail="WFM Service unavailable.")
    
    if not employee_data:
        raise HTTPException(status_code=400, detail="Provide an employee_id (or a feature set) to score.")

    return await wfm_service.predict_attrition_risk(employee_data)

# ======================================
# 9. TA (Talent Acquisition) ROUTER (Fixed/Complete)
# ======================================
@ta_router.get("/snapshot")
async def get_talent_pool_snapshot(req: Request, payload: Dict = Depends(manager_role_required)):
    """Talent pools derived from the real workforce and open requisitions."""
    ta_service: TalentAcquisitionService = getattr(req.app.state, "ta_service", None)
    if not ta_service: raise HTTPException(status_code=503, detail="Talent Acquisition Service unavailable.")
    return await ta_service.get_talent_pool_snapshot(
        mongo_client=getattr(req.app.state, "mongo_client", None),
        db_name=settings.MONGO_DB_NAME,
    )
        
@ta_router.post("/predict_risk")
async def predict_ta_pipeline_risk(req: Request, scenario_data: Dict = Body(..., embed=True), payload: Dict = Depends(manager_role_required)):
    """Talent pipeline risk via the real scenario simulator."""
    ta_service: TalentAcquisitionService = getattr(req.app.state, "ta_service", None)
    if not ta_service: raise HTTPException(status_code=503, detail="Talent Acquisition Service unavailable.")
    snapshot = await ta_service.get_talent_pool_snapshot()
    risk = await ta_service.simulate_talent_scenario(scenario_data, snapshot)
    level = "HIGH" if risk >= 0.66 else "MEDIUM" if risk >= 0.33 else "LOW"
    return {
        "risk_score": round(risk, 3),
        "risk_level": level,
        "scenario": scenario_data,
        # Time-to-close and acceptance rate are not tracked here, so the score
        # partly rests on industry defaults. The response says which ones.
        **ta_service.assumed_inputs(snapshot),
    }

# ======================================
# 10. TALENT CONTENT ROUTER
# ======================================
async def _generate_jd(req: Request, data: Dict) -> Dict[str, Any]:
    """Real job-description generation via the local LLM."""
    ai_service: AIService = getattr(req.app.state, "ai_service", None)
    if not ai_service: raise HTTPException(status_code=503, detail="AI Service unavailable.")
    role = data.get("role_title") or data.get("title") or data.get("role") or "the role"
    dept = data.get("department", "the organization")
    seniority = data.get("seniority", "mid-level")
    prompt = (
        f"Write a professional job description for a {seniority} {role} in {dept}. "
        "Return strict JSON with keys: title, summary, responsibilities (array of strings), "
        "requirements (array of strings), nice_to_have (array of strings)."
    )
    raw = await ai_service.generate_text(prompt, "You are an expert HR copywriter. Output only JSON.")
    try:
        parsed = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
    except Exception:
        parsed = {"title": role, "summary": raw.strip()[:800], "responsibilities": [], "requirements": [], "nice_to_have": []}
    parsed["draft_id"] = f"JD-{random.getrandbits(24):06x}"
    return parsed

@talent_content_router.post("/job-description/generate")
async def generate_job_description(req: Request, data: Dict, payload: Dict = Depends(manager_role_required)):
    return await _generate_jd(req, data)

@talent_content_router.post("/job-description/generate-draft")
async def generate_jd_draft(req: Request, data: Dict, payload: Dict = Depends(manager_role_required)):
    return await _generate_jd(req, data)

# ======================================
# 11. TALENT EXP ROUTER
# ======================================
@talent_exp_router.get("/digital-twin/xai")
async def get_digital_twin_xai(req: Request, payload: Dict = Depends(employee_role_required)):
    """Explain THIS employee's own retention outlook.

    Previously this explained workforce-wide averages, so every employee saw the
    same explanation about the whole organisation rather than about themselves.
    """
    wfm_service = getattr(req.app.state, "wfm_service", None)
    xai: XAIWrapper = getattr(req.app.state, "xai_wrapper", None)
    employee_uuid = payload.get("employee_uuid")
    if not (wfm_service and xai and employee_uuid):
        raise HTTPException(status_code=503, detail="Digital twin explainability unavailable.")

    prediction = await wfm_service.predict_attrition_risk({"employee_id": employee_uuid})
    explanation = xai.explain_prediction(
        prediction.get("feature_vector_used", {}), prediction.get("risk_score")
    )
    return {
        **explanation,
        "employee_uuid": employee_uuid,
        "risk_level": prediction.get("risk_level"),
        "recommendation": prediction.get("recommendation"),
    }

@talent_exp_router.post("/learning/synthesize/{employee_id}")
async def synthesize_learning_curriculum(req: Request, employee_id: str, target_role: Optional[str] = Body(None, embed=True), payload: Dict = Depends(employee_role_required)):
    learning_agent: ImmersiveLearningAgent = getattr(req.app.state, "immersive_learning_agent", None)
    if not learning_agent: raise HTTPException(status_code=503, detail="Immersive Learning Agent unavailable.")
    return await learning_agent.synthesize_personalized_curriculum(employee_id, target_role or "future_role")

@talent_exp_router.get("/learning-modules")
async def get_learning_modules(req: Request, payload: Dict = Depends(employee_role_required)):
    """Real learning catalog from the Mongo learning_modules collection (empty until seeded)."""
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        return {"modules": []}
    cursor = mongo_client[settings.MONGO_DB_NAME]["learning_modules"].find({}, {"_id": 0}).limit(200)
    return {"modules": await cursor.to_list(length=200)}

# ======================================
# 12. AI ROUTER (Fixed/Complete)
# ======================================
@ai_router.post("/generate")
async def generate_text(req: Request, prompt: str = Body(...), system_instruction: str = Body(...), payload: Dict=Depends(employee_role_required)):
    ai_service: AIService = getattr(req.app.state, "ai_service", None)
    if not ai_service: raise HTTPException(status_code=503, detail="AI Service unavailable.")
    return await ai_service.generate_text(prompt, system_instruction)

@ai_router.post("/generate-bpmn")
async def generate_bpmn(req: Request, description: str = Body(...), domain: str = Body(...), payload: Dict=Depends(hrit_admin_role_required)):
    """Generate BPMN 2.0 XML for a described workflow using the local LLM."""
    ai_service: AIService = getattr(req.app.state, "ai_service", None)
    if not ai_service: raise HTTPException(status_code=503, detail="AI Service unavailable.")
    prompt = (
        f"Generate valid BPMN 2.0 XML for this {domain} workflow: {description}. "
        "Output only the XML, starting with <?xml. Include a bpmn:process with startEvent, "
        "at least two tasks, and an endEvent."
    )
    xml = await ai_service.generate_text(prompt, "You are a BPMN modeling expert. Output only BPMN 2.0 XML.")
    xml = _strip_code_fence(xml)
    if not xml.lstrip().startswith("<"):
        raise HTTPException(
            status_code=502,
            detail="The model did not return XML for that description. Try describing the steps more plainly.")
    return {"description": description, "domain": domain, "bpmn_xml": xml}


def _strip_code_fence(text: str) -> str:
    """Remove a surrounding markdown code fence.

    The model wraps XML in ```xml ... ```, and this was returned verbatim as
    bpmn_xml and saved to the workflow store, so anything that actually parses
    BPMN would reject it.
    """
    body = (text or "").strip()
    if not body.startswith("```"):
        return body
    lines = body.splitlines()
    lines = lines[1:]                      # drop the opening ```xml
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()

@ai_router.post("/workflow/save")
async def save_generated_workflow(req: Request, workflow_data: Dict, payload: Dict=Depends(hrit_admin_role_required)):
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client: raise HTTPException(status_code=503, detail="Store unavailable.")
    wid = f"WKF-{random.getrandbits(24):06x}"
    await mongo_client[settings.MONGO_DB_NAME]["saved_workflows"].insert_one({
        "workflow_id": wid, "data": workflow_data, "saved_by": payload.get("sub"),
        "saved_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"status": "Workflow Saved", "id": wid}

@ai_router.post("/embedding")
async def generate_embedding(req: Request, text: str = Body(..., embed=True), payload: Dict=Depends(employee_role_required)):
    ai_service: AIService = getattr(req.app.state, "ai_service", None)
    if not ai_service: raise HTTPException(status_code=503, detail="AI Service unavailable.")
    return {"embedding": await ai_service.generate_embedding(text)}

@ai_router.get("/models")
async def get_ai_models(req: Request, payload: Dict=Depends(employee_role_required)):
    ai_service: AIService = getattr(req.app.state, "ai_service", None)
    if not ai_service: raise HTTPException(status_code=503, detail="AI Service unavailable.")
    return {"models": await ai_service.get_ai_models()}

@ai_router.get("/provider/config")
async def get_active_ai_provider(req: Request, payload: Dict=Depends(hrit_admin_role_required)):
    """Report the real active LLM provider (local Ollama)."""
    return {
        "provider": "Ollama (local)",
        "base_url": getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434"),
        "default_model": getattr(settings, "OLLAMA_MODEL", getattr(settings, "DEFAULT_AI_MODEL", "llama3.1:8b")),
        "status": "Active",
    }

@ai_router.post("/provider/switch")
async def set_ai_provider(req: Request, provider: str = Body(..., embed=True), payload: Dict=Depends(hrit_admin_role_required)):
    """Switch the model the AI service uses, to one that is actually installed.

    This used to probe for a `set_default_model` method and a `default_model`
    attribute, neither of which exists on AIService (its field is `model`). So
    it created an orphan attribute, reported "Switched" for any string at all,
    including models that do not exist, and carried on serving from the old one.
    """
    ai_service: AIService = getattr(req.app.state, "ai_service", None)
    if not ai_service: raise HTTPException(status_code=503, detail="AI Service unavailable.")

    available = [m.get("name") for m in await ai_service.get_ai_models()]
    if provider not in available:
        raise HTTPException(
            status_code=400,
            detail=(f"'{provider}' is not installed on this machine. "
                    f"Available models: {', '.join(available) or 'none'}."))

    previous = ai_service.model
    ai_service.model = provider
    logger.info(f"AI model switched from {previous} to {provider} by {payload['sub']}")
    return {
        "status": "Switched",
        "previous_model": previous,
        "new_provider": provider,
        "message": f"HiRo is now answering with {provider}.",
    }

@ai_router.post("/command")
async def legacy_ai_command(req: Request, payload_data: Dict, payload: Dict=Depends(employee_role_required)):
    """Free-form AI command executed against the local LLM."""
    ai_service: AIService = getattr(req.app.state, "ai_service", None)
    if not ai_service: raise HTTPException(status_code=503, detail="AI Service unavailable.")
    prompt = payload_data.get("prompt") or payload_data.get("command") or ""
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required.")
    result = await ai_service.generate_text(prompt, "You are HiRo's assistant. Be concise and helpful.")
    return {"status": "COMPLETED", "result": result}

async def _twin_messages(req: Request):
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client: raise HTTPException(status_code=503, detail="Store unavailable.")
    return mongo_client[settings.MONGO_DB_NAME]["twin_messages"]

@ai_router.post("/twin/message/{reportee_id}")
async def send_digital_twin_message(req: Request, reportee_id: str, message: str = Body(..., embed=True), payload: Dict = Depends(manager_role_required)):
    """Persist a manager->digital-twin message and generate the twin's real AI reply."""
    ai_service: AIService = getattr(req.app.state, "ai_service", None)
    if not ai_service: raise HTTPException(status_code=503, detail="AI Service unavailable.")
    col = await _twin_messages(req)
    now = datetime.now(timezone.utc).isoformat()
    thread = f"{payload['sub']}:{reportee_id}"
    await col.insert_one({"thread": thread, "role": "manager", "sender": payload['sub'], "text": message, "ts": now})
    reply = await ai_service.generate_text(
        f"You are the digital twin of employee {reportee_id}. A manager says: '{message}'. "
        "Respond briefly in first person as that employee's twin.",
        "You are an employee digital twin. Be realistic and concise.",
    )
    await col.insert_one({"thread": thread, "role": "twin", "sender": reportee_id, "text": reply, "ts": datetime.now(timezone.utc).isoformat()})
    return {"status": "SENT", "reply": reply}

@ai_router.get("/twin/history/{user_id}")
async def get_digital_twin_history(req: Request, user_id: str, payload: Dict = Depends(employee_role_required)):
    """Real conversation history between the caller and a reportee's twin."""
    col = await _twin_messages(req)
    thread = f"{payload['sub']}:{user_id}"
    cursor = col.find({"thread": thread}, {"_id": 0}).sort("ts", 1).limit(200)
    return await cursor.to_list(length=200)

# ======================================
# 13. PII ROUTER (Fixed/Complete)
# ======================================
def _pqc(req: Request) -> PQCEncryptionWrapper:
    pqc = getattr(req.app.state, "pqc_wrapper", None)
    if not pqc:
        raise HTTPException(status_code=503, detail="Encryption service unavailable.")
    return pqc

def _consents(req: Request):
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        raise HTTPException(status_code=503, detail="Consent store unavailable.")
    return mongo_client[settings.MONGO_DB_NAME]["privacy_consents"]

@pii_router.post("/tokenize")
async def tokenize_pii(req: Request, value: str = Body(..., embed=True), payload: Dict=Depends(employee_role_required)):
    """Real reversible token via the AES-256-Fernet wrapper (ciphertext is the token)."""
    ciphertext, metadata = _pqc(req).encrypt(value, data_context="pii_tokenize")
    return {
        "token": ciphertext,
        "value_hash": hashlib.sha256(value.encode("utf-8")).hexdigest()[:16],
        "metadata": metadata,
    }

@pii_router.post("/update_consent")
async def update_user_consent(req: Request, consent_data: Dict, payload: Dict=Depends(employee_role_required)):
    """Upsert a real consent record keyed by (employee_uuid, purpose_id)."""
    employee_uuid = payload.get("employee_uuid")
    if not employee_uuid:
        raise HTTPException(status_code=404, detail="No employee record linked to this account.")
    purpose_id = consent_data.get("purpose_id")
    if not purpose_id:
        raise HTTPException(status_code=400, detail="purpose_id is required.")
    # Accept the field under any of the names callers reasonably use, and REQUIRE
    # one of them. Silently defaulting to False meant the UI could report
    # "consent granted" while the record said the opposite.
    for key in ("granted", "consent_granted", "consent"):
        if key in consent_data:
            granted = bool(consent_data[key])
            break
    else:
        raise HTTPException(status_code=400, detail="A consent decision (granted) is required.")
    await _consents(req).update_one(
        {"employee_uuid": employee_uuid, "purpose_id": purpose_id},
        {"$set": {"granted": granted, "updated_by": payload.get("sub"),
                  "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return {"status": "Consent Updated", "purpose_id": purpose_id, "granted": granted}

@pii_router.post("/unmask")
async def get_unmasked_pii(req: Request, token: str = Body(..., embed=True), reason: str = Body(..., embed=True), payload: Dict=Depends(employee_role_required)):
    """Decrypt a PII token via the AES-256 encryption wrapper. Every access is logged to Mongo
    pii_access_log with the caller-supplied reason. Denies on invalid/empty input."""
    reason = (reason or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="A reason is required to unmask PII.")
    mongo_client = getattr(req.app.state, "mongo_client", None)
    now = datetime.now(timezone.utc).isoformat()
    try:
        plaintext = _pqc(req).decrypt(token, data_context="pii_unmask")
        outcome = "GRANTED"
    except ValueError:
        outcome = "DENIED_INVALID_TOKEN"
        plaintext = None
    if mongo_client:
        await mongo_client[settings.MONGO_DB_NAME]["pii_access_log"].insert_one({
            "actor": payload.get("sub"), "employee_uuid": payload.get("employee_uuid"),
            "reason": reason, "outcome": outcome,
            "token_hash": hashlib.sha256(token.encode("utf-8")).hexdigest()[:16], "accessed_at": now,
        })
    if plaintext is None:
        raise HTTPException(status_code=400, detail="Invalid token; access denied and logged.")
    return {"unmasked_value": plaintext, "reason": reason, "outcome": outcome}

@pii_router.post("/reveal-self")
async def reveal_own_pii(req: Request, reason: str = Body("Employee viewed their own protected fields", embed=True),
                         payload: Dict=Depends(employee_role_required)):
    """Decrypt the caller's OWN protected fields and log the access.

    The generic /pii/unmask endpoint takes a ciphertext token, which a browser
    never has. This is the employee-facing equivalent: it decrypts server-side,
    only ever for the caller's own record, and writes an audit entry.
    """
    employee_uuid = payload.get("employee_uuid")
    if not employee_uuid:
        raise HTTPException(status_code=404, detail="No employee record linked to this account.")

    hr = _hr(req)
    # Only the columns that actually exist on employee_pii.
    query = "SELECT full_name_encrypted, email_encrypted FROM employee_pii WHERE employee_uuid = $1"
    rows = await hr.vault.execute_pii_query(query, "employee_pii", "SelfService", None, employee_uuid)
    if not rows:
        raise HTTPException(status_code=404, detail="No protected fields are held for your record.")

    row = rows[0]
    fields = {
        "Full name": row.get("full_name"),
        "Email": row.get("email"),
    }
    revealed = {k: v for k, v in fields.items() if v}

    mongo_client = getattr(req.app.state, "mongo_client", None)
    if mongo_client:
        await mongo_client[settings.MONGO_DB_NAME]["pii_access_log"].insert_one({
            "actor": payload.get("sub"), "employee_uuid": employee_uuid,
            "reason": (reason or "").strip() or "Self service reveal",
            "outcome": "GRANTED_SELF", "fields": list(revealed.keys()),
            "accessed_at": datetime.now(timezone.utc).isoformat(),
        })

    return {"fields": revealed, "reason": reason, "outcome": "GRANTED"}

@pii_router.get("/check_consent")
async def check_user_consent(req: Request, purpose_id: str = Query(...), payload: Dict=Depends(employee_role_required)):
    """Real consent check. Default DENY (False) when no explicit grant exists."""
    employee_uuid = payload.get("employee_uuid")
    if not employee_uuid:
        raise HTTPException(status_code=404, detail="No employee record linked to this account.")
    record = await _consents(req).find_one({"employee_uuid": employee_uuid, "purpose_id": purpose_id})
    return {"consent": bool(record and record.get("granted", False)), "purpose_id": purpose_id}

# ======================================
# 14. INGESTION ROUTER (Fixed/Complete)
# ======================================
@ingestion_router.post("/upload")
async def upload_ingestion_file(req: Request, file: UploadFile = File(...), payload: Dict=Depends(policy_admin_role_required)):
    """Record a real ingestion job: the document is read, sized, content-hashed and
    persisted so the ingestion queue and history reflect actual uploads."""
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        raise HTTPException(status_code=503, detail="Ingestion store unavailable.")
    contents = await file.read()
    digest = hashlib.sha256(contents).hexdigest()
    doc = {
        # The id used to be derived from the content, so uploading the same file
        # twice produced two rows sharing one id. The history list keys its rows
        # on it, and React collapsed them into one.
        "job_id": f"ING-{uuid.uuid4().hex[:10].upper()}",
        "filename": file.filename,
        "content_type": file.content_type,
        "size_bytes": len(contents),
        "content_sha256": digest,
        "status": "INGESTED",
        "uploaded_by": payload.get("sub"),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }
    # Say plainly when this file has been through before rather than silently
    # recording it a second time.
    previous = await mongo_client[settings.MONGO_DB_NAME]["ingestion_jobs"].count_documents(
        {"content_sha256": digest})
    await mongo_client[settings.MONGO_DB_NAME]["ingestion_jobs"].insert_one(dict(doc))
    return {
        "status": "Ingested",
        **doc,
        "message": (f"{file.filename} was stored." if not previous else
                    f"{file.filename} was stored. The same file has been uploaded "
                    f"{previous} time{'s' if previous != 1 else ''} before."),
    }

@ingestion_router.get("/jobs")
async def list_ingestion_jobs(req: Request, limit: int = Query(20), payload: Dict=Depends(policy_admin_role_required)):
    """Real ingestion history for the status panel."""
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        return {"jobs": [], "pending": 0}
    lim = max(1, min(int(limit or 20), 200))
    col = mongo_client[settings.MONGO_DB_NAME]["ingestion_jobs"]
    jobs = await col.find({}, {"_id": 0}).sort("uploaded_at", -1).limit(lim).to_list(length=lim)
    # Every job is written with status INGESTED and nothing ever changes it, so
    # this count is structurally always zero. The panel presented it as live
    # queue depth, which implied a queue that does not exist: upload is
    # synchronous and there is nothing waiting behind it.
    total = await col.count_documents({})
    return {
        "jobs": jobs,
        "pending": 0,
        "total": total,
        "note": "Files are stored as they arrive, so nothing queues behind them.",
    }

# ======================================
# 15. ANALYTICS ROUTER (Fixed/Complete)
# ======================================
async def _workforce_analytics(req: Request, department: Optional[str] = None) -> Dict[str, Any]:
    """Derives real HR analytics from the live workforce projection (headcount,
    attrition risk, and average performance), optionally scoped to a department."""
    wfm = getattr(req.app.state, "wfm_service", None)
    if not wfm:
        raise HTTPException(status_code=503, detail="WFM Service unavailable.")
    projection = await wfm.get_current_projections(department=department)
    cs = projection.get("current_state", {})
    headcount = int(cs.get("total_employees", 0) or 0)

    # An empty selection is "no data", not a perfectly healthy workforce. This
    # previously computed (1 - 0) and reported 100% retention, 0 risk.
    if headcount == 0:
        return {
            "key_metric": "No data",
            "retention": "No data",
            "attrition_risk": "No data",
            "attrition_band": None,
            "average_performance": "No data",
            "ml_score": "No data",
            "headcount": 0,
            "scope": projection.get("scope", "All departments"),
            "has_data": False,
        }

    risk = float(cs.get("overall_risk_score", 0.0) or 0.0)
    perf = float(cs.get("average_performance_score", 0.0) or 0.0)
    composite = ((1 - risk) * 0.5 + (perf / 5.0) * 0.5) * 100
    # Risk band in words, so the UI does not have to hardcode one.
    band = "High" if risk >= 0.66 else "Medium" if risk >= 0.33 else "Low"
    return {
        "key_metric": f"{round(composite, 1)}%",
        "retention": f"{round((1 - risk) * 100, 1)}%",
        "attrition_risk": f"{round(risk * 10, 1)}/10",
        "attrition_band": band,
        "average_performance": f"{round(perf, 2)}/5",
        "ml_score": f"{round((perf / 5.0) * 100, 1)}%",
        "headcount": headcount,
        "scope": projection.get("scope", "All departments"),
        "has_data": True,
    }

@analytics_router.get("/departments")
async def list_analytics_departments(req: Request, payload: Dict=Depends(manager_role_required)):
    """The real departments available as an analytics filter."""
    wfm = getattr(req.app.state, "wfm_service", None)
    if not wfm:
        raise HTTPException(status_code=503, detail="WFM Service unavailable.")
    return {"departments": await wfm.list_departments()}

@analytics_router.get("/metrics")
async def get_advanced_analytics(req: Request, metric_type: Optional[str] = Query(None), time_window: Optional[str] = Query(None), department: Optional[str] = Query(None), payload: Dict=Depends(manager_role_required)):
    """Real composite workforce-health analytics, scopeable by department."""
    dept = None if department in (None, "", "All", "All departments") else department
    a = await _workforce_analytics(req, department=dept)
    # No hardcoded "up": report the direction the risk band actually implies.
    trend = "down" if a.get("attrition_band") == "High" else "steady" if a.get("attrition_band") == "Medium" else "up"
    return {"metric": "Composite Workforce Health", "value": a["key_metric"], "trend": trend, **a}

@analytics_router.get("/charts")
async def get_analytics_charts(req: Request, department: Optional[str] = Query(None),
                               payload: Dict=Depends(manager_role_required)):
    """Chart series aggregated from the employee record, optionally for one
    department, so the filter above the charts actually reaches them."""
    wfm = getattr(req.app.state, "wfm_service", None)
    if not wfm:
        raise HTTPException(status_code=503, detail="WFM Service unavailable.")
    return await wfm.get_analytics_charts(department=department)

@analytics_router.post("/metrics/aggregate")
async def aggregate_metrics(req: Request, payload_data: Dict, payload: Dict=Depends(manager_role_required)):
    """Real aggregated metrics for the analytics dashboard.

    Honours a department filter, so the dashboard's controls actually change the
    numbers rather than being decorative.
    """
    metric_type = payload_data.get('metric_type', 'default')
    filters = payload_data.get('filters') or {}
    department = filters.get('department') or payload_data.get('department')
    if department in ("All", "All departments", ""):
        department = None

    if metric_type == 'financial_impact':
        # ponytail: headcount-scaled estimate; base salaries are encrypted at rest,
        # so no cleartext payroll aggregate exists without bulk decryption.
        a = await _workforce_analytics(req, department=department)
        return {"metric_type": metric_type, "value": round(a["headcount"] * 8500.0, 2),
                "scope": a["scope"],
                "note": "Estimate based on headcount; compensation is encrypted at rest and is not aggregated."}
    return await _workforce_analytics(req, department=department)


# ======================================
# 16. DAO, COMPLIANCE, SOCIAL, INNOVATION ROUTES (Fixed/Complete)
# ======================================
@dao_router.get("/proposals/active")
async def get_active_proposals(req: Request, payload: Dict = Depends(employee_role_required)):
    """Real active DAO proposals from the Postgres governance ledger."""
    chaincode = getattr(req.app.state, "governance_chaincode", None)
    if not chaincode:
        raise HTTPException(status_code=503, detail="Governance service unavailable.")
    return await chaincode.list_active_proposals()

@dao_router.post("/vote")
async def cast_vote(req: Request, proposal_id: str = Body(...), vote: str = Body(...), voting_power: float = Body(...), payload: Dict = Depends(employee_role_required)):
    """Cast a real, persisted DAO vote through the governance chaincode (Postgres-backed)."""
    chaincode = getattr(req.app.state, "governance_chaincode", None)
    if not chaincode:
        raise HTTPException(status_code=503, detail="Governance service unavailable.")
    try:
        await chaincode.cast_vote({
            "proposal_id": proposal_id,
            "voter_id": payload.get("sub"),
            "vote": vote,
            "token_weight": voting_power,
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "Vote Cast", "proposal_id": proposal_id, "voter_id": payload.get("sub")}

@dao_router.get("/dashboard")
async def get_governance_dashboard_data(req: Request, payload: Dict = Depends(employee_role_required)):
    """Real DAO governance aggregates (matches the frontend contract)."""
    chaincode = getattr(req.app.state, "governance_chaincode", None)
    if not chaincode:
        raise HTTPException(status_code=503, detail="Governance service unavailable.")
    return await chaincode.get_governance_stats(getattr(req.app.state, "mongo_client", None))

@compliance_router.get("/dashboard")
async def get_compliance_dashboard_data(req: Request, payload: Dict = Depends(policy_admin_role_required)):
    """Real compliance aggregates from the policy_audit_log table.
    HRBP owns policy/compliance, so policy_admin (hrbp + hrit_admin) can view."""
    from services.enforcement_engine import get_compliance_overview
    # Pass the policy store so "the live policy set is the newest one" can
    # actually be checked rather than inferred from whether any decision exists.
    return await get_compliance_overview(getattr(req.app.state, "policy_versioning_service", None))

@compliance_router.post("/monitor_feeds")
async def monitor_regulatory_feeds(req: Request, jurisdictions: List[str] = Body(..., embed=True), payload: Dict = Depends(policy_admin_role_required)):
    """Record which jurisdictions are being watched.

    This used to return "Monitoring Started" without storing anything. The
    subscription is now persisted, and the response says plainly whether a live
    feed is attached or only the intent has been recorded.
    """
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        raise HTTPException(status_code=503, detail="Subscription store unavailable.")
    now = datetime.now(timezone.utc).isoformat()
    col = mongo_client[settings.MONGO_DB_NAME]["regulatory_subscriptions"]
    for j in jurisdictions:
        await col.update_one(
            {"jurisdiction": j},
            {"$set": {"jurisdiction": j, "requested_by": payload.get("sub"), "updated_at": now}},
            upsert=True,
        )
    live = bool(getattr(settings, "ENABLE_POLICY_SCRAPING", False))
    return {
        "status": "Subscription recorded",
        "jurisdictions": jurisdictions,
        "live_feed_active": live,
        "note": "The policy scraping agent is running and will apply updates."
                if live else
                "Saved. Updates will be applied once the policy scraping agent is enabled.",
    }

@social_router.get("/feed")
async def get_social_feed(req: Request, payload: Dict = Depends(employee_role_required)):
    """Real, persisted social feed (newest first) from MongoDB."""
    return await social_recognition.list_feed(social_recognition.get_db(req))

@social_router.post("/posts")
async def post_social_post(req: Request, data: Dict, payload: Dict = Depends(employee_role_required)):
    """Persist a new post so it appears on the next feed refresh."""
    try:
        post = await social_recognition.create_post(
            social_recognition.get_db(req),
            user_id=data.get("user_id") or payload.get("sub"),
            user_name=data.get("user_name") or payload.get("sub"),
            content=data.get("content"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "Posted", "post": post}
    
def _social_activities(req: Request):
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        raise HTTPException(status_code=503, detail="Social store unavailable.")
    return mongo_client[settings.MONGO_DB_NAME]["social_activities"]

@social_router.post("/activity")
async def create_activity_site(req: Request, activity_details: Dict, payload: Dict = Depends(employee_role_required)):
    """Persist a new social activity so it appears in the joinable-activities list."""
    activity_id = f"ACT-{random.getrandbits(48):012x}"
    doc = {
        "id": activity_id,
        "title": (activity_details.get("title") or "Untitled Activity").strip(),
        "description": activity_details.get("description", ""),
        "created_by": payload.get("sub"),
        "members": [payload.get("sub")],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await _social_activities(req).insert_one(dict(doc))
    return {"status": "Activity Created", "id": activity_id, "activity": doc}

@social_router.get("/activities")
async def get_joinable_activities(req: Request, payload: Dict = Depends(employee_role_required)):
    """Real joinable activities from Mongo (newest first, empty until created)."""
    cursor = _social_activities(req).find({}, {"_id": 0}).sort("created_at", -1).limit(200)
    return await cursor.to_list(length=200)

@social_router.post("/chat-link")
async def create_private_chat_link(req: Request, details: Dict, payload: Dict = Depends(employee_role_required)):
    """Generate a deterministic private chat link id for a pair of users and persist it."""
    peer = details.get("peer") or details.get("to_user") or details.get("target") or ""
    me = payload.get("sub") or ""
    seed = ":".join(sorted([me, str(peer)]))
    link_id = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if mongo_client:
        await mongo_client[settings.MONGO_DB_NAME]["chat_links"].update_one(
            {"link_id": link_id},
            {"$set": {"link_id": link_id, "participants": sorted([me, str(peer)]),
                      "created_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
    return {"link_id": link_id, "link": f"/collab/chat/{link_id}", "participants": sorted([me, str(peer)])}


def _ideas(req: Request):
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        raise HTTPException(status_code=503, detail="Innovation store unavailable.")
    return mongo_client[settings.MONGO_DB_NAME]["innovation_ideas"]

@innovation_router.get("/ideas")
async def get_innovation_ideas(req: Request, payload: Dict = Depends(employee_role_required)):
    """Real innovation ideas from Mongo, ranked by votes (empty until submitted)."""
    cursor = _ideas(req).find({}, {"_id": 0}).sort("votes", -1).limit(200)
    return await cursor.to_list(length=200)

@innovation_router.post("/ideas")
async def create_innovation_idea(req: Request, payload_data: Dict, payload: Dict = Depends(employee_role_required)):
    """Persist a new innovation idea (so /ideas and voting have real data to act on)."""
    title = (payload_data.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="title is required.")
    idea_id = f"IDEA-{random.getrandbits(48):012x}"
    doc = {
        "id": idea_id, "title": title, "description": payload_data.get("description", ""),
        "submitted_by": payload.get("sub"), "votes": 0, "voters": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await _ideas(req).insert_one(dict(doc))
    return {"status": "Idea Submitted", "id": idea_id, "idea": doc}

@innovation_router.post("/ideas/vote")
async def vote_innovation_idea(req: Request, payload_data: Dict, payload: Dict = Depends(employee_role_required)):
    """Cast a real, deduplicated up-vote (atomic $inc) on an innovation idea."""
    idea_id = payload_data.get("id") or payload_data.get("idea_id")
    if not idea_id:
        raise HTTPException(status_code=400, detail="idea id is required.")
    voter = payload.get("sub")
    result = await _ideas(req).update_one(
        {"id": idea_id, "voters": {"$ne": voter}},
        {"$inc": {"votes": 1}, "$addToSet": {"voters": voter}},
    )
    if result.matched_count == 0:
        existing = await _ideas(req).find_one({"id": idea_id}, {"_id": 0, "votes": 1})
        if not existing:
            raise HTTPException(status_code=404, detail="Idea not found.")
        return {"status": "Already Voted", "id": idea_id, "votes": existing.get("votes", 0)}
    updated = await _ideas(req).find_one({"id": idea_id}, {"_id": 0, "votes": 1})
    return {"status": "Voted", "id": idea_id, "votes": (updated or {}).get("votes", 0)}

# ======================================
# 17. RECOGNITION ROUTES (Dedicated router - Fixes 404)
# ======================================
@recognition_router.post("/star/{user_id}")
async def give_recognition_star(req: Request, user_id: str, reason: str = Body(..., embed=True), payload: Dict = Depends(employee_role_required)):
    """Persist a recognition star; recipient display name resolved from the users store.

    Peer recognition is open to everyone: the Collaboration Hub is in the
    employee sidebar and shows a "Give star" control, which used to 403 for the
    very people it was aimed at. Self-recognition is still rejected.
    """
    try:
        return await social_recognition.give_star(
            social_recognition.get_db(req),
            from_user=payload.get("sub"),
            to_user=user_id,
            reason=reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@recognition_router.get("/leaderboard")
async def get_recognition_leaderboard(req: Request, payload: Dict = Depends(employee_role_required)):
    """Real recognition leaderboard aggregated from persisted stars."""
    return await social_recognition.leaderboard(social_recognition.get_db(req))

# ======================================
# 18. ORCHESTRATOR ROUTES (Fixed/Complete)
# ======================================
@orchestrator_router.get("/dashboard")
async def get_orchestrator_dashboard(req: Request, payload: Dict = Depends(manager_role_required)):
    """Live orchestrator health from real app.state agents + psutil."""
    state = req.app.state
    # Count the agents the orchestrator can actually dispatch to, not app.state
    # attribute names. The old count matched anything ending _agent or _service,
    # so it included plain CRUD services that dispatch nothing, and counted
    # ta_service and talent_acquisition_service twice because they are the same
    # object under two names.
    dispatchable = sorted(ROUTABLE_AGENTS)
    agents = len(dispatchable)
    try:
        cpu = round(psutil.cpu_percent(interval=0.1), 1)
        mem = round(psutil.virtual_memory().percent, 1)
    except Exception:
        cpu, mem = 0.0, 0.0
    publisher = getattr(state, "event_publisher", None)
    nats_up = bool(getattr(getattr(publisher, "nc", None), "is_connected", False)) if publisher else False
    # Health was computed from CPU and memory alone, so it reported GREEN in the
    # same response that said the message bus was down.
    if cpu >= 95 or mem >= 97:
        health, health_reason = "RED", "This machine is out of processor or memory headroom."
    elif cpu >= 85 or mem >= 90:
        health, health_reason = "AMBER", "This machine is running hot."
    elif not nats_up:
        health, health_reason = "AMBER", "The message bus is down, so background agent work is not running."
    elif not agents:
        health, health_reason = "AMBER", "No agents are registered, so nothing can be dispatched."
    else:
        health, health_reason = "GREEN", "Everything is running normally."

    # Both of these used to read the same in-memory `active_twins` dict, which
    # nothing on any live code path ever populates -- so the dashboard showed two
    # separate metrics that were structurally always 0. active_tasks now counts
    # real in-flight orchestrator commands from Mongo; active_twins reports the
    # in-memory registry it actually names, and null when there is no agent.
    dt_agent = getattr(state, "digital_twin_agent", None)
    active_twins = len(getattr(dt_agent, "active_twins", {}) or {}) if dt_agent else None

    active_tasks = None
    mongo_client = getattr(state, "mongo_client", None)
    if mongo_client is not None:
        try:
            active_tasks = await mongo_client[settings.MONGO_DB_NAME]["orchestrator_commands"] \
                .count_documents({"status": {"$nin": ["COMPLETED", "FAILED", "REJECTED"]}})
        except Exception as e:
            logger.warning(f"Orchestrator dashboard: could not count in-flight commands: {e}")

    return {
        "agents": agents,
        "agent_names": dispatchable,
        "active_twins": active_twins,
        "active_tasks": active_tasks,
        "active_tasks_note": ("Orchestrator commands that have not reached a final state."
                              if active_tasks is not None
                              else "The command store could not be read, so in-flight work is unknown."),
        "system_health": health,
        "health_reason": health_reason,
        "message_bus_connected": nats_up,
        "metrics": {"cpu": cpu, "memory": mem},
        "last_update": datetime.now(timezone.utc).isoformat(),
    }

@orchestrator_router.post("/implement-policy")
async def trigger_policy_implementation(req: Request, version_id: str = Body(...), initiator_id: str = Body(...), policy_id: str = Body(...), payload: Dict=Depends(hrit_admin_role_required)):
    """Trigger real policy-workflow deployment via the BPEL agent."""
    bpel_agent: BPELAgent = getattr(req.app.state, "bpel_agent", None)
    if not bpel_agent: raise HTTPException(status_code=503, detail="BPEL Agent unavailable.")
    try:
        result = await bpel_agent.deploy_policy_workflow(version_id, performed_by=payload["sub"])
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if result.get("status") == "FAILED":
        # A deployment that stopped is not a deployment that started.
        raise HTTPException(status_code=409, detail=result.get("message"))
    return result

@orchestrator_router.get("/history/{process_id}")
async def get_process_execution_history(req: Request, process_id: str, payload: Dict=Depends(hrit_admin_role_required)):
    """Every step a deployment actually took, in order.

    This query was correct but had no writer: nothing ever populated process_id
    or step_name, so it returned [] for every id that was ever asked for. The
    BPEL agent records each step as it performs it now.
    """
    try:
        rows = await pg_client.fetch(
            """SELECT step_name, status, audit_trail, updated_at FROM implementation_status
               WHERE process_id = $1 ORDER BY updated_at ASC""",
            process_id,
        )
    except Exception as e:
        logger.warning(f"deployment history query failed: {e}")
        rows = []
    if not rows:
        return {"process_id": process_id, "steps": [],
                "message": "Nothing has been recorded against this deployment."}
    return {
        "process_id": process_id,
        "steps": [{"step": r["step_name"], "status": r["status"],
                   "detail": _audit_detail(r.get("audit_trail")),
                   "updated_at": str(r["updated_at"])}
                  for r in rows],
    }


# ======================================
# 19. COMMAND EXECUTION (SI CORE) (Fixed/Complete)
# ======================================
# The agents the command bar can route work to. One list, so the count shown on
# the orchestrator dashboard and the choices offered to the router cannot drift
# apart. The dashboard used to count app.state attribute names ending in _agent
# or _service instead, which included plain CRUD services that dispatch nothing
# and counted the same object twice under two names.
ROUTABLE_AGENTS = {
    "SyntheticTwinEngine": "models a change to one person before you commit to it",
    "ConfigurationAgent": "builds and configures new agents",
    "WorkforcePlanningService": "works out attrition risk, headcount and workforce projections",
    "AIService": "answers directly using the local model",
}

@command_router.post("/execute")
async def execute_orchestrator_command(req: Request, prompt: str = Body(..., embed=True), user_id: str = Body(..., embed=True), payload: Dict = Depends(hrit_admin_role_required)):
    """
    Unified endpoint for the frontend's natural language command bar (UnifiedCommandBar).
    """
    logger.info(f"Received Orchestrator Command from {user_id}: {prompt}")
    ai_service: AIService = getattr(req.app.state, "ai_service", None)
    if not ai_service: raise HTTPException(status_code=503, detail="AI Service unavailable.")

    # Real intent routing: ask the LLM to pick the responsible agent, then produce a plan.
    routing_prompt = (
        f"Classify this HR operations command and choose exactly one agent from "
        f"[{', '.join(ROUTABLE_AGENTS)}]. "
        f"Command: '{prompt}'. Return strict JSON: {{\"agent\": <name>, \"summary\": <one sentence plan>}}."
    )
    raw = await ai_service.generate_text(routing_prompt, "You are an orchestration planner. Output only JSON.")
    try:
        routed = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
        agent = routed.get("agent", "AIService")
        summary = routed.get("summary", "Command processed.")
    except Exception:
        agent, summary = "AIService", raw.strip()[:400]

    result_id = f"ORCH-{random.getrandbits(32):08x}"
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if mongo_client:
        await mongo_client[settings.MONGO_DB_NAME]["orchestrator_commands"].insert_one({
            "result_id": result_id, "prompt": prompt, "agent": agent, "summary": summary,
            "user_id": user_id, "status": "COMPLETED", "created_at": datetime.now(timezone.utc).isoformat(),
        })
    # This reported "COMPLETED" while only classifying the command: no agent was
    # ever invoked, so an operator was told their instruction had been carried out
    # when nothing had run.
    return {
        "status": "PLANNED",
        "agent": agent,
        "agent_role": ROUTABLE_AGENTS.get(agent, "handled directly"),
        "summary": summary,
        "result_id": result_id,
        "message": (f"This would be handled by the part of HiRo that {ROUTABLE_AGENTS.get(agent, 'answers directly')}. "
                    "Nothing has been carried out yet: open that area to act on it."),
    }

# /history MUST be declared before /status/{result_id}, or the path-param route
# captures "history" as a result_id and this 404s.
@command_router.get("/history")
async def get_command_history(req: Request, limit: int = Query(50), payload: Dict = Depends(employee_role_required)):
    """Recent orchestrator command history for the command console."""
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        return []
    lim = max(1, min(int(limit or 50), 200))
    cursor = mongo_client[settings.MONGO_DB_NAME]["orchestrator_commands"].find(
        {}, {"_id": 0}
    ).sort("created_at", -1).limit(lim)
    return await cursor.to_list(length=lim)

@command_router.get("/status/{result_id}")
async def get_command_status(req: Request, result_id: str, payload: Dict = Depends(employee_role_required)):
    """Real status/result lookup for a previously executed orchestrator command."""
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        raise HTTPException(status_code=503, detail="Command store unavailable.")
    doc = await mongo_client[settings.MONGO_DB_NAME]["orchestrator_commands"].find_one(
        {"result_id": result_id}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Command not found.")
    return doc

# ======================================
# 20. SI INTEGRATION: SIMULATION, REMEDIATION, TELEMETRY (Fixed/Complete)
# ======================================
@simulation_router.post("/run")
async def run_synthetic_simulation(req: Request, data: SimulationRequest, payload: Dict = Depends(manager_role_required)):
    twin_engine: SyntheticTwinEngine = getattr(req.app.state, 'synthetic_twin_engine', None)
    if not twin_engine:
        raise HTTPException(status_code=503, detail="Synthetic Twin Engine unavailable.")

    # Real engine signature: run_simulation(employee_id, adjustments, simulation_type, base_state)
    result = await twin_engine.run_simulation(
        data.employee_id,
        data.synthetic_adjustments,
        data.simulation_type,
    )

    delta = float(result.get("risk_score_delta", 0.0) or 0.0)
    attrition_change = float(result.get("attrition_probability_change", delta) or 0.0)
    recs = result.get("recommendations")
    recommendation = (
        recs[0] if isinstance(recs, list) and recs
        else (recs if isinstance(recs, str) else f"Review the simulated impact for {data.employee_id}.")
    )
    response = {
        "status": "Simulation Complete",
        "employee_id": data.employee_id,
        "simulation_id": result.get("simulation_id"),
        "metrics": {
            "risk_score_delta": round(delta, 3),
            "attrition_probability_change": round(attrition_change, 3),
            "productivity_impact": result.get("productivity_impact"),
            "cost_implication": result.get("cost_implication"),
        },
        "confidence_score": result.get("confidence_score"),
        "prescriptive_recommendation": recommendation,
        "adjustments_applied": result.get("adjustments_applied", data.synthetic_adjustments),
    }

    # Persist the run so /simulation/history returns real past runs.
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if mongo_client:
        await mongo_client[settings.MONGO_DB_NAME]["simulation_runs"].insert_one({
            **response,
            "type": data.simulation_type,
            "run_by": payload.get("sub"),
            "run_at": datetime.now(timezone.utc).isoformat(),
        })
    return response

@simulation_router.get("/history/{employee_id}")
async def get_simulation_history(req: Request, employee_id: str, limit: int = Query(20), payload: Dict = Depends(manager_role_required)):
    """Simulations actually run for this employee. Returns [] when there are none,
    rather than the fabricated row this used to serve for everybody."""
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        return []
    lim = max(1, min(int(limit or 20), 100))
    cursor = mongo_client[settings.MONGO_DB_NAME]["simulation_runs"].find(
        {"employee_id": employee_id}, {"_id": 0}
    ).sort("run_at", -1).limit(lim)
    return await cursor.to_list(length=lim)

@remediation_router.post("/audit-fail")
async def remediate_audit_failure(req: Request, data: RemediationRequest, payload: Dict = Depends(hrit_admin_role_required)):
    remediation_agent: CognitiveRemediationAgent = getattr(req.app.state, 'cognitive_remediation_agent', None)
    if not remediation_agent:
        raise HTTPException(status_code=503, detail="Cognitive Remediation Agent unavailable.")

    remediation_result = await remediation_agent.analyze_and_fix_transaction(
        data.audit_id, data.failed_transaction, data.policy_text
    )
    fix = remediation_result.get("proposed_fix", {})
    return {
        "status": "Remediation Suggested",
        "audit_id": data.audit_id,
        "suggested_fix": {
            "fixed_payload": fix.get("fixed_payload", fix) if isinstance(fix, dict) else fix,
            "reasoning": remediation_result.get("failure_analysis", "Agent analyzed the violation."),
            "confidence_score": remediation_result.get("compliance_score", 0.0),
        },
        "implementation_steps": remediation_result.get("implementation_steps", []),
    }
    
@remediation_router.post("/audit/{audit_id}/auto-resolve")
async def auto_resolve_audit(req: Request, audit_id: str, data: RemediationRequest, payload: Dict = Depends(hrit_admin_role_required)):
    """FIX: Added endpoint for the frontend's autoResolveAudit call."""
    remediation_agent: CognitiveRemediationAgent = getattr(req.app.state, 'cognitive_remediation_agent', None)
    if not remediation_agent:
        raise HTTPException(status_code=503, detail="Cognitive Remediation Agent unavailable.")
    
    remediation_result = await remediation_agent.analyze_and_fix_transaction(
        audit_id, data.failed_transaction, data.policy_text
    )
    fix = remediation_result.get("proposed_fix", {})
    return {
        "status": "Remediation Suggested",
        "audit_id": audit_id,
        "suggested_fix": {
            "fixed_payload": fix.get("fixed_payload", fix) if isinstance(fix, dict) else fix,
            "reasoning": remediation_result.get("failure_analysis", "Agent applied policy alignment logic."),
            "confidence_score": remediation_result.get("compliance_score", 0.0),
        },
        "implementation_steps": remediation_result.get("implementation_steps", []),
    }


@remediation_router.post("/apply-fix/{audit_id}")
async def apply_remediation_fix(req: Request, audit_id: str, fixed_payload: Dict, payload: Dict = Depends(hrit_admin_role_required)):
    """Record an accepted remediation against the audit entry.

    This previously returned "Fix Applied" without writing anything anywhere.
    The decision is now persisted and retrievable.
    """
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        raise HTTPException(status_code=503, detail="Remediation store unavailable.")
    record = {
        "audit_id": audit_id,
        "fixed_payload": fixed_payload,
        "applied_by": payload["sub"],
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "status": "APPLIED",
    }
    await mongo_client[settings.MONGO_DB_NAME]["remediations"].update_one(
        {"audit_id": audit_id}, {"$set": record}, upsert=True
    )
    return {"status": "Fix Applied", **record}

@remediation_router.get("/history/{audit_id}")
async def get_remediation_history(req: Request, audit_id: str, payload: Dict = Depends(hrit_admin_role_required)):
    """Remediations recorded against an audit entry (empty when there are none)."""
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        return []
    cursor = mongo_client[settings.MONGO_DB_NAME]["remediations"].find(
        {"audit_id": audit_id}, {"_id": 0}
    ).sort("applied_at", -1).limit(50)
    return await cursor.to_list(length=50)


@telemetry_router.get("/metrics/live")
async def get_live_metrics(req: Request, payload: Dict = Depends(manager_role_required)):
    cpu = psutil.cpu_percent()
    mem = psutil.virtual_memory().percent
    # This was served as `agent_activity` and charted as "Agent workload, live -
    # how busy the agent layer is". It is the average of processor and memory
    # load, so it read about 50 with the agent layer completely idle and, with
    # memory sitting at 70 percent, could never fall below about 35 whatever the
    # agents were doing. Real per-agent counts are at /telemetry/agents/activity.
    return {
        "cpu_load": cpu,
        "memory_load": mem,
        "machine_load": round((cpu + mem) / 2.0, 1),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

@telemetry_router.get("/agents/activity")
async def get_agents_activity(req: Request, time_window_minutes: int = 60, payload: Dict = Depends(manager_role_required)):
    """Real per-agent event counts from the orchestrator command log (last window)."""
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        return []
    since = (datetime.now(timezone.utc) - timedelta(minutes=max(1, time_window_minutes))).isoformat()
    cursor = mongo_client[settings.MONGO_DB_NAME]["orchestrator_commands"].aggregate([
        {"$match": {"created_at": {"$gte": since}}},
        {"$group": {"_id": "$agent", "events": {"$sum": 1}}},
        {"$sort": {"events": -1}},
    ])
    rows = await cursor.to_list(length=50)
    return [{"agent_id": r["_id"] or "unknown", "events": r["events"]} for r in rows]

# ======================================
# 21. STREAMING & WEBSOCKETS (Fixed/Complete)
# ======================================
@streaming_router.get("/agents/config/stream")
async def stream_agent_configuration(req: Request, nl_prompt: str):
    agent: SelfCorrectingAgent = getattr(req.app.state, 'self_correcting_agent', None)
    if not agent: raise HTTPException(status_code=503, detail="Self-Correcting Agent service unavailable.")
    
    async def event_stream():
        try:
            async for message in agent.generate_and_fix_bpcl(nl_prompt):
                if message == "COMPLETE":
                    yield f"data: {json.dumps({'status': 'completed', 'timestamp': datetime.now(timezone.utc).isoformat(), 'final_code_hash': f'BPCL-{random.getrandbits(16)}' })}\n\n"
                    break
                
                yield f"data: {message}\n\n"
                await asyncio.sleep(0.1) 
        
        except Exception as e:
            logger.error(f"Streaming error in config stream: {e}", exc_info=True)
            yield f"data: {json.dumps({'status': 'error', 'message': f'🚨 Error in agent process: {str(e)}', 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"
            yield "data: DONE\n\n"
            
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@streaming_router.websocket("/ws/live-telemetry")
async def websocket_telemetry(websocket: WebSocket, client_id: str = "dashboard"):
    await websocket.accept()
    
    _ws_manager = websocket_manager
    await _ws_manager.connect(websocket, client_id)
    
    try:
        await websocket.send_json({
            "type": "connection_established",
            "client_id": client_id,
            "message": "Connected to live telemetry",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                if message.get("type") == "subscribe_telemetry":
                    _ws_manager.subscribe_telemetry(client_id)
                    await websocket.send_json({"type": "subscription_confirmed", "channels": ["telemetry"], "timestamp": datetime.now(timezone.utc).isoformat()})
                elif message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                await websocket.send_json({"type": "error", "message": str(e), "timestamp": datetime.now(timezone.utc).isoformat()})
            
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
    finally:
        _ws_manager.disconnect(client_id)
        logger.info(f"Client {client_id} disconnected from telemetry")

# ======================================
# NOTIFICATIONS
# ======================================
@notifications_router.get("")
async def list_notifications(req: Request, limit: int = Query(50), unread_only: bool = Query(False),
                             payload: Dict = Depends(employee_role_required)):
    """What this person has been told, newest first, with the unread count."""
    me = _self_uuid(payload)
    items = await notification_service.list_for(me, limit=limit, unread_only=unread_only)
    return {"notifications": items, "unread": await notification_service.unread_count(me)}


@notifications_router.post("/{notification_id}/read")
async def mark_notification_read(req: Request, notification_id: str,
                                 payload: Dict = Depends(employee_role_required)):
    """Mark one notification read. Scoped to the owner."""
    changed = await notification_service.mark_read(_self_uuid(payload), notification_id)
    return {"marked": changed, "notification_id": notification_id}


@notifications_router.post("/read-all")
async def mark_all_notifications_read(req: Request, payload: Dict = Depends(employee_role_required)):
    """Clear the whole list for this person."""
    return {"marked": await notification_service.mark_read(_self_uuid(payload))}


# ======================================
# FINAL EXPORT (CRITICAL FIX: Ensure all routers are included)
# ======================================
ALL_ROUTERS = [
    # Core Routers
    policy_router, hrsd_router, admin_router, data_router, dev_router,
    hr_router, ess_router, mss_router, wfp_router, ta_router,
    talent_content_router, talent_exp_router, 
    # Infrastructure/SI Routers
    streaming_router, simulation_router, remediation_router, telemetry_router,
    ai_router, ingestion_router, pii_router, analytics_router,
    # Governance/Workflow Routers
    dao_router, compliance_router, social_router, innovation_router, 
    orchestrator_router, command_router,
    # FIX ENDPOINT: Recognition Router
    recognition_router,
    notifications_router,
]

