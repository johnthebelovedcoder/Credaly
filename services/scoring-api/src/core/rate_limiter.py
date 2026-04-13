"""
Rate Limiting — per-API-key sliding window rate limiter.
Per PRD FR-034: configurable per client (default 100 req/min).

Two-layer approach:
  1. Middleware enforces a global default rate limit on all requests (fast path)
  2. Per-client limits are enforced after auth via the `check_rate_limit` dependency
"""

import time
import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, status

from src.core.config import settings
from src.schemas import ErrorResponse

logger = logging.getLogger(__name__)


class _InMemoryRateLimiter:
    """
    Sliding window rate limiter backed by Redis (or in-memory fallback).
    Key format: ratelimit:{identifier}:{minute_bucket}
    """

    def __init__(self):
        # In-memory fallback: {identifier: {minute_bucket: count}}
        self._store: dict[str, dict[int, int]] = {}

    async def is_allowed(
        self,
        identifier: str,
        limit: int = 100,
        window_seconds: int = 60,
    ) -> tuple[bool, int]:
        """
        Check if the request is within the rate limit.
        Returns (allowed, remaining_requests).
        """
        bucket = int(time.time()) // window_seconds

        # Try Redis first
        from src.core.redis_client import get_redis
        redis_client = await get_redis()
        if redis_client:
            try:
                key = f"ratelimit:{identifier}:{bucket}"
                pipe = redis_client.pipeline()
                pipe.incr(key)
                pipe.expire(key, window_seconds * 2)
                results = await pipe.execute()
                current = results[0]
                if current <= limit:
                    return True, limit - current
                return False, 0
            except Exception as e:
                logger.warning(f"Redis rate limit failed, falling back to memory: {e}")

        # In-memory fallback
        if identifier not in self._store:
            self._store[identifier] = {}

        # Clean old buckets
        current_time = int(time.time()) // window_seconds
        self._store[identifier] = {
            k: v for k, v in self._store[identifier].items()
            if k >= current_time - 1
        }

        count = self._store[identifier].get(bucket, 0) + 1
        self._store[identifier][bucket] = count

        if count <= limit:
            return True, limit - count
        return False, 0

    def cleanup(self):
        """Periodically clean stale entries from in-memory store."""
        current_time = int(time.time()) // 60
        stale_keys = []
        for key, buckets in self._store.items():
            if max(buckets.keys()) < current_time - 5:
                stale_keys.append(key)
        for key in stale_keys:
            del self._store[key]


# Singleton
rate_limiter = _InMemoryRateLimiter()


class RateLimitMiddleware:
    """
    FastAPI middleware that enforces a default global rate limit.
    Per-client limits are enforced later via the `check_rate_limit` dependency.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        # Only apply to HTTP requests
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract API key for default rate limiting
        headers = dict(scope.get("headers", []))
        api_key = None
        for key, value in headers.items():
            if key.lower() == b"x-api-key":
                api_key = value.decode()
                break

        # No API key — let the auth middleware handle it, but still rate limit by IP
        if not api_key:
            client_info = scope.get("client")
            client_ip = client_info[0] if client_info else "unknown"
            identifier = f"ip:{client_ip}"
        else:
            import hashlib
            identifier = hashlib.sha256(api_key.encode()).hexdigest()

        # Default global rate limit
        limit = settings.default_rate_limit_per_minute
        allowed, remaining = await rate_limiter.is_allowed(
            identifier=identifier,
            limit=limit,
        )

        if not allowed:
            from fastapi.responses import JSONResponse
            response = JSONResponse(
                status_code=429,
                content=ErrorResponse(
                    code="RATE_LIMITED",
                    message=f"Rate limit exceeded. Maximum {limit} requests per minute.",
                    trace_id="unknown",
                    docs_url="https://docs.platform.com/errors/RATE_LIMITED",
                ).model_dump(),
            )
            await response(scope, receive, send)
            return

        # Attach remaining to request for downstream use
        scope["headers"] = scope["headers"] + [
            (b"x-ratelimit-remaining", str(remaining).encode())
        ]

        await self.app(scope, receive, send)


async def check_per_client_rate_limit(
    request: Request,
    lender = Depends(lambda: None),  # Injected by authenticate_lender
):
    """
    Per-client rate limit check — called after auth in endpoint dependencies.
    Uses the lender's configured rate_limit from the database.
    """
    # This is called from endpoints that have the lender dependency.
    # The actual enforcement happens via the middleware using the lender's
    # rate_limit. We override the default limit for this request.
    if lender and hasattr(lender, "rate_limit") and lender.rate_limit:
        # The middleware already checked with the default limit.
        # We do an additional check with the per-client limit.
        import hashlib
        api_key = request.headers.get("X-API-Key", "")
        identifier = hashlib.sha256(api_key.encode()).hexdigest()
        allowed, remaining = await rate_limiter.is_allowed(
            identifier=identifier,
            limit=lender.rate_limit,
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=ErrorResponse(
                    code="RATE_LIMITED",
                    message=f"Rate limit exceeded. Maximum {lender.rate_limit} requests per minute for this client.",
                    trace_id=getattr(request.state, "trace_id", "unknown"),
                    docs_url="https://docs.platform.com/errors/RATE_LIMITED",
                ).model_dump(),
            )
        request.state.rate_limit_remaining = remaining
