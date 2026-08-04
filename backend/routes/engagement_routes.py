"""engagement API routes.

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


@social_router.get("/feed")
async def get_social_feed(req: Request, payload: Dict = Depends(employee_role_required)):
    """Real, persisted social feed (newest first) from MongoDB."""
    return await social_recognition.list_feed(social_recognition.get_db(req))

@social_router.post("/posts")
async def post_social_post(req: Request, data: Dict, payload: Dict = Depends(employee_role_required)):
    """Persist a new post so it appears on the next feed refresh."""
    try:
        post = await social_recognition.create_post(
            social_recognition.get_db(req),
            user_id=data.get("user_id") or payload.get("sub"),
            user_name=data.get("user_name") or payload.get("sub"),
            content=data.get("content"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "Posted", "post": post}

@social_router.post("/activity")
async def create_activity_site(req: Request, activity_details: Dict, payload: Dict = Depends(employee_role_required)):
    """Persist a new social activity so it appears in the joinable-activities list."""
    activity_id = f"ACT-{random.getrandbits(48):012x}"
    doc = {
        "id": activity_id,
        "title": (activity_details.get("title") or "Untitled Activity").strip(),
        "description": activity_details.get("description", ""),
        "created_by": payload.get("sub"),
        "members": [payload.get("sub")],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await _social_activities(req).insert_one(dict(doc))
    return {"status": "Activity Created", "id": activity_id, "activity": doc}

@social_router.get("/activities")
async def get_joinable_activities(req: Request, payload: Dict = Depends(employee_role_required)):
    """Real joinable activities from Mongo (newest first, empty until created)."""
    cursor = _social_activities(req).find({}, {"_id": 0}).sort("created_at", -1).limit(200)
    return await cursor.to_list(length=200)

@social_router.post("/chat-link")
async def create_private_chat_link(req: Request, details: Dict, payload: Dict = Depends(employee_role_required)):
    """Generate a deterministic private chat link id for a pair of users and persist it."""
    peer = details.get("peer") or details.get("to_user") or details.get("target") or ""
    me = payload.get("sub") or ""
    seed = ":".join(sorted([me, str(peer)]))
    link_id = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if mongo_client:
        await mongo_client[settings.MONGO_DB_NAME]["chat_links"].update_one(
            {"link_id": link_id},
            {"$set": {"link_id": link_id, "participants": sorted([me, str(peer)]),
                      "created_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
    return {"link_id": link_id, "link": f"/collab/chat/{link_id}", "participants": sorted([me, str(peer)])}

@innovation_router.get("/ideas")
async def get_innovation_ideas(req: Request, payload: Dict = Depends(employee_role_required)):
    """Real innovation ideas from Mongo, ranked by votes (empty until submitted)."""
    cursor = _ideas(req).find({}, {"_id": 0}).sort("votes", -1).limit(200)
    return await cursor.to_list(length=200)

@innovation_router.post("/ideas")
async def create_innovation_idea(req: Request, payload_data: Dict, payload: Dict = Depends(employee_role_required)):
    """Persist a new innovation idea (so /ideas and voting have real data to act on)."""
    title = (payload_data.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="title is required.")
    idea_id = f"IDEA-{random.getrandbits(48):012x}"
    doc = {
        "id": idea_id, "title": title, "description": payload_data.get("description", ""),
        "submitted_by": payload.get("sub"), "votes": 0, "voters": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await _ideas(req).insert_one(dict(doc))
    return {"status": "Idea Submitted", "id": idea_id, "idea": doc}

@innovation_router.post("/ideas/vote")
async def vote_innovation_idea(req: Request, payload_data: Dict, payload: Dict = Depends(employee_role_required)):
    """Cast a real, deduplicated up-vote (atomic $inc) on an innovation idea."""
    idea_id = payload_data.get("id") or payload_data.get("idea_id")
    if not idea_id:
        raise HTTPException(status_code=400, detail="idea id is required.")
    voter = payload.get("sub")
    result = await _ideas(req).update_one(
        {"id": idea_id, "voters": {"$ne": voter}},
        {"$inc": {"votes": 1}, "$addToSet": {"voters": voter}},
    )
    if result.matched_count == 0:
        existing = await _ideas(req).find_one({"id": idea_id}, {"_id": 0, "votes": 1})
        if not existing:
            raise HTTPException(status_code=404, detail="Idea not found.")
        return {"status": "Already Voted", "id": idea_id, "votes": existing.get("votes", 0)}
    updated = await _ideas(req).find_one({"id": idea_id}, {"_id": 0, "votes": 1})
    return {"status": "Voted", "id": idea_id, "votes": (updated or {}).get("votes", 0)}

# ======================================
# 17. RECOGNITION ROUTES (Dedicated router - Fixes 404)
# ======================================
@recognition_router.post("/star/{user_id}")
async def give_recognition_star(req: Request, user_id: str, reason: str = Body(..., embed=True), payload: Dict = Depends(employee_role_required)):
    """Persist a recognition star; recipient display name resolved from the users store.

    Peer recognition is open to everyone: the Collaboration Hub is in the
    employee sidebar and shows a "Give star" control, which used to 403 for the
    very people it was aimed at. Self-recognition is still rejected.
    """
    try:
        return await social_recognition.give_star(
            social_recognition.get_db(req),
            from_user=payload.get("sub"),
            to_user=user_id,
            reason=reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@recognition_router.get("/leaderboard")
async def get_recognition_leaderboard(req: Request, payload: Dict = Depends(employee_role_required)):
    """Real recognition leaderboard aggregated from persisted stars."""
    return await social_recognition.leaderboard(social_recognition.get_db(req))
