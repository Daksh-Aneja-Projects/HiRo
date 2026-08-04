"""Unit tests for services/policy_versioning.py PolicyVersioningService.

The service persists to MongoDB when available and otherwise runs fully in
memory, so these exercise the real version lifecycle (create -> submit ->
approve -> activate -> rollback) without a database.
"""
import json
import pytest

from services.policy_versioning import (
    PolicyVersioningService,
    PolicyStatus,
    ApprovalStatus,
)


@pytest.fixture(scope="module")
def _service():
    return PolicyVersioningService()


@pytest.fixture
def svc(_service):
    for d in (_service.versions, _service.policy_index,
              _service.active_versions, _service.approval_requests):
        d.clear()
    _service.audit_trail.clear()
    return _service


CONTENT = {"policy_name": "Leave Policy", "rules": [{"max_days": 20}]}


# ---- version numbering -----------------------------------------------------

def test_increment_patch(svc):
    assert svc._increment_version("1.2.3", "patch") == "1.2.4"


def test_increment_minor(svc):
    assert svc._increment_version("1.2.3", "minor") == "1.3.0"


def test_increment_major(svc):
    assert svc._increment_version("1.2.3", "major") == "2.0.0"


def test_increment_short_version_padded(svc):
    assert svc._increment_version("2", "minor") == "2.1.0"


def test_increment_malformed_falls_back(svc):
    assert svc._increment_version("not.a.version", "patch") == "1.0.0"


# ---- content hashing -------------------------------------------------------

def test_content_hash_is_deterministic(svc):
    assert svc._generate_content_hash(CONTENT) == svc._generate_content_hash(dict(CONTENT))


def test_content_hash_changes_with_content(svc):
    other = {"policy_name": "Leave Policy", "rules": [{"max_days": 21}]}
    assert svc._generate_content_hash(CONTENT) != svc._generate_content_hash(other)


# ---- creation --------------------------------------------------------------

def test_first_version_is_1_0_0_and_draft(svc):
    v = svc.create_policy_version("POL1", CONTENT, "alice")
    assert v.version_number == "1.0.0"
    assert v.status == PolicyStatus.DRAFT
    assert v.created_by == "alice"
    assert v.parent_version is None


def test_second_version_increments_and_links_parent(svc):
    v1 = svc.create_policy_version("POL1", CONTENT, "alice")
    _approve_and_activate(svc, v1, ["boss"])
    v2 = svc.create_policy_version("POL1", {"policy_name": "x", "rules": []}, "alice")
    assert v2.version_number == "1.0.1"
    assert v2.parent_version == v1.version_id


def test_create_registers_in_history_and_audit(svc):
    v = svc.create_policy_version("POL2", CONTENT, "alice")
    assert v.version_id in [x.version_id for x in svc.get_version_history("POL2")]
    assert any(e["action"] == "created" for e in svc.get_audit_trail(v.version_id))


# ---- updating drafts -------------------------------------------------------

def test_update_draft_changes_hash(svc):
    v = svc.create_policy_version("POL3", CONTENT, "alice")
    old_hash = v.content_hash
    svc.update_version_content(v.version_id, {"policy_name": "y", "rules": []}, "alice")
    assert v.content_hash != old_hash


def test_update_unknown_version_raises(svc):
    with pytest.raises(ValueError):
        svc.update_version_content("nope", CONTENT, "alice")


def test_cannot_update_non_draft(svc):
    v = svc.create_policy_version("POL3", CONTENT, "alice")
    svc.submit_for_approval(v.version_id, "alice", ["boss"])
    with pytest.raises(ValueError):
        svc.update_version_content(v.version_id, CONTENT, "alice")


# ---- submission ------------------------------------------------------------

def test_submit_moves_to_review(svc):
    v = svc.create_policy_version("POL4", CONTENT, "alice")
    req = svc.submit_for_approval(v.version_id, "alice", ["boss"], comments="please review")
    assert v.status == PolicyStatus.REVIEW
    assert req.status == ApprovalStatus.PENDING
    assert req.comments and req.comments[0]["comment"] == "please review"


def test_submit_unknown_version_raises(svc):
    with pytest.raises(ValueError):
        svc.submit_for_approval("nope", "alice", ["boss"])


def test_cannot_submit_twice(svc):
    v = svc.create_policy_version("POL4", CONTENT, "alice")
    svc.submit_for_approval(v.version_id, "alice", ["boss"])
    with pytest.raises(ValueError):
        svc.submit_for_approval(v.version_id, "alice", ["boss"])


# ---- approval --------------------------------------------------------------

def test_reject_returns_version_to_draft(svc):
    v = svc.create_policy_version("POL5", CONTENT, "alice")
    req = svc.submit_for_approval(v.version_id, "alice", ["boss"])
    svc.approve_policy(req.request_id, "boss", approved=False, comments="no")
    assert req.status == ApprovalStatus.REJECTED
    assert v.status == PolicyStatus.DRAFT


def test_full_approval_marks_version_approved(svc):
    v = svc.create_policy_version("POL5", CONTENT, "alice")
    req = svc.submit_for_approval(v.version_id, "alice", ["boss"])
    svc.approve_policy(req.request_id, "boss", approved=True)
    assert req.status == ApprovalStatus.APPROVED
    assert v.status == PolicyStatus.APPROVED


def test_multi_approver_requires_all(svc):
    v = svc.create_policy_version("POL5", CONTENT, "alice")
    req = svc.submit_for_approval(v.version_id, "alice", ["boss", "vp"])
    svc.approve_policy(req.request_id, "boss", approved=True)
    assert req.status == ApprovalStatus.PENDING  # still waiting on vp
    svc.approve_policy(req.request_id, "vp", approved=True)
    assert req.status == ApprovalStatus.APPROVED


def test_unauthorized_approver_raises(svc):
    v = svc.create_policy_version("POL5", CONTENT, "alice")
    req = svc.submit_for_approval(v.version_id, "alice", ["boss"])
    with pytest.raises(ValueError):
        svc.approve_policy(req.request_id, "stranger", approved=True)


def test_approve_unknown_request_raises(svc):
    with pytest.raises(ValueError):
        svc.approve_policy("nope", "boss", approved=True)


# ---- activation & rollback -------------------------------------------------

def _approve_and_activate(svc, version, approvers):
    req = svc.submit_for_approval(version.version_id, "alice", approvers)
    for a in approvers:
        svc.approve_policy(req.request_id, a, approved=True)
    return svc.activate_version(version.version_id, "admin")


def test_activate_requires_approved(svc):
    v = svc.create_policy_version("POL6", CONTENT, "alice")
    with pytest.raises(ValueError):
        svc.activate_version(v.version_id, "admin")


def test_activate_sets_active_and_get_active(svc):
    v = svc.create_policy_version("POL6", CONTENT, "alice")
    _approve_and_activate(svc, v, ["boss"])
    assert v.status == PolicyStatus.ACTIVE
    assert svc.get_active_version("POL6").version_id == v.version_id


def test_activating_new_version_deprecates_old(svc):
    v1 = svc.create_policy_version("POL6", CONTENT, "alice")
    _approve_and_activate(svc, v1, ["boss"])
    v2 = svc.create_policy_version("POL6", {"policy_name": "z", "rules": []}, "alice")
    _approve_and_activate(svc, v2, ["boss"])
    assert v1.status == PolicyStatus.DEPRECATED
    assert svc.get_active_version("POL6").version_id == v2.version_id


def test_rollback_reactivates_target(svc):
    v1 = svc.create_policy_version("POL6", CONTENT, "alice")
    _approve_and_activate(svc, v1, ["boss"])
    v2 = svc.create_policy_version("POL6", {"policy_name": "z", "rules": []}, "alice")
    _approve_and_activate(svc, v2, ["boss"])
    svc.rollback_to_version("POL6", v1.version_id, "admin")
    assert svc.get_active_version("POL6").version_id == v1.version_id


def test_rollback_wrong_policy_raises(svc):
    v = svc.create_policy_version("POL7", CONTENT, "alice")
    with pytest.raises(ValueError):
        svc.rollback_to_version("OTHER", v.version_id, "admin")


# ---- history / compare / export -------------------------------------------

def test_get_active_version_none_when_absent(svc):
    assert svc.get_active_version("does-not-exist") is None


def test_history_contains_all_versions(svc):
    v1 = svc.create_policy_version("POL8", CONTENT, "alice")
    _approve_and_activate(svc, v1, ["boss"])
    v2 = svc.create_policy_version("POL8", {"policy_name": "z", "rules": []}, "alice")
    history_ids = {h.version_id for h in svc.get_version_history("POL8")}
    assert history_ids == {v1.version_id, v2.version_id}


def test_compare_versions_detects_content_change(svc):
    v1 = svc.create_policy_version("POL9", CONTENT, "alice")
    _approve_and_activate(svc, v1, ["boss"])
    v2 = svc.create_policy_version("POL9", {"policy_name": "z", "rules": []}, "alice")
    diff = svc.compare_versions(v1.version_id, v2.version_id)
    assert diff["content_changed"] is True


def test_compare_missing_version_raises(svc):
    v = svc.create_policy_version("POL9", CONTENT, "alice")
    with pytest.raises(ValueError):
        svc.compare_versions(v.version_id, "missing")


def test_export_version_as_json_roundtrips(svc):
    v = svc.create_policy_version("POL10", CONTENT, "alice")
    payload = json.loads(svc.export_version_as_json(v.version_id))
    assert payload["version_id"] == v.version_id
    assert payload["policy_id"] == "POL10"
