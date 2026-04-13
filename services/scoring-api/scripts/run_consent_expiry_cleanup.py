"""
Consent Expiry Background Job — auto-revokes expired consent records.
Per PRD FR-016: "automated data retention enforcement."

Designed to run daily via cron, Airflow DAG, or Celery beat.
Usage:
    python -m scripts.run_consent_expiry_cleanup
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import ConsentRecord

logger = logging.getLogger(__name__)


async def run_consent_expiry_cleanup(db: AsyncSession) -> dict:
    """
    Find all consent records that have expired (expiry_at < now)
    and are not already revoked. Mark them as revoked.

    Returns a summary of what was processed.
    """
    now = datetime.now(timezone.utc)

    stmt = (
        select(ConsentRecord)
        .where(
            ConsentRecord.expiry_at.isnot(None),
            ConsentRecord.expiry_at < now,
            ConsentRecord.revoked_at.is_(None),
        )
    )
    result = await db.execute(stmt)
    expired_consents = result.scalars().all()

    revoked_count = 0
    for consent in expired_consents:
        consent.revoked_at = now
        revoked_count += 1
        logger.info(
            "Auto-revoked expired consent",
            consent_id=consent.id,
            category=consent.data_category,
            expired_at=consent.expiry_at.isoformat(),
        )

    await db.flush()

    logger.info(
        "Consent expiry cleanup complete",
        revoked=revoked_count,
        total_scanned=len(expired_consents),
    )

    return {
        "revoked_count": revoked_count,
        "scanned_at": now.isoformat(),
    }


if __name__ == "__main__":
    import asyncio
    from src.core.database import async_session_factory

    async def main():
        async with async_session_factory() as session:
            results = await run_consent_expiry_cleanup(session)
            await session.commit()
            print(f"Consent expiry cleanup complete:")
            print(f"  Revoked: {results['revoked_count']}")
            print(f"  Scanned at: {results['scanned_at']}")

    asyncio.run(main())
