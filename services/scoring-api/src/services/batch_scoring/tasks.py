"""
Celery tasks for async batch scoring.
Per PRD US-005, Section 6.1: >10,000 records/hour throughput.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from celery import group

from src.services.batch_scoring.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="batch_scoring.score_single_borrower",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def score_single_borrower(
    self,
    bvn: str,
    tier_config: List[str],
    trace_id: str,
    consent_token_ref: str = None,
) -> Dict[str, Any]:
    """
    Score a single borrower.
    Retries up to 3 times on failure with 30s backoff.
    """
    try:
        # Import here to avoid circular imports at module load time
        import asyncio
        from src.core.database import async_session
        from src.services.scoring.service import ScoringService
        from src.core.security import hash_bvn
        from src.core.config import settings

        bvn_hash = hash_bvn(bvn, settings.bvn_encryption_key)

        async def _score():
            async with async_session() as db:
                scoring_service = ScoringService(db)
                result = await scoring_service.compute_score(
                    bvn=bvn,
                    tier_config=tier_config,
                    trace_id=trace_id,
                    consent_token_ref=consent_token_ref,
                )
                await db.commit()
                return result

        return asyncio.run(_score())

    except Exception as exc:
        logger.error(
            f"Failed to score borrower {bvn} (attempt {self.request.retries + 1})",
            exc_info=True,
        )
        raise self.retry(exc=exc)


@celery_app.task(name="batch_scoring.score_batch_job")
def score_batch_job(
    job_id: str,
    entries: List[Dict[str, Any]],
    lender_id: str,
) -> Dict[str, Any]:
    """
    Score a batch of borrowers in parallel using Celery group.
    entries: list of {bvn, phone, tier_config, external_ref}
    """
    logger.info(f"Starting batch job {job_id} with {len(entries)} entries")

    # Create a group of tasks — one task per borrower
    tasks = group(
        score_single_borrower.s(
            bvn=entry["bvn"],
            tier_config=entry.get("tier_config", ["formal"]),
            trace_id=entry.get("trace_id", f"batch_{job_id}"),
            consent_token_ref=entry.get("consent_token_ref"),
        )
        for entry in entries
    )

    # Execute the group and collect results
    result = tasks.apply_async()
    result.get(timeout=3600)  # 1 hour timeout for large batches

    results = result.get()

    # Build response
    completed = 0
    failed = 0
    output = []

    for i, (entry, score_result) in enumerate(zip(entries, results)):
        if isinstance(score_result, Exception):
            failed += 1
            output.append({
                "external_ref": entry.get("external_ref"),
                "score": None,
                "confidence_band": None,
                "data_coverage_pct": None,
                "error": str(score_result),
            })
        else:
            completed += 1
            output.append({
                "external_ref": entry.get("external_ref"),
                "score": score_result["score"],
                "confidence_band": score_result["confidence_band"],
                "data_coverage_pct": score_result["data_coverage_pct"],
                "error": None,
            })

    logger.info(
        f"Batch job {job_id} completed: {completed} succeeded, {failed} failed",
    )

    return {
        "job_id": job_id,
        "status": "completed",
        "total_entries": len(entries),
        "completed_entries": completed,
        "failed_entries": failed,
        "results": output,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
