# /C:/HiRo Project/backend/services/udm_schemas_complete.py
"""Complete Hire-to-Retire UDM Data Schemas
All domains: Talent Acquisition, Workforce Management, Payroll, Performance, Benefits, Offboarding"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass, field 

# --- Configuration Constants ---
DEFAULT_DEPARTMENT = "General"
DEFAULT_JOB_TITLE = "Employee"
DEFAULT_CURRENCY = "USD"
# Default values for tracking
DEFAULT_GOAL_RATING = 3.0
DEFAULT_PROFICIENCY_LEVEL = 3

class EmployeeStatus(str, Enum):
    ACTIVE = "active"
    ON_LEAVE = "on_leave"
    TERMINATED = "terminated"
    SUSPENDED = "suspended"

class EmployeeRole(str, Enum):
    EMPLOYEE = "employee"
    MANAGER = "manager"
    SALES = "sales" 
    ENGINEERING = "engineering"
    HR = "hr"
    FINANCE = "finance"
    OPERATIONS = "operations"

class JurisdictionCode(str, Enum):
    US_CA = "US-CA"
    US_NY = "US-NY"
    FR = "FR"
    DE = "DE"
    UK = "UK"
    IN = "IN"
    SG = "SG"
    AU = "AU"

# --- Requisition Statuses ---
class RequisitionStatus(str, Enum):
    OPEN = "OPEN"
    FILLED = "FILLED"
    CLOSED = "CLOSED"

# --- TimeClock Statuses ---
class TimeClockStatus(str, Enum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    VIOLATION = "VIOLATION"

# ========== CORE EMPLOYEE DATA PRODUCT ==========
class EmployeePIIDataProduct(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    """Universal Employee PII Data Product with Global Attributes"""
    # Global Mandatory Attributes
    employee_uuid: str = Field(..., description="Universal employee identifier")
    legal_entity_id: str = Field(..., description="Legal entity affiliation")
    jurisdiction_code: JurisdictionCode = Field(..., description="Legal jurisdiction")
    policy_affiliation_group: str = Field(..., description="Policy group for rule filtering")
    
    # PII Data (Encrypted)
    full_name_encrypted: str
    email_encrypted: str
    phone_encrypted: Optional[str] = None
    national_id_encrypted: Optional[str] = Field(None, description="SSN/National ID (encrypted)")
    date_of_birth: Optional[str] = None 
    
    # Organizational Context
    manager_id: Optional[str] = None
    role: EmployeeRole = Field(default=EmployeeRole.EMPLOYEE)
    department: str = Field(default=DEFAULT_DEPARTMENT)
    job_title: str = Field(default=DEFAULT_JOB_TITLE)
    hire_date: str
    
    status: EmployeeStatus = Field(default=EmployeeStatus.ACTIVE)
    
    # Security
    quantum_risk_flag: bool = Field(default=True)
    encryption_metadata: str = Field(default="")
    
    # Audit
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ========== TALENT ACQUISITION ==========
class JobRequisitionDataProduct(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    """Job opening and requisition tracking"""
    
    requisition_id: str
    legal_entity_id: str
    jurisdiction_code: JurisdictionCode
    job_title: str
    department: str
    hiring_manager_id: str
    required_skills: List[str] = Field(default_factory=list)
    job_description: str
    salary_range_min: float
    salary_range_max: float
    status: RequisitionStatus = Field(default=RequisitionStatus.OPEN)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class CandidateDataProduct(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    """Candidate tracking through hiring pipeline"""
    candidate_id: str
    requisition_id: str
    full_name: str
    email: str
    phone: str
    resume_text: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    stage: str = Field(default="APPLIED")
    interview_feedback: Optional[str] = None
    offer_amount: Optional[float] = None
    quantum_risk_flag: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ========== WORKFORCE MANAGEMENT (WFM) ==========
class TimeClockDataProduct(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    """Time and attendance tracking"""
    clock_id: str
    employee_uuid: str
    jurisdiction_code: JurisdictionCode
    clock_in_time: datetime
    clock_out_time: Optional[datetime] = None
    gps_lat: Optional[float] = Field(None, description="GPS latitude for compliance") 
    gps_lon: Optional[float] = Field(None, description="GPS longitude for compliance")
    biometric_verified: bool = Field(default=False)
    total_hours: Optional[float] = None
    status: TimeClockStatus = Field(default=TimeClockStatus.IN_PROGRESS)

class LeaveBalanceDataProduct(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    """Leave accrual and balance tracking"""
    employee_uuid: str
    jurisdiction_code: JurisdictionCode
    policy_affiliation_group: str
    accrual_rate: float
    balance_hours: float
    used_hours: float = 0.0
    policy_id: str
    # Jurisdiction-specific caps
    jurisdiction_annual_cap: Optional[float] = None
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class LeaveRequestDataProduct(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    """Leave request submission and approval"""
    request_id: str
    employee_uuid: str
    jurisdiction_code: JurisdictionCode
    requested_hours: float
    start_date: str 
    end_date: str
    leave_type: str = Field(default="VACATION")
    reason: Optional[str] = None
    status: str = Field(default="PENDING")
    denial_reason: Optional[str] = None
    approver_id: Optional[str] = None
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    decided_at: Optional[datetime] = None

# ========== GLOBAL PAYROLL ==========
class CompensationDataProduct(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    """Compensation and salary management"""
    compensation_id: str
    employee_uuid: str
    legal_entity_id: str
    jurisdiction_code: JurisdictionCode
    base_salary: float
    currency: str = Field(default=DEFAULT_CURRENCY)
    pay_frequency: str = Field(default="MONTHLY") 
    # Variable compensation
    bonus_target: Optional[float] = None
    commission_rate: Optional[float] = None
    # Jurisdiction-specific taxes (calculated)
    tax_rate: Optional[float] = None
    effective_date: datetime
    end_date: Optional[datetime] = None

class PayrollRunDataProduct(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    """Payroll execution tracking"""
    payroll_run_id: str
    legal_entity_id: str
    jurisdiction_code: JurisdictionCode
    start_date: str
    pay_period_end: str
    pay_date: str
    total_employees: int
    total_gross_pay: float
    total_net_pay: float
    total_tax_withheld: float
    status: str = Field(default="DRAFT")
    compliance_check_passed: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ========== PERFORMANCE MANAGEMENT ==========
class PerformanceReviewDataProduct(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    """Performance review cycle management"""
    review_id: str
    employee_uuid: str
    reviewer_id: str
    jurisdiction_code: JurisdictionCode
    review_period_start: str
    review_period_end: str
    overall_rating: Optional[float] = Field(
        default=DEFAULT_GOAL_RATING, 
        ge=1,
        le=5,
        description="1-5 rating scale"
    )
    goals_achieved: Optional[int] = None
    goals_total: Optional[int] = None
    manager_feedback: Optional[str] = None
    ai_generated_draft: Optional[str] = Field(None, description="LLM-generated feedback draft")
    status: str = Field(default="IN_PROGRESS")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

class SkillAssessmentDataProduct(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    """Employee skill tracking and assessment""" 
    assessment_id: str
    employee_uuid: str
    skill_name: str
    proficiency_level: int = Field(
        default=DEFAULT_PROFICIENCY_LEVEL,
        ge=1, 
        le=5, 
        description="1-5 proficiency"
    )
    assessed_by: Optional[str] = None
    certification: Optional[str] = None
    assessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ========== BENEFITS & TOTAL REWARDS ==========
class BenefitsEnrollmentDataProduct(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    """Employee benefits enrollment"""
    enrollment_id: str
    employee_uuid: str
    jurisdiction_code: JurisdictionCode
    plan_type: str
    plan_name: str
    coverage_level: str = Field(default="EMPLOYEE_ONLY")
    monthly_cost: float
    employer_contribution: float
    employee_contribution: float
    enrollment_date: datetime
    effective_date: datetime

# ========== HR SERVICE DELIVERY (HRSD) ==========
class HRSDTicketDataProduct(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    """HR service desk ticket tracking"""
    ticket_id: str
    employee_uuid: str
    jurisdiction_code: JurisdictionCode
    category: str
    subject: str
    description: str
    priority: str = Field(default="MEDIUM")
    status: str = Field(default="OPEN")
    assigned_to: Optional[str] = Field(None, description="Agent or HR specialist ID")
    resolution: Optional[str] = None
    ai_suggested_resolution: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None

# ========== PREDICTIVE ANALYTICS ==========
class AttritionRiskDataProduct(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    """AI-powered attrition risk prediction"""
    prediction_id: str
    employee_uuid: str
    risk_score: float = Field(..., ge=0, le=1, description="0-1 attrition probability")
    risk_level: str
    contributing_factors: List[Dict[str, Any]] = Field(default_factory=list)
    xai_trace: Optional[Dict[str, Any]] = None
    predicted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class SkillGapAnalysisDataProduct(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    """Workforce skill gap forecasting"""
    analysis_id: str
    department: str
    jurisdiction_code: JurisdictionCode
    required_skills: List[str]
    current_proficiency: Dict[str, float]
    gap_severity: Dict[str, str]
    recommended_actions: List[str] = Field(default_factory=list)
    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ========== OFFBOARDING ==========
class OffboardingDataProduct(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    """Employee offboarding and exit process"""
    offboarding_id: str
    employee_uuid: str
    legal_entity_id: str
    jurisdiction_code: JurisdictionCode
    termination_date: datetime
    termination_reason: str
    exit_interview_completed: bool = Field(default=False)
    final_pay_processed: bool = Field(default=False)
    checklist_completed: Dict[str, bool] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
