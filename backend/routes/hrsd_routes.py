"""hrsd API routes.

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
# 2. HRSD & TICKETS ROUTER (Fixed/Complete)
# ======================================
@hrsd_router.get("/tickets")
async def list_tickets(req: Request, employee_id: Optional[str] = Query(None), limit: Optional[int] = Query(None), offset: Optional[int] = Query(None), payload: Dict=Depends(manager_role_required)):
    """FIX: Added GET endpoint to list tickets (needed by frontend dashboard)."""
    hrsd_system: MultiAgentHRSDSystem = getattr(req.app.state, "hrsd_system", None)
    if not hrsd_system:
        raise HTTPException(status_code=503, detail="HRSD system unavailable.")
    # limit and offset were accepted and then never forwarded, so the case list
    # and both its charts covered the newest 50 of 808 while the monitoring
    # panel on the same screen reported 605 open.
    return await hrsd_system.list_tickets(employee_id, limit=limit, offset=offset)

@hrsd_router.get("/my-tickets")
async def list_my_tickets(req: Request, limit: Optional[int] = Query(None), offset: Optional[int] = Query(None),
                          payload: Dict = Depends(employee_role_required)):
    """The caller's own cases.

    GET /hrsd/tickets is manager-gated and takes employee_id as a free query
    parameter, so it can never be opened to employees. Employees had no way to
    see a case they had raised at all, which also meant the AI first-line
    suggestion had no one to confirm it: the loop is closed by the person who
    raised the case, and they could not reach it.
    """
    hrsd_system: MultiAgentHRSDSystem = getattr(req.app.state, "hrsd_system", None)
    if not hrsd_system:
        raise HTTPException(status_code=503, detail="HRSD system unavailable.")
    employee_uuid = payload.get("employee_uuid")
    if not employee_uuid:
        raise HTTPException(status_code=404, detail="No employee record is linked to this account.")
    return await hrsd_system.list_tickets(employee_uuid, limit=limit, offset=offset)


@hrsd_router.post("/tickets")
async def create_ticket(req: Request, subject: str = Body(...), description: str = Body(...),
                        employee_id: Optional[str] = Body(None), payload: Dict=Depends(employee_role_required)):
    hrsd_system: MultiAgentHRSDSystem = getattr(req.app.state, "hrsd_system", None)
    if not hrsd_system: raise HTTPException(status_code=503, detail="HRSD System unavailable.")

    # employee_id used to be taken from the body and trusted, so any employee
    # could raise a case in a colleague's name. Only roles that legitimately act
    # on behalf of others may name someone else; an employee always gets their
    # own record regardless of what the body says.
    self_uuid = payload.get("employee_uuid")
    acts_for_others = str(payload.get("role", "")).lower() in ("manager", "hrbp", "hrit_admin")
    if acts_for_others:
        employee_id = employee_id or self_uuid
    else:
        employee_id = self_uuid
    if not employee_id:
        raise HTTPException(status_code=404, detail="No employee record is linked to this account.")

    ticket = await hrsd_system.create_ticket(employee_id, subject, description)

    # Actually triage it. This route reported "Triage Initiated" while calling
    # nothing: triage_ticket had no caller anywhere in the codebase, so every
    # case sat at NEW with no owner until a person happened to notice it.
    try:
        ticket = await hrsd_system.triage_ticket(ticket.ticket_id)
        routed = ticket.assigned_agent
    except Exception as e:
        logger.warning(f"Could not triage {ticket.ticket_id}: {e}")
        routed = None

    # AI first-line suggestion runs in the background: LLM calls take 20-40s on
    # CPU-only Ollama, so ticket creation returns immediately rather than
    # blocking on it. Attaches to metadata.suggested_resolution once ready;
    # never auto-closes anything (see routes/ai_knowledge_routes.py).
    spawn_suggested_resolution(req.app.state, ticket.ticket_id, subject, description)

    return {
        "ticket_id": ticket.ticket_id,
        "status": ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status),
        "priority": ticket.priority.value if hasattr(ticket.priority, "value") else str(ticket.priority),
        "assigned_to": routed,
        "message": (f"Your case was raised and passed to the {_readable_agent(routed)}."
                    if routed and routed != "TriageAgent"
                    else "Your case was raised and is waiting for someone to pick it up."),
    }

@hrsd_router.put("/tickets/{ticket_id}/resolve")
async def resolve_ticket(req: Request, ticket_id: str, resolution_summary: str = Body(..., embed=True), payload: Dict=Depends(manager_role_required)):
    hrsd_system: MultiAgentHRSDSystem = getattr(req.app.state, "hrsd_system", None)
    if not hrsd_system: raise HTTPException(status_code=503, detail="HRSD System unavailable.")
    ticket = await hrsd_system.resolve_ticket_by_agent(ticket_id,
                                            resolution_summary, payload['sub'])
    # KIND_CASE was declared and never wired: the person who raised the case had
    # no way to learn it was resolved short of reopening the case list.
    await notification_service.notify(
        ticket.employee_id, notification_service.KIND_CASE,
        "Your case was resolved",
        f'Your case "{ticket.title}" was resolved: {resolution_summary}',
        link="/employee-portal?module=cases", related_id=ticket_id,
    )
    return {"status": "Resolved"}

@hrsd_router.put("/tickets/{ticket_id}/assign")
async def assign_ticket(req: Request, ticket_id: str, assignee: str = Body(..., embed=True), payload: Dict=Depends(manager_role_required)):
    """Assign a case to an owner. The UI rendered assigned_to but nothing could set it."""
    try:
        result = await pg_client.execute(
            "UPDATE hrsd_tickets SET assigned_agent = $1 WHERE ticket_id = $2",
            assignee, ticket_id,
        )
    except Exception as e:
        logger.error(f"assign ticket failed: {e}")
        raise HTTPException(status_code=500, detail="Could not assign the case.")
    if isinstance(result, str) and result.endswith("0"):
        raise HTTPException(status_code=404, detail="Ticket not found.")
    return {"status": "Assigned", "ticket_id": ticket_id, "assigned_agent": assignee}

@hrsd_router.get("/monitoring/overview")
async def get_hrsd_overview(req: Request, payload: Dict=Depends(manager_role_required)):
    hrsd_system: MultiAgentHRSDSystem = getattr(req.app.state, "hrsd_system", None)
    if not hrsd_system:
        raise HTTPException(status_code=503, detail="HRSD System unavailable.")
    return await hrsd_system.get_overview()

@hrsd_router.post("/integrations/snow/sync")
async def sync_servicenow(req: Request, payload: Dict=Depends(policy_admin_role_required)):
    """Record a ServiceNow sync attempt. There is no live ServiceNow tenant wired up,
    so this persists a local sync-log record (clearly marked as local) rather than
    fabricating an external ServiceNow id."""
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not mongo_client:
        raise HTTPException(status_code=503, detail="Sync log store unavailable.")
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "local_record_id": f"LOCAL-SNOWSYNC-{random.getrandbits(48):012x}",
        "source": "local",
        "external_system": "servicenow",
        "external_configured": False,
        "status": "RECORDED_LOCAL",
        "triggered_by": payload.get("sub"),
        "synced_at": now,
    }
    await mongo_client[settings.MONGO_DB_NAME]["servicenow_sync_log"].insert_one(dict(record))
    return {"status": "Sync Recorded (local)", "details": record}

# ======================================
# NOTIFICATIONS
# ======================================
@notifications_router.get("")
async def list_notifications(req: Request, limit: int = Query(50), unread_only: bool = Query(False),
                             payload: Dict = Depends(employee_role_required)):
    """What this person has been told, newest first, with the unread count."""
    me = _self_uuid(payload)
    items = await notification_service.list_for(me, limit=limit, unread_only=unread_only)
    return {"notifications": items, "unread": await notification_service.unread_count(me)}


@notifications_router.post("/{notification_id}/read")
async def mark_notification_read(req: Request, notification_id: str,
                                 payload: Dict = Depends(employee_role_required)):
    """Mark one notification read. Scoped to the owner."""
    changed = await notification_service.mark_read(_self_uuid(payload), notification_id)
    return {"marked": changed, "notification_id": notification_id}


@notifications_router.post("/read-all")
async def mark_all_notifications_read(req: Request, payload: Dict = Depends(employee_role_required)):
    """Clear the whole list for this person."""
    return {"marked": await notification_service.mark_read(_self_uuid(payload))}
