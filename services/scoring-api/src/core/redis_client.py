"""
Redis client — async connection pool for caching, rate limiting, online feature store.
"""

import logging
from typing import Optional

import redis.asyncio as aioredis

from src.core.config import settings

logger = logging.getLogger(__name__)

_redis: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    """Get or create the async Redis connection pool."""
    global _redis
    if _redis is None:
        try:
            _redis = aioredis.from_url(
                settings.redis_url,
                decode_responses=True,
                max_connections=10,
            )
            await _redis.ping()
            logger.info("Redis connection established")
        except Exception:
            logger.warning("Redis unavailable — falling back to no-op cache")
            _redis = None
    return _redis


async def close_redis():
    """Close Redis connection pool."""
    global _redis
    if _redis:
        await _redis.close()
        _redis = None
