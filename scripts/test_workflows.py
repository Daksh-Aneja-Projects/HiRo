"""End-to-end persona workflow tests against a running HiRo backend.

Drives real multi-persona flows (not just endpoint pings) so regressions in the
cross-role handoffs are caught: employee submits leave -> manager approves ->
employee sees the decision.

Usage:  python scripts/test_workflows.py
Exit code is non-zero if any workflow fails.
"""
import json
import sys
import urllib.error
import urllib.request

API = "http://localhost:8100/api"
_failures = []


def call(method, path, token=None, body=None, expect=200):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{API}{path}", data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            payload = json.loads(r.read().decode() or "null")
            status = r.status
    except urllib.error.HTTPError as e:
        payload, status = e.read().decode()[:200], e.code
    except Exception as e:
        payload, status = str(e), 0
    if expect is not None and status != expect:
        raise AssertionError(f"{method} {path} -> {status} (expected {expect}): {payload}")
    return payload


def login(user):
    return call("POST", "/auth/login", body={"username": user, "password": user})["access_token"]


def check(name, fn):
    try:
        fn()
        print(f"  PASS  {name}")
    except Exception as e:
        print(f"  FAIL  {name}\n          {e}")
        _failures.append(name)


def wf_leave_approval():
    """Employee requests leave, manager approves, employee sees APPROVED."""
    emp, mgr = login("employee"), login("manager")
    created = call("POST", "/ess/leave/submit", emp,
                   {"start_date": "2026-09-01", "end_date": "2026-09-03", "hours": 24})
    rid = created["request_id"]

    queue = call("GET", "/mss/approvals/queue", mgr)
    assert any(q["request_id"] == rid for q in queue), "new request missing from manager queue"

    decision = call("POST", "/mss/approvals/action", mgr,
                    {"request_id": rid, "approved": True, "comments": "ok"})
    assert decision["status"] == "APPROVED", f"expected APPROVED, got {decision}"

    history = call("GET", "/hr/leave/requests", emp)
    row = next((h for h in history if h["request_id"] == rid), None)
    assert row, "approved request missing from employee history"
    assert row["status"] == "APPROVED", f"employee sees {row['status']}"


def wf_leave_rejection():
    """A rejected request must read REJECTED, not APPROVED."""
    emp, mgr = login("employee"), login("manager")
    rid = call("POST", "/ess/leave/submit", emp,
               {"start_date": "2026-10-01", "end_date": "2026-10-02", "hours": 16})["request_id"]
    decision = call("POST", "/mss/approvals/action", mgr,
                    {"request_id": rid, "approved": False, "comments": "coverage"})
    assert decision["status"] == "REJECTED", f"expected REJECTED, got {decision}"


def wf_compensation():
    """HRBP reads real decrypted compensation for a seeded employee."""
    hrbp = login("hrbp")
    comp = call("GET", "/hr/comp/EMP-001", hrbp)
    assert comp["base_salary"] not in (None, "", "N/A"), f"no decrypted salary: {comp}"


def wf_ingestion():
    """Uploading a document produces a real, retrievable ingestion job."""
    hrbp = login("hrbp")
    before = call("GET", "/ingestion/jobs", hrbp)["total"]
    boundary = "----hiroTestBoundary"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="wf_test.txt"\r\n'
        "Content-Type: text/plain\r\n\r\nworkflow test document\r\n"
        f"--{boundary}--\r\n"
    ).encode()
    req = urllib.request.Request(f"{API}/ingestion/upload", data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("Authorization", f"Bearer {hrbp}")
    with urllib.request.urlopen(req, timeout=45) as r:
        job = json.loads(r.read().decode())
    assert job.get("content_sha256"), "ingestion did not hash the document"
    after = call("GET", "/ingestion/jobs", hrbp)["total"]
    assert after == before + 1, f"job count did not increase ({before} -> {after})"


def wf_analytics_real():
    """Analytics must be derived from the seeded workforce, not constants."""
    mgr = login("manager")
    charts = call("GET", "/advanced-analytics/charts", mgr)
    assert charts["headcount_by_department"], "no headcount series"
    assert sum(d["value"] for d in charts["headcount_by_department"]) > 100, "headcount looks fabricated"
    trend = call("GET", "/hr/performance/team-trend", mgr)
    assert len(trend) > 1, "performance trend has no real series"


def wf_expense_approval():
    """Employee files an expense, manager approves, employee sees APPROVED."""
    emp, mgr = login("employee"), login("manager")
    boundary = "----hiroExpBoundary"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="expense_data"\r\n\r\n'
        '{"amount": 12.5, "category": "Travel", "description": "workflow test"}\r\n'
        f"--{boundary}--\r\n"
    ).encode()
    req = urllib.request.Request(f"{API}/hr/expenses", data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("Authorization", f"Bearer {emp}")
    with urllib.request.urlopen(req, timeout=45) as r:
        eid = json.loads(r.read().decode())["expense"]["expense_id"]

    decision = call("POST", f"/hr/expenses/{eid}/decision", mgr, {"approved": True, "comments": "ok"})
    assert decision["status"] == "APPROVED", f"expected APPROVED, got {decision}"

    mine = call("GET", "/hr/expenses", emp)
    row = next((x for x in mine if x["expense_id"] == eid), None)
    assert row and row["status"] == "APPROVED", f"employee does not see the approval: {row}"


def wf_timesheet_approval():
    """Employee submits a timesheet, it reaches the manager queue, approval sticks."""
    emp, mgr = login("employee"), login("manager")
    pre = call("POST", "/hr/timesheets/pre-check", emp, {"hours": 45})
    assert pre["status"] == "FAIL", "a 45h week should fail the 40h policy pre-check"

    created = call("POST", "/hr/timesheets", emp, {"total_hours": 37, "week_ending": "2026-09-25"})
    tid = created["timesheet_id"]

    pending = call("GET", "/hr/timesheets/pending", mgr)
    assert any(p["request_id"] == tid for p in pending), "timesheet missing from the manager queue"

    decision = call("POST", f"/hr/timesheets/{tid}/decision", mgr, {"approved": True})
    assert decision["status"] == "APPROVED", f"expected APPROVED, got {decision}"


def wf_policy_lifecycle():
    """HRBP drafts, submits, approves, activates and attests a policy."""
    hrbp = login("hrbp")
    pid = "WF-TEST-POLICY"
    version = call("POST", f"/policy/{pid}/versions", hrbp,
                   {"content": {"policy_name": "WF Test", "rules": []}, "changelog": "workflow test"})
    vid = version["version_id"]
    request_id = call("POST", f"/policy/versions/{vid}/submit", hrbp, {"approvers": ["hrbp"]})["request_id"]
    call("POST", f"/policy/approvals/{request_id}", hrbp, {"approved": True, "comments": "ok"})
    call("POST", f"/policy/versions/{vid}/activate", hrbp)

    listed = call("GET", "/policy/list", hrbp)["policies"]
    assert any(p["policy_id"] == pid for p in listed), "policy missing from the list"

    block = call("POST", "/policy/ledger/commit", hrbp, {"policy_id": pid, "version_id": vid})
    assert len(block.get("block_hash", "")) == 64, f"ledger did not return a sha256 hash: {block}"


def wf_rbac():
    """RBAC still denies what it should."""
    emp = login("employee")
    call("GET", "/admin/users", emp, expect=403)
    call("GET", "/advanced-analytics/charts", emp, expect=403)


def main():
    print("HiRo persona workflow tests\n")
    check("employee -> manager leave approval round trip", wf_leave_approval)
    check("leave rejection records REJECTED", wf_leave_rejection)
    check("employee -> manager expense approval round trip", wf_expense_approval)
    check("timesheet pre-check blocks 45h, approval round trip", wf_timesheet_approval)
    check("HRBP policy lifecycle draft -> activate -> ledger", wf_policy_lifecycle)
    check("HRBP reads decrypted compensation", wf_compensation)
    check("document ingestion persists a real job", wf_ingestion)
    check("analytics derive from the real workforce", wf_analytics_real)
    check("RBAC denies cross-role access", wf_rbac)

    print()
    if _failures:
        print(f"{len(_failures)} workflow(s) FAILED: {', '.join(_failures)}")
        return 1
    print("All workflows passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
