"""Route smoke test: logs in as each role and checks every portal route/sub-module
for crashes and failed API calls. Requires the backend on :8100.

Usage:  python scripts/smoke_routes.py
"""
import json
import sys
import urllib.error
import urllib.request

API = "http://localhost:8100/api"

ROLE_ROUTES = {
    "employee": [
        "/dashboard", "/employee-portal?module=dashboard", "/employee-portal?module=leave",
        "/employee-portal?module=pii", "/social-feed", "/user-profile",
    ],
    "manager": [
        "/dashboard", "/manager-portal?module=team", "/manager-portal?module=overview",
        "/manager-portal?module=risk", "/social-feed", "/user-profile",
    ],
    "hrbp": [
        "/dashboard", "/hr-portal?module=policy", "/hr-portal?module=comp",
        "/hr-portal?module=talent", "/hr-portal?module=ingestion", "/hr-portal?module=cases",
        "/advanced-analytics", "/social-feed",
    ],
    "hritmanager": [
        "/dashboard", "/hrit-portal?module=agent", "/hrit-portal?module=governance",
        "/hrit-portal?module=health", "/admin-portal", "/ultimate-orchestrator?module=command",
        "/ultimate-orchestrator?module=danger", "/advanced-analytics",
    ],
}

# Endpoints each persona's screens actually call.
ROLE_ENDPOINTS = {
    "employee": [
        "/ess/dashboard/self", "/hr/leave/balance", "/hr/leave/requests", "/hr/timesheets",
        "/hr/profile/skills", "/hr/payslips", "/hr/benefits", "/social/feed",
        "/recognition/leaderboard", "/talent-exp/learning-modules", "/innovation/ideas",
    ],
    "manager": [
        "/mss/team/roster", "/mss/approvals/queue", "/wfp/projections",
        "/advanced-analytics/charts", "/hr/performance/team-trend",
        "/telemetry/metrics/live", "/orchestrator/dashboard",
    ],
    "hrbp": [
        "/compliance/dashboard", "/hrsd/tickets", "/hrsd/monitoring/overview",
        "/advanced-analytics/metrics", "/advanced-analytics/charts", "/dao/dashboard",
        "/dao/proposals/active",
    ],
    "hritmanager": [
        "/admin/dashboard", "/admin/users", "/admin/announcement", "/admin/health",
        "/ai/models", "/ai/provider/config", "/telemetry/agents/activity",
        "/admin/system/message-bus/status", "/command/history",
    ],
}


def login(username: str) -> str:
    body = json.dumps({"username": username, "password": username}).encode()
    req = urllib.request.Request(
        f"{API}/auth/login", data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)["access_token"]


def check(token: str, path: str):
    req = urllib.request.Request(f"{API}{path}", headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            payload = r.read(400).decode("utf-8", "replace")
            return r.status, payload
    except urllib.error.HTTPError as e:
        return e.code, e.read(200).decode("utf-8", "replace")
    except Exception as e:  # connection refused, timeout, ...
        return 0, str(e)


def main() -> int:
    failures = []
    for role, endpoints in ROLE_ENDPOINTS.items():
        try:
            token = login(role)
        except Exception as e:
            print(f"[{role}] LOGIN FAILED: {e}")
            failures.append((role, "login", 0))
            continue
        print(f"\n=== {role} ===")
        for ep in endpoints:
            status, body = check(token, ep)
            ok = status == 200
            # A 403 is a correct answer when the role genuinely lacks access.
            marker = "ok " if ok else ("403" if status == 403 else "FAIL")
            print(f"  {marker} {status:<4} {ep}")
            if not ok and status != 403:
                failures.append((role, ep, status))

    print("\n--- routes to verify in a browser ---")
    for role, routes in ROLE_ROUTES.items():
        print(f"  {role}: {len(routes)} routes")

    if failures:
        print(f"\n{len(failures)} FAILING endpoint(s):")
        for role, ep, status in failures:
            print(f"  [{role}] {status} {ep}")
        return 1
    print("\nAll endpoints healthy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
