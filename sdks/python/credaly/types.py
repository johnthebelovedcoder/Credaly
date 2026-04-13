"""Credaly SDK — strongly typed data classes for API responses."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass(frozen=True)
class ConfidenceInterval:
    lower: int
    upper: int
    level: str  # "95%"


@dataclass(frozen=True)
class ScoreResult:
    """Response from POST /v1/score."""
    score: int
    confidence_interval: ConfidenceInterval
    confidence_band: str  # HIGH | MEDIUM | LOW
    data_coverage_pct: float
    positive_factors: List[str]
    negative_factors: List[str]
    consent_token_ref: Optional[str]
    model_version: str
    computed_at: datetime
    trace_id: str


@dataclass(frozen=True)
class ScoreHistoryEntry:
    score: int
    confidence_band: str
    data_coverage_pct: float
    model_version: str
    computed_at: datetime


@dataclass(frozen=True)
class ScoreHistoryResult:
    """Response from GET /v1/score/{bvn}/history."""
    bvn_hash: str
    scores: List[ScoreHistoryEntry]


@dataclass(frozen=True)
class ConsentResult:
    """Response from POST /v1/consent."""
    consent_id: str
    borrower_bvn_hash: str
    data_category: str
    purpose: str
    authorized_lenders: List[str]
    expiry_at: Optional[datetime]
    is_active: bool
    token_signature: str
    created_at: datetime


@dataclass(frozen=True)
class ConsentStatusEntry:
    data_category: str
    is_active: bool
    purpose: str
    expiry_at: Optional[datetime]
    granted_at: datetime


@dataclass(frozen=True)
class ConsentStatusResult:
    """Response from GET /v1/consent/{bvn}/status."""
    borrower_bvn_hash: str
    consents: List[ConsentStatusEntry]
    minimum_consent_met: bool


@dataclass(frozen=True)
class ConsentWithdrawResult:
    """Response from DELETE /v1/consent/{consent_id}."""
    consent_id: str
    status: str
    withdrawn_at: datetime
    downstream_lenders_notified: List[str]


@dataclass(frozen=True)
class OutcomeResult:
    """Response from POST /v1/outcomes."""
    loan_id: str
    status: str
    message: str


@dataclass(frozen=True)
class SubjectDataResult:
    """Response from GET /v1/subject/{bvn}/data (DSAR)."""
    bvn_hash: str
    profile: dict
    consent_records: List[dict]
    feature_summary: List[dict]
    score_history: List[dict]
    compiled_at: datetime
