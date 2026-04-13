"""
Data Retention & Purge Service — automated data lifecycle management.
Per PRD FR-016, FR-017:
  - Raw transaction data purged after 24 months
  - Derived features purged after 36 months
  - Audit logs retained for 7 years (compliance)
  - Expired consents automatically marked as expired
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.models import (
    ConsentAuditLog,
    ConsentRecord,
    CreditScore,
    DataPipelineRun,
    FeatureSnapshot,
)

logger = logging.getLogger(__name__)


class DataRetentionService:
    """
    Automated data retention enforcement.
    PRD FR-016: Raw data 24 months, derived features 36 months, audit logs 7 years.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def purge_expired_raw_data(self) -> Dict[str, int]:
        """
        Purge raw transaction data older than the retention period.
        Per PRD: raw_transaction_retention_months = 24.

        Note: In Phase 0, we don't have raw transaction tables yet.
        This method is a placeholder for when raw data ingestion is implemented.
        Returns: {"purged": count}
        """
        # Phase 0: No raw transaction tables exist yet.
        # When bank statements, telco data, etc. are ingested,
        # this method will purge them.
        logger.info("Raw data purge — no raw transaction tables in Phase 0")
        return {"purged": 0}

    async def purge_expired_features(self) -> Dict[str, int]:
        """
        Purge derived feature snapshots older than the retention period.
        Per PRD: derived_feature_retention_months = 36.
        Returns: {"purged": count}
        """
        cutoff = datetime.now(timezone.utc) - timedelta(
            days=settings.derived_feature_retention_months * 30
        )

        stmt = delete(FeatureSnapshot).where(
            FeatureSnapshot.computed_at < cutoff
        )
        result = await self.db.execute(stmt)
        await self.db.flush()

        purged = result.rowcount if result.rowcount else 0
        logger.info(
            "Feature purge completed",
            purged=purged,
            cutoff=cutoff.isoformat(),
        )
        return {"purged": purged}

    async def purge_expired_pipeline_runs(self) -> Dict[str, int]:
        """
        Purge pipeline run logs older than 90 days (hot retention).
        Returns: {"purged": count}
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)

        stmt = delete(DataPipelineRun).where(
            DataPipelineRun.completed_at < cutoff
        )
        result = await self.db.execute(stmt)
        await self.db.flush()

        purged = result.rowcount if result.rowcount else 0
        logger.info(
            "Pipeline run purge completed",
            purged=purged,
            cutoff=cutoff.isoformat(),
        )
        return {"purged": purged}

    async def purge_expired_audit_logs(self) -> Dict[str, int]:
        """
        Purge consent audit logs older than the retention period.
        Per PRD: audit_log_retention_years = 7.
        Returns: {"purged": count}
        """
        cutoff = datetime.now(timezone.utc) - timedelta(
            days=settings.audit_log_retention_years * 365
        )

        stmt = delete(ConsentAuditLog).where(
            ConsentAuditLog.timestamp < cutoff
        )
        result = await self.db.execute(stmt)
        await self.db.flush()

        purged = result.rowcount if result.rowcount else 0
        logger.info(
            "Audit log purge completed",
            purged=purged,
            cutoff=cutoff.isoformat(),
        )
        return {"purged": purged}

    async def purge_expired_scores(self) -> Dict[str, int]:
        """
        Purge credit scores older than 3 years (scores are derived, not raw).
        Returns: {"purged": count}
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=365 * 3)

        stmt = delete(CreditScore).where(
            CreditScore.computed_at < cutoff
        )
        result = await self.db.execute(stmt)
        await self.db.flush()

        purged = result.rowcount if result.rowcount else 0
        logger.info(
            "Score purge completed",
            purged=purged,
            cutoff=cutoff.isoformat(),
        )
        return {"purged": purged}

    async def run_full_purge(self) -> Dict[str, Dict[str, int]]:
        """
        Run all purge operations. Should be called by a scheduled job (e.g., daily).
        """
        logger.info("Starting full data retention purge cycle")

        results = {
            "raw_data": await self.purge_expired_raw_data(),
            "features": await self.purge_expired_features(),
            "pipeline_runs": await self.purge_expired_pipeline_runs(),
            "audit_logs": await self.purge_expired_audit_logs(),
            "scores": await self.purge_expired_scores(),
        }

        total_purged = sum(r["purged"] for r in results.values())
        logger.info(
            "Full purge cycle completed",
            total_purged=total_purged,
            details=results,
        )

        return results


class ConsentExpiryService:
    """
    Automated consent expiry enforcement.
    Per PRD FR-011, FR-014, FR-016:
      - Consents with expiry_at in the past are marked as expired
      - Cached scores for affected borrowers are invalidated
      - Downstream lenders are notified
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def expire_expired_consents(self) -> Dict[str, int]:
        """
        Mark all consents that have passed their expiry_at as expired.
        Returns: {"expired": count}
        """
        now = datetime.now(timezone.utc)

        # Find expired but not yet marked expired consents
        stmt = (
            select(ConsentRecord)
            .where(
                ConsentRecord.expiry_at.isnot(None),
                ConsentRecord.expiry_at < now,
                ConsentRecord.revoked_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        expired_consents = list(result.scalars().all())

        if not expired_consents:
            return {"expired": 0}

        # Mark them as revoked (using 'expired' as the reason)
        for consent in expired_consents:
            consent.revoked_at = now
            logger.info(
                "Consent expired automatically",
                consent_id=consent.id,
                category=consent.data_category,
                borrower_hash=consent.borrower_bvn_hash,
            )

            # Create audit log entry
            from src.services.consent.service import create_audit_log_entry

            await create_audit_log_entry(
                self.db,
                consent_id=consent.id,
                event_type="expired",
                actor_id="system",
            )

        await self.db.flush()

        # Invalidate cached scores for affected borrowers
        affected_borrowers = list(set(c.borrower_bvn_hash for c in expired_consents))
        await self._invalidate_cached_scores(affected_borrowers)

        logger.info(
            "Consent expiry processed",
            expired=len(expired_consents),
            affected_borrowers=len(affected_borrowers),
        )

        return {"expired": len(expired_consents)}

    async def _invalidate_cached_scores(self, bvn_hashes: List[str]) -> None:
        """Invalidate cached scores for borrowers whose consents expired."""
        try:
            from src.services.cache.service import CacheService

            cache = CacheService()
            for bvn_hash in bvn_hashes:
                await cache.invalidate_bvn(bvn_hash)
        except Exception as e:
            logger.warning(f"Failed to invalidate cached scores: {e}")
