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
        # The succession-readiness aggregate selects job_title; this unit test
        # covers the headcount/skill-gap path, so that query gets a no-data state.
        if "job_title" in query:
            return []
        return self.dept_rows


def _svc():
    s = WorkforcePlanningService.__new__(WorkforcePlanningService)
    s.publisher = None
    s.mongo_client = None
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
    # Skill gaps come from real skill profiles now. With no skills store attached
    # the honest answer is "no gaps derivable", never a headcount guess.
    assert proj["skill_gaps"] == {}


class FakeSkillsMongo:
    """Minimal stand-in for the motor client: one aggregate over employee_skills."""
    def __init__(self, rows):
        self._rows = rows

    def __getitem__(self, _db):
        rows = self._rows

        class _Coll:
            def aggregate(self, _pipeline):
                async def gen():
                    for r in rows:
                        yield r
                return gen()

        return {"employee_skills": _Coll()}


def test_skill_gaps_derive_from_real_skill_coverage(monkeypatch):
    # Engineering, headcount 100 -> a skill is covered when >= 25 people hold it.
    # 6 of its 8 required skills are covered (share 0.75 -> LOW). Sales, headcount
    # 100 -> only 2 of 7 covered (share ~0.29 -> HIGH).
    from services.skill_requirements import REQUIRED_SKILLS
    eng_skills = REQUIRED_SKILLS["Engineering"][:6]
    sales_skills = REQUIRED_SKILLS["Sales"][:2]
    rows = ([{"_id": {"d": "Engineering", "s": s}, "n": 30} for s in eng_skills]
            + [{"_id": {"d": "Sales", "s": s}, "n": 40} for s in sales_skills])

    fake_pg = FakePgClient(
        emp_row=None, perf_row=None,
        dept_rows=[{"department": "Engineering", "c": 100},
                   {"department": "Sales", "c": 100}],
    )
    monkeypatch.setattr(wfp_mod, "pg_client", fake_pg)
    svc = _svc()
    svc.mongo_client = FakeSkillsMongo(rows)

    gaps = asyncio.run(svc._derive_skill_gaps(200))
    assert gaps["Engineering"] == "LOW"
    assert gaps["Sales"] == "HIGH"


def test_projections_empty_db(monkeypatch):
    fake = FakePgClient(emp_row=None, perf_row=None, dept_rows=[])
    monkeypatch.setattr(wfp_mod, "pg_client", fake)
    proj = asyncio.run(_svc().get_current_projections())
    assert proj["current_state"]["total_employees"] == 0
    assert proj["skill_gaps"] == {}               # no headcount -> no derivation, no crash


class FakeChartsPg:
    """Routes the dept-aggregate vs scatter queries by keyword."""
    async def fetch(self, query, *args):
        if "JOIN public.performance_reviews" in query:
            return [{"tenure": 36, "rating": 3.5, "department": "Sales"},
                    {"tenure": 12, "rating": 4.0, "department": "Engineering"}]
        return [{"department": "Engineering", "headcount": 8000, "avg_risk": 0.30},
                {"department": "Sales", "headcount": 3000, "avg_risk": 0.55}]


def test_analytics_charts_shapes(monkeypatch):
    monkeypatch.setattr(wfp_mod, "pg_client", FakeChartsPg())
    charts = asyncio.run(_svc().get_analytics_charts())

    assert charts["headcount_by_department"][0] == {"name": "Engineering", "value": 8000}
    # avg_risk 0.55 -> 55.0 on a 0-100 scale
    assert charts["attrition_by_department"][1] == {"name": "Sales", "value": 55.0}
    pts = charts["perf_vs_tenure"]
    assert pts[0] == {"tenure": 36, "rating": 3.5, "department": "Sales"}
    assert all({"tenure", "rating", "department"} == set(p) for p in pts)


_TESTS = [test_projections_map_real_aggregates, test_projections_empty_db,
          test_skill_gaps_derive_from_real_skill_coverage, test_analytics_charts_shapes]

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
