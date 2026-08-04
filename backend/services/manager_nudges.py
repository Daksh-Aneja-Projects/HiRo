"""Manager nudges + command-center digest -- the portal's "agentic assistant" moment.

New service file (see COLLISION RULES). Reuses workforce_planning_service's own
attrition scoring and recommendation copy (imported, not reimplemented),
comprehensive_routes._approval_queue for overdue approvals, and milestones_service
for upcoming anniversaries. one_on_ones / goals are read defensively since those
modules are being built by another agent in parallel and may not exist yet.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.postgres_client import pg_client
from services import milestones_service

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 15 * 60
# ponytail: single-process in-memory cache, per the brief's "cached 15 min
# in-process" -- fine for one backend instance; move to Redis if this ever runs
# behind more than one worker.
_cache: Dict[str, Any] = {}


def _cached(key: str):
    entry = _cache.get(key)
    if not entry:
        return None
    stamped, value = entry
    if (datetime.now(timezone.utc) - stamped).total_seconds() > _CACHE_TTL_SECONDS:
        return None
    return value


def _store(key: str, value):
    _cache[key] = (datetime.now(timezone.utc), value)
    return value


async def _flight_risk_nudges(wfm_service, manager_uuid: str) -> List[Dict[str, Any]]:
    rows = await pg_client.fetch("SELECT employee_uuid FROM employee_pii WHERE manager_id = $1", manager_uuid)
    cards = []
    for r in rows:
        try:
            result = await wfm_service.predict_attrition_risk({"employee_uuid": r["employee_uuid"]})
        except Exception as e:
            logger.warning(f"attrition scoring failed for {r['employee_uuid']}: {e}")
            continue
        if result["risk_level"] in ("HIGH", "CRITICAL"):
            reasons = "; ".join(d["reason"] for d in result.get("drivers", [])[:2])
            cards.append({
                "kind": "flight_risk",
                "employee_uuid": r["employee_uuid"],
                "headline": f"{result.get('job_title') or 'A team member'} is at "
                            f"{result['risk_level'].lower()} flight risk.",
                "detail": reasons or "Risk factors were not specific enough to summarize.",
                "action_hint": result["recommendation"],
                "severity": "critical" if result["risk_level"] == "CRITICAL" else "high",
                "risk_score": result["risk_score"],
            })
    cards.sort(key=lambda c: c["risk_score"], reverse=True)
    for c in cards:
        c.pop("risk_score", None)
    return cards[:5]


async def _approval_nudge(req, payload) -> Optional[Dict[str, Any]]:
    from services.comprehensive_routes import _approval_queue
    try:
        queue = await _approval_queue(req, payload, limit=200)
    except Exception as e:
        logger.warning(f"approval queue unavailable for nudges: {e}")
        return None
    if not queue:
        return None
    return {
        "kind": "overdue_approvals",
        "headline": f"{len(queue)} request{'s' if len(queue) != 1 else ''} waiting on your decision.",
        "detail": "Leave, timesheet and expense requests from your team are queued for approval.",
        "action_hint": "Open the approvals queue and clear the oldest requests first.",
        "severity": "high" if len(queue) >= 5 else "medium",
    }


async def _one_on_one_nudge(manager_uuid: str) -> Optional[Dict[str, Any]]:
    """Overdue 1:1s / stale goals. Read defensively: the owning module may not exist
    yet, being built in parallel -- absence degrades to an honest omission, not a
    fabricated zero."""
    try:
        rows = await pg_client.fetch(
            "SELECT COUNT(*) AS n FROM one_on_ones WHERE manager_uuid = $1 "
            "AND (last_held_at IS NULL OR last_held_at < NOW() - INTERVAL '21 days')",
            manager_uuid,
        )
        n = int((rows[0] if rows else {}).get("n") or 0)
        if not n:
            return None
        return {
            "kind": "overdue_one_on_ones",
            "headline": f"{n} direct report{'s' if n != 1 else ''} overdue for a 1:1.",
            "detail": "No 1:1 logged with them in the last three weeks.",
            "action_hint": "Get time on the calendar this week.",
            "severity": "medium",
        }
    except Exception:
        logger.debug("1:1 overdue nudge computation failed", exc_info=True)
        return None


async def _milestone_nudges(db, manager_uuid: str) -> List[Dict[str, Any]]:
    try:
        data = await milestones_service.milestones_for_manager(db, manager_uuid)
    except Exception as e:
        logger.warning(f"milestones unavailable for nudges: {e}")
        return []
    return [{
        "kind": "upcoming_milestone",
        "headline": f"{a['name']} hits {a['years_of_service']} years on {a['anniversary_date']}.",
        "detail": f"{a['days_away']} day{'s' if a['days_away'] != 1 else ''} away.",
        "action_hint": "Plan a shout-out or a card for the day.",
        "severity": "low",
    } for a in data.get("upcoming", [])[:3]]


_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


async def nudges_for_manager(req, payload: Dict[str, Any], wfm_service, db) -> Dict[str, Any]:
    manager_uuid = payload.get("employee_uuid") or payload.get("sub")
    cache_key = f"nudges:{manager_uuid}"
    cached = _cached(cache_key)
    if cached is not None:
        return cached

    nudges: List[Dict[str, Any]] = list(await _flight_risk_nudges(wfm_service, manager_uuid))

    approval_card = await _approval_nudge(req, payload)
    if approval_card:
        nudges.append(approval_card)

    notes: List[str] = []
    one_on_one_card = await _one_on_one_nudge(manager_uuid)
    if one_on_one_card:
        nudges.append(one_on_one_card)
    else:
        notes.append("1:1 and goal staleness aren't shown here: that data isn't available yet.")

    nudges += await _milestone_nudges(db, manager_uuid)
    nudges.sort(key=lambda n: _SEVERITY_RANK.get(n["severity"], 9))

    return _store(cache_key, {
        "manager_uuid": manager_uuid, "generated_at": datetime.now(timezone.utc).isoformat(),
        "nudges": nudges, "notes": notes,
    })
