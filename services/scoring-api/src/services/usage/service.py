"""
Lender Usage Tracking Service — tracks API call volume, spending, and rate limits.
Per PRD US-009: "view my API usage, spending, and rate limits in real time."

Uses Redis for real-time counters + PostgreSQL for historical daily aggregates.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.core.config import settings
from src.core.redis_client import get_redis

logger = logging.getLogger(__name__)


class UsageService:
    """Tracks and retrieves API usage metrics per lender."""

    async def record_api_call(
        self,
        lender_id: str,
        endpoint: str,
        response_status: int,
        response_time_ms: float,
    ) -> None:
        """Record a single API call for usage tracking."""
        redis_client = await get_redis()
        if not redis_client:
            return

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        try:
            pipe = redis_client.pipeline()
            # Daily call count
            pipe.incr(f"usage:{lender_id}:{today}:calls")
            pipe.expire(f"usage:{lender_id}:{today}:calls", 86400 * 90)  # Keep 90 days

            # Daily error count (4xx + 5xx)
            if response_status >= 400:
                pipe.incr(f"usage:{lender_id}:{today}:errors")
                pipe.expire(f"usage:{lender_id}:{today}:errors", 86400 * 90)

            # Daily response time sum (for averaging)
            pipe.incrbyfloat(f"usage:{lender_id}:{today}:latency_sum", response_time_ms)
            pipe.expire(f"usage:{lender_id}:{today}:latency_sum", 86400 * 90)

            # Endpoint-specific counts
            pipe.incr(f"usage:{lender_id}:{today}:endpoint:{endpoint}")
            pipe.expire(f"usage:{lender_id}:{today}:endpoint:{endpoint}", 86400 * 90)

            await pipe.execute()
        except Exception as e:
            logger.warning(f"Failed to record API call usage: {e}")

    async def get_usage(
        self,
        lender_id: str,
        days: int = 30,
    ) -> dict:
        """
        Get usage statistics for a lender over the past N days.
        Returns daily breakdown + summary.
        """
        redis_client = await get_redis()
        if not redis_client:
            return self._empty_usage()

        daily_data = []
        total_calls = 0
        total_errors = 0
        total_latency = 0.0

        for i in range(days):
            date = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")

            try:
                pipe = redis_client.pipeline()
                pipe.get(f"usage:{lender_id}:{date}:calls")
                pipe.get(f"usage:{lender_id}:{date}:errors")
                pipe.get(f"usage:{lender_id}:{date}:latency_sum")
                results = await pipe.execute()

                calls = int(results[0] or 0)
                errors = int(results[1] or 0)
                latency_sum = float(results[2] or 0)
                avg_latency = latency_sum / calls if calls > 0 else 0

                daily_data.append({
                    "date": date,
                    "calls": calls,
                    "errors": errors,
                    "avg_latency_ms": round(avg_latency, 1),
                })

                total_calls += calls
                total_errors += errors
                total_latency += latency_sum

            except Exception as e:
                logger.warning(f"Failed to retrieve usage for {date}: {e}")
                daily_data.append({"date": date, "calls": 0, "errors": 0, "avg_latency_ms": 0})

        avg_latency = total_latency / total_calls if total_calls > 0 else 0

        return {
            "lender_id": lender_id,
            "period_days": days,
            "summary": {
                "total_calls": total_calls,
                "total_errors": total_errors,
                "error_rate_pct": round((total_errors / total_calls * 100) if total_calls > 0 else 0, 2),
                "avg_latency_ms": round(avg_latency, 1),
            },
            "daily": daily_data,
        }

    async def get_rate_limit_headroom(self, lender_id: str, rate_limit: int) -> dict:
        """Get current rate limit usage vs. the limit."""
        redis_client = await get_redis()
        if not redis_client:
            return {"limit": rate_limit, "used": 0, "remaining": rate_limit, "pct_used": 0}

        bucket = int(datetime.now(timezone.utc).timestamp()) // 60
        key = f"ratelimit:{lender_id}:{bucket}"

        try:
            current = int(await redis_client.get(key) or 0)
        except Exception:
            current = 0

        return {
            "limit": rate_limit,
            "used": current,
            "remaining": max(0, rate_limit - current),
            "pct_used": round((current / rate_limit * 100) if rate_limit > 0 else 0, 1),
        }

    def _empty_usage(self) -> dict:
        return {
            "lender_id": "",
            "period_days": 30,
            "summary": {"total_calls": 0, "total_errors": 0, "error_rate_pct": 0, "avg_latency_ms": 0},
            "daily": [],
        }
