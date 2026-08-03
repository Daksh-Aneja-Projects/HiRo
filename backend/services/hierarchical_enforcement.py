# backend/services/hierarchical_enforcement.py
# /C:/HiRo Project/backend/services/hierarchical_enforcement.py
"""Hierarchical Enforcement Engine
Implements the Three-Dimensional Compliance Stack (Global/Industry/Local)
Resolves policy conflicts by applying strictest rule"""
import json
import logging
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass, asdict, field
from copy import deepcopy
from config.settings import settings

logger = logging.getLogger(__name__)

# --- Configuration Constants ---
GLOBAL_MIN_AGE = settings.GLOBAL_MIN_AGE if hasattr(settings, 'GLOBAL_MIN_AGE') else 16
GLOBAL_MAX_HOURS = settings.GLOBAL_MAX_HOURS if hasattr(settings, 'GLOBAL_MAX_HOURS') else 60
UK_MAX_HOURS = settings.UK_MAX_HOURS if hasattr(settings, 'UK_MAX_HOURS') else 48
UK_MIN_WAGE = settings.UK_MIN_WAGE if hasattr(settings, 'UK_MIN_WAGE') else 11.44
US_CA_MIN_WAGE = settings.US_CA_MIN_WAGE if hasattr(settings, 'US_CA_MIN_WAGE') else 16.00
POLICY_PRIORITY_LOW = settings.POLICY_PRIORITY_LOW if hasattr(settings, 'POLICY_PRIORITY_LOW') else 50
POLICY_PRIORITY_MEDIUM = settings.POLICY_PRIORITY_MEDIUM if hasattr(settings, 'POLICY_PRIORITY_MEDIUM') else 90
POLICY_PRIORITY_HIGH = settings.POLICY_PRIORITY_HIGH if hasattr(settings, 'POLICY_PRIORITY_HIGH') else 100

class HierarchyLevel(str, Enum):
    GLOBAL = "global"
    INDUSTRY = "industry"
    LOCAL = "local"

class IndustryVertical(str, Enum):
    BFSI = "financial_services"
    HEALTHCARE = "healthcare"
    GOVERNMENT = "government"
    TECHNOLOGY = "technology"
    MANUFACTURING = "manufacturing"
    RETAIL = "retail"
    GENERAL = "general"

class ConflictResolutionStrategy(str, Enum):
    STRICTEST = "strictest"
    LOCAL_PRIORITY = "local_priority"
    CUSTOM = "custom"

@dataclass
class PolicyConstraint:
    constraint_id: str
    hierarchy_level: HierarchyLevel
    jurisdiction: Optional[str]
    industry: Optional[IndustryVertical]
    rule_type: str
    field: str
    value: Any
    priority: int
    description: str
    effective_date: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class EnforcementDecision:
    allowed: bool
    applied_constraint: Optional[PolicyConstraint]
    all_applicable_constraints: List[PolicyConstraint]
    resolution_strategy: str
    reasoning: str
    audit_trail: Dict[str, Any]
    timestamp: str

class HierarchicalEnforcementEngine:
    """Enforces Three-Dimensional Compliance Stack with conflict resolution"""
    
    def __init__(self):
        self.constraints: Dict[str, PolicyConstraint] = {}
        self.enforcement_history: List[EnforcementDecision] = []
        self._initialize_default_constraints()

    def _initialize_default_constraints(self):
        # GLOBAL constraints
        self.add_constraint(PolicyConstraint(
            "GLOBAL_MIN_AGE", HierarchyLevel.GLOBAL, None, None,
            "minimum", "employee_age", GLOBAL_MIN_AGE, POLICY_PRIORITY_LOW,
            "Global minimum employment age"
        ))
        
        self.add_constraint(PolicyConstraint(
            "GLOBAL_MAX_HOURS", HierarchyLevel.GLOBAL, None, None,
            "maximum", "weekly_hours", GLOBAL_MAX_HOURS, POLICY_PRIORITY_LOW + 10,
            "Global safety standard"
        ))
        
        # INDUSTRY constraints
        self.add_constraint(PolicyConstraint(
            "SOX_SEGREGATION", HierarchyLevel.INDUSTRY, None, IndustryVertical.BFSI,
            "required", "sox_segregation_of_duties", True, POLICY_PRIORITY_MEDIUM,
            "SOX compliance"
        ))
        
        self.add_constraint(PolicyConstraint(
            "HIPAA_PHI_ENCRYPTION", HierarchyLevel.INDUSTRY, None, IndustryVertical.HEALTHCARE,
            "required", "phi_encryption", True, POLICY_PRIORITY_MEDIUM + 5,
            "HIPAA compliance"
        ))
        
        # LOCAL constraints
        self.add_constraint(PolicyConstraint(
            "UK_MAX_HOURS", HierarchyLevel.LOCAL, "UK", None,
            "maximum", "weekly_hours", UK_MAX_HOURS, POLICY_PRIORITY_HIGH,
            "UK WTR"
        ))
        
        self.add_constraint(PolicyConstraint(
            "UK_MIN_WAGE", HierarchyLevel.LOCAL, "UK", None,
            "minimum", "hourly_wage", UK_MIN_WAGE, POLICY_PRIORITY_HIGH,
            "UK NLW"
        ))
        
        self.add_constraint(PolicyConstraint(
            "US_CA_MIN_WAGE", HierarchyLevel.LOCAL, "US-CA", None,
            "minimum", "hourly_wage", US_CA_MIN_WAGE, POLICY_PRIORITY_HIGH,
            "CA Min Wage"
        ))
        
        self.add_constraint(PolicyConstraint(
            "EU_GDPR_CONSENT", HierarchyLevel.LOCAL, "EU", None,
            "required", "explicit_data_consent", True, POLICY_PRIORITY_HIGH,
            "GDPR Consent"
        ))

    def add_constraint(self, constraint: PolicyConstraint):
        self.constraints[constraint.constraint_id] = constraint

    def get_applicable_constraints(self, field: str, jurisdiction: Optional[str] = None,
                                   industry: Optional[IndustryVertical] = None) -> List[PolicyConstraint]:
        applicable = []
        
        for constraint in self.constraints.values():
            if constraint.field != field:
                continue
            
            if constraint.hierarchy_level == HierarchyLevel.GLOBAL:
                applicable.append(constraint)
            elif constraint.hierarchy_level == HierarchyLevel.INDUSTRY:
                if industry and constraint.industry == industry:
                    applicable.append(constraint)
            elif constraint.hierarchy_level == HierarchyLevel.LOCAL:
                if jurisdiction and constraint.jurisdiction == jurisdiction:
                    applicable.append(constraint)
        
        if not applicable:
             return []

        # Sorting: Highest priority first, then by Hierarchy level (Local > Industry > Global)
        # Hierarchy values are strings: 'local' > 'industry' > 'global'
        applicable.sort(key=lambda c: (c.priority, c.hierarchy_level.value), reverse=True)
        return applicable

    def resolve_conflict(self, constraints: List[PolicyConstraint], 
                         strategy: ConflictResolutionStrategy = ConflictResolutionStrategy.STRICTEST) -> Optional[PolicyConstraint]:
        if not constraints:
            return None
        
        if len(constraints) == 1:
            return constraints[0]

        if strategy == ConflictResolutionStrategy.STRICTEST:
            return self._apply_strictest_rule(constraints)
        elif strategy == ConflictResolutionStrategy.LOCAL_PRIORITY:
            local_constraints = [c for c in constraints if c.hierarchy_level == HierarchyLevel.LOCAL]
            if local_constraints:
                return max(local_constraints, key=lambda c: c.priority)
            return constraints[0] # Fallback to general priority sort if no local rule exists
        else:
            return constraints[0]

    def _apply_strictest_rule(self, constraints: List[PolicyConstraint]) -> PolicyConstraint:
        # Separate constraints by type
        minimums = [c for c in constraints if c.rule_type == "minimum"]
        maximums = [c for c in constraints if c.rule_type == "maximum"]
        requirements = [c for c in constraints if c.rule_type == "required"]
        
        # For minimums, take the highest value (strictest)
        if minimums:
            strictest_min = max(minimums, key=lambda c: c.value)
            return strictest_min
        
        # For maximums, take the lowest value (strictest)
        if maximums:
            strictest_max = min(maximums, key=lambda c: c.value)
            return strictest_max
        
        # For requirements, take the highest priority
        if requirements:
            strictest_req = max(requirements, key=lambda c: c.priority)
            return strictest_req
        
        # Fallback to highest priority constraint
        return max(constraints, key=lambda c: c.priority)

    def enforce(self, field: str, proposed_value: Any, jurisdiction: Optional[str] = None,
                industry: Optional[IndustryVertical] = None, 
                strategy: ConflictResolutionStrategy = ConflictResolutionStrategy.STRICTEST) -> EnforcementDecision:
        
        applicable = self.get_applicable_constraints(field, jurisdiction, industry)
        strictest_constraint = self.resolve_conflict(applicable, strategy)
        
        allowed = True
        reasoning = "No constraints apply"
        
        if strictest_constraint:
            reasoning = f"Applied rule {strictest_constraint.constraint_id}: {strictest_constraint.description}."
            
            if strictest_constraint.rule_type == "minimum":
                if proposed_value < strictest_constraint.value:
                    allowed = False
                    reasoning = f"Value {proposed_value} below minimum {strictest_constraint.value} set by rule {strictest_constraint.constraint_id}."
            elif strictest_constraint.rule_type == "maximum":
                if proposed_value > strictest_constraint.value:
                    allowed = False
                    reasoning = f"Value {proposed_value} above maximum {strictest_constraint.value} set by rule {strictest_constraint.constraint_id}."
            elif strictest_constraint.rule_type == "required":
                if not proposed_value:
                    allowed = False
                    reasoning = f"Required field '{field}' not provided (rule {strictest_constraint.constraint_id})."
            
            decision = EnforcementDecision(
                allowed=allowed,
                applied_constraint=strictest_constraint,
                all_applicable_constraints=applicable,
                resolution_strategy=strategy.value,
                reasoning=reasoning,
                audit_trail={
                    "field": field,
                    "proposed_value": proposed_value,
                    "jurisdiction": jurisdiction,
                    "industry": industry.value if industry else None
                },
                timestamp=datetime.now(timezone.utc).isoformat()
            )
        else:
             # Case where no constraints apply
            decision = EnforcementDecision(
                allowed=True,
                applied_constraint=None,
                all_applicable_constraints=applicable,
                resolution_strategy=strategy.value,
                reasoning=reasoning,
                audit_trail={
                    "field": field,
                    "proposed_value": proposed_value,
                    "jurisdiction": jurisdiction,
                    "industry": industry.value if industry else None
                },
                timestamp=datetime.now(timezone.utc).isoformat()
            )

        self.enforcement_history.append(decision)
        return decision

    def get_enforcement_history(self, limit: int = 100) -> List[EnforcementDecision]:
        return self.enforcement_history[-limit:] if self.enforcement_history else []

# Singleton instance
hierarchical_enforcer = HierarchicalEnforcementEngine()
