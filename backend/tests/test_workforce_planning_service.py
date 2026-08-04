"""Unit tests for services/workforce_planning_service.py attrition scoring.

predict_attrition_risk is exercised with supplied feature values (no employee
id), which keeps it self-contained -- no Mongo/Postgres lookup -- so the scoring
math and its human-readable drivers/recommendation are verified directly.
"""
import asyncio
import pytest

from services.workforce_planning_service import WorkforcePlanningService


@pytest.fixture(scope="module")
def svc():
    return WorkforcePlanningService(publisher=None, mongo_client=None)


def risk(svc, **features):
    return asyncio.run(svc.predict_attrition_risk(dict(features)))


LOW = dict(tenure_months=60, satisfaction_score=5.0, compensation_percentile=90, last_raise_months=6)
HIGH = dict(tenure_months=24, satisfaction_score=2.0, compensation_percentile=10, last_raise_months=36)
CRIT = dict(tenure_months=13, satisfaction_score=1.0, compensation_percentile=5, last_raise_months=48)


def test_result_shape(svc):
    r = risk(svc, **LOW)
    for key in ("risk_score", "risk_level", "drivers", "recommendation", "feature_vector_used", "baseline_risk"):
        assert key in r


def test_risk_score_bounded(svc):
    for data in (LOW, HIGH, CRIT):
        r = risk(svc, **data)
        assert 0.0 <= r["risk_score"] <= 1.0


def test_low_profile_is_low_risk(svc):
    assert risk(svc, **LOW)["risk_level"] == "LOW"


def test_high_profile_is_high_or_critical(svc):
    assert risk(svc, **HIGH)["risk_level"] in ("HIGH", "CRITICAL")


def test_worse_profile_scores_higher(svc):
    assert risk(svc, **CRIT)["risk_score"] >= risk(svc, **HIGH)["risk_score"] >= risk(svc, **LOW)["risk_score"]


def test_extreme_profile_clamps_to_one(svc):
    r = risk(svc, tenure_months=13, satisfaction_score=0.0, compensation_percentile=0, last_raise_months=120)
    assert r["risk_score"] <= 1.0
    assert r["risk_level"] == "CRITICAL"


def test_drivers_have_readable_reasons(svc):
    drivers = risk(svc, **HIGH)["drivers"]
    assert drivers
    for d in drivers:
        assert set(d) == {"feature", "impact", "reason"}
        assert isinstance(d["reason"], str) and d["reason"]


def test_compa_ratio_hidden_without_percentile(svc):
    r = risk(svc, tenure_months=40, satisfaction_score=4.0, last_raise_months=6)
    assert r["feature_vector_used"]["compa_ratio"] is None


def test_compa_ratio_shown_with_percentile(svc):
    r = risk(svc, **LOW)
    assert r["feature_vector_used"]["compa_ratio"] is not None


def test_new_employee_flagged(svc):
    r = risk(svc, tenure_months=3, satisfaction_score=4.0)
    features = [d["feature"] for d in r["drivers"]]
    assert "Tenure_Months" in features


def test_source_supplied_when_no_job_title(svc):
    assert risk(svc, **LOW)["source"] == "supplied values only"


def test_dtla_fallback_used_when_no_tenure(svc):
    r = risk(svc, satisfaction_score=3.0, dtla_risk_score=0.9)
    # With no tenure on file the bulk-computed signal is used as the fallback.
    assert r["risk_score"] == pytest.approx(0.9, abs=0.05)


def test_recommendation_critical(svc):
    assert "URGENT" in svc._get_recommendation("CRITICAL", 1.0, 4.0, 6)


def test_recommendation_high_low_comp(svc):
    assert "compensation" in svc._get_recommendation("HIGH", 0.85, 4.0, 18).lower()


def test_recommendation_high_low_perf(svc):
    assert "mentorship" in svc._get_recommendation("HIGH", 1.2, 2.5, 6).lower()


def test_recommendation_high_default_stay_interview(svc):
    assert "stay interview" in svc._get_recommendation("HIGH", 1.2, 4.0, 6).lower()


def test_recommendation_low_maintain(svc):
    assert "check-ins" in svc._get_recommendation("LOW", 1.0, 4.0, 6).lower()
