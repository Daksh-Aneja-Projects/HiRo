# /backend/services/enforcement_microservice.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any, Optional, Tuple
import time
import logging
import uuid
import json
from datetime import datetime, timezone
from config.settings import settings
from services.agent_spec_dsl import AgentSpecDSLRule, TriggerType, EnforcementAction

logger = logging.getLogger(__name__)

CACHE_TTL = 300
ENFORCER_AGENT_ID = "RUNTIME_ENFORCER"

# --- RUST ENGINE LOADING (THE MOAT) ---
try:
    import pac_engine_rs
    RUST_ENGINE_AVAILABLE = True
    logger.info("✅ Rust Policy Engine Loaded (High-Performance Mode)")
except ImportError:
    RUST_ENGINE_AVAILABLE = False
    logger.warning("⚠️ Rust Policy Engine NOT found. Falling back to Python Interpreter.")

# --- Helper Models ---
class EnforcementResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    decision: str
    rule_id: Optional[str] = None
    reason: Optional[str] = None
    execution_time_ms: float
    audit_id: str
    xai_trace: Optional[Dict[str, Any]] = None

class EnforcementMicroservice:
    def __init__(self):
        self.active_rules = {}
        self._load_rules()

    def _load_rules(self):
        # Fallback rules for Python engine
        self.active_rules["attrition_action"] = AgentSpecDSLRule(
            rule_id="attrition_action",
            description="High attrition risk block.",
            trigger_type=TriggerType.PRE_EXECUTION,
            condition_expression="input.get('risk_score', 0) > 0.8",
            action_type=EnforcementAction.BLOCK,
            is_active=True
        )
        # Add leave cap rule
        self.active_rules["policy_leave_cap_check"] = AgentSpecDSLRule(
            rule_id="policy_leave_cap_check",
            description="A single leave request cannot exceed 160 hours.",
            trigger_type=TriggerType.LEAVE_REQUEST_SUBMIT,
            condition_expression="input.get('Proposed', {}).get('Hours', 0) > 160",
            action_type=EnforcementAction.BLOCK,
            is_active=True
        )
        # Working-time limit. Both the timesheet pre-check and submission route
        # through this, so a dry run and the real decision cannot disagree.
        self.active_rules["policy_max_weekly_hours"] = AgentSpecDSLRule(
            rule_id="policy_max_weekly_hours",
            description="A timesheet week cannot exceed 48 hours without an approved overtime agreement.",
            trigger_type=TriggerType.TIME_CLOCK_IN,
            condition_expression=(
                "input.get('Proposed', {}).get('Hours', 0) > 48 "
                "and not input.get('Policy_Context', {}).get('overtime_agreement', False)"
            ),
            action_type=EnforcementAction.BLOCK,
            is_active=True
        )

    def execute_dsl_check(self, trigger: str, context_data: Dict[str, Any]) -> Tuple[EnforcementResponse, Dict[str, Any]]:
        """
        [SYNCHRONOUS CORE] Executes policy evaluation pipeline.
        Returns: (EnforcementResponse, audit_data)
        """
        start_time = time.perf_counter()
        audit_id = str(uuid.uuid4())

        # 1. RUST ACCELERATOR PATH
        if RUST_ENGINE_AVAILABLE:
            try:
                # Map Python trigger to Rust DSL keyword
                rule_dsl = "max_hours" if "leave" in trigger else "risk_check"
                context_json = json.dumps(context_data, default=str)
                
                # CALL RUST BINARY
                rust_resp_str = pac_engine_rs.validate_policy_rust(rule_dsl, context_json)
                rust_data = json.loads(rust_resp_str)
                
                execution_time = (time.perf_counter() - start_time) * 1000
                
                response = EnforcementResponse(
                    decision=rust_data['decision'],
                    rule_id=rust_data.get('rule_id'),
                    reason=rust_data['reason'],
                    execution_time_ms=execution_time,
                    audit_id=audit_id,
                    xai_trace={"engine": "rust_pac_v1"}
                )
                
                audit_data = {
                    "audit_id": audit_id,
                    "decision_timestamp": datetime.now(timezone.utc).isoformat(),
                    "policy_version": "RUST_V1",
                    "trigger_type": trigger,
                    "result": response.model_dump(),
                    "execution_time_ms": execution_time
                }
                return response, audit_data
            except Exception as e:
                logger.error(f"Rust Engine Failed: {e}. Falling back to Python.")

        # 2. PYTHON EVALUATION
        #
        # This previously returned APPROVE unconditionally without ever looking at
        # self.active_rules, so with the Rust accelerator unavailable the whole
        # policy engine was a rubber stamp: a 60-hour week and a 300-hour leave
        # request both "passed policy". The loaded rules are now actually evaluated.
        matched_rule = None
        evaluated = []
        for rule in self.active_rules.values():
            if not rule.is_active:
                continue
            # Only rules registered for this trigger apply.
            rule_trigger = getattr(rule.trigger_type, "value", rule.trigger_type)
            if rule_trigger not in (trigger, TriggerType.PRE_EXECUTION.value, TriggerType.PRE_EXECUTION):
                continue
            try:
                # Conditions are defined in code, never supplied by a user, and are
                # evaluated with no builtins so they cannot reach the runtime.
                hit = bool(eval(rule.condition_expression, {"__builtins__": {}}, {"input": context_data}))
            except Exception as e:
                logger.error(f"Rule {rule.rule_id} could not be evaluated: {e}")
                continue
            evaluated.append({"rule_id": rule.rule_id, "matched": hit, "description": rule.description})
            if hit and rule.action_type == EnforcementAction.BLOCK:
                matched_rule = rule
                break

        execution_time = (time.perf_counter() - start_time) * 1000
        if matched_rule:
            response = EnforcementResponse(
                decision="DENY",
                rule_id=matched_rule.rule_id,
                reason=matched_rule.description,
                execution_time_ms=execution_time,
                audit_id=audit_id,
                xai_trace={"engine": "python", "rules_evaluated": evaluated},
            )
        else:
            response = EnforcementResponse(
                decision="APPROVE",
                rule_id="PYTHON_ENGINE",
                reason=f"Passed {len(evaluated)} applicable policy rule(s).",
                execution_time_ms=execution_time,
                audit_id=audit_id,
                xai_trace={"engine": "python", "rules_evaluated": evaluated},
            )
        
        audit_data = {
            "audit_id": audit_id,
            "decision_timestamp": datetime.now(timezone.utc).isoformat(),
            "policy_version": "PYTHON_FALLBACK",
            "trigger_type": trigger,
            "result": response.model_dump(),
            "execution_time_ms": execution_time
        }
        return response, audit_data

enforcement_engine = EnforcementMicroservice()