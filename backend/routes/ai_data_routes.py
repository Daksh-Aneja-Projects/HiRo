"""ai_data API routes.

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
# 4. DATA & XAI ROUTER (Fixed/Complete)
# ======================================
@data_router.post("/xai/explain")
async def explain_prediction(req: Request, model_name: str = Body(...), prediction_input: Dict = Body(...), payload: Dict=Depends(manager_role_required)):
    wfm_service = getattr(req.app.state, "wfm_service", None)
    xai: XAIWrapper = getattr(req.app.state, "xai_wrapper", None) 
    if not wfm_service or not xai: raise HTTPException(status_code=503, detail="WFM or XAI Service unavailable.")
    
    prediction = await wfm_service.predict_attrition_risk(prediction_input)
    feature_vector = prediction.get('feature_vector_used', prediction_input)
    # Report the adjustments the model actually made. Recomputing them with the
    # explainer's own weights produced a breakdown that disagreed with the score
    # it was explaining. Older predictions without a driver list fall back.
    explanation = (xai.explain_drivers(prediction) if prediction.get("drivers")
                   else xai.explain_prediction(feature_vector, prediction.get('risk_score')))
    return {
        **explanation,
        "risk_level": prediction.get("risk_level"),
        "recommendation": prediction.get("recommendation"),
        "employee_uuid": prediction.get("employee_uuid"),
    }

@data_router.get("/xai/audit/{model_name}")
async def get_model_audit_log(req: Request, model_name: str, limit: int = Query(10), payload: Dict=Depends(hrit_admin_role_required)):
    """Decisions the policy engine made, optionally narrowed to one trigger.

    This used to select every row in policy_audit_log unfiltered and stamp the
    name from the URL onto each one, so /xai/audit/anything_at_all returned the
    same rows labelled with whatever was asked for. They are policy decisions,
    not model inferences, and they are now labelled as such.
    """
    lim = max(1, min(int(limit or 10), 500))
    # The path segment names a decision trigger (for example time_clock_in).
    # "all" or an unknown name returns everything rather than pretending to filter.
    trigger = None if model_name.lower() in ("all", "any", "*") else model_name.lower()
    try:
        if trigger:
            rows = await pg_client.fetch(
                """SELECT audit_id, decision_timestamp, policy_version, trigger_type, decision, reason
                   FROM policy_audit_log WHERE lower(trigger_type) = $1
                   ORDER BY decision_timestamp DESC LIMIT $2""",
                trigger, lim,
            )
            if not rows:
                # Nothing matched, so this was not a trigger name. Say so rather
                # than returning unrelated rows under that heading.
                known = await pg_client.fetch(
                    "SELECT DISTINCT trigger_type FROM policy_audit_log ORDER BY trigger_type")
                return {
                    "decisions": [],
                    "decision_type": model_name,
                    "message": (f"No decisions have been recorded for '{model_name}'. "
                                f"Recorded decision types: "
                                f"{', '.join(humanise(r['trigger_type']) for r in known) or 'none yet'}."),
                }
        else:
            rows = await pg_client.fetch(
                """SELECT audit_id, decision_timestamp, policy_version, trigger_type, decision, reason
                   FROM policy_audit_log ORDER BY decision_timestamp DESC LIMIT $1""",
                lim,
            )
    except Exception as e:
        logger.warning(f"policy decision audit query failed: {e}")
        return {"decisions": [], "decision_type": model_name, "message": "The decision log could not be read."}

    return {
        "decisions": [
            {"audit_id": r["audit_id"], "timestamp": str(r["decision_timestamp"]),
             "policy_version": r["policy_version"], "action": r["trigger_type"],
             "action_label": humanise(r["trigger_type"]),
             "decision": r["decision"], "reason": r.get("reason"),
             "decided_by": "policy engine"}
            for r in rows
        ],
        "decision_type": model_name,
    }

@data_router.post("/correction/{data_id}")
async def submit_data_correction(req: Request, data_id: str, corrections: Dict[str, Any] = Body(..., embed=True), payload: Dict=Depends(hrit_admin_role_required)):
    """Persist a data-correction request to Mongo for review/replay."""
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        raise HTTPException(status_code=503, detail="Correction store unavailable.")
    correction_id = f"CORR-{random.getrandbits(48):012x}"
    await mongo_client[settings.MONGO_DB_NAME]["data_corrections"].insert_one({
        "correction_id": correction_id, "data_id": data_id, "corrections": corrections,
        "submitted_by": payload.get("sub"), "status": "PENDING_REVIEW",
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"status": "Correction Submitted", "correction_id": correction_id,
            "data_id": data_id, "fields": list(corrections.keys())}


@data_router.post("/dtla/command")
async def dtla_command(req: Request, command_type: str = Body(...), data: Dict = Body(...), payload: Dict=Depends(manager_role_required)):
    dtla: DigitalTwinAgent = getattr(req.app.state, "digital_twin_agent", None) 
    if not dtla: raise HTTPException(status_code=503, detail="Digital Twin Agent unavailable.")
    
    data["command_type"] = command_type
    data["requester_id"] = payload['sub']
    return await dtla.execute_dtla_command(data)

# ======================================
# 12. AI ROUTER (Fixed/Complete)
# ======================================
@ai_router.post("/generate")
async def generate_text(req: Request, prompt: str = Body(...), system_instruction: str = Body(...), payload: Dict=Depends(employee_role_required)):
    ai_service: AIService = getattr(req.app.state, "ai_service", None)
    if not ai_service: raise HTTPException(status_code=503, detail="AI Service unavailable.")
    return await ai_service.generate_text(prompt, system_instruction)

@ai_router.post("/generate-bpmn")
async def generate_bpmn(req: Request, description: str = Body(...), domain: str = Body(...), payload: Dict=Depends(hrit_admin_role_required)):
    """Generate BPMN 2.0 XML for a described workflow using the local LLM."""
    ai_service: AIService = getattr(req.app.state, "ai_service", None)
    if not ai_service: raise HTTPException(status_code=503, detail="AI Service unavailable.")
    prompt = (
        f"Generate valid BPMN 2.0 XML for this {domain} workflow: {description}. "
        "Output only the XML, starting with <?xml. Include a bpmn:process with startEvent, "
        "at least two tasks, and an endEvent."
    )
    xml = await ai_service.generate_text(prompt, "You are a BPMN modeling expert. Output only BPMN 2.0 XML.")
    xml = _strip_code_fence(xml)
    if not xml.lstrip().startswith("<"):
        raise HTTPException(
            status_code=502,
            detail="The model did not return XML for that description. Try describing the steps more plainly.")
    return {"description": description, "domain": domain, "bpmn_xml": xml}

@ai_router.post("/workflow/save")
async def save_generated_workflow(req: Request, workflow_data: Dict, payload: Dict=Depends(hrit_admin_role_required)):
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client: raise HTTPException(status_code=503, detail="Store unavailable.")
    wid = f"WKF-{random.getrandbits(24):06x}"
    await mongo_client[settings.MONGO_DB_NAME]["saved_workflows"].insert_one({
        "workflow_id": wid, "data": workflow_data, "saved_by": payload.get("sub"),
        "saved_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"status": "Workflow Saved", "id": wid}

@ai_router.post("/embedding")
async def generate_embedding(req: Request, text: str = Body(..., embed=True), payload: Dict=Depends(employee_role_required)):
    ai_service: AIService = getattr(req.app.state, "ai_service", None)
    if not ai_service: raise HTTPException(status_code=503, detail="AI Service unavailable.")
    return {"embedding": await ai_service.generate_embedding(text)}

@ai_router.get("/models")
async def get_ai_models(req: Request, payload: Dict=Depends(employee_role_required)):
    ai_service: AIService = getattr(req.app.state, "ai_service", None)
    if not ai_service: raise HTTPException(status_code=503, detail="AI Service unavailable.")
    return {"models": await ai_service.get_ai_models()}

@ai_router.get("/provider/config")
async def get_active_ai_provider(req: Request, payload: Dict=Depends(hrit_admin_role_required)):
    """Report the real active LLM provider (local Ollama)."""
    return {
        "provider": "Ollama (local)",
        "base_url": getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434"),
        "default_model": getattr(settings, "OLLAMA_MODEL", getattr(settings, "DEFAULT_AI_MODEL", "llama3.1:8b")),
        "status": "Active",
    }

@ai_router.post("/provider/switch")
async def set_ai_provider(req: Request, provider: str = Body(..., embed=True), payload: Dict=Depends(hrit_admin_role_required)):
    """Switch the model the AI service uses, to one that is actually installed.

    This used to probe for a `set_default_model` method and a `default_model`
    attribute, neither of which exists on AIService (its field is `model`). So
    it created an orphan attribute, reported "Switched" for any string at all,
    including models that do not exist, and carried on serving from the old one.
    """
    ai_service: AIService = getattr(req.app.state, "ai_service", None)
    if not ai_service: raise HTTPException(status_code=503, detail="AI Service unavailable.")

    available = [m.get("name") for m in await ai_service.get_ai_models()]
    if provider not in available:
        raise HTTPException(
            status_code=400,
            detail=(f"'{provider}' is not installed on this machine. "
                    f"Available models: {', '.join(available) or 'none'}."))

    previous = ai_service.model
    ai_service.model = provider
    logger.info(f"AI model switched from {previous} to {provider} by {payload['sub']}")
    return {
        "status": "Switched",
        "previous_model": previous,
        "new_provider": provider,
        "message": f"HiRo is now answering with {provider}.",
    }

@ai_router.post("/command")
async def legacy_ai_command(req: Request, payload_data: Dict, payload: Dict=Depends(employee_role_required)):
    """Free-form AI command executed against the local LLM."""
    ai_service: AIService = getattr(req.app.state, "ai_service", None)
    if not ai_service: raise HTTPException(status_code=503, detail="AI Service unavailable.")
    prompt = payload_data.get("prompt") or payload_data.get("command") or ""
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required.")
    result = await ai_service.generate_text(prompt, "You are HiRo's assistant. Be concise and helpful.")
    return {"status": "COMPLETED", "result": result}

@ai_router.post("/twin/message/{reportee_id}")
async def send_digital_twin_message(req: Request, reportee_id: str, message: str = Body(..., embed=True), payload: Dict = Depends(manager_role_required)):
    """Persist a manager->digital-twin message and generate the twin's real AI reply."""
    ai_service: AIService = getattr(req.app.state, "ai_service", None)
    if not ai_service: raise HTTPException(status_code=503, detail="AI Service unavailable.")
    col = await _twin_messages(req)
    now = datetime.now(timezone.utc).isoformat()
    thread = f"{payload['sub']}:{reportee_id}"
    await col.insert_one({"thread": thread, "role": "manager", "sender": payload['sub'], "text": message, "ts": now})
    reply = await ai_service.generate_text(
        f"You are the digital twin of employee {reportee_id}. A manager says: '{message}'. "
        "Respond briefly in first person as that employee's twin.",
        "You are an employee digital twin. Be realistic and concise.",
    )
    await col.insert_one({"thread": thread, "role": "twin", "sender": reportee_id, "text": reply, "ts": datetime.now(timezone.utc).isoformat()})
    return {"status": "SENT", "reply": reply}

@ai_router.get("/twin/history/{user_id}")
async def get_digital_twin_history(req: Request, user_id: str, payload: Dict = Depends(employee_role_required)):
    """Real conversation history between the caller and a reportee's twin."""
    col = await _twin_messages(req)
    thread = f"{payload['sub']}:{user_id}"
    cursor = col.find({"thread": thread}, {"_id": 0}).sort("ts", 1).limit(200)
    return await cursor.to_list(length=200)

@pii_router.post("/tokenize")
async def tokenize_pii(req: Request, value: str = Body(..., embed=True), payload: Dict=Depends(employee_role_required)):
    """Real reversible token via the AES-256-Fernet wrapper (ciphertext is the token)."""
    ciphertext, metadata = _pqc(req).encrypt(value, data_context="pii_tokenize")
    return {
        "token": ciphertext,
        "value_hash": hashlib.sha256(value.encode("utf-8")).hexdigest()[:16],
        "metadata": metadata,
    }

@pii_router.post("/update_consent")
async def update_user_consent(req: Request, consent_data: Dict, payload: Dict=Depends(employee_role_required)):
    """Upsert a real consent record keyed by (employee_uuid, purpose_id)."""
    employee_uuid = payload.get("employee_uuid")
    if not employee_uuid:
        raise HTTPException(status_code=404, detail="No employee record linked to this account.")
    purpose_id = consent_data.get("purpose_id")
    if not purpose_id:
        raise HTTPException(status_code=400, detail="purpose_id is required.")
    # Accept the field under any of the names callers reasonably use, and REQUIRE
    # one of them. Silently defaulting to False meant the UI could report
    # "consent granted" while the record said the opposite.
    for key in ("granted", "consent_granted", "consent"):
        if key in consent_data:
            granted = bool(consent_data[key])
            break
    else:
        raise HTTPException(status_code=400, detail="A consent decision (granted) is required.")
    await _consents(req).update_one(
        {"employee_uuid": employee_uuid, "purpose_id": purpose_id},
        {"$set": {"granted": granted, "updated_by": payload.get("sub"),
                  "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return {"status": "Consent Updated", "purpose_id": purpose_id, "granted": granted}

@pii_router.post("/unmask")
async def get_unmasked_pii(req: Request, token: str = Body(..., embed=True), reason: str = Body(..., embed=True), payload: Dict=Depends(employee_role_required)):
    """Decrypt a PII token via the AES-256 encryption wrapper. Every access is logged to Mongo
    pii_access_log with the caller-supplied reason. Denies on invalid/empty input."""
    reason = (reason or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="A reason is required to unmask PII.")
    mongo_client = getattr(req.app.state, "mongo_client", None)
    now = datetime.now(timezone.utc).isoformat()
    try:
        plaintext = _pqc(req).decrypt(token, data_context="pii_unmask")
        outcome = "GRANTED"
    except ValueError:
        outcome = "DENIED_INVALID_TOKEN"
        plaintext = None
    if mongo_client:
        await mongo_client[settings.MONGO_DB_NAME]["pii_access_log"].insert_one({
            "actor": payload.get("sub"), "employee_uuid": payload.get("employee_uuid"),
            "reason": reason, "outcome": outcome,
            "token_hash": hashlib.sha256(token.encode("utf-8")).hexdigest()[:16], "accessed_at": now,
        })
    if plaintext is None:
        raise HTTPException(status_code=400, detail="Invalid token; access denied and logged.")
    return {"unmasked_value": plaintext, "reason": reason, "outcome": outcome}

@pii_router.post("/reveal-self")
async def reveal_own_pii(req: Request, reason: str = Body("Employee viewed their own protected fields", embed=True),
                         payload: Dict=Depends(employee_role_required)):
    """Decrypt the caller's OWN protected fields and log the access.

    The generic /pii/unmask endpoint takes a ciphertext token, which a browser
    never has. This is the employee-facing equivalent: it decrypts server-side,
    only ever for the caller's own record, and writes an audit entry.
    """
    employee_uuid = payload.get("employee_uuid")
    if not employee_uuid:
        raise HTTPException(status_code=404, detail="No employee record linked to this account.")

    hr = _hr(req)
    # Only the columns that actually exist on employee_pii.
    query = "SELECT full_name_encrypted, email_encrypted FROM employee_pii WHERE employee_uuid = $1"
    rows = await hr.vault.execute_pii_query(query, "employee_pii", "SelfService", None, employee_uuid)
    if not rows:
        raise HTTPException(status_code=404, detail="No protected fields are held for your record.")

    row = rows[0]
    fields = {
        "Full name": row.get("full_name"),
        "Email": row.get("email"),
    }
    revealed = {k: v for k, v in fields.items() if v}

    mongo_client = getattr(req.app.state, "mongo_client", None)
    if mongo_client:
        await mongo_client[settings.MONGO_DB_NAME]["pii_access_log"].insert_one({
            "actor": payload.get("sub"), "employee_uuid": employee_uuid,
            "reason": (reason or "").strip() or "Self service reveal",
            "outcome": "GRANTED_SELF", "fields": list(revealed.keys()),
            "accessed_at": datetime.now(timezone.utc).isoformat(),
        })

    return {"fields": revealed, "reason": reason, "outcome": "GRANTED"}

@pii_router.get("/check_consent")
async def check_user_consent(req: Request, purpose_id: str = Query(...), payload: Dict=Depends(employee_role_required)):
    """Real consent check. Default DENY (False) when no explicit grant exists."""
    employee_uuid = payload.get("employee_uuid")
    if not employee_uuid:
        raise HTTPException(status_code=404, detail="No employee record linked to this account.")
    record = await _consents(req).find_one({"employee_uuid": employee_uuid, "purpose_id": purpose_id})
    return {"consent": bool(record and record.get("granted", False)), "purpose_id": purpose_id}

# ======================================
# 18. ORCHESTRATOR ROUTES (Fixed/Complete)
# ======================================
@orchestrator_router.get("/dashboard")
async def get_orchestrator_dashboard(req: Request, payload: Dict = Depends(manager_role_required)):
    """Live orchestrator health from real app.state agents + psutil."""
    state = req.app.state
    # Count the agents the orchestrator can actually dispatch to, not app.state
    # attribute names. The old count matched anything ending _agent or _service,
    # so it included plain CRUD services that dispatch nothing, and counted
    # ta_service and talent_acquisition_service twice because they are the same
    # object under two names.
    dispatchable = sorted(ROUTABLE_AGENTS)
    agents = len(dispatchable)
    try:
        cpu = round(psutil.cpu_percent(interval=0.1), 1)
        mem = round(psutil.virtual_memory().percent, 1)
    except Exception:
        logger.debug("psutil read failed", exc_info=True)
        cpu, mem = 0.0, 0.0
    publisher = getattr(state, "event_publisher", None)
    nats_up = bool(getattr(getattr(publisher, "nc", None), "is_connected", False)) if publisher else False
    # Health was computed from CPU and memory alone, so it reported GREEN in the
    # same response that said the message bus was down.
    if cpu >= 95 or mem >= 97:
        health, health_reason = "RED", "This machine is out of processor or memory headroom."
    elif cpu >= 85 or mem >= 90:
        health, health_reason = "AMBER", "This machine is running hot."
    elif not nats_up:
        health, health_reason = "AMBER", "The message bus is down, so background agent work is not running."
    elif not agents:
        health, health_reason = "AMBER", "No agents are registered, so nothing can be dispatched."
    else:
        health, health_reason = "GREEN", "Everything is running normally."

    # Both of these used to read the same in-memory `active_twins` dict, which
    # nothing on any live code path ever populates -- so the dashboard showed two
    # separate metrics that were structurally always 0. active_tasks now counts
    # real in-flight orchestrator commands from Mongo; active_twins reports the
    # in-memory registry it actually names, and null when there is no agent.
    dt_agent = getattr(state, "digital_twin_agent", None)
    active_twins = len(getattr(dt_agent, "active_twins", {}) or {}) if dt_agent else None

    active_tasks = None
    mongo_client = getattr(state, "mongo_client", None)
    if mongo_client is not None:
        try:
            active_tasks = await mongo_client[settings.MONGO_DB_NAME]["orchestrator_commands"] \
                .count_documents({"status": {"$nin": ["COMPLETED", "FAILED", "REJECTED"]}})
        except Exception as e:
            logger.warning(f"Orchestrator dashboard: could not count in-flight commands: {e}")

    return {
        "agents": agents,
        "agent_names": dispatchable,
        "active_twins": active_twins,
        "active_tasks": active_tasks,
        "active_tasks_note": ("Orchestrator commands that have not reached a final state."
                              if active_tasks is not None
                              else "The command store could not be read, so in-flight work is unknown."),
        "system_health": health,
        "health_reason": health_reason,
        "message_bus_connected": nats_up,
        "metrics": {"cpu": cpu, "memory": mem},
        "last_update": datetime.now(timezone.utc).isoformat(),
    }

@orchestrator_router.post("/implement-policy")
async def trigger_policy_implementation(req: Request, version_id: str = Body(...), initiator_id: str = Body(...), policy_id: str = Body(...), payload: Dict=Depends(hrit_admin_role_required)):
    """Trigger real policy-workflow deployment via the BPEL agent."""
    bpel_agent: BPELAgent = getattr(req.app.state, "bpel_agent", None)
    if not bpel_agent: raise HTTPException(status_code=503, detail="BPEL Agent unavailable.")
    try:
        result = await bpel_agent.deploy_policy_workflow(version_id, performed_by=payload["sub"])
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if result.get("status") == "FAILED":
        # A deployment that stopped is not a deployment that started.
        raise HTTPException(status_code=409, detail=result.get("message"))
    return result

@orchestrator_router.get("/history/{process_id}")
async def get_process_execution_history(req: Request, process_id: str, payload: Dict=Depends(hrit_admin_role_required)):
    """Every step a deployment actually took, in order.

    This query was correct but had no writer: nothing ever populated process_id
    or step_name, so it returned [] for every id that was ever asked for. The
    BPEL agent records each step as it performs it now.
    """
    try:
        rows = await pg_client.fetch(
            """SELECT step_name, status, audit_trail, updated_at FROM implementation_status
               WHERE process_id = $1 ORDER BY updated_at ASC""",
            process_id,
        )
    except Exception as e:
        logger.warning(f"deployment history query failed: {e}")
        rows = []
    if not rows:
        return {"process_id": process_id, "steps": [],
                "message": "Nothing has been recorded against this deployment."}
    return {
        "process_id": process_id,
        "steps": [{"step": r["step_name"], "status": r["status"],
                   "detail": _audit_detail(r.get("audit_trail")),
                   "updated_at": str(r["updated_at"])}
                  for r in rows],
    }

@command_router.post("/execute")
async def execute_orchestrator_command(req: Request, prompt: str = Body(..., embed=True), user_id: str = Body(..., embed=True), payload: Dict = Depends(hrit_admin_role_required)):
    """
    Unified endpoint for the frontend's natural language command bar (UnifiedCommandBar).
    """
    logger.info(f"Received Orchestrator Command from {user_id}: {prompt}")
    ai_service: AIService = getattr(req.app.state, "ai_service", None)
    if not ai_service: raise HTTPException(status_code=503, detail="AI Service unavailable.")

    # Command-bar memory: prior turns for this user are injected as context so
    # a follow-up command can reference what was asked before (surgical edit;
    # full logic lives in services/agent_memory.py).
    mongo_client = getattr(req.app.state, "mongo_client", None)
    memory_context = ""
    if mongo_client is not None:
        try:
            memory_context = agent_memory.context_block(await agent_memory.get_memory(mongo_client, user_id))
        except Exception as e:
            logger.warning(f"Command memory lookup failed: {e}")

    # Real intent routing: ask the LLM to pick the responsible agent, then produce a plan.
    routing_prompt = (
        (f"Conversation memory:\n{memory_context}\n\n" if memory_context else "") +
        f"Classify this HR operations command and choose exactly one agent from "
        f"[{', '.join(ROUTABLE_AGENTS)}]. "
        f"Command: '{prompt}'. Return strict JSON: {{\"agent\": <name>, \"summary\": <one sentence plan>}}."
    )
    raw = await ai_service.generate_text(routing_prompt, "You are an orchestration planner. Output only JSON.")
    try:
        routed = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
        agent = routed.get("agent", "AIService")
        summary = routed.get("summary", "Command processed.")
    except (ValueError, TypeError, AttributeError):
        agent, summary = "AIService", raw.strip()[:400]

    result_id = f"ORCH-{random.getrandbits(32):08x}"
    if mongo_client:
        await mongo_client[settings.MONGO_DB_NAME]["orchestrator_commands"].insert_one({
            "result_id": result_id, "prompt": prompt, "agent": agent, "summary": summary,
            "user_id": user_id, "status": "COMPLETED", "outcome": "not_executed",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        try:
            await agent_memory.record_turn(mongo_client, ai_service, user_id, payload.get("role"), "user", prompt)
            await agent_memory.record_turn(mongo_client, ai_service, user_id, payload.get("role"), "assistant", summary)
        except Exception as e:
            logger.warning(f"Command memory write failed: {e}")
    # This reported "COMPLETED" while only classifying the command: no agent was
    # ever invoked, so an operator was told their instruction had been carried out
    # when nothing had run.
    return {
        "status": "PLANNED",
        "agent": agent,
        "agent_role": ROUTABLE_AGENTS.get(agent, "handled directly"),
        "summary": summary,
        "result_id": result_id,
        "message": (f"This would be handled by the part of HiRo that {ROUTABLE_AGENTS.get(agent, 'answers directly')}. "
                    "Nothing has been carried out yet: open that area to act on it."),
    }

# /history MUST be declared before /status/{result_id}, or the path-param route
# captures "history" as a result_id and this 404s.
@command_router.get("/history")
async def get_command_history(req: Request, limit: int = Query(50), payload: Dict = Depends(employee_role_required)):
    """Recent orchestrator command history for the command console."""
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        return []
    lim = max(1, min(int(limit or 50), 200))
    cursor = mongo_client[settings.MONGO_DB_NAME]["orchestrator_commands"].find(
        {}, {"_id": 0}
    ).sort("created_at", -1).limit(lim)
    return await cursor.to_list(length=lim)

@command_router.get("/status/{result_id}")
async def get_command_status(req: Request, result_id: str, payload: Dict = Depends(employee_role_required)):
    """Real status/result lookup for a previously executed orchestrator command."""
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        raise HTTPException(status_code=503, detail="Command store unavailable.")
    doc = await mongo_client[settings.MONGO_DB_NAME]["orchestrator_commands"].find_one(
        {"result_id": result_id}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Command not found.")
    return doc

# ======================================
# 21. STREAMING & WEBSOCKETS (Fixed/Complete)
# ======================================
@streaming_router.get("/agents/config/stream")
async def stream_agent_configuration(req: Request, nl_prompt: str):
    agent: SelfCorrectingAgent = getattr(req.app.state, 'self_correcting_agent', None)
    if not agent: raise HTTPException(status_code=503, detail="Self-Correcting Agent service unavailable.")
    
    async def event_stream():
        try:
            async for message in agent.generate_and_fix_bpcl(nl_prompt):
                if message == "COMPLETE":
                    yield f"data: {json.dumps({'status': 'completed', 'timestamp': datetime.now(timezone.utc).isoformat(), 'final_code_hash': f'BPCL-{random.getrandbits(16)}' })}\n\n"
                    break
                
                yield f"data: {message}\n\n"
                await asyncio.sleep(0.1) 
        
        except Exception as e:
            logger.error(f"Streaming error in config stream: {e}", exc_info=True)
            yield f"data: {json.dumps({'status': 'error', 'message': f'🚨 Error in agent process: {str(e)}', 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"
            yield "data: DONE\n\n"
            
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@streaming_router.websocket("/ws/live-telemetry")
async def websocket_telemetry(websocket: WebSocket, client_id: str = "dashboard"):
    await websocket.accept()
    
    _ws_manager = websocket_manager
    await _ws_manager.connect(websocket, client_id)
    
    try:
        await websocket.send_json({
            "type": "connection_established",
            "client_id": client_id,
            "message": "Connected to live telemetry",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                if message.get("type") == "subscribe_telemetry":
                    _ws_manager.subscribe_telemetry(client_id)
                    await websocket.send_json({"type": "subscription_confirmed", "channels": ["telemetry"], "timestamp": datetime.now(timezone.utc).isoformat()})
                elif message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                await websocket.send_json({"type": "error", "message": str(e), "timestamp": datetime.now(timezone.utc).isoformat()})
            
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
    finally:
        _ws_manager.disconnect(client_id)
        logger.info(f"Client {client_id} disconnected from telemetry")
