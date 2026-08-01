"""People-lifecycle data layer: onboarding, goals/OKRs, one-on-ones, offboarding
knowledge/exit interviews, profile-change review, and notification preferences.

Follows the house pattern (see social_recognition.py / hr_modules.py): functions
take a Mongo `db` handle (or use the shared `pg_client`) so they are unit-testable
with a fake, and every write path has a matching read path exposed by a route.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from services.postgres_client import pg_client
from services.pii_vault import PIIVault
from services import notification_service as notify_svc

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Onboarding
# ---------------------------------------------------------------------------

# Equipment / access / intro tasks a new hire's plan starts from. HR can add
# more on top of this when creating a plan.
DEFAULT_ONBOARDING_TEMPLATE: List[Dict[str, Any]] = [
    {"description": "Laptop and core equipment issued", "owner": "hr", "due_offset_days": 0},
    {"description": "System access provisioned (email, VPN, HRIS)", "owner": "hr", "due_offset_days": 1},
    {"description": "Welcome conversation with your manager", "owner": "manager", "due_offset_days": 1},
    {"description": "Complete new-hire orientation", "owner": "employee", "due_offset_days": 3},
    {"description": "Meet the team and introduce yourself", "owner": "employee", "due_offset_days": 5},
]
_VALID_OWNERS = {"employee", "manager", "hr"}


def _plan_progress(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(items)
    done = sum(1 for i in items if i.get("status") == "DONE")
    return {"done": done, "total": total, "percent": round((done / total) * 100, 1) if total else 0.0}


async def create_onboarding_plan(db, *, employee_uuid: str, created_by: str,
                                 extra_items: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    if not employee_uuid:
        raise ValueError("employee_uuid is required.")
    now = datetime.now(timezone.utc).isoformat()
    items = []
    for spec in DEFAULT_ONBOARDING_TEMPLATE + (extra_items or []):
        owner = spec.get("owner") if spec.get("owner") in _VALID_OWNERS else "hr"
        items.append({
            "item_id": f"OBI-{uuid.uuid4().hex[:8].upper()}",
            "description": (spec.get("description") or "").strip() or "Onboarding task",
            "owner": owner,
            "due_offset_days": int(spec.get("due_offset_days") or 0),
            "status": "PENDING",
            "completed_at": None,
            "completed_by": None,
        })
    plan = {
        "plan_id": f"OBP-{uuid.uuid4().hex[:10].upper()}",
        "employee_uuid": employee_uuid,
        "created_by": created_by,
        "created_at": now,
        "items": items,
    }
    await db.onboarding_plans.insert_one(dict(plan))
    return plan


async def get_my_onboarding_plan(db, employee_uuid: str) -> Optional[Dict[str, Any]]:
    plan = await db.onboarding_plans.find_one(
        {"employee_uuid": employee_uuid}, {"_id": 0}, sort=[("created_at", -1)]
    )
    if not plan:
        return None
    plan["progress"] = _plan_progress(plan.get("items", []))
    return plan


async def complete_onboarding_item(db, *, item_id: str, completed_by: str,
                                   scope_uuids: Optional[List[str]] = None,
                                   allowed_owners: Sequence[str] = ("employee",)) -> Dict[str, Any]:
    """Mark one onboarding item done, and tell whoever else cares.

    A plan's items are owned by the employee, their manager or HR, and each owner
    closes their own. Two independent guards keep that honest:

    `scope_uuids` limits which people's plans the caller may touch at all: the
    employee passes their own uuid, a manager passes their direct reports, HR
    passes None for the whole organisation.

    `allowed_owners` limits which items within a reachable plan the caller may
    close. Without it an employee could close out the steps their manager and HR
    still owe them, which is how a plan reaches 100% with the work undone.
    """
    query: Dict[str, Any] = {"items.item_id": item_id}
    if scope_uuids is not None:
        query["employee_uuid"] = {"$in": list(scope_uuids)}
    plan = await db.onboarding_plans.find_one(query, {"_id": 0}, sort=[("created_at", -1)])
    if not plan:
        raise ValueError("There is no onboarding item with that id on a plan you can act on.")

    employee_uuid = plan["employee_uuid"]
    item = next((i for i in plan["items"] if i["item_id"] == item_id), None)
    if item and item.get("owner") not in allowed_owners:
        raise PermissionError(
            f"That step is {item.get('owner')}'s to complete, not yours."
        )

    now = datetime.now(timezone.utc).isoformat()
    if item and item.get("status") != "DONE":
        await db.onboarding_plans.update_one(
            {"plan_id": plan["plan_id"], "items.item_id": item_id},
            {"$set": {"items.$.status": "DONE", "items.$.completed_at": now, "items.$.completed_by": completed_by}},
        )
        item = {**item, "status": "DONE", "completed_at": now, "completed_by": completed_by}

        # Tell the manager, and the HR person who set up the plan, that progress
        # was made. A lost notification here must not undo the completion.
        await notify_svc.notify_manager_of(
            employee_uuid, notify_svc.KIND_ONBOARDING,
            "An onboarding task was completed",
            f"{item['description']} is now done.",
            link="/manager-portal?module=onboarding", related_id=plan["plan_id"],
        )
        creator = plan.get("created_by")
        if creator:
            creator_user = await db.users.find_one({"username": creator}, {"employee_uuid": 1})
            creator_uuid = (creator_user or {}).get("employee_uuid")
            if creator_uuid and creator_uuid != employee_uuid:
                await notify_svc.notify(
                    creator_uuid, notify_svc.KIND_ONBOARDING,
                    "An onboarding task was completed",
                    f"{item['description']} is now done for the plan you created.",
                    link="/hr-portal?module=onboarding", related_id=plan["plan_id"],
                )

    plan_items = [i if i["item_id"] != item_id else item for i in plan["items"]]
    return {"item": item, "progress": _plan_progress(plan_items)}


async def direct_report_uuids(manager_uuid: str) -> List[str]:
    """The employee uuids reporting to this manager, or an empty list.

    A lookup failure returns empty rather than raising, so a caller scoping a
    write by this list ends up able to touch nothing instead of everything.
    """
    try:
        rows = await pg_client.fetch(
            "SELECT employee_uuid FROM employee_pii WHERE manager_id = $1", manager_uuid
        )
    except Exception as e:
        logger.warning(f"direct-report lookup failed for {manager_uuid}: {e}")
        return []
    return [r["employee_uuid"] for r in rows]


async def get_team_onboarding(db, manager_uuid: str) -> List[Dict[str, Any]]:
    """Onboarding progress for this manager's direct reports."""
    report_ids = await direct_report_uuids(manager_uuid)
    if not report_ids:
        return []
    cursor = db.onboarding_plans.find({"employee_uuid": {"$in": report_ids}}, {"_id": 0}).sort("created_at", -1)
    plans = await cursor.to_list(length=500)
    for p in plans:
        p["progress"] = _plan_progress(p.get("items", []))
    return plans


# ---------------------------------------------------------------------------
# Goals / OKRs
# ---------------------------------------------------------------------------

_ACTIVE_STATUSES = {"active", "achieved", "dropped"}


async def create_goal(db, *, employee_uuid: str, title: str, description: str,
                      key_results: List[str], created_by: str, cycle_id: Optional[str] = None) -> Dict[str, Any]:
    title = (title or "").strip()
    if not title:
        raise ValueError("A goal needs a title.")
    krs = [{"text": str(kr).strip(), "done": False} for kr in (key_results or []) if str(kr).strip()]
    now = datetime.now(timezone.utc).isoformat()
    goal = {
        "goal_id": f"GOAL-{uuid.uuid4().hex[:10].upper()}",
        "employee_uuid": employee_uuid,
        "title": title,
        "description": (description or "").strip(),
        "key_results": krs,
        "status": "active",
        "created_by": created_by,
        "cycle_id": cycle_id,
        "comments": [],
        "created_at": now,
        "updated_at": now,
    }
    await db.goals.insert_one(dict(goal))
    return goal


async def list_goals(db, employee_uuid: str) -> List[Dict[str, Any]]:
    cursor = db.goals.find({"employee_uuid": employee_uuid}, {"_id": 0}).sort("created_at", -1)
    return await cursor.to_list(length=500)


_UPDATABLE_GOAL_FIELDS = {"title", "description", "key_results", "status"}


async def update_goal(db, *, goal_id: str, employee_uuid: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    goal = await db.goals.find_one({"goal_id": goal_id, "employee_uuid": employee_uuid}, {"_id": 0})
    if not goal:
        raise ValueError("There is no goal with that id on your account.")
    changes = {k: v for k, v in (updates or {}).items() if k in _UPDATABLE_GOAL_FIELDS}
    if "status" in changes and changes["status"] not in _ACTIVE_STATUSES:
        raise ValueError(f"status must be one of {sorted(_ACTIVE_STATUSES)}.")
    if "key_results" in changes:
        changes["key_results"] = [
            kr if isinstance(kr, dict) else {"text": str(kr), "done": False}
            for kr in (changes["key_results"] or [])
        ]
    if not changes:
        return goal
    changes["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.goals.update_one({"goal_id": goal_id}, {"$set": changes})
    return {**goal, **changes}


async def delete_goal(db, *, goal_id: str, employee_uuid: str) -> bool:
    result = await db.goals.delete_one({"goal_id": goal_id, "employee_uuid": employee_uuid})
    return result.deleted_count > 0


async def list_team_goals(db, manager_uuid: str) -> List[Dict[str, Any]]:
    try:
        rows = await pg_client.fetch(
            "SELECT employee_uuid FROM employee_pii WHERE manager_id = $1", manager_uuid
        )
    except Exception as e:
        logger.warning(f"direct-report lookup failed for {manager_uuid}: {e}")
        return []
    report_ids = [r["employee_uuid"] for r in rows]
    if not report_ids:
        return []
    cursor = db.goals.find({"employee_uuid": {"$in": report_ids}}, {"_id": 0}).sort("updated_at", -1)
    return await cursor.to_list(length=500)


async def add_goal_comment(db, *, goal_id: str, manager_uuid: str, text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    if not text:
        raise ValueError("Comment cannot be empty.")
    goal = await db.goals.find_one({"goal_id": goal_id}, {"_id": 0})
    if not goal:
        raise ValueError("There is no goal with that id.")
    row = await pg_client.fetchrow(
        "SELECT 1 AS ok FROM employee_pii WHERE employee_uuid = $1 AND manager_id = $2",
        goal["employee_uuid"], manager_uuid,
    )
    if not row:
        raise PermissionError("You can only comment on your own direct reports' goals.")
    comment = {"by": manager_uuid, "text": text, "at": datetime.now(timezone.utc).isoformat()}
    await db.goals.update_one({"goal_id": goal_id}, {"$push": {"comments": comment}})
    await notify_svc.notify(
        goal["employee_uuid"], notify_svc.KIND_APPROVAL_WAITING,
        "Your manager commented on a goal",
        f'On "{goal["title"]}": {text}',
        link="/employee-portal?module=goals", related_id=goal_id,
    )
    return {**goal, "comments": goal.get("comments", []) + [comment]}


async def goals_summary(db, employee_uuid: str) -> Dict[str, int]:
    """achieved/total counts, the shape the UDM's unused goals_achieved/goals_total fields
    were meant to carry. Dropped goals don't count toward either side."""
    goals = await list_goals(db, employee_uuid)
    live = [g for g in goals if g.get("status") in ("active", "achieved")]
    achieved = sum(1 for g in live if g.get("status") == "achieved")
    return {"achieved": achieved, "total": len(live)}


GOAL_DRAFT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "A short, specific goal title."},
        "key_results": {
            "type": "array", "items": {"type": "string"},
            "description": "Exactly three measurable, time-bound key results.",
        },
    },
    "required": ["title", "key_results"],
}


async def draft_goal(ai_service, intent: str) -> Dict[str, Any]:
    intent = (intent or "").strip()
    if not intent:
        raise ValueError("Describe what you want the goal to achieve.")
    draft = await ai_service.generate_json_response(
        f"Turn this into a goal with measurable, time-bound key results.\n\nIntent: {intent}\n\n"
        "key_results must each state a concrete number or date so progress can be checked objectively.",
        GOAL_DRAFT_SCHEMA, task_type="goal_drafting",
    )
    if not draft or not draft.get("title"):
        raise ValueError("The model could not turn that into a goal. Try describing it differently.")
    krs = [str(kr).strip() for kr in (draft.get("key_results") or []) if str(kr).strip()][:3]
    return {"title": str(draft["title"])[:200], "key_results": krs}


# ---------------------------------------------------------------------------
# One-on-ones (Postgres)
# ---------------------------------------------------------------------------

ONE_ON_ONE_OVERDUE_DAYS = 30

_ONE_ON_ONE_DDL = """
CREATE TABLE IF NOT EXISTS public.one_on_ones (
    id SERIAL PRIMARY KEY,
    manager_uuid VARCHAR(50) NOT NULL,
    employee_uuid VARCHAR(50) NOT NULL,
    held_at TIMESTAMPTZ NOT NULL,
    talking_points TEXT,
    notes TEXT,
    shared_with_employee BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_one_on_ones_employee ON public.one_on_ones (employee_uuid, held_at DESC);
CREATE INDEX IF NOT EXISTS idx_one_on_ones_manager ON public.one_on_ones (manager_uuid, held_at DESC);
"""
_one_on_one_schema_ready = False


async def _ensure_one_on_one_schema() -> None:
    global _one_on_one_schema_ready
    if _one_on_one_schema_ready:
        return
    try:
        await pg_client.execute(_ONE_ON_ONE_DDL)
    except Exception as e:
        logger.warning(f"Could not prepare the one_on_ones table: {e}")
    _one_on_one_schema_ready = True


def _row_to_one_on_one(r: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": r["id"], "manager_uuid": r["manager_uuid"], "employee_uuid": r["employee_uuid"],
        "held_at": r["held_at"].isoformat() if hasattr(r["held_at"], "isoformat") else r["held_at"],
        "talking_points": r.get("talking_points"), "notes": r.get("notes"),
        "shared_with_employee": bool(r.get("shared_with_employee")),
    }


async def create_one_on_one(*, manager_uuid: str, employee_uuid: str, held_at, talking_points: str = "",
                            notes: str = "", shared_with_employee: bool = False) -> Dict[str, Any]:
    await _ensure_one_on_one_schema()
    row = await pg_client.fetchrow(
        """INSERT INTO one_on_ones (manager_uuid, employee_uuid, held_at, talking_points, notes, shared_with_employee)
           VALUES ($1, $2, $3, $4, $5, $6) RETURNING *""",
        manager_uuid, employee_uuid, held_at, talking_points, notes, shared_with_employee,
    )
    if shared_with_employee:
        await notify_svc.notify(
            employee_uuid, notify_svc.KIND_APPROVAL_WAITING,
            "Your manager shared 1:1 notes with you",
            "New notes from your one-on-one are available.",
            link="/employee-portal?module=one-on-ones", related_id=str(row["id"]),
        )
    return _row_to_one_on_one(row)


async def list_one_on_ones(*, manager_uuid: Optional[str] = None, employee_uuid: Optional[str] = None,
                           shared_only: bool = False) -> List[Dict[str, Any]]:
    await _ensure_one_on_one_schema()
    clauses, args = [], []
    if manager_uuid:
        args.append(manager_uuid); clauses.append(f"manager_uuid = ${len(args)}")
    if employee_uuid:
        args.append(employee_uuid); clauses.append(f"employee_uuid = ${len(args)}")
    if shared_only:
        clauses.append("shared_with_employee = TRUE")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = await pg_client.fetch(f"SELECT * FROM one_on_ones {where} ORDER BY held_at DESC", *args)
    return [_row_to_one_on_one(r) for r in rows]


async def update_one_on_one(*, one_on_one_id: int, manager_uuid: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Scoped to the manager who created the meeting record."""
    await _ensure_one_on_one_schema()
    allowed = {"talking_points", "notes", "shared_with_employee", "held_at"}
    changes = {k: v for k, v in (updates or {}).items() if k in allowed}
    if not changes:
        raise ValueError("No updatable fields supplied.")
    set_clause = ", ".join(f"{k} = ${i + 3}" for i, k in enumerate(changes))
    row = await pg_client.fetchrow(
        f"""UPDATE one_on_ones SET {set_clause} WHERE id = $1 AND manager_uuid = $2 RETURNING *""",
        one_on_one_id, manager_uuid, *changes.values(),
    )
    if not row:
        raise ValueError("There is no one-on-one with that id on your own calendar.")
    return _row_to_one_on_one(row)


async def delete_one_on_one(*, one_on_one_id: int, manager_uuid: str) -> bool:
    await _ensure_one_on_one_schema()
    result = await pg_client.execute(
        "DELETE FROM one_on_ones WHERE id = $1 AND manager_uuid = $2", one_on_one_id, manager_uuid
    )
    try:
        return int(str(result).rsplit(" ", 1)[-1]) > 0
    except (ValueError, AttributeError):
        return False


async def one_on_one_status(manager_uuid: str) -> List[Dict[str, Any]]:
    """Per direct report: when they last had a 1:1, and whether it's overdue."""
    await _ensure_one_on_one_schema()
    try:
        reports = await pg_client.fetch(
            "SELECT employee_uuid FROM employee_pii WHERE manager_id = $1", manager_uuid
        )
    except Exception as e:
        logger.warning(f"direct-report lookup failed for {manager_uuid}: {e}")
        return []
    last_rows = await pg_client.fetch(
        "SELECT employee_uuid, MAX(held_at) AS last_held FROM one_on_ones WHERE manager_uuid = $1 GROUP BY employee_uuid",
        manager_uuid,
    )
    last_by_employee = {r["employee_uuid"]: r["last_held"] for r in last_rows}
    now = datetime.now(timezone.utc)
    out = []
    for r in reports:
        emp = r["employee_uuid"]
        last_held = last_by_employee.get(emp)
        days_since = (now - last_held).days if last_held else None
        out.append({
            "employee_uuid": emp,
            "last_held_at": last_held.isoformat() if last_held else None,
            "days_since": days_since,
            "overdue": days_since is None or days_since > ONE_ON_ONE_OVERDUE_DAYS,
        })
    return out


# ---------------------------------------------------------------------------
# Offboarding: knowledge read-back + exit interviews
# ---------------------------------------------------------------------------

async def list_offboarding_knowledge(db, employee_uuid: Optional[str] = None) -> List[Dict[str, Any]]:
    """Reads the same `offboarding_knowledge` collection HRModulesService writes to."""
    query = {"employee_uuid": employee_uuid} if employee_uuid else {}
    cursor = db.offboarding_knowledge.find(query, {"_id": 0}).sort("submitted_at", -1).limit(500)
    return await cursor.to_list(length=500)


EXIT_REASONS = [
    "compensation", "career_growth", "management", "relocation", "work_life_balance",
    "role_fit", "company_direction", "retirement", "other",
]


async def submit_exit_interview(db, *, employee_uuid: str, reasons: List[str], comments: str,
                                would_recommend: bool) -> Dict[str, Any]:
    clean_reasons = [r for r in (reasons or []) if r in EXIT_REASONS]
    if not clean_reasons:
        raise ValueError(f"Choose at least one reason from {EXIT_REASONS}.")
    doc = {
        "interview_id": f"EXIT-{uuid.uuid4().hex[:10].upper()}",
        "employee_uuid": employee_uuid,
        "reasons": clean_reasons,
        "comments": (comments or "").strip(),
        "would_recommend": bool(would_recommend),
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.exit_interviews.insert_one(dict(doc))
    return doc


async def list_exit_interviews(db) -> Dict[str, Any]:
    cursor = db.exit_interviews.find({}, {"_id": 0}).sort("submitted_at", -1).limit(1000)
    interviews = await cursor.to_list(length=1000)
    reason_counts: Dict[str, int] = {}
    for iv in interviews:
        for r in iv.get("reasons", []):
            reason_counts[r] = reason_counts.get(r, 0) + 1
    return {"interviews": interviews, "reason_counts": reason_counts, "count": len(interviews)}


# ---------------------------------------------------------------------------
# Profile-change review (closes the PENDING_REVIEW dead end)
# ---------------------------------------------------------------------------

_PENDING_STATUSES = ("PENDING", "PENDING_REVIEW")

# Only fields with a real encrypted column in employee_pii can be safely applied.
# phone/address/emergency_contact were accepted by the self-service form but have
# no backing column at all -- applying them would either crash on an unknown
# column or silently discard the value, so they are honestly refused instead.
_APPLIABLE_FIELDS = {
    "email": "email_encrypted",
    "full_name": "full_name_encrypted",
}


async def list_pending_profile_change_requests(mongo_db) -> List[Dict[str, Any]]:
    cursor = mongo_db.profile_change_requests.find(
        {"status": {"$in": list(_PENDING_STATUSES)}}, {"_id": 0}
    ).sort("submitted_at", 1)
    return await cursor.to_list(length=500)


async def decide_profile_change_request(mongo_db, *, request_id: str, approve: bool,
                                        comments: str, decided_by: str) -> Dict[str, Any]:
    req = await mongo_db.profile_change_requests.find_one({"request_id": request_id}, {"_id": 0})
    if not req:
        raise ValueError("There is no profile-change request with that id.")
    if req.get("status") not in _PENDING_STATUSES:
        raise ValueError(f"This request was already decided ({req.get('status')}).")

    employee_uuid = req.get("employee_uuid")
    now = datetime.now(timezone.utc).isoformat()

    if not approve:
        await mongo_db.profile_change_requests.update_one(
            {"request_id": request_id},
            {"$set": {"status": "REJECTED", "decided_by": decided_by, "decided_at": now, "decision_comments": comments}},
        )
        if employee_uuid:
            await notify_svc.notify(
                employee_uuid, notify_svc.KIND_APPROVAL_WAITING,
                "Your profile change request was declined",
                notify_svc.decision_sentence("profile change request", False, detail=(comments or "").strip()),
                link="/employee-portal?module=profile", related_id=request_id,
            )
        return {"status": "REJECTED", "request_id": request_id, "field_results": {}}

    field_results: Dict[str, str] = {}
    vault = PIIVault.get_instance()
    requested_changes = req.get("requested_changes") or {}
    for field, value in requested_changes.items():
        column = _APPLIABLE_FIELDS.get(field)
        if not column or not employee_uuid:
            field_results[field] = "REFUSED: no employee_pii column exists to store this field safely."
            continue
        try:
            encrypted, _ = vault.encrypt(str(value), data_context=f"PROFILE_CHANGE_{field.upper()}")
            await pg_client.execute(f"UPDATE employee_pii SET {column} = $1 WHERE employee_uuid = $2",
                                    encrypted, employee_uuid)
            field_results[field] = "APPLIED"
        except Exception as e:
            logger.error(f"profile-change apply failed for {field}: {e}")
            field_results[field] = f"FAILED: {e}"

    applied_any = any(v == "APPLIED" for v in field_results.values())
    refused_any = any(v != "APPLIED" for v in field_results.values())
    final_status = "APPROVED" if applied_any and not refused_any else (
        "PARTIALLY_APPLIED" if applied_any else "REFUSED")

    await mongo_db.profile_change_requests.update_one(
        {"request_id": request_id},
        {"$set": {"status": final_status, "decided_by": decided_by, "decided_at": now,
                  "decision_comments": comments, "field_results": field_results}},
    )
    if employee_uuid:
        summary = "; ".join(f"{k}: {v}" for k, v in field_results.items()) or "no fields were requested"
        await notify_svc.notify(
            employee_uuid, notify_svc.KIND_APPROVAL_WAITING,
            "Your profile change request was reviewed",
            f"Result: {final_status}. {summary}",
            link="/employee-portal?module=profile", related_id=request_id,
        )
    return {"status": final_status, "request_id": request_id, "field_results": field_results}


# ---------------------------------------------------------------------------
# Notification preferences
# ---------------------------------------------------------------------------

DEFAULT_NOTIFICATION_KINDS = [
    "leave", "timesheet", "expense", "approval", "case", "policy", "onboarding", "performance",
]


async def get_notification_preferences(db, employee_uuid: str, username: str) -> Dict[str, Any]:
    doc = await db.notification_prefs.find_one({"employee_uuid": employee_uuid}, {"_id": 0})
    kinds = {k: True for k in DEFAULT_NOTIFICATION_KINDS}
    if doc:
        kinds.update({k: bool(v) for k, v in (doc.get("kinds") or {}).items() if k in DEFAULT_NOTIFICATION_KINDS})
    return {"employee_uuid": employee_uuid, "username": username, "kinds": kinds}


async def set_notification_preferences(db, employee_uuid: str, username: str, kinds: Dict[str, bool]) -> Dict[str, Any]:
    clean = {k: bool(v) for k, v in (kinds or {}).items() if k in DEFAULT_NOTIFICATION_KINDS}
    await db.notification_prefs.update_one(
        {"employee_uuid": employee_uuid},
        {"$set": {"employee_uuid": employee_uuid, "username": username, "kinds": clean,
                  "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return await get_notification_preferences(db, employee_uuid, username)
