"""Talent Intelligence: internal mobility matching, succession planning (nominations +
9-box), and the lightweight candidate pipeline (ATS).

New service file (see COLLISION RULES in the build brief) -- does not edit
workforce_planning_service.py or talent_acquisition_service.py, but reuses their
conventions (career ladders, required skills, the PII vault, correlated-subquery-free
aggregation) via direct import. Functions take pg_client/mongo handles rather than
wrapping a class, matching services/social_recognition.py's style.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.postgres_client import pg_client
from services.pii_vault import PIIVault
from services.career_ladders import LADDERS
from services.skill_requirements import REQUIRED_SKILLS

logger = logging.getLogger(__name__)

READINESS_VALUES = ("ready_now", "ready_soon", "develop")
CANDIDATE_STAGES = ("applied", "screen", "interview", "offer", "hired", "rejected")
_NEXT_STAGE = {"applied": "screen", "screen": "interview", "interview": "offer", "offer": "hired"}


async def names_for_uuids(uuids: List[str]) -> Dict[str, str]:
    """Real names for a set of employee uuids, decrypted from the PII vault.
    Shared by succession plans and comp cycles so a line item shows a person, not a uuid."""
    if not uuids:
        return {}
    vault = PIIVault.get_instance()
    rows = await vault.execute_pii_query(
        "SELECT employee_uuid, full_name_encrypted FROM employee_pii WHERE employee_uuid = ANY($1)",
        "employee_pii", "TalentIntelligence", None, uuids,
    )
    return {r["employee_uuid"]: r.get("full_name") or r["employee_uuid"] for r in rows}


# ---------------------------------------------------------------------------
# 1. Internal mobility matching
# ---------------------------------------------------------------------------

# score = 0.5 x (skills held / skills the role needs) + 0.3 x career-ladder adjacency
#       + 0.2 x readiness (tenure + rating). Deterministic -- no LLM in the score itself.
MOBILITY_WEIGHTS = {"skills": 0.5, "ladder_adjacency": 0.3, "readiness": 0.2}


def _ladder_adjacency(dept_ladder: List[str], requisition_title: str, candidate_dept: str,
                       requisition_dept: str, candidate_title: str) -> float:
    """How natural a step this move is on the department's career ladder.

    1.0  - the requisition is exactly the next rung up from the candidate's title.
    0.6  - same department, within two rungs either way.
    0.3  - same department, further away, or a title not on record on the ladder.
    0.15 - a cross-department move: still a real internal move, just not a laddered step.
    """
    if candidate_dept != requisition_dept:
        return 0.15
    if requisition_title not in dept_ladder or candidate_title not in dept_ladder:
        return 0.3
    diff = dept_ladder.index(requisition_title) - dept_ladder.index(candidate_title)
    if diff == 1:
        return 1.0
    if -1 <= diff <= 2:
        return 0.6
    return 0.3


def _mobility_narrative(name: str, dept: str, title: str, matched: List[str], gaps: List[str],
                         adjacency: float, req_title: str) -> str:
    parts = [f"{name} is currently a {title} in {dept}."]
    if matched:
        parts.append(f"Already holds {len(matched)} of the skills this role needs: {', '.join(matched)}.")
    else:
        parts.append("Does not yet hold any of the named skills for this role.")
    if gaps:
        parts.append(f"Would need to build: {', '.join(gaps)}.")
    if adjacency >= 1.0:
        parts.append(f"{req_title} is the natural next step up from their current role.")
    elif adjacency <= 0.15:
        parts.append("This would be a cross-department move rather than a step up an existing ladder.")
    return " ".join(parts)


async def internal_matches_for_requisition(mongo_client, requisition: Dict[str, Any],
                                            limit: int = 10) -> Dict[str, Any]:
    """Rank internal candidates for an open requisition.

    Pool: anyone anywhere in the company who holds at least one of the role's required
    skills (found via Mongo employee_skills, not restricted to the requisition's own
    department -- an internal move across departments is the point of this feature).
    Capped at the top 150 skill matches before scoring, so a company-wide scan stays fast.
    """
    req_dept = requisition.get("department") or ""
    req_title = requisition.get("title") or ""
    needed = REQUIRED_SKILLS.get(req_dept, [])

    if not needed:
        return {"requisition_id": requisition.get("requisition_id"), "department": req_dept,
                "role": req_title, "matches": [],
                "note": f"No skill requirements are defined for '{req_dept}', so matches cannot be scored."}

    from config.settings import settings
    db = mongo_client[settings.MONGO_DB_NAME]
    cursor = db["employee_skills"].aggregate([
        {"$match": {"skills": {"$in": needed}}},
        {"$project": {"_id": 0, "employee_uuid": 1, "department": 1,
                      "matched": {"$setIntersection": ["$skills", needed]}}},
        {"$addFields": {"match_count": {"$size": "$matched"}}},
        {"$match": {"match_count": {"$gt": 0}}},
        {"$sort": {"match_count": -1}},
        {"$limit": 150},
    ])
    profiles = await cursor.to_list(150)
    if not profiles:
        return {"requisition_id": requisition.get("requisition_id"), "department": req_dept,
                "role": req_title, "matches": [],
                "note": "No employee on record holds any of the skills this role needs."}

    uuids = [p["employee_uuid"] for p in profiles]
    # Pre-aggregated join, not a per-row correlated subquery -- see
    # workforce_planning_service.succession_readiness for why that matters at this scale.
    rows = await pg_client.fetch(
        """SELECT e.employee_uuid, e.full_name_encrypted, e.department, e.job_title,
                  e.tenure_months, r.avg_rating
           FROM employee_pii e
           LEFT JOIN (SELECT employee_uuid, AVG(overall_rating) AS avg_rating
                      FROM performance_reviews GROUP BY employee_uuid) r
             ON r.employee_uuid = e.employee_uuid
           WHERE e.employee_uuid = ANY($1)""",
        uuids,
    )
    by_uuid = {r["employee_uuid"]: r for r in rows}
    vault = PIIVault.get_instance()
    dept_ladder = LADDERS.get(req_dept, [])

    scored = []
    for p in profiles:
        row = by_uuid.get(p["employee_uuid"])
        if not row:
            continue
        tenure = int(row.get("tenure_months") or 0)
        rating = float(row.get("avg_rating") or 0.0)
        skill_ratio = p["match_count"] / len(needed)
        candidate_dept = row.get("department") or ""
        adjacency = _ladder_adjacency(dept_ladder, req_title, candidate_dept, req_dept, row.get("job_title") or "")
        readiness = 0.5 * min(1.0, tenure / 24.0) + 0.5 * min(1.0, rating / 5.0)
        score = (MOBILITY_WEIGHTS["skills"] * skill_ratio +
                 MOBILITY_WEIGHTS["ladder_adjacency"] * adjacency +
                 MOBILITY_WEIGHTS["readiness"] * readiness)
        matched_skills = list(p["matched"])
        gaps = [s for s in needed if s not in matched_skills]
        try:
            name = vault.decrypt(row["full_name_encrypted"]) if row.get("full_name_encrypted") else row["employee_uuid"]
        except Exception:
            name = row["employee_uuid"]
        scored.append({
            "employee_uuid": row["employee_uuid"],
            "name": name,
            "current_department": candidate_dept,
            "current_title": row.get("job_title"),
            "tenure_months": tenure,
            "average_rating": round(rating, 2) if rating else None,
            "match_score": round(score * 100, 1),
            "matched_skills": matched_skills,
            "skill_gaps": gaps,
            "narrative": _mobility_narrative(name, candidate_dept, row.get("job_title") or "unknown role",
                                              matched_skills, gaps, adjacency, req_title),
        })

    scored.sort(key=lambda m: m["match_score"], reverse=True)
    return {
        "requisition_id": requisition.get("requisition_id"), "department": req_dept, "role": req_title,
        "score_formula": ("0.5 x (skills held / skills the role needs) + 0.3 x career-ladder adjacency "
                           "+ 0.2 x readiness (tenure and rating). Computed directly, no LLM in the score."),
        "matches": scored[:max(1, min(limit, 50))],
    }


# ---------------------------------------------------------------------------
# 2. Succession planning: nominations + 9-box
# ---------------------------------------------------------------------------

async def create_nomination(role_or_person_uuid: Optional[str], nominee_uuid: Optional[str],
                             nominated_by: str, readiness: Optional[str],
                             rationale: Optional[str]) -> Dict[str, Any]:
    if not role_or_person_uuid or not nominee_uuid:
        raise ValueError("role_or_person_uuid and nominee_uuid are required.")
    if readiness not in READINESS_VALUES:
        raise ValueError(f"readiness must be one of {READINESS_VALUES}.")
    row = await pg_client.fetchrow(
        """INSERT INTO succession_nominations
             (role_or_person_uuid, nominee_uuid, nominated_by, readiness, rationale)
           VALUES ($1,$2,$3,$4,$5)
           RETURNING id, role_or_person_uuid, nominee_uuid, nominated_by, readiness, rationale, created_at""",
        role_or_person_uuid, nominee_uuid, nominated_by, readiness, (rationale or "").strip()[:1000],
    )
    return dict(row)


async def succession_plan(wfm_service) -> Dict[str, Any]:
    """Nominations grouped by the critical role or incumbent they target, plus the
    department-level succession-readiness aggregates workforce_planning_service already
    computes (reused, not recomputed)."""
    rows = await pg_client.fetch(
        "SELECT id, role_or_person_uuid, nominee_uuid, nominated_by, readiness, rationale, created_at "
        "FROM succession_nominations ORDER BY role_or_person_uuid, created_at DESC"
    )
    names = await names_for_uuids(list({r["nominee_uuid"] for r in rows}))

    by_role: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        by_role.setdefault(r["role_or_person_uuid"], []).append({
            "nomination_id": r["id"],
            "nominee_uuid": r["nominee_uuid"],
            "nominee_name": names.get(r["nominee_uuid"], r["nominee_uuid"]),
            "nominated_by": r["nominated_by"],
            "readiness": r["readiness"],
            "rationale": r["rationale"],
            "created_at": r["created_at"],
        })

    readiness_by_dept = await wfm_service.succession_readiness() if wfm_service else {}
    return {
        "roles": [{"role_or_person": role, "nominations": noms} for role, noms in by_role.items()],
        "department_readiness": readiness_by_dept,
    }


PERFORMANCE_BUCKETS = (("Low", 0.0, 3.0), ("Solid", 3.0, 4.0), ("High", 4.0, 5.01))
POTENTIAL_BUCKETS = (("Low", 0.0, 0.4), ("Medium", 0.4, 0.7), ("High", 0.7, 1.01))


def _bucket(value: float, buckets) -> str:
    for label, lo, hi in buckets:
        if lo <= value < hi:
            return label
    return buckets[-1][0]


async def nine_box(mongo_client) -> Dict[str, Any]:
    """9-box grid for the leadership pipeline: the senior-band roles and the one-to-two
    rungs below them in each department -- the exact population
    workforce_planning_service.succession_readiness() scores as "ready" or "senior".

    Performance axis: measured, average performance-review rating (0-5).
    Potential axis: NOT measured. A documented heuristic --
        potential = 0.4 x (tenure_months / 60, capped at 1) + 0.6 x (skills held / skills the
        department needs, capped at 1). Skills breadth is weighted higher than raw tenure
        because time served alone is a weak signal of future potential.
    """
    pipeline_titles: List[str] = []
    dept_of_title: Dict[str, str] = {}
    for dept, ladder in LADDERS.items():
        senior_from = max(1, len(ladder) - 2)
        band = ladder[max(0, senior_from - 2):]
        pipeline_titles.extend(band)
        for t in band:
            dept_of_title.setdefault(t, dept)

    rows = await pg_client.fetch(
        """SELECT e.employee_uuid, e.full_name_encrypted, e.department, e.job_title,
                  e.tenure_months, r.avg_rating
           FROM employee_pii e
           LEFT JOIN (SELECT employee_uuid, AVG(overall_rating) AS avg_rating
                      FROM performance_reviews GROUP BY employee_uuid) r
             ON r.employee_uuid = e.employee_uuid
           WHERE e.job_title = ANY($1)""",
        pipeline_titles,
    )
    if not rows:
        return {"cells": [], "population": 0,
                "note": "No one currently sits in a leadership-pipeline role."}

    from config.settings import settings
    skill_counts: Dict[str, int] = {}
    if mongo_client is not None:
        db = mongo_client[settings.MONGO_DB_NAME]
        uuids = [r["employee_uuid"] for r in rows]
        cursor = db["employee_skills"].aggregate([
            {"$match": {"employee_uuid": {"$in": uuids}}},
            {"$project": {"_id": 0, "employee_uuid": 1, "n": {"$size": {"$ifNull": ["$skills", []]}}}},
        ])
        async for doc in cursor:
            skill_counts[doc["employee_uuid"]] = doc["n"]

    vault = PIIVault.get_instance()
    grid: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        rating = float(r.get("avg_rating") or 0.0)
        tenure = int(r.get("tenure_months") or 0)
        dept = r.get("department") or dept_of_title.get(r.get("job_title"), "Unknown")
        needed = len(REQUIRED_SKILLS.get(dept, [])) or 1
        breadth = min(1.0, skill_counts.get(r["employee_uuid"], 0) / needed)
        potential = 0.4 * min(1.0, tenure / 60.0) + 0.6 * breadth
        perf_label, pot_label = _bucket(rating, PERFORMANCE_BUCKETS), _bucket(potential, POTENTIAL_BUCKETS)
        cell_key = f"{pot_label.lower()}_potential__{perf_label.lower()}_performance"
        cell = grid.setdefault(cell_key, {"performance": perf_label, "potential": pot_label,
                                           "count": 0, "people": []})
        cell["count"] += 1
        if len(cell["people"]) < 10:
            try:
                name = vault.decrypt(r["full_name_encrypted"]) if r.get("full_name_encrypted") else r["employee_uuid"]
            except Exception:
                name = r["employee_uuid"]
            cell["people"].append({"employee_uuid": r["employee_uuid"], "name": name,
                                    "department": dept, "job_title": r.get("job_title")})

    return {
        "cells": list(grid.values()),
        "population": len(rows),
        "scope": "Leadership pipeline: senior-band roles and the one-to-two rungs below them, per department.",
        "potential_is_heuristic": True,
        "heuristic_note": ("Potential is not measured. It is derived from tenure (40%) and skills "
                            "breadth relative to what the department needs (60%). Treat it as a "
                            "starting conversation, not a verdict."),
    }


# ---------------------------------------------------------------------------
# 3. Candidate pipeline (lightweight ATS)
# ---------------------------------------------------------------------------

def _legal_transition(current: str, target: str) -> bool:
    if target == "rejected":
        return current not in ("hired", "rejected")
    return _NEXT_STAGE.get(current) == target


async def create_candidate(db, *, requisition_id: str, name: Optional[str],
                            source: Optional[str], by: str) -> Dict[str, Any]:
    name = (name or "").strip()
    if not name:
        raise ValueError("Candidate name is required.")
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "candidate_id": f"CAND-{uuid.uuid4().hex[:10].upper()}",
        "requisition_id": requisition_id,
        "name": name,
        "source": (source or "unspecified").strip(),
        "stage": "applied",
        "notes": [],
        "stage_history": [{"stage": "applied", "at": now, "by": by}],
        "created_at": now,
    }
    await db.candidates.insert_one(dict(doc))
    doc.pop("_id", None)
    return doc


async def list_candidates(db, requisition_id: str) -> Dict[str, Any]:
    cursor = db.candidates.find({"requisition_id": requisition_id}, {"_id": 0}).sort("created_at", -1)
    candidates = await cursor.to_list(500)
    summary: Dict[str, int] = {}
    for c in candidates:
        summary[c["stage"]] = summary.get(c["stage"], 0) + 1
    return {"candidates": candidates, "pipeline_summary": summary}


async def advance_candidate(db, candidate_id: str, target_stage: str,
                             note: Optional[str], by: str) -> Dict[str, Any]:
    if target_stage not in CANDIDATE_STAGES:
        raise ValueError(f"Unknown stage '{target_stage}'.")
    candidate = await db.candidates.find_one({"candidate_id": candidate_id})
    if not candidate:
        raise ValueError(f"No candidate '{candidate_id}' on record.")
    current = candidate["stage"]
    if not _legal_transition(current, target_stage):
        raise ValueError(f"Cannot move a candidate from '{current}' to '{target_stage}'.")

    at = datetime.now(timezone.utc).isoformat()
    push: Dict[str, Any] = {"stage_history": {"stage": target_stage, "at": at, "by": by}}
    if note and note.strip():
        push["notes"] = {"by": by, "text": note.strip()[:1000], "at": at}
    await db.candidates.update_one({"candidate_id": candidate_id},
                                    {"$set": {"stage": target_stage}, "$push": push})

    result = {"candidate_id": candidate_id, "previous_stage": current, "stage": target_stage}
    if target_stage == "hired":
        result["onboarding_hint"] = ("This candidate is hired. Onboarding can be started for them "
                                      "from the Onboarding module when ready.")
    return result
