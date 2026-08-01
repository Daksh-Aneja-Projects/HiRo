"""People-lifecycle API: onboarding, performance cycles, goals/OKRs, one-on-ones,
offboarding read-back + exit interviews, profile-change review, and notification
preferences.

All business logic lives in services/people_lifecycle.py and
services/performance_cycles.py; this module is routing + auth scoping only,
following the pattern in services/comprehensive_routes.py (role-guard
dependencies from services/auth_deps.py, `payload["employee_uuid"]` as the
caller's own Postgres identity).
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request

from config.settings import settings
from services import people_lifecycle, performance_cycles
from services.postgres_client import pg_client
from services.auth_deps import (
    employee_role_required,
    manager_role_required,
    hrbp_role_required,
)

logger = logging.getLogger(__name__)


def _mongo(req: Request):
    return req.app.state.mongo_client[settings.MONGO_DB_NAME]


def _self_uuid(payload: Dict[str, Any]) -> str:
    uid = payload.get("employee_uuid")
    if not uid:
        raise HTTPException(status_code=404, detail="No employee record linked to this account.")
    return uid


def _manager_uuid(payload: Dict[str, Any]) -> str:
    uid = payload.get("employee_uuid")
    if not uid:
        raise HTTPException(status_code=404, detail="No manager record linked to this account.")
    return uid


async def _reports_to(employee_uuid: str, manager_uuid: Optional[str]) -> bool:
    if not manager_uuid:
        return False
    row = await pg_client.fetchrow(
        "SELECT 1 AS ok FROM employee_pii WHERE employee_uuid = $1 AND manager_id = $2",
        employee_uuid, manager_uuid,
    )
    return bool(row)


def _as_date(value):
    if isinstance(value, str) and value:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    return value


def _as_datetime(value):
    if isinstance(value, str) and value:
        v = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(v)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return value


# ======================================
# ONBOARDING
# ======================================
onboarding_hr_router = APIRouter(prefix="/hr/onboarding", tags=["Onboarding"])
onboarding_ess_router = APIRouter(prefix="/ess/onboarding", tags=["Onboarding"])
onboarding_mss_router = APIRouter(prefix="/mss/onboarding", tags=["Onboarding"])


@onboarding_hr_router.post("/plans")
async def create_onboarding_plan_route(req: Request, data: Dict[str, Any],
                                       payload: Dict = Depends(hrbp_role_required)):
    """HR builds a new hire's plan from the default template plus any extra items."""
    employee_uuid = data.get("employee_uuid")
    if not employee_uuid:
        raise HTTPException(status_code=400, detail="employee_uuid is required.")
    try:
        return await people_lifecycle.create_onboarding_plan(
            _mongo(req), employee_uuid=employee_uuid, created_by=payload["sub"],
            extra_items=data.get("extra_items"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@onboarding_ess_router.get("/my-plan")
async def my_onboarding_plan_route(req: Request, payload: Dict = Depends(employee_role_required)):
    plan = await people_lifecycle.get_my_onboarding_plan(_mongo(req), _self_uuid(payload))
    if not plan:
        return {"plan": None, "message": "No onboarding plan has been created for you yet."}
    return {"plan": plan}


@onboarding_ess_router.post("/items/{item_id}/complete")
async def complete_onboarding_item_route(req: Request, item_id: str,
                                         payload: Dict = Depends(employee_role_required)):
    try:
        return await people_lifecycle.complete_onboarding_item(
            _mongo(req), employee_uuid=_self_uuid(payload), item_id=item_id, completed_by=payload["sub"],
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@onboarding_mss_router.get("/team")
async def team_onboarding_route(req: Request, payload: Dict = Depends(manager_role_required)):
    return {"plans": await people_lifecycle.get_team_onboarding(_mongo(req), _manager_uuid(payload))}


# ======================================
# PERFORMANCE CYCLES
# ======================================
perf_hr_router = APIRouter(prefix="/hr/performance", tags=["Performance Cycles"])
perf_ess_router = APIRouter(prefix="/ess/performance", tags=["Performance Cycles"])
perf_mss_router = APIRouter(prefix="/mss/performance", tags=["Performance Cycles"])


@perf_hr_router.post("/cycles")
async def create_cycle_route(data: Dict[str, Any], payload: Dict = Depends(hrbp_role_required)):
    try:
        return await performance_cycles.create_cycle(
            name=data.get("name", ""), opens_at=_as_date(data.get("opens_at")),
            closes_at=_as_date(data.get("closes_at")), employee_uuids=data.get("employee_uuids") or [],
            created_by=payload["sub"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@perf_hr_router.get("/cycles")
async def list_cycles_route(payload: Dict = Depends(hrbp_role_required)):
    return {"cycles": await performance_cycles.list_cycles()}


@perf_hr_router.get("/cycles/{cycle_id}")
async def get_cycle_route(cycle_id: str, payload: Dict = Depends(hrbp_role_required)):
    cycle = await performance_cycles.get_cycle(cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail=f"There is no performance cycle with the id {cycle_id}.")
    return cycle


@perf_hr_router.post("/cycles/{cycle_id}/advance")
async def advance_cycle_route(cycle_id: str, payload: Dict = Depends(hrbp_role_required)):
    try:
        return await performance_cycles.advance_cycle_stage(cycle_id, payload["sub"])
    except performance_cycles.StageError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@perf_hr_router.post("/cycles/{cycle_id}/calibrate-entry")
async def calibrate_entry_route(cycle_id: str, data: Dict[str, Any] = Body(...),
                                payload: Dict = Depends(hrbp_role_required)):
    employee_uuid = data.get("employee_uuid")
    rating = data.get("calibrated_rating")
    if not employee_uuid or rating is None:
        raise HTTPException(status_code=400, detail="employee_uuid and calibrated_rating are required.")
    try:
        return await performance_cycles.calibrate_entry(
            cycle_id=cycle_id, employee_uuid=employee_uuid, calibrated_rating=float(rating),
        )
    except performance_cycles.StageError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@perf_ess_router.post("/self-assessment")
async def submit_self_assessment_route(data: Dict[str, Any], payload: Dict = Depends(employee_role_required)):
    cycle_id = data.get("cycle_id")
    if not cycle_id:
        raise HTTPException(status_code=400, detail="cycle_id is required.")
    try:
        return await performance_cycles.submit_self_assessment(
            cycle_id=cycle_id, employee_uuid=_self_uuid(payload),
            self_assessment=data.get("self_assessment", ""), self_rating=data.get("self_rating"),
        )
    except performance_cycles.StageError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@perf_ess_router.post("/sign-off")
async def sign_off_route(data: Dict[str, Any], payload: Dict = Depends(employee_role_required)):
    cycle_id = data.get("cycle_id")
    if not cycle_id:
        raise HTTPException(status_code=400, detail="cycle_id is required.")
    try:
        return await performance_cycles.sign_off(cycle_id=cycle_id, employee_uuid=_self_uuid(payload))
    except performance_cycles.StageError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@perf_ess_router.get("/my-cycles")
async def my_cycle_entries_route(payload: Dict = Depends(employee_role_required)):
    return {"entries": await performance_cycles.get_my_cycle_entries(_self_uuid(payload))}


@perf_mss_router.get("/cycle-entries")
async def cycle_entries_route(req: Request, cycle_id: str = Query(...),
                              payload: Dict = Depends(manager_role_required)):
    mgr = _manager_uuid(payload)
    db = _mongo(req)

    async def _goals(employee_uuid: str):
        return await people_lifecycle.goals_summary(db, employee_uuid)

    return {"entries": await performance_cycles.list_cycle_entries_for_manager(cycle_id, mgr, goals_summary_fn=_goals)}


@perf_mss_router.post("/review-entry")
async def review_entry_route(data: Dict[str, Any], payload: Dict = Depends(manager_role_required)):
    cycle_id, employee_uuid, rating = data.get("cycle_id"), data.get("employee_uuid"), data.get("manager_rating")
    if not cycle_id or not employee_uuid or rating is None:
        raise HTTPException(status_code=400, detail="cycle_id, employee_uuid and manager_rating are required.")
    try:
        return await performance_cycles.submit_manager_review(
            cycle_id=cycle_id, employee_uuid=employee_uuid, manager_rating=float(rating),
            manager_comments=data.get("manager_comments", ""), manager_uuid=_manager_uuid(payload),
        )
    except performance_cycles.StageError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ======================================
# GOALS / OKRs
# ======================================
goals_ess_router = APIRouter(prefix="/ess/goals", tags=["Goals"])
goals_mss_router = APIRouter(prefix="/mss/goals", tags=["Goals"])


@goals_ess_router.get("")
async def list_my_goals_route(req: Request, payload: Dict = Depends(employee_role_required)):
    return {"goals": await people_lifecycle.list_goals(_mongo(req), _self_uuid(payload))}


@goals_ess_router.post("")
async def create_goal_route(req: Request, data: Dict[str, Any], payload: Dict = Depends(employee_role_required)):
    try:
        return await people_lifecycle.create_goal(
            _mongo(req), employee_uuid=_self_uuid(payload), title=data.get("title", ""),
            description=data.get("description", ""), key_results=data.get("key_results") or [],
            created_by=payload["sub"], cycle_id=data.get("cycle_id"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@goals_ess_router.put("/{goal_id}")
async def update_goal_route(req: Request, goal_id: str, data: Dict[str, Any],
                            payload: Dict = Depends(employee_role_required)):
    try:
        return await people_lifecycle.update_goal(
            _mongo(req), goal_id=goal_id, employee_uuid=_self_uuid(payload), updates=data,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@goals_ess_router.delete("/{goal_id}")
async def delete_goal_route(req: Request, goal_id: str, payload: Dict = Depends(employee_role_required)):
    ok = await people_lifecycle.delete_goal(_mongo(req), goal_id=goal_id, employee_uuid=_self_uuid(payload))
    if not ok:
        raise HTTPException(status_code=404, detail="There is no goal with that id on your account.")
    return {"status": "DELETED", "goal_id": goal_id}


@goals_ess_router.post("/draft")
async def draft_goal_route(req: Request, data: Dict[str, Any] = Body(...),
                           payload: Dict = Depends(employee_role_required)):
    ai_service = getattr(req.app.state, "ai_service", None)
    if not ai_service:
        raise HTTPException(status_code=503, detail="AI service unavailable.")
    try:
        return await people_lifecycle.draft_goal(ai_service, data.get("intent", ""))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@goals_mss_router.get("/team")
async def team_goals_route(req: Request, payload: Dict = Depends(manager_role_required)):
    return {"goals": await people_lifecycle.list_team_goals(_mongo(req), _manager_uuid(payload))}


@goals_mss_router.post("/{goal_id}/comment")
async def comment_goal_route(req: Request, goal_id: str, data: Dict[str, Any] = Body(...),
                             payload: Dict = Depends(manager_role_required)):
    try:
        return await people_lifecycle.add_goal_comment(
            _mongo(req), goal_id=goal_id, manager_uuid=_manager_uuid(payload), text=data.get("text", ""),
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ======================================
# ONE-ON-ONES
# ======================================
oneonone_mss_router = APIRouter(prefix="/mss/one-on-ones", tags=["One-on-Ones"])
oneonone_ess_router = APIRouter(prefix="/ess/one-on-ones", tags=["One-on-Ones"])


@oneonone_mss_router.post("")
async def create_one_on_one_route(data: Dict[str, Any], payload: Dict = Depends(manager_role_required)):
    mgr = _manager_uuid(payload)
    employee_uuid = data.get("employee_uuid")
    if not employee_uuid:
        raise HTTPException(status_code=400, detail="employee_uuid is required.")
    if not await _reports_to(employee_uuid, mgr):
        raise HTTPException(status_code=403, detail="You can only log one-on-ones with your own direct reports.")
    held_at = _as_datetime(data.get("held_at"))
    if not held_at:
        raise HTTPException(status_code=400, detail="held_at is required.")
    return await people_lifecycle.create_one_on_one(
        manager_uuid=mgr, employee_uuid=employee_uuid, held_at=held_at,
        talking_points=data.get("talking_points", ""), notes=data.get("notes", ""),
        shared_with_employee=bool(data.get("shared_with_employee", False)),
    )


@oneonone_mss_router.get("")
async def list_one_on_ones_route(employee_uuid: Optional[str] = Query(None),
                                 payload: Dict = Depends(manager_role_required)):
    return {"one_on_ones": await people_lifecycle.list_one_on_ones(
        manager_uuid=_manager_uuid(payload), employee_uuid=employee_uuid,
    )}


@oneonone_mss_router.get("/status")
async def one_on_one_status_route(payload: Dict = Depends(manager_role_required)):
    return {"status": await people_lifecycle.one_on_one_status(_manager_uuid(payload))}


@oneonone_mss_router.put("/{one_on_one_id}")
async def update_one_on_one_route(one_on_one_id: int, data: Dict[str, Any],
                                  payload: Dict = Depends(manager_role_required)):
    if "held_at" in data:
        data["held_at"] = _as_datetime(data["held_at"])
    try:
        return await people_lifecycle.update_one_on_one(
            one_on_one_id=one_on_one_id, manager_uuid=_manager_uuid(payload), updates=data,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@oneonone_mss_router.delete("/{one_on_one_id}")
async def delete_one_on_one_route(one_on_one_id: int, payload: Dict = Depends(manager_role_required)):
    ok = await people_lifecycle.delete_one_on_one(one_on_one_id=one_on_one_id, manager_uuid=_manager_uuid(payload))
    if not ok:
        raise HTTPException(status_code=404, detail="There is no one-on-one with that id on your own calendar.")
    return {"status": "DELETED", "id": one_on_one_id}


@oneonone_ess_router.get("")
async def my_one_on_ones_route(payload: Dict = Depends(employee_role_required)):
    return {"one_on_ones": await people_lifecycle.list_one_on_ones(
        employee_uuid=_self_uuid(payload), shared_only=True,
    )}


# ======================================
# OFFBOARDING (read-back + exit interviews)
# ======================================
offboarding_hr_router = APIRouter(prefix="/hr/offboarding", tags=["Offboarding"])
offboarding_ess_router = APIRouter(prefix="/ess/offboarding", tags=["Offboarding"])


@offboarding_hr_router.get("/knowledge")
async def list_offboarding_knowledge_route(req: Request, employee_uuid: Optional[str] = Query(None),
                                           payload: Dict = Depends(hrbp_role_required)):
    return {"entries": await people_lifecycle.list_offboarding_knowledge(_mongo(req), employee_uuid)}


@offboarding_ess_router.get("/knowledge/mine")
async def my_offboarding_knowledge_route(req: Request, payload: Dict = Depends(employee_role_required)):
    return {"entries": await people_lifecycle.list_offboarding_knowledge(_mongo(req), _self_uuid(payload))}


@offboarding_ess_router.post("/exit-interview")
async def submit_exit_interview_route(req: Request, data: Dict[str, Any],
                                      payload: Dict = Depends(employee_role_required)):
    try:
        return await people_lifecycle.submit_exit_interview(
            _mongo(req), employee_uuid=_self_uuid(payload), reasons=data.get("reasons") or [],
            comments=data.get("comments", ""), would_recommend=bool(data.get("would_recommend", False)),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@offboarding_hr_router.get("/exit-interviews")
async def list_exit_interviews_route(req: Request, payload: Dict = Depends(hrbp_role_required)):
    return await people_lifecycle.list_exit_interviews(_mongo(req))


# ======================================
# PROFILE CHANGE REVIEW
# ======================================
profile_change_router = APIRouter(prefix="/hr/profile-change-requests", tags=["Profile Change Review"])


@profile_change_router.get("")
async def list_pending_profile_changes_route(req: Request, payload: Dict = Depends(hrbp_role_required)):
    return {"requests": await people_lifecycle.list_pending_profile_change_requests(_mongo(req))}


@profile_change_router.post("/{request_id}/decide")
async def decide_profile_change_route(req: Request, request_id: str, data: Dict[str, Any],
                                      payload: Dict = Depends(hrbp_role_required)):
    try:
        return await people_lifecycle.decide_profile_change_request(
            _mongo(req), request_id=request_id, approve=bool(data.get("approve", False)),
            comments=data.get("comments", ""), decided_by=payload["sub"],
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ======================================
# NOTIFICATION PREFERENCES
# ======================================
notification_prefs_router = APIRouter(prefix="/me", tags=["Notification Preferences"])


@notification_prefs_router.get("/notification-preferences")
async def get_notification_preferences_route(req: Request, payload: Dict = Depends(employee_role_required)):
    return await people_lifecycle.get_notification_preferences(_mongo(req), _self_uuid(payload), payload.get("sub"))


@notification_prefs_router.put("/notification-preferences")
async def set_notification_preferences_route(req: Request, data: Dict[str, Any],
                                              payload: Dict = Depends(employee_role_required)):
    kinds = data.get("kinds") if isinstance(data.get("kinds"), dict) else data
    return await people_lifecycle.set_notification_preferences(
        _mongo(req), _self_uuid(payload), payload.get("sub"), kinds,
    )


PEOPLE_LIFECYCLE_ROUTERS = [
    onboarding_hr_router, onboarding_ess_router, onboarding_mss_router,
    perf_hr_router, perf_ess_router, perf_mss_router,
    goals_ess_router, goals_mss_router,
    oneonone_mss_router, oneonone_ess_router,
    offboarding_hr_router, offboarding_ess_router,
    profile_change_router,
    notification_prefs_router,
]
