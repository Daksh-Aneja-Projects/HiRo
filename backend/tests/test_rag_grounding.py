"""Unit tests for grounded Q&A (retrieval + hallucination guard).

Fake pg_client + fake AIService; no live Ollama/Postgres dependency, per the
pattern in test_hrsd_persistence.py.
"""
import asyncio

from services import grounded_answers, retrieval
from services.ai_services import AIServiceError


class FakePgClient:
    def __init__(self, rows):
        self.rows = rows

    async def fetch(self, query, *args):
        return self.rows

    async def fetchrow(self, query, *args):
        return None

    async def execute(self, query, *args):
        return "OK"


class FakeAIService:
    """generate_embedding maps a question to a fixed 3-d vector by keyword;
    generate_text returns a canned answer (optionally quoting a chunk)."""

    def __init__(self, vector_by_keyword, answer_text=None, raise_on_embed=False, raise_on_text=False):
        self.vector_by_keyword = vector_by_keyword
        self.answer_text = answer_text
        self.raise_on_embed = raise_on_embed
        self.raise_on_text = raise_on_text

    async def generate_embedding(self, text):
        if self.raise_on_embed:
            raise AIServiceError("embedding model down")
        for kw, vec in self.vector_by_keyword.items():
            if kw != "__default__" and kw in text.lower():
                return vec
        return self.vector_by_keyword.get("__default__", [0.0, 0.0, 0.0])

    async def generate_text(self, prompt, system_instruction=""):
        if self.raise_on_text:
            raise AIServiceError("llm down")
        return self.answer_text or ""


CHUNK_PTO = {
    "id": "11111111-1111-1111-1111-111111111111",
    "source_type": "policy", "source_id": "PTO-CAP", "title": "PTO policy",
    "chunk_text": "The PTO cap policy limits accrual to 240 hours per year.",
    "embedding": [1.0, 0.0, 0.0], "meta": {},
}
CHUNK_BENEFITS = {
    "id": "22222222-2222-2222-2222-222222222222",
    "source_type": "policy", "source_id": "BEN-01", "title": "Benefits policy",
    "chunk_text": "Health benefits enroll within 30 days of hire.",
    "embedding": [0.0, 1.0, 0.0], "meta": {},
}


def _run(coro):
    return asyncio.run(coro)


def test_question_in_corpus_answers_with_citation(monkeypatch):
    monkeypatch.setattr(retrieval, "pg_client", FakePgClient([CHUNK_PTO, CHUNK_BENEFITS]))
    ai = FakeAIService(
        vector_by_keyword={"pto": [1.0, 0.0, 0.0], "__default__": [0.0, 0.0, 1.0]},
        answer_text="The PTO cap policy limits accrual to 240 hours per year.",
    )
    result = _run(grounded_answers.answer_question("What is the PTO cap policy?", ai))
    assert result["status"] == "answered"
    assert result["citations"], "expected at least one citation"
    assert result["citations"][0]["source_id"] == "PTO-CAP"
    assert result["confidence"] > grounded_answers.CONFIDENCE_THRESHOLD


def test_question_out_of_corpus_refuses(monkeypatch):
    monkeypatch.setattr(retrieval, "pg_client", FakePgClient([CHUNK_PTO, CHUNK_BENEFITS]))
    ai = FakeAIService(vector_by_keyword={"__default__": [0.0, 0.0, 1.0]})  # orthogonal to both chunks
    result = _run(grounded_answers.answer_question("What is the capital of France?", ai))
    assert result["status"] == "refused"
    assert result["answer"] is None
    assert result["citations"] == []


def test_real_zero_score_is_not_dropped_or_confused_with_no_results(monkeypatch):
    """A real 0.0 cosine score must still flow through as 0.0, not be treated
    as falsy and either dropped from results or mistaken for 'no corpus'."""
    monkeypatch.setattr(retrieval, "pg_client", FakePgClient([CHUNK_PTO]))
    ai = FakeAIService(vector_by_keyword={"__default__": [0.0, 1.0, 0.0]})  # exactly orthogonal -> cosine 0.0

    results = _run(retrieval.retrieve("irrelevant question", ai))
    assert len(results) == 1              # not dropped by a truthy filter
    assert results[0]["score"] == 0.0     # exact zero, preserved

    result = _run(grounded_answers.answer_question("irrelevant question", ai))
    assert result["status"] == "refused"
    assert result["confidence"] == 0.0    # present as 0.0, not None/missing


def test_llm_outage_degrades_to_unavailable_not_fabrication(monkeypatch):
    monkeypatch.setattr(retrieval, "pg_client", FakePgClient([CHUNK_PTO]))
    ai = FakeAIService(vector_by_keyword={"pto": [1.0, 0.0, 0.0]}, raise_on_text=True)
    result = _run(grounded_answers.answer_question("What is the PTO cap?", ai))
    assert result["status"] == "unavailable"
    assert result["answer"] is None


def test_embedding_outage_degrades_to_unavailable(monkeypatch):
    monkeypatch.setattr(retrieval, "pg_client", FakePgClient([CHUNK_PTO]))
    ai = FakeAIService(vector_by_keyword={}, raise_on_embed=True)
    result = _run(grounded_answers.answer_question("anything", ai))
    assert result["status"] == "unavailable"
    assert result["answer"] is None


if __name__ == "__main__":
    import sys as _sys

    class _MP:
        def __init__(self):
            self._undo = []

        def setattr(self, obj, name, val):
            self._undo.append((obj, name, getattr(obj, name)))
            setattr(obj, name, val)

        def undo(self):
            for obj, name, val in reversed(self._undo):
                setattr(obj, name, val)
            self._undo = []

    tests = [
        test_question_in_corpus_answers_with_citation,
        test_question_out_of_corpus_refuses,
        test_real_zero_score_is_not_dropped_or_confused_with_no_results,
        test_llm_outage_degrades_to_unavailable_not_fabrication,
        test_embedding_outage_degrades_to_unavailable,
    ]
    passed = 0
    for fn in tests:
        mp = _MP()
        try:
            fn(mp)
            print(f"PASS {fn.__name__}")
            passed += 1
        finally:
            mp.undo()
    print(f"{passed}/{len(tests)} passed")
    _sys.exit(0 if passed == len(tests) else 1)
