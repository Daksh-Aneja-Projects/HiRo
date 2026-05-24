# /backend/services/test_timesheet_e2e_flow.py - REPLACEMENT (Test Assertion and Mock Cleanup/Setup)
"""End-to-End Integration Test for Timesheet Submission Flow.
Verifies the submission logic correctly interacts with the Policy Enforcer and the Event Publisher."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
# NOTE: Assuming HRModulesService is defined elsewhere (e.g., in hr_modules.py)
from services.hr_modules import HRModulesService
from services.event_publisher_service import EventPublisherService
# NOTE: Assuming these dependencies are defined and accessible
from services.enforcement_microservice import EnforcementResponse
from services.agent_spec_dsl import TriggerType
from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone, timedelta 
from config.settings import settings 
import json # FIX: Added missing json import

# Mock MongoDB collections
@pytest.fixture
def mock_mongo_client():
    mock_db = MagicMock()
    mock_db.__getitem__.return_value = mock_db
    mock_db.users = AsyncMock()
    mock_db.timesheets = AsyncMock()
    # Mock user context for timesheet submission
    mock_db.users.find_one.return_value = {
        "username": "testuser",
        "manager_id": "manager1",
        "work_location": "US-CA",
        "employment_type": "Full-Time",
        # CRITICAL FIX: Ensure datetime object is returned for robustness
        "hire_date": datetime.now(timezone.utc), 
        "hashed_password": "hashed_pass",
        "employee_id": "EMP-001"
    }
    mock_db.timesheets.insert_one.return_value = AsyncMock(inserted_id="TS-001")
    return mock_db

# Mock Publisher fixture
@pytest.fixture
def mock_publisher():
    # CRITICAL FIX: Use the actual EventPublisherService instance, but mock its methods
    publisher = EventPublisherService(agent_id="TestOrchestrator")
    publisher.publish_event = AsyncMock()
    # Ensure constants are set for assertion safety
    publisher.TOPIC_POLICY_DECISION = "policy.decision"
    publisher.TOPIC_POLICY_VIOLATION = "policy.violation"
    return publisher

# Mock Enforcement Microservice
@pytest.fixture
def mock_enforcer_check():
    # Use patch to mock the actual dependency injection point
    with patch('services.hr_modules.runtime_enforcer') as mock:
        # Mock the entire singleton instance or the relevant method
        mock.execute_dsl_check = AsyncMock()
        yield mock

# Service Fixture
@pytest.fixture
def hr_service(mock_mongo_client, mock_publisher, mock_enforcer_check):
    # CRITICAL FIX: The HRModulesService needs a valid pg_client if it interacts with PG.
    mock_pg_client = MagicMock() 
    
    return HRModulesService(
        mongo_client=mock_mongo_client,
        pg_client=mock_pg_client,
        publisher=mock_publisher
    )

@pytest.mark.asyncio
async def test_timesheet_e2e_approval_path(hr_service, mock_publisher, mock_enforcer_check):
    """Tests the path where timesheet is approved and successfully recorded."""
    
    SUBMITTED_HOURS = 40.0
    
    # 1. Configure Enforcer to PASS
    mock_enforcer_check.execute_dsl_check.return_value = EnforcementResponse(
        decision="PASS",
        reason="No policy violation detected",
        execution_time_ms=1.5,
        audit_id="A-001"
    ).model_dump() 

    # 2. Execute
    result = await hr_service.submit_timesheet("testuser", 
                                             {"week_ending": "2025-12-31", "total_hours": SUBMITTED_HOURS})

    # 3. Assertions
    assert result['status'] == "SUBMITTED"
    assert result['policy_status'] == "PASS"
    
    # CRITICAL ASSERTION: Assert DB commit was called with correct data
    hr_service.mongo_client.timesheets.insert_one.assert_called_once()
    
    # Extract the data passed to insert_one
    inserted_data = hr_service.mongo_client.timesheets.insert_one.call_args[0][0]
    assert inserted_data['employee_id'] == "EMP-001"
    assert inserted_data['total_hours'] == SUBMITTED_HOURS
    assert 'submitted_at' in inserted_data
    
    # Assert Event Published (Policy Decision)
    mock_publisher.publish_event.assert_called()
    
    # CRITICAL FIX: Assert correct topic for policy decision
    mock_publisher.publish_event.assert_any_call(
        mock_publisher.TOPIC_POLICY_DECISION, 
        # CRITICAL FIX: Check for the presence of key fields
        {'decision': 'PASS', 'user_id': 'EMP-001', 'audit_id': 'A-001'},
        key='timesheet'
    )

@pytest.mark.asyncio
async def test_timesheet_e2e_policy_violation_path(hr_service, mock_publisher, mock_enforcer_check):
    """
    Tests the path where policy enforcement fails (e.g., STOP decision).
    Should raise HTTP 403 and publish a violation event, skipping DB commit."""
    
    VIOLATING_HOURS = 80.0
    
    # 1. Configure Enforcer to STOP
    mock_enforcer_check.execute_dsl_check.return_value = EnforcementResponse(
        decision="STOP",
        reason="Exceeded 60h weekly limit",
        execution_time_ms=2.0,
        audit_id="A-002"
    ).model_dump() 
    
    with pytest.raises(HTTPException) as excinfo:
        await hr_service.submit_timesheet("highload_user", 
                                         {"week_ending": "2025-12-31", "total_hours": VIOLATING_HOURS})
        
    # 2. Assert HTTP 403 Forbidden
    assert excinfo.value.status_code == 403
    assert "Timesheet blocked by policy" in excinfo.value.detail
    
    # 3. Assert Policy Violation Event Published
    mock_publisher.publish_event.assert_called_once()
    
    # Find the call that published the violation event
    call_args = mock_publisher.publish_event.call_args_list[0]
    topic = call_args[0][0]
    data = call_args[0][1]

    # Check topic and decision type
    assert topic == mock_publisher.TOPIC_POLICY_VIOLATION
    assert data['decision'] == "STOP"
    assert "A-002" in data['audit_id']
    
    # CRITICAL ASSERTION: Assert DB commit was SKIPPED
    hr_service.mongo_client.timesheets.insert_one.assert_not_called()