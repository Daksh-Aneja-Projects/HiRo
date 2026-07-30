# backend/init_test_data.py - REPLACEMENT (FINAL DEFINITIVE FIXED PRODUCTION VERSION - TRUNCATE ADDED)
#!/usr/bin/env python3

"""Master data initialization and extensive bulk seeding script for Investor Demo.
CRITICAL FIX: Added TRUNCATE command to the schema creation phase to ensure the 
database is clean and bypasses duplicate key errors from prior failed runs.
"""

import asyncio
import csv
import json
import sys
import logging
import random
import uuid
from pathlib import Path
from datetime import datetime, timezone, timedelta, date
from typing import List, Dict, Any, Tuple

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add backend directory to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

# Import required modules
from services.scripts import seed_employees
from services.auth_service import AuthService
from services.pqc_pii_layer import PQCEncryptionWrapper 
from services.postgres_client import pg_client 
from config.settings import settings 
from motor.motor_asyncio import AsyncIOMotorClient

# --- CONFIGURATION CONSTANTS (Same as before) ---
BULK_EMPLOYEE_COUNT = 20000 
BATCH_SIZE = 5000 
DEPARTMENTS = ["Engineering", "Sales", "HR", "Finance", "Marketing", "R&D", "Operations", "Legal"]
JURISDICTIONS = ["US-CA", "US-NY", "UK-LON", "IN-BLR", "JP-TOK", "AU-SYD"]
JOB_TITLES = ["Senior Engineer", "Sales Rep", "HR Analyst", "Financial Controller", "Product Manager", "Staff Engineer", "VP", "Director"]

# --- PII Data Structure Definition (DDL) ---
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

-- CRITICAL FIX: TRUNCATE ALL TABLES TO ENSURE IDEMPOTENCY AND CLEAR DUPLICATE KEYS
TRUNCATE public.performance_reviews, public.leave_balance, public.hrsd_tickets, public.employee_pii RESTART IDENTITY CASCADE;
TRUNCATE public.dao_proposals, public.policy_audit_log;
"""

# --- CORE DEMO USERS (Logic remains the same, ensures unique ID strings E00001-E00010) ---
def calculate_tenure(hire_date_str: str) -> int:
    """Calculates tenure in months from a hire date string."""
    try:
        hire_date = datetime.strptime(hire_date_str, '%Y-%m-%d')
        tenure_months = (datetime.now() - hire_date).days // 30
        return max(1, tenure_months)
    except:
        return 1

async def get_core_demo_employees():
    ADMIN_UUID = "EMP-001"
    HRIT_MGR_UUID = "EMP-002"
    MANAGER_C_UUID = "EMP-004"
    MANAGER_G_UUID = "EMP-007"
    
    # Core Demo Employee Set
    DEMO_EMPLOYEES = [
        {"id": ADMIN_UUID, "employee_id_str": "E00001", "username": "admin", "name": "System Admin", "email": "admin@hiro.com", "salary": "250000.00", "bonus": "0.20", "role": "hrit_admin", "mgr": None, "hire_date": "2020-01-01", "dept": "IT", "jurisdiction": "GLOBAL", "leave": 200.0, "review": 5.0, "title": "Chief Architect", "risk": 0.10},
        {"id": HRIT_MGR_UUID, "employee_id_str": "E00002", "username": "hritmanager", "name": "Alice HRIT Manager", "email": "hritmanager@hiro.com", "salary": "180000.00", "bonus": "0.15", "role": "hrit_manager", "mgr": ADMIN_UUID, "hire_date": "2021-03-15", "dept": "HRIT", "jurisdiction": "US-CA", "leave": 180.0, "review": 4.5, "title": "VP HRIT", "risk": 0.25},
        {"id": "EMP-003", "employee_id_str": "E00003", "username": "hrbp", "name": "Bob HRBP Lead", "email": "hrbp@hiro.com", "salary": "150000.00", "bonus": "0.10", "role": "hrbp", "mgr": HRIT_MGR_UUID, "hire_date": "2022-06-01", "dept": "HR", "jurisdiction": "US-NY", "leave": 160.0, "review": 4.0, "title": "HR Business Partner", "risk": 0.35},
        {"id": MANAGER_C_UUID, "employee_id_str": "E00004", "username": "manager", "name": "Charlie Manager", "email": "manager@hiro.com", "salary": "120000.00", "bonus": "0.05", "role": "manager", "mgr": "EMP-003", "hire_date": "2023-09-10", "dept": "Engineering", "jurisdiction": "US-CA", "leave": 120.0, "review": 3.5, "title": "Engineering Manager", "risk": 0.40},
        {"id": "EMP-005", "employee_id_str": "E00005", "username": "employee", "name": "Dana Employee", "email": "employee@hiro.com", "salary": "60000.00", "bonus": "0.00", "role": "employee", "mgr": MANAGER_C_UUID, "hire_date": "2024-05-20", "dept": "Sales", "jurisdiction": "US-TX", "leave": 80.0, "review": 3.0, "title": "Sales Associate", "risk": 0.50},
        {"id": "EMP-006", "employee_id_str": "E00006", "username": "evan_hr", "name": "Evan HighRisk", "email": "evan.hr@hiro.com", "salary": "65000.00", "bonus": "0.02", "role": "employee", "mgr": MANAGER_C_UUID, "hire_date": "2023-11-01", "dept": "Marketing", "jurisdiction": "US-TX", "leave": 100.0, "review": 4.8, "title": "Marketing Analyst", "risk": 0.95},
        {"id": MANAGER_G_UUID, "employee_id_str": "E00007", "username": "gita_mgr", "name": "Gita Manager (UK)", "email": "gita.mgr@hiro.com", "salary": "140000.00", "bonus": "0.10", "role": "manager", "mgr": "EMP-003", "hire_date": "2022-04-15", "dept": "Operations", "jurisdiction": "UK-LON", "leave": 20.0, "review": 4.2, "title": "Operations Lead", "risk": 0.30},
        {"id": "EMP-008", "employee_id_str": "E00008", "username": "henry_pqc", "name": "Henry PQC Test", "email": "henry.pqc@hiro.com", "salary": "300000.00", "bonus": "0.50", "role": "employee", "mgr": MANAGER_G_UUID, "hire_date": "2021-07-25", "dept": "Executive", "jurisdiction": "US-CA", "leave": 180.0, "review": 5.0, "title": "CTO", "risk": 0.15},
        {"id": "EMP-009", "employee_id_str": "E00009", "username": "ivy_new", "name": "Ivy NewHire", "email": "ivy.newhire@hiro.com", "salary": "75000.00", "bonus": "0.00", "role": "employee", "mgr": MANAGER_G_UUID, "hire_date": "2025-11-15", "dept": "R&D", "jurisdiction": "UK-LON", "leave": 10.0, "review": 3.0, "title": "Research Assistant", "risk": 0.55},
        {"id": "EMP-010", "employee_id_str": "E00010", "username": "jake_hrsd", "name": "Jake HRSD", "email": "jake.hrsd@hiro.com", "salary": "85000.00", "bonus": "0.05", "role": "employee", "mgr": MANAGER_C_UUID, "hire_date": "2023-01-01", "dept": "Support", "jurisdiction": "US-TX", "leave": 120.0, "review": 3.7, "title": "Customer Support", "risk": 0.60},
    ]

    for emp in DEMO_EMPLOYEES:
        emp['tenure'] = calculate_tenure(emp['hire_date'])

    return DEMO_EMPLOYEES

# --- BULK DATA GENERATION AND SEEDING ---
async def generate_large_dataset_and_seed_pii(pqc_wrapper: PQCEncryptionWrapper, total_count: int):
    logger.info(f"Generating and encrypting {total_count:,} synthetic employee records...")
    
    all_employees = []
    core_users = await get_core_demo_employees() 
    all_employees.extend(core_users)
    
    manager_uuids = [u['id'] for u in core_users if u['role'] in ('manager', 'hrit_manager', 'hrit_admin', 'hrbp')]
    
    # 2. Generate Synthetic Bulk Data
    synthetic_start_index = len(core_users) + 1 # Starts at 11
    
    for i in range(synthetic_start_index, total_count + 1):
        employee_uuid = f"SYN-{uuid.uuid4().hex[:10].upper()}"
        employee_id_str = f"E{i:05d}" # Generates E00011, E00012, etc.
        
        dept = random.choice(DEPARTMENTS)
        jurisdiction = random.choice(JURISDICTIONS)
        role = random.choice(['employee', 'employee', 'employee', 'manager'])
        
        base_salary = round(random.uniform(50000, 200000), 2)
        bonus_target = round(random.uniform(0.00, 0.30), 2)
        
        hire_date_obj = datetime.now() - timedelta(days=random.randint(30, 1800))
        hire_date_str = hire_date_obj.strftime('%Y-%m-%d')
        tenure_months = calculate_tenure(hire_date_str)
        
        dtla_risk_score = round(random.uniform(0.10, 0.99), 2)
        manager_uuid = random.choice(manager_uuids)

        all_employees.append({
            "id": employee_uuid,
            "employee_id_str": employee_id_str, # Unique ID string
            "username": employee_id_str,
            "name": f"Synthetic Employee {i:05d}",
            "email": f"synthetic.{employee_id_str}@hiro.com",
            "salary": str(base_salary),
            "bonus": str(bonus_target),
            "role": role,
            "mgr": manager_uuid,
            "hire_date": hire_date_str,
            "dept": dept,
            "jurisdiction": jurisdiction,
            "leave": round(random.uniform(0, 200), 2),
            "review": round(random.uniform(2.5, 5.0), 1),
            "title": random.choice(JOB_TITLES),
            "risk": dtla_risk_score,
            "tenure": tenure_months 
        })

    logger.info(f"Generated {len(all_employees):,} records. Starting encryption and batch insert...")

    # 3. Encrypt and Prepare Records for Bulk Insert
    pii_records_to_insert = []
    leave_records_to_insert = []
    performance_records_to_insert = []
    
    for emp in all_employees:
        # Encryption
        encrypted_name, _ = pqc_wrapper.encrypt(emp['name'], data_context=f"PII_NAME_{emp['id']}")
        encrypted_email, _ = pqc_wrapper.encrypt(emp['email'], data_context=f"PII_EMAIL_{emp['id']}")
        encrypted_salary, _ = pqc_wrapper.encrypt(emp['salary'], data_context=f"PII_SALARY_{emp['id']}")
        encrypted_bonus, _ = pqc_wrapper.encrypt(emp['bonus'], data_context=f"PII_BONUS_{emp['id']}")

        # --- PII Record Preparation (Date Fixes applied) ---
        hire_date_obj = datetime.strptime(emp['hire_date'], '%Y-%m-%d').date()

        pii_records_to_insert.append((
            emp['id'], emp['employee_id_str'], emp['mgr'], emp['jurisdiction'], encrypted_name, encrypted_email,
            encrypted_salary, encrypted_bonus, hire_date_obj, emp['dept'], emp['role'], 
            emp['title'], emp['risk'], emp['tenure'] 
        ))
        
        leave_records_to_insert.append((
            emp['id'], emp['leave'], 0.0, f"LEAVE_POLICY_{emp['jurisdiction']}"
        ))

        # --- Performance Review Record Preparation (Date Fixes applied) ---
        review_date_str = (datetime.now() - timedelta(days=random.randint(90, 365))).strftime('%Y-%m-%d')
        review_date_obj = datetime.strptime(review_date_str, '%Y-%m-%d').date() 

        performance_records_to_insert.append((
            emp['id'], 
            emp['review'], 
            review_date_obj,
            core_users[0]['id']
        ))
    
    # 4. Bulk Insert Operations 
    pii_insert_query = """
        INSERT INTO public.employee_pii (
            employee_uuid, employee_id_str, manager_id, jurisdiction_code, full_name_encrypted, 
            email_encrypted, base_salary_encrypted, bonus_target_encrypted, hire_date, department, 
            role, job_title, dtla_risk_score, tenure_months
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
        ON CONFLICT (employee_uuid) DO UPDATE SET full_name_encrypted = EXCLUDED.full_name_encrypted;
    """
    leave_insert_query = """
        INSERT INTO public.leave_balance (employee_uuid, balance_hours, used_hours, policy_id)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (employee_uuid) DO UPDATE SET balance_hours = EXCLUDED.balance_hours;
    """
    performance_insert_query = """
        INSERT INTO public.performance_reviews (employee_uuid, overall_rating, review_period_end, reviewer_id)
        VALUES ($1, $2, $3, $4);
    """

    async with pg_client.transaction("InitScript", "bulk_insert"):
        logger.info(f"Starting bulk insert of {len(pii_records_to_insert):,} PII records...")
        await pg_client.executemany_async(pii_insert_query, pii_records_to_insert, batch_size=BATCH_SIZE)
        logger.info(" ✅ PII Bulk Insert complete.")

        logger.info(f"Starting bulk insert of {len(leave_records_to_insert):,} Leave Balance records...")
        await pg_client.executemany_async(leave_insert_query, leave_records_to_insert, batch_size=BATCH_SIZE)
        logger.info(" ✅ Leave Balance Bulk Insert complete.")

        logger.info(f"Starting bulk insert of {len(performance_records_to_insert):,} Performance Review records...")
        await pg_client.executemany_async(performance_insert_query, performance_records_to_insert, batch_size=BATCH_SIZE)
        logger.info(" ✅ Performance Reviews Bulk Insert complete.")

    return all_employees

# --- GOVERNANCE + COMPLIANCE SEEDING ---
async def seed_governance_and_audit():
    """Seeds realistic DAO proposals and policy-audit decisions so the governance and
    compliance dashboards show meaningful, non-trivial live data (idempotent UPSERTs)."""
    import json as _json

    now = datetime.now(timezone.utc)
    proposals = [
        ("Flexible Remote-Work Policy", "VOTING", 6200.0, 1400.0, 41),
        ("Q3 Parental-Leave Expansion", "VOTING", 3100.0, 900.0, 18),
        ("Pay-Transparency Framework", "VOTING", 5400.0, 5100.0, 63),
        ("AI-Assisted Performance Reviews", "APPROVED", 8200.0, 1200.0, 77),
        ("Four-Day Work-Week Pilot", "EXPIRED", 2100.0, 4400.0, 55),
    ]
    prop_rows = []
    for i, (title, status, vfor, vagainst, n_voters) in enumerate(proposals):
        pid = f"PROP_SEED{i:03d}"
        deadline = (now + timedelta(hours=48 if status == "VOTING" else -24)).isoformat()
        data = {
            "proposal_id": pid, "proposer": "HRBP_LEAD",
            "rule_content": {"title": title},
            "status": status, "votes_for": vfor, "votes_against": vagainst,
            "total_votes": vfor + vagainst,
            "voters": [f"V{j:04d}" for j in range(n_voters)],
            "deadline": deadline, "executed": status == "APPROVED",
        }
        prop_rows.append((pid, status, _json.dumps(data)))

    await pg_client.executemany_async(
        """INSERT INTO public.dao_proposals (proposal_id, status, data, updated_at)
           VALUES ($1, $2, $3::jsonb, NOW())
           ON CONFLICT (proposal_id) DO UPDATE SET status = EXCLUDED.status, data = EXCLUDED.data, updated_at = NOW()""",
        prop_rows,
    )

    # ~60 policy decisions over the last 30 days, ~18% DENY (a realistic violation rate).
    triggers = ["LEAVE_APPROVAL", "COMP_CHANGE", "DATA_ACCESS", "POLICY_EXCEPTION", "TERMINATION"]
    audit_rows = []
    for i in range(60):
        deny = random.random() < 0.18
        ts = (now - timedelta(hours=random.randint(0, 30 * 24))).isoformat()
        audit_rows.append((
            f"AUD_SEED{i:04d}", ts, "policy-v2.4", random.choice(triggers),
            "DENY" if deny else "ALLOW",
            "Violates jurisdiction ceiling" if deny else "Within policy bounds",
            random.randint(2, 40),
            _json.dumps({"decision": "DENY" if deny else "ALLOW", "seed": True}),
        ))
    await pg_client.executemany_async(
        """INSERT INTO public.policy_audit_log
             (audit_id, decision_timestamp, policy_version, trigger_type, decision, reason, execution_time_ms, context_json)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
           ON CONFLICT (audit_id) DO NOTHING""",
        audit_rows,
    )
    logger.info(f" ✅ Seeded {len(prop_rows)} DAO proposals and {len(audit_rows)} policy-audit decisions.")


# --- EXTERNAL DATASET SEEDING (verified, license-clear public datasets) ---
# Staged locally under backend/data/external/ (gitignored, never committed).
EXTERNAL_DATA_DIR = Path(__file__).parent / "data" / "external"

# IBM HR Analytics Employee Attrition & Performance (CC0 public domain).
# Source: https://www.kaggle.com/datasets/yasserh/ibm-attrition-dataset
IBM_HR_CSV = EXTERNAL_DATA_DIR / "ibm_hr_attrition.csv"

# UCI Incident Management Process Enriched Event Log (CC BY 4.0).
# Source: https://archive.ics.uci.edu/dataset/498/incident+management+process+enriched+event+log
UCI_INCIDENT_CSV = EXTERNAL_DATA_DIR / "incident_event_log.csv"

HR_TOPICS = [
    "Leave Request", "Payroll Discrepancy", "Benefits Enrollment", "Onboarding Access",
    "Compensation Review", "Performance Feedback", "Workplace Accommodation",
    "IT Access Request", "Policy Clarification", "Timesheet Correction",
]


async def seed_ibm_hr_dataset(pqc_wrapper: PQCEncryptionWrapper):
    """Seeds real employee records from the IBM HR Attrition dataset (CC0), alongside
    the synthetic bulk data, so attrition/performance/comp views reflect a real-world
    distribution rather than only generated numbers."""
    if not IBM_HR_CSV.exists():
        logger.info(f"IBM HR dataset not staged at {IBM_HR_CSV}, skipping (optional).")
        return

    with open(IBM_HR_CSV, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    pii_rows, leave_rows, perf_rows = [], [], []
    for row in rows:
        emp_num = row["EmployeeNumber"]
        uid = f"IBM-{emp_num}"
        years_at_company = int(row.get("YearsAtCompany") or 0)
        hire_date = (datetime.now() - timedelta(days=years_at_company * 365)).date()
        monthly_income = float(row.get("MonthlyIncome") or 0)
        attrition = row.get("Attrition") == "Yes"
        job_satisfaction = int(row.get("JobSatisfaction") or 3)
        # Real dataset has no attrition probability score; derive one consistent with
        # HiRo's own risk scale (0-1) from the actual attrition label + satisfaction.
        risk = (0.65 if attrition else 0.15) + (1 - job_satisfaction / 4.0) * 0.25
        risk = round(min(1.0, max(0.0, risk)), 2)

        name_enc, _ = pqc_wrapper.encrypt(f"IBM Dataset Employee {emp_num}", data_context=f"PII_NAME_{uid}")
        email_enc, _ = pqc_wrapper.encrypt(f"ibm.{emp_num}@hiro.com", data_context=f"PII_EMAIL_{uid}")
        salary_enc, _ = pqc_wrapper.encrypt(str(round(monthly_income * 12, 2)), data_context=f"PII_SALARY_{uid}")
        bonus_enc, _ = pqc_wrapper.encrypt(str(round(float(row.get("PercentSalaryHike") or 0) / 100, 2)), data_context=f"PII_BONUS_{uid}")

        pii_rows.append((
            uid, uid, None, random.choice(JURISDICTIONS), name_enc, email_enc,
            salary_enc, bonus_enc, hire_date, row.get("Department") or "Unknown",
            "employee", row.get("JobRole") or "Employee", risk, max(1, years_at_company * 12),
        ))
        leave_rows.append((uid, round(random.uniform(0, 200), 2), 0.0, "LEAVE_POLICY_DEFAULT"))
        perf_rows.append((
            uid, float(row.get("PerformanceRating") or 3.0),
            (datetime.now() - timedelta(days=random.randint(30, 300))).date(), "EMP-001",
        ))

    async with pg_client.transaction("InitScript", "ibm_hr_seed"):
        await pg_client.executemany_async(
            """INSERT INTO public.employee_pii (
                   employee_uuid, employee_id_str, manager_id, jurisdiction_code, full_name_encrypted,
                   email_encrypted, base_salary_encrypted, bonus_target_encrypted, hire_date, department,
                   role, job_title, dtla_risk_score, tenure_months)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
               ON CONFLICT (employee_uuid) DO UPDATE SET full_name_encrypted = EXCLUDED.full_name_encrypted""",
            pii_rows,
        )
        await pg_client.executemany_async(
            """INSERT INTO public.leave_balance (employee_uuid, balance_hours, used_hours, policy_id)
               VALUES ($1,$2,$3,$4) ON CONFLICT (employee_uuid) DO UPDATE SET balance_hours = EXCLUDED.balance_hours""",
            leave_rows,
        )
        await pg_client.executemany_async(
            """INSERT INTO public.performance_reviews (employee_uuid, overall_rating, review_period_end, reviewer_id)
               VALUES ($1,$2,$3,$4)""",
            perf_rows,
        )
    logger.info(f" ✅ Seeded {len(pii_rows):,} real employees from the IBM HR Attrition dataset (CC0).")


async def seed_uci_incident_tickets(limit: int = 800):
    """Seeds hrsd_tickets from the UCI Incident Management event log (CC BY 4.0).

    The log is an anonymized real IT-service-desk event stream (one row per state
    change); categories are already anonymized numeric codes with no HR meaning, so
    they're relabeled to HR topics for demo realism while the real volume, priority
    mix, and resolution timing are preserved as-is.
    """
    if not UCI_INCIDENT_CSV.exists():
        logger.info(f"UCI incident dataset not staged at {UCI_INCIDENT_CSV}, skipping (optional).")
        return

    status_map = {
        "New": "NEW", "Active": "IN_TRIAGE", "Awaiting User Info": "IN_TRIAGE",
        "Awaiting Vendor": "IN_TRIAGE", "Awaiting Problem": "IN_TRIAGE",
        "Awaiting Evidence": "IN_TRIAGE", "Resolved": "IN_RESOLUTION", "Closed": "CLOSED",
    }
    priority_map = {"1": "CRITICAL", "2": "HIGH", "3": "MEDIUM", "4": "LOW"}

    def parse_dt(s: str):
        try:
            return datetime.strptime(s.strip(), "%d/%m/%Y %H:%M").replace(tzinfo=timezone.utc)
        except (ValueError, AttributeError):
            return None

    # The log is one row per state change, and every incident's LAST row is always
    # "Closed" (it's a fully historical archive) -- sampling that would make every
    # seeded ticket look resolved. Reservoir-sample ONE random event per incident
    # instead, so the seeded statuses/priorities keep their natural, live-looking mix.
    picked: Dict[str, Dict[str, Any]] = {}
    seen_count: Dict[str, int] = {}
    with open(UCI_INCIDENT_CSV, encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            num = row.get("number")
            if not num:
                continue
            seen_count[num] = seen_count.get(num, 0) + 1
            if num not in picked or random.random() < 1.0 / seen_count[num]:
                picked[num] = row

    sampled_numbers = random.sample(list(picked.keys()), min(limit, len(picked)))
    rows = []
    for num in sampled_numbers:
        row = picked[num]
        topic = HR_TOPICS[hash(row.get("category", "")) % len(HR_TOPICS)]
        created = parse_dt(row.get("opened_at", "")) or datetime.now(timezone.utc)
        priority = priority_map.get((row.get("priority") or "").split(" - ")[0], "MEDIUM")
        status = status_map.get(row.get("incident_state"), "NEW")
        group = (row.get("assignment_group") or "").replace("Group ", "HR_Team_") or None
        meta = {"employee_id": None, "resolution_summary": None, "resolved_at": None,
                "source": "uci_incident_log", "original_ticket": num}
        rows.append((
            f"UCI-{num}", created, status, group, priority,
            f"{topic} ({num})", f"Auto-imported from a real service-desk log, relabeled as {topic.lower()}.",
            json.dumps(meta),
        ))

    await pg_client.executemany_async(
        """INSERT INTO public.hrsd_tickets (ticket_id, created_at, status, assigned_agent, priority, subject, description, metadata)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb)
           ON CONFLICT (ticket_id) DO NOTHING""",
        rows,
    )
    logger.info(f" ✅ Seeded {len(rows):,} HRSD tickets from the UCI incident-log dataset (CC BY 4.0).")


# --- MAIN EXECUTION LOGIC ---
async def initialize_data_and_users():
    logger.info("Initializing Postgres schema and extensive test data.")
    
    # 1. PQC Key Initialization
    pqc_wrapper = PQCEncryptionWrapper.get_instance()
    await pqc_wrapper.initialize_keys()
    
    # 2. Schema Creation (NOW INCLUDES TRUNCATE)
    try:
        await pg_client.connect(settings.postgres_url())
        async with pg_client.transaction("InitScript", "schema_creation") as conn:
            logger.info("Ensuring CORE UDM Schemas exist and cleaning old data...")
            await conn.execute(EMPLOYEE_PII_DDL)
            
    except Exception as e:
        logger.critical(f" ❌ Postgres schema creation failed: {e}")
        sys.exit(1)

    # 3. Bulk Data Generation and Seeding
    try:
        all_seeded_employees = await generate_large_dataset_and_seed_pii(pqc_wrapper, BULK_EMPLOYEE_COUNT)
        logger.info(f" ✅ Total {len(all_seeded_employees):,} employee records are now LIVE in the UDM.")
        
    except Exception as e:
        logger.critical(f" ❌ Postgres bulk data seeding failed: {e}")
        sys.exit(1)
        
    # 4. Initialize MongoDB Test Users 
    logger.info("Initializing MongoDB test users.")
    try:
        mongo_client = AsyncIOMotorClient(settings.mongo_url())
        auth_service = AuthService(mongo_client)
        
        core_demo_employees = await get_core_demo_employees()
        
        mongo_users = [{"username": u['username'], "role": u['role'], "employee_id_str": u['employee_id_str']} for u in core_demo_employees]
        
        if hasattr(auth_service, 'initialize_extended_test_users'):
            await auth_service.initialize_extended_test_users(mongo_users)
        else:
            await auth_service.initialize_test_users()
            logger.warning("Using fallback user creation: additional 5 users must be manually ensured in AuthService.")
        
        logger.info(f" ✅ MongoDB {len(mongo_users):,} core test users initialized successfully.")
        
    except Exception as e:
        logger.critical(f" ❌ MongoDB user initialization failed: {e}")
        sys.exit(1)

    # 5. Seed HRSD Tickets 
    try:
        database_url = settings.postgres_url() 
        logger.info("Running HRSD ticket seeder (for core users only)...")
        await seed_employees.run_seeder(database_url, seed_example_rows=True)
        logger.info(" ✅ HRSD ticket seeding complete.")
    except Exception as e:
        logger.warning(f" ⚠️ HRSD ticket seeding failed (non-critical): {e}")

    # 6. Seed DAO governance + policy-audit decisions
    try:
        logger.info("Seeding DAO governance proposals and policy-audit decisions...")
        await seed_governance_and_audit()
    except Exception as e:
        logger.warning(f" ⚠️ Governance/audit seeding failed (non-critical): {e}")

    # 7. Seed real external datasets (optional - only if staged under data/external/)
    try:
        await seed_ibm_hr_dataset(pqc_wrapper)
    except Exception as e:
        logger.warning(f" ⚠️ IBM HR dataset seeding failed (non-critical): {e}")
    try:
        await seed_uci_incident_tickets()
    except Exception as e:
        logger.warning(f" ⚠️ UCI incident-log seeding failed (non-critical): {e}")

    # 8. Seed social feed + recognition leaderboard (MongoDB, references the demo users)
    try:
        from services import social_recognition
        n_posts, n_stars = await social_recognition.seed(
            mongo_client[settings.MONGO_DB_NAME], core_demo_employees
        )
        logger.info(f" ✅ Seeded {n_posts} social posts and {n_stars} recognition stars.")
    except Exception as e:
        logger.warning(f" ⚠️ Social/recognition seeding failed (non-critical): {e}")


if __name__ == "__main__":
    from dotenv import load_dotenv
    from pathlib import Path
    
    load_dotenv(Path(__file__).parent.parent.parent / ".env")
    
    try:
        random.seed(42) 
        asyncio.run(initialize_data_and_users())
    except Exception as e:
        logger.critical(f"FATAL INITIALIZATION ERROR: {e}")
        sys.exit(1)
