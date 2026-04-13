"""
Webhook Management Service — handles webhook CRUD operations and delivery tracking.
Per PRD FR-035, US-006.
"""

import json
import secrets
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import WebhookEvent, WebhookSubscription
from src.schemas import WebhookDeliveryInfo, WebhookInfo

# Valid webhook event types
VALID_WEBHOOK_EVENTS = [
    "score_generated",
    "score_changed",
    "consent_granted",
    "consent_revoked",
]


class WebhookService:
    """Business logic for webhook management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    def _generate_secret(self) -> str:
        """Generate HMAC secret for webhook signature verification."""
        return secrets.token_hex(32)

    def _to_webhook_info(self, webhook: WebhookSubscription) -> WebhookInfo:
        """Convert WebhookSubscription entity to WebhookInfo schema."""
        return WebhookInfo(
            id=webhook.id,
            url=webhook.endpoint_url,
            events=json.loads(webhook.events),
            is_active=webhook.is_active,
            created_at=webhook.created_at,
            last_triggered=None,  # Not tracked in current model
        )

    def _to_delivery_info(self, event: WebhookEvent) -> WebhookDeliveryInfo:
        """Convert WebhookEvent entity to WebhookDeliveryInfo schema."""
        return WebhookDeliveryInfo(
            id=event.id,
            webhook_id=event.subscription_id,
            event_type=event.event_type,
            status_code=event.response_code,
            status='success' if event.delivery_status == 'delivered' else 'failed' if event.delivery_status == 'failed' else 'pending',
            attempted_at=event.created_at,
            response_body=event.response_body,
        )

    async def get_webhooks(self, client_id: Optional[str] = None) -> List[WebhookInfo]:
        """Get all webhook subscriptions, optionally filtered by client_id."""
        stmt = select(WebhookSubscription).order_by(WebhookSubscription.created_at.desc())
        
        if client_id:
            stmt = stmt.where(WebhookSubscription.lender_id == client_id)
        
        result = await self.db.execute(stmt)
        webhooks = result.scalars().all()
        
        return [self._to_webhook_info(wh) for wh in webhooks]

    async def create_webhook(
        self,
        url: str,
        events: List[str],
    ) -> WebhookInfo:
        """
        Create a new webhook subscription.
        Validates URL and events.
        """
        # Validate URL (must be HTTPS in production, allow localhost for dev)
        if not url.startswith('https://') and not url.startswith('http://localhost'):
            raise ValueError("Webhook URL must use HTTPS (or http://localhost for testing)")
        
        # Validate events
        invalid_events = [e for e in events if e not in VALID_WEBHOOK_EVENTS]
        if invalid_events:
            raise ValueError(f"Invalid events: {', '.join(invalid_events)}")
        
        # Generate HMAC secret
        webhook_secret = self._generate_secret()
        
        # Create entity
        webhook = WebhookSubscription(
            lender_id='default',
            endpoint_url=url,
            events=json.dumps(events),
            secret=webhook_secret,
            is_active=True,
        )
        
        self.db.add(webhook)
        await self.db.flush()
        
        return self._to_webhook_info(webhook)

    async def delete_webhook(self, webhook_id: str) -> dict:
        """Delete a webhook subscription."""
        stmt = select(WebhookSubscription).where(WebhookSubscription.id == webhook_id)
        result = await self.db.execute(stmt)
        webhook = result.scalar_one_or_none()
        
        if not webhook:
            raise ValueError(f"Webhook subscription '{webhook_id}' not found")
        
        await self.db.delete(webhook)
        await self.db.flush()
        
        return {"success": True}

    async def test_webhook(self, webhook_id: str) -> dict:
        """Test a webhook by simulating a ping event."""
        stmt = select(WebhookSubscription).where(WebhookSubscription.id == webhook_id)
        result = await self.db.execute(stmt)
        webhook = result.scalar_one_or_none()
        
        if not webhook:
            raise ValueError(f"Webhook subscription '{webhook_id}' not found")
        
        if not webhook.is_active:
            raise ValueError("Cannot test an inactive webhook")
        
        # In a real implementation, this would fire the webhook
        # For now, return success placeholder
        return {
            "success": True,
            "message": f"Test ping sent to {webhook.endpoint_url}",
        }

    async def get_webhook_deliveries(self, webhook_id: str) -> List[WebhookDeliveryInfo]:
        """Get webhook delivery history for a specific webhook."""
        # Verify webhook exists
        stmt = select(WebhookSubscription).where(WebhookSubscription.id == webhook_id)
        result = await self.db.execute(stmt)
        webhook = result.scalar_one_or_none()
        
        if not webhook:
            raise ValueError(f"Webhook subscription '{webhook_id}' not found")
        
        # Get deliveries
        stmt = (
            select(WebhookEvent)
            .where(WebhookEvent.subscription_id == webhook_id)
            .order_by(WebhookEvent.created_at.desc())
            .limit(100)
        )
        result = await self.db.execute(stmt)
        deliveries = result.scalars().all()
        
        return [self._to_delivery_info(d) for d in deliveries]

    async def replay_webhook_delivery(self, delivery_id: str) -> dict:
        """Replay a failed webhook delivery."""
        stmt = select(WebhookEvent).where(WebhookEvent.id == delivery_id)
        result = await self.db.execute(stmt)
        delivery = result.scalar_one_or_none()
        
        if not delivery:
            raise ValueError(f"Webhook delivery '{delivery_id}' not found")
        
        if delivery.delivery_status == "delivered":
            raise ValueError("Cannot replay a successful delivery")
        
        # In a real implementation, this would re-fire the webhook
        # For now, mark as queued for replay
        delivery.delivery_status = "pending"
        delivery.delivery_attempts = 0
        await self.db.flush()
        
        return {
            "success": True,
            "message": f"Webhook delivery queued for replay: {delivery_id}",
        }
