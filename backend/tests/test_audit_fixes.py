"""Unit tests for the audited backend defects.

Same fake-client pattern as test_hrsd_persistence.py: a stand-in pg/mongo client
records calls and returns canned rows, so the logic is verified without a live
database. Nothing here needs Docker or the running server.
"""
import asyncio

from services import admin_service as admin_mod
from services.admin_service import AdminService, PURGE_TABLES
from services import hr_modules as hr_mod
from services import hyperledger_chaincode as gov_mod
from services.hyperledger_chaincode import AHCMGovernanceChaincode
from services.pqc_pii_layer import PQCEncryptionWrapper
from services.synthetic_twin_engine import SyntheticTwinEngine
from services.event_publisher_service import EventPublisherService


# --------------------------------------------------------------------------
# Fakes
# --------------------------------------------------------------------------
class FakePgClient:
    """Records SQL. `existing_tables` drives the information_schema lookup."""

    def __init__(self, existing_tables=(), row=None, fail_execute=None):
        self.existing_tables = list(existing_tables)
        self.row = row
        self.fail_execute = fail_execute
        self.calls = []

    async def fetch(self, query, *args):
        self.calls.append(("fetch", query, args))
        if "information_schema.tables" in query:
            wanted = set(args[0])
            return [{"table_name": t} for t in self.existing_tables if t in wanted]
        return []

    async def fetchrow(self, query, *args):
        self.calls.append(("fetchrow", query, args))
        return self.row

    async def execute(self, query, *args):
        self.calls.append(("execute", query, args))
        if self.fail_execute:
            raise self.fail_execute
        return "TRUNCATE TABLE"

    def executed(self):
        return [c[1] for c in self.calls if c[0] == "execute"]


class FakeDeleteResult:
    def __init__(self, n):
        self.deleted_count = n


class FakeCollection:
    def __init__(self, n=0, error=None):
        self.n = n
        self.error = error
        self.filters = []

    async def delete_many(self, flt):
        self.filters.append(flt)
        if self.error:
            raise self.error
        return FakeDeleteResult(self.n)

    async def count_documents(self, flt):
        return self.n


class FakeDb:
    def __init__(self, counts=None):
        self.counts = counts or {}
        self.collections = {}

    def __getitem__(self, name):
        if name not in self.collections:
            self.collections[name] = FakeCollection(self.counts.get(name, 0))
        return self.collections[name]

    def __getattr__(self, name):
        return self[name]


class FakeMongoClient:
    def __init__(self, counts=None):
        self.db = FakeDb(counts)

    def __getitem__(self, _name):
        return self.db


def _admin_service(pg, mongo):
    svc = AdminService.__new__(AdminService)
    svc.db = mongo.db
    svc.announcements = mongo.db["announcements"]
    svc.system_logs = mongo.db["system_logs"]
    svc.audit_logs = mongo.db["audit_logs"]
    svc.profile_change_requests = mongo.db["profile_change_requests"]
    svc.users = mongo.db["users"]
    svc.pg_client = pg
    return svc


# --------------------------------------------------------------------------
# Item 1 -- hard purge
# --------------------------------------------------------------------------
def test_purge_only_touches_tables_that_exist():
    """A table that was never created must not blow up the whole purge.

    The old list named five tables that exist in no HiRo schema, so every call
    raised UndefinedTableError and nothing was ever purged.
    """
    present = ["employee_pii", "leave_requests", "dao_proposals",
               "notifications", "policy_audit_log"]
    pg = FakePgClient(existing_tables=present)
    svc = _admin_service(pg, FakeMongoClient())

    result = asyncio.run(svc.hard_purge_system_data("admin"))

    assert result["purged_cleanly"] is True
    truncate = [q for q in pg.executed() if q.startswith("TRUNCATE")]
    assert len(truncate) == 1                      # one atomic statement
    for table in present:
        assert table in truncate[0]
        assert result["postgres"][table] == "purged"
    # Absent tables are reported honestly, not silently claimed as purged.
    absent = [t for t in PURGE_TABLES if t not in present]
    assert absent, "test needs at least one absent table"
    for table in absent:
        assert table not in truncate[0]
        assert result["postgres"][table] == "does not exist; skipped"


def test_purge_includes_the_real_dao_proposals_and_audit_tables():
    """dao_proposals lives in Postgres; notifications and policy_audit_log were omitted."""
    for table in ("dao_proposals", "notifications", "policy_audit_log"):
        assert table in PURGE_TABLES

    pg = FakePgClient(existing_tables=PURGE_TABLES)
    mongo = FakeMongoClient()
    svc = _admin_service(pg, mongo)
    asyncio.run(svc.hard_purge_system_data("admin"))

    truncate = [q for q in pg.executed() if q.startswith("TRUNCATE")][0]
    assert "dao_proposals" in truncate
    # The phantom Mongo dao_proposals drop is gone: nothing ever wrote it, and
    # dropping it looked like a purge while the real Postgres rows survived.
    assert "dao_proposals" not in mongo.db.collections


def test_purge_reports_failures_per_store_and_keeps_admin():
    pg = FakePgClient(existing_tables=["employee_pii"], fail_execute=RuntimeError("boom"))
    mongo = FakeMongoClient(counts={"announcements": 3, "users": 9})
    svc = _admin_service(pg, mongo)

    result = asyncio.run(svc.hard_purge_system_data("admin"))

    assert result["purged_cleanly"] is False
    assert result["postgres"]["employee_pii"].startswith("failed: RuntimeError")
    # Mongo still ran and is reported separately, with real deleted counts.
    assert result["mongo"]["announcements"] == "purged 3 document(s)"
    assert mongo.db["users"].filters == [{"username": {"$ne": "admin"}}]


# --------------------------------------------------------------------------
# Item 2 -- synthetic twin confidence
# --------------------------------------------------------------------------
def _twin():
    return SyntheticTwinEngine(dt_agent=None, ai_service=None)


def test_confidence_tracks_data_completeness():
    """Confidence was hardcoded 0.5 for everyone (a call to a method that never
    existed, whose AttributeError was swallowed). It must now vary with data."""
    engine = _twin()
    full = {"data_signals_present": list(SyntheticTwinEngine.CONFIDENCE_SIGNALS),
            "current_risk_score": 0.4, "attrition_probability": 0.4,
            "productivity_score": 0.6, "compensation": 100000.0}
    thin = dict(full, data_signals_present=["department"])
    synthetic = {"levers_applied": {"promotion": 1}, "levers_clipped": []}

    high, high_basis = engine._estimate_confidence(full, synthetic)
    low, low_basis = engine._estimate_confidence(thin, synthetic)

    assert high > low, "a complete record must score above a sparse one"
    assert high == 0.85 and low == 0.41
    assert high_basis.startswith("Heuristic confidence:")
    assert "missing" in low_basis


def test_confidence_penalises_levers_outside_the_calibrated_range():
    engine = _twin()
    base = {"data_signals_present": list(SyntheticTwinEngine.CONFIDENCE_SIGNALS)}
    inside, _ = engine._estimate_confidence(
        base, {"levers_applied": {"salary_increase_pct": 5}, "levers_clipped": []})
    outside, basis = engine._estimate_confidence(
        base, {"levers_applied": {"salary_increase_pct": 20}, "levers_clipped": ["salary_increase_pct"]})

    assert outside < inside
    assert "calibrated" in basis


def test_lever_beyond_cap_is_recorded_as_clipped():
    engine = _twin()
    state = engine._apply_adjustments(
        {"current_risk_score": 0.5, "engagement_score": 0.5,
         "productivity_score": 0.6, "compensation": 100000.0},
        {"salary_increase_pct": 500},   # cap is 20
    )
    assert state["levers_clipped"] == ["salary_increase_pct"]
    assert state["levers_applied"]["salary_increase_pct"] == 20


# --------------------------------------------------------------------------
# Item 3 -- DAO quorum against the real electorate
# --------------------------------------------------------------------------
def _proposal(n_voters, votes_for, votes_against=0.0, weight=100.0):
    """A proposal with `n_voters` distinct heads and token-weighted tallies."""
    return {"proposal_id": "PROP_X", "status": "VOTING",
            "voters": [f"EMP-{i}" for i in range(n_voters)],
            "total_votes": votes_for + votes_against,
            "votes_for": votes_for, "votes_against": votes_against,
            "deadline": "2099-01-01T00:00:00+00:00", "executed": False}


def test_quorum_reached_against_real_voter_count():
    """Quorum used to divide by a hardcoded 10000 'Mock Total Supply', so with a
    real handful of accounts no proposal could ever pass, whatever anyone voted."""
    cc = AHCMGovernanceChaincode(mongo_client=FakeMongoClient(counts={"users": 10}))
    proposal = _proposal(n_voters=8, votes_for=800.0)        # 80% turnout, 100% for
    asyncio.run(cc._check_execution(proposal))

    assert proposal["eligible_voters"] == 10
    assert proposal["participation_pct"] == 80.0
    assert proposal["status"] == "APPROVED"
    assert proposal["executed"] is True
    # Under the old hardcoded 10000 electorate this same vote was 8% of quorum.
    assert 800.0 / 10000 * 100 < 51


def test_quorum_not_reached_leaves_proposal_open():
    cc = AHCMGovernanceChaincode(mongo_client=FakeMongoClient(counts={"users": 100}))
    proposal = _proposal(n_voters=8, votes_for=800.0)        # 8% turnout
    asyncio.run(cc._check_execution(proposal))

    assert proposal["participation_pct"] == 8.0
    assert proposal["status"] == "VOTING"
    assert "quorum" in proposal["quorum_note"]


def test_turnout_counts_heads_not_token_weight():
    """Quorum is turnout; approval is weight. Mixing them made a proposal with
    heavy token weights read as thousands of percent turnout."""
    cc = AHCMGovernanceChaincode(mongo_client=FakeMongoClient(counts={"users": 100}))
    proposal = _proposal(n_voters=2, votes_for=6200.0, votes_against=1400.0)
    asyncio.run(cc._check_execution(proposal))

    assert proposal["participation_pct"] == 2.0       # 2 of 100 heads, not 7600%
    assert proposal["status"] == "VOTING"             # nowhere near quorum


def test_unknown_electorate_makes_no_quorum_claim():
    cc = AHCMGovernanceChaincode(mongo_client=None)
    proposal = _proposal(n_voters=99, votes_for=99.0)
    asyncio.run(cc._check_execution(proposal))

    assert proposal["eligible_voters"] is None
    assert proposal["participation_pct"] is None      # no invented percentage
    assert proposal["status"] == "VOTING"             # and no quorum decision


# --------------------------------------------------------------------------
# Item 4 -- performance score is null, never invented
# --------------------------------------------------------------------------
def _hr_service():
    svc = hr_mod.HRModulesService.__new__(hr_mod.HRModulesService)
    return svc


def test_performance_returns_null_when_there_is_no_review(monkeypatch):
    """A 3.0 'meets expectations' rating for someone never reviewed is fabricated."""
    monkeypatch.setattr(hr_mod, "pg_client", FakePgClient(row=None))
    out = asyncio.run(_hr_service().get_employee_performance("EMP-1", "manager"))

    assert out["score"] is None
    assert out["score_available"] is False
    assert "No review" in out["status"]
    assert "score" in out            # key still present: frontend contract


def test_performance_returns_the_real_score_when_one_exists(monkeypatch):
    monkeypatch.setattr(hr_mod, "pg_client",
                        FakePgClient(row={"overall_rating": 4.5, "review_period_end": "2026-01-31"}))
    out = asyncio.run(_hr_service().get_employee_performance("EMP-1", "hrbp"))

    assert out["score"] == 4.5
    assert out["score_available"] is True
    assert out["last_review_date"] == "2026-01-31"


def test_dead_adjust_compensation_method_is_gone():
    assert not hasattr(hr_mod.HRModulesService, "adjust_compensation")


# --------------------------------------------------------------------------
# Item 6 -- key rotation can never destroy data
# --------------------------------------------------------------------------
def test_rotate_keys_refuses_and_old_ciphertext_still_decrypts():
    """The old rotate_keys swapped in an unpersisted random key and re-encrypted
    nothing, so every stored PII value became permanently unreadable."""
    wrapper = PQCEncryptionWrapper.get_instance()
    ciphertext, _ = wrapper.encrypt("Ada Lovelace", data_context="test")
    key_before = wrapper.master_key_bytes

    result = asyncio.run(wrapper.rotate_keys())

    assert result["rotated"] is False
    assert result["status"] == "ROTATION_NOT_CONFIGURED"
    assert wrapper.master_key_bytes == key_before          # key untouched
    assert wrapper.decrypt(ciphertext) == "Ada Lovelace"   # data still readable


def test_encryption_metadata_does_not_claim_post_quantum():
    _, metadata = PQCEncryptionWrapper.get_instance().encrypt("x")
    assert metadata["algorithm"] == "AES-256-Fernet"
    assert metadata["post_quantum"] is False


# --------------------------------------------------------------------------
# Item 14 -- publishes report delivery
# --------------------------------------------------------------------------
def test_publish_reports_undelivered_when_there_is_no_bus():
    pub = EventPublisherService()
    pub.mock_mode = True
    delivered = asyncio.run(pub.publish_event("hr.test", {"a": 1}))

    assert delivered is False
    assert pub.last_publish["delivered"] is False
    assert pub.last_publish["topic"] == "hr.test"
    assert "not delivered" in pub.last_publish["detail"]


def test_publish_reports_delivered_on_ack():
    class _Ack:
        seq = 42

    class _JS:
        async def publish(self, *a, **k):
            return _Ack()

    pub = EventPublisherService()
    pub.js = _JS()
    delivered = asyncio.run(pub.publish_event("hr.test", {"a": 1}))

    assert delivered is True
    assert pub.last_publish["delivered"] is True
    assert "42" in pub.last_publish["detail"]


_TESTS = [
    test_purge_only_touches_tables_that_exist,
    test_purge_includes_the_real_dao_proposals_and_audit_tables,
    test_purge_reports_failures_per_store_and_keeps_admin,
    test_confidence_tracks_data_completeness,
    test_confidence_penalises_levers_outside_the_calibrated_range,
    test_lever_beyond_cap_is_recorded_as_clipped,
    test_quorum_reached_against_real_voter_count,
    test_quorum_not_reached_leaves_proposal_open,
    test_turnout_counts_heads_not_token_weight,
    test_unknown_electorate_makes_no_quorum_claim,
    test_performance_returns_null_when_there_is_no_review,
    test_performance_returns_the_real_score_when_one_exists,
    test_dead_adjust_compensation_method_is_gone,
    test_rotate_keys_refuses_and_old_ciphertext_still_decrypts,
    test_encryption_metadata_does_not_claim_post_quantum,
    test_publish_reports_undelivered_when_there_is_no_bus,
    test_publish_reports_delivered_on_ack,
]

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

    passed = 0
    for fn in _TESTS:
        mp = _MP()
        try:
            fn(mp) if fn.__code__.co_argcount else fn()
            print(f"PASS {fn.__name__}")
            passed += 1
        except Exception as e:
            print(f"FAIL {fn.__name__}: {type(e).__name__}: {e}")
        finally:
            mp.undo()
    print(f"{passed}/{len(_TESTS)} passed")
    _sys.exit(0 if passed == len(_TESTS) else 1)
