"""talent_ext API routes.

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
# 9. TA (Talent Acquisition) ROUTER (Fixed/Complete)
# ======================================
@ta_router.get("/snapshot")
async def get_talent_pool_snapshot(req: Request, payload: Dict = Depends(manager_role_required)):
    """Talent pools derived from the real workforce and open requisitions."""
    ta_service: TalentAcquisitionService = getattr(req.app.state, "ta_service", None)
    if not ta_service: raise HTTPException(status_code=503, detail="Talent Acquisition Service unavailable.")
    return await ta_service.get_talent_pool_snapshot(
        mongo_client=getattr(req.app.state, "mongo_client", None),
        db_name=settings.MONGO_DB_NAME,
    )
        
@ta_router.post("/predict_risk")
async def predict_ta_pipeline_risk(req: Request, scenario_data: Dict = Body(..., embed=True), payload: Dict = Depends(manager_role_required)):
    """Talent pipeline risk via the real scenario simulator."""
    ta_service: TalentAcquisitionService = getattr(req.app.state, "ta_service", None)
    if not ta_service: raise HTTPException(status_code=503, detail="Talent Acquisition Service unavailable.")
    snapshot = await ta_service.get_talent_pool_snapshot()
    risk = await ta_service.simulate_talent_scenario(scenario_data, snapshot)
    level = "HIGH" if risk >= 0.66 else "MEDIUM" if risk >= 0.33 else "LOW"
    return {
        "risk_score": round(risk, 3),
        "risk_level": level,
        "scenario": scenario_data,
        # Time-to-close and acceptance rate are not tracked here, so the score
        # partly rests on industry defaults. The response says which ones.
        **ta_service.assumed_inputs(snapshot),
    }

@talent_content_router.post("/job-description/generate")
async def generate_job_description(req: Request, data: Dict, payload: Dict = Depends(manager_role_required)):
    return await _generate_jd(req, data)

@talent_content_router.post("/job-description/generate-draft")
async def generate_jd_draft(req: Request, data: Dict, payload: Dict = Depends(manager_role_required)):
    return await _generate_jd(req, data)

# ======================================
# 11. TALENT EXP ROUTER
# ======================================
@talent_exp_router.get("/digital-twin/xai")
async def get_digital_twin_xai(req: Request, payload: Dict = Depends(employee_role_required)):
    """Explain THIS employee's own retention outlook.

    Previously this explained workforce-wide averages, so every employee saw the
    same explanation about the whole organisation rather than about themselves.
    """
    wfm_service = getattr(req.app.state, "wfm_service", None)
    xai: XAIWrapper = getattr(req.app.state, "xai_wrapper", None)
    employee_uuid = payload.get("employee_uuid")
    if not (wfm_service and xai and employee_uuid):
        raise HTTPException(status_code=503, detail="Digital twin explainability unavailable.")

    prediction = await wfm_service.predict_attrition_risk({"employee_id": employee_uuid})
    explanation = xai.explain_prediction(
        prediction.get("feature_vector_used", {}), prediction.get("risk_score")
    )
    return {
        **explanation,
        "employee_uuid": employee_uuid,
        "risk_level": prediction.get("risk_level"),
        "recommendation": prediction.get("recommendation"),
    }

@talent_exp_router.post("/learning/synthesize/{employee_id}")
async def synthesize_learning_curriculum(req: Request, employee_id: str, target_role: Optional[str] = Body(None, embed=True), payload: Dict = Depends(employee_role_required)):
    learning_agent: ImmersiveLearningAgent = getattr(req.app.state, "immersive_learning_agent", None)
    if not learning_agent: raise HTTPException(status_code=503, detail="Immersive Learning Agent unavailable.")
    return await learning_agent.synthesize_personalized_curriculum(employee_id, target_role or "future_role")

@talent_exp_router.get("/learning-modules")
async def get_learning_modules(req: Request, payload: Dict = Depends(employee_role_required)):
    """Real learning catalog from the Mongo learning_modules collection (empty until seeded)."""
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        return {"modules": []}
    cursor = mongo_client[settings.MONGO_DB_NAME]["learning_modules"].find({}, {"_id": 0}).limit(200)
    return {"modules": await cursor.to_list(length=200)}

# ======================================
# 14. INGESTION ROUTER (Fixed/Complete)
# ======================================
@ingestion_router.post("/upload")
async def upload_ingestion_file(req: Request, file: UploadFile = File(...), payload: Dict=Depends(policy_admin_role_required)):
    """Record a real ingestion job: the document is read, sized, content-hashed and
    persisted so the ingestion queue and history reflect actual uploads."""
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        raise HTTPException(status_code=503, detail="Ingestion store unavailable.")
    contents = await file.read()
    digest = hashlib.sha256(contents).hexdigest()
    doc = {
        # The id used to be derived from the content, so uploading the same file
        # twice produced two rows sharing one id. The history list keys its rows
        # on it, and React collapsed them into one.
        "job_id": f"ING-{uuid.uuid4().hex[:10].upper()}",
        "filename": file.filename,
        "content_type": file.content_type,
        "size_bytes": len(contents),
        "content_sha256": digest,
        "status": "INGESTED",
        "uploaded_by": payload.get("sub"),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }
    # Say plainly when this file has been through before rather than silently
    # recording it a second time.
    previous = await mongo_client[settings.MONGO_DB_NAME]["ingestion_jobs"].count_documents(
        {"content_sha256": digest})
    await mongo_client[settings.MONGO_DB_NAME]["ingestion_jobs"].insert_one(dict(doc))

    # Parse + index text-extractable uploads into the RAG corpus so newly
    # uploaded documents become answerable through /api/knowledge/ask.
    # Anything not text-extractable is reported as unsupported, not silently
    # dropped (see routes/ai_knowledge_routes.py / services/retrieval.py).
    ext = ("." + file.filename.rsplit(".", 1)[-1].lower()) if file.filename and "." in file.filename else ""
    ai_service = getattr(req.app.state, "ai_service", None)
    if ext not in (".txt", ".md", ".csv"):
        indexing = {"status": "unsupported",
                    "reason": f"'{ext or 'unknown'}' files are not text-extractable yet; only .txt, .md, .csv are indexed."}
    elif not ai_service:
        indexing = {"status": "skipped", "reason": "AI service unavailable."}
    else:
        try:
            from services.retrieval import index_text
            chunks = await index_text(ai_service, "document", doc["job_id"], file.filename,
                                       contents.decode("utf-8", errors="replace"))
            indexing = {"status": "indexed", "chunks": chunks}
        except Exception as e:
            logger.warning(f"Indexing upload {file.filename} failed: {e}")
            indexing = {"status": "error", "reason": "Indexing failed; the file was stored but is not searchable yet."}

    return {
        "status": "Ingested",
        **doc,
        "indexing": indexing,
        "message": (f"{file.filename} was stored." if not previous else
                    f"{file.filename} was stored. The same file has been uploaded "
                    f"{previous} time{'s' if previous != 1 else ''} before."),
    }

@ingestion_router.get("/jobs")
async def list_ingestion_jobs(req: Request, limit: int = Query(20), payload: Dict=Depends(policy_admin_role_required)):
    """Real ingestion history for the status panel."""
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        return {"jobs": [], "pending": 0}
    lim = max(1, min(int(limit or 20), 200))
    col = mongo_client[settings.MONGO_DB_NAME]["ingestion_jobs"]
    jobs = await col.find({}, {"_id": 0}).sort("uploaded_at", -1).limit(lim).to_list(length=lim)
    # Every job is written with status INGESTED and nothing ever changes it, so
    # this count is structurally always zero. The panel presented it as live
    # queue depth, which implied a queue that does not exist: upload is
    # synchronous and there is nothing waiting behind it.
    total = await col.count_documents({})
    return {
        "jobs": jobs,
        "pending": 0,
        "total": total,
        "note": "Files are stored as they arrive, so nothing queues behind them.",
    }
