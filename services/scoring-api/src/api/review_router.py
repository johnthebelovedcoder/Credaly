"""
Human Review API — POST /v1/review
Per PRD US-015, NDPA Section 34: borrowers can request human review of
automated credit decisions.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_consent_service, get_db
from src.core.auth import authenticate_lender
from src.core.database import get_db
from src.core.security import generate_trace_id
from src.models import LenderClient
from src.schemas import ErrorCodes, ErrorResponse
from src.services.human_review.service import HumanReviewService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/review", tags=["Human Review"])


class ReviewRequest(BaseModel):
    bvn: str = Field(..., min_length=11, max_length=11)
    loan_id: str = Field(..., description="The loan that was decided on")
    reason: str = Field(..., max_length=1000, description="Why the borrower is requesting review")
    score_at_decision: int = Field(..., ge=300, le=850)
    decision_outcome: str = Field(..., description="e.g., 'rejected', 'approved_with_conditions'")


class ReviewResponse(BaseModel):
    review_id: str
    status: str
    sla_deadline: str
    message: str


@router.post(
    "",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
    summary="Request human review of a credit decision",
    description="Submit a request for human review of an automated credit decision. PRD US-015, NDPA Section 34.",
)
async def request_human_review(
    body: ReviewRequest,
    db: AsyncSession = Depends(get_db),
    lender: LenderClient = Depends(authenticate_lender),
):
    """POST /v1/review — Request human review."""
    trace_id = generate_trace_id()

    service = HumanReviewService(db)
    review = await service.create_review_request(
        bvn=body.bvn,
        reason=body.reason,
        lender_id=lender.id,
        loan_id=body.loan_id,
        score_at_decision=body.score_at_decision,
        decision_outcome=body.decision_outcome,
    )

    return ReviewResponse(
        review_id=review.id,
        status=review.status,
        sla_deadline=review.sla_deadline.isoformat(),
        message="Human review request submitted. SLA: 5 business days.",
    )


@router.get(
    "",
    responses={401: {"model": ErrorResponse}},
    summary="List pending review requests",
    description="Get all pending human review requests, optionally filtered by lender.",
)
async def list_pending_reviews(
    lender_id: Optional[str] = Query(None, description="Filter by lender ID"),
    db: AsyncSession = Depends(get_db),
    lender: LenderClient = Depends(authenticate_lender),
):
    """GET /v1/review — List pending reviews."""
    service = HumanReviewService(db)
    # Lenders can only see their own reviews
    reviews = await service.get_pending_reviews(lender_id=lender.id)

    return [
        {
            "review_id": r.id,
            "borrower_bvn_hash": r.borrower_bvn_hash,
            "loan_id": r.loan_id,
            "score_at_decision": r.score_at_decision,
            "decision_outcome": r.decision_outcome,
            "reason": r.reason,
            "status": r.status,
            "created_at": r.created_at.isoformat(),
            "sla_deadline": r.sla_deadline.isoformat(),
        }
        for r in reviews
    ]


@router.get(
    "/{review_id}",
    responses={404: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
    summary="Get review request details",
    description="Get a specific human review request by ID.",
)
async def get_review_request(
    review_id: str,
    db: AsyncSession = Depends(get_db),
    lender: LenderClient = Depends(authenticate_lender),
):
    """GET /v1/review/{review_id} — Get review request."""
    service = HumanReviewService(db)
    review = await service.get_review_request(review_id)

    if not review or review.lender_id != lender.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                code=ErrorCodes.NOT_FOUND,
                message="Review request not found",
                trace_id=generate_trace_id(),
            ).model_dump(),
        )

    return {
        "review_id": review.id,
        "borrower_bvn_hash": review.borrower_bvn_hash,
        "loan_id": review.loan_id,
        "score_at_decision": review.score_at_decision,
        "decision_outcome": review.decision_outcome,
        "reason": review.reason,
        "status": review.status,
        "outcome": review.outcome,
        "reviewer_notes": review.reviewer_notes,
        "created_at": review.created_at.isoformat(),
        "sla_deadline": review.sla_deadline.isoformat(),
        "completed_at": review.completed_at.isoformat() if review.completed_at else None,
    }


class CompleteReviewRequest(BaseModel):
    outcome: str = Field(..., description="Review outcome: upheld, overturned, partially_overturned, insufficient_data")
    reviewer_notes: Optional[str] = Field(None, max_length=2000)


@router.post(
    "/{review_id}/complete",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
    summary="Complete a review request",
    description="Mark a review as completed with outcome and notes.",
)
async def complete_review_request(
    review_id: str,
    body: CompleteReviewRequest,
    db: AsyncSession = Depends(get_db),
    lender: LenderClient = Depends(authenticate_lender),
):
    """POST /v1/review/{review_id}/complete — Complete a review."""
    service = HumanReviewService(db)
    review = await service.get_review_request(review_id)

    if not review or review.lender_id != lender.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                code=ErrorCodes.NOT_FOUND,
                message="Review request not found",
                trace_id=generate_trace_id(),
            ).model_dump(),
        )

    try:
        completed = await service.complete_review(
            review_id=review_id,
            outcome=body.outcome,
            reviewer_notes=body.reviewer_notes,
        )
        return {
            "review_id": completed.id,
            "status": completed.status,
            "outcome": completed.outcome,
            "completed_at": completed.completed_at.isoformat(),
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                code="INVALID_OUTCOME",
                message=str(e),
                trace_id=generate_trace_id(),
            ).model_dump(),
        )
