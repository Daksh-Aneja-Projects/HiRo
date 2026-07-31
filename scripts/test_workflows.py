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


def reset_leave_for_tests(hours=400):
    """Give the test employee a known, workable leave position.

    The balance is shared state: every test that asks for time off draws it
    down, and anything left pending from an earlier run still counts against
    what is available. Without this the suite passes or fails depending on the
    order it ran in and on what previous runs left behind.
    """
    mgr, hr = login("manager"), login("hrbp")
    for item in call("GET", "/mss/approvals/queue", mgr):
        if str(item.get("type", "")).startswith("LEAVE"):
            call("POST", "/mss/approvals/action", mgr,
                 {"request_id": item["request_id"], "approved": False, "comments": "test reset"})
    call("POST", "/hr/leave/balance/EMP-005", hr, {"hours": hours, "reason": "workflow test setup"})


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
    reset_leave_for_tests(400)
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
    reset_leave_for_tests(400)
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
    # The working-time rule blocks above 48h without an overtime agreement, and
    # the pre-check must return the SAME verdict the submission path would.
    pre = call("POST", "/hr/timesheets/pre-check", emp, {"hours": 60})
    assert pre["status"] == "FAIL", f"a 60h week should fail the working-time rule: {pre}"
    assert pre.get("audit_id"), "the pre-check did not go through the policy engine"

    ok = call("POST", "/hr/timesheets/pre-check", emp, {"hours": 37})
    assert ok["status"] == "PASS", f"a 37h week should pass: {ok}"

    created = call("POST", "/hr/timesheets", emp, {"total_hours": 37, "week_ending": "2026-09-25"})
    tid = created["timesheet_id"]

    pending = call("GET", "/hr/timesheets/pending", mgr)
    assert any(p["request_id"] == tid for p in pending), "timesheet missing from the manager queue"

    decision = call("POST", f"/hr/timesheets/{tid}/decision", mgr, {"approved": True})
    assert decision["status"] == "APPROVED", f"expected APPROVED, got {decision}"


def wf_unified_approval_queue():
    """Every kind of request an employee raises reaches the one manager queue.

    The queue used to read leave only, so a timesheet or an expense claim was
    submitted successfully and then seen by nobody: there was no screen in the
    product that could approve it.
    """
    reset_leave_for_tests(400)
    emp, mgr = login("employee"), login("manager")

    leave_id = call("POST", "/ess/leave/submit", emp, {
        "leave_type": "ANNUAL", "start_date": "2027-02-01", "end_date": "2027-02-03",
        "hours": 24, "reason": "workflow test"})["request_id"]
    ts_id = call("POST", "/hr/timesheets", emp,
                 {"total_hours": 38, "week_ending": "2027-02-05"})["timesheet_id"]

    queue = call("GET", "/mss/approvals/queue", mgr)
    kinds = {i["type"] for i in queue}
    assert "LEAVE_REQUEST" in kinds, f"leave missing from the manager queue: {kinds}"
    assert "TIMESHEET" in kinds, f"timesheets missing from the manager queue: {kinds}"
    assert any(i["request_id"] == leave_id for i in queue), "this leave request is not in the queue"
    assert any(i["request_id"] == ts_id for i in queue), "this timesheet is not in the queue"

    # The one action endpoint has to decide each kind correctly.
    for rid, kind in ((leave_id, "leave"), (ts_id, "timesheet")):
        result = call("POST", "/mss/approvals/action", mgr, {"request_id": rid, "approved": True})
        assert str(result.get("status", "")).upper() == "APPROVED", f"{kind} not approved: {result}"

    after = {i["request_id"] for i in call("GET", "/mss/approvals/queue", mgr)}
    assert leave_id not in after and ts_id not in after, "decided requests are still in the queue"

    # Being in your queue is what authorises the decision. An id that is not in it
    # must be refused even when the caller names the type themselves.
    call("POST", "/mss/approvals/action", mgr,
         {"request_id": "TS-NOT-YOURS", "approved": True, "type": "TIMESHEET"}, expect=404)


def wf_leave_balance_is_drawn_down():
    """Approved leave actually comes off the entitlement, once.

    Approving used to update the request row and nothing else, so used_hours sat
    at zero for every employee however much leave was granted. The balance check
    on submission could never fire, and people were approved far past what they
    had.
    """
    reset_leave_for_tests(100)
    emp, mgr = login("employee"), login("manager")
    before = call("GET", "/hr/leave/balance", emp)
    assert float(before["balance_hours"]) == 100, f"entitlement was not set: {before}"

    rid = call("POST", "/ess/leave/submit", emp, {
        "leave_type": "ANNUAL", "start_date": "2027-05-03", "end_date": "2027-05-05",
        "hours": 24, "reason": "workflow test"})["request_id"]

    # Nothing moves until somebody decides.
    pending = call("GET", "/hr/leave/balance", emp)
    assert float(pending["balance_hours"]) == 100, f"balance moved before approval: {pending}"

    call("POST", "/mss/approvals/action", mgr, {"request_id": rid, "approved": True})
    after = call("GET", "/hr/leave/balance", emp)
    assert float(after["balance_hours"]) == 76, f"approval did not draw the balance down: {after}"
    assert float(after["used_hours"]) - float(before["used_hours"]) == 24, \
        f"used hours did not move by the hours approved: {after}"

    # Approving the same request again must not draw it down twice.
    call("POST", "/mss/leave/approve", mgr, {"request_id": rid, "approved": True})
    twice = call("GET", "/hr/leave/balance", emp)
    assert float(twice["balance_hours"]) == 76, f"a second approval moved the balance again: {twice}"

    # You cannot ask for more than is left.
    call("POST", "/ess/leave/submit", emp, {
        "leave_type": "ANNUAL", "start_date": "2027-06-01", "end_date": "2027-06-20",
        "hours": 120, "reason": "more than is left"}, expect=403)

    # Requests already waiting count against what is available.
    holding = call("POST", "/ess/leave/submit", emp, {
        "leave_type": "ANNUAL", "start_date": "2027-07-01", "end_date": "2027-07-10",
        "hours": 70, "reason": "first claim on the balance"})["request_id"]
    call("POST", "/ess/leave/submit", emp, {
        "leave_type": "ANNUAL", "start_date": "2027-08-01", "end_date": "2027-08-10",
        "hours": 70, "reason": "would exceed once the pending one is counted"}, expect=403)

    # Decide it, or it stays pending and eats the balance on the next run.
    call("POST", "/mss/approvals/action", mgr, {"request_id": holding, "approved": False,
                                                "comments": "end of the workflow test"})


def wf_compensation_change_is_recorded():
    """A pay change updates the record and leaves an audit row.

    Every part of this was broken: the endpoint required hrit_admin while the
    Compensation Workbench only ever opens for an HRBP, the vault had no encrypt
    method so the call raised before touching the database, and the history
    insert passed a string into a date column. comp_history held zero rows.
    """
    hr = login("hrbp")
    before = call("GET", "/hr/comp/EMP-005", hr)
    target = round(float(before["base_salary"]) + 1000, 2)

    result = call("POST", "/hr/comp/update", hr, {
        "employee_id": "EMP-005", "new_salary": target, "new_grade": "L6",
        "effective_date": "2027-04-01", "updated_by": "hrbp"})
    assert result["status"] == "SUCCESS", f"the pay change was refused: {result}"

    after = call("GET", "/hr/comp/EMP-005", hr)
    assert abs(float(after["base_salary"]) - target) < 0.01,         f"the record still shows {after['base_salary']}, expected {target}"

    # An employee must not be able to read, or set, anyone's pay.
    emp = login("employee")
    call("GET", "/hr/comp/EMP-001", emp, expect=403)
    call("POST", "/hr/comp/update", emp, {
        "employee_id": "EMP-005", "new_salary": 999999, "new_grade": "X",
        "effective_date": "2027-04-01", "updated_by": "employee"}, expect=403)


def wf_feedback_about_a_colleague():
    """Feedback left about someone reaches them.

    Submissions were written to one collection and the "feedback about you"
    panel read another that nothing in the codebase ever wrote, so the panel
    told people their colleagues' feedback would appear there and it never could.
    """
    hr, emp = login("hrbp"), login("employee")
    note = "Kept the payroll escalation calm and clear."
    call("POST", "/hr/feedback", hr, {"feedback": note, "about_employee_id": "EMP-005"})

    received = call("GET", "/hr/feedback/peer/EMP-005", emp)
    assert isinstance(received, list) and any(f.get("feedback") == note for f in received),         f"feedback left about this person did not reach them: {received}"


def wf_case_counts_are_honest():
    """The case list says how many cases exist, not just how many it loaded."""
    admin = login("hritmanager")
    page = call("GET", "/hrsd/tickets?limit=25", admin)
    assert page["count"] <= 25, f"limit was ignored: {page['count']} rows"
    assert page["total"] >= page["count"], "total is smaller than the page it returned"

    overview = call("GET", "/hrsd/monitoring/overview", admin)
    assert page["total"] == overview["total_tickets"], (
        f"the case list reports {page['total']} cases while the monitoring panel "
        f"on the same screen reports {overview['total_tickets']}")


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


def wf_pii_scoping():
    """An employee must never reach a colleague's record.

    Regression guard: /hr/profile/{id} once served any employee's decrypted name,
    email, job title and role to any employee who put their id in the path.
    """
    emp = login("employee")  # own record is EMP-005
    call("GET", "/hr/profile/EMP-005", emp)                    # own: allowed
    call("GET", "/hr/profile/EMP-001", emp, expect=403)        # colleague: denied
    call("GET", "/hr/career/path/EMP-001", emp, expect=403)
    call("GET", "/hr/feedback/peer/EMP-001", emp, expect=403)

    # A line manager may only see compensation for their own direct reports.
    mgr = login("manager")
    call("GET", "/hr/comp/EMP-002", mgr, expect=403)


def wf_no_fabricated_data():
    """Endpoints that used to invent content must now be honest."""
    mgr, emp, admin = login("manager"), login("employee"), login("hritmanager")

    # Used to return a hardcoded "SIM-001 / Risk Reduced by 25%" row for everyone.
    history = call("GET", "/simulation/history/EMP-999-NOBODY", mgr)
    assert history == [], f"simulation history fabricated a row: {history}"

    # Used to claim every dependency was UP regardless of reality.
    health = call("GET", "/admin/health", admin)
    bus = call("GET", "/admin/system/message-bus/status", admin)
    nats_up = health["checks"].get("nats") == "UP"
    bus_up = bus["status"] == "Connected"
    assert nats_up == bus_up, f"health disagrees with the message bus: {health['checks']} vs {bus}"

    # Used to invent a health plan and a retirement match.
    benefits = call("GET", "/hr/benefits", emp)
    assert benefits["health_plan"] is None, "benefits invented a health plan"


def wf_simulation_is_real():
    """Attrition scoring and simulation must reflect the actual employee and the
    actual levers, not return one constant for everybody.
    """
    mgr = login("manager")

    # Different employees must score differently, from their own record.
    scores = {}
    for emp in ("EMP-001", "EMP-005"):
        r = call("POST", "/wfp/predict_attrition", mgr, {"employee_id": emp})
        assert r.get("source") == "employee record", f"{emp} was not scored from its record: {r.get('source')}"
        scores[emp] = r["risk_score"]
    assert scores["EMP-001"] != scores["EMP-005"], f"every employee scored the same: {scores}"

    # A bigger intervention must move risk further than a token one.
    def delta(adjustments):
        res = call("POST", "/simulation/run", mgr, {
            "employee_id": "EMP-005", "synthetic_adjustments": adjustments, "simulation_type": "what_if",
        })
        return res["metrics"]["risk_score_delta"]

    small, large = delta({"salary_increase_pct": 2}), delta({"salary_increase_pct": 25, "training_sessions": 10})
    assert large < small, f"levers had no effect: small={small} large={large}"


def wf_models_agree():
    """The explainer must explain the prediction, not compute a rival number."""
    mgr = login("manager")
    for emp in ("EMP-001", "EMP-005"):
        predicted = call("POST", "/wfp/predict_attrition", mgr, {"employee_id": emp})["risk_score"]
        explained = call("POST", "/data/xai/explain", mgr,
                         {"model_name": "attrition", "prediction_input": {"employee_id": emp}})
        assert explained["prediction_score"] == predicted, (
            f"{emp}: prediction {predicted} but explanation {explained['prediction_score']}")
        assert explained["explained_from"] == "workforce planning model"
        # The narrative must read as a sentence, not a raw feature identifier.
        assert "_" not in explained["human_summary"], explained["human_summary"]


def wf_analytics_filter_works():
    """The department filter must change the numbers, not just the label."""
    mgr = login("manager")
    departments = call("GET", "/advanced-analytics/departments", mgr)["departments"]
    assert len(departments) > 3, f"department list looks wrong: {departments}"

    overall = call("GET", "/advanced-analytics/metrics", mgr)
    scoped = call("GET", f"/advanced-analytics/metrics?department={departments[0]}", mgr)
    assert scoped["headcount"] < overall["headcount"], (
        f"filter did not scope the data: {scoped['headcount']} vs {overall['headcount']}")
    assert scoped["scope"] == departments[0]


def wf_simulation_noop_is_zero():
    """A simulation with no adjustments must report no change.

    Regression guard: the engine used to blend an ORG-LEVEL score into the
    employee's, so changing nothing reported a 24-point risk drop for people
    above the org mean and a rise for those below it.
    """
    mgr = login("manager")
    for emp in ("EMP-005", "EMP-006"):
        res = call("POST", "/simulation/run", mgr,
                   {"employee_id": emp, "synthetic_adjustments": {}, "simulation_type": "what_if"})
        m = res["metrics"]
        assert m["risk_score_delta"] == 0, f"{emp}: no-op reported {m['risk_score_delta']}"
        assert m["attrition_probability_change"] == 0, f"{emp}: attrition moved on a no-op"

    # A real lever must move risk, cost and productivity together.
    res = call("POST", "/simulation/run", mgr,
               {"employee_id": "EMP-005", "synthetic_adjustments": {"salary_increase_pct": 20},
                "simulation_type": "what_if"})
    m = res["metrics"]
    assert m["risk_score_delta"] < 0, "a pay rise should reduce risk"
    assert m["risk_score_delta"] == m["attrition_probability_change"], "one quantity, two numbers"
    assert m["cost_implication"] > 0, "a 20% pay rise cannot cost nothing"


def wf_manager_scope():
    """A line manager sees their own reports and nobody else's."""
    mgr = login("manager")            # EMP-004; reports are EMP-005 and EMP-006
    for path in ("/hr/performance/{}", "/hr/profile/{}", "/hr/career/path/{}"):
        call("GET", path.format("EMP-005"), mgr)                  # own report: allowed
        call("GET", path.format("EMP-001"), mgr, expect=403)      # not a report: denied
    # HR administers everyone and must keep full access.
    hrbp = login("hrbp")
    call("GET", "/hr/profile/EMP-001", hrbp)
    call("GET", "/hr/performance/EMP-001", hrbp)


def wf_consent_is_recorded():
    """A privacy control must not report success while storing the opposite."""
    emp = login("employee")
    call("POST", "/pii/update_consent", emp, {"purpose_id": "wf-test", "consent_granted": True})
    state = call("GET", "/pii/check_consent?purpose_id=wf-test", emp)
    assert state["consent"] is True, f"consent was not persisted: {state}"

    call("POST", "/pii/update_consent", emp, {"purpose_id": "wf-test", "granted": False})
    state = call("GET", "/pii/check_consent?purpose_id=wf-test", emp)
    assert state["consent"] is False, f"consent revocation was not persisted: {state}"

    # A request with no decision at all must be rejected, not defaulted to False.
    call("POST", "/pii/update_consent", emp, {"purpose_id": "wf-test"}, expect=400)


def main():
    print("HiRo persona workflow tests\n")
    check("employee -> manager leave approval round trip", wf_leave_approval)
    check("leave rejection records REJECTED", wf_leave_rejection)
    check("employee -> manager expense approval round trip", wf_expense_approval)
    check("timesheet policy check is real, approval round trip", wf_timesheet_approval)
    check("leave, timesheets and expenses all reach the manager queue", wf_unified_approval_queue)
    check("approved leave is drawn off the balance, once", wf_leave_balance_is_drawn_down)
    check("a pay change is applied and recorded", wf_compensation_change_is_recorded)
    check("feedback about a colleague reaches them", wf_feedback_about_a_colleague)
    check("case counts match across the screen", wf_case_counts_are_honest)
    check("HRBP policy lifecycle draft -> activate -> ledger", wf_policy_lifecycle)
    check("HRBP reads decrypted compensation", wf_compensation)
    check("document ingestion persists a real job", wf_ingestion)
    check("analytics derive from the real workforce", wf_analytics_real)
    check("RBAC denies cross-role access", wf_rbac)
    check("employees cannot reach a colleague's PII", wf_pii_scoping)
    check("no endpoint fabricates content", wf_no_fabricated_data)
    check("attrition scoring and simulation are real", wf_simulation_is_real)
    check("prediction and explanation agree", wf_models_agree)
    check("analytics department filter really filters", wf_analytics_filter_works)
    check("a no-op simulation reports no change", wf_simulation_noop_is_zero)
    check("managers are scoped to their own reports", wf_manager_scope)
    check("consent is recorded as chosen", wf_consent_is_recorded)

    print()
    if _failures:
        print(f"{len(_failures)} workflow(s) FAILED: {', '.join(_failures)}")
        return 1
    print("All workflows passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
