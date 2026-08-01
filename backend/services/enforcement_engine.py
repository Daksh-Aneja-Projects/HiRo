# services/enforcement_engine.py - REPLACEMENT (Asynchronous Execution and Logging)
"""
Async Wrapper for Enforcement Engine.
Handles threading, error boundaries, and failsafe stubs for the policy system.
"""
import asyncio
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone # CRITICAL FIX: Add missing datetime/timezone
from config.settings import settings 
import json 

# CRITICAL FIX: Import pg_client for the async logging function
from services.postgres_client import pg_client

# Robust import for metrics (handle missing dependency gracefully)
try:
    from services.metrics import track_time 
except ImportError:
    # No-op decorator if metrics service is missing
    def track_time(name):
        def decorator(func):
            def wrapper(*args, **kwargs): # CRITICAL FIX: Added wrapper function to match decorator pattern
                return func(*args, **kwargs)
            return wrapper
        return decorator

logger = logging.getLogger("enforcement.engine")

# Robust import of the synchronous enforcement engine
try:
    # This imports the EnforcementMicroservice class instance
    from services.enforcement_microservice import enforcement_engine 
    # CRITICAL FIX: Verify the expected method exists on the imported instance
    if not hasattr(enforcement_engine, 'execute_dsl_check'):
         raise AttributeError("Imported engine instance lacks required method 'execute_dsl_check'.")
    logger.info("✓ Real Enforcement Engine imported successfully.")
except (ImportError, AttributeError) as e:
    logger.critical(f"Enforcement Engine failed to import: {e}. Using stub.")
    
    class EnforcementEngineStub:
        """Failsafe stub that denies all actions when the real engine is broken."""
        def execute_dsl_check(self, trigger: str, context_data: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]: 
            # CRITICAL FIX: Returns the required Tuple (response_model, audit_data)
            response = {
                "decision": "DENY",
                "rule_id": "STUB_FAILSAFE",
                "reason": "Enforcement engine is unavailable (stub active).",
                "execution_time_ms": 0,
                "audit_id": "stub-fail",
                "xai_trace": {}
            }
            audit_data = {
                "audit_id": "stub-fail",
                "decision_timestamp": datetime.now(timezone.utc).isoformat(),
                "policy_version": "STUB_FAILSAFE",
                "trigger_type": trigger,
                "result": response,
                "execution_time_ms": 0,
            }
            return response, audit_data
    enforcement_engine = EnforcementEngineStub()


async def log_policy_decision_async(audit_data: Dict[str, Any]):
    """Logs policy decision to Postgres using the async client."""
    try:
        # CRITICAL FIX: Use the specific table name and columns required for audit logging
        query = """
            INSERT INTO policy_audit_log
              (audit_id, decision_timestamp, policy_version, trigger_type, decision, reason, execution_time_ms, context_json)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
            ON CONFLICT (audit_id) DO NOTHING;"""
        
        # Ensure timestamp is string for Postgres
        decision_timestamp = audit_data["decision_timestamp"]
        
        await pg_client.execute(
            query,
            audit_data["audit_id"],
            decision_timestamp,
            audit_data["policy_version"],
            audit_data["trigger_type"],
            audit_data["result"]["decision"],
            audit_data["result"]["reason"],
            audit_data["result"]["execution_time_ms"],
            # CRITICAL FIX: Log the full result dictionary as context
            json.dumps(audit_data["result"], default=str), 
        )
    except Exception as e:
        logger.error(f"Failed to log policy decision to Postgres: {e}")


async def _approved_but_not_live(policy_versioning=None):
    """Approved policy versions that are not the live one for their policy.

    Returns (list, whether the check could run). An empty list with the check
    unavailable is not the same as nothing being out of date, so the caller can
    say which it is instead of showing a reassuring tick either way.
    """
    if policy_versioning is None:
        return [], False
    try:
        stale = []
        for policy_id in {v.policy_id for v in policy_versioning.versions.values()}:
            active = policy_versioning.get_active_version(policy_id)
            approved = [v for v in policy_versioning.versions.values()
                        if v.policy_id == policy_id
                        and str(getattr(v.status, "value", v.status)).upper() == "APPROVED"]
            for version in approved:
                if not active or active.version_id != version.version_id:
                    stale.append({"policy_id": policy_id, "version_id": version.version_id,
                                  "version_number": getattr(version, "version_number", None)})
        return stale, True
    except Exception as e:
        logger.warning(f"could not check whether approved policies are live: {e}")
        return [], False


async def get_compliance_overview(policy_versioning=None) -> Dict[str, Any]:
    """Real compliance aggregates from the policy_audit_log table.

    Backs /compliance/dashboard: overall compliance score (allow-rate), high-severity
    violations (DENY decisions in the last 24h), and the regulatory-feed liveness signal.
    """
    row = await pg_client.fetchrow(
        """
        SELECT
          COUNT(*)                                                           AS total_decisions,
          COUNT(*) FILTER (WHERE decision = 'DENY')                          AS denials,
          COUNT(*) FILTER (WHERE decision = 'DENY'
              AND decision_timestamp::timestamptz > NOW() - INTERVAL '24 hours') AS high_severity_violations,
          COUNT(*) FILTER (WHERE decision_timestamp::timestamptz > NOW() - INTERVAL '24 hours') AS decisions_24h,
          MAX(decision_timestamp::timestamptz)                               AS last_decision_at
        FROM policy_audit_log
        """
    ) or {}

    total = int(row.get("total_decisions") or 0)
    denials = int(row.get("denials") or 0)
    decisions_24h = int(row.get("decisions_24h") or 0)
    # No decisions means no compliance rate. This used to default to 1.0, so a
    # brand-new deployment that had never enforced anything showed "100%
    # compliant" -- a perfect score awarded for the absence of evidence.
    score = round(1.0 - (denials / total), 4) if total else None
    score_note = ("Allow-rate across all recorded policy decisions."
                  if total else "No policy decisions have been recorded yet, so there is "
                                "no compliance rate to report.")

    last = row.get("last_decision_at")

    # Whether every approved policy is actually the one being enforced. This
    # used to be `total > 0`, which is "has any decision ever been recorded",
    # presented to an HRBP as confirmation that the live policy set is the
    # newest one. It could not detect an unapplied newer version, which is the
    # one thing the card exists to tell them.
    approved_not_live, live_check_available = await _approved_but_not_live(policy_versioning)

    return {
        "score": score,
        "score_available": score is not None,
        "score_note": score_note,
        # DENY decisions in the last day. There is no severity column on the
        # decision log and no open/closed state, so calling these "open high
        # severity breaches" claimed two things the data does not hold.
        "denials_24h": int(row.get("high_severity_violations") or 0),
        "high_severity_violations": int(row.get("high_severity_violations") or 0),
        # This read "ONLINE" whenever any internal policy decision had been made
        # in the last day, which has nothing to do with a regulatory feed. There
        # is no live feed attached, and /compliance/monitor_feeds says so; the
        # two endpoints used to contradict each other.
        "regulatory_feed_status": "NOT_CONNECTED",
        "regulatory_feed_note": ("No external regulatory feed is attached. "
                                 "Jurisdictions can be subscribed, and updates apply "
                                 "once a feed is connected."),
        "latest_version_applied": (not approved_not_live) if live_check_available else None,
        "policies_approved_but_not_live": approved_not_live,
        "latest_version_note": (
            "Every approved policy is the one being enforced." if live_check_available and not approved_not_live
            else f"{len(approved_not_live)} approved {'policy is' if len(approved_not_live) == 1 else 'policies are'} "
                 f"not the live version yet." if live_check_available
            else "The policy store could not be read, so this could not be checked."),
        "last_decision_at": last.isoformat() if last is not None else None,
        "total_decisions": total,
        "denials": denials,
    }


# CRITICAL FIX: The wrapper should handle the execution time tracking
async def execute_dsl_check(trigger: str, context_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Async wrapper for synchronous enforcement engine.
    """
    try:
        # Run synchronous CPU-bound policy logic in a separate thread
        result_tuple = await asyncio.to_thread(
            enforcement_engine.execute_dsl_check,
            trigger,
            context_data
        )
        
        result_response = result_tuple[0]
        audit_data = result_tuple[1]

        # Normalize result (handle Pydantic models vs Dicts)
        if hasattr(result_response, 'model_dump'):
            result_dict = result_response.model_dump()
        else:
            result_dict = result_response
            
        # CRITICAL FIX: Dispatch the async logging task to the main event loop
        asyncio.create_task(log_policy_decision_async(audit_data))
            
        # Ensure all expected fields are present
        return {
            "decision": result_dict.get("decision", "DENY"),
            "rule_id": result_dict.get("rule_id", "N/A"),
            "reason": result_dict.get("reason", "Policy check complete."),
            "execution_time_ms": result_dict.get("execution_time_ms", 0),
            "audit_id": result_dict.get("audit_id", "N/A"),
            "xai_trace": result_dict.get("xai_trace", {})
        }
        
    except Exception as e:
        logger.error(f"Error during DSL check for {trigger}: {type(e).__name__} - {e}")
        return {
            "decision": "DENY",
            "rule_id": "ENGINE_ERROR",
            "reason": f"Policy engine internal failure: {type(e).__name__}",
            "execution_time_ms": 0,
            "audit_id": "fail",
            "xai_trace": {}
        }

# Alias for server.py compatibility
runtime_enforcer = execute_dsl_check