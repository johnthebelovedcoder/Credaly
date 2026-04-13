"""
Score API Router — POST /v1/score, GET /v1/score/{bvn}/history.
Per PRD Section 8.1 and US-001 through US-005.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

from src.api.dependencies import get_consent_service, get_scoring_service
from src.core.auth import authenticate_lender
from src.core.security import generate_trace_id
from src.models import LenderClient
from src.schemas import (
    ErrorCodes,
    ErrorResponse,
    ScoreHistoryResponse,
    ScoreRequest,
    ScoreResponse,
)
from src.services.consent.service import ConsentService
from src.services.scoring.service import ScoringService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/score", tags=["Scoring"])


@router.post(
    "",
    response_model=ScoreResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
    },
    summary="Compute credit score for a borrower",
    description=
        "Submit a BVN and phone number to receive a composite credit score "
        "with confidence interval, reliability band, and human-readable explanations. "
        "Response time: < 3s p95. PRD US-001, US-002, US-003.",
)
async def compute_score(
    request_body: ScoreRequest,
    request: Request,
    lender: LenderClient = Depends(authenticate_lender),
    consent_service: ConsentService = Depends(get_consent_service),
    scoring_service: ScoringService = Depends(get_scoring_service),
):
    """
    POST /v1/score — Compute credit score. PRD Section 8.1.
    """
    trace_id = getattr(request.state, "trace_id", generate_trace_id())

    # Verify lender is authorized for the requested tiers
    tier_config = [t.value for t in request_body.tier_config]

    # Verify consent status
    all_consented, missing_categories, token_ref = await consent_service.verify_consent_for_scoring(
        bvn=request_body.bvn,
        data_categories=tier_config,
        lender_id=lender.id,
    )

    if not all_consented:
        # Score with available tiers, warn about missing consent
        logger.warning(
            f"Missing consent for categories {missing_categories} — "
            f"scoring with available tiers only"
        )
        # Filter out unconsented tiers
        tier_config = [
            t for t in tier_config
            if t not in _map_categories_to_tiers(missing_categories)
        ]
        if not tier_config:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=ErrorResponse(
                    code=ErrorCodes.INSUFFICIENT_CONSENT,
                    message=f"Borrower has not consented to data sharing for categories: {missing_categories}",
                    trace_id=trace_id,
                    docs_url="https://docs.platform.com/errors/INSUFFICIENT_CONSENT",
                ).model_dump(),
            )

    # Compute score
    try:
        result = await scoring_service.compute_score(
            bvn=request_body.bvn,
            tier_config=tier_config,
            trace_id=trace_id,
            consent_token_ref=token_ref,
        )
    except Exception as e:
        logger.error(f"Scoring failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                code=ErrorCodes.MODEL_ERROR,
                message=f"Scoring failed: {str(e)}",
                trace_id=trace_id,
                docs_url="https://docs.platform.com/errors/MODEL_ERROR",
            ).model_dump(),
        )

    return ScoreResponse(**result)


@router.get(
    "/{bvn}/history",
    response_model=ScoreHistoryResponse,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="Get borrower score history",
    description="Retrieve monthly credit scores for the past 12 months. PRD US-004.",
)
async def get_score_history(
    bvn: str,
    lender: LenderClient = Depends(authenticate_lender),
    scoring_service: ScoringService = Depends(get_scoring_service),
):
    """GET /v1/score/{bvn}/history — Score trend for the last 12 periods. PRD US-004."""
    trace_id = generate_trace_id()

    try:
        history = await scoring_service.get_score_history(bvn, limit=12)
    except Exception as e:
        logger.error(f"Score history fetch failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                code=ErrorCodes.INTERNAL_ERROR,
                message=str(e),
                trace_id=trace_id,
            ).model_dump(),
        )

    from src.core.security import hash_bvn
    return ScoreHistoryResponse(
        bvn_hash=hash_bvn(bvn),
        scores=history,
    )


def _map_categories_to_tiers(categories: list) -> list:
    """Map missing consent categories to their tiers for filtering."""
    tier_map = {
        "bureau": "formal",
        "bank": "formal",
        "telco": "alternative",
        "mobile_money": "alternative",
        "utility": "alternative",
        "psychographic": "psychographic",
    }
    tiers = set()
    for cat in categories:
        # Remove " (lender not authorized)" suffix if present
        clean_cat = cat.split(" (")[0]
        tier = tier_map.get(clean_cat)
        if tier:
            tiers.add(tier)
    return list(tiers)
