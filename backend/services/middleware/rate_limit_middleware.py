# /backend/services/middleware/rate_limit_middleware.py - FIXED
# /backend/services/middleware/rate_limit_middleware.py
"""ASGI Rate Limiting Middleware"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Union # CRITICAL FIX: Ensure imports are correctly placed and separated
import hashlib
import logging
import time

logger = logging.getLogger("rate.limit")

class RateLimitMiddleware(BaseHTTPMiddleware):
    # How often to drop buckets that have gone quiet. Buckets are keyed per
    # session, and a long-lived process would otherwise hold one list per token
    # ever seen: a slow leak that only shows up in production.
    _SWEEP_EVERY_SECONDS = 300.0

    def __init__(self, app, requests_per_minute: int = 60, max_body_size: int = 10_000_000):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.max_body_size = max_body_size
        # CRITICAL FIX: Use floats (timestamps) for better performance and consistency
        self.request_counts: Dict[str, List[float]] = defaultdict(list)
        self._last_sweep = 0.0

    def _sweep(self, now_ts: float) -> None:
        """Drop buckets with nothing left in the current window."""
        if now_ts - self._last_sweep < self._SWEEP_EVERY_SECONDS:
            return
        self._last_sweep = now_ts
        cutoff = now_ts - 60.0
        for key in [k for k, v in self.request_counts.items() if not v or v[-1] <= cutoff]:
            del self.request_counts[key]

    def _get_client_identifier(self, request: Request) -> str:
        """Bucket per signed-in session where there is one, per IP otherwise.

        Keying purely on IP means everyone behind a corporate NAT or an ingress
        that does not set a forwarded header shares a single budget, so one busy
        person throttles the whole office. The bearer token identifies the
        session, and hashing it is enough to tell sessions apart: this only picks
        a bucket, it authorises nothing, so the token is never decoded or trusted
        here. Unauthenticated traffic (login, health) still buckets by IP, which
        is what protects the login endpoint from one host.
        """
        auth = request.headers.get("authorization")
        if auth and auth.lower().startswith("bearer "):
            token = auth[7:].strip()
            if token:
                return f"session:{hashlib.sha256(token.encode('utf-8')).hexdigest()[:16]}"

        # FIX: Prioritize proxies (X-Forwarded-For, X-Real-IP) for accurate client identification in Docker/K8s
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return f"ip:{forwarded_for.split(',')[0].strip()}"

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return f"ip:{real_ip.strip()}"

        # Fallback to direct client host
        return f"ip:{request.client.host if request.client else 'unknown_ip'}"

    async def dispatch(self, 
                      request: Request, call_next):
        
        # Body size check
        # FIX: Check only POST/PUT/PATCH requests where body 
        # size matters
        if request.method in ["POST", "PUT", "PATCH"]:
            content_length_str = request.headers.get("content-length")
            if content_length_str:
                try:
                    # CRITICAL FIX: Use the configured max_body_size (already converted to bytes)
                    if int(content_length_str) > self.max_body_size:
                        return JSONResponse({"detail": "Request body too large"}, status_code=413)
                except ValueError:
                    # Ignore if Content-Length header is malformed
                    pass
                    
        # Rate limiting
        client_ip = self._get_client_identifier(request)
        
        # CRITICAL FIX: Use monotonic time for accurate rate 
        # calculation, 
        # independent of system clock changes/timezones.
        # However, for pruning requests based on a real-world time window (60s), 
        # using real timestamp is kept for time window consistency.
        now_ts = datetime.now(timezone.utc).timestamp()
        self._sweep(now_ts)

        # Prune old requests (1 minute window)
        one_minute_ago_ts = now_ts - 60.0
        
        # FIX: Filter list in place for efficiency (reassignment is atomic and fast)
        self.request_counts[client_ip] = [
            req_time for req_time in self.request_counts[client_ip]
            if req_time > one_minute_ago_ts
        ]
        
        if len(self.request_counts[client_ip]) >= self.requests_per_minute:
            # CRITICAL FIX: If rate limiting is enabled, always log the warning
            logger.warning(f"Rate limit exceeded: {client_ip}")
            
            # FIX: Ensure 
            # headers reflect the current state
            remaining = 0
            headers = {
                "Retry-After": "60",
                "X-RateLimit-Limit": str(self.requests_per_minute),
                "X-RateLimit-Remaining": str(remaining)
            }
            return JSONResponse(
                {"detail": "Rate limit exceeded"},
                status_code=429,
                headers=headers
            )
        
        # Record the current request time (timestamp 
        # float)
        self.request_counts[client_ip].append(now_ts)
        
        response = await call_next(request)
        
        # Add headers
        remaining = max(0, self.requests_per_minute - len(self.request_counts[client_ip]))
        response.headers['X-RateLimit-Limit'] = str(self.requests_per_minute)
        # FIX: Corrected the invalid syntax by merging the line
        response.headers['X-RateLimit-Remaining'] = str(remaining)
        
        return response