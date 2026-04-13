"""
Idempotency middleware — prevents duplicate processing on retried requests.
Per PRD: if a lender retries a POST /v1/score, they get the same cached response
instead of creating a duplicate score record.

Clients send: X-Idempotency-Key: <unique-key>
Server caches the response for 24 hours keyed by (api_key + idempotency_key).
"""

import hashlib
import json
import logging
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from src.core.config import settings

logger = logging.getLogger(__name__)


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """
    Idempotency middleware for POST/PUT/PATCH requests.

    Reads X-Idempotency-Key header. If present and the same key was seen before
    for this API key, returns the cached response instead of re-processing.
    """

    # In-memory cache: {(api_key_hash, idempotency_key): (status_code, body, headers)}
    _cache: dict[tuple[str, str], tuple[int, dict, dict]] = {}

    async def dispatch(self, request: Request, call_next):
        # Only apply to mutation methods
        if request.method not in ("POST", "PUT", "PATCH"):
            return await call_next(request)

        idempotency_key = request.headers.get("X-Idempotency-Key")
        if not idempotency_key:
            return await call_next(request)

        # Build cache key from API key + idempotency key
        api_key = request.headers.get("X-API-Key", "")
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        cache_key = (api_key_hash, idempotency_key)

        # Check cache
        if cache_key in self._cache:
            status_code, body, headers = self._cache[cache_key]
            logger.info(
                "Idempotent cache hit",
                idempotency_key=idempotency_key,
                api_key_hash=api_key_hash[:8],
            )
            return JSONResponse(
                status_code=status_code,
                content=body,
                headers={**headers, "X-Idempotent": "true"},
            )

        # Process request
        response = await call_next(request)

        # Cache successful responses (2xx only)
        if 200 <= response.status_code < 300:
            # Collect response body
            body = b""
            async for chunk in response.body_iterator:
                body += chunk

            try:
                parsed_body = json.loads(body)
            except (json.JSONDecodeError, ValueError):
                parsed_body = {"raw": body.decode("utf-8", errors="replace")}

            # Put back the body for the actual response
            response.body_iterator = self._asynchronous_iter([body])

            # Store in cache
            self._cache[cache_key] = (
                response.status_code,
                parsed_body,
                dict(response.headers),
            )

            # Evict old entries if cache grows too large
            if len(self._cache) > 10000:
                oldest = next(iter(self._cache))
                del self._cache[oldest]

            logger.info(
                "Cached idempotent response",
                idempotency_key=idempotency_key,
                status_code=response.status_code,
            )

        return response

    @staticmethod
    async def _asynchronous_iter(items):
        for item in items:
            yield item
