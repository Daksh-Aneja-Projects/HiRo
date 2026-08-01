# /backend/tests/test_leave_flow.py
"""Policy-engine tests for the leave-request check, against the REAL engine.

The previous version of this file mocked the engine and then asserted the
mock's own return value: it tested nothing, and its mocks returned a dict
where the real engine returns a (response, audit) tuple, so every run just
exercised the wrapper's fail-safe. These tests load the real
EnforcementMicroservice with its real rules and assert real decisions.
"""
import asyncio
from unittest.mock import patch

from services.enforcement_engine import execute_dsl_check
from services.enforcement_microservice import enforcement_engine
from services.agent_spec_dsl import TriggerType


def test_over_cap_leave_request_is_denied_by_the_real_rule():
    context = {
        "employee_id": "test-emp-2",
        "Proposed": {"Hours": 200},
        "UDM": {"Balance": {"Hours": 40}},
    }
    result = asyncio.run(execute_dsl_check(TriggerType.LEAVE_REQUEST_SUBMIT.value, context))
    assert result["decision"] == "DENY"
    assert result["rule_id"] == "policy_leave_cap_check"
    assert "160" in result["reason"]
    # The decision must carry a real evaluation trace, not an empty shell.
    assert result["xai_trace"].get("rules_evaluated")


def test_within_cap_leave_request_is_approved_after_real_evaluation():
    context = {
        "employee_id": "test-emp-1",
        "Proposed": {"Hours": 40},
        "UDM": {"Balance": {"Hours": 120}},
    }
    result = asyncio.run(execute_dsl_check(TriggerType.LEAVE_REQUEST_SUBMIT.value, context))
    assert result["decision"] == "APPROVE"
    # Approval must state how many rules were actually evaluated, and the
    # trace must show at least one applicable rule was really consulted.
    evaluated = result["xai_trace"].get("rules_evaluated") or []
    assert any(r["rule_id"] == "policy_leave_cap_check" for r in evaluated)


def test_sync_engine_returns_the_tuple_contract_the_wrapper_relies_on():
    response, audit = enforcement_engine.execute_dsl_check(
        TriggerType.LEAVE_REQUEST_SUBMIT.value,
        {"Proposed": {"Hours": 10}},
    )
    assert response.decision in ("APPROVE", "DENY")
    assert audit["audit_id"] == response.audit_id


def test_wrapper_fails_safe_to_deny_when_the_engine_breaks():
    class BrokenEngine:
        def execute_dsl_check(self, trigger, context_data):
            raise RuntimeError("engine down")

    with patch("services.enforcement_engine.enforcement_engine", new=BrokenEngine()):
        result = asyncio.run(execute_dsl_check(TriggerType.LEAVE_REQUEST_SUBMIT.value, {}))
    assert result["decision"] == "DENY"
    assert result["rule_id"] == "ENGINE_ERROR"


if __name__ == "__main__":
    test_over_cap_leave_request_is_denied_by_the_real_rule()
    test_within_cap_leave_request_is_approved_after_real_evaluation()
    test_sync_engine_returns_the_tuple_contract_the_wrapper_relies_on()
    test_wrapper_fails_safe_to_deny_when_the_engine_breaks()
    print("PASS  leave policy checks run against the real engine")
