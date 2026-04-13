"""
Human Review Request Service — borrowers can request human review of
automated credit decisions. Per PRD US-015, NDPA Section 34.

Workflow:
  1. Borrower submits review request with loan/score reference
  2. Request is persisted with 5-business-day SLA
  3. Lender is notified via webhook
  4. Review is completed or escalates if SLA breached
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import hash_bvn
from src.models import HumanReviewRequest

logger = logging.getLogger(__name__)


class HumanReviewService:
    """
    Manages human review requests for automated credit decisions.
    PRD US-015, NDPA Section 34.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_review_request(
        self,
        bvn: str,
        reason: str,
        lender_id: str,
        loan_id: Optional[str] = None,
        score_at_decision: Optional[int] = None,
        decision_outcome: Optional[str] = None,
    ) -> HumanReviewRequest:
        """
        Create a human review request.
        SLA: 5 business days from creation.
        """
        bvn_hash = hash_bvn(bvn)
        review_id = f"rev_{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc)
        # 5 business days = 7 calendar days (conservative)
        sla_deadline = now + timedelta(days=7)

        review = HumanReviewRequest(
            id=review_id,
            borrower_bvn_hash=bvn_hash,
            loan_id=loan_id,
            score_at_decision=score_at_decision,
            decision_outcome=decision_outcome,
            reason=reason,
            lender_id=lender_id,
            status="pending",
            sla_deadline=sla_deadline,
        )

        self.db.add(review)
        await self.db.flush()

        logger.info(
            "Human review request created",
            review_id=review_id,
            borrower_bvn_hash=bvn_hash,
            lender_id=lender_id,
            sla_deadline=sla_deadline.isoformat(),
        )

        # Notify lender via webhook (async — don't block creation)
        await self._notify_lender_of_review(lender_id, review_id, bvn_hash)

        return review

    async def get_review_request(self, review_id: str) -> Optional[HumanReviewRequest]:
        """Get a review request by ID."""
        stmt = select(HumanReviewRequest).where(HumanReviewRequest.id == review_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_pending_reviews(self, lender_id: Optional[str] = None) -> List[HumanReviewRequest]:
        """Get all pending reviews, optionally filtered by lender."""
        stmt = (
            select(HumanReviewRequest)
            .where(HumanReviewRequest.status == "pending")
            .order_by(HumanReviewRequest.created_at.asc())
        )
        if lender_id:
            stmt = stmt.where(HumanReviewRequest.lender_id == lender_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def complete_review(
        self,
        review_id: str,
        outcome: str,
        reviewer_notes: Optional[str] = None,
    ) -> HumanReviewRequest:
        """Mark a review as completed with outcome."""
        valid_outcomes = ["upheld", "overturned", "partially_overturned", "insufficient_data"]
        if outcome not in valid_outcomes:
            raise ValueError(f"Invalid outcome '{outcome}'. Must be one of: {valid_outcomes}")

        stmt = select(HumanReviewRequest).where(HumanReviewRequest.id == review_id)
        result = await self.db.execute(stmt)
        review = result.scalar_one_or_none()
        if not review:
            raise ValueError(f"Review request '{review_id}' not found")

        review.status = "completed"
        review.outcome = outcome
        review.reviewer_notes = reviewer_notes
        review.completed_at = datetime.now(timezone.utc)
        await self.db.flush()

        logger.info(
            "Human review completed",
            review_id=review_id,
            outcome=outcome,
        )

        return review

    async def update_review_status(
        self,
        review_id: str,
        status: str,
        reviewer_notes: Optional[str] = None,
    ) -> HumanReviewRequest:
        """Update the status of a review (e.g., pending -> in_review)."""
        valid_statuses = ["pending", "in_review", "completed", "escalated", "closed"]
        if status not in valid_statuses:
            raise ValueError(f"Invalid status '{status}'. Must be one of: {valid_statuses}")

        stmt = select(HumanReviewRequest).where(HumanReviewRequest.id == review_id)
        result = await self.db.execute(stmt)
        review = result.scalar_one_or_none()
        if not review:
            raise ValueError(f"Review request '{review_id}' not found")

        review.status = status
        if reviewer_notes:
            review.reviewer_notes = reviewer_notes
        await self.db.flush()

        return review

    async def check_sla_breaches(self) -> List[HumanReviewRequest]:
        """
        Find all reviews that have breached their SLA deadline.
        Should be called by a periodic job (every hour).
        """
        now = datetime.now(timezone.utc)
        stmt = (
            select(HumanReviewRequest)
            .where(
                HumanReviewRequest.status.notin_(["completed", "closed"]),
                HumanReviewRequest.sla_deadline < now,
            )
            .order_by(HumanReviewRequest.created_at.asc())
        )
        result = await self.db.execute(stmt)
        breached = list(result.scalars().all())

        # Escalate breached reviews
        for review in breached:
            if review.status != "escalated":
                review.status = "escalated"
                logger.warning(
                    "SLA breach detected — escalating review",
                    review_id=review.id,
                    lender_id=review.lender_id,
                    sla_deadline=review.sla_deadline.isoformat(),
                )

        if breached:
            await self.db.flush()

        return breached

    async def _notify_lender_of_review(
        self,
        lender_id: str,
        review_id: str,
        borrower_bvn_hash: str,
    ) -> None:
        """
        Notify lender of new human review request via webhook.
        This is async and non-blocking — failures are logged but don't prevent review creation.
        """
        try:
            from src.services.webhooks.service import WebhookDispatcher

            dispatcher = WebhookDispatcher(self.db)
            try:
                payload = {
                    "review_id": review_id,
                    "borrower_bvn_hash": borrower_bvn_hash,
                    "lender_id": lender_id,
                    "message": "A borrower has requested human review of an automated credit decision.",
                }
                await dispatcher.dispatch("human_review_requested", payload)
            finally:
                await dispatcher.close()
        except Exception as e:
            logger.warning(f"Failed to notify lender of review request: {e}")
