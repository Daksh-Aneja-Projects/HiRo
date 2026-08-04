"""governance API routes.

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
# 1. POLICY GOVERNANCE ROUTER (Fixed/Complete)
# ======================================
# Declared before /{policy_id}/... so "list" is not captured as a policy id.
@policy_router.get("/list")
async def list_policies(req: Request, payload: Dict = Depends(policy_admin_role_required)):
    """Every policy the versioning service knows about, with its live version.
    Without this the UI had no way to discover existing policy ids."""
    pvs = getattr(req.app.state, 'policy_versioning_service', None)
    if not pvs:
        raise HTTPException(status_code=503, detail="Policy Versioning Service unavailable.")
    active = getattr(pvs, "active_versions", {}) or {}
    versions = getattr(pvs, "versions", {}) or {}
    by_policy: Dict[str, Dict[str, Any]] = {}
    for v in versions.values():
        pid = getattr(v, "policy_id", None)
        if not pid:
            continue
        entry = by_policy.setdefault(pid, {"policy_id": pid, "version_count": 0, "active_version_id": active.get(pid)})
        entry["version_count"] += 1
        entry["latest_version_number"] = getattr(v, "version_number", None)
    return {"policies": sorted(by_policy.values(), key=lambda p: p["policy_id"]), "count": len(by_policy)}

@policy_router.get("/{policy_id}/active")
async def get_active_policy(req: Request, policy_id: str):
    pvs: PolicyVersioningService = getattr(req.app.state, 'policy_versioning_service', None)
    if not pvs: raise HTTPException(status_code=503, detail="Policy Versioning Service unavailable.")
    return pvs.get_active_version(policy_id)

@policy_router.get("/{policy_id}/history")
async def get_policy_history(req: Request, policy_id: str):
    pvs: PolicyVersioningService = getattr(req.app.state, 'policy_versioning_service', None)
    if not pvs: raise HTTPException(status_code=503, detail="Policy Versioning Service unavailable.")
    return await asyncio.to_thread(pvs.get_version_history, policy_id)

@policy_router.post("/{policy_id}/versions")
async def create_policy_draft(req: Request, policy_id: str, data: PolicyUpdateRequest, payload: Dict=Depends(policy_admin_role_required)):
    pvs = _pvs(req)
    active_version = getattr(pvs, 'active_versions', {}).get(policy_id)
    draft = await _policy_call(pvs.create_policy_version, policy_id, data.content, payload['sub'], data.changelog, active_version)
    return {"version_id": draft.version_id, "version_number": draft.version_number}

@policy_router.put("/versions/{version_id}/content")
async def update_policy_draft_content(req: Request, version_id: str, data: PolicyUpdateRequest, payload: Dict=Depends(policy_admin_role_required)):
    await _policy_call(_pvs(req).update_version_content, version_id, data.content, payload['sub'], data.changelog)
    return {"status": "Updated"}

@policy_router.post("/versions/{version_id}/submit")
async def submit_policy(req: Request, version_id: str,
                      approvers: List[str] = Body(..., embed=True), payload: Dict=Depends(policy_admin_role_required)):
    req_obj = await _policy_call(_pvs(req).submit_for_approval, version_id, payload['sub'], approvers)
    return {"request_id": req_obj.request_id}

@policy_router.post("/approvals/{request_id}")
async def process_policy_approval(req: Request, request_id: str, action: ApprovalActionRequest, payload: Dict=Depends(policy_admin_role_required)):
    await _policy_call(_pvs(req).approve_policy, request_id, payload['sub'], action.approved, action.comments)
    return {"status": "Processed"}

@policy_router.post("/versions/{version_id}/activate")
async def activate_policy(req: Request, version_id: str, payload: Dict=Depends(policy_admin_role_required)):
    await _policy_call(_pvs(req).activate_version, version_id, payload['sub'])

    # KIND_POLICY was declared and never wired: HRBP users had no way to learn a
    # policy went live short of stumbling onto the policy list.
    pvs = _pvs(req)
    version_obj = (getattr(pvs, "versions", {}) or {}).get(version_id)
    policy_id = getattr(version_obj, "policy_id", None) or version_id
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if mongo_client:
        try:
            hrbp_users = await mongo_client[settings.MONGO_DB_NAME]["users"].find(
                {"role": "hrbp"}, {"employee_uuid": 1}
            ).to_list(length=500)
            for u in hrbp_users:
                if u.get("employee_uuid"):
                    await notification_service.notify(
                        u["employee_uuid"], notification_service.KIND_POLICY,
                        "A policy went live",
                        f'Policy "{policy_id}" was activated.',
                        link="/hr-portal?module=policy", related_id=policy_id,
                    )
        except Exception as e:
            logger.warning(f"could not notify HRBP users of policy activation: {e}")

    return {"status": "Activated"}

@policy_router.post("/{policy_id}/rollback")
async def rollback_policy(req: Request, policy_id: str, target_version_id: str = Body(..., embed=True), payload: Dict=Depends(policy_admin_role_required)):
    await _policy_call(_pvs(req).rollback_to_version, policy_id, target_version_id, payload['sub'])
    return {"status": "Rollback Success"}

@policy_router.post("/ledger/commit")
async def commit_to_ledger(req: Request, data: Dict[str, Any], auth_payload: Dict = Depends(policy_admin_role_required)):
    """Append a content-addressed record to the policy ledger (Mongo). Each block's
    hash chains the previous block's hash, so tampering is detectable."""
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        raise HTTPException(status_code=503, detail="Ledger store unavailable.")
    ledger = mongo_client[settings.MONGO_DB_NAME]["policy_ledger"]

    prev = await ledger.find_one(sort=[("index", -1)])
    prev_hash = prev["block_hash"] if prev else "0" * 64
    index = (prev["index"] + 1) if prev else 0
    timestamp = data.get("timestamp") or datetime.now(timezone.utc).isoformat()

    payload_str = json.dumps(data, sort_keys=True, default=str)
    block_hash = hashlib.sha256(f"{index}{prev_hash}{payload_str}{timestamp}".encode()).hexdigest()

    await ledger.insert_one({
        "index": index,
        "prev_hash": prev_hash,
        "block_hash": block_hash,
        "payload": data,
        "committed_by": auth_payload.get("sub"),
        "timestamp": timestamp,
    })
    return {"status": "COMMITTED", "block_hash": block_hash, "index": index, "timestamp": timestamp}

@policy_router.post("/scan-policy-for-deployment")
async def scan_policy_for_deployment(req: Request, data: PolicyScanRequest, payload: Dict=Depends(policy_admin_role_required)):
    # runtime_enforcer is the module-level async function execute_dsl_check(trigger, context_data).
    scan_result = await runtime_enforcer("pre_deployment_scan", {
        "PolicyVersion": data.version_id,
        "PolicyContent": data.policy_content,
    })

    decision = (scan_result.get("decision") or "").upper()
    if decision in ("DENY", "STOP", "BLOCK"):
        raise HTTPException(status_code=400, detail=f"Scan failed: {scan_result.get('reason', 'policy denied')}")

    return {
        "status": "SECURE",
        "decision": decision or "PASS",
        "vulnerabilities": [],
        "audit_id": scan_result.get("audit_id"),
        "trace": scan_result.get("xai_trace", "Policy passed syntax and enforcement checks."),
    }

@policy_router.post("/deploy-bpcl-from-prompt/{policy_id}")
async def deploy_bpcl_from_prompt(req: Request, policy_id: str, nl_prompt: str = Body(..., embed=True), payload: Dict=Depends(policy_admin_role_required)):
    """Turn a written instruction into a draft policy rule, and show it back.

    This used to spend seven seconds of real inference, write the result into a
    Mongo collection nothing ever reads, discard it from the response, and tell
    the operator "Deployment Initiated". Nothing was deployed and the generated
    rule was never seen by anyone. If the model failed it said the same thing.

    A written instruction becomes a draft that a person reads and approves; it
    does not become live policy on its own. The response now says which of those
    happened, and carries the draft.
    """
    ai_service: AIService = getattr(req.app.state, "ai_service", None)
    if not ai_service:
        raise HTTPException(status_code=503, detail="AI Service unavailable.")

    schema = {
        "type": "object",
        "properties": {
            "rule_name": {"type": "string"},
            "condition": {"type": "string"},
            "action": {"type": "string"},
            "plain_english": {"type": "string"},
        },
        "required": ["rule_name", "condition", "action", "plain_english"],
    }
    try:
        draft = await ai_service.generate_json_response(
            f"Turn this HR policy instruction into one rule.\n\nInstruction: {nl_prompt}\n\n"
            "condition: when the rule applies. action: what happens then, one of BLOCK, FLAG or LOG. "
            "plain_english: one sentence an employee would understand.",
            schema, task_type="policy_drafting")
    except Exception as e:
        logger.warning(f"policy drafting failed for {policy_id}: {e}")
        raise HTTPException(
            status_code=502,
            detail="The model could not turn that instruction into a rule. Try rewording it.")

    if not draft or not draft.get("condition"):
        raise HTTPException(
            status_code=502,
            detail="The model did not produce a usable rule from that instruction.")

    task_id = f"DRAFT-{random.getrandbits(48):012x}"
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if mongo_client:
        await mongo_client[settings.MONGO_DB_NAME]["policy_deployments"].insert_one({
            "task_id": task_id, "policy_id": policy_id, "prompt": nl_prompt,
            "draft": draft, "status": "AWAITING_REVIEW",
            "requested_by": payload.get("sub"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    return {
        "status": "AWAITING_REVIEW",
        "policy_id": policy_id,
        "task_id": task_id,
        "draft": draft,
        "message": ("This is a draft, not live policy. Review it and submit it through "
                    "the policy approval process to put it into effect."),
    }


@policy_router.get("/drafts/{policy_id}")
async def list_policy_drafts(req: Request, policy_id: str, limit: int = Query(20),
                             payload: Dict = Depends(policy_admin_role_required)):
    """Drafts written from an instruction and still waiting for review.

    Drafts were written to a collection that nothing read, so once the response
    was discarded there was no way to find them again.
    """
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        return {"policy_id": policy_id, "drafts": []}
    cursor = mongo_client[settings.MONGO_DB_NAME]["policy_deployments"].find(
        {"policy_id": policy_id}, {"_id": 0}
    ).sort("created_at", -1).limit(max(1, min(int(limit or 20), 100)))
    return {"policy_id": policy_id, "drafts": await cursor.to_list(length=100)}


# ======================================
# 16. DAO, COMPLIANCE, SOCIAL, INNOVATION ROUTES (Fixed/Complete)
# ======================================
@dao_router.get("/proposals/active")
async def get_active_proposals(req: Request, payload: Dict = Depends(employee_role_required)):
    """Real active DAO proposals from the Postgres governance ledger."""
    chaincode = getattr(req.app.state, "governance_chaincode", None)
    if not chaincode:
        raise HTTPException(status_code=503, detail="Governance service unavailable.")
    return await chaincode.list_active_proposals()

@dao_router.post("/vote")
async def cast_vote(req: Request, proposal_id: str = Body(...), vote: str = Body(...), voting_power: float = Body(...), payload: Dict = Depends(employee_role_required)):
    """Cast a real, persisted DAO vote through the governance chaincode (Postgres-backed)."""
    chaincode = getattr(req.app.state, "governance_chaincode", None)
    if not chaincode:
        raise HTTPException(status_code=503, detail="Governance service unavailable.")
    try:
        await chaincode.cast_vote({
            "proposal_id": proposal_id,
            "voter_id": payload.get("sub"),
            "vote": vote,
            "token_weight": voting_power,
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "Vote Cast", "proposal_id": proposal_id, "voter_id": payload.get("sub")}

@dao_router.get("/dashboard")
async def get_governance_dashboard_data(req: Request, payload: Dict = Depends(employee_role_required)):
    """Real DAO governance aggregates (matches the frontend contract)."""
    chaincode = getattr(req.app.state, "governance_chaincode", None)
    if not chaincode:
        raise HTTPException(status_code=503, detail="Governance service unavailable.")
    return await chaincode.get_governance_stats(getattr(req.app.state, "mongo_client", None))

@compliance_router.get("/dashboard")
async def get_compliance_dashboard_data(req: Request, payload: Dict = Depends(policy_admin_role_required)):
    """Real compliance aggregates from the policy_audit_log table.
    HRBP owns policy/compliance, so policy_admin (hrbp + hrit_admin) can view."""
    from services.enforcement_engine import get_compliance_overview
    # Pass the policy store so "the live policy set is the newest one" can
    # actually be checked rather than inferred from whether any decision exists.
    return await get_compliance_overview(getattr(req.app.state, "policy_versioning_service", None))

@compliance_router.post("/monitor_feeds")
async def monitor_regulatory_feeds(req: Request, jurisdictions: List[str] = Body(..., embed=True), payload: Dict = Depends(policy_admin_role_required)):
    """Record which jurisdictions are being watched.

    This used to return "Monitoring Started" without storing anything. The
    subscription is now persisted, and the response says plainly whether a live
    feed is attached or only the intent has been recorded.
    """
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        raise HTTPException(status_code=503, detail="Subscription store unavailable.")
    now = datetime.now(timezone.utc).isoformat()
    col = mongo_client[settings.MONGO_DB_NAME]["regulatory_subscriptions"]
    for j in jurisdictions:
        await col.update_one(
            {"jurisdiction": j},
            {"$set": {"jurisdiction": j, "requested_by": payload.get("sub"), "updated_at": now}},
            upsert=True,
        )
    live = bool(getattr(settings, "ENABLE_POLICY_SCRAPING", False))
    return {
        "status": "Subscription recorded",
        "jurisdictions": jurisdictions,
        "live_feed_active": live,
        "note": "The policy scraping agent is running and will apply updates."
                if live else
                "Saved. Updates will be applied once the policy scraping agent is enabled.",
    }
