"""Unit tests for real DAO governance + compliance aggregation.

Fake pg_client returns canned aggregate rows so the mapping/derivation logic is
verified without a live database.
"""
import asyncio
import json
from datetime import datetime, timezone, timedelta

from services import hyperledger_chaincode as gov_mod
from services import enforcement_engine as enf_mod
from services.hyperledger_chaincode import AHCMGovernanceChaincode


class FakePgClient:
    def __init__(self, rows=None, row=None):
        self.rows = rows or []
        self.row = row
        self.calls = []

    async def fetch(self, query, *args):
        self.calls.append(("fetch", query, args))
        return self.rows

    async def fetchrow(self, query, *args):
        self.calls.append(("fetchrow", query, args))
        return self.row


def test_list_active_proposals_shape(monkeypatch):
    data = {"proposal_id": "PROP_1", "rule_content": {"title": "Remote Work"},
            "proposer": "HRBP", "votes_for": 12.0, "votes_against": 3.0, "deadline": "2026-08-01"}
    fake = FakePgClient(rows=[{"data": data}])
    monkeypatch.setattr(gov_mod, "pg_client", fake)
    cc = AHCMGovernanceChaincode()
    out = asyncio.run(cc.list_active_proposals())
    assert out[0]["id"] == "PROP_1"
    assert out[0]["title"] == "Remote Work"
    assert out[0]["votes_for"] == 12.0
    # only VOTING proposals are queried
    assert "status = 'VOTING'" in fake.calls[0][1]


def test_list_active_proposals_handles_json_string(monkeypatch):
    data = {"proposal_id": "PROP_2", "rule_content": {}, "proposer": "X"}
    fake = FakePgClient(rows=[{"data": json.dumps(data)}])   # asyncpg may hand back a str
    monkeypatch.setattr(gov_mod, "pg_client", fake)
    cc = AHCMGovernanceChaincode()
    out = asyncio.run(cc.list_active_proposals())
    assert out[0]["id"] == "PROP_2"
    assert out[0]["title"] == "PROP_2"   # falls back to id when no title


def test_governance_stats(monkeypatch):
    fake = FakePgClient(row={"active_proposals": 3, "total_voting_power": 15200.0,
                             "members_voting": 210, "ledger_commits_24h": 4})
    monkeypatch.setattr(gov_mod, "pg_client", fake)
    cc = AHCMGovernanceChaincode()
    stats = asyncio.run(cc.get_governance_stats())
    assert stats == {"active_proposals": 3, "total_voting_power": 15200.0,
                     "members_voting": 210, "ledger_commits_24h": 4}


def test_governance_stats_null_row(monkeypatch):
    fake = FakePgClient(row=None)   # empty table
    monkeypatch.setattr(gov_mod, "pg_client", fake)
    cc = AHCMGovernanceChaincode()
    stats = asyncio.run(cc.get_governance_stats())
    assert stats["active_proposals"] == 0
    assert stats["total_voting_power"] == 0.0


def test_compliance_overview(monkeypatch):
    last = datetime.now(timezone.utc) - timedelta(days=5)
    fake = FakePgClient(row={"total_decisions": 100, "denials": 18,
                             "high_severity_violations": 4, "decisions_24h": 7,
                             "last_decision_at": last})
    monkeypatch.setattr(enf_mod, "pg_client", fake)
    ov = asyncio.run(enf_mod.get_compliance_overview())
    assert ov["score"] == 0.82                     # 1 - 18/100
    assert ov["high_severity_violations"] == 4
    assert ov["regulatory_feed_status"] == "ONLINE"   # decisions_24h > 0
    assert ov["latest_version_applied"] is True
    assert ov["days_to_next_audit"] == 25          # 30 - 5


def test_compliance_overview_empty(monkeypatch):
    fake = FakePgClient(row={"total_decisions": 0, "denials": 0,
                             "high_severity_violations": 0, "decisions_24h": 0,
                             "last_decision_at": None})
    monkeypatch.setattr(enf_mod, "pg_client", fake)
    ov = asyncio.run(enf_mod.get_compliance_overview())
    assert ov["score"] == 1.0                      # no decisions -> perfect, no div-by-zero
    assert ov["regulatory_feed_status"] == "DEGRADED"
    assert ov["latest_version_applied"] is False
    assert ov["days_to_next_audit"] == 30


_TESTS = [
    test_list_active_proposals_shape, test_list_active_proposals_handles_json_string,
    test_governance_stats, test_governance_stats_null_row,
    test_compliance_overview, test_compliance_overview_empty,
]

if __name__ == "__main__":
    import sys as _sys

    class _MP:
        def __init__(self): self._undo = []
        def setattr(self, obj, name, val):
            self._undo.append((obj, name, getattr(obj, name)))
            setattr(obj, name, val)
        def undo(self):
            for obj, name, val in reversed(self._undo): setattr(obj, name, val)
            self._undo = []

    passed = 0
    for fn in _TESTS:
        mp = _MP()
        try:
            fn(mp)
            print(f"PASS {fn.__name__}")
            passed += 1
        except Exception as e:
            print(f"FAIL {fn.__name__}: {type(e).__name__}: {e}")
        finally:
            mp.undo()
    print(f"{passed}/{len(_TESTS)} passed")
    _sys.exit(0 if passed == len(_TESTS) else 1)
