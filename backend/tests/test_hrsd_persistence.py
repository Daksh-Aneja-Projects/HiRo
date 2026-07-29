"""Unit tests for real HRSD Postgres persistence (multi_agent_hrsd).

Uses a fake pg_client that records SQL and returns canned rows, so the mapping,
enum-safety, and aggregation logic are verified without a live database.
"""
import asyncio
import json
from datetime import datetime, timezone

from services import multi_agent_hrsd as hrsd_mod
from services.multi_agent_hrsd import MultiAgentHRSDSystem
from services.schemas.models import TicketStatus, TicketPriority


class FakePgClient:
    def __init__(self, rows=None, row=None):
        self.rows = rows or []
        self.row = row
        self.calls = []

    async def execute(self, query, *args):
        self.calls.append(("execute", query, args))
        return "INSERT 0 1"

    async def fetch(self, query, *args):
        self.calls.append(("fetch", query, args))
        return self.rows

    async def fetchrow(self, query, *args):
        self.calls.append(("fetchrow", query, args))
        return self.row


class _NoopPublisher:
    async def publish_agent_task(self, *args, **kwargs):
        return None

    async def publish_event(self, *args, **kwargs):
        return None


def _system():
    # Build without running __init__ (which needs AI/publisher services).
    sys_ = MultiAgentHRSDSystem.__new__(MultiAgentHRSDSystem)
    sys_.publisher = _NoopPublisher()
    return sys_


def test_save_ticket_upserts_and_maps_metadata(monkeypatch):
    fake = FakePgClient()
    monkeypatch.setattr(hrsd_mod, "pg_client", fake)
    sys_ = _system()

    async def run():
        ticket = await sys_.create_ticket("EMP-7", "Laptop broken", "It won't boot")
        return ticket

    ticket = asyncio.run(run())
    assert ticket.title == "Laptop broken"          # subject arg maps to model.title
    assert ticket.employee_id == "EMP-7"
    # One execute (the UPSERT) was issued.
    execs = [c for c in fake.calls if c[0] == "execute"]
    assert len(execs) == 1
    query, args = execs[0][1], execs[0][2]
    assert "ON CONFLICT (ticket_id) DO UPDATE" in query
    # metadata JSONB carries the model-only fields.
    meta = json.loads(args[7])
    assert meta["employee_id"] == "EMP-7"


def test_row_to_ticket_safe_enum_fallback():
    sys_ = _system()
    row = {
        "ticket_id": "T-ABC",
        "subject": "Reset password",
        "description": "SSO locked",
        "status": "NEW",
        "priority": "NORMAL",  # not a valid TicketPriority -> should fall back to MEDIUM
        "assigned_agent": None,
        "created_at": datetime.now(timezone.utc),
        "metadata": {"employee_id": "EMP-1"},
    }
    ticket = sys_._row_to_ticket(row)
    assert ticket.status == TicketStatus.NEW
    assert ticket.priority == TicketPriority.MEDIUM   # graceful fallback, no crash
    assert ticket.employee_id == "EMP-1"
    assert ticket.title == "Reset password"


def test_get_overview_counts(monkeypatch):
    fake = FakePgClient(
        rows=[{"status": "NEW", "c": 3}, {"status": "IN_TRIAGE", "c": 2}, {"status": "CLOSED", "c": 5}],
        row={"c": 1},
    )
    monkeypatch.setattr(hrsd_mod, "pg_client", fake)
    sys_ = _system()
    overview = asyncio.run(sys_.get_overview())
    assert overview["active_tickets"] == 5          # NEW(3) + IN_TRIAGE(2), CLOSED excluded
    assert overview["total_tickets"] == 10
    assert overview["sla_breaches"] == 1


def test_list_tickets_shape(monkeypatch):
    fake = FakePgClient(rows=[{
        "ticket_id": "T-1", "subject": "s", "description": "d", "status": "NEW",
        "priority": "HIGH", "assigned_agent": None, "created_at": datetime.now(timezone.utc),
        "metadata": {"employee_id": "EMP-9"},
    }])
    monkeypatch.setattr(hrsd_mod, "pg_client", fake)
    sys_ = _system()
    result = asyncio.run(sys_.list_tickets(employee_id="EMP-9"))
    assert result["count"] == 1
    assert result["tickets"][0]["ticket_id"] == "T-1"
    # employee_id filter is applied via a metadata JSONB predicate.
    fetch_calls = [c for c in fake.calls if c[0] == "fetch"]
    assert "metadata->>'employee_id'" in fetch_calls[0][1]


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
    for fn in [test_save_ticket_upserts_and_maps_metadata, test_row_to_ticket_safe_enum_fallback,
               test_get_overview_counts, test_list_tickets_shape]:
        mp = _MP()
        try:
            fn(mp) if fn.__code__.co_argcount else fn()
            print(f"PASS {fn.__name__}")
            passed += 1
        finally:
            mp.undo()
    print(f"{passed}/4 passed")
    _sys.exit(0 if passed == 4 else 1)
