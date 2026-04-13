"""
Webhook Dispatcher — sends outbound webhook events to lender endpoints
with retry logic, exponential backoff, and HMAC signature signing.
Per PRD FR-035, US-006.
"""

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.webhook_validation import validate_webhook_url, WebhookURLValidationError
from src.models import WebhookEvent, WebhookSubscription

logger = logging.getLogger(__name__)


class WebhookDispatcher:
    """
    Dispatches webhook events to subscribed lender endpoints.
    Features:
      - HMAC signature signing (X-Webhook-Signature header)
      - Retry with exponential backoff (3 attempts)
      - Delivery status tracking in DB
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.client = httpx.AsyncClient(
            timeout=settings.webhook_timeout_seconds,
            headers={"Content-Type": "application/json"},
        )

    async def close(self):
        await self.client.aclose()

    def _sign_payload(self, payload: str, secret: str) -> str:
        """Generate HMAC-SHA256 signature of the webhook payload."""
        return hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()

    async def dispatch(
        self,
        event_type: str,
        payload: Dict[str, Any],
        subscription_ids: Optional[List[str]] = None,
    ) -> int:
        """
        Dispatch a webhook event to all matching subscriptions.
        Returns the number of webhooks attempted.
        """
        # Find matching subscriptions
        stmt = select(WebhookSubscription).where(
            WebhookSubscription.is_active == True,
        )
        if subscription_ids:
            stmt = stmt.where(WebhookSubscription.id.in_(subscription_ids))

        result = await self.db.execute(stmt)
        subscriptions = result.scalars().all()

        dispatched = 0
        for sub in subscriptions:
            # Check if this subscription is subscribed to this event type
            events = json.loads(sub.events) if sub.events else []
            if events and event_type not in events:
                continue

            # Validate webhook URL — SSRF protection
            try:
                validate_webhook_url(sub.endpoint_url)
            except WebhookURLValidationError as e:
                logger.error(
                    f"Webhook URL validation failed for subscription {sub.id}: {e}"
                )
                continue

            # Create webhook event record
            payload_json = json.dumps({
                "event_type": event_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": payload,
            })

            webhook_event = WebhookEvent(
                subscription_id=sub.id,
                event_type=event_type,
                payload=payload_json,
                delivery_status="pending",
            )
            self.db.add(webhook_event)
            await self.db.flush()

            # Send with retries
            success = await self._send_with_retry(
                url=sub.endpoint_url,
                payload=payload_json,
                secret=sub.secret,
                webhook_event_id=webhook_event.id,
            )
            if success:
                dispatched += 1

        return dispatched

    async def _send_with_retry(
        self,
        url: str,
        payload: str,
        secret: str,
        webhook_event_id: str,
    ) -> bool:
        """Send webhook with exponential backoff retry."""
        signature = self._sign_payload(payload, secret)
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": f"sha256={signature}",
            "X-Webhook-Event-Id": webhook_event_id,
        }

        for attempt in range(settings.webhook_max_retries):
            try:
                response = await self.client.post(url, content=payload, headers=headers)

                # Update event record
                stmt = select(WebhookEvent).where(WebhookEvent.id == webhook_event_id)
                result = await self.db.execute(stmt)
                event = result.scalar_one_or_none()
                if event:
                    event.delivery_status = "delivered" if response.status_code < 400 else "failed"
                    event.delivery_attempts = attempt + 1
                    event.last_attempt_at = datetime.now(timezone.utc)
                    event.response_code = response.status_code
                    event.response_body = response.text[:1000]  # Truncate
                await self.db.flush()

                if response.status_code < 400:
                    logger.info(f"Webhook delivered to {url} (attempt {attempt + 1})")
                    return True

                logger.warning(
                    f"Webhook returned {response.status_code} for {url} "
                    f"(attempt {attempt + 1}/{settings.webhook_max_retries})"
                )

            except Exception as e:
                logger.error(
                    f"Webhook delivery failed to {url} "
                    f"(attempt {attempt + 1}/{settings.webhook_max_retries}): {e}"
                )

                # Update attempt count on failure
                stmt = select(WebhookEvent).where(WebhookEvent.id == webhook_event_id)
                result = await self.db.execute(stmt)
                event = result.scalar_one_or_none()
                if event:
                    event.delivery_attempts = attempt + 1
                    event.last_attempt_at = datetime.now(timezone.utc)
                    event.delivery_status = "failed"
                await self.db.flush()

            # Backoff before retry
            if attempt < settings.webhook_max_retries - 1:
                import asyncio
                backoff = settings.webhook_retry_backoff_seconds * (2 ** attempt)
                await asyncio.sleep(backoff)

        return False

    async def check_score_change_and_dispatch(
        self,
        bvn_hash: str,
        new_score: int,
        old_score: Optional[int] = None,
        old_band: Optional[str] = None,
        new_band: Optional[str] = None,
    ) -> int:
        """
        Check if a score has changed materially and dispatch webhook.
        Per US-006: fires when score changes by > 40 points or confidence band changes.
        """
        score_changed = old_score is not None and abs(new_score - old_score) > 40
        band_changed = old_band is not None and new_band is not None and old_band != new_band

        if not score_changed and not band_changed:
            return 0

        event_type = "score_material_change"
        payload = {
            "bvn_hash": bvn_hash,
            "new_score": new_score,
            "old_score": old_score,
            "new_confidence_band": new_band,
            "old_confidence_band": old_band,
            "reason": "score_change" if score_changed else "band_change",
        }

        return await self.dispatch(event_type, payload)
