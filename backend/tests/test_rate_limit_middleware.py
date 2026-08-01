"""Rate limiting has to bucket per signed-in session, not per IP.

Keying on IP alone means everyone behind one NAT or a header-less ingress shares
a single budget, so one busy person throttles the whole office. And the limit has
to be high enough for real use: a portal screen fires six to ten calls, so a low
figure rate-limits a user against their own app after a handful of screens.
"""
from types import SimpleNamespace

from services.middleware.rate_limit_middleware import RateLimitMiddleware


def _request(token=None, ip="10.0.0.1", forwarded=None):
    headers = {}
    if token:
        headers["authorization"] = f"Bearer {token}"
    if forwarded:
        headers["x-forwarded-for"] = forwarded
    return SimpleNamespace(headers=headers, client=SimpleNamespace(host=ip), method="GET")


def _mw():
    return RateLimitMiddleware(app=None, requests_per_minute=60)


def test_two_sessions_from_one_ip_get_separate_buckets():
    mw = _mw()
    a = mw._get_client_identifier(_request(token="token-alice"))
    b = mw._get_client_identifier(_request(token="token-bob"))
    assert a != b, "two people behind one IP must not share a rate-limit budget"
    assert a.startswith("session:") and b.startswith("session:")


def test_the_same_session_keeps_one_bucket():
    mw = _mw()
    first = mw._get_client_identifier(_request(token="token-alice"))
    second = mw._get_client_identifier(_request(token="token-alice", ip="10.0.0.9"))
    assert first == second, "one session must count as one caller even if its IP moves"


def test_the_raw_token_never_becomes_the_key():
    """The key is stored and logged, so it must not be a usable credential."""
    mw = _mw()
    key = mw._get_client_identifier(_request(token="super-secret-token"))
    assert "super-secret-token" not in key


def test_unauthenticated_traffic_still_buckets_by_ip():
    """Login and health have no token, and that is exactly the traffic an
    IP-based limit is protecting."""
    mw = _mw()
    assert mw._get_client_identifier(_request(ip="10.0.0.1")) == "ip:10.0.0.1"
    assert mw._get_client_identifier(_request(forwarded="203.0.113.7, 10.0.0.1")) == "ip:203.0.113.7"


def test_quiet_buckets_are_swept_so_the_map_cannot_grow_forever():
    mw = _mw()
    now = 10_000.0
    mw.request_counts["session:old"] = [now - 600.0]   # outside the 60s window
    mw.request_counts["session:live"] = [now - 5.0]    # still inside it
    mw.request_counts["session:empty"] = []

    mw._last_sweep = 0.0
    mw._sweep(now)

    assert "session:old" not in mw.request_counts
    assert "session:empty" not in mw.request_counts
    assert "session:live" in mw.request_counts, "an active caller must keep its window"


def test_the_configured_limit_allows_a_real_session():
    """Seven screens at ten calls each inside a minute is ordinary use, not abuse."""
    from config.settings import settings
    assert settings.RATE_LIMIT_PER_MINUTE >= 300, (
        f"RATE_LIMIT_PER_MINUTE is {settings.RATE_LIMIT_PER_MINUTE}, which throttles "
        f"normal portal navigation"
    )
