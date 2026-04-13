"""
Outcome Service — handles repayment outcome submission from lenders.
Per PRD Section 8.2 and FR-030.

Outcomes feed into model retraining ground truth.
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.security import hash_bvn
from src.models import LoanOutcome

logger = logging.getLogger(__name__)


class OutcomeService:
    """Business logic for outcome submission and management. PRD FR-030."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def submit_outcome(
        self,
        loan_id: str,
        bvn: str,
        lender_id: str,
        disbursement_date: datetime,
        due_date: datetime,
        loan_amount_ngn: int,
        outcome: str,
        outcome_date: datetime,
        score_at_origination: int,
    ) -> dict:
        """
        Submit a loan repayment outcome. PRD Section 8.2.
        Accepted outcomes: REPAID_ON_TIME, REPAID_LATE, DEFAULTED, RESTRUCTURED, WRITTEN_OFF.
        """
        # Check for duplicate
        existing = await self.db.execute(
            select(LoanOutcome).where(LoanOutcome.loan_id == loan_id)
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"Outcome for loan_id '{loan_id}' already exists")

        bvn_hash = hash_bvn(bvn)

        loan_outcome = LoanOutcome(
            loan_id=loan_id,
            borrower_bvn_hash=bvn_hash,
            lender_id=lender_id,
            disbursement_date=disbursement_date,
            due_date=due_date,
            loan_amount_ngn=loan_amount_ngn,
            outcome=outcome,
            outcome_date=outcome_date,
            score_at_origination=score_at_origination,
        )
        self.db.add(loan_outcome)
        await self.db.flush()

        return {
            "loan_id": loan_id,
            "status": "received",
            "message": "Outcome recorded successfully",
        }

    async def get_outcomes_for_lender(
        self,
        lender_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list:
        """Retrieve outcomes for a specific lender."""
        stmt = select(LoanOutcome).where(LoanOutcome.lender_id == lender_id)
        if start_date:
            stmt = stmt.where(LoanOutcome.outcome_date >= start_date)
        if end_date:
            stmt = stmt.where(LoanOutcome.outcome_date <= end_date)
        stmt = stmt.order_by(LoanOutcome.outcome_date.desc())

        result = await self.db.execute(stmt)
        outcomes = result.scalars().all()

        return [
            {
                "loan_id": o.loan_id,
                "borrower_bvn_hash": o.borrower_bvn_hash,
                "lender_id": o.lender_id,
                "disbursement_date": o.disbursement_date,
                "due_date": o.due_date,
                "loan_amount_ngn": o.loan_amount_ngn,
                "outcome": o.outcome,
                "outcome_date": o.outcome_date,
                "score_at_origination": o.score_at_origination,
            }
            for o in outcomes
        ]

    async def get_retraining_dataset(
        self,
        min_records: int = 1000,
    ) -> list:
        """
        Compile a dataset for model retraining from loan outcomes.
        PRD FR-030: outcomes are ground truth for retraining.
        """
        stmt = (
            select(LoanOutcome)
            .order_by(LoanOutcome.outcome_date.desc())
            .limit(max(min_records, 10000))
        )
        result = await self.db.execute(stmt)
        outcomes = result.scalars().all()

        return [
            {
                "loan_id": o.loan_id,
                "bvn_hash": o.borrower_bvn_hash,
                "outcome_label": o.outcome,
                "outcome_numeric": self._outcome_to_numeric(o.outcome),
                "score_at_origination": o.score_at_origination,
                "loan_amount_ngn": o.loan_amount_ngn,
                "loan_tenure_days": (o.due_date - o.disbursement_date).days,
            }
            for o in outcomes
        ]

    @staticmethod
    def _outcome_to_numeric(outcome: str) -> int:
        """Convert outcome label to numeric for ML training."""
        mapping = {
            "REPAID_ON_TIME": 1,
            "REPAID_LATE": 0,
            "DEFAULTED": -1,
            "RESTRUCTURED": 0,
            "WRITTEN_OFF": -1,
        }
        return mapping.get(outcome, 0)
