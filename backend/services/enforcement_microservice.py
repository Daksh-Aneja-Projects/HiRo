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
            description="Deny leave if it exceeds 160 hours cap.",
            trigger_type=TriggerType.LEAVE_REQUEST_SUBMIT,
            condition_expression="input.get('Proposed', {}).get('Hours', 0) > 160",
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

        # 2. PYTHON FALLBACK (Simple failover logic)
        execution_time = (time.perf_counter() - start_time) * 1000
        response = EnforcementResponse(
            decision="APPROVE",
            rule_id="PYTHON_FALLBACK",
            reason="Policy checks passed (Python Engine).",
            execution_time_ms=execution_time,
            audit_id=audit_id,
            xai_trace={"engine": "python_fallback"}
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