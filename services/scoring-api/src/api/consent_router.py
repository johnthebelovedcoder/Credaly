"""
Consent API Router — POST /v1/consent, DELETE /v1/consent/{token_id}, GET /v1/consent/{bvn}/status.
Per PRD FR-011 through FR-019.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status

from src.api.dependencies import get_consent_service
from src.core.security import generate_trace_id
from src.schemas import (
    ConsentGrantRequest,
    ConsentResponse,
    ConsentStatusResponse,
    ConsentWithdrawRequest,
    ConsentWithdrawResponse,
    ErrorCodes,
    ErrorResponse,
)
from src.services.consent.service import ConsentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/consent", tags=["Consent"])


@router.post(
    "",
    response_model=ConsentResponse,
    responses={
        400: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
    summary="Grant consent for a data category",
    description=
        "Grant granular consent for a specific data category. "
        "Each category requires separate consent. PRD FR-011, FR-012.",
)
async def grant_consent(
    request_body: ConsentGrantRequest,
    request: Request,
    consent_service: ConsentService = Depends(get_consent_service),
):
    """
    POST /v1/consent — Grant consent for a data category. PRD FR-011, FR-012.
    """
    trace_id = getattr(request.state, "trace_id", generate_trace_id())

    try:
        result = await consent_service.grant_consent(request_body)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=ErrorResponse(
                code="CONSENT_EXISTS",
                message=str(e),
                trace_id=trace_id,
            ).model_dump(),
        )
    except Exception as e:
        logger.error(f"Consent grant failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                code=ErrorCodes.INTERNAL_ERROR,
                message=str(e),
                trace_id=trace_id,
            ).model_dump(),
        )

    return result


@router.delete(
    "/{consent_id}",
    response_model=ConsentWithdrawResponse,
    responses={
        404: {"model": ErrorResponse},
    },
    summary="Withdraw consent for a data category",
    description=
        "Withdraw previously granted consent. Triggers cascade: "
        "stop ingestion, flag features, notify lenders. PRD FR-014.",
)
async def withdraw_consent(
    consent_id: str,
    request: Request,
    body: ConsentWithdrawRequest = ConsentWithdrawRequest(),
    consent_service: ConsentService = Depends(get_consent_service),
):
    """DELETE /v1/consent/{token_id} — Withdraw consent. PRD FR-014."""
    trace_id = getattr(request.state, "trace_id", generate_trace_id())

    try:
        result = await consent_service.withdraw_consent(
            consent_id=consent_id,
            ip_address=request.client.host if request.client else None,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                code=ErrorCodes.NOT_FOUND,
                message=str(e),
                trace_id=trace_id,
            ).model_dump(),
        )
    except Exception as e:
        logger.error(f"Consent withdrawal failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                code=ErrorCodes.INTERNAL_ERROR,
                message=str(e),
                trace_id=trace_id,
            ).model_dump(),
        )

    return result


@router.get(
    "/{bvn}/status",
    response_model=ConsentStatusResponse,
    summary="Check borrower consent status",
    description="Return active consent status for all data categories.",
)
async def check_consent_status(
    bvn: str,
    consent_service: ConsentService = Depends(get_consent_service),
):
    """GET /v1/consent/{bvn}/status — Check per-category consent status."""
    trace_id = generate_trace_id()

    try:
        result = await consent_service.check_consent_status(bvn)
    except Exception as e:
        logger.error(f"Consent status check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                code=ErrorCodes.INTERNAL_ERROR,
                message=str(e),
                trace_id=trace_id,
            ).model_dump(),
        )

    return result
