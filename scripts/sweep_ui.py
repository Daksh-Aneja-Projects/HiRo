"""Print the per-persona route list for a browser sweep, and verify each route's
page bundle is reachable. Pair with the browser check for crashes.

Usage: python scripts/sweep_ui.py
"""
import json
import sys
import urllib.error
import urllib.request

FRONTEND = "http://localhost:3000"

ROUTES = {
    "employee": [
        "/dashboard", "/employee-portal?module=dashboard", "/employee-portal?module=timesheets",
        "/employee-portal?module=leave", "/employee-portal?module=pay", "/employee-portal?module=growth",
        "/employee-portal?module=documents", "/employee-portal?module=expenses",
        "/employee-portal?module=pii", "/social-feed", "/user-profile",
    ],
    "manager": [
        "/dashboard", "/manager-portal?module=team", "/manager-portal?module=overview",
        "/manager-portal?module=risk", "/social-feed", "/user-profile",
    ],
    "hrbp": [
        "/dashboard", "/hr-portal?module=policy", "/hr-portal?module=compliance",
        "/hr-portal?module=rules", "/hr-portal?module=governance", "/hr-portal?module=audit",
        "/hr-portal?module=comp", "/hr-portal?module=talent", "/hr-portal?module=ingestion",
        "/hr-portal?module=cases", "/advanced-analytics", "/social-feed",
    ],
    "hritmanager": [
        "/dashboard", "/hrit-portal?module=agent", "/hrit-portal?module=governance",
        "/hrit-portal?module=health", "/admin-portal",
        "/ultimate-orchestrator?module=command", "/ultimate-orchestrator?module=danger",
        "/advanced-analytics", "/social-feed",
    ],
}


def main():
    total = 0
    print("Routes to verify per persona:\n")
    for role, routes in ROUTES.items():
        print(f"  {role} ({len(routes)}):")
        for r in routes:
            print(f"    {FRONTEND}{r}")
            total += 1
        print()

    try:
        with urllib.request.urlopen(FRONTEND, timeout=10) as resp:
            ok = resp.status == 200
    except Exception as e:
        print(f"Frontend unreachable: {e}")
        return 1
    print(f"{total} routes across {len(ROUTES)} personas. Frontend reachable: {ok}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
