"""Unit tests for the HRSD closed loop: suggestion attach -> feedback ->
outcome recorded -> outcome boosts that chunk's next retrieval.

Fake pg_client + fake Mongo collections, per the pattern in
test_hrsd_persistence.py. No live Ollama/Postgres/Mongo dependency.
"""
import asyncio
import json

from config.settings import settings
from routes import ai_knowledge_routes as akr
from services import retrieval


class FakePg:
    """One fake pg_client shared by services.retrieval and
    routes.ai_knowledge_routes -- routes it by which table the query touches."""

    def __init__(self, chunk_rows):
        self.chunk_rows = chunk_rows
        self.tickets = {}  # ticket_id -> metadata dict

    async def fetch(self, query, *args):
        if "rag_chunks" in query:
            return self.chunk_rows
        return []

    async def fetchrow(self, query, *args):
        if "hrsd_tickets" in query:
            ticket_id = args[0]
            meta = self.tickets.get(ticket_id)
            return {"metadata": meta} if meta is not None else None
        return None

    async def execute(self, query, *args):
        if "UPDATE hrsd_tickets SET metadata" in query:
            ticket_id, meta_json = args
            existing = self.tickets.get(ticket_id, {})
            existing.update(json.loads(meta_json))
            self.tickets[ticket_id] = existing
        return "OK"


class FakeAI:
    async def generate_embedding(self, text):
        return [1.0, 0.0, 0.0]

    async def generate_text(self, prompt, system_instruction=""):
        return "Reset your password from the self-service portal within 24 hours."


class FakeHrsdSystem:
    def __init__(self):
        self.resolved = []

    async def resolve_ticket_by_agent(self, ticket_id, resolution_summary, resolved_by):
        self.resolved.append((ticket_id, resolution_summary, resolved_by))


class _AsyncIter:
    def __init__(self, items):
        self._items = list(items)
        self._i = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._i >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._i]
        self._i += 1
        return item


class FakeCollection:
    def __init__(self):
        self.docs = []

    async def insert_one(self, doc):
        self.docs.append(doc)

    def find(self, filt=None, projection=None):
        filt = filt or {}
        return _AsyncIter(d for d in self.docs if all(d.get(k) == v for k, v in filt.items()))

    async def count_documents(self, filt):
        filt = filt or {}
        return sum(1 for d in self.docs if all(d.get(k) == v for k, v in filt.items()))


class FakeDB(dict):
    def __missing__(self, key):
        self[key] = FakeCollection()
        return self[key]


class FakeMongoClient(dict):
    def __missing__(self, key):
        self[key] = FakeDB()
        return self[key]


class AppState:
    def __init__(self, ai_service, mongo_client, hrsd_system=None):
        self.ai_service = ai_service
        self.mongo_client = mongo_client
        self.hrsd_system = hrsd_system


CHUNK = {
    "id": "33333333-3333-3333-3333-333333333333",
    "source_type": "document", "source_id": "faq.txt", "title": "Password reset FAQ",
    "chunk_text": "Reset your password from the self-service portal within 24 hours.",
    "embedding": [1.0, 0.0, 0.0], "meta": {},
}


def _run(coro):
    return asyncio.run(coro)


def test_suggestion_attached_then_solved_closes_and_records_outcome(monkeypatch):
    fake_pg = FakePg([CHUNK])
    monkeypatch.setattr(retrieval, "pg_client", fake_pg)
    monkeypatch.setattr(akr, "pg_client", fake_pg)

    ai = FakeAI()
    mongo = FakeMongoClient()
    hrsd = FakeHrsdSystem()
    app_state = AppState(ai, mongo, hrsd)

    # 1. Ticket create -> background suggestion attach.
    _run(akr.attach_suggested_resolution(app_state, "T-1", "Cannot log in", "Password expired"))
    row = _run(fake_pg.fetchrow("SELECT metadata FROM hrsd_tickets WHERE ticket_id = $1", "T-1"))
    assert row is not None, "suggestion was not attached to the ticket"
    suggestion = row["metadata"]["suggested_resolution"]
    assert suggestion["confidence"] >= 0.35
    chunk_id = suggestion["citations"][0]["chunk_id"]
    assert chunk_id == CHUNK["id"]

    # 2. Employee says "this solved it" -> closes ticket, records helpful outcome.
    result = _run(akr.record_resolution_feedback(app_state, "T-1", True, "employee1"))
    assert result["outcome"] == "resolved_by_ai"
    assert hrsd.resolved and hrsd.resolved[0][0] == "T-1"

    outcomes = mongo[settings.MONGO_DB_NAME]["ai_resolution_outcomes"].docs
    assert len(outcomes) == 1
    assert outcomes[0]["helpful"] is True
    assert outcomes[0]["chunk_ids"] == [chunk_id]


def test_spawn_keeps_a_reference_so_the_task_cannot_be_collected(monkeypatch):
    """asyncio.create_task only holds a weak reference, so a fire-and-forget task
    can be garbage collected before it finishes. These wait 20-40s on a CPU-only
    model, and suggestions really were vanishing on live tickets while the same
    question answered fine through /knowledge/ask."""
    fake_pg = FakePg([CHUNK])
    monkeypatch.setattr(retrieval, "pg_client", fake_pg)
    monkeypatch.setattr(akr, "pg_client", fake_pg)
    app_state = AppState(FakeAI(), FakeMongoClient(), FakeHrsdSystem())

    async def scenario():
        akr.spawn_suggested_resolution(app_state, "T-3", "Cannot log in", "Password expired")
        # The task is held for as long as it is running, not left to chance.
        assert len(akr._BACKGROUND_TASKS) == 1
        await asyncio.gather(*list(akr._BACKGROUND_TASKS))
        # ...and released once it is done, so the set cannot grow without bound.
        assert akr._BACKGROUND_TASKS == set()

    _run(scenario())
    row = _run(fake_pg.fetchrow("SELECT metadata FROM hrsd_tickets WHERE ticket_id = $1", "T-3"))
    assert row is not None, "the spawned task did not attach its suggestion"


def test_still_need_help_escalates_without_closing(monkeypatch):
    fake_pg = FakePg([CHUNK])
    monkeypatch.setattr(retrieval, "pg_client", fake_pg)
    monkeypatch.setattr(akr, "pg_client", fake_pg)

    ai = FakeAI()
    mongo = FakeMongoClient()
    hrsd = FakeHrsdSystem()
    app_state = AppState(ai, mongo, hrsd)

    _run(akr.attach_suggested_resolution(app_state, "T-2", "Cannot log in", "Password expired"))
    result = _run(akr.record_resolution_feedback(app_state, "T-2", False, "employee2"))

    assert result["outcome"] == "escalated"
    assert hrsd.resolved == []  # never closed
    outcomes = mongo[settings.MONGO_DB_NAME]["ai_resolution_outcomes"].docs
    assert outcomes[0]["helpful"] is False


def test_helpful_outcome_boosts_next_retrieval_score(monkeypatch):
    fake_pg = FakePg([CHUNK])
    monkeypatch.setattr(retrieval, "pg_client", fake_pg)
    ai = FakeAI()
    mongo = FakeMongoClient()

    baseline = _run(retrieval.retrieve("password reset", ai, mongo_client=mongo))[0]["score"]

    _run(mongo[settings.MONGO_DB_NAME]["ai_resolution_outcomes"].insert_one(
        {"ticket_id": "T-1", "helpful": True, "chunk_ids": [CHUNK["id"]], "ts": "now"}))

    boosted = _run(retrieval.retrieve("password reset", ai, mongo_client=mongo))[0]["score"]
    assert boosted > baseline
    assert round(boosted - baseline, 4) == 0.02  # one helpful outcome, bounded +/-0.05


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
        test_suggestion_attached_then_solved_closes_and_records_outcome,
        test_still_need_help_escalates_without_closing,
        test_helpful_outcome_boosts_next_retrieval_score,
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
