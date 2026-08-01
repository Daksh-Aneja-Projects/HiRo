# /backend/services/retrieval.py
"""RAG retrieval over the rag_chunks table (no pgvector -- plain float8[]).

# ponytail: brute-force cosine similarity computed in Python over every row
# in rag_chunks. Fine while the corpus is a few hundred chunks; move to
# pgvector (or at least server-side ORDER BY) if it ever grows past ~50k.
"""
import json
import logging
import uuid as _uuid
from typing import Any, Dict, List, Optional

from config.settings import settings
from services.ai_services import AIService, AIServiceError
from services.postgres_client import pg_client

logger = logging.getLogger(__name__)


def chunk_text(text: str, size: int = 1000, overlap: int = 150) -> List[str]:
    """Fixed-size character chunks with overlap. Stdlib only."""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    step = max(1, size - overlap)
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start:start + size])
        if start + size >= len(text):
            break
        start += step
    return chunks


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


async def _helpfulness_boosts(mongo_client) -> Dict[str, float]:
    """Bounded +/-0.05 nudge per chunk id, from recorded HRSD resolution outcomes.

    Chunks that solved tickets rank up a little; chunks attached to unhelpful
    suggestions rank down a little. Relevance (cosine) still dominates.
    """
    if mongo_client is None:
        return {}
    try:
        col = mongo_client[settings.MONGO_DB_NAME]["ai_resolution_outcomes"]
        tally: Dict[str, int] = {}
        async for doc in col.find({}, {"chunk_ids": 1, "helpful": 1}):
            sign = 1 if doc.get("helpful") else -1
            for cid in doc.get("chunk_ids") or []:
                tally[cid] = tally.get(cid, 0) + sign
        return {cid: max(-0.05, min(0.05, 0.02 * n)) for cid, n in tally.items()}
    except Exception as e:
        logger.warning(f"Helpfulness boost lookup failed: {e}")
        return {}


async def retrieve(question: str, ai_service: AIService, top_k: int = 4,
                    source_type: Optional[str] = None, mongo_client=None) -> List[Dict[str, Any]]:
    """Top-k [{chunk, score}] by cosine similarity (+ bounded helpfulness boost).

    Returns [] when the corpus is empty -- never raises for "nothing
    matched". Raises AIServiceError only for a genuine embedding failure, so
    callers can tell "AI is down" apart from "nothing matched".
    """
    qvec = await ai_service.generate_embedding(question)

    query = "SELECT id, source_type, source_id, title, chunk_text, embedding, meta FROM rag_chunks"
    args: tuple = ()
    if source_type:
        query += " WHERE source_type = $1"
        args = (source_type,)
    rows = await pg_client.fetch(query, *args)
    if not rows:
        return []

    boosts = await _helpfulness_boosts(mongo_client)

    scored = []
    for row in rows:
        vec = [float(x) for x in (row.get("embedding") or [])]
        score = _cosine(qvec, vec) + boosts.get(str(row.get("id")), 0.0)
        scored.append((row, score))
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [{"chunk": r, "score": s} for r, s in scored[:top_k]]


async def index_text(ai_service: AIService, source_type: str, source_id: str,
                      title: str, text: str, meta: Optional[Dict[str, Any]] = None) -> int:
    """Chunk, embed and store `text` in rag_chunks. Returns chunks written.

    A failed embedding for one chunk is logged and skipped rather than
    aborting the whole document -- a partial index beats none.
    """
    written = 0
    for piece in chunk_text(text):
        try:
            vec = await ai_service.generate_embedding(piece)
        except AIServiceError as e:
            logger.warning(f"Embedding failed while indexing {source_id}: {e}")
            continue
        await pg_client.execute(
            "INSERT INTO rag_chunks (id, source_type, source_id, title, chunk_text, embedding, meta) "
            "VALUES ($1::uuid, $2, $3, $4, $5, $6, $7::jsonb)",
            str(_uuid.uuid4()), source_type, source_id, title, piece, vec, json.dumps(meta or {}),
        )
        written += 1
    return written
