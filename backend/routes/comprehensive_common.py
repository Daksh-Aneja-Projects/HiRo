# backend/services/comprehensive_routes.py
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

logger = logging.getLogger(__name__)

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
# AI knowledge layer (Task 5): background ticket suggestions + command-bar memory.
from routes.ai_knowledge_routes import spawn_suggested_resolution
from services import agent_memory


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

recognition_router = APIRouter(prefix="/recognition", tags=["Recognition"])
notifications_router = APIRouter(prefix="/notifications", tags=["Notifications"])

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

def _require_admin_service(req: Request) -> AdminService:
    svc = getattr(req.app.state, "admin_service", None)
    if not svc:
        raise HTTPException(status_code=503, detail="Admin service unavailable.")
    return svc

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

def _owner_scope(payload: Dict) -> Optional[str]:
    """Employees are scoped to their own records; manager+ are not."""
    return _self_uuid(payload) if (payload.get("role") or "").lower() == "employee" else None


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

async def _twin_messages(req: Request):
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client: raise HTTPException(status_code=503, detail="Store unavailable.")
    return mongo_client[settings.MONGO_DB_NAME]["twin_messages"]

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
    
def _social_activities(req: Request):
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        raise HTTPException(status_code=503, detail="Social store unavailable.")
    return mongo_client[settings.MONGO_DB_NAME]["social_activities"]


def _ideas(req: Request):
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        raise HTTPException(status_code=503, detail="Innovation store unavailable.")
    return mongo_client[settings.MONGO_DB_NAME]["innovation_ideas"]


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


# ======================================
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
    recognition_router,
    notifications_router,
]

