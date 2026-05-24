# /backend/tests/test_leave_flow.py - FIXED
"""Integration Tests for Leave Request Flow"""
import pytest
from unittest.mock import patch, Mock
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List # CRITICAL FIX: Add missing imports
import asyncio # CRITICAL FIX: Add missing imports

# Import the actual wrapper and helper
# CRITICAL FIX: Import the wrapper function, not the internal implementation
from services.enforcement_engine import execute_dsl_check
from utils.async_helpers import maybe_await 
from services.agent_spec_dsl import TriggerType 
from services.enforcement_microservice import EnforcementResponse # CRITICAL FIX: Import model for denial mock

# Fixture to simulate a Denial response from the synchronous core engine
@pytest.fixture
def mock_denial_engine():
    """Mocks synchronous enforcement engine object to return a DENY result."""
    
    # CRITICAL FIX: Match the expected output of EnforcementResponse.model_dump()
    mock_denial_result = EnforcementResponse(
        decision="STOP",
        rule_id="LEAVE_CAP_001",
        reason="Insufficient leave balance",
        execution_time_ms=3.2,
        audit_id="test-audit-deny",
        xai_trace={}
    ).model_dump()
    
    engine = Mock()
    def mock_execute_dsl_check_deny(trigger, context_data):
        if context_data.get('Proposed') is not None and context_data['Proposed'].get('SubmittedDate') is None:
            context_data['Proposed']['SubmittedDate'] = datetime.now(timezone.utc).isoformat()
        return mock_denial_result
        
    engine.execute_dsl_check = Mock(side_effect=mock_execute_dsl_check_deny)
    return engine

@pytest.mark.asyncio
async def test_leave_request_approve_via_wrapper(mock_enforcement_engine, mock_enforcement_engine_result):
    """Test leave request flow assuming the enforcement engine approves."""
    
    context_data = {
        "employee_id": "test-emp-1",
        "Proposed": {"Hours": 40},
        "UDM": {"Balance": {"Hours": 120}}
    }
    
    # CRITICAL FIX: Patch the module where the original object lives
    with patch('services.enforcement_engine.enforcement_engine', new=mock_enforcement_engine):
        
        # The actual execution goes through the async wrapper
        result = await execute_dsl_check(
            TriggerType.LEAVE_REQUEST_SUBMIT.value, # CRITICAL FIX: Use LEAVE_REQUEST_SUBMIT
            context_data
        )
        
        # Assert result structure and decision
        assert result["decision"] == "APPROVE"
        assert result["reason"] == "Test passed"
        
        # FIX: Assert that the mocked engine was called with the correct trigger
        mock_enforcement_engine.execute_dsl_check.assert_called_once_with(
            TriggerType.LEAVE_REQUEST_SUBMIT.value,
            context_data
        )

@pytest.mark.asyncio
async def test_leave_request_deny_via_wrapper(mock_denial_engine):
    """Test leave request flow assuming the enforcement engine denies (STOPs)."""
    
    context_data = {
        "employee_id": "test-emp-2",
        "Proposed": {"Hours": 200},
        "UDM": {"Balance": {"Hours": 40}}
    }
    
    # Patch the engine import to use our 
    # denial mock for this test
    # CRITICAL FIX: Patch the module where 
    # the original object lives
    with patch('services.enforcement_engine.enforcement_engine', new=mock_denial_engine):
        result = await execute_dsl_check(
            TriggerType.LEAVE_REQUEST_SUBMIT.value, # CRITICAL FIX: Use LEAVE_REQUEST_SUBMIT
            context_data
        )
        
        # Assert denial decision
        assert result["decision"] == "STOP"
        assert "balance" in result["reason"].lower()
        
        # CRITICAL FIX: Replace [REDACTED_JWT] placeholder with mock object method
        mock_denial_engine.execute_dsl_check.assert_called_once()