# /backend/services/middleware/rate_limit_middleware.py - FIXED
# /backend/services/middleware/rate_limit_middleware.py
"""ASGI Rate Limiting Middleware"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Union # CRITICAL FIX: Ensure imports are correctly placed and separated
import logging
import time 

logger = logging.getLogger("rate.limit")

class RateLimitMiddleware(BaseHTTPMiddleware):
    RATE_LIMIT_HEADERS = {
        "Retry-After": "60",
        "X-RateLimit-Limit": "60",
        "X-RateLimit-Remaining": "0"
    }
    
    def __init__(self, app, requests_per_minute: int = 60, max_body_size: int = 10_000_000):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.max_body_size = max_body_size
        # CRITICAL FIX: Use floats (timestamps) for better performance and consistency
        self.request_counts: Dict[str, List[float]] = defaultdict(list) 

    def _get_client_identifier(self, request: Request) -> str:
        # FIX: Prioritize proxies (X-Forwarded-For, X-Real-IP) for accurate client identification in Docker/K8s
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
            
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
            
        # Fallback to direct client host
        return request.client.host if request.client else "unknown_ip"

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