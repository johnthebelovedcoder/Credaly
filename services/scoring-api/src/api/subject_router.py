"""
Data Subject Rights Router — GET /v1/subject/{bvn}/data (DSAR).
Per PRD FR-017, US-013.
"""

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.database import get_db
from src.core.security import generate_trace_id, hash_bvn
from src.models import BorrowerProfile, ConsentRecord, CreditScore, FeatureSnapshot
from src.schemas import DataSubjectDataResponse, ErrorCodes, ErrorResponse
from src.services.consent.service import ConsentService
from src.api.dependencies import get_consent_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subject", tags=["Data Subject Rights"])


@router.get(
    "/{bvn}/data",
    response_model=DataSubjectDataResponse,
    responses={
        404: {"model": ErrorResponse},
    },
    summary="Data Subject Access Request (DSAR)",
    description=
        "Compile all data held about a data subject within 72 hours. "
        "PRD FR-017, US-013.",
)
async def get_subject_data(
    bvn: str,
    db: AsyncSession = Depends(get_db),
    consent_service: ConsentService = Depends(get_consent_service),
):
    """
    GET /v1/subject/{bvn}/data — DSAR response. PRD FR-017.
    Returns all data held about a borrower: profile, consents, features, scores.
    """
    trace_id = generate_trace_id()
    bvn_hash = hash_bvn(bvn)

    # Fetch profile
    profile_stmt = select(BorrowerProfile).where(BorrowerProfile.bvn_hash == bvn_hash)
    profile_result = await db.execute(profile_stmt)
    profile = profile_result.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                code=ErrorCodes.NOT_FOUND,
                message="No data found for this BVN",
                trace_id=trace_id,
            ).model_dump(),
        )

    # Fetch consent records
    consent_stmt = (
        select(ConsentRecord)
        .where(ConsentRecord.borrower_bvn_hash == bvn_hash)
        .order_by(ConsentRecord.created_at.desc())
    )
    consent_result = await db.execute(consent_stmt)
    consents = consent_result.scalars().all()

    consent_data = [
        {
            "consent_id": c.id,
            "data_category": c.data_category,
            "purpose": c.purpose,
            "is_active": c.is_active,
            "granted_at": c.created_at.isoformat(),
            "revoked_at": c.revoked_at.isoformat() if c.revoked_at else None,
            "expiry_at": c.expiry_at.isoformat() if c.expiry_at else None,
        }
        for c in consents
    ]

    # Fetch feature summary
    feature_stmt = (
        select(FeatureSnapshot)
        .where(FeatureSnapshot.borrower_bvn_hash == bvn_hash)
        .order_by(FeatureSnapshot.computed_at.desc())
    )
    feature_result = await db.execute(feature_stmt)
    features = feature_result.scalars().all()

    # De-duplicate by feature_name
    feature_map = {}
    for f in features:
        if f.feature_name not in feature_map:
            feature_map[f.feature_name] = {
                "feature_name": f.feature_name,
                "value": f.feature_value,
                "source_tier": f.source_tier,
                "computed_at": f.computed_at.isoformat(),
            }
    feature_summary = list(feature_map.values())

    # Fetch score history
    score_stmt = (
        select(CreditScore)
        .where(CreditScore.borrower_bvn_hash == bvn_hash)
        .order_by(CreditScore.computed_at.desc())
        .limit(12)
    )
    score_result = await db.execute(score_stmt)
    scores = score_result.scalars().all()

    score_history = [
        {
            "score": s.score,
            "confidence_band": s.confidence_band,
            "data_coverage_pct": s.data_coverage_pct,
            "model_version": s.model_version,
            "computed_at": s.computed_at.isoformat(),
        }
        for s in scores
    ]

    return DataSubjectDataResponse(
        bvn_hash=bvn_hash,
        profile={
            "data_coverage_pct": profile.data_coverage_pct,
            "created_at": profile.created_at.isoformat(),
        },
        consent_records=consent_data,
        feature_summary=feature_summary,
        score_history=score_history,
        compiled_at=datetime.now(timezone.utc),
    )
