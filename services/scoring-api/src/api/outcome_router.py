"""
Outcome API Router — POST /v1/outcomes, GET /v1/outcomes.
Per PRD Section 8.2 and FR-030.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from src.api.dependencies import get_outcome_service
from src.core.auth import authenticate_lender
from src.core.security import generate_trace_id
from src.models import LenderClient
from src.schemas import (
    ErrorCodes,
    ErrorResponse,
    OutcomeHistoryResponse,
    OutcomeResponse,
    OutcomeSubmission,
)
from src.services.outcomes.service import OutcomeService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/outcomes", tags=["Outcomes"])


@router.post(
    "",
    response_model=OutcomeResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
    summary="Submit loan repayment outcome",
    description=
        "Submit a loan repayment outcome to contribute to the model's ground truth dataset. "
        "PRD Section 8.2, US-010.",
)
async def submit_outcome(
    request_body: OutcomeSubmission,
    request: Request,
    lender: LenderClient = Depends(authenticate_lender),
    outcome_service: OutcomeService = Depends(get_outcome_service),
):
    """
    POST /v1/outcomes — Submit loan repayment outcome. PRD Section 8.2.
    """
    trace_id = getattr(request.state, "trace_id", generate_trace_id())

    try:
        result = await outcome_service.submit_outcome(
            loan_id=request_body.loan_id,
            bvn=request_body.bvn,
            lender_id=lender.id,
            disbursement_date=request_body.disbursement_date,
            due_date=request_body.due_date,
            loan_amount_ngn=request_body.loan_amount_ngn,
            outcome=request_body.outcome.value,
            outcome_date=request_body.outcome_date,
            score_at_origination=request_body.score_at_origination,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=ErrorResponse(
                code=ErrorCodes.DUPLICATE_LOAN,
                message=str(e),
                trace_id=trace_id,
                docs_url="https://docs.platform.com/errors/DUPLICATE_LOAN",
            ).model_dump(),
        )
    except Exception as e:
        logger.error(f"Outcome submission failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                code=ErrorCodes.INTERNAL_ERROR,
                message=str(e),
                trace_id=trace_id,
            ).model_dump(),
        )

    return OutcomeResponse(**result)


@router.get(
    "",
    response_model=OutcomeHistoryResponse,
    responses={
        401: {"model": ErrorResponse},
    },
    summary="List loan outcomes",
    description="Retrieve loan outcomes for the authenticated lender with optional date filtering.",
)
async def list_outcomes(
    request: Request,
    start_date: Optional[datetime] = Query(
        default=None,
        description="Filter outcomes from this date (inclusive)",
    ),
    end_date: Optional[datetime] = Query(
        default=None,
        description="Filter outcomes until this date (inclusive)",
    ),
    lender: LenderClient = Depends(authenticate_lender),
    outcome_service: OutcomeService = Depends(get_outcome_service),
):
    """
    GET /v1/outcomes — List loan outcomes for the authenticated lender.
    """
    trace_id = getattr(request.state, "trace_id", generate_trace_id())

    try:
        outcomes = await outcome_service.get_outcomes_for_lender(
            lender_id=lender.id,
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as e:
        logger.error(f"Outcome listing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                code=ErrorCodes.INTERNAL_ERROR,
                message=str(e),
                trace_id=trace_id,
            ).model_dump(),
        )

    return OutcomeHistoryResponse(
        outcomes=outcomes,
        total=len(outcomes),
    )
