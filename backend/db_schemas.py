# backend/db_schemas.py
"""SQL DDL for the tables init_test_data.py creates and seeds.

Kept separate so the seeding logic reads as workflow, not schema text.
"""

EMPLOYEE_PII_DDL = """
CREATE TABLE IF NOT EXISTS public.employee_pii (
    employee_uuid VARCHAR(50) PRIMARY KEY,
    employee_id_str VARCHAR(50) UNIQUE NOT NULL,
    manager_id VARCHAR(50),
    jurisdiction_code VARCHAR(10),
    full_name_encrypted TEXT,
    email_encrypted TEXT,
    base_salary_encrypted TEXT,
    bonus_target_encrypted TEXT,
    hire_date DATE,
    department VARCHAR(50),
    role VARCHAR(50), 
    job_title VARCHAR(50),
    dtla_risk_score NUMERIC(3, 2),
    tenure_months INTEGER 
);
CREATE TABLE IF NOT EXISTS public.leave_balance (
    employee_uuid VARCHAR(50) PRIMARY KEY REFERENCES public.employee_pii(employee_uuid),
    balance_hours NUMERIC NOT NULL,
    used_hours NUMERIC NOT NULL,
    policy_id VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS public.performance_reviews (
    review_id SERIAL PRIMARY KEY,
    employee_uuid VARCHAR(50) REFERENCES public.employee_pii(employee_uuid),
    overall_rating NUMERIC(2, 1) NOT NULL,
    review_period_end DATE NOT NULL,
    reviewer_id VARCHAR(50)
);

-- Schema matches what multi_agent_hrsd.py._save_ticket actually writes (employee_id
-- lives in the metadata JSONB, not a dedicated column/FK -- see that module for why).
CREATE TABLE IF NOT EXISTS public.hrsd_tickets (
    ticket_id VARCHAR(50) PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status VARCHAR(20) NOT NULL DEFAULT 'NEW',
    assigned_agent VARCHAR(100),
    priority VARCHAR(20) DEFAULT 'MEDIUM',
    subject TEXT,
    description TEXT,
    metadata JSONB
);
CREATE INDEX IF NOT EXISTS idx_hrsd_tickets_status_created_at
    ON public.hrsd_tickets (status, created_at);

-- DAO governance world-state (written by hyperledger_chaincode, read by /dao/* dashboards).
CREATE TABLE IF NOT EXISTS public.dao_proposals (
    proposal_id VARCHAR(64) PRIMARY KEY,
    status VARCHAR(20),
    data JSONB NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Policy decision audit trail (written by enforcement_engine; decision_timestamp kept as TEXT
-- because the writer passes an ISO string). Read/aggregated by /compliance/dashboard.
CREATE TABLE IF NOT EXISTS public.policy_audit_log (
    audit_id VARCHAR(64) PRIMARY KEY,
    decision_timestamp TEXT,
    policy_version VARCHAR(64),
    trigger_type VARCHAR(64),
    decision VARCHAR(20),
    reason TEXT,
    execution_time_ms INTEGER,
    context_json JSONB
);

-- Agent deployment tracking (written by AgentCreationService, read by the
-- orchestrator process-history endpoint). Was referenced but never created.
CREATE TABLE IF NOT EXISTS public.implementation_status (
    task_id VARCHAR(64) PRIMARY KEY,
    project_id VARCHAR(64),
    status VARCHAR(32),
    agent_id VARCHAR(64),
    requester_id VARCHAR(64),
    step_name VARCHAR(128),
    process_id VARCHAR(64),
    audit_trail JSONB,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Compensation change ledger (written by HRModulesService.update_compensation,
-- read by payslip history). Was referenced but never created.
CREATE TABLE IF NOT EXISTS public.comp_history (
    id SERIAL PRIMARY KEY,
    employee_uuid VARCHAR(50),
    new_salary NUMERIC,
    new_grade VARCHAR(50),
    effective_date DATE,
    updated_by VARCHAR(50),
    updated_at TEXT
);

-- Leave requests (written by ESS submit / read by leave history + MSS approvals).
-- Was referenced but never created.
CREATE TABLE IF NOT EXISTS public.leave_requests (
    request_id VARCHAR(50) PRIMARY KEY,
    employee_uuid VARCHAR(50),
    start_date DATE,
    end_date DATE,
    hours NUMERIC,
    status VARCHAR(20),
    submitted_at TEXT,
    -- Written by MSSService.approve_leave when a manager decides.
    approved_by VARCHAR(50),
    decided_at TEXT,
    denial_reason TEXT
);
-- Idempotent upgrade for clusters created before the approval columns existed.
ALTER TABLE public.leave_requests ADD COLUMN IF NOT EXISTS approved_by VARCHAR(50);
ALTER TABLE public.leave_requests ADD COLUMN IF NOT EXISTS decided_at TEXT;
ALTER TABLE public.leave_requests ADD COLUMN IF NOT EXISTS denial_reason TEXT;

-- Indexes for the three filters the live app runs constantly and had no index for:
-- the department rollups behind every workforce chart, the manager_id lookup behind
-- every MSS "my team" view, and the (employee, status) predicate behind leave
-- history and the manager approval queue.
CREATE INDEX IF NOT EXISTS idx_employee_pii_department ON public.employee_pii (department);
CREATE INDEX IF NOT EXISTS idx_employee_pii_manager_id ON public.employee_pii (manager_id);
CREATE INDEX IF NOT EXISTS idx_leave_requests_employee_status
    ON public.leave_requests (employee_uuid, status);

-- Truncate all tables for idempotent re-seeding (clears any prior duplicate keys).
TRUNCATE public.performance_reviews, public.leave_balance, public.hrsd_tickets, public.employee_pii RESTART IDENTITY CASCADE;
TRUNCATE public.dao_proposals, public.policy_audit_log, public.comp_history, public.leave_requests;
"""


RAG_CHUNKS_DDL = """
CREATE TABLE IF NOT EXISTS public.rag_chunks (
    id UUID PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_id TEXT,
    title TEXT,
    chunk_text TEXT,
    embedding FLOAT8[],
    meta JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_source_type ON public.rag_chunks (source_type);
"""


TALENT_INTELLIGENCE_DDL = """
CREATE TABLE IF NOT EXISTS public.succession_nominations (
    id SERIAL PRIMARY KEY,
    role_or_person_uuid VARCHAR(100) NOT NULL,
    nominee_uuid VARCHAR(50) NOT NULL,
    nominated_by VARCHAR(50),
    readiness VARCHAR(20) NOT NULL CHECK (readiness IN ('ready_now','ready_soon','develop')),
    rationale TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_succession_nominations_role
    ON public.succession_nominations (role_or_person_uuid);

CREATE TABLE IF NOT EXISTS public.comp_cycles (
    cycle_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    department VARCHAR(50),
    status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','review','finalized')),
    budget_pct NUMERIC(5,2) NOT NULL,
    created_by VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS public.comp_cycle_lines (
    id SERIAL PRIMARY KEY,
    cycle_id VARCHAR(50) REFERENCES public.comp_cycles(cycle_id),
    employee_uuid VARCHAR(50) NOT NULL,
    current_comp_cents BIGINT NOT NULL,
    proposed_pct NUMERIC(5,2) NOT NULL DEFAULT 0,
    proposed_by VARCHAR(50),
    status VARCHAR(20) NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed','adjusted','applied')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_comp_cycle_lines_cycle ON public.comp_cycle_lines (cycle_id);

CREATE TABLE IF NOT EXISTS public.headcount_plans (
    plan_id VARCHAR(50) PRIMARY KEY,
    department VARCHAR(50) NOT NULL,
    fiscal_label VARCHAR(50) NOT NULL,
    planned_headcount INTEGER NOT NULL,
    created_by VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_headcount_plans_department ON public.headcount_plans (department);
"""


PEOPLE_LIFECYCLE_DDL = """
CREATE TABLE IF NOT EXISTS public.perf_cycles (
    cycle_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    stage VARCHAR(20) NOT NULL DEFAULT 'self_assessment',
    opens_at DATE,
    closes_at DATE,
    created_by VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS public.perf_cycle_entries (
    id SERIAL PRIMARY KEY,
    cycle_id VARCHAR(50) NOT NULL REFERENCES public.perf_cycles(cycle_id),
    employee_uuid VARCHAR(50) NOT NULL REFERENCES public.employee_pii(employee_uuid),
    self_assessment TEXT,
    self_rating NUMERIC(2,1),
    manager_rating NUMERIC(2,1),
    manager_comments TEXT,
    calibrated_rating NUMERIC(2,1),
    signed_off_by_employee BOOLEAN NOT NULL DEFAULT FALSE,
    signed_off_at TIMESTAMPTZ,
    UNIQUE (cycle_id, employee_uuid)
);
CREATE INDEX IF NOT EXISTS idx_perf_cycle_entries_employee ON public.perf_cycle_entries (employee_uuid);
"""


