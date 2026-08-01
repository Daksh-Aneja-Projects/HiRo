# /backend/services/agent_memory.py
"""Per-user conversation memory for the command bar / chat surfaces.

Mongo `agent_memory`: {username, role, turns:[{role, content, ts}], summary}.
Raw turns are capped at 20; past that, the oldest 10 are folded into a
running LLM summary so memory stays small without just dropping history.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config.settings import settings
from services.ai_services import AIService, AIServiceError

logger = logging.getLogger(__name__)

MAX_TURNS = 20
SUMMARIZE_BATCH = 10
COLLECTION = "agent_memory"


def _col(mongo_client):
    return mongo_client[settings.MONGO_DB_NAME][COLLECTION]


async def get_memory(mongo_client, username: str) -> Dict[str, Any]:
    doc = await _col(mongo_client).find_one({"username": username}, {"_id": 0})
    return doc or {"username": username, "role": None, "turns": [], "summary": ""}


def context_block(memory: Dict[str, Any], max_recent: int = 6) -> str:
    """Renders memory as plain text to inject as context ahead of a new prompt."""
    lines = []
    if memory.get("summary"):
        lines.append(f"Earlier in this conversation: {memory['summary']}")
    for turn in (memory.get("turns") or [])[-max_recent:]:
        lines.append(f"{turn.get('role', 'user')}: {turn.get('content', '')}")
    return "\n".join(lines)


async def _summarize(ai_service: AIService, prior_summary: str, turns: List[Dict[str, Any]]) -> str:
    transcript = "\n".join(f"{t.get('role', 'user')}: {t.get('content', '')}" for t in turns)
    prompt = (
        f"Prior summary: {prior_summary or '(none yet)'}\n\n"
        "Fold these older turns into the running summary. Keep concrete facts, "
        f"decisions and open questions; drop small talk. Under 120 words.\n\n{transcript}"
    )
    return (await ai_service.generate_text(
        prompt, system_instruction="You compress conversation history into a terse factual summary.",
    )).strip()


async def record_turn(mongo_client, ai_service: AIService, username: str, role: Optional[str],
                       message_role: str, content: str) -> None:
    """Appends one turn and folds the oldest batch into `summary` once the cap is hit."""
    memory = await get_memory(mongo_client, username)
    turns = list(memory.get("turns") or [])
    turns.append({"role": message_role, "content": content, "ts": datetime.now(timezone.utc).isoformat()})
    summary = memory.get("summary", "")

    if len(turns) > MAX_TURNS:
        oldest, rest = turns[:SUMMARIZE_BATCH], turns[SUMMARIZE_BATCH:]
        try:
            summary = await _summarize(ai_service, summary, oldest)
            turns = rest
        except AIServiceError as e:
            # Don't silently lose history because the model is unreachable --
            # leave turns over-cap for now and retry the fold on the next call.
            logger.warning(f"Memory summarization unavailable for {username}: {e}")

    await _col(mongo_client).update_one(
        {"username": username},
        {"$set": {"username": username, "role": role, "turns": turns, "summary": summary}},
        upsert=True,
    )
