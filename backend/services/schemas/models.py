# /backend/services/schemas/models.py - FIXED
# /backend/services/schemas/models.py
"""Pydantic models and schemas - FINAL MERGED VERSION
Combines HRBP features with Core Agent requirements."""
from typing import Optional, List, Dict, Any, Union 
from pydantic import BaseModel, Field, ConfigDict, EmailStr 
from datetime import datetime, timezone 
from enum import Enum

# =============================================================================
# 1. ENUMS & CONSTANTS
# =============================================================================
class UserRole(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    EMPLOYEE = "employee"
    HRIT_ADMIN = "hrit_admin"
    HR = "hr"
    HRBP = "hrbp"

class LeaveType(str, Enum):
    ANNUAL = "annual"
    SICK = "sick"
    PERSONAL = "personal"
    UNPAID = "unpaid"

class TicketStatus(str, Enum):
    NEW = "NEW"
    TRIAGE = "IN_TRIAGE"
    RESOLUTION = "IN_RESOLUTION"
    COMPLIANCE = "COMPLIANCE_REVIEW"
    CLOSED = "CLOSED"
    REJECTED = "REJECTED"
    RESOLVED_BY_AGENT = "RESOLVED_BY_AGENT"

class TicketPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

# =============================================================================
# 2. AUTH & USER MODELS
# =============================================================================
class AuthPayload(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    sub: str
    role: str
    user_id: str # <--- CRITICAL FIX: Added for JWT consistency
    email: str   # <--- CRITICAL FIX: Added for JWT consistency
    exp: Optional[int] = None
    iat: Optional[int] = None

class SanitizedUser(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    username: str
    role: str
    is_active: bool = True
    last_login: Optional[str] = None

class LoginRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    username: str
    password: str

# CRITICAL FIX: Use EmailStr for strong typing (but keep previous fields)
class UserDetails(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    id: Optional[str] = None          # frontend reads user.id (mirrors user_id)
    user_id: Optional[str] = None
    username: str
    email: Optional[EmailStr] = None # FIXED: Use imported EmailStr
    full_name: Optional[str] = None
    role: str
    is_active: bool = True
    created_at: Optional[str] = None

class LoginResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    access_token: str
    token_type: str = "bearer"
    user: UserDetails

class UserCreateRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    username: str
    password: str
    email: Optional[EmailStr] = None # FIXED: Use imported EmailStr
    full_name: Optional[str] = None
    role: str = "employee"
    manager_id: Optional[str] = None

# =============================================================================
# 3. HR, LEAVE & PAYROLL MODELS
# =============================================================================
class LeaveRequestSubmit(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    leave_type: str
    start_date: str # Use string for ISO input from client
    end_date: str # Use string for ISO input from client
    reason: Optional[str] = None
    days: float
    requested_hours: Optional[float] = None

class LeaveRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    employee_id: str
    start_date: datetime
    end_date: datetime
    leave_type: LeaveType
    reason: str
    status: str = "pending"

class PayslipMetadata(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    pay_period: str
    pay_date: str
    file_key: str
    status: str = "uploaded"
    net_pay: Optional[float] = None
    jurisdiction_code: Optional[str] = None

class BulkUploadRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    file_type: str = Field(..., description="e.g., payslip, compensation_letter, user_csv")
    # CRITICAL FIX: Use timezone aware datetime.now(timezone.utc)
    upload_date: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat()) 
    validation_required: bool = True

class CompensationPlan(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    plan_id: str
    employee_id: str
    base_salary: float
    annual_bonus_pct: float
    equity_value: float
    status: str = "pending_hrbp_review"

class TimesheetEntry(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    employee_id: str
    date: datetime
    hours_worked: float
    project_code: str

# =============================================================================
# 4. HRSD TICKET MODELS
# =============================================================================
class HRSDTicket(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    ticket_id: str = Field(..., description="Unique ID for the ticket.")
    employee_id: str = Field(..., description="ID of the affected employee.")
    title: str = Field(..., description="Summary of the request.")
    description: str = Field(..., 
        description="Detailed description of the issue.")
    status: TicketStatus = Field(TicketStatus.NEW, description="Current status.")
    priority: TicketPriority = Field(TicketPriority.MEDIUM, description="Priority level.")
    assigned_agent: Optional[str] = None
    # CRITICAL FIX: Use timezone aware datetime.now(timezone.utc)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc)) 
    resolution_summary: Optional[str] = None
    resolved_at: Optional[datetime] = None

# =============================================================================
# 5. COMMAND & CONTROL MODELS
# =============================================================================
class CommandRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    prompt: str
    context: Optional[Dict[str, Any]] = None

class CommandResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    agent: str
    message: str
    data: Optional[Dict[str, Any]] = None
    verified: bool = False

class FullAgentCommand(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    target_agent: str
    employee_id: Optional[str] = None
    prompt: Optional[str] = None
    data_context: Optional[Dict[str, Any]] = None

class ConfigurationUpdate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    key: str
    value: Any
    applied_by: str

# =============================================================================
# 6. WORKFORCE, TALENT & AI MODELS
# =============================================================================
class WorkforceModelData(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    snapshot_date: str
    department: str
    headcount: int
    attrition_rate: float
    avg_tenure_years: float
    open_positions: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)

class PredictiveModelConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    model_name: str = "default_attrition_model"
    target_variable: str = "attrition_risk"
    features: List[str]
    lookback_period_days: int = 365
    threshold: float = 0.7

class PredictiveModelOutput(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    score: float
    label: Optional[str] = None
    confidence: Optional[float] = None

class XAIExplanation(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    model: str
    prediction_score: float
    human_summary: str
    feature_contributions: List[Dict[str, Any]]
    generated_at: str

class TalentPoolData(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    candidate_id: str
    name: str
    skills: List[str]
    experience_years: float
    current_role: Optional[str] = None
    application_status: str = "new"
    resume_url: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class OffboardingKnowledge(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    employee_id: str
    successor_id: str
    knowledge_documents: List[str] = []
    completion_date: Optional[str] = None

class AIEmbeddingRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    text: str
    model: Optional[str] = "default"

# =============================================================================
# 7. ADVANCED AGENT MODELS
# =============================================================================
class RLFFFeedbackEntry(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    interaction_id: str
    prompt: str
    response: str
    feedback_score: float
    human_correction: Optional[str] = None
    # CRITICAL FIX: Use timezone aware datetime.now(timezone.utc)
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ModelVersionUpdate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    base_model: str
    new_version_tag: str
    training_loss: float
    validation_accuracy: float
    artifact_path: str

class IntegrationTaskModel(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    task_id: str
    target_system: str
    operation: str
    payload: Dict[str, Any]
    status: str = "pending"
    retry_count: int = 0
    # CRITICAL FIX: Use timezone aware datetime.now(timezone.utc)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

class DigitalTwinState(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    twin_id: str
    entity_type: str
    current_metrics: Dict[str, float]
    active_scenarios: List[str] = []
    # CRITICAL FIX: Use timezone aware datetime.now(timezone.utc)
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class SimulationRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    scenario_name: str
    parameters: Dict[str, Any]
    duration_steps: int = 100

class SystemHealthMetric(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    service_name: str
    status: str = "healthy"
    latency_ms: float
    error_rate: float
    cpu_usage: float
    memory_usage: float
    # CRITICAL FIX: Use timezone aware datetime.now(timezone.utc)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UpgradeLog(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    upgrade_id: str
    target_module: str
    change_summary: str
    diff_url: Optional[str] = None
    status: str = "applied"
    # CRITICAL FIX: Use timezone aware datetime.now(timezone.utc)
    applied_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class BPELProcessDefinition(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    process_id: str
    name: str
    xml_definition: str
    variables: Dict[str, str] = {}
    partner_links: List[str] = []
    version: int = 1

class DaoProposal(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    title: str
    description: str
    proposer_id: str
    category: str
    vote_deadline: Optional[str] = None

class DaoVote(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    proposal_id: str
    voter_id: str
    vote: bool