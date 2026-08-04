"""Unit tests for the goals data layer in services/people_lifecycle.py.

A tiny in-memory fake of the motor collection API (only the calls these
functions make) exercises the create/list/update/delete/summary logic without a
live MongoDB.
"""
import asyncio
import pytest

from services import people_lifecycle as pl


class _Result:
    def __init__(self, deleted_count):
        self.deleted_count = deleted_count


class FakeCursor:
    def __init__(self, docs, projection=None):
        self._docs = docs
        self._projection = projection or {}

    def sort(self, field, direction):
        self._docs = sorted(self._docs, key=lambda d: d.get(field), reverse=direction < 0)
        return self

    async def to_list(self, length=None):
        docs = self._docs if length is None else self._docs[:length]
        if self._projection.get("_id") == 0:
            docs = [{k: v for k, v in d.items() if k != "_id"} for d in docs]
        return list(docs)


class FakeGoals:
    def __init__(self):
        self.docs = []

    @staticmethod
    def _match(doc, query):
        return all(doc.get(k) == v for k, v in query.items())

    async def insert_one(self, doc):
        doc["_id"] = f"oid{len(self.docs):06d}"
        self.docs.append(doc)

    def find(self, query, projection=None):
        return FakeCursor([dict(d) for d in self.docs if self._match(d, query)], projection)

    async def find_one(self, query, projection=None):
        for d in self.docs:
            if self._match(d, query):
                out = dict(d)
                if (projection or {}).get("_id") == 0:
                    out.pop("_id", None)
                return out
        return None

    async def update_one(self, query, update):
        for d in self.docs:
            if self._match(d, query):
                d.update(update.get("$set", {}))
                return
        return None

    async def delete_one(self, query):
        for i, d in enumerate(self.docs):
            if self._match(d, query):
                del self.docs[i]
                return _Result(1)
        return _Result(0)


class FakeDB:
    def __init__(self):
        self.goals = FakeGoals()


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def db():
    return FakeDB()


def test_create_goal_shape(db):
    g = run(pl.create_goal(db, employee_uuid="EMP-1", title="Ship v2", description="  do it  ",
                           key_results=["kr one", "  ", "kr two"], created_by="EMP-1"))
    assert g["goal_id"].startswith("GOAL-")
    assert g["title"] == "Ship v2"
    assert g["description"] == "do it"
    assert g["status"] == "active"
    # Blank key results are dropped; the rest become {text, done:false}.
    assert g["key_results"] == [{"text": "kr one", "done": False}, {"text": "kr two", "done": False}]


def test_create_goal_requires_title(db):
    with pytest.raises(ValueError):
        run(pl.create_goal(db, employee_uuid="EMP-1", title="   ", description="",
                           key_results=[], created_by="EMP-1"))


def test_list_goals_only_returns_own(db):
    run(pl.create_goal(db, employee_uuid="EMP-1", title="A", description="", key_results=[], created_by="EMP-1"))
    run(pl.create_goal(db, employee_uuid="EMP-2", title="B", description="", key_results=[], created_by="EMP-2"))
    mine = run(pl.list_goals(db, "EMP-1"))
    assert [g["title"] for g in mine] == ["A"]
    assert all("_id" not in g for g in mine)


def test_update_goal_changes_fields(db):
    g = run(pl.create_goal(db, employee_uuid="EMP-1", title="A", description="", key_results=[], created_by="EMP-1"))
    updated = run(pl.update_goal(db, goal_id=g["goal_id"], employee_uuid="EMP-1",
                                 updates={"title": "A2", "status": "achieved"}))
    assert updated["title"] == "A2"
    assert updated["status"] == "achieved"


def test_update_goal_rejects_bad_status(db):
    g = run(pl.create_goal(db, employee_uuid="EMP-1", title="A", description="", key_results=[], created_by="EMP-1"))
    with pytest.raises(ValueError):
        run(pl.update_goal(db, goal_id=g["goal_id"], employee_uuid="EMP-1", updates={"status": "banana"}))


def test_update_goal_missing_raises(db):
    with pytest.raises(ValueError):
        run(pl.update_goal(db, goal_id="nope", employee_uuid="EMP-1", updates={"title": "x"}))


def test_update_goal_ignores_unknown_fields(db):
    g = run(pl.create_goal(db, employee_uuid="EMP-1", title="A", description="", key_results=[], created_by="EMP-1"))
    updated = run(pl.update_goal(db, goal_id=g["goal_id"], employee_uuid="EMP-1",
                                 updates={"created_by": "hacker"}))
    assert updated["created_by"] == "EMP-1"


def test_delete_goal(db):
    g = run(pl.create_goal(db, employee_uuid="EMP-1", title="A", description="", key_results=[], created_by="EMP-1"))
    assert run(pl.delete_goal(db, goal_id=g["goal_id"], employee_uuid="EMP-1")) is True
    assert run(pl.delete_goal(db, goal_id=g["goal_id"], employee_uuid="EMP-1")) is False


def test_cannot_delete_others_goal(db):
    g = run(pl.create_goal(db, employee_uuid="EMP-1", title="A", description="", key_results=[], created_by="EMP-1"))
    assert run(pl.delete_goal(db, goal_id=g["goal_id"], employee_uuid="EMP-2")) is False


def test_goals_summary_counts_live_only(db):
    run(pl.create_goal(db, employee_uuid="EMP-1", title="A", description="", key_results=[], created_by="EMP-1"))
    g2 = run(pl.create_goal(db, employee_uuid="EMP-1", title="B", description="", key_results=[], created_by="EMP-1"))
    g3 = run(pl.create_goal(db, employee_uuid="EMP-1", title="C", description="", key_results=[], created_by="EMP-1"))
    run(pl.update_goal(db, goal_id=g2["goal_id"], employee_uuid="EMP-1", updates={"status": "achieved"}))
    run(pl.update_goal(db, goal_id=g3["goal_id"], employee_uuid="EMP-1", updates={"status": "dropped"}))
    summary = run(pl.goals_summary(db, "EMP-1"))
    # A (active) + B (achieved) are live; C (dropped) counts toward neither.
    assert summary == {"achieved": 1, "total": 2}
