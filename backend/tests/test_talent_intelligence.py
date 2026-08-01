"""Unit tests for the Talent Intelligence build: internal mobility, succession 9-box,
comp-cycle budget guard + finalize-through-real-path, headcount variance, eNPS
arithmetic + anonymity floor + dedupe, milestone dedupe, candidate stage-transition
enforcement, and nudges degrading gracefully when sibling data is absent.

Fake clients only -- no live Postgres/Mongo/LLM required. Run with:
    pytest tests/test_talent_intelligence.py --noconftest
"""
import asyncio
from datetime import date

import pytest

from config.settings import settings
from services import comp_planning_service as comp
from services import engagement_service as eng
from services import manager_nudges as nudges_svc
from services import milestones_service
from services import talent_intelligence as ti
import services.comprehensive_routes as cr


# ---------------------------------------------------------------------------
# Shared fakes
# ---------------------------------------------------------------------------

class FakeVault:
    def decrypt(self, ciphertext, data_context="default"):
        return ciphertext.replace("ENC:", "")

    async def execute_pii_query(self, query, table_name, agent_id, auth=None, *args):
        uuids = args[-1] if args else []
        names = {"E1": "Alice Adjacent", "E2": "Bob Cross"}
        return [{"employee_uuid": u, "full_name": names.get(u, u)} for u in uuids]


class _FakeVaultClass:
    _instance = FakeVault()

    @staticmethod
    def get_instance():
        return _FakeVaultClass._instance


class FakeCursor:
    """Supports both `await cursor.to_list(n)` and `async for d in cursor`, matching
    the two ways motor cursors get consumed across this build."""
    def __init__(self, docs):
        self.docs = docs

    async def to_list(self, n):
        return self.docs[:n]

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        for d in self.docs:
            yield d


# ---------------------------------------------------------------------------
# 1. Internal mobility matching
# ---------------------------------------------------------------------------

class FakeSkillsCollection:
    def __init__(self, docs):
        self.docs = docs

    def aggregate(self, pipeline):
        needed = pipeline[0]["$match"]["skills"]["$in"]
        out = []
        for d in self.docs:
            matched = [s for s in d["skills"] if s in needed]
            if matched:
                out.append({"employee_uuid": d["employee_uuid"], "department": d["department"],
                            "matched": matched, "match_count": len(matched)})
        out.sort(key=lambda x: x["match_count"], reverse=True)
        limit = pipeline[-1].get("$limit", len(out))
        return FakeCursor(out[:limit])


class FakeMongoSkills(dict):
    def __init__(self, skills_docs):
        super().__init__()
        self[settings.MONGO_DB_NAME] = {"employee_skills": FakeSkillsCollection(skills_docs)}


class FakePgRows:
    def __init__(self, rows):
        self.rows = rows

    async def fetch(self, query, *args):
        return self.rows


def test_mobility_scores_ladder_adjacency_and_reports_gaps(monkeypatch):
    monkeypatch.setattr(ti, "PIIVault", _FakeVaultClass)
    needed = ti.REQUIRED_SKILLS["Engineering"]
    skills_docs = [
        {"employee_uuid": "E1", "department": "Engineering", "skills": needed[:-1]},
        {"employee_uuid": "E2", "department": "Marketing", "skills": needed[:1]},
    ]
    monkeypatch.setattr(ti, "pg_client", FakePgRows([
        {"employee_uuid": "E1", "full_name_encrypted": "ENC:Alice Adjacent", "department": "Engineering",
         "job_title": "Senior Engineer", "tenure_months": 36, "avg_rating": 4.5},
        {"employee_uuid": "E2", "full_name_encrypted": "ENC:Bob Cross", "department": "Marketing",
         "job_title": "Marketing Specialist", "tenure_months": 6, "avg_rating": 3.0},
    ]))

    requisition = {"requisition_id": "REQ-1", "department": "Engineering", "title": "Staff Engineer"}
    result = asyncio.run(ti.internal_matches_for_requisition(FakeMongoSkills(skills_docs), requisition, limit=10))

    matches = result["matches"]
    # E1: Engineering, one rung below the role, holds nearly everything it needs -> outranks E2.
    assert [m["employee_uuid"] for m in matches] == ["E1", "E2"]
    assert matches[0]["skill_gaps"] == [needed[-1]]
    assert "natural next step" in matches[0]["narrative"]
    assert matches[1]["current_department"] == "Marketing"
    assert "cross-department" in matches[1]["narrative"]


def test_mobility_no_requirements_defined_returns_honest_note():
    requisition = {"requisition_id": "REQ-X", "department": "NoSuchDept", "title": "Something"}
    result = asyncio.run(ti.internal_matches_for_requisition(FakeMongoSkills([]), requisition))
    assert result["matches"] == []
    assert "No skill requirements" in result["note"]


# ---------------------------------------------------------------------------
# 2. 9-box axis math
# ---------------------------------------------------------------------------

class FakeSkillCountCollection:
    def __init__(self, counts):
        self.counts = counts

    def aggregate(self, pipeline):
        uuids = pipeline[0]["$match"]["employee_uuid"]["$in"]
        return FakeCursor([{"employee_uuid": u, "n": self.counts.get(u, 0)} for u in uuids])


class FakeMongoSkillCounts(dict):
    def __init__(self, counts):
        super().__init__()
        self[settings.MONGO_DB_NAME] = {"employee_skills": FakeSkillCountCollection(counts)}


def test_nine_box_potential_heuristic_buckets_correctly(monkeypatch):
    monkeypatch.setattr(ti, "LADDERS", {"Eng": ["Engineer", "Senior Engineer", "Staff Engineer"]})
    monkeypatch.setattr(ti, "REQUIRED_SKILLS", {"Eng": ["A", "B", "C", "D"]})
    monkeypatch.setattr(ti, "PIIVault", _FakeVaultClass)
    monkeypatch.setattr(ti, "pg_client", FakePgRows([
        {"employee_uuid": "P1", "full_name_encrypted": "ENC:Pat High", "department": "Eng",
         "job_title": "Staff Engineer", "tenure_months": 60, "avg_rating": 4.8},
        {"employee_uuid": "P2", "full_name_encrypted": "ENC:Lee Low", "department": "Eng",
         "job_title": "Engineer", "tenure_months": 3, "avg_rating": 2.0},
    ]))

    result = asyncio.run(ti.nine_box(FakeMongoSkillCounts({"P1": 4, "P2": 0})))

    cells = {(c["performance"], c["potential"]): c for c in result["cells"]}
    assert cells[("High", "High")]["count"] == 1        # P1: rating 4.8, full tenure + skill breadth
    assert cells[("Low", "Low")]["count"] == 1           # P2: rating 2.0, new and no skills logged
    assert result["potential_is_heuristic"] is True
    assert result["population"] == 2


# ---------------------------------------------------------------------------
# 3. Comp cycle budget guard + finalize-through-real-path
# ---------------------------------------------------------------------------

class FakePgComp:
    def __init__(self, cycle, lines):
        self.cycle = cycle
        self.lines = lines
        self.executed = []

    async def fetchrow(self, query, *args):
        return dict(self.cycle) if "FROM comp_cycles" in query and self.cycle else None

    async def fetch(self, query, *args):
        return [dict(l) for l in self.lines] if "FROM comp_cycle_lines" in query else []

    async def execute(self, query, *args):
        self.executed.append((query, args))
        return "UPDATE 1"


class FakeHRModules:
    def __init__(self):
        self.calls = []

    async def update_compensation(self, employee_id, new_salary, new_grade, effective_date, updated_by):
        self.calls.append((employee_id, new_salary))
        return {"status": "SUCCESS"}


def test_finalize_cycle_over_budget_raises_with_plain_english_arithmetic(monkeypatch):
    cycle = {"cycle_id": "CYC-1", "status": "draft", "budget_pct": 3.0}
    lines = [{"id": 1, "cycle_id": "CYC-1", "employee_uuid": "E1",
              "current_comp_cents": 10_000_000, "proposed_pct": 10.0, "status": "proposed"}]
    monkeypatch.setattr(comp, "pg_client", FakePgComp(cycle, lines))

    with pytest.raises(comp.BudgetExceeded) as exc:
        asyncio.run(comp.finalize_cycle("CYC-1", FakeHRModules(), "hrbp"))
    message = str(exc.value)
    assert "budget" in message and "%" in message and "$" in message


def test_finalize_cycle_within_budget_applies_through_hr_modules_service(monkeypatch):
    cycle = {"cycle_id": "CYC-2", "status": "draft", "budget_pct": 5.0}
    lines = [{"id": 1, "cycle_id": "CYC-2", "employee_uuid": "E1",
              "current_comp_cents": 10_000_000, "proposed_pct": 3.0, "status": "proposed"}]
    monkeypatch.setattr(comp, "pg_client", FakePgComp(cycle, lines))
    hr = FakeHRModules()

    result = asyncio.run(comp.finalize_cycle("CYC-2", hr, "hrbp"))

    assert result["status"] == "finalized"
    assert result["lines_applied"] == 1
    # The exact real path a manual pay change already uses: update_compensation, not
    # a duplicate write to employee_pii/comp_history from this module.
    assert hr.calls == [("E1", 103000.0)]


# ---------------------------------------------------------------------------
# 4. Headcount variance
# ---------------------------------------------------------------------------

class FakePgHeadcount:
    def __init__(self, plans, actuals):
        self.plans, self.actuals = plans, actuals

    async def fetch(self, query, *args):
        return self.plans if "FROM headcount_plans" in query else self.actuals


def test_headcount_variance_computes_planned_vs_actual(monkeypatch):
    plans = [{"department": "Engineering", "plan_id": "P1", "fiscal_label": "FY26", "planned_headcount": 100}]
    actuals = [{"department": "Engineering", "actual": 120}]
    monkeypatch.setattr(comp, "pg_client", FakePgHeadcount(plans, actuals))

    row = asyncio.run(comp.headcount_variance())["departments"][0]
    assert row["variance"] == 20
    assert row["variance_pct"] == 20.0
    assert "over plan by 20" in row["summary"]


# ---------------------------------------------------------------------------
# 5. eNPS arithmetic + anonymity floor + dedupe
# ---------------------------------------------------------------------------

class FakePulseCollection:
    def __init__(self):
        self.docs = []

    async def find_one(self, query):
        return next((d for d in self.docs if all(d.get(k) == v for k, v in query.items())), None)

    async def insert_one(self, doc):
        self.docs.append(dict(doc))

    def find(self, query, projection=None):
        return FakeCursor([d for d in self.docs if all(d.get(k) == v for k, v in query.items())])


class FakeEngDB:
    def __init__(self):
        self.pulse_responses = FakePulseCollection()


def test_pulse_dedupe_rejects_second_submission_to_same_survey():
    db = FakeEngDB()
    asyncio.run(eng.submit_pulse(db, username="dana", score=9, comment="great", survey_id="s1"))
    with pytest.raises(ValueError):
        asyncio.run(eng.submit_pulse(db, username="dana", score=2, comment="bad", survey_id="s1"))


def test_enps_arithmetic_and_response_rate():
    db = FakeEngDB()
    for i, score in enumerate([9, 9, 9, 0, 5]):  # 3 promoters (>=9), 2 detractors (<=6: 0 and 5)
        asyncio.run(eng.submit_pulse(db, username=f"user{i}", score=score, comment="fine", survey_id="s1"))

    summary = asyncio.run(eng.engagement_summary(db, ai_service=None, total_accounts=10, survey_id="s1"))
    assert summary["responses"] == 5
    assert summary["enps"] == 20.0          # (3 - 2) / 5 * 100
    assert summary["response_rate_pct"] == 50.0


def test_enps_below_anonymity_floor_withholds_themes_but_keeps_scores():
    db = FakeEngDB()
    for i in range(3):  # below ANONYMITY_FLOOR of 5
        asyncio.run(eng.submit_pulse(db, username=f"user{i}", score=8, comment="ok", survey_id="s2"))

    summary = asyncio.run(eng.engagement_summary(db, ai_service=None, total_accounts=10, survey_id="s2"))
    assert summary["responses"] == 3
    assert summary["enps"] is not None       # scores shown even below the floor
    assert summary["themes"] == "unavailable"
    assert "identif" in summary["note"].lower()


# ---------------------------------------------------------------------------
# 6. Milestone dedupe
# ---------------------------------------------------------------------------

class FakeMilestonePostsCollection:
    def __init__(self):
        self.docs = []

    async def find_one(self, query):
        return next((d for d in self.docs if all(d.get(k) == v for k, v in query.items())), None)

    async def insert_one(self, doc):
        self.docs.append(dict(doc))


class FakeSocialPostsCollection:
    def __init__(self):
        self.insert_calls = 0

    async def insert_one(self, doc):
        self.insert_calls += 1


class FakeMilestoneDB:
    def __init__(self):
        self.milestone_posts = FakeMilestonePostsCollection()
        self.social_posts = FakeSocialPostsCollection()


def test_milestone_posts_once_per_employee_per_anniversary_year(monkeypatch):
    today = date.today()
    hire = today.replace(year=today.year - 5)  # anniversary is exactly today
    monkeypatch.setattr(milestones_service, "pg_client", FakePgRows([
        {"employee_uuid": "E1", "full_name_encrypted": "ENC:Anniversary Ann",
         "department": "Sales", "job_title": "Sales Associate", "hire_date": hire},
    ]))
    monkeypatch.setattr(milestones_service, "PIIVault", _FakeVaultClass)

    db = FakeMilestoneDB()
    first = asyncio.run(milestones_service.check_and_post_todays_anniversaries(db))
    second = asyncio.run(milestones_service.check_and_post_todays_anniversaries(db))

    assert first == 1
    assert second == 0                          # already posted this anniversary year
    assert db.social_posts.insert_calls == 1


# ---------------------------------------------------------------------------
# 7. Candidate stage-transition enforcement
# ---------------------------------------------------------------------------

class FakeCandidatesCollection:
    def __init__(self):
        self.docs = {}

    async def insert_one(self, doc):
        self.docs[doc["candidate_id"]] = dict(doc)

    async def find_one(self, query):
        return self.docs.get(query.get("candidate_id"))

    async def update_one(self, query, update):
        doc = self.docs[query["candidate_id"]]
        doc.update(update.get("$set", {}))
        for field, value in update.get("$push", {}).items():
            doc.setdefault(field, []).append(value)


class FakeCandidateDB:
    def __init__(self):
        self.candidates = FakeCandidatesCollection()


def test_candidate_stage_transitions_enforce_legal_order():
    db = FakeCandidateDB()
    created = asyncio.run(ti.create_candidate(db, requisition_id="REQ-1", name="Cam Didate",
                                               source="referral", by="mgr"))
    cid = created["candidate_id"]

    advanced = asyncio.run(ti.advance_candidate(db, cid, "screen", "looks good", "mgr"))
    assert advanced["stage"] == "screen"

    with pytest.raises(ValueError):  # cannot skip "interview"
        asyncio.run(ti.advance_candidate(db, cid, "offer", "", "mgr"))

    rejected = asyncio.run(ti.advance_candidate(db, cid, "rejected", "not a fit", "mgr"))
    assert rejected["stage"] == "rejected"
    assert "onboarding_hint" not in rejected

    with pytest.raises(ValueError):  # terminal state, no further moves
        asyncio.run(ti.advance_candidate(db, cid, "screen", "", "mgr"))


def test_candidate_hired_includes_onboarding_pointer():
    db = FakeCandidateDB()
    created = asyncio.run(ti.create_candidate(db, requisition_id="REQ-1", name="Hana Hire",
                                               source="referral", by="mgr"))
    cid = created["candidate_id"]
    for stage in ("screen", "interview", "offer", "hired"):
        result = asyncio.run(ti.advance_candidate(db, cid, stage, "", "mgr"))
    assert "onboarding" in result["onboarding_hint"].lower()


# ---------------------------------------------------------------------------
# 8. Nudges degrade gracefully when sibling collections/tables are absent
# ---------------------------------------------------------------------------

class FakeNudgesPg:
    def __init__(self, roster):
        self.roster = roster

    async def fetch(self, query, *args):
        if "FROM employee_pii WHERE manager_id" in query:
            return self.roster
        if "FROM one_on_ones" in query:
            raise Exception('relation "one_on_ones" does not exist')
        return []


class FakeWfm:
    async def predict_attrition_risk(self, employee_data):
        return {"employee_uuid": employee_data["employee_uuid"], "risk_level": "LOW",
                "risk_score": 0.1, "recommendation": "Maintain regular check-ins.",
                "drivers": [], "job_title": "Engineer"}


async def _fake_approval_queue(req, payload, limit=100):
    return []


def test_nudges_omit_one_on_ones_honestly_when_table_missing(monkeypatch):
    nudges_svc._cache.clear()
    monkeypatch.setattr(nudges_svc, "pg_client", FakeNudgesPg(roster=[{"employee_uuid": "E1"}]))
    monkeypatch.setattr(milestones_service, "pg_client", FakePgRows([]))
    monkeypatch.setattr(cr, "_approval_queue", _fake_approval_queue)

    result = asyncio.run(nudges_svc.nudges_for_manager(
        None, {"sub": "mgr1", "role": "manager", "employee_uuid": "MGR1"}, FakeWfm(), FakeMilestoneDB()))

    assert not any(n["kind"] == "overdue_one_on_ones" for n in result["nudges"])
    assert not any(n["kind"] == "flight_risk" for n in result["nudges"])  # roster is LOW risk only
    assert any("isn't available yet" in note for note in result["notes"])
