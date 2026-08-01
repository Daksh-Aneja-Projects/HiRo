# /backend/services/grounded_answers.py
"""Grounded answers: the model may only answer from retrieved rag_chunks.

Three outcomes, always honest about which one happened:
  - "answered": a confident enough match, LLM answer grounded in the sources.
  - "refused": nothing relevant enough in the corpus, or the model couldn't
    ground its answer in what was retrieved -- refusal beats fabrication.
  - "unavailable": Ollama/the embedding model couldn't be reached; degrade
    honestly instead of a fabricated answer or a 500.
"""
import logging
import re
from typing import Any, Dict, List, Optional

from services import retrieval
from services.ai_services import AIService, AIServiceError

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.35
TOP_K = 4

_STOPWORDS = {
    "the", "a", "an", "and", "or", "is", "are", "was", "were", "to", "of",
    "in", "on", "for", "with", "this", "that", "it", "as", "by", "be", "has",
    "have", "had", "not", "your", "you", "can", "will", "from", "at", "does",
}

_REFUSAL_PHRASES = (
    "do not contain", "don't contain", "does not contain", "doesn't contain",
    "no information", "not mentioned", "cannot find", "can't find",
    "not contain the answer", "sources do not", "unable to answer",
    "i don't know", "i do not know", "not covered", "don't cover",
)


def _tokens(text: str) -> set:
    return {w.lower() for w in re.findall(r"[a-zA-Z0-9_\-]{4,}", text or "")} - _STOPWORDS


def _looks_like_self_refusal(answer: str) -> bool:
    low = (answer or "").lower()
    return any(p in low for p in _REFUSAL_PHRASES)


def _overlaps_corpus(answer: str, results: List[Dict[str, Any]]) -> bool:
    """Post-check hallucination guard: the answer must share real vocabulary
    with what was actually retrieved, or it is treated as off-corpus."""
    ans_tokens = _tokens(answer)
    if not ans_tokens:
        return False
    corpus_tokens: set = set()
    for r in results:
        chunk = r["chunk"]
        corpus_tokens |= _tokens(chunk.get("chunk_text", "")) | _tokens(chunk.get("title", ""))
    return bool(ans_tokens & corpus_tokens)


def _refused(reason: str, confidence: float = 0.0) -> Dict[str, Any]:
    # confidence defaults to 0.0, not None: a real 0.0 top score must still
    # come through as 0.0, never disappear behind a falsy check.
    return {"status": "refused", "answer": None, "reason": reason,
            "confidence": round(confidence, 4), "citations": []}


def _unavailable(reason: str) -> Dict[str, Any]:
    return {"status": "unavailable", "answer": None, "reason": reason,
            "confidence": None, "citations": []}


def _citation(r: Dict[str, Any]) -> Dict[str, Any]:
    chunk = r["chunk"]
    return {
        "chunk_id": str(chunk.get("id")),
        "title": chunk.get("title"),
        "source_id": chunk.get("source_id"),
        "score": round(r["score"], 4),
        "snippet": (chunk.get("chunk_text") or "")[:240],
    }


async def answer_question(question: str, ai_service: AIService, top_k: int = TOP_K,
                           mongo_client=None, source_type: Optional[str] = None) -> Dict[str, Any]:
    if not question or not question.strip():
        return _refused("No question was asked.")

    try:
        results = await retrieval.retrieve(question, ai_service, top_k=top_k,
                                            mongo_client=mongo_client, source_type=source_type)
    except AIServiceError as e:
        logger.warning(f"Grounded answer retrieval failed (embedding): {e}")
        return _unavailable(f"AI is unavailable right now: {e}")
    except Exception as e:
        logger.error(f"Grounded answer retrieval failed: {e}")
        return _unavailable("The knowledge service could not be reached.")

    if not results:
        return _refused("Nothing in the knowledge base is close enough to answer this.")

    # top_score may legitimately be 0.0 (orthogonal embeddings) -- compare
    # numerically, never `if not top_score`.
    top_score = results[0]["score"]
    if top_score < CONFIDENCE_THRESHOLD:
        return _refused("Nothing in the knowledge base is close enough to answer this.", confidence=top_score)

    context = "\n\n".join(
        f"[{i + 1}] {r['chunk'].get('title') or r['chunk'].get('source_id')}: {r['chunk'].get('chunk_text', '')}"
        for i, r in enumerate(results)
    )
    prompt = (
        f"Sources:\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer using ONLY the sources above. If they do not contain the answer, say plainly "
        "that the sources do not cover this. Do not use outside knowledge."
    )
    try:
        answer_text = await ai_service.generate_text(
            prompt,
            system_instruction=(
                "You answer strictly from the given sources and refuse honestly "
                "when they don't cover the question."
            ),
        )
    except AIServiceError as e:
        logger.warning(f"Grounded answer generation failed: {e}")
        return _unavailable(f"AI is unavailable right now: {e}")

    if not answer_text or _looks_like_self_refusal(answer_text) or not _overlaps_corpus(answer_text, results):
        return _refused("The sources retrieved don't cover this question.", confidence=top_score)

    return {
        "status": "answered",
        "answer": answer_text,
        "citations": [_citation(r) for r in results],
        "confidence": round(top_score, 4),
    }
