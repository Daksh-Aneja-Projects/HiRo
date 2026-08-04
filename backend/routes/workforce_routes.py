"""workforce API routes.

Split verbatim from services/comprehensive_routes.py; URL paths unchanged.
Router objects and shared helpers live in routes.comprehensive_common.
"""
from routes.comprehensive_common import *  # noqa: F401,F403
from routes.comprehensive_common import (  # noqa: F401
    _pvs,
    _policy_call,
    _readable_agent,
    _require_admin_service,
    _admin_audit,
    _audit_detail,
    _dev_persist,
    _parse_bpcl,
    _hr,
    _self_uuid,
    _reports_to,
    _scoped_employee_id,
    _owner_scope,
    _pending_leave_requests,
    _approval_queue,
    _generate_jd,
    _strip_code_fence,
    _twin_messages,
    _pqc,
    _consents,
    _workforce_analytics,
    _social_activities,
    _ideas,
    _BPCL_FIELD,
    _BPCL_CONSTRAINT,
)



# ======================================
# 8. WFP (Workforce Planning) ROUTER (Fixed/Complete)
# ======================================
@wfp_router.get("/dashboard{path:path}") 
async def get_wfp_dashboard_data(req: Request, path: str, payload: Dict = Depends(manager_role_required)):
    """FIX: Added robust endpoint to handle frontend's dashboard data request that currently 404s."""
    wfm_service = getattr(req.app.state, "wfm_service", None)
    if not wfm_service: raise HTTPException(status_code=503, detail="WFM Service unavailable.")
    
    data = await wfm_service.get_current_projections()
    return {"dashboard_data": data, "status": "OK"}


@wfp_router.get("/projections")
async def get_wfp_projections(req: Request, payload: Dict = Depends(manager_role_required)):
    """FIX: Added missing endpoint for WFP projections."""
    wfm_service = getattr(req.app.state, "wfm_service", None)
    if not wfm_service: raise HTTPException(status_code=503, detail="WFM Service unavailable.")
    return await wfm_service.get_current_projections()

@wfp_router.post("/predict_attrition")
async def predict_attrition(req: Request, employee_data: Dict = Body(...), payload: Dict = Depends(manager_role_required)):
    wfm_service = getattr(req.app.state, "wfm_service", None)
    if not wfm_service: raise HTTPException(status_code=503, detail="WFM Service unavailable.")
    
    if not employee_data:
        raise HTTPException(status_code=400, detail="Provide an employee_id (or a feature set) to score.")

    return await wfm_service.predict_attrition_risk(employee_data)

@analytics_router.get("/departments")
async def list_analytics_departments(req: Request, payload: Dict=Depends(manager_role_required)):
    """The real departments available as an analytics filter."""
    wfm = getattr(req.app.state, "wfm_service", None)
    if not wfm:
        raise HTTPException(status_code=503, detail="WFM Service unavailable.")
    return {"departments": await wfm.list_departments()}

@analytics_router.get("/metrics")
async def get_advanced_analytics(req: Request, metric_type: Optional[str] = Query(None), time_window: Optional[str] = Query(None), department: Optional[str] = Query(None), payload: Dict=Depends(manager_role_required)):
    """Real composite workforce-health analytics, scopeable by department."""
    dept = None if department in (None, "", "All", "All departments") else department
    a = await _workforce_analytics(req, department=dept)
    # No hardcoded "up": report the direction the risk band actually implies.
    trend = "down" if a.get("attrition_band") == "High" else "steady" if a.get("attrition_band") == "Medium" else "up"
    return {"metric": "Composite Workforce Health", "value": a["key_metric"], "trend": trend, **a}

@analytics_router.get("/charts")
async def get_analytics_charts(req: Request, department: Optional[str] = Query(None),
                               payload: Dict=Depends(manager_role_required)):
    """Chart series aggregated from the employee record, optionally for one
    department, so the filter above the charts actually reaches them."""
    wfm = getattr(req.app.state, "wfm_service", None)
    if not wfm:
        raise HTTPException(status_code=503, detail="WFM Service unavailable.")
    return await wfm.get_analytics_charts(department=department)

@analytics_router.post("/metrics/aggregate")
async def aggregate_metrics(req: Request, payload_data: Dict, payload: Dict=Depends(manager_role_required)):
    """Real aggregated metrics for the analytics dashboard.

    Honours a department filter, so the dashboard's controls actually change the
    numbers rather than being decorative.
    """
    metric_type = payload_data.get('metric_type', 'default')
    filters = payload_data.get('filters') or {}
    department = filters.get('department') or payload_data.get('department')
    if department in ("All", "All departments", ""):
        department = None

    if metric_type == 'financial_impact':
        # ponytail: headcount-scaled estimate; base salaries are encrypted at rest,
        # so no cleartext payroll aggregate exists without bulk decryption.
        a = await _workforce_analytics(req, department=department)
        return {"metric_type": metric_type, "value": round(a["headcount"] * 8500.0, 2),
                "scope": a["scope"],
                "note": "Estimate based on headcount; compensation is encrypted at rest and is not aggregated."}
    return await _workforce_analytics(req, department=department)

# ======================================
# 20. SI INTEGRATION: SIMULATION, REMEDIATION, TELEMETRY (Fixed/Complete)
# ======================================
@simulation_router.post("/run")
async def run_synthetic_simulation(req: Request, data: SimulationRequest, payload: Dict = Depends(manager_role_required)):
    twin_engine: SyntheticTwinEngine = getattr(req.app.state, 'synthetic_twin_engine', None)
    if not twin_engine:
        raise HTTPException(status_code=503, detail="Synthetic Twin Engine unavailable.")

    # Real engine signature: run_simulation(employee_id, adjustments, simulation_type, base_state)
    result = await twin_engine.run_simulation(
        data.employee_id,
        data.synthetic_adjustments,
        data.simulation_type,
    )

    delta = float(result.get("risk_score_delta", 0.0) or 0.0)
    attrition_change = float(result.get("attrition_probability_change", delta) or 0.0)
    recs = result.get("recommendations")
    recommendation = (
        recs[0] if isinstance(recs, list) and recs
        else (recs if isinstance(recs, str) else f"Review the simulated impact for {data.employee_id}.")
    )
    response = {
        "status": "Simulation Complete",
        "employee_id": data.employee_id,
        "simulation_id": result.get("simulation_id"),
        "metrics": {
            "risk_score_delta": round(delta, 3),
            "attrition_probability_change": round(attrition_change, 3),
            "productivity_impact": result.get("productivity_impact"),
            "cost_implication": result.get("cost_implication"),
        },
        "confidence_score": result.get("confidence_score"),
        "prescriptive_recommendation": recommendation,
        "adjustments_applied": result.get("adjustments_applied", data.synthetic_adjustments),
    }

    # Persist the run so /simulation/history returns real past runs.
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if mongo_client:
        await mongo_client[settings.MONGO_DB_NAME]["simulation_runs"].insert_one({
            **response,
            "type": data.simulation_type,
            "run_by": payload.get("sub"),
            "run_at": datetime.now(timezone.utc).isoformat(),
        })
    return response

@simulation_router.get("/history/{employee_id}")
async def get_simulation_history(req: Request, employee_id: str, limit: int = Query(20), payload: Dict = Depends(manager_role_required)):
    """Simulations actually run for this employee. Returns [] when there are none,
    rather than the fabricated row this used to serve for everybody."""
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        return []
    lim = max(1, min(int(limit or 20), 100))
    cursor = mongo_client[settings.MONGO_DB_NAME]["simulation_runs"].find(
        {"employee_id": employee_id}, {"_id": 0}
    ).sort("run_at", -1).limit(lim)
    return await cursor.to_list(length=lim)

@remediation_router.post("/audit-fail")
async def remediate_audit_failure(req: Request, data: RemediationRequest, payload: Dict = Depends(hrit_admin_role_required)):
    remediation_agent: CognitiveRemediationAgent = getattr(req.app.state, 'cognitive_remediation_agent', None)
    if not remediation_agent:
        raise HTTPException(status_code=503, detail="Cognitive Remediation Agent unavailable.")

    remediation_result = await remediation_agent.analyze_and_fix_transaction(
        data.audit_id, data.failed_transaction, data.policy_text
    )
    fix = remediation_result.get("proposed_fix", {})
    return {
        "status": "Remediation Suggested",
        "audit_id": data.audit_id,
        "suggested_fix": {
            "fixed_payload": fix.get("fixed_payload", fix) if isinstance(fix, dict) else fix,
            "reasoning": remediation_result.get("failure_analysis", "Agent analyzed the violation."),
            "confidence_score": remediation_result.get("compliance_score", 0.0),
        },
        "implementation_steps": remediation_result.get("implementation_steps", []),
    }
    
@remediation_router.post("/audit/{audit_id}/auto-resolve")
async def auto_resolve_audit(req: Request, audit_id: str, data: RemediationRequest, payload: Dict = Depends(hrit_admin_role_required)):
    """FIX: Added endpoint for the frontend's autoResolveAudit call."""
    remediation_agent: CognitiveRemediationAgent = getattr(req.app.state, 'cognitive_remediation_agent', None)
    if not remediation_agent:
        raise HTTPException(status_code=503, detail="Cognitive Remediation Agent unavailable.")
    
    remediation_result = await remediation_agent.analyze_and_fix_transaction(
        audit_id, data.failed_transaction, data.policy_text
    )
    fix = remediation_result.get("proposed_fix", {})
    return {
        "status": "Remediation Suggested",
        "audit_id": audit_id,
        "suggested_fix": {
            "fixed_payload": fix.get("fixed_payload", fix) if isinstance(fix, dict) else fix,
            "reasoning": remediation_result.get("failure_analysis", "Agent applied policy alignment logic."),
            "confidence_score": remediation_result.get("compliance_score", 0.0),
        },
        "implementation_steps": remediation_result.get("implementation_steps", []),
    }


@remediation_router.post("/apply-fix/{audit_id}")
async def apply_remediation_fix(req: Request, audit_id: str, fixed_payload: Dict, payload: Dict = Depends(hrit_admin_role_required)):
    """Record an accepted remediation against the audit entry.

    This previously returned "Fix Applied" without writing anything anywhere.
    The decision is now persisted and retrievable.
    """
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        raise HTTPException(status_code=503, detail="Remediation store unavailable.")
    record = {
        "audit_id": audit_id,
        "fixed_payload": fixed_payload,
        "applied_by": payload["sub"],
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "status": "APPLIED",
    }
    await mongo_client[settings.MONGO_DB_NAME]["remediations"].update_one(
        {"audit_id": audit_id}, {"$set": record}, upsert=True
    )
    return {"status": "Fix Applied", **record}

@remediation_router.get("/history/{audit_id}")
async def get_remediation_history(req: Request, audit_id: str, payload: Dict = Depends(hrit_admin_role_required)):
    """Remediations recorded against an audit entry (empty when there are none)."""
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        return []
    cursor = mongo_client[settings.MONGO_DB_NAME]["remediations"].find(
        {"audit_id": audit_id}, {"_id": 0}
    ).sort("applied_at", -1).limit(50)
    return await cursor.to_list(length=50)
