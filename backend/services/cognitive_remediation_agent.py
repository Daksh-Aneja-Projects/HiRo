# /backend/services/cognitive_remediation_agent.py - REPLACEMENT (Adding Trigger Inference for Validation)
"""Cognitive Remediation Agent
Analyzes failed transactions and proposes policy-compliant fixes"""
import logging
import json
import re
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from services.ai_services import AIService
from services.enforcement_engine import runtime_enforcer
from services.agent_spec_dsl import TriggerType

logger = logging.getLogger(__name__)

class CognitiveRemediationAgent:
    def __init__(self, ai_service: AIService):
        self.ai_service = ai_service
        
    def _infer_trigger_type(self, transaction: Dict[str, Any]) -> str:
        """Infers the appropriate policy trigger type from the failed transaction data."""
        transaction_keys = [k.lower() for k in transaction.keys()]
        
        if 'leave_request' in transaction_keys or 'leave_submission' in transaction_keys:
            return TriggerType.LEAVE_REQUEST_SUBMIT.value
        if 'timesheet_id' in transaction_keys or 'total_hours' in transaction_keys:
            # Timesheets go through TIME_CLOCK_IN; there is no TIMESHEET_SUBMISSION
            # member, so this used to raise AttributeError after the LLM work was done.
            return TriggerType.TIME_CLOCK_IN.value
        if 'compensation' in transaction_keys or 'salary_change' in transaction_keys:
            return "compensation_change" # Using the string from UDM/PolicyScraping
        
        return TriggerType.PRE_EXECUTION.value # Default to general pre-execution check


    async def analyze_and_fix_transaction(self,
                                         audit_id: str,
                                         failed_transaction: Dict[str, Any],
                                         policy_text: str) -> Dict[str, Any]:
        """Analyze failed transaction and propose compliant fix"""
        
        logger.info(f"Analyzing failed transaction {audit_id}")
        
        # 1. Extract failure details
        failure_details = await self._extract_failure_details(failed_transaction, policy_text)
        
        # 2. Generate multiple fix candidates
        fix_candidates = await self._generate_fix_candidates(failure_details, policy_text)
        
        # 3. Validate each candidate
        validated_fixes: List[Dict[str, Any]] = []
        
        # CRITICAL FIX: Infer the trigger type to use for validation
        validation_trigger = self._infer_trigger_type(failed_transaction) 
        
        for candidate in fix_candidates:
            validation = await self._validate_fix_candidate(candidate, validation_trigger)
            if validation["compliant"]:
                validated_fixes.append({
                    **candidate,
                    "compliance_score": validation["score"],
                    "explanation": validation["explanation"]
                })

        # 4. Select best fix
        best_fix = self._select_best_fix(validated_fixes)
        
        # 5. Generate implementation steps
        implementation = await self._generate_implementation_steps(best_fix, failed_transaction)
        
        return {
            "remediation_id": f"REMED_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "audit_id": audit_id,
            "original_transaction": failed_transaction,
            "failure_analysis": failure_details,
            "proposed_fix": best_fix,
            "compliance_score": best_fix.get("compliance_score", 0),
            "implementation_steps": implementation,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "estimated_resolution_time": "5-10 minutes"
        }

    async def _extract_failure_details(self, transaction: Dict[str, Any], policy_text: str) -> Dict[str, Any]:
        """Extract why the transaction failed"""
        
        prompt = f"""
        Analyze why this transaction failed against the policy:

        Transaction: {json.dumps(transaction, indent=2)}
        Policy: {policy_text}

        Identify:
        1. Which specific policy clauses were violated
        2. The exact data fields causing violations
        3. Suggested corrections for each violation

        Output JSON format.
        """
        
        analysis = await self.ai_service.generate_json_response(
            prompt,
            response_schema={
                "type": "object",
                "properties": {
                    "violations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "policy_clause": {"type": "string"},
                                "violated_field": {"type": "string"},
                                "current_value": {"type": "string"},
                                "required_value": {"type": "string"},
                                "severity": {"type": "string", "enum": ["high", "medium", "low"]}
                            }
                        }
                    },
                    "root_cause": {"type": "string"},
                    "correction_approach": {"type": "string"}
                }
            },
            task_type="analysis"
        )
        
        return analysis or {"violations": [], "root_cause": "Unknown", "correction_approach": "Manual review"}

    async def _generate_fix_candidates(self, failure_details: Dict[str, Any], policy_text: str) -> List[Dict[str, Any]]:
        """Generate multiple potential fixes"""
        
        candidates: List[Dict[str, Any]] = []
        
        # Generate conservative fix
        conservative_prompt = f"""
        Generate a conservative fix for these policy violations:
        Violations: {json.dumps(failure_details.get('violations', []), indent=2)}
        Policy: {policy_text}

        Approach: Minimal changes, maximum 
        compliance

        Output the fixed transaction data.
        """
        
        conservative_fix = await self.ai_service.generate_json_response(
            conservative_prompt,
            response_schema={
                "type": "object",
                "properties": {
                    "fixed_transaction": {"type": "object"},
                    "changes_made": {"type": "array", "items": {"type": "string"}},
                    "compliance_guarantee": {"type": "string"}
                }
            },
            task_type="generation"
        )
        
        if conservative_fix:
            candidates.append({
                **conservative_fix,
                "strategy": "conservative",
                "risk_level": "low"
            })
            
        # Generate balanced fix
        balanced_prompt = f"""
        Generate a balanced fix that maintains business intent while ensuring compliance:
        Violations: {json.dumps(failure_details.get('violations', []), indent=2)}
        Policy: {policy_text}

        Approach: Balance business needs with compliance requirements

        Output the fixed transaction data.
        """
        
        balanced_fix = await self.ai_service.generate_json_response(
            balanced_prompt,
            response_schema={
                "type": "object",
                "properties": {
                    "fixed_transaction": {"type": "object"},
                    "changes_made": {"type": "array", "items": {"type": "string"}},
                    "business_preservation": {"type": "string"}
                }
            },
            task_type="generation"
        )
        
        if balanced_fix:
            candidates.append({
                **balanced_fix,
                "strategy": "balanced",
                "risk_level": "medium"
            })
            
        return candidates

    async def _validate_fix_candidate(self, candidate: Dict[str, Any], validation_trigger: str) -> Dict[str, Any]:
        """Validate fix candidate against policy using the inferred trigger type."""
        
        # Use enforcement engine to validate
        validation_result = await runtime_enforcer(
            validation_trigger,
            candidate.get("fixed_transaction", {})
        )
        
        compliant = validation_result["decision"] in ["APPROVE", "FLAG"]
        
        # Get the actual execution score if available, otherwise use heuristics
        score = validation_result.get("compliance_score", 0.95 if compliant else 0.3)
        
        return {
            "compliant": compliant,
            "score": score,
            "explanation": validation_result["reason"],
            "enforcement_result": validation_result
        }

    def _select_best_fix(self, validated_fixes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Select the best fix from validated candidates"""
        if not validated_fixes:
            return {"error": "No compliant fixes found"}
        
        # Prioritize by compliance score, then low risk
        return max(
            validated_fixes,
            key=lambda x: (x.get("compliance_score", 0), 
                          1 if x.get("risk_level") == "low" else 0.5)
        )

    async def _generate_implementation_steps(self, best_fix: Dict[str, Any],
                                             original_transaction: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate step-by-step implementation guide"""
        
        steps = [
            {
                "step": 1,
                "action": "Review proposed changes",
                "details": "Compare original vs fixed transaction",
                "estimated_time": "1 minute"
            },
            {
                "step": 2,
                "action": "Update transaction data",
                "details": f"Modify {len(best_fix.get('changes_made', []))} field(s)",
                "estimated_time": "2 minutes"
            },
            {
                "step": 3,
                "action": "Verify compliance",
                "details": "Re-run policy validation",
                "estimated_time": "1 minute"
            },
            {
                "step": 4,
                "action": "Submit corrected transaction",
                "details": "Use the 'Submit with Fix' button",
                "estimated_time": "1 minute"
            }
        ]
        
        return steps