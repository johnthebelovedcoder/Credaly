"""
Sandbox Data Generator — generates synthetic borrower profiles for sandbox testing.
Per PRD US-008: 100 synthetic borrower profiles available in sandbox.
"""

import hashlib
import json
import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.security import hash_bvn
from src.models import (
    BorrowerProfile,
    CreditScore,
    FeatureSnapshot,
    ConsentRecord,
    LoanOutcome,
)


# Realistic Nigerian data distributions
SCORE_BUCKETS = [
    (300, 450, 0.05),   # Very poor
    (450, 550, 0.15),   # Poor
    (550, 650, 0.30),   # Fair
    (650, 750, 0.30),   # Good
    (750, 850, 0.20),   # Excellent
]

OUTCOMES = ["REPAID_ON_TIME", "REPAID_LATE", "DEFAULTED", "RESTRUCTURED"]
OUTCOME_WEIGHTS = [0.60, 0.15, 0.15, 0.10]  # Realistic distribution

FIRST_NAMES = [
    "Chinedu", "Ngozi", "Oluwaseun", "Adebayo", "Fatima", "Ibrahim",
    "Emeka", "Chioma", "Tunde", "Aisha", "Obi", "Nneka", "Segun",
    "Bukola", "Kelechi", "Amina", "Yemi", "Funke", "Kemi", "Dayo",
]

LAST_NAMES = [
    "Okafor", "Adeyemi", "Obi", "Bello", "Nwosu", "Ogunlade",
    "Eze", "Afolabi", "Onyekachi", "Musa", "Abubakar", "Oladipo",
    "Chukwu", "Akinwande", "Okonkwo", "Salami", "Nnamdi", "Balogun",
]

PHONE_PREFIXES = ["0803", "0806", "0810", "0813", "0816", "0901", "0902", "0903", "0906", "0913"]


def _weighted_score() -> int:
    """Generate a score based on realistic distribution."""
    r = random.random()
    cumulative = 0
    for low, high, weight in SCORE_BUCKETS:
        cumulative += weight
        if r <= cumulative:
            return random.randint(low, high)
    return random.randint(550, 700)


def _random_date(years_back: int = 3) -> datetime:
    """Generate a random date within the past N years."""
    days_ago = random.randint(0, years_back * 365)
    return datetime.now(timezone.utc) - timedelta(days=days_ago)


async def generate_sandbox_borrowers(
    db: AsyncSession,
    count: int = 100,
    lender_id: str = "lnd_sandbox",
) -> list[dict]:
    """
    Generate synthetic borrower profiles for sandbox testing.
    PRD US-008: 100 synthetic borrower profiles.
    """
    borrowers = []

    for i in range(count):
        # Generate BVN
        bvn = f"224{random.randint(10000000, 99999999)}"
        bvn_hash = hash_bvn(bvn)
        phone = f"+234{random.choice(PHONE_PREFIXES)}{random.randint(1000000, 9999999)}"

        # Create borrower profile
        profile = BorrowerProfile(
            id=f"brw_sbx_{uuid.uuid4().hex[:8]}",
            bvn_hash=bvn_hash,
            phone_hash=hashlib.sha256(phone.encode()).hexdigest(),
            data_coverage_pct=random.uniform(40, 95),
        )
        db.add(profile)

        # Create consent record (sandbox — no real consent needed)
        consent = ConsentRecord(
            id=f"cst_sbx_{uuid.uuid4().hex[:8]}",
            borrower_bvn_hash=bvn_hash,
            data_category="bureau",
            purpose="sandbox testing",
            authorized_lenders=json.dumps([lender_id]),
            token_signature="sandbox_signature",
        )
        db.add(consent)

        # Generate features
        base_score = _weighted_score()
        features = {
            "bureau_delinquency_flag": 1.0 if base_score < 500 else 0.0,
            "avg_bureau_score": float(base_score),
            "total_credit_accounts": float(random.randint(0, 8)),
            "debt_to_income_ratio": round(random.uniform(0.1, 0.8), 2),
            "credit_utilization_ratio": round(random.uniform(0.1, 0.9), 2),
            "oldest_account_age_months": float(random.randint(1, 120)),
            "recent_inquiries_6m": float(random.randint(0, 10)),
            "telco_consistency_index": round(random.uniform(0, 1), 2),
            "mobile_money_inflow_trend": round(random.uniform(0, 1), 2),
            "utility_payment_streak": float(random.randint(0, 24)),
        }

        for name, value in features.items():
            tier = "formal" if name in [
                "bureau_delinquency_flag", "avg_bureau_score",
                "total_credit_accounts", "debt_to_income_ratio",
                "credit_utilization_ratio", "oldest_account_age_months",
                "recent_inquiries_6m",
            ] else "alternative"

            feature = FeatureSnapshot(
                id=f"fet_sbx_{uuid.uuid4().hex[:8]}",
                borrower_bvn_hash=bvn_hash,
                feature_name=name,
                feature_value=value,
                source_tier=tier,
                computed_at=datetime.now(timezone.utc),
                data_snapshot_at=datetime.now(timezone.utc),
            )
            db.add(feature)

        # Generate credit score
        confidence_margin = max(10, int(80 - profile.data_coverage_pct))
        score = CreditScore(
            id=f"sco_sbx_{uuid.uuid4().hex[:8]}",
            borrower_bvn_hash=bvn_hash,
            score=base_score,
            confidence_lower=max(300, base_score - confidence_margin),
            confidence_upper=min(850, base_score + confidence_margin),
            confidence_band="HIGH" if profile.data_coverage_pct > 70 else "MEDIUM" if profile.data_coverage_pct > 40 else "LOW",
            data_coverage_pct=profile.data_coverage_pct,
            model_version="v1.0.0-sandbox",
            consent_token_ref=consent.id,
            trace_id=f"trc_sbx_{uuid.uuid4().hex[:6]}",
            positive_factors=json.dumps(["Sandbox borrower — no real factors"]),
            negative_factors=json.dumps(["Sandbox borrower — synthetic data"]),
        )
        db.add(score)

        borrowers.append({
            "bvn": bvn,
            "phone": phone,
            "score": base_score,
            "data_coverage_pct": profile.data_coverage_pct,
        })

    await db.flush()
    return borrowers


if __name__ == "__main__":
    import asyncio
    from src.core.database import async_session_factory

    async def main():
        async with async_session_factory() as session:
            borrowers = await generate_sandbox_borrowers(session, count=100)
            await session.commit()
            print(f"Generated {len(borrowers)} sandbox borrowers")
            for b in borrowers[:5]:
                print(f"  BVN: {b['bvn']} | Score: {b['score']} | Coverage: {b['data_coverage_pct']:.1f}%")

    asyncio.run(main())
