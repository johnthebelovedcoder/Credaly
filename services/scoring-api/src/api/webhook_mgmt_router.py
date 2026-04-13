"""
Webhook Management Router — /v1/webhooks
Per PRD FR-035, US-006: Webhook subscriptions and delivery tracking.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db
from src.schemas import (
    CreateWebhookRequest,
    ErrorResponse,
    WebhookDeliveryInfo,
    WebhookInfo,
)
from src.services.webhook.service import WebhookService

router = APIRouter(prefix="/webhooks", tags=["Webhook Management"])


@router.get(
    "",
    response_model=list[WebhookInfo],
    responses={401: {"model": ErrorResponse}},
    summary="List all webhook subscriptions",
    description="Retrieve all webhook subscriptions.",
)
async def list_webhooks(
    db: AsyncSession = Depends(get_db),
):
    """GET /v1/webhooks — List all webhook subscriptions."""
    service = WebhookService(db)
    return await service.get_webhooks()


@router.post(
    "",
    response_model=WebhookInfo,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
    summary="Create a webhook subscription",
    description="Create a new webhook subscription for event notifications.",
)
async def create_webhook(
    request: CreateWebhookRequest,
    db: AsyncSession = Depends(get_db),
):
    """POST /v1/webhooks — Create webhook."""
    service = WebhookService(db)
    
    try:
        webhook_info = await service.create_webhook(
            url=request.url,
            events=request.events,
        )
        
        return webhook_info
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                code="INVALID_WEBHOOK_CONFIG",
                message=str(e),
                trace_id="unknown",
            ).model_dump(),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                code="WEBHOOK_CREATION_FAILED",
                message=str(e),
                trace_id="unknown",
            ).model_dump(),
        )


@router.delete(
    "/{webhook_id}",
    responses={404: {"model": ErrorResponse}},
    summary="Delete a webhook subscription",
    description="Remove a webhook subscription.",
)
async def delete_webhook(
    webhook_id: str,
    db: AsyncSession = Depends(get_db),
):
    """DELETE /v1/webhooks/:id — Delete webhook."""
    service = WebhookService(db)
    
    try:
        await service.delete_webhook(webhook_id)
        
        return {
            "success": True,
            "message": f"Webhook '{webhook_id}' has been deleted",
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                code="WEBHOOK_NOT_FOUND",
                message=str(e),
                trace_id="unknown",
            ).model_dump(),
        )


@router.post(
    "/{webhook_id}/test",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Test a webhook",
    description="Send a test ping event to the webhook endpoint.",
)
async def test_webhook(
    webhook_id: str,
    db: AsyncSession = Depends(get_db),
):
    """POST /v1/webhooks/:id/test — Test webhook."""
    service = WebhookService(db)
    
    try:
        result = await service.test_webhook(webhook_id)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                code="WEBHOOK_NOT_FOUND",
                message=str(e),
                trace_id="unknown",
            ).model_dump(),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                code="WEBHOOK_TEST_FAILED",
                message=str(e),
                trace_id="unknown",
            ).model_dump(),
        )


@router.get(
    "/{webhook_id}/deliveries",
    response_model=list[WebhookDeliveryInfo],
    responses={404: {"model": ErrorResponse}},
    summary="Get webhook delivery history",
    description="Retrieve the last 100 delivery attempts for a webhook.",
)
async def get_webhook_deliveries(
    webhook_id: str,
    db: AsyncSession = Depends(get_db),
):
    """GET /v1/webhooks/:id/deliveries — Get webhook deliveries."""
    service = WebhookService(db)
    
    try:
        deliveries = await service.get_webhook_deliveries(webhook_id)
        return deliveries
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                code="WEBHOOK_NOT_FOUND",
                message=str(e),
                trace_id="unknown",
            ).model_dump(),
        )


@router.post(
    "/deliveries/{delivery_id}/replay",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Replay a failed webhook delivery",
    description="Queue a failed webhook delivery for retry.",
)
async def replay_webhook_delivery(
    delivery_id: str,
    db: AsyncSession = Depends(get_db),
):
    """POST /v1/webhooks/deliveries/:id/replay — Replay webhook delivery."""
    service = WebhookService(db)
    
    try:
        result = await service.replay_webhook_delivery(delivery_id)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                code="DELIVERY_NOT_FOUND",
                message=str(e),
                trace_id="unknown",
            ).model_dump(),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                code="REPLAY_FAILED",
                message=str(e),
                trace_id="unknown",
            ).model_dump(),
        )
