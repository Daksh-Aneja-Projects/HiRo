# /backend/services/agent_spec_dsl.py - FIXED
# /C:/HiRo Project/backend/services/agent_spec_dsl.py
"""Agent Specification Domain-Specific Language (DSL) Parser.
Defines the structure and provides tools to parse the intent into a machine-readable format."""
import logging
from enum import Enum # CRITICAL FIX: Added missing Enum import
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger(__name__)

# --- Configuration Constants ---
DSL_VERSION = "1.0"

# --- CRITICAL FIX: Missing Enums Required by Enforcement Engine ---
class TriggerType(str, Enum):
    """Defines when a rule should be evaluated."""
    PRE_EXECUTION = "pre_execution"
    POST_EXECUTION = "post_execution"
    SCHEDULED = "scheduled"
    ON_EVENT = "on_event"
    TIME_CLOCK_IN = "time_clock_in"
    LEAVE_REQUEST_SUBMIT = "leave_request_submit"  # CRITICAL FIX: Add missing trigger type for ESS

class ActionType(str, Enum):
    """Defines what happens when a rule matches."""
    BLOCK = "block"
    FLAG = "flag"
    REDACT = "redact"
    LOG_ONLY = "log_only"

# Alias for backward compatibility
EnforcementAction = ActionType

# Core DSL Schema Definitions
CORE_SPEC_SCHEMA: Dict[str, Dict[str, Any]] = {
    "agent_name": {"type": "string", "description": "Unique, descriptive name."},
    "description": {"type": "string", "description": "High-level goal and function."},
    "dependencies": {"type": "array", "items": {"type": "string"}},
    "permissions": {"type": "array", "items": {"type": "string"}},
    "input_schema": {"type": "object", "description": "JSON Schema defining expected input."},
    "execution_module": {"type": "string", "description": "Python path to execution class."},
    "is_proactive": {"type": "boolean", "description": "True if agent runs in background."}
}

# --- Pydantic Models ---
class AgentSpecDSLRule(BaseModel):
    """Defines a rule within the Agent Specification Domain Specific Language."""
    model_config = ConfigDict(protected_namespaces=())
    
    rule_id: str = Field(..., description="Unique identifier for the rule")
    description: Optional[str] = Field(None, description="Human-readable description")
    trigger_type: TriggerType = Field(TriggerType.PRE_EXECUTION, description="When to evaluate this rule")
    condition_expression: str = Field(..., description="Logic string to evaluate")
    action_type: ActionType = Field(ActionType.FLAG, description="Action to take")
    action_params: Dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(100, description="Execution priority (lower runs first)")
    is_active: bool = Field(True, description="Enabled status")

class AgentSpecDSL:
    """Provides tools for structuring and validating the high-level agent specification."""
    def __init__(self):
        self.schema = CORE_SPEC_SCHEMA
        logger.info(f"✓ Agent Spec DSL initialized (v{DSL_VERSION}).")
        
    def get_full_schema(self) -> Dict[str, Dict[str, Any]]:
        return self.schema
        
    def validate_syntactic_structure(self, spec_data: Dict[str, Any]) -> List[str]:
        errors = []
        for key in ["agent_name", "execution_module", "dependencies"]:
            if key not in spec_data:
                errors.append(f"Missing required key: {key}")
                
        if "dependencies" in spec_data and not isinstance(spec_data["dependencies"], list):
            errors.append("Key 'dependencies' must be a list.")
            
        return errors

# --- Default Rules ---
LEAVE_CAP_CHECK_RULE = AgentSpecDSLRule(
    rule_id="policy_leave_cap_check",
    description="Standard enforcement rule to flag leave requests exceeding 30 days.", # FIXED: Unterminated string literal
    trigger_type=TriggerType.LEAVE_REQUEST_SUBMIT,
    condition_expression="input.get('leave_days', 0) > 30",
    action_type=ActionType.FLAG,
    action_params={"severity": "medium", "reason": "Leave duration exceeds policy cap"},
    priority=10,
    is_active=True
)
