"""Unit tests for the social feed + recognition data layer (services/social_recognition.py).

Uses a tiny in-memory fake of the motor collection API (just the calls the module makes),
so the shaping/aggregation/guards are verified without a live MongoDB.
"""
import asyncio
import pytest

from services import social_recognition as sr


class FakeCursor:
    def __init__(self, docs, projection=None):
        self._docs = docs
        self._projection = projection or {}

    def sort(self, spec, direction=None):
        # Accept either sort("field", dir) or sort([("f1", d1), ("f2", d2)]).
        keys = spec if isinstance(spec, list) else [(spec, direction)]
        # Stable multi-key sort: apply least-significant key first.
        for field, dirn in reversed(keys):
            self._docs = sorted(self._docs, key=lambda d: d.get(field), reverse=dirn < 0)
        return self

    def limit(self, n):
        self._docs = self._docs[:n]
        return self

    async def to_list(self, n):
        # Mongo applies the projection last (after sort/limit), so _id is available
        # for sorting even when the caller projects it out.
        docs = self._docs[:n]
        if self._projection.get("_id") == 0:
            docs = [{k: v for k, v in d.items() if k != "_id"} for d in docs]
        return list(docs)


class FakeCollection:
    def __init__(self):
        self.docs = []

    def find(self, query=None, projection=None):
        return FakeCursor([dict(d) for d in self.docs], projection)

    async def find_one(self, query):
        for d in self.docs:
            if all(d.get(k) == v for k, v in query.items()):
                return d
        return None

    async def insert_one(self, doc):
        doc["_id"] = f"oid{len(self.docs):06d}"
        self.docs.append(doc)

    async def insert_many(self, docs):
        for d in docs:
            await self.insert_one(d)

    async def delete_many(self, query):
        self.docs = []

    def aggregate(self, pipeline):
        # Supports the exact leaderboard pipeline: $group by to_user (count + last name),
        # then $sort by stars desc, then $limit.
        groups = {}
        for d in self.docs:
            key = d["to_user"]
            g = groups.setdefault(key, {"_id": key, "stars": 0, "user_name": None})
            g["stars"] += 1
            g["user_name"] = d.get("to_user_name")
        rows = sorted(groups.values(), key=lambda g: g["stars"], reverse=True)
        limit = pipeline[-1].get("$limit", len(rows))
        return FakeCursor(rows[:limit])


class FakeDB:
    def __init__(self):
        self.social_posts = FakeCollection()
        self.recognition_stars = FakeCollection()
        self.users = FakeCollection()


def test_create_and_list_feed_shape_and_order():
    db = FakeDB()
    p1 = asyncio.run(sr.create_post(db, user_id="employee", user_name="Dana", content="  first  "))
    p2 = asyncio.run(sr.create_post(db, user_id="manager", user_name="Charlie", content="second"))

    assert p1["content"] == "first"          # trimmed
    assert set(p1) == {"id", "user_id", "user_name", "content", "timestamp", "upvotes", "downvotes"}

    feed = asyncio.run(sr.list_feed(db))
    assert [f["content"] for f in feed] == ["second", "first"]   # newest first
    assert all("_id" not in f for f in feed)                      # mongo _id stripped


def test_empty_post_rejected():
    db = FakeDB()
    with pytest.raises(ValueError):
        asyncio.run(sr.create_post(db, user_id="x", user_name="X", content="   "))


def test_give_star_resolves_name_and_leaderboard_ranks():
    db = FakeDB()
    db.users.docs.append({"username": "employee", "full_name": "Dana Employee"})
    db.users.docs.append({"username": "manager", "full_name": "Charlie Manager"})

    asyncio.run(sr.give_star(db, from_user="manager", to_user="employee", reason="great work"))
    asyncio.run(sr.give_star(db, from_user="admin", to_user="employee", reason="again"))
    asyncio.run(sr.give_star(db, from_user="admin", to_user="manager", reason="ok"))

    board = asyncio.run(sr.leaderboard(db))
    assert board[0] == {"user_id": "employee", "user_name": "Dana Employee", "stars": 2}
    assert board[1]["user_id"] == "manager" and board[1]["stars"] == 1
    assert board[1]["user_name"] == "Charlie Manager"


def test_give_star_rejects_someone_not_on_record():
    # Recognition must land on a real person: a recipient in neither the account
    # directory nor the employee directory is an error, not a silent fallback row.
    db = FakeDB()
    with pytest.raises(ValueError):
        asyncio.run(sr.give_star(db, from_user="admin", to_user="ghost-9999", reason="hi"))


def test_self_star_rejected():
    db = FakeDB()
    with pytest.raises(ValueError):
        asyncio.run(sr.give_star(db, from_user="admin", to_user="admin", reason="me"))


def test_seed_populates_both_collections():
    db = FakeDB()
    employees = [
        {"username": "admin", "name": "System Admin", "role": "hrit_admin"},
        {"username": "manager", "name": "Charlie Manager", "role": "manager"},
        {"username": "employee", "name": "Dana Employee", "role": "employee"},
    ]
    n_posts, n_stars = asyncio.run(sr.seed(db, employees))
    assert n_posts == 5 and n_stars > 0
    board = asyncio.run(sr.leaderboard(db))
    assert board and board[0]["stars"] >= board[-1]["stars"]     # ranked
    assert all(b["user_name"] for b in board)                    # names present


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
