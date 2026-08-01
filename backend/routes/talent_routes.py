"""Talent Intelligence API surface (see COLLISION RULES -- the one new router file
for this build): internal mobility matching, succession planning, compensation
review cycles, headcount planning, engagement pulses, milestones, manager nudges
and the lightweight candidate pipeline.

All persistent logic lives in services/talent_intelligence.py,
services/comp_planning_service.py, services/engagement_service.py,
services/milestones_service.py and services/manager_nudges.py -- this file is
thin HTTP plumbing: auth, ownership checks, request/response shaping.
"""
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request

from config.settings import settings
from services.postgres_client import pg_client
from services.auth_deps import employee_role_required, hrbp_role_required, manager_role_required
from services import comp_planning_service as comp
from services import engagement_service as eng
from services import manager_nudges as nudges_svc
from services import milestones_service
from services import talent_intelligence as ti

logger = logging.getLogger(__name__)

hiring_router = APIRouter(prefix="/mss/hiring", tags=["Talent Intelligence: Mobility & Pipeline"])
succession_router = APIRouter(prefix="/hr/succession", tags=["Talent Intelligence: Succession"])
comp_cycle_router = APIRouter(prefix="/hr/comp", tags=["Talent Intelligence: Comp Cycles"])
headcount_router = APIRouter(prefix="/hr/headcount", tags=["Talent Intelligence: Headcount"])
engagement_router = APIRouter(tags=["Talent Intelligence: Engagement"])
mss_extra_router = APIRouter(prefix="/mss", tags=["Talent Intelligence: Milestones & Nudges"])

TALENT_ROUTERS = [hiring_router, succession_router, comp_cycle_router, headcount_router,
                   engagement_router, mss_extra_router]


def _mongo(req: Request):
    m = getattr(req.app.state, "mongo_client", None)
    if m is None:
        raise HTTPException(status_code=503, detail="Data store unavailable.")
    return m


def _db(req: Request):
    return _mongo(req)[settings.MONGO_DB_NAME]


async def _requisition_or_404(req: Request, requisition_id: str) -> Dict[str, Any]:
    doc = await _db(req)["requisitions"].find_one({"requisition_id": requisition_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail=f"No requisition '{requisition_id}'.")
    return doc


def _owns_requisition(payload: Dict[str, Any], requisition: Dict[str, Any]) -> bool:
    if (payload.get("role") or "").lower() in ("hrit_admin", "hrbp"):
        return True
    return requisition.get("manager_id") == (payload.get("employee_uuid") or payload.get("sub"))


# --- 1. Internal mobility matching -------------------------------------------------

@hiring_router.get("/requisitions/{requisition_id}/internal-matches")
async def internal_matches(req: Request, requisition_id: str, limit: int = Query(10, le=50),
                            payload: Dict = Depends(manager_role_required)):
    requisition = await _requisition_or_404(req, requisition_id)
    if not _owns_requisition(payload, requisition):
        raise HTTPException(status_code=403, detail="You can only view matches for your own requisitions.")
    return await ti.internal_matches_for_requisition(_mongo(req), requisition, limit=limit)


# --- 7. Candidate pipeline -----------------------------------------------------------

@hiring_router.post("/requisitions/{requisition_id}/candidates")
async def create_candidate(req: Request, requisition_id: str, data: Dict[str, Any] = Body(...),
                            payload: Dict = Depends(manager_role_required)):
    requisition = await _requisition_or_404(req, requisition_id)
    if not _owns_requisition(payload, requisition):
        raise HTTPException(status_code=403, detail="You can only add candidates to your own requisitions.")
    try:
        return await ti.create_candidate(_db(req), requisition_id=requisition_id, name=data.get("name"),
                                          source=data.get("source"), by=payload.get("sub"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@hiring_router.get("/requisitions/{requisition_id}/candidates")
async def get_candidates(req: Request, requisition_id: str, payload: Dict = Depends(manager_role_required)):
    requisition = await _requisition_or_404(req, requisition_id)
    if not _owns_requisition(payload, requisition):
        raise HTTPException(status_code=403, detail="You can only view candidates on your own requisitions.")
    return await ti.list_candidates(_db(req), requisition_id)


@hiring_router.post("/candidates/{candidate_id}/advance")
async def advance_candidate(req: Request, candidate_id: str, stage: str = Body(...), note: str = Body(""),
                             payload: Dict = Depends(manager_role_required)):
    db = _db(req)
    candidate = await db.candidates.find_one({"candidate_id": candidate_id}, {"_id": 0})
    if not candidate:
        raise HTTPException(status_code=404, detail=f"No candidate '{candidate_id}'.")
    requisition = await _requisition_or_404(req, candidate["requisition_id"])
    if not _owns_requisition(payload, requisition):
        raise HTTPException(status_code=403, detail="You can only advance candidates on your own requisitions.")
    try:
        return await ti.advance_candidate(db, candidate_id, stage, note, payload.get("sub"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- 2. Succession planning -----------------------------------------------------------

@succession_router.post("/nominations")
async def create_nomination(req: Request, data: Dict[str, Any] = Body(...),
                             payload: Dict = Depends(hrbp_role_required)):
    try:
        return await ti.create_nomination(
            data.get("role_or_person_uuid"), data.get("nominee_uuid"), payload.get("sub"),
            data.get("readiness"), data.get("rationale"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@succession_router.get("/plan")
async def succession_plan(req: Request, payload: Dict = Depends(hrbp_role_required)):
    return await ti.succession_plan(getattr(req.app.state, "wfm_service", None))


@succession_router.get("/nine-box")
async def nine_box(req: Request, payload: Dict = Depends(hrbp_role_required)):
    return await ti.nine_box(_mongo(req))


# --- 3. Compensation review cycles ----------------------------------------------------

@comp_cycle_router.post("/cycles")
async def create_cycle(req: Request, data: Dict[str, Any] = Body(...), payload: Dict = Depends(hrbp_role_required)):
    try:
        return await comp.create_cycle(data.get("department"), data.get("name"),
                                        float(data.get("budget_pct") or 0), payload.get("sub"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@comp_cycle_router.get("/cycles")
async def list_cycles(req: Request, payload: Dict = Depends(hrbp_role_required)):
    return {"cycles": await comp.list_cycles()}


@comp_cycle_router.get("/cycles/{cycle_id}")
async def get_cycle(req: Request, cycle_id: str, payload: Dict = Depends(hrbp_role_required)):
    try:
        return await comp.get_cycle(cycle_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@comp_cycle_router.patch("/cycles/{cycle_id}/lines/{line_id}")
async def adjust_line(req: Request, cycle_id: str, line_id: int,
                       proposed_pct: float = Body(..., embed=True), payload: Dict = Depends(hrbp_role_required)):
    try:
        return await comp.adjust_line(cycle_id, line_id, proposed_pct, payload.get("sub"))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@comp_cycle_router.post("/cycles/{cycle_id}/finalize")
async def finalize_cycle(req: Request, cycle_id: str, payload: Dict = Depends(hrbp_role_required)):
    hr_modules_service = getattr(req.app.state, "hr_modules_service", None)
    if not hr_modules_service:
        raise HTTPException(status_code=503, detail="Compensation service unavailable.")
    try:
        return await comp.finalize_cycle(cycle_id, hr_modules_service, payload.get("sub"))
    except comp.BudgetExceeded as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- 4. Headcount planning -------------------------------------------------------------

@headcount_router.post("/plans")
async def create_plan(req: Request, data: Dict[str, Any] = Body(...), payload: Dict = Depends(hrbp_role_required)):
    try:
        return await comp.create_headcount_plan(data.get("department"), data.get("fiscal_label"),
                                                  data.get("planned_headcount"), payload.get("sub"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@headcount_router.get("/plans")
async def list_plans(req: Request, department: Optional[str] = Query(None),
                      payload: Dict = Depends(hrbp_role_required)):
    return {"plans": await comp.list_headcount_plans(department)}


@headcount_router.patch("/plans/{plan_id}")
async def update_plan(req: Request, plan_id: str, data: Dict[str, Any] = Body(...),
                       payload: Dict = Depends(hrbp_role_required)):
    try:
        return await comp.update_headcount_plan(plan_id, data.get("planned_headcount"), data.get("fiscal_label"))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@headcount_router.delete("/plans/{plan_id}")
async def delete_plan(req: Request, plan_id: str, payload: Dict = Depends(hrbp_role_required)):
    try:
        await comp.delete_headcount_plan(plan_id)
        return {"status": "deleted", "plan_id": plan_id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@headcount_router.get("/variance")
async def headcount_variance(req: Request, payload: Dict = Depends(hrbp_role_required)):
    return await comp.headcount_variance()


# --- 5. Engagement / eNPS pulse ---------------------------------------------------------

@engagement_router.post("/ess/pulse")
async def submit_pulse(req: Request, data: Dict[str, Any] = Body(...),
                        payload: Dict = Depends(employee_role_required)):
    try:
        return await eng.submit_pulse(_db(req), username=payload.get("sub"), score=data.get("score"),
                                       comment=data.get("comment"), survey_id=data.get("survey_id"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@engagement_router.get("/hr/engagement/summary")
async def engagement_summary(req: Request, survey_id: Optional[str] = Query(None),
                              payload: Dict = Depends(hrbp_role_required)):
    # Denominator is the real workforce (Postgres employee_pii), not the handful of
    # portal login accounts -- a pulse survey goes to every employee, not just the
    # people who happen to have a HiRo login in this demo.
    total = await pg_client.fetchrow("SELECT COUNT(*) AS n FROM employee_pii")
    total_employees = int((total or {}).get("n") or 0)
    ai_service = getattr(req.app.state, "ai_service", None)
    return await eng.engagement_summary(_db(req), ai_service, total_employees, survey_id)


# --- 6. Milestone auto-recognition -------------------------------------------------------

@mss_extra_router.get("/milestones")
async def get_milestones(req: Request, payload: Dict = Depends(manager_role_required)):
    manager_uuid = payload.get("employee_uuid") or payload.get("sub")
    return await milestones_service.milestones_for_manager(_db(req), manager_uuid)


# --- 8. Manager nudges + command-center digest -------------------------------------------

@mss_extra_router.get("/nudges")
async def get_nudges(req: Request, payload: Dict = Depends(manager_role_required)):
    wfm_service = getattr(req.app.state, "wfm_service", None)
    if not wfm_service:
        raise HTTPException(status_code=503, detail="Workforce planning service unavailable.")
    return await nudges_svc.nudges_for_manager(req, payload, wfm_service, _db(req))
