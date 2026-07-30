"""Unit tests for the real admin + analytics dashboard route logic.

Uses lightweight fakes for Request.app.state so the derivation math and field
mapping are verified without a live app or database.
"""
import asyncio
from types import SimpleNamespace

from services import comprehensive_routes as routes


def _req(**state):
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(**state)))


class FakeWFM:
    def __init__(self, risk, perf, headcount):
        self._risk, self._perf, self._headcount = risk, perf, headcount

    async def get_current_projections(self):
        return {"current_state": {
            "overall_risk_score": self._risk,
            "average_performance_score": self._perf,
            "total_employees": self._headcount,
        }}


class FakePQC:
    master_key_bytes = b"key"


def test_workforce_analytics_math():
    req = _req(wfm_service=FakeWFM(risk=0.4, perf=4.0, headcount=20000))
    a = asyncio.run(routes._workforce_analytics(req))
    # retention = (1-0.4)*100 = 60.0
    assert a["retention"] == "60.0%"
    # attrition_risk = 0.4*10 = 4.0/10
    assert a["attrition_risk"] == "4.0/10"
    # composite = ((0.6)*0.5 + (0.8)*0.5)*100 = 70.0
    assert a["key_metric"] == "70.0%"
    assert a["ml_score"] == "80.0%"
    assert a["headcount"] == 20000


def test_financial_impact_estimate():
    req = _req(wfm_service=FakeWFM(risk=0.3, perf=3.5, headcount=100))
    out = asyncio.run(routes.aggregate_metrics.__wrapped__(req, {"metric_type": "financial_impact"}, {})) \
        if hasattr(routes.aggregate_metrics, "__wrapped__") else \
        asyncio.run(routes.aggregate_metrics(req, {"metric_type": "financial_impact"}, {}))
    assert out["value"] == 850000.0        # 100 * 8500
    assert "estimate" in out["note"]


def test_admin_dashboard_maps_real_signals(monkeypatch):
    async def fake_overview():
        return {"score": 0.82, "high_severity_violations": 4}
    # patch the symbol imported lazily inside the route
    monkeypatch.setattr("services.enforcement_engine.get_compliance_overview", fake_overview)

    req = _req(pqc_wrapper=FakePQC())
    out = asyncio.run(routes.get_admin_dashboard(req, {}))
    assert out["integrity_score"] == 82.0
    assert out["active_pqc_keys"] == 1
    assert out["critical_alerts"] == 4
    assert out["cache_util_pct"] != None   # psutil value or "N/A", never crashes


_TESTS = [test_workforce_analytics_math, test_financial_impact_estimate, test_admin_dashboard_maps_real_signals]

if __name__ == "__main__":
    import sys as _sys

    class _MP:
        def __init__(self): self._undo = []
        def setattr(self, target, *rest):
            if rest and isinstance(target, str):
                mod_name, attr = target.rsplit(".", 1)
                import importlib
                obj = importlib.import_module(mod_name)
                val = rest[0]
            else:
                obj, attr, val = target, rest[0], rest[1]
            self._undo.append((obj, attr, getattr(obj, attr)))
            setattr(obj, attr, val)
        def undo(self):
            for obj, attr, val in reversed(self._undo): setattr(obj, attr, val)
            self._undo = []

    passed = 0
    for fn in _TESTS:
        mp = _MP()
        try:
            fn(mp) if fn.__code__.co_argcount else fn()
            print(f"PASS {fn.__name__}"); passed += 1
        except Exception as e:
            print(f"FAIL {fn.__name__}: {type(e).__name__}: {e}")
        finally:
            mp.undo()
    print(f"{passed}/{len(_TESTS)} passed")
    _sys.exit(0 if passed == len(_TESTS) else 1)
