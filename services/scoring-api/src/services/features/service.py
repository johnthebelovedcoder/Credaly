"""
Feature Engineering Service — computes standardized features from ingested data.
Per PRD Section 5.3: FR-020 through FR-023.

Features computed (minimum set per FR-020):
  - income_stability_score
  - expense_volatility_score
  - telco_consistency_index
  - mobile_money_inflow_trend
  - utility_payment_streak
  - bureau_delinquency_flag
  - debt_to_income_ratio
"""

import hashlib
import json
import logging
import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.models import FeatureSnapshot, _hash_bvn

logger = logging.getLogger(__name__)

# Canonical feature definitions per PRD FR-020
CANONICAL_FEATURES = {
    "formal": [
        "income_stability_score",
        "expense_volatility_score",
        "bureau_delinquency_flag",
        "debt_to_income_ratio",
        "total_credit_accounts",
        "active_credit_accounts",
        "credit_utilization_ratio",
        "oldest_account_age_months",
        "recent_inquiries_6m",
    ],
    "alternative": [
        "telco_consistency_index",
        "mobile_money_inflow_trend",
        "utility_payment_streak",
        "bnpl_repayment_rate",
        "savings_balance_trend",
    ],
    "psychographic": [
        "address_stability_score",
        "employment_tenure_months",
        "app_usage_regularity",
    ],
}


def _seeded_random(seed_str: str) -> random.Random:
    """Create a deterministic RNG seeded by BVN hash for reproducible mock features."""
    seed = int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16)
    return random.Random(seed)


class FeatureService:
    """
    Computes, stores, and retrieves ML features.
    PRD FR-020 — FR-023.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    def compute_features_from_ingested_data(
        self,
        bvn_hash: str,
        ingested_data: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Compute standardized features from normalized ingested data.
        PRD FR-020.

        Each bureau source contributes to formal features.
        Alternative and psychographic features come from their respective tiers.
        """
        features = []
        now = datetime.now(timezone.utc)

        # ── Formal features from bureau data ──────────────────────────
        bureau_scores = []
        total_accounts = 0
        total_delinquent = 0
        total_outstanding = 0
        max_oldest_age = 0
        total_inquiries = 0
        bureau_count = 0

        for source_name, data in ingested_data.items():
            if "bureau" in source_name:
                bureau_count += 1
                if data.get("credit_score"):
                    bureau_scores.append(data["credit_score"])
                total_accounts += data.get("total_accounts", 0)
                total_delinquent += data.get("delinquent_accounts", 0)
                total_outstanding += data.get("total_outstanding_balance", 0)
                if data.get("oldest_account_age_months"):
                    max_oldest_age = max(max_oldest_age, data["oldest_account_age_months"])
                total_inquiries += data.get("inquiries_last_6_months", 0)

        if bureau_count > 0:
            # Aggregate bureau features
            avg_bureau_score = sum(bureau_scores) / len(bureau_scores) if bureau_scores else 0
            delinquency_flag = 1.0 if total_delinquent > 0 else 0.0

            features.append({
                "borrower_bvn_hash": bvn_hash,
                "feature_name": "income_stability_score",
                "feature_value": 0.5,  # Placeholder — computed from bank statements (Phase 2)
                "source_tier": "formal",
            })
            features.append({
                "borrower_bvn_hash": bvn_hash,
                "feature_name": "expense_volatility_score",
                "feature_value": 0.5,  # Placeholder
                "source_tier": "formal",
            })
            features.append({
                "borrower_bvn_hash": bvn_hash,
                "feature_name": "bureau_delinquency_flag",
                "feature_value": delinquency_flag,
                "source_tier": "formal",
            })
            features.append({
                "borrower_bvn_hash": bvn_hash,
                "feature_name": "debt_to_income_ratio",
                "feature_value": total_outstanding / 1000000 if total_outstanding > 0 else 0.0,  # Placeholder
                "source_tier": "formal",
            })
            features.append({
                "borrower_bvn_hash": bvn_hash,
                "feature_name": "total_credit_accounts",
                "feature_value": float(total_accounts),
                "source_tier": "formal",
            })
            features.append({
                "borrower_bvn_hash": bvn_hash,
                "feature_name": "active_credit_accounts",
                "feature_value": float(total_accounts - total_delinquent),
                "source_tier": "formal",
            })
            features.append({
                "borrower_bvn_hash": bvn_hash,
                "feature_name": "credit_utilization_ratio",
                "feature_value": 0.0,  # Placeholder — needs credit limit data
                "source_tier": "formal",
            })
            features.append({
                "borrower_bvn_hash": bvn_hash,
                "feature_name": "oldest_account_age_months",
                "feature_value": float(max_oldest_age),
                "source_tier": "formal",
            })
            features.append({
                "borrower_bvn_hash": bvn_hash,
                "feature_name": "recent_inquiries_6m",
                "feature_value": float(total_inquiries),
                "source_tier": "formal",
            })
            features.append({
                "borrower_bvn_hash": bvn_hash,
                "feature_name": "avg_bureau_score",
                "feature_value": avg_bureau_score,
                "source_tier": "formal",
            })

        # ── Alternative features — mock generation for sandbox/dev ──────
        # Generate realistic alternative features correlated with formal data quality.
        # In production, these come from real telco/mobile money/utility data sources.
        rng = _seeded_random(bvn_hash)

        # Derive alt feature quality from formal signals (good borrowers tend to have good alt signals)
        alt_quality = 0.5  # Default
        if features:
            # Use bureau score as proxy for overall financial behavior quality
            bureau_score = next(
                (f["feature_value"] for f in features if f["feature_name"] == "avg_bureau_score"),
                None
            )
            if bureau_score and bureau_score > 0:
                alt_quality = max(0, min(1, (bureau_score - 300) / 550))

        # Telco consistency: correlated with creditworthiness
        telco_index = max(0, min(1, rng.gauss(alt_quality, 0.15)))
        features.append({
            "borrower_bvn_hash": bvn_hash,
            "feature_name": "telco_consistency_index",
            "feature_value": round(telco_index, 4),
            "source_tier": "alternative",
        })

        # Mobile money inflow trend: correlated with creditworthiness
        mm_trend = max(0, min(1, rng.gauss(alt_quality * 0.7 + 0.2, 0.2)))
        features.append({
            "borrower_bvn_hash": bvn_hash,
            "feature_name": "mobile_money_inflow_trend",
            "feature_value": round(mm_trend, 4),
            "source_tier": "alternative",
        })

        # Utility payment streak: good borrowers pay utilities on time
        utility_streak = max(0, rng.gauss(alt_quality * 18, 6))
        features.append({
            "borrower_bvn_hash": bvn_hash,
            "feature_name": "utility_payment_streak",
            "feature_value": round(utility_streak, 2),
            "source_tier": "alternative",
        })

        # BNPL repayment rate
        bnpl_rate = max(0, min(1, rng.gauss(alt_quality * 0.7 + 0.25, 0.12)))
        features.append({
            "borrower_bvn_hash": bvn_hash,
            "feature_name": "bnpl_repayment_rate",
            "feature_value": round(bnpl_rate, 4),
            "source_tier": "alternative",
        })

        # Savings balance trend
        savings_trend = max(0, min(1, rng.gauss(alt_quality * 0.5 + 0.25, 0.2)))
        features.append({
            "borrower_bvn_hash": bvn_hash,
            "feature_name": "savings_balance_trend",
            "feature_value": round(savings_trend, 4),
            "source_tier": "alternative",
        })

        # ── Psychographic features — mock generation for sandbox/dev ────
        # Address stability: correlated with age/credit history
        age_proxy = max(0, min(1, (alt_quality * 0.6 + 0.2)))
        addr_stability = max(0, min(1, rng.gauss(age_proxy, 0.15)))
        features.append({
            "borrower_bvn_hash": bvn_hash,
            "feature_name": "address_stability_score",
            "feature_value": round(addr_stability, 4),
            "source_tier": "psychographic",
        })

        # Employment tenure: older borrowers have longer tenure
        tenure = max(0, rng.gauss(age_proxy * 48 + 12, 18))
        features.append({
            "borrower_bvn_hash": bvn_hash,
            "feature_name": "employment_tenure_months",
            "feature_value": round(tenure, 2),
            "source_tier": "psychographic",
        })

        # App usage regularity
        app_regularity = max(0, min(1, rng.gauss(0.5, 0.2)) + (alt_quality - 0.5) * 0.2)
        features.append({
            "borrower_bvn_hash": bvn_hash,
            "feature_name": "app_usage_regularity",
            "feature_value": round(max(0, min(1, app_regularity)), 4),
            "source_tier": "psychographic",
        })

        # Tag all with timestamps
        for f in features:
            f["computed_at"] = now
            f["data_snapshot_at"] = now

        return features

    async def store_features(self, features: List[Dict[str, Any]]) -> None:
        """
        Store computed feature snapshots in the database (offline store) AND
        populate the Redis online feature store. PRD FR-021.
        """
        import uuid

        # Group features by borrower for Redis online store
        features_by_borrower: Dict[str, Dict[str, float]] = {}

        for f in features:
            snapshot = FeatureSnapshot(
                id=f"fet_{uuid.uuid4().hex[:10]}",
                borrower_bvn_hash=f["borrower_bvn_hash"],
                feature_name=f["feature_name"],
                feature_value=f["feature_value"],
                source_tier=f["source_tier"],
                computed_at=f.get("computed_at", datetime.now(timezone.utc)),
                data_snapshot_at=f.get("data_snapshot_at", datetime.now(timezone.utc)),
            )
            self.db.add(snapshot)

            # Collect for Redis online store
            bvn_hash = f["borrower_bvn_hash"]
            if bvn_hash not in features_by_borrower:
                features_by_borrower[bvn_hash] = {}
            features_by_borrower[bvn_hash][f["feature_name"]] = f["feature_value"]

        # Populate Redis online feature store for each borrower
        for bvn_hash, borrower_features in features_by_borrower.items():
            await self._set_features_to_redis(bvn_hash, borrower_features)

    async def get_latest_features(
        self,
        bvn: str,
        tier_config: Optional[List[str]] = None,
    ) -> Dict[str, float]:
        """
        Retrieve latest features for a borrower. PRD FR-021.
        
        Online feature store pattern:
        1. Check Redis online feature store first (low-latency, < 10ms)
        2. Fall back to PostgreSQL offline store
        3. Populate Redis from PostgreSQL on cache miss
        
        If tier_config is provided, filter features to only those tiers.
        """
        bvn_hash = _hash_bvn(bvn, settings.bvn_encryption_key)

        # 1. Check Redis online feature store
        online_features = await self._get_features_from_redis(bvn_hash)
        if online_features:
            # Filter by tier if requested
            if tier_config:
                # We need to know the tier for each feature — fetch metadata
                online_features = self._filter_features_by_tier(online_features, tier_config)
            logger.debug(f"Features retrieved from Redis for {bvn_hash}")
            return online_features

        # 2. Fall back to PostgreSQL offline store
        stmt = (
            select(FeatureSnapshot)
            .where(FeatureSnapshot.borrower_bvn_hash == bvn_hash)
            .order_by(FeatureSnapshot.computed_at.desc())
        )
        result = await self.db.execute(stmt)
        all_snapshots = result.scalars().all()

        # De-duplicate by feature_name (keep latest per feature)
        latest = {}
        for snap in all_snapshots:
            if snap.feature_name not in latest:
                if tier_config is None or snap.source_tier in tier_config:
                    latest[snap.feature_name] = snap.feature_value

        # 3. Populate Redis online store (async, don't block the response)
        if latest:
            await self._set_features_to_redis(bvn_hash, latest)

        return latest

    async def _get_features_from_redis(self, bvn_hash: str) -> Optional[Dict[str, float]]:
        """Get features from Redis online feature store."""
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
            logger.warning(f"Redis online feature store read failed: {e}")
        return None

    async def _set_features_to_redis(self, bvn_hash: str, features: Dict[str, float]) -> None:
        """Store features in Redis online feature store. TTL: 6 hours."""
        from src.core.redis_client import get_redis
        redis_client = await get_redis()
        if not redis_client:
            return

        try:
            key = f"features:{bvn_hash}"
            feature_ttl = 6 * 3600  # 6 hours per PRD freshness target
            await redis_client.setex(key, feature_ttl, json.dumps(features))
        except Exception as e:
            logger.warning(f"Redis online feature store write failed: {e}")

    def _filter_features_by_tier(
        self,
        features: Dict[str, float],
        tier_config: List[str],
    ) -> Dict[str, float]:
        """Filter features to only those belonging to the requested tiers."""
        allowed_features = set()
        for tier in tier_config:
            allowed_features.update(CANONICAL_FEATURES.get(tier, []))

        return {k: v for k, v in features.items() if k in allowed_features}

    def compute_data_coverage_pct(
        self,
        features: Dict[str, float],
        tier_config: Optional[List[str]] = None,
    ) -> float:
        """
        Compute data_coverage_pct — percentage of total feature signals available.
        PRD FR-023.
        """
        if tier_config:
            total_possible = sum(
                len(CANONICAL_FEATURES.get(tier, [])) for tier in tier_config
            )
        else:
            total_possible = sum(len(f) for f in CANONICAL_FEATURES.values())

        available = len(features)
        return (available / total_possible * 100) if total_possible > 0 else 0.0
