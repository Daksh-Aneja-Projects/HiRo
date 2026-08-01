"""Unit tests for the people-lifecycle backend (services/people_lifecycle.py,
services/performance_cycles.py, and the notification-preferences gate added to
services/notification_service.py).

Follows the house pattern (tests/test_hrsd_persistence.py, tests/test_social_recognition.py):
fake pg_client / Mongo collections, no live database. Run with:
    python -m pytest tests/test_people_lifecycle.py --noconftest -q
"""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from services import people_lifecycle, performance_cycles
from services import notification_service


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Fake Mongo (extends the pattern in tests/test_social_recognition.py with
# update_one/$set/$push/positional-array support and find_one(sort=...))
# ---------------------------------------------------------------------------

def _matches(doc, query):
    for k, v in (query or {}).items():
        if k == "items.item_id":
            if not any(i.get("item_id") == v for i in doc.get("items", [])):
                return False
            continue
        if isinstance(v, dict) and "$in" in v:
            if doc.get(k) not in v["$in"]:
                return False
            continue
        if doc.get(k) != v:
            return False
    return True


def _set_dotted(doc, path, value):
    parts = path.split(".")
    cur = doc
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = value


class FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, field, direction=1):
        self._docs = sorted(self._docs, key=lambda d: d.get(field) or "", reverse=direction < 0)
        return self

    def limit(self, n):
        self._docs = self._docs[:n]
        return self

    async def to_list(self, length=None):
        return list(self._docs if length is None else self._docs[:length])


class FakeCollection:
    def __init__(self):
        self.docs = []

    def find(self, query=None, projection=None):
        out = [{k: v for k, v in d.items() if k != "_id"} for d in self.docs if _matches(d, query)]
        return FakeCursor(out)

    async def find_one(self, query=None, projection=None, sort=None):
        matches = [d for d in self.docs if _matches(d, query)]
        if sort:
            for field, direction in reversed(sort):
                matches.sort(key=lambda d: d.get(field) or "", reverse=direction < 0)
        if not matches:
            return None
        return {k: v for k, v in matches[0].items() if k != "_id"}

    async def insert_one(self, doc):
        doc["_id"] = f"oid{len(self.docs)}"
        self.docs.append(doc)

    async def update_one(self, query, update, upsert=False):
        matches = [d for d in self.docs if _matches(d, query)]
        if not matches:
            if upsert:
                new_doc = {k: v for k, v in query.items() if not isinstance(v, dict)}
                for k, v in (update.get("$set") or {}).items():
                    _set_dotted(new_doc, k, v)
                new_doc["_id"] = f"oid{len(self.docs)}"
                self.docs.append(new_doc)
                return SimpleNamespace(matched_count=0, modified_count=0, upserted_id=new_doc["_id"])
            return SimpleNamespace(matched_count=0, modified_count=0)
        d = matches[0]
        item_id_filter = query.get("items.item_id")
        set_ops = update.get("$set") or {}
        positional = {k[len("items.$."):]: v for k, v in set_ops.items() if k.startswith("items.$.")}
        plain = {k: v for k, v in set_ops.items() if not k.startswith("items.$.")}
        if positional and item_id_filter is not None:
            for item in d.get("items", []):
                if item.get("item_id") == item_id_filter:
                    item.update(positional)
                    break
        for k, v in plain.items():
            _set_dotted(d, k, v)
        for k, v in (update.get("$push") or {}).items():
            d.setdefault(k, []).append(v)
        return SimpleNamespace(matched_count=1, modified_count=1)

    async def delete_one(self, query):
        matches = [d for d in self.docs if _matches(d, query)]
        if not matches:
            return SimpleNamespace(deleted_count=0)
        self.docs.remove(matches[0])
        return SimpleNamespace(deleted_count=1)

    async def count_documents(self, query=None):
        return len([d for d in self.docs if _matches(d, query)])


class FakeMongoDB:
    def __init__(self):
        self.onboarding_plans = FakeCollection()
        self.goals = FakeCollection()
        self.users = FakeCollection()
        self.offboarding_knowledge = FakeCollection()
        self.exit_interviews = FakeCollection()
        self.profile_change_requests = FakeCollection()
        self.notification_prefs = FakeCollection()


# ---------------------------------------------------------------------------
# Fake Postgres for performance_cycles.py + the one-on-one / roster queries in
# people_lifecycle.py. Recognises the exact statements those modules issue.
# ---------------------------------------------------------------------------

class FakePgClient:
    def __init__(self):
        self.perf_cycles = {}
        self.perf_cycle_entries = {}   # (cycle_id, employee_uuid) -> dict
        self.employee_pii = {}         # employee_uuid -> {"manager_id": ...}
        self.performance_reviews = []
        self.one_on_ones = []
        self._next_id = 1
        self.calls = []

    def _blank_entry(self, cycle_id, employee_uuid):
        return {"cycle_id": cycle_id, "employee_uuid": employee_uuid, "self_assessment": None,
                "self_rating": None, "manager_rating": None, "manager_comments": None,
                "calibrated_rating": None, "signed_off_by_employee": False, "signed_off_at": None}

    def transaction(self, *a, **kw):
        return _FakeTxn()

    async def execute(self, query, *args):
        self.calls.append(("execute", query, args))
        q = " ".join(query.split())
        if q.startswith("CREATE TABLE") or q.startswith("CREATE INDEX"):
            return "OK"
        if q.startswith("INSERT INTO perf_cycles"):
            cycle_id, name, opens_at, closes_at, created_by = args
            self.perf_cycles[cycle_id] = {"cycle_id": cycle_id, "name": name, "stage": "self_assessment",
                                          "opens_at": opens_at, "closes_at": closes_at, "created_by": created_by}
            return "INSERT 0 1"
        if q.startswith("INSERT INTO perf_cycle_entries (cycle_id, employee_uuid) VALUES"):
            cycle_id, emp = args
            self.perf_cycle_entries.setdefault((cycle_id, emp), self._blank_entry(cycle_id, emp))
            return "INSERT 0 1"
        if q.startswith("UPDATE perf_cycles SET stage"):
            stage, cycle_id = args
            self.perf_cycles[cycle_id]["stage"] = stage
            return "UPDATE 1"
        if q.startswith("UPDATE perf_cycle_entries SET signed_off_by_employee"):
            cycle_id, employee_uuid = args
            entry = self.perf_cycle_entries[(cycle_id, employee_uuid)]
            entry["signed_off_by_employee"] = True
            entry["signed_off_at"] = datetime.now(timezone.utc)
            return "UPDATE 1"
        if q.startswith("INSERT INTO performance_reviews"):
            employee_uuid, rating, reviewer_id = args
            self.performance_reviews.append({"employee_uuid": employee_uuid, "overall_rating": rating,
                                             "reviewer_id": reviewer_id})
            return "INSERT 0 1"
        if q.startswith("UPDATE employee_pii SET"):
            value, employee_uuid = args
            column = q.split("SET", 1)[1].split("=")[0].strip()
            self.employee_pii.setdefault(employee_uuid, {})[column] = value
            return "UPDATE 1"
        if q.startswith("DELETE FROM one_on_ones"):
            one_on_one_id, manager_uuid = args
            before = len(self.one_on_ones)
            self.one_on_ones = [r for r in self.one_on_ones
                                if not (r["id"] == one_on_one_id and r["manager_uuid"] == manager_uuid)]
            return f"DELETE {before - len(self.one_on_ones)}"
        return "OK"

    async def fetch(self, query, *args):
        self.calls.append(("fetch", query, args))
        q = " ".join(query.split())
        if q.startswith("SELECT * FROM perf_cycles ORDER BY"):
            return list(self.perf_cycles.values())
        if q.startswith("SELECT employee_uuid FROM perf_cycle_entries WHERE cycle_id"):
            (cycle_id,) = args
            return [{"employee_uuid": e} for (c, e) in self.perf_cycle_entries if c == cycle_id]
        if q.startswith("SELECT employee_uuid FROM employee_pii WHERE manager_id"):
            (manager_id,) = args
            return [{"employee_uuid": u} for u, row in self.employee_pii.items() if row.get("manager_id") == manager_id]
        if "SELECT e.*, c.name, c.stage FROM perf_cycle_entries" in q:
            (employee_uuid,) = args
            out = []
            for (c, e), entry in self.perf_cycle_entries.items():
                if e == employee_uuid:
                    cyc = self.perf_cycles[c]
                    out.append({**entry, "name": cyc["name"], "stage": cyc["stage"]})
            return out
        if "SELECT e.* FROM perf_cycle_entries e" in q:
            cycle_id, manager_uuid = args
            return [entry for (c, e), entry in self.perf_cycle_entries.items()
                   if c == cycle_id and self.employee_pii.get(e, {}).get("manager_id") == manager_uuid]
        if q.startswith("SELECT * FROM one_on_ones"):
            rows = list(self.one_on_ones)
            for a in args:
                rows = [r for r in rows if a in (r.get("manager_uuid"), r.get("employee_uuid"))]
            rows.sort(key=lambda r: r["held_at"], reverse=True)
            return rows
        if q.startswith("SELECT employee_uuid, MAX(held_at)"):
            (manager_uuid,) = args
            by_emp = {}
            for r in self.one_on_ones:
                if r["manager_uuid"] == manager_uuid:
                    if r["employee_uuid"] not in by_emp or r["held_at"] > by_emp[r["employee_uuid"]]:
                        by_emp[r["employee_uuid"]] = r["held_at"]
            return [{"employee_uuid": k, "last_held": v} for k, v in by_emp.items()]
        return []

    async def fetchrow(self, query, *args):
        self.calls.append(("fetchrow", query, args))
        q = " ".join(query.split())
        if q.startswith("SELECT * FROM perf_cycles WHERE cycle_id"):
            (cycle_id,) = args
            return self.perf_cycles.get(cycle_id)
        if q.startswith("INSERT INTO perf_cycle_entries (cycle_id, employee_uuid, self_assessment, self_rating)"):
            cycle_id, employee_uuid, self_assessment, self_rating = args
            entry = self.perf_cycle_entries.get((cycle_id, employee_uuid)) or self._blank_entry(cycle_id, employee_uuid)
            entry["self_assessment"], entry["self_rating"] = self_assessment, self_rating
            self.perf_cycle_entries[(cycle_id, employee_uuid)] = entry
            return dict(entry)
        if q.startswith("SELECT 1 AS ok FROM employee_pii WHERE employee_uuid"):
            employee_uuid, manager_uuid = args
            row = self.employee_pii.get(employee_uuid)
            return {"ok": 1} if row and row.get("manager_id") == manager_uuid else None
        if q.startswith("INSERT INTO perf_cycle_entries (cycle_id, employee_uuid, manager_rating, manager_comments)"):
            cycle_id, employee_uuid, manager_rating, manager_comments = args
            entry = self.perf_cycle_entries.get((cycle_id, employee_uuid)) or self._blank_entry(cycle_id, employee_uuid)
            entry["manager_rating"], entry["manager_comments"] = manager_rating, manager_comments
            self.perf_cycle_entries[(cycle_id, employee_uuid)] = entry
            return dict(entry)
        if q.startswith("UPDATE perf_cycle_entries SET calibrated_rating"):
            calibrated_rating, cycle_id, employee_uuid = args
            entry = self.perf_cycle_entries.get((cycle_id, employee_uuid))
            if entry is None:
                return None
            entry["calibrated_rating"] = calibrated_rating
            return dict(entry)
        if q.startswith("SELECT * FROM perf_cycle_entries WHERE cycle_id"):
            cycle_id, employee_uuid = args
            entry = self.perf_cycle_entries.get((cycle_id, employee_uuid))
            return dict(entry) if entry else None
        if q.startswith("SELECT manager_id FROM employee_pii WHERE employee_uuid"):
            (employee_uuid,) = args
            row = self.employee_pii.get(employee_uuid)
            return {"manager_id": row.get("manager_id")} if row else None
        if q.startswith("INSERT INTO one_on_ones"):
            manager_uuid, employee_uuid, held_at, talking_points, notes, shared = args
            row = {"id": self._next_id, "manager_uuid": manager_uuid, "employee_uuid": employee_uuid,
                  "held_at": held_at, "talking_points": talking_points, "notes": notes,
                  "shared_with_employee": shared}
            self._next_id += 1
            self.one_on_ones.append(row)
            return dict(row)
        if q.startswith("UPDATE one_on_ones SET"):
            one_on_one_id, manager_uuid, *values = args
            set_part = q.split("SET", 1)[1].split("WHERE")[0]
            cols = [c.split("=")[0].strip() for c in set_part.split(",")]
            row = next((r for r in self.one_on_ones
                       if r["id"] == one_on_one_id and r["manager_uuid"] == manager_uuid), None)
            if not row:
                return None
            for col, val in zip(cols, values):
                row[col] = val
            return dict(row)
        return None


class _FakeTxn:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _NoopNotify:
    def __init__(self):
        self.calls = []

    async def notify(self, *args, **kwargs):
        self.calls.append(("notify", args, kwargs))
        return "NTF-FAKE"

    async def notify_manager_of(self, *args, **kwargs):
        self.calls.append(("notify_manager_of", args, kwargs))
        return "NTF-FAKE"


def _patch_notify(monkeypatch):
    noop = _NoopNotify()
    monkeypatch.setattr(notification_service, "notify", noop.notify)
    monkeypatch.setattr(notification_service, "notify_manager_of", noop.notify_manager_of)
    return noop


# ---------------------------------------------------------------------------
# Onboarding: completion notifies + progress math
# ---------------------------------------------------------------------------

def test_onboarding_completion_notifies_and_progress_math(monkeypatch):
    noop = _patch_notify(monkeypatch)
    db = FakeMongoDB()

    plan = run(people_lifecycle.create_onboarding_plan(db, employee_uuid="EMP-100", created_by="hrbp"))
    total = len(plan["items"])
    assert total == len(people_lifecycle.DEFAULT_ONBOARDING_TEMPLATE)
    first_item = plan["items"][0]["item_id"]

    result = run(people_lifecycle.complete_onboarding_item(
        db, employee_uuid="EMP-100", item_id=first_item, completed_by="EMP-100"))

    assert result["item"]["status"] == "DONE"
    assert result["progress"] == {"done": 1, "total": total, "percent": round((1 / total) * 100, 1)}
    # The manager was told.
    assert any(c[0] == "notify_manager_of" for c in noop.calls)

    # Completing the same item again is a no-op, not a duplicate notification.
    noop.calls.clear()
    result2 = run(people_lifecycle.complete_onboarding_item(
        db, employee_uuid="EMP-100", item_id=first_item, completed_by="EMP-100"))
    assert result2["progress"]["done"] == 1
    assert noop.calls == []


def test_onboarding_unknown_item_rejected():
    db = FakeMongoDB()
    run(people_lifecycle.create_onboarding_plan(db, employee_uuid="EMP-101", created_by="hrbp"))
    try:
        run(people_lifecycle.complete_onboarding_item(
            db, employee_uuid="EMP-101", item_id="NO-SUCH-ITEM", completed_by="EMP-101"))
        assert False, "expected ValueError"
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# Performance cycles: stage gating + sign-off writes performance_reviews
# ---------------------------------------------------------------------------

def test_self_assessment_rejected_during_manager_review(monkeypatch):
    _patch_notify(monkeypatch)
    fake = FakePgClient()
    monkeypatch.setattr(performance_cycles, "pg_client", fake)
    fake.perf_cycles["CYC-1"] = {"cycle_id": "CYC-1", "name": "H1 2026", "stage": "manager_review",
                                 "opens_at": None, "closes_at": None, "created_by": "hrbp"}

    try:
        run(performance_cycles.submit_self_assessment(
            cycle_id="CYC-1", employee_uuid="EMP-1", self_assessment="text", self_rating=4.0))
        assert False, "expected StageError"
    except performance_cycles.StageError as e:
        assert "manager_review" in str(e) and "self_assessment" in str(e)


def test_advance_cycle_stage_sequence_and_final_stage_rejected(monkeypatch):
    _patch_notify(monkeypatch)
    fake = FakePgClient()
    monkeypatch.setattr(performance_cycles, "pg_client", fake)
    fake.perf_cycles["CYC-2"] = {"cycle_id": "CYC-2", "name": "H1 2026", "stage": "self_assessment",
                                 "opens_at": None, "closes_at": None, "created_by": "hrbp"}

    stage1 = run(performance_cycles.advance_cycle_stage("CYC-2", "hrbp"))
    assert stage1["stage"] == "manager_review"
    stage2 = run(performance_cycles.advance_cycle_stage("CYC-2", "hrbp"))
    assert stage2["stage"] == "calibration"
    stage3 = run(performance_cycles.advance_cycle_stage("CYC-2", "hrbp"))
    assert stage3["stage"] == "signed_off"

    try:
        run(performance_cycles.advance_cycle_stage("CYC-2", "hrbp"))
        assert False, "expected StageError at the final stage"
    except performance_cycles.StageError:
        pass


def test_sign_off_writes_performance_reviews(monkeypatch):
    _patch_notify(monkeypatch)
    fake = FakePgClient()
    monkeypatch.setattr(performance_cycles, "pg_client", fake)
    fake.perf_cycles["CYC-3"] = {"cycle_id": "CYC-3", "name": "H1 2026", "stage": "signed_off",
                                 "opens_at": None, "closes_at": None, "created_by": "hrbp"}
    fake.perf_cycle_entries[("CYC-3", "EMP-9")] = {
        "cycle_id": "CYC-3", "employee_uuid": "EMP-9", "self_assessment": "did well", "self_rating": 4.0,
        "manager_rating": 4.5, "manager_comments": "great work", "calibrated_rating": 4.2,
        "signed_off_by_employee": False, "signed_off_at": None,
    }
    fake.employee_pii["EMP-9"] = {"manager_id": "EMP-4"}

    result = run(performance_cycles.sign_off(cycle_id="CYC-3", employee_uuid="EMP-9"))
    assert result["status"] == "SIGNED_OFF"
    assert result["final_rating"] == 4.2   # calibrated_rating wins over manager/self
    assert len(fake.performance_reviews) == 1
    review = fake.performance_reviews[0]
    assert review["employee_uuid"] == "EMP-9"
    assert review["overall_rating"] == 4.2
    assert review["reviewer_id"] == "EMP-4"
    assert fake.perf_cycle_entries[("CYC-3", "EMP-9")]["signed_off_by_employee"] is True


def test_sign_off_with_no_rating_refused(monkeypatch):
    _patch_notify(monkeypatch)
    fake = FakePgClient()
    monkeypatch.setattr(performance_cycles, "pg_client", fake)
    fake.perf_cycles["CYC-4"] = {"cycle_id": "CYC-4", "name": "H1 2026", "stage": "signed_off",
                                 "opens_at": None, "closes_at": None, "created_by": "hrbp"}
    fake.perf_cycle_entries[("CYC-4", "EMP-8")] = {
        "cycle_id": "CYC-4", "employee_uuid": "EMP-8", "self_assessment": None, "self_rating": None,
        "manager_rating": None, "manager_comments": None, "calibrated_rating": None,
        "signed_off_by_employee": False, "signed_off_at": None,
    }
    try:
        run(performance_cycles.sign_off(cycle_id="CYC-4", employee_uuid="EMP-8"))
        assert False, "expected ValueError"
    except ValueError as e:
        assert "no rating" in str(e).lower()
    assert fake.performance_reviews == []


# ---------------------------------------------------------------------------
# Goals: AI draft schema handling
# ---------------------------------------------------------------------------

class _FakeAIService:
    def __init__(self, response):
        self._response = response

    async def generate_json_response(self, prompt, schema, task_type="general"):
        return self._response


def test_draft_goal_returns_title_and_three_key_results():
    ai = _FakeAIService({"title": "Grow enterprise revenue",
                         "key_results": ["Close 5 deals > $50k by Q3", "Reach $2M ARR", "Cut churn to 4%", "extra"]})
    draft = run(people_lifecycle.draft_goal(ai, "grow enterprise revenue"))
    assert draft["title"] == "Grow enterprise revenue"
    assert len(draft["key_results"]) == 3   # capped at three


def test_draft_goal_rejects_empty_model_output():
    ai = _FakeAIService({})
    try:
        run(people_lifecycle.draft_goal(ai, "grow revenue"))
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_draft_goal_requires_intent():
    ai = _FakeAIService({"title": "x", "key_results": ["a"]})
    try:
        run(people_lifecycle.draft_goal(ai, "   "))
        assert False, "expected ValueError"
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# One-on-ones: overdue math
# ---------------------------------------------------------------------------

def test_one_on_one_overdue_math(monkeypatch):
    fake = FakePgClient()
    monkeypatch.setattr(people_lifecycle, "pg_client", fake)
    fake.employee_pii["EMP-A"] = {"manager_id": "MGR-1"}
    fake.employee_pii["EMP-B"] = {"manager_id": "MGR-1"}
    fake.employee_pii["EMP-C"] = {"manager_id": "MGR-1"}  # never had a 1:1

    now = datetime.now(timezone.utc)
    fake.one_on_ones = [
        {"id": 1, "manager_uuid": "MGR-1", "employee_uuid": "EMP-A", "held_at": now - timedelta(days=10)},
        {"id": 2, "manager_uuid": "MGR-1", "employee_uuid": "EMP-B", "held_at": now - timedelta(days=45)},
    ]

    status = run(people_lifecycle.one_on_one_status("MGR-1"))
    by_emp = {s["employee_uuid"]: s for s in status}
    assert by_emp["EMP-A"]["overdue"] is False
    assert by_emp["EMP-A"]["days_since"] == 10
    assert by_emp["EMP-B"]["overdue"] is True
    assert by_emp["EMP-C"]["overdue"] is True
    assert by_emp["EMP-C"]["last_held_at"] is None


# ---------------------------------------------------------------------------
# Exit interviews: aggregation
# ---------------------------------------------------------------------------

def test_exit_interview_reason_aggregation():
    db = FakeMongoDB()
    run(people_lifecycle.submit_exit_interview(
        db, employee_uuid="EMP-1", reasons=["compensation", "career_growth"], comments="", would_recommend=True))
    run(people_lifecycle.submit_exit_interview(
        db, employee_uuid="EMP-2", reasons=["compensation"], comments="meh", would_recommend=False))

    result = run(people_lifecycle.list_exit_interviews(db))
    assert result["count"] == 2
    assert result["reason_counts"]["compensation"] == 2
    assert result["reason_counts"]["career_growth"] == 1


def test_exit_interview_requires_a_real_reason():
    db = FakeMongoDB()
    try:
        run(people_lifecycle.submit_exit_interview(
            db, employee_uuid="EMP-1", reasons=["not_a_real_reason"], comments="", would_recommend=True))
        assert False, "expected ValueError"
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# Notification preferences: opt-out suppresses
# ---------------------------------------------------------------------------

class _FakeNotifyPgClient:
    """Just enough of pg_client for notification_service.notify()'s INSERT."""
    def __init__(self):
        self.rows = []

    async def execute(self, query, *args):
        self.rows.append(args)
        return "INSERT 0 1"


def test_notification_prefs_suppress_opted_out_kind(monkeypatch):
    mongo_db = FakeMongoDB()
    run(mongo_db.notification_prefs.insert_one(
        {"employee_uuid": "EMP-1", "username": "dana", "kinds": {"leave": False}}))

    monkeypatch.setattr(notification_service, "_prefs_db", lambda: mongo_db)
    fake_pg = _FakeNotifyPgClient()
    monkeypatch.setattr(notification_service, "pg_client", fake_pg)

    result = run(notification_service.notify("EMP-1", notification_service.KIND_LEAVE, "t", "b"))
    assert result is None
    assert fake_pg.rows == []   # suppressed: nothing written

    # A kind that wasn't opted out still goes through.
    result2 = run(notification_service.notify("EMP-1", notification_service.KIND_EXPENSE, "t", "b"))
    assert result2 is not None
    assert len(fake_pg.rows) == 1


def test_notification_prefs_default_all_on(monkeypatch):
    mongo_db = FakeMongoDB()  # no prefs doc at all
    monkeypatch.setattr(notification_service, "_prefs_db", lambda: mongo_db)
    fake_pg = _FakeNotifyPgClient()
    monkeypatch.setattr(notification_service, "pg_client", fake_pg)

    result = run(notification_service.notify("EMP-2", notification_service.KIND_LEAVE, "t", "b"))
    assert result is not None
    assert len(fake_pg.rows) == 1


def test_get_and_set_notification_preferences_roundtrip():
    db = FakeMongoDB()
    defaults = run(people_lifecycle.get_notification_preferences(db, "EMP-1", "dana"))
    assert all(v is True for v in defaults["kinds"].values())

    updated = run(people_lifecycle.set_notification_preferences(db, "EMP-1", "dana", {"leave": False, "case": False}))
    assert updated["kinds"]["leave"] is False
    assert updated["kinds"]["case"] is False
    assert updated["kinds"]["expense"] is True   # untouched kinds stay on


# ---------------------------------------------------------------------------
# Profile change review: approval applies to employee_pii
# ---------------------------------------------------------------------------

class _FakeVault:
    def encrypt(self, plaintext, data_context="default"):
        return f"ENC({plaintext})", {"context": data_context}


def test_profile_change_approval_applies_allowed_fields_and_refuses_others(monkeypatch):
    _patch_notify(monkeypatch)
    fake = FakePgClient()
    monkeypatch.setattr(people_lifecycle, "pg_client", fake)
    monkeypatch.setattr(people_lifecycle.PIIVault, "get_instance", staticmethod(lambda: _FakeVault()))

    db = FakeMongoDB()
    run(db.profile_change_requests.insert_one({
        "request_id": "PCR-1", "employee_uuid": "EMP-1", "status": "PENDING_REVIEW",
        "requested_changes": {"email": "new@example.com", "phone": "555-0100"},
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }))

    result = run(people_lifecycle.decide_profile_change_request(
        db, request_id="PCR-1", approve=True, comments="looks fine", decided_by="hrbp"))

    assert result["status"] == "PARTIALLY_APPLIED"
    assert result["field_results"]["email"] == "APPLIED"
    assert "REFUSED" in result["field_results"]["phone"]
    # The real column got the encrypted value; phone has no column to write to.
    assert fake.employee_pii["EMP-1"]["email_encrypted"] == "ENC(new@example.com)"
    assert "phone_encrypted" not in fake.employee_pii.get("EMP-1", {})

    # Deciding an already-decided request is rejected.
    try:
        run(people_lifecycle.decide_profile_change_request(
            db, request_id="PCR-1", approve=True, comments="", decided_by="hrbp"))
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_profile_change_rejection_notifies_without_touching_pii(monkeypatch):
    noop = _patch_notify(monkeypatch)
    fake = FakePgClient()
    monkeypatch.setattr(people_lifecycle, "pg_client", fake)

    db = FakeMongoDB()
    run(db.profile_change_requests.insert_one({
        "request_id": "PCR-2", "employee_uuid": "EMP-2", "status": "PENDING",
        "requested_changes": {"email": "x@example.com"},
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }))

    result = run(people_lifecycle.decide_profile_change_request(
        db, request_id="PCR-2", approve=False, comments="not verifiable", decided_by="hrbp"))
    assert result["status"] == "REJECTED"
    assert "EMP-2" not in fake.employee_pii
    assert any(c[0] == "notify" for c in noop.calls)


if __name__ == "__main__":
    import sys
    import pytest as _pytest
    sys.exit(_pytest.main([__file__, "-q"]))
