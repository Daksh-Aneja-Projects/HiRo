"""Engagement / eNPS pulse surveys. New service file (see COLLISION RULES).

Function-based, matching services/social_recognition.py's style: callers pass a
motor `db` handle so this is unit-testable with a fake.
"""
import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Below this many responses, individual comments would be identifiable against a
# small team -- theme/comment breakdowns are withheld, scores are still shown.
ANONYMITY_FLOOR = 5


def _response_hash(username: str, survey_id: str) -> str:
    """One-way identifier so a raw username is never stored against a response.
    This -- not access control -- is what keeps a pulse response anonymous."""
    return hashlib.sha256(f"{username}:{survey_id}".encode()).hexdigest()


def current_survey_id() -> str:
    """The one open survey, rotating monthly. HiRo has no survey-campaign admin
    screen; a rolling monthly window covers "once per open survey" without
    building one. Skipped: multi-survey scheduling, add when a real cadence needs it."""
    return datetime.now(timezone.utc).strftime("pulse-%Y-%m")


async def submit_pulse(db, *, username: str, score: Any, comment: Optional[str],
                        survey_id: Optional[str] = None) -> Dict[str, Any]:
    survey_id = survey_id or current_survey_id()
    try:
        score = int(score)
    except (TypeError, ValueError):
        raise ValueError("score must be a whole number from 0 to 10.")
    if not 0 <= score <= 10:
        raise ValueError("score must be between 0 and 10.")

    username_hash = _response_hash(username, survey_id)
    # ponytail: check-then-insert, not a unique index -- a race between two
    # concurrent submits from the same person is a demo-scale, not production-scale,
    # risk here. Add a unique index on (survey_id, username_hash) if that changes.
    if await db.pulse_responses.find_one({"survey_id": survey_id, "username_hash": username_hash}):
        raise ValueError("You have already responded to this survey.")

    await db.pulse_responses.insert_one({
        "survey_id": survey_id, "username_hash": username_hash, "score": score,
        "comment": (comment or "").strip()[:1000],
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"survey_id": survey_id, "status": "recorded"}


async def engagement_summary(db, ai_service, total_accounts: int,
                              survey_id: Optional[str] = None) -> Dict[str, Any]:
    """eNPS arithmetic + response rate always; comment theming only at/above the
    anonymity floor, and only when the local LLM actually returns something usable."""
    survey_id = survey_id or current_survey_id()
    responses = await db.pulse_responses.find({"survey_id": survey_id}, {"_id": 0}).to_list(10000)
    n = len(responses)
    if n == 0:
        return {"survey_id": survey_id, "responses": 0, "response_rate_pct": 0.0,
                "enps": None, "themes": "unavailable", "note": "No responses yet for this survey."}

    promoters = sum(1 for r in responses if r["score"] >= 9)
    detractors = sum(1 for r in responses if r["score"] <= 6)
    enps = round((promoters - detractors) / n * 100, 1)
    response_rate = round(n / total_accounts * 100, 1) if total_accounts else None

    result: Dict[str, Any] = {
        "survey_id": survey_id, "responses": n, "response_rate_pct": response_rate,
        "enps": enps, "promoters": promoters, "detractors": detractors, "passives": n - promoters - detractors,
    }

    if n < ANONYMITY_FLOOR:
        result["themes"] = "unavailable"
        result["note"] = (f"Fewer than {ANONYMITY_FLOOR} responses ({n}) -- comment themes are withheld "
                           "so an individual response can't be identified. Scores only.")
        return result

    comments = [r["comment"] for r in responses if r.get("comment")]
    if not comments:
        result["themes"] = "unavailable"
        result["themes_note"] = "No comments were left to theme."
        return result
    if ai_service is None:
        result["themes"] = "unavailable"
        result["themes_note"] = "Theme clustering unavailable (AI service not configured)."
        return result

    try:
        clustered = await ai_service.generate_json_response(
            "Group these anonymous employee pulse-survey comments into 2 to 5 recurring themes. "
            "Paraphrase each representative quote rather than repeating it verbatim, to keep "
            "individual respondents from being identifiable.\n\n"
            + "\n".join(f"- {c}" for c in comments[:200]),
            {"themes": [{"theme": "string", "count": "number", "representative_quote": "string"}]},
            task_type="engagement_theming",
        )
        themes = clustered.get("themes") if isinstance(clustered, dict) else None
        if themes:
            result["themes"] = themes
        else:
            result["themes"] = "unavailable"
            result["themes_note"] = "The local model did not return usable themes; scores above are unaffected."
    except Exception as e:
        logger.warning(f"Pulse theme clustering unavailable: {e}")
        result["themes"] = "unavailable"
        result["themes_note"] = "Theme clustering unavailable (LLM unreachable); scores above are unaffected."

    return result
