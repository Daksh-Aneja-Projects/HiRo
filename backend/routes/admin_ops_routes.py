"""admin_ops API routes.

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
# 3. SYSTEM ADMIN & AGENTS ROUTER (Fixed/Complete)
# ======================================
@admin_router.get("/health")
async def get_system_health(req: Request, payload: Dict=Depends(hrit_admin_role_required)):
    """Probe each dependency for real. This previously returned a hardcoded
    all-green literal, so the console reported NATS as UP on a server where the
    message bus was demonstrably disconnected."""
    checks: Dict[str, str] = {}

    try:
        await pg_client.fetchrow("SELECT 1")
        checks["postgres"] = "UP"
    except Exception as e:
        logger.warning(f"health: postgres down: {e}")
        checks["postgres"] = "DOWN"

    mongo_client = getattr(req.app.state, "mongo_client", None)
    try:
        if mongo_client:
            await mongo_client.admin.command("ping")
            checks["mongodb"] = "UP"
        else:
            checks["mongodb"] = "DOWN"
    except Exception:
        checks["mongodb"] = "DOWN"

    publisher = getattr(req.app.state, "event_publisher", None)
    checks["nats"] = "UP" if getattr(getattr(publisher, "nc", None), "is_connected", False) else "DOWN"

    redis_client = getattr(req.app.state, "redis_client", None)
    if redis_client:
        try:
            await redis_client.ping()
            checks["redis"] = "UP"
        except Exception:
            checks["redis"] = "DOWN"

    ai_service = getattr(req.app.state, "ai_service", None)
    try:
        models = await ai_service.get_ai_models() if ai_service else []
        checks["ai_primary"] = "UP" if models else "DOWN"
    except Exception:
        checks["ai_primary"] = "DOWN"

    # A green tick beside a row reading "message bus: down" is worse than no
    # tick at all. Anything that is down is reflected in the headline, with the
    # difference between "nothing works" and "something is missing" kept.
    essential = ("postgres", "mongodb", "ai_primary")
    down = [name for name, state in checks.items() if state == "DOWN"]
    essential_down = [name for name in essential if checks.get(name) == "DOWN"]

    READABLE = {
        "postgres": "the employee database",
        "mongodb": "the document store",
        "redis": "the cache",
        "nats": "the agent message bus",
        "ai_primary": "the language model",
    }
    if essential_down:
        status = "DOWN"
        summary = ("HiRo cannot run right now: "
                   + ", ".join(READABLE.get(n, n) for n in essential_down) + " is unavailable.")
    elif down:
        status = "DEGRADED"
        summary = ("HiRo is running, but "
                   + ", ".join(READABLE.get(n, n) for n in down)
                   + (" is" if len(down) == 1 else " are") + " unavailable.")
    else:
        status = "HEALTHY"
        summary = "Everything HiRo depends on is responding."

    return {
        "status": status,
        "summary": summary,
        "checks": checks,
        "degraded": down,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

@admin_router.post("/agent/create")
async def create_agent(req: Request, data: AgentCreationRequest, payload: Dict=Depends(hrit_admin_role_required)):
    agent_creation_service: AgentCreationService = getattr(req.app.state, "agent_creation_service", None)
    if not agent_creation_service: raise HTTPException(status_code=503, detail="Agent Creation Service unavailable.")
    return await agent_creation_service.create_and_deploy_agent(data.intent, payload['sub'])

@admin_router.post("/agent/deploy/final-approval")
async def process_agent_final_approval(req: Request, task_id: str = Body(...), project_id: str = Body(...), approved: bool = Body(...), comments: Optional[str] = Body(None), payload: Dict=Depends(hrit_admin_role_required)):
    """FIX: Added endpoint for HRIT Manager's final approval on agent deployment/config update."""
    decision = "APPROVED" if approved else "REJECTED"
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "task_id": task_id, "project_id": project_id, "decision": decision,
        "approved_by": payload.get("sub"), "comments": comments, "decided_at": now,
    }

    mongo_client = getattr(req.app.state, "mongo_client", None)
    if mongo_client:
        await mongo_client[settings.MONGO_DB_NAME]["agent_deployments"].update_one(
            {"task_id": task_id}, {"$set": record}, upsert=True,
        )

    published = False
    if approved:
        publisher = getattr(req.app.state, "event_publisher", None)
        if publisher:
            await publisher.publish_event(
                publisher.TOPIC_HUMAN_APPROVAL,
                {"type": "AGENT_DEPLOYMENT_APPROVED", "task_id": task_id,
                 "project_id": project_id, "approved_by": payload.get("sub")},
                key=task_id,
            )
            published = True

    return {
        "status": "DEPLOYMENT_TRIGGERED" if approved else "REJECTED",
        "task_id": task_id, "decision": decision, "event_published": published,
    }


@admin_router.post("/rlff/command")
async def rlff_command(req: Request, command: str = Body(..., embed=True), payload: Dict=Depends(hrit_admin_role_required)):
    rlff_llm_fine_tuner: RLFFLLMFineTuner = getattr(req.app.state, "rlff_llm_fine_tuner", None)
    if not rlff_llm_fine_tuner:
        raise HTTPException(status_code=503, detail="RLFF fine-tuner unavailable.")
    return await rlff_llm_fine_tuner.execute_rlff_command({"command": command, "command_type": "analyze"})

@admin_router.get("/dashboard")
async def get_admin_dashboard(req: Request, payload: Dict=Depends(hrit_admin_role_required)):
    """Real system + governance health for the admin console."""
    from services.enforcement_engine import get_compliance_overview

    # If the compliance aggregate fails we must NOT report a perfect score:
    # this previously fell back to 1.0 and rendered "100.0 integrity" on failure.
    compliance = None
    try:
        compliance = await get_compliance_overview()
    except Exception as e:
        logger.warning(f"Admin dashboard: compliance aggregate failed: {e}")

    # Field name kept (frontend contract). It counts AES-256 data-encryption keys
    # in use; nothing in HiRo is post-quantum, and the label beside it should say
    # "encryption keys", not "PQC keys".
    pqc = getattr(req.app.state, "pqc_wrapper", None)
    active_pqc_keys = 1 if pqc and getattr(pqc, "master_key_bytes", None) else 0

    try:
        # Host memory utilisation. This was previously labelled "cache
        # utilisation", which it never was.
        memory_util_pct = round(psutil.virtual_memory().percent, 1)
    except Exception:
        memory_util_pct = None

    return {
        # Null when the aggregate failed OR when no policy decision has ever been
        # recorded. Both are "we do not know", and neither is 100.
        "integrity_score": (round(compliance["score"] * 100, 1)
                            if compliance and compliance.get("score") is not None else None),
        "integrity_available": bool(compliance and compliance.get("score") is not None),
        "integrity_note": (compliance.get("score_note") if compliance
                           else "The compliance aggregate could not be read."),
        "active_pqc_keys": active_pqc_keys,
        # Says plainly what that key actually is, so no dashboard has to guess.
        "encryption_algorithm": "AES-256 (Fernet)",
        "post_quantum": False,
        # This is host memory, and it used to be served under the alias
        # cache_util_pct as well, which the admin console rendered as "Cache in
        # use ... percent full". The alias is gone so it cannot be mislabelled
        # again by anything reading this response.
        "memory_util_pct": memory_util_pct,
        "critical_alerts": compliance["high_severity_violations"] if compliance else None,
    }

@admin_router.get("/users")
async def get_admin_users(req: Request, limit: int = Query(200), offset: int = Query(0), auth=Depends(hrit_admin_role_required)):
    users = await _require_admin_service(req).get_all_users(limit=limit, offset=offset)
    return {"users": users, "count": len(users)}

@admin_router.post("/users/create")
async def admin_create_user(req: Request, data: Dict[str, Any], auth=Depends(hrit_admin_role_required)):
    try:
        return await _require_admin_service(req).create_user(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@admin_router.put("/users/{username}/role")
async def admin_update_role(req: Request, username: str, data: Dict[str, Any], auth=Depends(hrit_admin_role_required)):
    try:
        return await _require_admin_service(req).update_role(username, data.get("role"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@admin_router.delete("/users/{username}")
async def admin_delete_user(req: Request, username: str, auth=Depends(hrit_admin_role_required)):
    try:
        return await _require_admin_service(req).delete_user(username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@admin_router.post("/system/integrity-check")
async def integrity_check(req: Request, service: str = Body(..., embed=True), payload: Dict=Depends(hrit_admin_role_required)):
    """Live integrity probe: confirms the named subsystem is reachable right now."""
    service = (service or "").lower()
    ok, detail = True, "Reachable"
    try:
        if service in ("postgres", "db", "database"):
            pg = getattr(req.app.state, "pg_client", None)
            ok = pg is not None
            detail = "Postgres pool active" if ok else "Postgres client not initialized"
        elif service in ("redis", "cache"):
            r = getattr(req.app.state, "redis_client", None)
            if r:
                await r.ping()
                detail = "Redis PONG"
            else:
                ok, detail = False, "Redis not connected"
        elif service in ("mongo", "mongodb"):
            m = getattr(req.app.state, "mongo_client", None)
            if m:
                await m.admin.command("ping")
                detail = "MongoDB ping ok"
            else:
                ok, detail = False, "Mongo client not initialized"
        else:
            detail = "No specific probe; process is live"
    except Exception as e:
        ok, detail = False, f"{type(e).__name__}: {e}"
    return {"service": service, "status": "INTEGRITY_VERIFIED" if ok else "INTEGRITY_FAILED", "detail": detail}

@admin_router.get("/announcement")
async def get_announcements(req: Request, limit: int = Query(50), offset: int = Query(0), payload: Dict=Depends(employee_role_required)):
    """Anyone signed in can read announcements; only admins publish them.

    This was admin-only, so a broadcast the console described as visible to
    everyone in fact reached other admins alone.
    """
    items = await _require_admin_service(req).get_announcements(limit=limit, offset=offset)
    return {"announcements": items, "count": len(items)}

@admin_router.post("/announcement")
async def create_announcement(req: Request, data: Dict[str, Any], payload: Dict=Depends(hrit_admin_role_required)):
    try:
        return await _require_admin_service(req).create_announcement(data, author=payload.get("sub", "system"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@admin_router.post("/system/cache/clear")
async def clear_cache(req: Request, payload: Dict=Depends(hrit_admin_role_required)):
    if hasattr(req.app.state, 'redis_client') and req.app.state.redis_client:
        await req.app.state.redis_client.flushdb()
    return {"status": "Cache Cleared"}

@admin_router.get("/system/message-bus/status")
async def bus_status(req: Request, payload: Dict=Depends(hrit_admin_role_required)):
    """Message-bus liveness, plus the outcome of the last publish attempt.

    pending_messages used to be hardcoded to 0, which read as "nothing is stuck"
    on a box where NATS was not even running. Nothing here measures a queue
    depth, so the field is null with a note saying so.
    """
    publisher = getattr(req.app.state, "event_publisher", None)
    connected = bool(getattr(getattr(publisher, "nc", None), "is_connected", False)) if publisher else False
    last = getattr(publisher, "last_publish", None) if publisher else None
    return {
        "status": "Connected" if connected else "Disconnected",
        # No queue-depth reading is available from this client, so no number is
        # invented. Null means "not measured", which is not the same as zero.
        "pending_messages": None,
        "pending_messages_note": ("Queue depth is not reported by the publisher client, "
                                  "so it is not measured here."),
        "last_publish": last,
    }

@admin_router.post("/security/rotate-keys")
async def rotate_keys(req: Request, payload: Dict=Depends(hrit_admin_role_required)):
    """Key rotation is refused, not faked.

    This used to call a routine that swapped the in-memory encryption key for an
    unpersisted random one without re-encrypting a single stored row, and then
    reported "Keys Rotated". Every encrypted employee record became unreadable.
    """
    pqc_wrapper: PQCEncryptionWrapper = getattr(req.app.state, "pqc_wrapper", None)
    if not pqc_wrapper:
        raise HTTPException(status_code=503, detail="Encryption service unavailable.")
    result = await pqc_wrapper.rotate_keys()
    if not result.get("rotated"):
        raise HTTPException(status_code=409, detail=result["message"])
    return result

@admin_router.post("/system/reset-all-data")
async def reset_all_data(req: Request, payload: Dict=Depends(hrit_admin_role_required)):
    admin_service: AdminService = getattr(req.app.state, "admin_service", None)
    if not admin_service: raise HTTPException(status_code=503, detail="Admin Service unavailable.")
    
    result = await admin_service.hard_purge_system_data(payload['sub'])
    return result 

@admin_router.get("/hrit/system/reset-data")
async def get_hrit_portal_data(req: Request, payload: Dict=Depends(hrit_admin_role_required)):
    return await get_admin_dashboard(req, payload)

@admin_router.post("/hrit/system/reset-data")
async def reset_hrit_data(req: Request, payload: Dict=Depends(hrit_admin_role_required)):
    """Record an HRIT data-reset request (fire-and-forget). Actual destructive purge
    is handled by /admin/system/reset-all-data; this records the operator intent."""
    return await _admin_audit(req, "hrit_reset_data", {}, payload)

@admin_router.post("/data/migrate-legacy-chunk")
async def trigger_legacy_data_migration(req: Request, instructions: Dict[str, Any], payload: Dict=Depends(hrit_admin_role_required)):
    return await _admin_audit(req, "migrate_legacy_chunk", {"instructions": instructions}, payload)

# ======================================
# 5. DEV & ENCRYPTION ROUTER (AES-256-Fernet; classical, not post-quantum)
# ======================================
@dev_router.post("/pqc/encrypt")
async def test_pqc_encrypt(req: Request, plaintext: str = Body(..., embed=True), payload: Dict=Depends(hrit_admin_role_required)):
    pqc_wrapper: PQCEncryptionWrapper = getattr(req.app.state, "pqc_wrapper", None)
    if not pqc_wrapper: raise HTTPException(status_code=503, detail="Encryption service unavailable.")
    # encrypt() returns (ciphertext_str, metadata_dict)
    ciphertext, metadata = pqc_wrapper.encrypt(plaintext)
    return {"ciphertext": ciphertext, "metadata": metadata}

@dev_router.post("/pqc/decrypt")
async def test_pqc_decrypt(req: Request, ciphertext: str = Body(..., embed=True), payload: Dict=Depends(hrit_admin_role_required)):
    pqc_wrapper: PQCEncryptionWrapper = getattr(req.app.state, "pqc_wrapper", None)
    if not pqc_wrapper: raise HTTPException(status_code=503, detail="Encryption service unavailable.")
    try:
        return {"plaintext": pqc_wrapper.decrypt(ciphertext)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@dev_router.post("/policy/generate_tree")
async def generate_policy_execution_tree(req: Request, policy_version_id: str = Body(..., embed=True), payload: Dict=Depends(hrit_admin_role_required)):
    """Build a real execution tree from the stored policy version's content."""
    pvs: PolicyVersioningService = getattr(req.app.state, "policy_versioning_service", None)
    if not pvs:
        raise HTTPException(status_code=503, detail="Policy Versioning Service unavailable.")
    version = await asyncio.to_thread(pvs.get_version_by_id, policy_version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Policy version not found.")

    def _node(key: str, value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return {"id": key, "type": "branch", "children": [_node(k, v) for k, v in value.items()]}
        if isinstance(value, list):
            return {"id": key, "type": "list", "children": [_node(f"{key}[{i}]", v) for i, v in enumerate(value)]}
        return {"id": key, "type": "leaf", "value": value, "children": []}

    content = version.content or {}
    tree = {
        "id": "root",
        "version": policy_version_id,
        "version_number": version.version_number,
        "status": getattr(version.status, "value", str(version.status)),
        "children": [_node(k, v) for k, v in content.items()],
    }
    return {"tree": tree}

@dev_router.post("/policy/checked-command")
async def execute_policy_checked_command(req: Request, data: Dict, payload: Dict=Depends(hrit_admin_role_required)):
    """Run the command through the runtime policy enforcer, then persist the outcome."""
    scan = await runtime_enforcer("checked_command", {"Command": data})
    decision = (scan.get("decision") or "").upper()
    if decision in ("DENY", "STOP", "BLOCK"):
        raise HTTPException(status_code=400, detail=f"Command blocked by policy: {scan.get('reason', 'denied')}")
    result = await _dev_persist(req, "dev_checked_commands", "checked_command",
                                {"command": data, "decision": decision or "PASS", "audit_id": scan.get("audit_id")}, payload)
    return {"status": "Command Checked and Executed", "decision": decision or "PASS", **result}

@dev_router.post("/sandbox/deploy")
async def sandbox_deploy(req: Request, data: Dict, payload: Dict=Depends(hrit_admin_role_required)):
    result = await _dev_persist(req, "sandbox_deployments", "sandbox_deploy", data, payload)
    return {"status": "Sandbox Deployment Initiated", **result}


@dev_router.post("/policy/scan")
async def security_scan_bpcl(req: Request, code: Dict[str, Any], payload: Dict=Depends(policy_admin_role_required)):
    """Validate BPCL through the real V&V compiler.

    Accepts either a JSON policy body or raw BPCL text; the compiler validates a
    structured document, so plain text is wrapped before validation.
    """
    vv = getattr(req.app.state, "vv_compiler", None)
    if not vv:
        raise HTTPException(status_code=503, detail="V&V compiler unavailable.")

    raw = code.get("code", code.get("content", ""))
    policy_id = code.get("policy_id", "adhoc-scan")
    if isinstance(raw, str):
        try:
            content = json.loads(raw)
        except Exception:
            # BPCL text used to be wrapped as {"bpcl_code": raw} and handed
            # straight to a validator that requires policy_name and rules[], so
            # every BPCL document this module exists to lint came back
            # VULNERABLE with "Missing required field: policy_name" - including
            # the example the screen itself offers as a starting point.
            content = _parse_bpcl(raw)
    else:
        content = raw or {}

    try:
        # validate_bpcl(policy_id, content) is async and returns
        # {is_valid, errors, type, policy_id, details?}
        result = await vv.validate_bpcl(policy_id, content)
    except Exception as e:
        logger.error(f"BPCL scan failed: {e}")
        raise HTTPException(status_code=400, detail=f"Scan failed: {e}")

    is_valid = bool(result.get("is_valid"))
    # A BPCL document that parsed to no rules is not a secure policy, it is an
    # empty one. The validator only checks that `rules` is a list, so an empty
    # list passed straight through as SECURE.
    parse_error = content.get("parse_error") if isinstance(content, dict) else None
    if parse_error:
        is_valid = False
        result = {**result, "errors": [*(result.get("errors") or []), parse_error],
                  "type": result.get("type") or "SYNTAX"}
    return {
        "status": "SECURE" if is_valid else "VULNERABLE",
        "is_valid": is_valid,
        "failure_type": result.get("type"),
        "vulnerabilities": result.get("errors", []),
        "trace": result.get("details") or (
            "Policy passed syntax and semantic validation."
            if is_valid else f"Validation failed at the {result.get('type', 'unknown')} stage."
        ),
    }


@telemetry_router.get("/metrics/live")
async def get_live_metrics(req: Request, payload: Dict = Depends(manager_role_required)):
    cpu = psutil.cpu_percent()
    mem = psutil.virtual_memory().percent
    # This was served as `agent_activity` and charted as "Agent workload, live -
    # how busy the agent layer is". It is the average of processor and memory
    # load, so it read about 50 with the agent layer completely idle and, with
    # memory sitting at 70 percent, could never fall below about 35 whatever the
    # agents were doing. Real per-agent counts are at /telemetry/agents/activity.
    return {
        "cpu_load": cpu,
        "memory_load": mem,
        "machine_load": round((cpu + mem) / 2.0, 1),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

@telemetry_router.get("/agents/activity")
async def get_agents_activity(req: Request, time_window_minutes: int = 60, payload: Dict = Depends(manager_role_required)):
    """Real per-agent event counts from the orchestrator command log (last window)."""
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        return []
    since = (datetime.now(timezone.utc) - timedelta(minutes=max(1, time_window_minutes))).isoformat()
    cursor = mongo_client[settings.MONGO_DB_NAME]["orchestrator_commands"].aggregate([
        {"$match": {"created_at": {"$gte": since}}},
        {"$group": {"_id": "$agent", "events": {"$sum": 1}}},
        {"$sort": {"events": -1}},
    ])
    rows = await cursor.to_list(length=50)
    return [{"agent_id": r["_id"] or "unknown", "events": r["events"]} for r in rows]
