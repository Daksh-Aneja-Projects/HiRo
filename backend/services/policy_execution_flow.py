# services/policy_execution_flow.py - REPLACEMENT (Test Harness Clarity)
import asyncio
import logging
from services.agent_spec_dsl import LEAVE_CAP_CHECK_RULE, TriggerType # FIX: Added TriggerType for clarity
from services.enforcement_engine import runtime_enforcer
from services.xai_wrapper import XAIWrapper
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# NOTE: XAIWrapper needs to be initialized outside of main_simulation for reuse if run by a service
xai_explainer = XAIWrapper()
# CRITICAL FIX: Added placeholder for the required synchronous method
if not hasattr(xai_explainer, 'explain_prediction'):
    xai_explainer.explain_prediction = xai_explainer.get_feature_contributions # Mock the method to point to the async version

async def main_simulation():
    """Simulates a timesheet submission/leave request triggering policy enforcement, rollback, and XAI explanation."""
    # 1. Setup Context
    context = {
        "input": {"leave_days": 45, "employee_uuid": "EMP-001", "tenure_months": 36}, # Exceeds 30 day cap
        "employee_tier": "Standard",
        "UDM": {
             "AI_Features": {"compensation_percentile": 60, "satisfaction_score": 4.0},
             "employee_uuid": "EMP-001"
        }
    }
    
    # 2. Run Enforcement (Real Engine - Asynchronous)
    print("\n--- Executing Policy Check ---")
    
    try:
        # CRITICAL FIX: runtime_enforcer.execute_dsl_check is the public async interface
        # Use the specific trigger type from the imported rule
        result = await runtime_enforcer.execute_dsl_check(LEAVE_CAP_CHECK_RULE.trigger_type.value, context)
        
        print(f"Decision: {result['decision']}")
        print(f"Reason: {result['reason']}")
        
        # 3. Explain (Real XAI - Asynchronous)
        print("\n--- Generating XAI Explanation ---")
        explanation = await xai_explainer.get_feature_contributions(context.get("UDM", {}))
        
        print(f"Explanation: {explanation['human_summary']}")
        print(f"Top Factors: {explanation['feature_contributions'][:2]}")
        
    except Exception as e:
        logger.error(f"Simulation FAILED: {e}")
        print(f"Simulation FAILED: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    asyncio.run(main_simulation())