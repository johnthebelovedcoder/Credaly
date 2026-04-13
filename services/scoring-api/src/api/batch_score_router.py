"""
Batch Scoring API — POST /v1/score/batch
Per PRD US-005, Section 6.1: >10,000 records/hour throughput.
For portfolio review use case.

Production: Uses Celery async workers for parallel processing.
Development: Falls back to synchronous processing when Celery unavailable.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.api.dependencies import get_scoring_service
from src.core.auth import authenticate_lender
from src.core.config import settings
from src.core.security import generate_trace_id
from src.models import LenderClient
from src.schemas import ErrorCodes, ErrorResponse, ScoreResponse, TierEnum
from src.services.scoring.service import ScoringService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/score", tags=["Batch Scoring"])


class BatchScoreEntry(BaseModel):
    bvn: str = Field(..., min_length=11, max_length=11)
    phone: str
    tier_config: List[TierEnum] = [TierEnum.formal]
    external_ref: Optional[str] = None  # Client's own reference for this entry


class BatchScoreRequest(BaseModel):
    entries: List[BatchScoreEntry] = Field(..., min_length=1, max_length=10000)


class BatchScoreResultEntry(BaseModel):
    external_ref: Optional[str]
    score: Optional[int]
    confidence_band: Optional[str]
    data_coverage_pct: Optional[float]
    error: Optional[str]


class BatchScoreJobResponse(BaseModel):
    job_id: str
    status: str  # completed, processing, failed
    total_entries: int
    completed_entries: int
    failed_entries: int
    results: Optional[List[BatchScoreResultEntry]]
    created_at: str
    completed_at: Optional[str]
    estimated_completion_seconds: Optional[int] = None


# In-memory job store for development fallback
_batch_jobs: dict = {}


def _is_celery_available() -> bool:
    """Check if Celery workers are running and accepting tasks."""
    try:
        from src.services.batch_scoring.celery_app import celery_app
        inspect = celery_app.control.inspect()
        ping_result = inspect.ping()
        return ping_result is not None and len(ping_result) > 0
    except Exception:
        return False


@router.post(
    "/batch",
    response_model=BatchScoreJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
    summary="Submit batch scoring job",
    description="Score up to 10,000 borrowers in one request for portfolio review. PRD US-005.",
)
async def submit_batch_score(
    body: BatchScoreRequest,
    lender: LenderClient = Depends(authenticate_lender),
    scoring_service: ScoringService = Depends(get_scoring_service),
):
    """
    POST /v1/score/batch — Submit batch scoring job.

    Production: Dispatches to Celery workers for async parallel processing.
    Development: Falls back to synchronous processing.
    """
    trace_id = generate_trace_id()

    if len(body.entries) > 10000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                code="BATCH_TOO_LARGE",
                message="Maximum 10,000 entries per batch",
                trace_id=trace_id,
            ).model_dump(),
        )

    job_id = f"batch_{uuid.uuid4().hex[:10]}"

    # Try Celery first
    if _is_celery_available():
        from src.services.batch_scoring.tasks import score_batch_job

        entries_data = [
            {
                "bvn": entry.bvn,
                "phone": entry.phone,
                "tier_config": [t.value for t in entry.tier_config],
                "external_ref": entry.external_ref,
                "trace_id": trace_id,
            }
            for entry in body.entries
        ]

        # Dispatch to Celery
        task = score_batch_job.apply_async(
            args=[job_id, entries_data, lender.id],
            task_id=job_id,
        )

        # Estimate completion: ~100 entries/minute per worker
        estimated_workers = 1  # Would query Celery for actual worker count
        entries_per_minute = 100 * estimated_workers
        estimated_seconds = max(60, len(body.entries) // entries_per_minute * 60)

        return BatchScoreJobResponse(
            job_id=job_id,
            status="processing",
            total_entries=len(body.entries),
            completed_entries=0,
            failed_entries=0,
            results=None,
            created_at=datetime.now(timezone.utc).isoformat(),
            completed_at=None,
            estimated_completion_seconds=estimated_seconds,
        )

    # Fallback: synchronous processing (development only)
    logger.warning(
        "Celery not available — falling back to synchronous batch processing"
    )

    results = []
    failed = 0
    for entry in body.entries:
        try:
            result = await scoring_service.compute_score(
                bvn=entry.bvn,
                tier_config=[t.value for t in entry.tier_config],
                trace_id=trace_id,
            )
            results.append(BatchScoreResultEntry(
                external_ref=entry.external_ref,
                score=result["score"],
                confidence_band=result["confidence_band"],
                data_coverage_pct=result["data_coverage_pct"],
                error=None,
            ))
        except Exception as e:
            logger.error(f"Batch score failed for {entry.bvn}: {e}")
            failed += 1
            results.append(BatchScoreResultEntry(
                external_ref=entry.external_ref,
                score=None,
                confidence_band=None,
                data_coverage_pct=None,
                error=str(e),
            ))

    _batch_jobs[job_id] = {
        "job_id": job_id,
        "lender_id": lender.id,
        "status": "completed",
        "total_entries": len(body.entries),
        "completed_entries": len(body.entries) - failed,
        "failed_entries": failed,
        "results": [r.model_dump() for r in results],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }

    return BatchScoreJobResponse(
        job_id=job_id,
        status="completed",
        total_entries=len(body.entries),
        completed_entries=len(body.entries) - failed,
        failed_entries=failed,
        results=results,
        created_at=_batch_jobs[job_id]["created_at"],
        completed_at=_batch_jobs[job_id]["completed_at"],
    )


@router.get(
    "/batch/{job_id}",
    response_model=BatchScoreJobResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get batch scoring job status",
    description="Check status and retrieve results of a batch scoring job.",
)
async def get_batch_score_job(
    job_id: str,
    lender: LenderClient = Depends(authenticate_lender),
):
    """GET /v1/score/batch/{job_id} — Get job status and results."""
    trace_id = generate_trace_id()

    # Check Celery first
    if _is_celery_available():
        from celery.result import AsyncResult
        from src.services.batch_scoring.tasks import score_batch_job

        result = AsyncResult(job_id, app=score_batch_job.app)

        if result.state == "PENDING":
            return BatchScoreJobResponse(
                job_id=job_id,
                status="processing",
                total_entries=0,
                completed_entries=0,
                failed_entries=0,
                results=None,
                created_at="",
                completed_at=None,
            )
        elif result.state == "SUCCESS":
            job_data = result.get()
            results = [BatchScoreResultEntry(**r) for r in job_data.get("results", [])]
            return BatchScoreJobResponse(
                job_id=job_id,
                status=job_data["status"],
                total_entries=job_data["total_entries"],
                completed_entries=job_data["completed_entries"],
                failed_entries=job_data.get("failed_entries", 0),
                results=results,
                created_at=job_data["created_at"],
                completed_at=job_data.get("completed_at"),
            )
        elif result.state == "FAILURE":
            return BatchScoreJobResponse(
                job_id=job_id,
                status="failed",
                total_entries=0,
                completed_entries=0,
                failed_entries=0,
                results=None,
                created_at="",
                completed_at=None,
            )

    # Fallback: in-memory store
    job = _batch_jobs.get(job_id)

    if not job or job["lender_id"] != lender.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                code=ErrorCodes.NOT_FOUND,
                message="Batch job not found",
                trace_id=trace_id,
            ).model_dump(),
        )

    results = [BatchScoreResultEntry(**r) for r in (job.get("results") or [])]

    return BatchScoreJobResponse(
        job_id=job["job_id"],
        status=job["status"],
        total_entries=job["total_entries"],
        completed_entries=job["completed_entries"],
        failed_entries=job.get("failed_entries", 0),
        results=results,
        created_at=job["created_at"],
        completed_at=job.get("completed_at"),
    )
