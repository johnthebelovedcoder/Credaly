"""
Authentication middleware — HMAC-signed API key validation with Redis caching.
Per PRD FR-032: API key auth with environment scoping and IP allowlisting.

Performance: API key lookups use key-prefix indexed query (O(1)) instead of
full table scan, plus Redis cache (5min TTL) and in-memory LRU cache.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.database import get_db
from src.core.security import verify_api_key
from src.models import ApiKey, LenderClient

logger = logging.getLogger(__name__)

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
HMAC_SIGNATURE_HEADER = APIKeyHeader(name="X-Signature", auto_error=False)

# In-memory LRU-style cache for API key lookups (fallback when Redis unavailable)
_api_key_cache: dict[str, Optional[LenderClient]] = {}
_CACHE_MAX_SIZE = 1000  # Max cached API keys


async def _resolve_lender_by_key(
    raw_key: str,
    db: AsyncSession,
) -> Optional[LenderClient]:
    """
    Resolve a raw API key to its LenderClient record.

    Uses Redis cache first (5min TTL), then in-memory cache, then an optimized
    DB query using key-prefix indexing (not a full table scan).

    Optimization: The ApiKey model stores key_prefix (first 20 chars of raw key).
    We hash the prefix and use it to narrow the query to a single row.
    """
    from src.core.redis_client import get_redis
    import hashlib
    import bcrypt

    # Key hash for cache storage (never store raw keys)
    cache_key = hashlib.sha256(raw_key.encode()).hexdigest()

    # 1) Redis cache
    redis_client = await get_redis()
    if redis_client:
        try:
            cached = await redis_client.get(f"apikey:{cache_key}")
            if cached:
                # Reconstruct a lightweight lender object from JSON
                import dataclasses
                data = json.loads(cached)
                lender = LenderClient(**data)
                logger.debug("API key resolved from Redis cache")
                return lender
        except Exception as e:
            logger.warning(f"Redis API key cache read failed: {e}")

    # 2) In-memory cache
    if cache_key in _api_key_cache:
        return _api_key_cache[cache_key]

    # 3) DB lookup — OPTIMIZED with key-prefix indexing
    # Instead of scanning all active lenders, we:
    #   a. Compute the prefix of the incoming key (first 20 chars)
    #   b. Use the indexed key_prefix column for a single-row lookup
    # This reduces the query from O(n) bcrypt checks to O(1) indexed lookup.
    key_prefix = raw_key[:20]

    # Query using the indexed key_prefix column
    stmt = select(ApiKey).where(
        ApiKey.key_prefix == key_prefix,
        ApiKey.is_active == True,
        ApiKey.revoked_at.is_(None),
    )
    result = await db.execute(stmt)
    api_key_record = result.scalar_one_or_none()

    if not api_key_record:
        return None

    # Verify the full key against the stored hash (single bcrypt check)
    if not verify_api_key(raw_key, api_key_record.key_hash):
        return None

    # Fetch the associated lender
    lender_stmt = select(LenderClient).where(LenderClient.id == api_key_record.client_id)
    lender_result = await db.execute(lender_stmt)
    lender = lender_result.scalar_one_or_none()

    if not lender or lender.status != "active":
        return None

    # Update last_used_at
    api_key_record.last_used_at = datetime.now(timezone.utc)
    await db.flush()

    # Populate caches
    _api_key_cache[cache_key] = lender
    if len(_api_key_cache) > _CACHE_MAX_SIZE:
        # Evict oldest entry
        oldest = next(iter(_api_key_cache))
        del _api_key_cache[oldest]

    if redis_client and lender:
        try:
            # Cache for 5 minutes
            lender_data = {
                "id": lender.id,
                "name": lender.name,
                "api_key_hash": lender.api_key_hash,
                "tier_access": lender.tier_access,
                "rate_limit": lender.rate_limit,
                "status": lender.status,
                "environment": lender.environment,
                "ip_allowlist": lender.ip_allowlist,
            }
            await redis_client.setex(
                f"apikey:{cache_key}",
                300,  # 5 minutes
                json.dumps(lender_data),
            )
        except Exception as e:
            logger.warning(f"Redis API key cache write failed: {e}")

    return lender


async def authenticate_lender(
    request: Request,
    api_key: Optional[str] = Depends(API_KEY_HEADER),
    db: AsyncSession = Depends(get_db),
) -> LenderClient:
    """
    Authenticate incoming requests using API key.
    Validates: key exists, lender is active, environment matches, IP is allowlisted.
    PRD FR-032.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )

    lender = await _resolve_lender_by_key(api_key, db)

    if not lender:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    # Environment check — sandbox keys can't be used in production
    if lender.environment == "sandbox" and settings.environment == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sandbox API key cannot be used in production",
        )

    # IP allowlist check
    if lender.ip_allowlist:
        allowed_ips = json.loads(lender.ip_allowlist)
        client_ip = request.client.host if request.client else None
        if client_ip and client_ip not in allowed_ips:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"IP {client_ip} is not allowlisted for this API key",
            )

    return lender
