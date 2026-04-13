"""
Credaly Python SDK — official client library for the Credaly Scoring API.

Usage:
    from credaly import CredalyClient

    client = CredalyClient(api_key="credaly_...")

    # Score a borrower
    result = client.score(
        bvn="22412345678",
        phone="+2348012345678",
        tier_config=["formal", "alternative"],
    )
    print(f"Score: {result.score}, Confidence: {result.confidence_band}")

    # Grant consent
    consent = client.grant_consent(
        bvn="22412345678",
        phone="+2348012345678",
        data_category="bureau",
        purpose="credit scoring",
    )

    # Submit outcome
    outcome = client.submit_outcome(
        loan_id="ln_123456",
        bvn="22412345678",
        outcome="REPAID_ON_TIME",
        ...
    )
"""

from credaly.client import CredalyClient
from credaly.types import (
    ScoreResult,
    ConsentResult,
    ConsentStatusResult,
    OutcomeResult,
    ScoreHistoryResult,
    SubjectDataResult,
)
from credaly.exceptions import (
    CredalyError,
    AuthenticationError,
    RateLimitError,
    ValidationError,
    ConsentError,
    ServerError,
)

__all__ = [
    "CredalyClient",
    "ScoreResult",
    "ConsentResult",
    "ConsentStatusResult",
    "OutcomeResult",
    "ScoreHistoryResult",
    "SubjectDataResult",
    "CredalyError",
    "AuthenticationError",
    "RateLimitError",
    "ValidationError",
    "ConsentError",
    "ServerError",
]

__version__ = "1.0.0"
