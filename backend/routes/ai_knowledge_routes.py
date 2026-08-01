# /backend/routes/ai_knowledge_routes.py
"""AI knowledge layer: grounded Q&A, corpus sync, HRSD auto-resolution and the
closed-loop stats surface. All new routing logic for this feature lives in
this single file (plus services/retrieval.py, services/grounded_answers.py,
services/agent_memory.py) so it can land alongside other in-flight backend
work without touching shared route files.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from config.settings import settings
from services import grounded_answers, retrieval
from services.auth_deps import employee_role_required, manager_role_required, policy_admin_role_required
from services.grounded_answers import CONFIDENCE_THRESHOLD
from services.postgres_client import pg_client

logger = logging.getLogger(__name__)

knowledge_router = APIRouter(prefix="/knowledge", tags=["AI Knowledge"])
hrsd_ai_router = APIRouter(prefix="/hrsd", tags=["HRSD AI Resolution"])


class AskRequest(BaseModel):
    question: str


class ResolutionFeedbackRequest(BaseModel):
    helpful: bool


# --------------------------------------------------------------------------
# Q&A
# --------------------------------------------------------------------------
@knowledge_router.post("/ask")
async def ask_knowledge(req: Request, body: AskRequest, payload: Dict = Depends(employee_role_required)):
    """Grounded answer with citations/confidence, or an honest refusal. Never fabricates."""
    ai_service = getattr(req.app.state, "ai_service", None)
    if not ai_service:
        raise HTTPException(status_code=503, detail="AI service unavailable.")
    mongo_client = getattr(req.app.state, "mongo_client", None)
    return await grounded_answers.answer_question(body.question, ai_service, mongo_client=mongo_client)


@knowledge_router.get("/tickets/{ticket_id}")
async def get_ticket_suggestion(req: Request, ticket_id: str, payload: Dict = Depends(employee_role_required)):
    """Read-only lookup of a ticket's AI-suggested resolution (if any)."""
    row = await pg_client.fetchrow(
        "SELECT ticket_id, status, metadata FROM hrsd_tickets WHERE ticket_id = $1", ticket_id)
    if not row:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    meta = row.get("metadata") or {}
    if isinstance(meta, str):
        meta = json.loads(meta)
    return {
        "ticket_id": row["ticket_id"],
        "status": row["status"],
        "suggested_resolution": meta.get("suggested_resolution"),
    }


# --------------------------------------------------------------------------
# Corpus sync + stats
# --------------------------------------------------------------------------
def _render_policy_ledger_doc(doc: Dict[str, Any]):
    """policy_ledger rows are terse governance events, not policy prose --
    render them into a readable sentence so they're something a question can
    actually match against."""
    p = doc.get("payload") or {}
    policy_id = p.get("policy_id", "unknown-policy")
    bits = [f"policy {policy_id}"]
    for key, label in (("event", "event"), ("action", "action"), ("status", "status"), ("version_id", "version")):
        if p.get(key):
            bits.append(f"{label} {p[key]}")
    text = (f"Policy governance record: {', '.join(bits)}. "
            f"Committed by {doc.get('committed_by', 'unknown')} on {doc.get('timestamp', 'an unknown date')}.")
    return f"Policy ledger: {policy_id}", text, str(doc.get("_id"))


def _render_offboarding_doc(doc: Dict[str, Any]):
    title = doc.get("title") or "Untitled"
    text = doc.get("content") or ""
    return f"Offboarding knowledge: {title}", text, doc.get("entry_id") or str(doc.get("_id"))


_SOURCES = (
    ("policy", "policy_ledger", _render_policy_ledger_doc),
    ("knowledge", "offboarding_knowledge", _render_offboarding_doc),
)


@knowledge_router.post("/sync")
async def sync_knowledge(req: Request, payload: Dict = Depends(policy_admin_role_required)):
    """Re-index the Mongo corpus (policy_ledger, offboarding_knowledge) into rag_chunks."""
    ai_service = getattr(req.app.state, "ai_service", None)
    mongo_client = getattr(req.app.state, "mongo_client", None)
    if not ai_service or mongo_client is None:
        raise HTTPException(status_code=503, detail="AI or Mongo service unavailable.")
    db = mongo_client[settings.MONGO_DB_NAME]

    counts: Dict[str, int] = {}
    for source_type, collection_name, render in _SOURCES:
        await pg_client.execute("DELETE FROM rag_chunks WHERE source_type = $1", source_type)
        indexed = 0
        async for doc in db[collection_name].find({}):
            title, text, source_id = render(doc)
            if not text.strip():
                continue
            indexed += await retrieval.index_text(
                ai_service, source_type, source_id, title, text, meta={"mongo_id": str(doc.get("_id"))})
        counts[source_type] = indexed

    return {"status": "synced", "chunks_indexed": counts, "total": sum(counts.values())}


@knowledge_router.get("/stats")
async def knowledge_stats(req: Request, payload: Dict = Depends(manager_role_required)):
    """Corpus size by source + closed-loop stats (suggestions made, solved-by-AI rate, escalation rate)."""
    corpus_rows = await pg_client.fetch("SELECT source_type, COUNT(*) AS n FROM rag_chunks GROUP BY source_type")
    corpus_total = sum(r["n"] for r in corpus_rows)

    # Tickets still carrying a live suggestion in metadata.suggested_resolution.
    open_rows = await pg_client.fetch("SELECT ticket_id FROM hrsd_tickets WHERE metadata ? 'suggested_resolution'")
    suggested_ticket_ids = {r["ticket_id"] for r in open_rows}

    mongo_client = getattr(req.app.state, "mongo_client", None)
    resolved_by_ai = escalated = 0
    top_sources: List[Dict[str, Any]] = []
    if mongo_client is not None:
        col = mongo_client[settings.MONGO_DB_NAME]["ai_resolution_outcomes"]
        resolved_by_ai = await col.count_documents({"helpful": True})
        escalated = await col.count_documents({"helpful": False})
        # "This solved it" closes the ticket, which overwrites hrsd_tickets.metadata
        # and wipes suggested_resolution -- exactly the success stories would
        # otherwise disappear from the metadata-based count above. The Mongo
        # outcome log is the durable record that a suggestion existed for a ticket.
        async for doc in col.find({}, {"ticket_id": 1}):
            if doc.get("ticket_id"):
                suggested_ticket_ids.add(doc["ticket_id"])
        tally: Dict[str, int] = {}
        async for doc in col.find({"helpful": True}, {"chunk_ids": 1}):
            for cid in doc.get("chunk_ids") or []:
                tally[cid] = tally.get(cid, 0) + 1
        if tally:
            top_ids = sorted(tally, key=tally.get, reverse=True)[:5]
            rows = await pg_client.fetch(
                "SELECT id, title, source_type FROM rag_chunks WHERE id = ANY($1::uuid[])", top_ids)
            by_id = {str(r["id"]): r for r in rows}
            top_sources = [
                {"title": by_id[i]["title"], "source_type": by_id[i]["source_type"], "times_helpful": tally[i]}
                for i in top_ids if i in by_id
            ]

    suggestions_made = len(suggested_ticket_ids)
    return {
        "corpus": {"total": corpus_total, "by_source": {r["source_type"]: r["n"] for r in corpus_rows}},
        "loop": {
            "suggestions_made": suggestions_made,
            "solved_by_ai": resolved_by_ai,
            "escalated": escalated,
            "solved_by_ai_rate": round(resolved_by_ai / suggestions_made, 4) if suggestions_made else 0.0,
            "escalation_rate": round(escalated / suggestions_made, 4) if suggestions_made else 0.0,
            "top_helpful_sources": top_sources,
        },
    }


# --------------------------------------------------------------------------
# HRSD closed loop: suggestion attach (background) + feedback
# --------------------------------------------------------------------------
async def attach_suggested_resolution(app_state, ticket_id: str, subject: str, description: str) -> None:
    """Runs as a background task from comprehensive_routes.create_ticket so ticket
    creation never blocks on a 20-40s CPU-only LLM call. Only attaches a
    confidence-gated suggestion for a human (or the employee) to accept or
    dismiss -- never closes or otherwise changes the ticket."""
    ai_service = getattr(app_state, "ai_service", None)
    if not ai_service:
        return
    mongo_client = getattr(app_state, "mongo_client", None)
    try:
        result = await grounded_answers.answer_question(
            f"{subject}\n{description}", ai_service, mongo_client=mongo_client)
    except Exception as e:
        logger.warning(f"Suggested-resolution generation failed for {ticket_id}: {e}")
        return

    if result.get("status") != "answered" or (result.get("confidence") or 0) < CONFIDENCE_THRESHOLD:
        return

    suggestion = {
        "text": result["answer"],
        "citations": result["citations"],
        "confidence": result["confidence"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        await pg_client.execute(
            "UPDATE hrsd_tickets SET metadata = COALESCE(metadata, '{}'::jsonb) || $2::jsonb WHERE ticket_id = $1",
            ticket_id, json.dumps({"suggested_resolution": suggestion}),
        )
    except Exception as e:
        logger.warning(f"Could not persist suggested resolution for {ticket_id}: {e}")


async def record_resolution_feedback(app_state, ticket_id: str, helpful: bool,
                                      actor: Optional[str]) -> Dict[str, Any]:
    """"This solved it" closes the ticket (resolved_by_ai) and records a helpful
    outcome; "I still need help" records an escalation and leaves the ticket
    in the normal queue flow. Either way the outcome is recorded so future
    retrieval can weight the chunks that were actually shown."""
    row = await pg_client.fetchrow("SELECT metadata FROM hrsd_tickets WHERE ticket_id = $1", ticket_id)
    if not row:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    meta = row.get("metadata") or {}
    if isinstance(meta, str):
        meta = json.loads(meta)
    suggestion = meta.get("suggested_resolution") or {}
    chunk_ids = [c.get("chunk_id") for c in suggestion.get("citations", []) if c.get("chunk_id")]

    mongo_client = getattr(app_state, "mongo_client", None)
    if mongo_client is not None:
        await mongo_client[settings.MONGO_DB_NAME]["ai_resolution_outcomes"].insert_one({
            "ticket_id": ticket_id, "helpful": bool(helpful), "chunk_ids": chunk_ids,
            "actor": actor, "ts": datetime.now(timezone.utc).isoformat(),
        })

    outcome = "escalated"
    if helpful:
        hrsd_system = getattr(app_state, "hrsd_system", None)
        if hrsd_system:
            await hrsd_system.resolve_ticket_by_agent(
                ticket_id, "Resolved from the AI-suggested answer, confirmed by the employee.", actor or "AI")
        outcome = "resolved_by_ai"
    return {"ticket_id": ticket_id, "helpful": bool(helpful), "outcome": outcome}


@hrsd_ai_router.post("/tickets/{ticket_id}/resolution-feedback")
async def resolution_feedback(req: Request, ticket_id: str, body: ResolutionFeedbackRequest,
                               payload: Dict = Depends(employee_role_required)):
    return await record_resolution_feedback(req.app.state, ticket_id, body.helpful, payload.get("sub"))


ALL_AI_KNOWLEDGE_ROUTERS = [knowledge_router, hrsd_ai_router]
