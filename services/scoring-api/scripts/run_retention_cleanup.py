"""
Data Retention Service — automated purge of expired data.
Per PRD FR-016:
  - Raw transaction data purged after 24 months
  - Derived features purged after 36 months or consent withdrawal
  - Audit logs retained for 7 years (cold storage)

This is designed to run as a periodic Celery beat task or Airflow DAG.
For Phase 0, it's a standalone script that can be scheduled via cron.

Usage:
    python -m scripts.run_retention_cleanup
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.models import (
    ConsentRecord,
    FeatureSnapshot,
    CreditScore,
    DataPipelineRun,
)

logger = logging.getLogger(__name__)


async def run_retention_cleanup(db: AsyncSession) -> dict:
    """
    Execute data retention policies.
    Returns a summary of what was purged.
    """
    now = datetime.now(timezone.utc)
    results = {
        "expired_features_purged": 0,
        "expired_pipeline_runs_purged": 0,
        "expired_consent_records_archived": 0,
        "purge_timestamp": now.isoformat(),
    }

    # ── Purge expired derived features (36 months) ─────────────────────
    feature_cutoff = now - timedelta(days=settings.derived_feature_retention_months * 30)
    feature_stmt = delete(FeatureSnapshot).where(
        FeatureSnapshot.computed_at < feature_cutoff
    )
    feature_result = await db.execute(feature_stmt)
    results["expired_features_purged"] = feature_result.rowcount or 0
    logger.info(f"Purged {results['expired_features_purged']} expired feature snapshots")

    # ── Purge old pipeline runs (90 days) ──────────────────────────────
    pipeline_cutoff = now - timedelta(days=90)
    pipeline_stmt = delete(DataPipelineRun).where(
        DataPipelineRun.completed_at < pipeline_cutoff
    )
    pipeline_result = await db.execute(pipeline_stmt)
    results["expired_pipeline_runs_purged"] = pipeline_result.rowcount or 0
    logger.info(f"Purged {results['expired_pipeline_runs_purged']} old pipeline runs")

    # ── Mark expired consent records (do not delete — keep for audit) ──
    consent_cutoff = now - timedelta(days=730)  # ~24 months
    expired_consents_stmt = (
        select(ConsentRecord)
        .where(
            ConsentRecord.expiry_at.isnot(None),
            ConsentRecord.expiry_at < consent_cutoff,
            ConsentRecord.revoked_at.is_(None),
        )
    )
    expired_result = await db.execute(expired_consents_stmt)
    expired_consents = expired_result.scalars().all()
    results["expired_consent_records_archived"] = len(expired_consents)

    for consent in expired_consents:
        consent.revoked_at = now
        logger.info(f"Auto-revoked expired consent {consent.id}")

    logger.info(f"Retention cleanup complete: {results}")
    return results


if __name__ == "__main__":
    import asyncio
    from src.core.database import async_session_factory

    async def main():
        async with async_session_factory() as session:
            results = await run_retention_cleanup(session)
            await session.commit()
            print(f"Retention cleanup complete:")
            for key, value in results.items():
                print(f"  {key}: {value}")

    asyncio.run(main())
