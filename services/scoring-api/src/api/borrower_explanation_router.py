"""
Borrower Explanation API — GET /v1/score/{bvn}/explanation
Per PRD FR-014: borrower-facing score explanation with different vocabulary.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.security import generate_trace_id, hash_bvn
from src.core.database import get_db
from src.models import CreditScore
from src.schemas import ErrorCodes, ErrorResponse
from src.services.borrower_explanation.service import generate_borrower_explanation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/score", tags=["Borrower Explanation"])


@router.get(
    "/{bvn}/explanation",
    responses={404: {"model": ErrorResponse}},
    summary="Get borrower-friendly score explanation",
    description="Returns a plain-language explanation of the credit score, designed for the borrower. PRD FR-014.",
)
async def get_borrower_explanation(
    bvn: str,
    db: AsyncSession = Depends(get_db),
):
    """GET /v1/score/{bvn}/explanation — Borrower-facing score explanation."""
    trace_id = generate_trace_id()
    bvn_hash = hash_bvn(bvn)

    # Get the most recent score
    stmt = (
        select(CreditScore)
        .where(CreditScore.borrower_bvn_hash == bvn_hash)
        .order_by(CreditScore.computed_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    score_record = result.scalar_one_or_none()

    if not score_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                code=ErrorCodes.NOT_FOUND,
                message="No score found for this BVN",
                trace_id=trace_id,
            ).model_dump(),
        )

    import json
    from src.services.features.service import FeatureService
    lender_positive = json.loads(score_record.positive_factors) if score_record.positive_factors else []
    lender_negative = json.loads(score_record.negative_factors) if score_record.negative_factors else []

    # Fetch real features from the feature store
    feature_service = FeatureService(db)
    try:
        features = await feature_service.get_latest_features(bvn)
    except Exception as e:
        logger.warning(f"Could not fetch features for explanation: {e}")
        features = {}

    # Generate borrower-friendly explanation
    explanation = generate_borrower_explanation(
        lender_positive_factors=lender_positive,
        lender_negative_factors=lender_negative,
        features=features,
    )

    return {
        "score": score_record.score,
        "confidence_band": score_record.confidence_band,
        "data_coverage_pct": score_record.data_coverage_pct,
        "model_version": score_record.model_version,
        "positive_factors": explanation["positive_factors"],
        "negative_factors": explanation["negative_factors"],
        "actionable_tips": explanation["actionable_tips"],
        "scored_at": score_record.computed_at.isoformat(),
    }
