"""
Webhook Subscription API — lenders register webhook endpoints and choose events.
Per PRD FR-035, US-006.

Endpoints:
  POST   /v1/webhooks         — register webhook
  GET    /v1/webhooks         — list subscriptions
  GET    /v1/webhooks/{id}    — get subscription
  DELETE /v1/webhooks/{id}    — remove subscription
"""

import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_consent_service
from src.core.auth import authenticate_lender
from src.core.security import generate_trace_id
from src.core.webhook_validation import validate_webhook_url, WebhookURLValidationError
from src.models import LenderClient, WebhookSubscription
from src.core.database import get_db
from src.schemas import ErrorCodes, ErrorResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

VALID_WEBHOOK_EVENTS = [
    "score_material_change",
    "consent_withdrawn",
    "score_computed",
]


class WebhookSubscriptionRequest(BaseModel):
    endpoint_url: str
    events: List[str]
    secret: Optional[str] = None


class WebhookSubscriptionResponse:
    def __init__(self, sub: WebhookSubscription):
        self.id = sub.id
        self.lender_id = sub.lender_id
        self.endpoint_url = sub.endpoint_url
        self.events = sub.events
        self.is_active = sub.is_active
        self.created_at = sub.created_at


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
    summary="Register a webhook subscription",
    description="Register a webhook endpoint to receive score change and consent events. PRD FR-035.",
)
async def create_webhook_subscription(
    body: WebhookSubscriptionRequest,
    lender: LenderClient = Depends(authenticate_lender),
    db: AsyncSession = Depends(get_db),
):
    """POST /v1/webhooks — Register webhook subscription."""
    trace_id = generate_trace_id()

    # Validate URL — SSRF protection
    try:
        validate_webhook_url(body.endpoint_url)
    except WebhookURLValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                code="INVALID_WEBHOOK_URL",
                message=str(e),
                trace_id=trace_id,
                docs_url="https://docs.platform.com/errors/INVALID_WEBHOOK_URL",
            ).model_dump(),
        )

    # Validate events
    for event in body.events:
        if event not in VALID_WEBHOOK_EVENTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorResponse(
                    code="INVALID_EVENT",
                    message=f"Invalid event '{event}'. Must be one of: {VALID_WEBHOOK_EVENTS}",
                    trace_id=trace_id,
                ).model_dump(),
            )

    # Generate secret if not provided
    import secrets
    secret = body.secret or f"whsec_{secrets.token_hex(32)}"

    sub = WebhookSubscription(
        id=f"whs_{uuid.uuid4().hex[:10]}",
        lender_id=lender.id,
        endpoint_url=body.endpoint_url,
        events=str(body.events),  # Store as JSON-like string
        secret=secret,
        is_active=True,
    )
    db.add(sub)
    await db.flush()

    return {
        "id": sub.id,
        "lender_id": sub.lender_id,
        "endpoint_url": sub.endpoint_url,
        "events": body.events,
        "secret": secret,
        "is_active": sub.is_active,
        "created_at": sub.created_at,
    }


@router.get(
    "",
    summary="List webhook subscriptions",
    description="List all webhook subscriptions for the authenticated lender.",
)
async def list_webhook_subscriptions(
    lender: LenderClient = Depends(authenticate_lender),
    db: AsyncSession = Depends(get_db),
):
    """GET /v1/webhooks — List subscriptions."""
    stmt = select(WebhookSubscription).where(WebhookSubscription.lender_id == lender.id)
    result = await db.execute(stmt)
    subs = result.scalars().all()

    return [
        {
            "id": s.id,
            "lender_id": s.lender_id,
            "endpoint_url": s.endpoint_url,
            "events": s.events,
            "is_active": s.is_active,
            "created_at": s.created_at,
        }
        for s in subs
    ]


@router.get(
    "/{subscription_id}",
    summary="Get webhook subscription details",
    responses={404: {"model": ErrorResponse}},
)
async def get_webhook_subscription(
    subscription_id: str,
    lender: LenderClient = Depends(authenticate_lender),
    db: AsyncSession = Depends(get_db),
):
    """GET /v1/webhooks/{id} — Get subscription."""
    trace_id = generate_trace_id()

    stmt = select(WebhookSubscription).where(
        WebhookSubscription.id == subscription_id,
        WebhookSubscription.lender_id == lender.id,
    )
    result = await db.execute(stmt)
    sub = result.scalar_one_or_none()

    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                code=ErrorCodes.NOT_FOUND,
                message="Webhook subscription not found",
                trace_id=trace_id,
            ).model_dump(),
        )

    return {
        "id": sub.id,
        "lender_id": sub.lender_id,
        "endpoint_url": sub.endpoint_url,
        "events": sub.events,
        "is_active": sub.is_active,
        "created_at": sub.created_at,
    }


@router.delete(
    "/{subscription_id}",
    summary="Delete webhook subscription",
    responses={404: {"model": ErrorResponse}},
)
async def delete_webhook_subscription(
    subscription_id: str,
    lender: LenderClient = Depends(authenticate_lender),
    db: AsyncSession = Depends(get_db),
):
    """DELETE /v1/webhooks/{id} — Remove subscription."""
    trace_id = generate_trace_id()

    stmt = select(WebhookSubscription).where(
        WebhookSubscription.id == subscription_id,
        WebhookSubscription.lender_id == lender.id,
    )
    result = await db.execute(stmt)
    sub = result.scalar_one_or_none()

    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                code=ErrorCodes.NOT_FOUND,
                message="Webhook subscription not found",
                trace_id=trace_id,
            ).model_dump(),
        )

    sub.is_active = False
    await db.flush()

    return {"id": subscription_id, "status": "deleted"}
