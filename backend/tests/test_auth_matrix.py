"""Security matrix: every auth-guarded API route must reject an unauthenticated
request before its handler runs.

The route list is built by introspecting the live app for routes whose dependency
tree includes one of the auth/role dependencies, so this test automatically covers
new endpoints as they are added. A guarded route must answer an anonymous request
with 401/403 (auth rejected) or 422 (request rejected at validation) -- never 200
(handler executed for an anonymous caller) and never 5xx (handler crashed).
"""
import re
import pytest
from fastapi.routing import APIRoute

from server import app

AUTH_DEPENDENCY_NAMES = {
    "get_auth_payload",
    "policy_admin_role_required",
    "hrit_admin_role_required",
    "manager_role_required",
    "employee_role_required",
    "hrbp_role_required",
    "admin_role_required",
}


def _dependency_names(dependant):
    names = set()
    call = getattr(dependant, "call", None)
    if call is not None and getattr(call, "__name__", None):
        names.add(call.__name__)
    for sub in dependant.dependencies:
        names |= _dependency_names(sub)
    return names


def _guarded_routes():
    seen = set()
    out = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if not (_dependency_names(route.dependant) & AUTH_DEPENDENCY_NAMES):
            continue
        for method in sorted(route.methods or set()):
            if method in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                key = (method, route.path)
                if key not in seen:
                    seen.add(key)
                    out.append(key)
    return out


GUARDED_ROUTES = _guarded_routes()


def test_guarded_route_list_is_substantial():
    # Guard against the introspection silently matching nothing.
    assert len(GUARDED_ROUTES) > 100


@pytest.mark.parametrize("method,path", GUARDED_ROUTES, ids=[f"{m} {p}" for m, p in GUARDED_ROUTES])
def test_guarded_route_rejects_anonymous(client, method, path):
    url = re.sub(r"\{[^}]+\}", "test", path)
    resp = client.request(method, url, json={} if method in ("POST", "PUT", "PATCH") else None)
    assert resp.status_code in (401, 403, 422), (
        f"{method} {url} returned {resp.status_code} for an unauthenticated caller"
    )
    # The handler must not have executed, and must not have crashed.
    assert resp.status_code != 200
    assert resp.status_code < 500
