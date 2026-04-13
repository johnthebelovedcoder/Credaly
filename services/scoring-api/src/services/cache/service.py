"""
Cache Service — Redis-backed score and feature caching.
Per PRD Section 6.1: cached score p95 < 500ms (when score computed < 24h ago).
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from src.core.config import settings

logger = logging.getLogger(__name__)


class CacheService:
    """Redis-backed cache for scores and features."""

    def __init__(self):
        self._ttl = settings.score_cache_ttl_seconds

    async def get_cached_score(self, bvn_hash: str, tier_config: str) -> Optional[Dict[str, Any]]:
        """Get a cached score result. Key: score:{bvn_hash}:{tier_config}."""
        from src.core.redis_client import get_redis
        redis_client = await get_redis()
        if not redis_client:
            return None

        try:
            key = f"score:{bvn_hash}:{tier_config}"
            data = await redis_client.get(key)
            if data:
                result = json.loads(data)
                # Re-parse datetime strings back into datetime objects downstream
                logger.debug(f"Cache hit for score {bvn_hash}")
                return result
        except Exception as e:
            logger.warning(f"Redis score cache read failed: {e}")
        return None

    async def set_cached_score(self, bvn_hash: str, tier_config: str, score_data: Dict[str, Any]) -> None:
        """Cache a score result."""
        from src.core.redis_client import get_redis
        redis_client = await get_redis()
        if not redis_client:
            return

        try:
            key = f"score:{bvn_hash}:{tier_config}"
            # Convert datetime objects to ISO strings for JSON
            serializable = {}
            for k, v in score_data.items():
                if isinstance(v, datetime):
                    serializable[k] = v.isoformat()
                else:
                    serializable[k] = v

            await redis_client.setex(key, self._ttl, json.dumps(serializable))
            logger.debug(f"Cached score for {bvn_hash}, TTL={self._ttl}s")
        except Exception as e:
            logger.warning(f"Redis score cache write failed: {e}")

    async def get_cached_features(self, bvn_hash: str) -> Optional[Dict[str, float]]:
        """Get cached online features. Key: features:{bvn_hash}."""
        from src.core.redis_client import get_redis
        redis_client = await get_redis()
        if not redis_client:
            return None

        try:
            key = f"features:{bvn_hash}"
            data = await redis_client.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.warning(f"Redis feature cache read failed: {e}")
        return None

    async def set_cached_features(self, bvn_hash: str, features: Dict[str, float]) -> None:
        """Cache features in the online feature store. TTL: 6 hours (PRD Section 6.1)."""
        from src.core.redis_client import get_redis
        redis_client = await get_redis()
        if not redis_client:
            return

        try:
            key = f"features:{bvn_hash}"
            feature_ttl = 6 * 3600  # 6 hours per PRD freshness target
            await redis_client.setex(key, feature_ttl, json.dumps(features))
        except Exception as e:
            logger.warning(f"Redis feature cache write failed: {e}")

    async def invalidate_bvn(self, bvn_hash: str) -> None:
        """Invalidate all cached data for a BVN (e.g., on consent withdrawal)."""
        from src.core.redis_client import get_redis
        redis_client = await get_redis()
        if not redis_client:
            return

        try:
            pattern = f"score:{bvn_hash}:*"
            async for key in redis_client.scan_iter(match=pattern):
                await redis_client.delete(key)
            await redis_client.delete(f"features:{bvn_hash}")
            logger.info(f"Invalidated all cache for {bvn_hash}")
        except Exception as e:
            logger.warning(f"Redis cache invalidation failed: {e}")
