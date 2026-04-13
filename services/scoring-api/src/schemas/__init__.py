"""
Pydantic schemas for API request/response validation.
Mirrors PRD Section 8 — Core API Specifications.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


# ── Tier Configuration ────────────────────────────────────────────────

class TierEnum(str, Enum):
    formal = "formal"
    alternative = "alternative"
    psychographic = "psychographic"


# ── Score Request / Response ─────────────────────────────────────────

class ScoreRequest(BaseModel):
    """POST /v1/score request body — PRD Section 8.1."""
    bvn: str = Field(..., min_length=11, max_length=11, description="Bank Verification Number")
    phone: str = Field(..., description="Borrower phone number")
    lender_id: str = Field(..., description="Lender client ID")
    tier_config: List[TierEnum] = Field(
        default=[TierEnum.formal, TierEnum.alternative, TierEnum.psychographic],
        description="Data tiers to include in scoring",
    )
    loan_amount_ngn: Optional[int] = Field(default=None, ge=0)
    loan_tenure_days: Optional[int] = Field(default=None, gt=0)

    @field_validator("bvn")
    @classmethod
    def bvn_must_be_numeric(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("BVN must contain only digits")
        return v


class ConfidenceInterval(BaseModel):
    lower: int
    upper: int
    level: str = "95%"


class ScoreResponse(BaseModel):
    """POST /v1/score 200 OK response — PRD Section 8.1."""
    score: int = Field(..., ge=300, le=850)
    confidence_interval: ConfidenceInterval
    confidence_band: str  # HIGH | MEDIUM | LOW
    data_coverage_pct: float
    positive_factors: List[str]
    negative_factors: List[str]
    consent_token_ref: Optional[str] = None
    model_version: str
    computed_at: datetime
    trace_id: str


# ── Score History ─────────────────────────────────────────────────────

class ScoreHistoryEntry(BaseModel):
    score: int
    confidence_band: str
    data_coverage_pct: float
    model_version: str
    computed_at: datetime


class ScoreHistoryResponse(BaseModel):
    bvn_hash: str
    scores: List[ScoreHistoryEntry]


# ── Outcome Submission ────────────────────────────────────────────────

class OutcomeEnum(str, Enum):
    REPAID_ON_TIME = "REPAID_ON_TIME"
    REPAID_LATE = "REPAID_LATE"
    DEFAULTED = "DEFAULTED"
    RESTRUCTURED = "RESTRUCTURED"
    WRITTEN_OFF = "WRITTEN_OFF"


class OutcomeSubmission(BaseModel):
    """POST /v1/outcomes request body — PRD Section 8.2."""
    loan_id: str = Field(..., description="Unique loan identifier")
    bvn: str = Field(..., min_length=11, max_length=11)
    disbursement_date: datetime
    due_date: datetime
    loan_amount_ngn: int = Field(..., gt=0)
    outcome: OutcomeEnum
    outcome_date: datetime
    score_at_origination: int = Field(..., ge=300, le=850)

    @field_validator("bvn")
    @classmethod
    def bvn_must_be_numeric(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("BVN must contain only digits")
        return v


class OutcomeResponse(BaseModel):
    """POST /v1/outcomes 200 OK response."""
    loan_id: str
    status: str = "received"
    message: str = "Outcome recorded successfully"


class OutcomeHistoryEntry(BaseModel):
    """Single entry in outcome history response."""
    loan_id: str
    borrower_bvn_hash: str
    lender_id: str
    disbursement_date: datetime
    due_date: datetime
    loan_amount_ngn: int
    outcome: str
    outcome_date: datetime
    score_at_origination: int


class OutcomeHistoryResponse(BaseModel):
    """GET /v1/outcomes 200 OK response."""
    outcomes: List[OutcomeHistoryEntry]
    total: int


# ── Consent ───────────────────────────────────────────────────────────

class ConsentGrantRequest(BaseModel):
    """POST /v1/consent request body."""
    bvn: str = Field(..., min_length=11, max_length=11)
    phone: str = Field(..., description="Borrower phone number for identity linkage")
    data_category: str = Field(
        ..., description="Data category: bureau, bank, telco, mobile_money, utility, psychographic"
    )
    purpose: str = Field(..., max_length=500, description="Stated purpose of data collection")
    authorized_lenders: List[str] = Field(default_factory=list)
    expiry_date: Optional[datetime] = None
    policy_version: str = Field(default="1.0")
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class ConsentResponse(BaseModel):
    """POST /v1/consent 200 OK response."""
    consent_id: str
    borrower_bvn_hash: str
    data_category: str
    purpose: str
    authorized_lenders: List[str]
    expiry_at: Optional[datetime]
    is_active: bool
    token_signature: str
    created_at: datetime


class ConsentWithdrawRequest(BaseModel):
    """Used internally when a borrower withdraws consent."""
    reason: Optional[str] = None


class ConsentWithdrawResponse(BaseModel):
    consent_id: str
    status: str = "withdrawn"
    withdrawn_at: datetime
    downstream_lenders_notified: List[str]


# ── Data Subject Access Request (DSAR) ────────────────────────────────

class DataSubjectDataResponse(BaseModel):
    """GET /v1/subject/{bvn}/data response."""
    bvn_hash: str
    profile: dict
    consent_records: List[dict]
    feature_summary: List[dict]
    score_history: List[dict]
    compiled_at: datetime


# ── Consent Status Check ──────────────────────────────────────────────

class ConsentStatusEntry(BaseModel):
    data_category: str
    is_active: bool
    purpose: str
    expiry_at: Optional[datetime]
    granted_at: datetime


class ConsentStatusResponse(BaseModel):
    borrower_bvn_hash: str
    consents: List[ConsentStatusEntry]
    minimum_consent_met: bool


# ── Error Response ────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    """Standard error response — PRD Section 8.3."""
    code: str
    message: str
    trace_id: str
    docs_url: Optional[str] = None


# ── Error Codes (per PRD) ─────────────────────────────────────────────

class ErrorCodes:
    INSUFFICIENT_CONSENT = "INSUFFICIENT_CONSENT"
    INVALID_BVN = "INVALID_BVN"
    LENDER_NOT_FOUND = "LENDER_NOT_FOUND"
    LENDER_SUSPENDED = "LENDER_SUSPENDED"
    RATE_LIMITED = "RATE_LIMITED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    MODEL_ERROR = "MODEL_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    DUPLICATE_LOAN = "DUPLICATE_LOAN"


# ── API Key Management ────────────────────────────────────────────────

class CreateApiKeyRequest(BaseModel):
    """POST /v1/api-keys request body."""
    name: str = Field(..., description="User-defined label for the key")
    environment: str = Field(..., description="Environment: sandbox or production")


class ApiKeyInfo(BaseModel):
    """API key metadata response (never includes raw key or hash)."""
    id: str
    name: str
    key_prefix: str
    environment: str  # sandbox | production
    created_at: datetime
    last_used: Optional[datetime]
    is_active: bool
    ip_allowlist: List[str] = Field(default_factory=list)


class CreateApiKeyResponse(BaseModel):
    """POST /v1/api-keys 200 OK response."""
    key: ApiKeyInfo
    rawApiKey: str = Field(..., description="Raw API key — shown only once at creation")


class RotateApiKeyResponse(BaseModel):
    """POST /v1/api-keys/:id/rotate 200 OK response."""
    key: ApiKeyInfo
    rawApiKey: str = Field(..., description="New raw API key — shown only once")


# ── Webhook Management ───────────────────────────────────────────────

class CreateWebhookRequest(BaseModel):
    """POST /v1/webhooks request body."""
    url: str = Field(..., description="Webhook endpoint URL")
    events: List[str] = Field(..., description="Event types to subscribe to")


class WebhookInfo(BaseModel):
    """Webhook subscription metadata."""
    id: str
    url: str
    events: List[str]
    is_active: bool
    created_at: datetime
    last_triggered: Optional[datetime]


class WebhookDeliveryInfo(BaseModel):
    """Webhook delivery tracking info."""
    id: str
    webhook_id: str
    event_type: str
    status_code: Optional[int]
    status: str  # success | failed | pending
    attempted_at: datetime
    response_body: Optional[str]
