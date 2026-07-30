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


def wf_rbac():
    """RBAC still denies what it should."""
    emp = login("employee")
    call("GET", "/admin/users", emp, expect=403)
    call("GET", "/advanced-analytics/charts", emp, expect=403)


def main():
    print("HiRo persona workflow tests\n")
    check("employee -> manager leave approval round trip", wf_leave_approval)
    check("leave rejection records REJECTED", wf_leave_rejection)
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
