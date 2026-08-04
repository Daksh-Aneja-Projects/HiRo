"""hr_core API routes.

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
# 6. HR MODULES ROUTER (Fixed/Complete)
# ======================================
@hr_router.get("/comp/{employee_id}")
async def get_comp(req: Request, employee_id: str, payload: Dict=Depends(manager_role_required)):
    """Salary is among the most sensitive fields we hold. HR roles may look up
    anyone; a line manager may only see their own direct reports."""
    hr_modules_service: HRModulesService = getattr(req.app.state, "hr_modules_service", None)
    if not hr_modules_service: raise HTTPException(status_code=503, detail="HR Modules Service unavailable.")

    role = (payload.get("role") or "").lower()
    if role == "manager":
        manager_uuid = payload.get("employee_uuid")
        try:
            row = await pg_client.fetchrow(
                "SELECT 1 AS ok FROM employee_pii WHERE employee_uuid = $1 AND manager_id = $2",
                employee_id, manager_uuid,
            )
        except Exception as e:
            logger.error(f"comp reporting-line check failed: {e}")
            raise HTTPException(status_code=500, detail="Could not verify the reporting line.")
        if not row:
            raise HTTPException(status_code=403, detail="You can only view compensation for your own direct reports.")

    return await hr_modules_service.get_employee_compensation(employee_id, payload['role'])

@hr_router.post("/comp/update")
async def update_comp(req: Request, data: CompensationUpdateRequest, payload: Dict=Depends(policy_admin_role_required)):
    """Record a pay change.

    This required hrit_admin, but the Compensation Workbench ships under HR
    Operations and only an HRBP ever opens it, so the save button returned 403
    for every person who could reach it.
    """
    hr_modules_service: HRModulesService = getattr(req.app.state, "hr_modules_service", None)
    if not hr_modules_service: raise HTTPException(status_code=503, detail="HR Modules Service unavailable.")
    return await hr_modules_service.update_compensation(
        data.employee_id,
        data.new_salary,
        data.new_grade,
        data.effective_date,
        payload['sub']
    )

# team-trend MUST be declared before /performance/{employee_id}, or the path
# param route captures "team-trend" as an employee_id.
@hr_router.get("/performance/team-trend")
async def get_team_performance(req: Request, month: Optional[str] = Query(None), year: Optional[int] = Query(None), payload: Dict=Depends(manager_role_required)):
    hr_modules_service: HRModulesService = getattr(req.app.state, "hr_modules_service", None)
    if not hr_modules_service: raise HTTPException(status_code=503, detail="HR Modules Service unavailable.")
    return await hr_modules_service.get_team_performance_trend()

@hr_router.get("/performance/{employee_id}")
async def get_perf(req: Request, employee_id: str, payload: Dict=Depends(manager_role_required)):
    """A line manager sees their own reports; HR roles see anyone."""
    hr_modules_service: HRModulesService = getattr(req.app.state, "hr_modules_service", None)
    if not hr_modules_service: raise HTTPException(status_code=503, detail="HR Modules Service unavailable.")
    scoped = await _scoped_employee_id(payload, employee_id)
    return await hr_modules_service.get_employee_performance(scoped, payload['role'])

@hr_router.get("/timesheets")
async def get_timesheets(req: Request, limit: int = Query(50), offset: int = Query(0), payload: Dict=Depends(employee_role_required)):
    hr_modules_service: HRModulesService = getattr(req.app.state, "hr_modules_service", None)
    if not hr_modules_service: raise HTTPException(status_code=503, detail="HR Modules Service unavailable.")
    return await hr_modules_service.get_timesheets(payload['sub'], limit=limit, offset=offset)

@hr_router.post("/timesheets")
async def submit_timesheet(req: Request, data: Dict, payload: Dict=Depends(employee_role_required)): 
    hr_modules_service: HRModulesService = getattr(req.app.state, "hr_modules_service", None)
    if not hr_modules_service: HTTPException(status_code=503, detail="HR Modules Service unavailable.")
    return await hr_modules_service.submit_timesheet(payload['sub'], data)

@hr_router.post("/timesheets/pre-check")
async def run_timesheet_pre_check(req: Request, data: Dict, payload: Dict=Depends(employee_role_required)):
    """Run the SAME policy engine that gates submission, without saving anything.

    This used to be an inline `hours > 40` literal with invented policy prose, so
    the pre-check could tell someone they were fine and submission could then
    refuse them (or the reverse). A dry run must use the real decision path.
    """
    from services.agent_spec_dsl import TriggerType

    try:
        hours = float(data.get("hours", 0) or 0)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="hours must be a number.")

    employee_uuid = payload.get("employee_uuid")
    jurisdiction = None
    if employee_uuid:
        try:
            row = await pg_client.fetchrow(
                "SELECT jurisdiction_code FROM employee_pii WHERE employee_uuid = $1", employee_uuid
            )
            jurisdiction = (row or {}).get("jurisdiction_code")
        except Exception as e:
            logger.warning(f"pre-check jurisdiction lookup failed: {e}")

    context = {
        "employee_id": employee_uuid,
        "Proposed": {"Hours": hours, "SubmittedDate": datetime.now(timezone.utc).isoformat()},
        "Policy_Context": {
            "jurisdiction": jurisdiction,
            "employment_type": data.get("employment_type", "FULL_TIME"),
            "total_hours_this_week": hours,
        },
    }

    try:
        result = await runtime_enforcer(TriggerType.TIME_CLOCK_IN.value, context)
    except Exception as e:
        logger.error(f"Timesheet pre-check enforcement failed: {e}")
        raise HTTPException(status_code=503, detail="The policy engine is unavailable, so this cannot be checked now.")

    decision = (result.get("decision") or "").upper()
    blocked = decision in ("DENY", "STOP", "BLOCK", "ERROR")
    reason = result.get("reason") or ("Blocked by policy" if blocked else "Within policy")
    return {
        "status": "FAIL" if blocked else "PASS",
        "decision": decision,
        "messages": [reason],
        "reason": reason,
        "audit_id": result.get("audit_id"),
        "jurisdiction": jurisdiction,
    }

@hr_router.get("/leave/balance")
async def get_leave_balance(req: Request, payload: Dict=Depends(employee_role_required)):
    hr_modules_service: HRModulesService = getattr(req.app.state, "hr_modules_service", None)
    if not hr_modules_service: raise HTTPException(status_code=503, detail="HR Modules Service unavailable.")
    employee_uuid = payload.get("employee_uuid")
    if not employee_uuid:
        raise HTTPException(status_code=404, detail="No employee record linked to this account.")
    return await hr_modules_service.get_employee_leave_balance(employee_uuid)

@hr_router.post("/leave/balance/{employee_id}")
async def set_leave_balance(req: Request, employee_id: str,
                            hours: float = Body(..., embed=True),
                            reason: str = Body("", embed=True),
                            payload: Dict = Depends(policy_admin_role_required)):
    """Grant or correct an employee's remaining leave entitlement.

    There was no way to do this anywhere in the product: entitlements only ever
    came from the initial seed, so HR could not grant a new starter their
    allowance, apply an annual reset, or correct a mistake.

    This sets what is left to take. Hours already taken are not disturbed.
    """
    if hours < 0:
        raise HTTPException(status_code=400, detail="An entitlement cannot be negative.")
    exists = await pg_client.fetchrow(
        "SELECT 1 AS ok FROM employee_pii WHERE employee_uuid = $1", employee_id)
    if not exists:
        raise HTTPException(status_code=404, detail=f"There is no employee with the id {employee_id}.")

    await pg_client.execute(
        """INSERT INTO leave_balance (employee_uuid, balance_hours, used_hours, policy_id)
           VALUES ($1, $2, 0, 'LEAVE_POLICY_GLOBAL')
           ON CONFLICT (employee_uuid) DO UPDATE SET balance_hours = EXCLUDED.balance_hours""",
        employee_id, hours,
    )
    logger.info(f"Leave entitlement for {employee_id} set to {hours}h by {payload['sub']}: {reason or 'no reason given'}")
    return {
        "employee_id": employee_id,
        "remaining_hours": hours,
        "set_by": payload["sub"],
        "reason": reason,
        "message": f"{employee_id} now has {hours:g} hours of leave left to take.",
    }

@hr_router.get("/leave/requests")
async def get_leave_history(req: Request, limit: int = Query(50), offset: Optional[int] = Query(None), payload: Dict=Depends(employee_role_required)):
    hr_modules_service: HRModulesService = getattr(req.app.state, "hr_modules_service", None)
    if not hr_modules_service: raise HTTPException(status_code=503, detail="HR Modules Service unavailable.")
    employee_uuid = payload.get("employee_uuid")
    if not employee_uuid:
        return []
    return await hr_modules_service.get_leave_history(employee_uuid, limit=limit)

@hr_router.post("/performance/review")
async def submit_review(req: Request, data: Dict, payload: Dict=Depends(manager_role_required)):
    """Persist a performance review to the Postgres UDM."""
    employee_uuid = data.get("employee_uuid") or data.get("employee_id")
    rating = data.get("overall_rating") or data.get("rating")
    if not employee_uuid or rating is None:
        raise HTTPException(status_code=400, detail="employee_uuid and overall_rating are required.")
    try:
        await pg_client.execute(
            """INSERT INTO performance_reviews (employee_uuid, overall_rating, review_period_end, reviewer_id)
               VALUES ($1, $2, CURRENT_DATE, $3)""",
            employee_uuid, float(rating), payload["sub"],
        )
    except Exception as e:
        logger.error(f"submit_review failed: {e}")
        raise HTTPException(status_code=500, detail="Could not save review.")
    return {"status": "Review Saved", "employee_uuid": employee_uuid, "overall_rating": float(rating)}

@hr_router.get("/career/path/{employee_id}")
async def get_career_path(req: Request, employee_id: str, payload: Dict=Depends(employee_role_required)):
    return await _hr(req).get_career_path(await _scoped_employee_id(payload, employee_id))

@hr_router.get("/feedback/peer/{employee_id}")
async def get_peer_feedback(req: Request, employee_id: str, payload: Dict=Depends(employee_role_required)):
    return await _hr(req).get_peer_feedback(await _scoped_employee_id(payload, employee_id))

@hr_router.get("/profile/skills")
async def get_skills(req: Request, payload: Dict=Depends(employee_role_required)):
    return await _hr(req).get_skills(_self_uuid(payload))

@hr_router.post("/profile/skills")
async def save_skills(req: Request, data: Dict, payload: Dict=Depends(employee_role_required)):
    return await _hr(req).save_skills(_self_uuid(payload), data.get("skills", []))

@hr_router.get("/payslips")
async def get_payslips(req: Request, month: Optional[str] = Query(None), year: Optional[int] = Query(None), payload: Dict=Depends(employee_role_required)):
    return await _hr(req).get_payslips(_self_uuid(payload))

@hr_router.get("/benefits")
async def get_benefits(req: Request, payload: Dict=Depends(employee_role_required)):
    """Benefits the platform actually holds for this employee.

    Only the leave entitlement is a real record today. Health cover and
    retirement matching are not stored anywhere, so they are reported as
    unavailable rather than invented.
    """
    hr = _hr(req)
    employee_uuid = _self_uuid(payload)
    balance = await hr.get_employee_leave_balance(employee_uuid)
    return {
        "employee_id": employee_uuid,
        "leave_policy": balance.get("policy"),
        "annual_leave_hours": balance.get("balance_hours"),
        "used_leave_hours": balance.get("used_hours"),
        "health_plan": None,
        "retirement_match_pct": None,
        "unavailable": ["health_plan", "retirement_match_pct"],
        "note": "Health cover and retirement matching are administered outside HiRo.",
    }

@hr_router.post("/feedback")
async def submit_feedback(req: Request, feedback: str = Body(..., embed=True),
                          about_employee_id: Optional[str] = Body(None, embed=True),
                          payload: Dict=Depends(employee_role_required)):
    """Leave feedback, either general or about a named colleague.

    Without somewhere to say who the feedback is about, nothing could ever write
    peer feedback, and the "feedback about you" panel was permanently empty.
    """
    return await _hr(req).submit_feedback(_self_uuid(payload), feedback, about_employee_id)

@hr_router.get("/retention/preference")
async def get_retention_preference(req: Request, payload: Dict=Depends(employee_role_required)):
    return await _hr(req).get_retention_preference(_self_uuid(payload))

@hr_router.post("/retention/preference")
async def save_retention_preference(req: Request, preference: str = Body(..., embed=True), payload: Dict=Depends(employee_role_required)):
    return await _hr(req).save_retention_preference(_self_uuid(payload), preference)

@hr_router.post("/expenses")
async def submit_expense(req: Request, expense_data: str = Form(...), receipt: Optional[UploadFile] = File(None), payload: Dict=Depends(employee_role_required)):
    data = json.loads(expense_data)
    return await _hr(req).submit_expense(_self_uuid(payload), data, receipt.filename if receipt else None)

@hr_router.get("/expenses")
async def list_expenses(req: Request, status: Optional[str] = Query(None), limit: int = Query(100), payload: Dict=Depends(employee_role_required)):
    """Employees see their own claims; a manager sees their direct reports';
    HR roles see everyone's."""
    role = (payload.get("role") or "").lower()
    employee_id = _self_uuid(payload) if role == "employee" else None
    team_of = payload.get("employee_uuid") if role == "manager" else None
    return await _hr(req).get_expenses(employee_id, status=status, limit=limit, team_of=team_of)

@hr_router.post("/expenses/{expense_id}/decision")
async def decide_expense(req: Request, expense_id: str, approved: bool = Body(...), comments: str = Body(""), payload: Dict=Depends(manager_role_required)):
    """Approve or reject an expense claim."""
    return await _hr(req).decide_expense(expense_id, approved, payload["sub"], comments)

@hr_router.get("/timesheets/pending")
async def list_pending_timesheets(req: Request, limit: int = Query(100), payload: Dict=Depends(manager_role_required)):
    """Timesheets awaiting a decision, scoped to the caller's own team.

    A line manager should not see, let alone approve, the whole company's
    timesheets. HR roles still see everything.
    """
    role = (payload.get("role") or "").lower()
    team_of = payload.get("employee_uuid") if role == "manager" else None
    return await _hr(req).get_timesheets_for_approval(limit=limit, team_of=team_of)

@hr_router.post("/timesheets/{timesheet_id}/decision")
async def decide_timesheet(req: Request, timesheet_id: str, approved: bool = Body(...), comments: str = Body(""), payload: Dict=Depends(manager_role_required)):
    """Approve or reject a submitted timesheet."""
    return await _hr(req).decide_timesheet(timesheet_id, approved, payload["sub"], comments)

@hr_router.get("/audit/trace")
async def get_audit_trace(req: Request, employee_id: Optional[str] = Query(None), action: Optional[str] = Query(None), limit: int = Query(50), payload: Dict=Depends(policy_admin_role_required)):
    """Real audit trail from the Postgres policy_audit_log."""
    clauses, args = [], []
    if action:
        args.append(action); clauses.append(f"trigger_type = ${len(args)}")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    args.append(max(1, min(int(limit or 50), 500)))
    query = f"""SELECT audit_id, trigger_type, decision, reason, decision_timestamp
                FROM policy_audit_log {where} ORDER BY decision_timestamp DESC LIMIT ${len(args)}"""
    try:
        rows = await pg_client.fetch(query, *args)
    except Exception as e:
        logger.warning(f"audit trace query failed: {e}")
        return []
    return [
        {"timestamp": str(r["decision_timestamp"]), "audit_id": r["audit_id"],
         "action": r["trigger_type"], "decision": r["decision"], "summary": r.get("reason")}
        for r in rows
    ]

@hr_router.post("/expenses/ocr-scan")
async def scan_expense_receipt(req: Request, file: UploadFile = File(...), payload: Dict=Depends(employee_role_required)):
    """Extract expense fields from a receipt using the local LLM (vision-free: OCR text
    is not available, so we parse the filename + let the model infer a structured draft)."""
    ai = getattr(req.app.state, "ai_service", None)
    if not ai:
        raise HTTPException(status_code=503, detail="AI service unavailable.")
    raw = (await file.read())[:4000]
    text = raw.decode("utf-8", errors="ignore") if raw else file.filename
    prompt = (
        "Extract expense fields from this receipt text as strict JSON with keys "
        "vendor (string), amount (number), currency (string), category (string), date (string). "
        f"Receipt:\n{text}"
    )
    try:
        result = await ai.generate_text(prompt, "You are a precise receipt parser. Output only JSON.")
        parsed = json.loads(result[result.find("{"): result.rfind("}") + 1])
    except Exception as e:
        logger.warning(f"OCR parse failed, returning minimal draft: {e}")
        parsed = {"vendor": "", "amount": 0, "currency": "USD", "category": "General", "date": ""}
    return parsed

@hr_router.post("/offboarding/knowledge")
async def submit_offboarding_knowledge(req: Request, data: Dict, payload: Dict=Depends(employee_role_required)):
    return await _hr(req).submit_offboarding_knowledge(_self_uuid(payload), data)

@hr_router.get("/profile/{employee_id}")
async def get_employee_profile(req: Request, employee_id: str, payload: Dict=Depends(employee_role_required)):
    return await _hr(req).get_employee_profile(await _scoped_employee_id(payload, employee_id))

@hr_router.put("/profile/{employee_id}")
async def update_employee_profile(req: Request, employee_id: str, data: Dict, payload: Dict=Depends(employee_role_required)):
    return await _hr(req).update_employee_profile(await _scoped_employee_id(payload, employee_id), data)

@hr_router.get("/payslips/download/{file_key}")
async def download_payslip(req: Request, file_key: str, payload: Dict=Depends(employee_role_required)):
    """Return a real payslip document built from the employee's comp record."""
    hr = _hr(req)
    employee_uuid = _self_uuid(payload)
    slips = await hr.get_payslips(employee_uuid, limit=60)
    match = next((s for s in slips if s["period"] == file_key), slips[0] if slips else None)
    if not match:
        raise HTTPException(status_code=404, detail="No payslip found for this period.")
    body = (
        "HiRo Payslip\n============\n"
        f"Employee: {employee_uuid}\n"
        f"Period:   {match['period']}\n"
        f"Gross (monthly): {match['gross']:.2f}\n"
    )
    return Response(content=body.encode(), media_type="text/plain",
                    headers={"Content-Disposition": f"attachment; filename=payslip-{file_key}.txt"})

@hr_router.get("/doc/details/{document_id}")
async def get_document_details(req: Request, document_id: str, payload: Dict=Depends(employee_role_required)):
    return await _hr(req).get_document_details(document_id, owner_uuid=_owner_scope(payload))

@hr_router.delete("/doc/delete/{document_id}")
async def delete_employee_document(req: Request, document_id: str, payload: Dict=Depends(employee_role_required)):
    return await _hr(req).delete_document(document_id, owner_uuid=_owner_scope(payload))

@hr_router.post("/doc/ingestion/{employee_id}/{doc_type}")
async def upload_employee_document(req: Request, employee_id: str, doc_type: str, file: UploadFile = File(...), payload: Dict=Depends(employee_role_required)):
    """Employees may upload their own documents; manager+ may upload for anyone."""
    role = (payload.get("role") or "").lower()
    if role == "employee":
        employee_id = _self_uuid(payload)
    contents = await file.read()
    return await _hr(req).upload_document(employee_id, doc_type, file.filename, size=len(contents))

@hr_router.get("/doc/employee-documents")
async def get_employee_documents(req: Request, employee_id: Optional[str] = Query(None), payload: Dict = Depends(employee_role_required)):
    """Employees see their own documents; manager+ may request any employee's."""
    role = (payload.get("role") or "").lower()
    if role == "employee":
        employee_id = _self_uuid(payload)  # employees are scoped to themselves
    return await _hr(req).get_employee_documents(employee_id)

@hr_router.post("/offboarding/upload")
async def upload_offboarding_file(req: Request, file: UploadFile = File(...), payload: Dict=Depends(employee_role_required)):
    # Employees hand over their own knowledge/files on the way out; the caller's own
    # employee_uuid identifies the upload, so widening this role gate does not let
    # anyone touch someone else's offboarding record. It used to require hrit_admin,
    # which meant an employee submitting their own handover file always got a 403.
    contents = await file.read()
    return await _hr(req).upload_document(payload.get("employee_uuid", "SYSTEM"), "offboarding", file.filename, size=len(contents))

# ======================================
# 7. ESS & MSS ROUTERS (Fixed/Complete)
# ======================================
@ess_router.get("/dashboard/{employee_id}")
async def ess_dash(req: Request, employee_id: str, payload: Dict=Depends(employee_role_required)):
    # The frontend passes the caller's own id (user.id); always serve the
    # authenticated user's own record, resolved to their Postgres employee_uuid.
    emp_uuid = payload.get("employee_uuid")
    if not emp_uuid:
        raise HTTPException(404, "No employee record linked to this account.")
    ess_service: ESSService = getattr(req.app.state, "ess_service", None)
    if not ess_service: raise HTTPException(status_code=503, detail="ESS Service unavailable.")
    return await ess_service.get_employee_dashboard_data(emp_uuid, payload['role'])

@ess_router.post("/leave/submit")
async def ess_leave(req: Request, data: LeaveRequestSubmit, payload: Dict=Depends(employee_role_required)):
    ess_service: ESSService = getattr(req.app.state, "ess_service", None)
    if not ess_service: raise HTTPException(status_code=503, detail="ESS Service unavailable.")
    # Store against the Postgres employee_uuid, not the login name, so the request
    # joins to employee_pii and shows up in the employee's own leave history.
    employee_uuid = payload.get("employee_uuid")
    if not employee_uuid:
        raise HTTPException(status_code=404, detail="No employee record linked to this account.")
    return await ess_service.submit_leave_request(employee_uuid, data.model_dump())

@ess_router.get("/profile/personal-info")
async def get_personal_info(req: Request, payload: Dict=Depends(employee_role_required)):
    """The caller's own profile from the users store (real record, no fabricated defaults)."""
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        raise HTTPException(status_code=503, detail="User store unavailable.")
    user = await mongo_client[settings.MONGO_DB_NAME]["users"].find_one(
        {"username": payload.get("sub")}, {"_id": 0, "password": 0, "hashed_password": 0},
    )
    if not user:
        raise HTTPException(status_code=404, detail="No profile found for this account.")
    return {
        "username": user.get("username"),
        "email": user.get("email"),
        "full_name": user.get("full_name"),
        "role": user.get("role"),
        "employee_uuid": user.get("employee_uuid"),
    }

@ess_router.post("/profile/update-request")
async def update_personal_info(req: Request, data: Dict, payload: Dict=Depends(employee_role_required)):
    """Persist a self-service profile-change request for HR review (does not mutate
    the record directly; approval flow applies it)."""
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        raise HTTPException(status_code=503, detail="Request store unavailable.")
    request_id = f"PCR-{random.getrandbits(48):012x}"
    await mongo_client[settings.MONGO_DB_NAME]["profile_change_requests"].insert_one({
        "request_id": request_id, "username": payload.get("sub"),
        "employee_uuid": payload.get("employee_uuid"), "requested_changes": data,
        "status": "PENDING", "submitted_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"status": "Update Requested", "request_id": request_id}

@mss_router.get("/team/roster")
async def get_team_roster(req: Request, manager_id: Optional[str] = Query(None), status: Optional[str] = Query(None),
                          limit: int = Query(50), offset: int = Query(0), payload: Dict=Depends(manager_role_required)):
    """Real team roster: the manager's direct reports via the MSS service (PII-vault backed).
    Paginated - a large org otherwise decrypts thousands of PII rows per request."""
    mss_service: MSSService = getattr(req.app.state, "mss_service", None)
    if not mss_service:
        raise HTTPException(status_code=503, detail="MSS Service unavailable.")
    mgr_uuid = payload.get("employee_uuid") or manager_id
    if not mgr_uuid:
        raise HTTPException(status_code=404, detail="No manager record linked to this account.")
    try:
        data = await mss_service.get_manager_team_data(mgr_uuid, payload["role"], limit=limit, offset=offset)
    except Exception as e:
        logger.warning(f"team roster query failed: {e}")
        return {"roster": []}
    return {
        "manager_id": mgr_uuid,
        "roster": data.get("team", []),
        "total": data.get("total", len(data.get("team", []))),
        "limit": data.get("limit"),
        "offset": data.get("offset"),
    }

@mss_router.get("/hiring/requisitions")
async def get_requisitions(req: Request, manager_id: Optional[str] = Query(None), status: Optional[str] = Query(None), payload: Dict=Depends(manager_role_required)):
    """Real hiring requisitions from the Mongo requisitions collection (empty until created)."""
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        return {"requisitions": []}
    query: Dict[str, Any] = {}
    if manager_id:
        query["manager_id"] = manager_id
    if status:
        query["status"] = status
    cursor = mongo_client[settings.MONGO_DB_NAME]["requisitions"].find(query, {"_id": 0}).sort("created_at", -1).limit(200)
    return {"requisitions": await cursor.to_list(length=200)}

@mss_router.post("/hiring/requisitions")
async def create_requisition(req: Request, data: Dict[str, Any], payload: Dict=Depends(manager_role_required)):
    """Open a hiring requisition. There was previously no way to create one."""
    title = (data.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="title is required.")
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        raise HTTPException(status_code=503, detail="Requisition store unavailable.")
    doc = {
        "requisition_id": f"REQ-{random.getrandbits(24):06x}".upper(),
        "title": title,
        "department": data.get("department", ""),
        "headcount": int(data.get("headcount", 1) or 1),
        "seniority": data.get("seniority", ""),
        "justification": data.get("justification", ""),
        "status": "OPEN",
        "manager_id": payload.get("employee_uuid") or payload.get("sub"),
        "created_by": payload.get("sub"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await mongo_client[settings.MONGO_DB_NAME]["requisitions"].insert_one(dict(doc))
    return {"status": "OPEN", "requisition": doc}

@mss_router.get("/team/{manager_id}")
async def mss_team(req: Request, manager_id: str, payload: Dict=Depends(manager_role_required)):
    # Resolve the caller's own manager record (frontend passes user.id in the path).
    mgr_uuid = payload.get("employee_uuid") or manager_id
    mss_service: MSSService = getattr(req.app.state, "mss_service", None)
    if not mss_service: raise HTTPException(status_code=503, detail="MSS Service unavailable.")
    return await mss_service.get_manager_team_data(mgr_uuid, payload['role'])

@mss_router.post("/leave/approve")
async def mss_approve(req: Request, request_id: str = Body(...), approved: bool = Body(...), comments: str = Body(""), payload: Dict=Depends(manager_role_required)):
    mss_service: MSSService = getattr(req.app.state, "mss_service", None)
    if not mss_service: raise HTTPException(status_code=503, detail="MSS Service unavailable.")
    return await mss_service.approve_leave(request_id, payload['sub'], approved)

@mss_router.get("/approvals/queue")
async def get_approval_queue(req: Request, limit: int = Query(100), payload: Dict=Depends(manager_role_required)):
    """Everything waiting on this manager: leave, timesheets and expense claims."""
    return await _approval_queue(req, payload, limit=limit)

@mss_router.get("/approvals/hrit-queue")
async def get_hrit_queue(req: Request, payload: Dict=Depends(hrit_admin_role_required)):
    """Organisation-wide pending approval queue."""
    return await _approval_queue(req, payload, limit=500)

@mss_router.post("/approvals/action")
async def action_approval(req: Request, payload_data: Dict, payload: Dict=Depends(manager_role_required)):
    """Approve or reject anything in the approval queue.

    One screen clears the whole queue, so this dispatches by request kind to the
    same handlers the dedicated endpoints use.

    The kind is always resolved from the caller's own queue, never from the
    request body. Trusting a client-supplied type would let a manager approve
    another team's timesheet by naming its id, because the per-kind decision
    handlers below take an id and do not re-check whose report it belongs to.
    Being in your queue is what authorises the decision.
    """
    request_id = payload_data.get("request_id") or payload_data.get("id")
    if not request_id:
        raise HTTPException(status_code=400, detail="request_id is required.")
    approved = bool(payload_data.get("approved", payload_data.get("action") == "approve"))
    comments = payload_data.get("comments", "")

    queue = await _approval_queue(req, payload, limit=500)
    match = next((i for i in queue if i.get("request_id") == request_id), None)
    if not match:
        raise HTTPException(
            status_code=404,
            detail="That request is not in your approval queue. It may already have been decided.")
    kind = str(match.get("type") or "").upper()

    if kind == "TIMESHEET":
        return await _hr(req).decide_timesheet(request_id, approved, payload["sub"], comments)
    if kind == "EXPENSE":
        return await _hr(req).decide_expense(request_id, approved, payload["sub"], comments)
    if kind in ("LEAVE_REQUEST", "LEAVE"):
        mss_service: MSSService = getattr(req.app.state, "mss_service", None)
        if not mss_service:
            raise HTTPException(status_code=503, detail="MSS Service unavailable.")
        return await mss_service.approve_leave(request_id, payload["sub"], approved, comments)
    raise HTTPException(status_code=400, detail=f"There is no approval handler for a {kind or 'blank'} request.")
