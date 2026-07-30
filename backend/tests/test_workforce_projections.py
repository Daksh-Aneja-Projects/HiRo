"""Unit test for real workforce projections aggregated from the employee UDM."""
import asyncio

from services import workforce_planning_service as wfp_mod
from services.workforce_planning_service import WorkforcePlanningService


class FakePgClient:
    """Returns different canned rows per query by matching a keyword."""
    def __init__(self, emp_row, perf_row, dept_rows):
        self.emp_row, self.perf_row, self.dept_rows = emp_row, perf_row, dept_rows

    async def fetchrow(self, query, *args):
        return self.perf_row if "performance_reviews" in query else self.emp_row

    async def fetch(self, query, *args):
        return self.dept_rows


def _svc():
    s = WorkforcePlanningService.__new__(WorkforcePlanningService)
    s.publisher = None
    return s


def test_projections_map_real_aggregates(monkeypatch):
    fake = FakePgClient(
        emp_row={"total_employees": 20000, "critical_roles": 3200,
                 "average_tenure_months": 34, "overall_risk_score": 0.512},
        perf_row={"avg_perf": 3.74},
        dept_rows=[{"department": "Engineering", "c": 8000},
                   {"department": "Legal", "c": 400},
                   {"department": "Sales", "c": 3000}],
    )
    monkeypatch.setattr(wfp_mod, "pg_client", fake)
    proj = asyncio.run(_svc().get_current_projections())

    cs = proj["current_state"]
    assert cs["total_employees"] == 20000
    assert cs["overall_risk_score"] == 0.512      # real base for the digital-twin sim
    assert cs["average_performance_score"] == 3.74
    # fair share = 20000/3 ≈ 6667; Legal(400) is far below -> HIGH, Engineering(8000) above -> LOW
    assert proj["skill_gaps"]["Legal"] == "HIGH"
    assert proj["skill_gaps"]["Engineering"] == "LOW"


def test_projections_empty_db(monkeypatch):
    fake = FakePgClient(emp_row=None, perf_row=None, dept_rows=[])
    monkeypatch.setattr(wfp_mod, "pg_client", fake)
    proj = asyncio.run(_svc().get_current_projections())
    assert proj["current_state"]["total_employees"] == 0
    assert proj["skill_gaps"] == {}               # no headcount -> no derivation, no crash


_TESTS = [test_projections_map_real_aggregates, test_projections_empty_db]

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
            fn(mp); print(f"PASS {fn.__name__}"); passed += 1
        except Exception as e:
            print(f"FAIL {fn.__name__}: {type(e).__name__}: {e}")
        finally:
            mp.undo()
    print(f"{passed}/{len(_TESTS)} passed")
    _sys.exit(0 if passed == len(_TESTS) else 1)
