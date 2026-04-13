"""
Credaly SDK — main client class.

Usage:
    from credaly import CredalyClient

    client = CredalyClient(api_key="credaly_xxx")
    result = client.score(bvn="224...", phone="+234...")
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import List, Optional
from urllib.parse import urljoin

import httpx

from credaly.exceptions import (
    CredalyError,
    AuthenticationError,
    RateLimitError,
    ValidationError,
    ConsentError,
    NotFoundError,
    ServerError,
)
from credaly.types import (
    ScoreResult,
    ConfidenceInterval,
    ScoreHistoryResult,
    ScoreHistoryEntry,
    ConsentResult,
    ConsentStatusResult,
    ConsentStatusEntry,
    ConsentWithdrawResult,
    OutcomeResult,
    SubjectDataResult,
)

DEFAULT_BASE_URL = "https://api.credaly.com"
DEFAULT_TIMEOUT = 30.0  # seconds
DEFAULT_MAX_RETRIES = 3

OUTCOME_VALUES = {"REPAID_ON_TIME", "REPAID_LATE", "DEFAULTED", "RESTRUCTURED", "WRITTEN_OFF"}
TIER_VALUES = {"formal", "alternative", "psychographic"}
CONSENT_CATEGORIES = {"bureau", "bank", "telco", "mobile_money", "utility", "psychographic"}


class CredalyClient:
    """
    Client for the Credaly Scoring API.

    Args:
        api_key: Your Credaly API key (sandbox or production).
        base_url: API base URL. Defaults to production.
        timeout: Request timeout in seconds. Default 30.
        max_retries: Number of retries on transient errors. Default 3.
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ):
        if not api_key or not api_key.startswith("credaly_"):
            raise ValueError("api_key must be a valid Credaly API key (starts with 'credaly_')")

        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries
        self._client = httpx.Client(
            base_url=self._base_url,
            headers={
                "X-API-Key": self._api_key,
                "Content-Type": "application/json",
                "User-Agent": f"credaly-python-sdk/1.0.0",
            },
            timeout=self._timeout,
        )

    # ── Internal helpers ────────────────────────────────────────────────

    def _parse_datetime(self, value: Optional[str]) -> Optional[datetime]:
        if value is None:
            return None
        # Handle both ISO 8601 with and without timezone
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)

    def _request(self, method: str, path: str, **kwargs) -> dict:
        """
        Make an HTTP request with automatic error mapping.
        All errors are raised as typed exceptions.
        """
        for attempt in range(self._max_retries):
            try:
                response = self._client.request(method, path, **kwargs)
            except httpx.ConnectTimeout:
                if attempt == self._max_retries - 1:
                    raise ServerError(
                        f"Connection timeout after {self._max_retries} attempts",
                        code="CONNECTION_TIMEOUT",
                    )
                continue

            # Success
            if response.status_code == 200 or response.status_code == 201:
                return response.json()

            # Error mapping
            try:
                error_body = response.json()
                error = error_body.get("error", {})
                code = error.get("code", "UNKNOWN")
                message = error.get("message", response.text)
                trace_id = error.get("trace_id")
            except (json.JSONDecodeError, KeyError):
                code = "UNKNOWN"
                message = response.text
                trace_id = None

            if response.status_code == 401 or response.status_code == 403:
                raise AuthenticationError(message, code=code, trace_id=trace_id)
            elif response.status_code == 422 or response.status_code == 400:
                raise ValidationError(message, code=code, trace_id=trace_id)
            elif response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                raise RateLimitError(message, retry_after=retry_after, code=code, trace_id=trace_id)
            elif response.status_code == 409:
                raise ConsentError(message, code=code, trace_id=trace_id)
            elif response.status_code == 404:
                raise NotFoundError(message, code=code, trace_id=trace_id)
            elif response.status_code >= 500:
                if attempt < self._max_retries - 1:
                    import time
                    time.sleep(2 ** attempt)
                    continue
                raise ServerError(message, code=code, trace_id=trace_id)
            else:
                raise CredalyError(message, code=code, trace_id=trace_id)

        raise ServerError("Request failed after maximum retries", code="MAX_RETRIES_EXCEEDED")

    def close(self):
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    # ── Scoring ─────────────────────────────────────────────────────────

    def score(
        self,
        *,
        bvn: str,
        phone: str,
        tier_config: Optional[List[str]] = None,
        loan_amount_ngn: Optional[int] = None,
        loan_tenure_days: Optional[int] = None,
    ) -> ScoreResult:
        """
        Compute a credit score for a borrower. PRD Section 8.1.

        Args:
            bvn: Bank Verification Number (11 digits).
            phone: Borrower phone number.
            tier_config: Data tiers to include. Default: ["formal", "alternative", "psychographic"].
            loan_amount_ngn: Optional loan amount for context.
            loan_tenure_days: Optional loan tenure in days.

        Returns:
            ScoreResult with score, confidence interval, factors, and metadata.

        Raises:
            ValidationError: Invalid BVN or phone number.
            AuthenticationError: Invalid API key.
            RateLimitError: Rate limit exceeded.
            ConsentError: Borrower has not consented to required data sharing.
            ServerError: Internal server error.
        """
        if tier_config:
            for tier in tier_config:
                if tier not in TIER_VALUES:
                    raise ValueError(f"Invalid tier '{tier}'. Must be one of: {TIER_VALUES}")

        body = {
            "bvn": bvn,
            "phone": phone,
            "lender_id": self._extract_lender_id(),
            "tier_config": tier_config or ["formal", "alternative", "psychographic"],
        }
        if loan_amount_ngn is not None:
            body["loan_amount_ngn"] = loan_amount_ngn
        if loan_tenure_days is not None:
            body["loan_tenure_days"] = loan_tenure_days

        data = self._request("POST", "/v1/score", json=body)

        ci = data["confidence_interval"]
        return ScoreResult(
            score=data["score"],
            confidence_interval=ConfidenceInterval(
                lower=ci["lower"],
                upper=ci["upper"],
                level=ci["level"],
            ),
            confidence_band=data["confidence_band"],
            data_coverage_pct=data["data_coverage_pct"],
            positive_factors=data["positive_factors"],
            negative_factors=data["negative_factors"],
            consent_token_ref=data.get("consent_token_ref"),
            model_version=data["model_version"],
            computed_at=self._parse_datetime(data["computed_at"]),
            trace_id=data["trace_id"],
        )

    def get_score_history(self, bvn: str) -> ScoreHistoryResult:
        """
        Get the credit score history for a borrower. PRD US-004.

        Returns up to 12 monthly score entries.
        """
        data = self._request("GET", f"/v1/score/{bvn}/history")

        scores = [
            ScoreHistoryEntry(
                score=s["score"],
                confidence_band=s["confidence_band"],
                data_coverage_pct=s["data_coverage_pct"],
                model_version=s["model_version"],
                computed_at=self._parse_datetime(s["computed_at"]),
            )
            for s in data["scores"]
        ]

        return ScoreHistoryResult(
            bvn_hash=data["bvn_hash"],
            scores=scores,
        )

    # ── Consent ─────────────────────────────────────────────────────────

    def grant_consent(
        self,
        *,
        bvn: str,
        phone: str,
        data_category: str,
        purpose: str,
        authorized_lenders: Optional[List[str]] = None,
        expiry_date: Optional[str] = None,
        policy_version: str = "1.0",
    ) -> ConsentResult:
        """
        Grant consent for a specific data category. PRD FR-011.

        Args:
            bvn: Bank Verification Number.
            phone: Borrower phone number.
            data_category: One of: bureau, bank, telco, mobile_money, utility, psychographic.
            purpose: Stated purpose of data collection.
            authorized_lenders: List of lender IDs authorized to access this data.
            expiry_date: Optional ISO 8601 expiry date.
            policy_version: Privacy policy version at time of consent.

        Returns:
            ConsentResult with consent_id, token_signature, and metadata.

        Raises:
            ConsentError: Duplicate consent for same category + purpose.
            ValidationError: Invalid data_category.
        """
        if data_category not in CONSENT_CATEGORIES:
            raise ValueError(f"Invalid data_category '{data_category}'. Must be one of: {CONSENT_CATEGORIES}")

        body: dict = {
            "bvn": bvn,
            "phone": phone,
            "data_category": data_category,
            "purpose": purpose,
            "authorized_lenders": authorized_lenders or [],
            "policy_version": policy_version,
        }
        if expiry_date:
            body["expiry_date"] = expiry_date

        data = self._request("POST", "/v1/consent", json=body)

        return ConsentResult(
            consent_id=data["consent_id"],
            borrower_bvn_hash=data["borrower_bvn_hash"],
            data_category=data["data_category"],
            purpose=data["purpose"],
            authorized_lenders=data["authorized_lenders"],
            expiry_at=self._parse_datetime(data.get("expiry_at")),
            is_active=data["is_active"],
            token_signature=data["token_signature"],
            created_at=self._parse_datetime(data["created_at"]),
        )

    def check_consent_status(self, bvn: str) -> ConsentStatusResult:
        """
        Check the consent status for a borrower across all data categories.

        Returns:
            ConsentStatusResult with per-category status and minimum_consent_met flag.
        """
        data = self._request("GET", f"/v1/consent/{bvn}/status")

        consents = [
            ConsentStatusEntry(
                data_category=c["data_category"],
                is_active=c["is_active"],
                purpose=c["purpose"],
                expiry_at=self._parse_datetime(c.get("expiry_at")),
                granted_at=self._parse_datetime(c["granted_at"]),
            )
            for c in data["consents"]
        ]

        return ConsentStatusResult(
            borrower_bvn_hash=data["borrower_bvn_hash"],
            consents=consents,
            minimum_consent_met=data["minimum_consent_met"],
        )

    def withdraw_consent(self, consent_id: str, reason: Optional[str] = None) -> ConsentWithdrawResult:
        """
        Withdraw previously granted consent. PRD FR-014.

        Triggers cascade: stops ingestion, flags features, notifies lenders.
        """
        body: dict = {}
        if reason:
            body["reason"] = reason

        data = self._request("DELETE", f"/v1/consent/{consent_id}", json=body if body else None)

        return ConsentWithdrawResult(
            consent_id=data["consent_id"],
            status=data["status"],
            withdrawn_at=self._parse_datetime(data["withdrawn_at"]),
            downstream_lenders_notified=data.get("downstream_lenders_notified", []),
        )

    # ── Outcomes ────────────────────────────────────────────────────────

    def submit_outcome(
        self,
        *,
        loan_id: str,
        bvn: str,
        disbursement_date: str,
        due_date: str,
        loan_amount_ngn: int,
        outcome: str,
        outcome_date: str,
        score_at_origination: int,
    ) -> OutcomeResult:
        """
        Submit a loan repayment outcome for model training. PRD Section 8.2.

        Args:
            loan_id: Unique loan identifier.
            bvn: Borrower BVN.
            disbursement_date: ISO 8601 date.
            due_date: ISO 8601 date.
            loan_amount_ngn: Loan amount in Naira.
            outcome: One of REPAID_ON_TIME, REPAID_LATE, DEFAULTED, RESTRUCTURED, WRITTEN_OFF.
            outcome_date: ISO 8601 date.
            score_at_origination: Score at the time of loan origination.

        Returns:
            OutcomeResult confirming receipt.
        """
        if outcome not in OUTCOME_VALUES:
            raise ValueError(f"Invalid outcome '{outcome}'. Must be one of: {OUTCOME_VALUES}")

        body = {
            "loan_id": loan_id,
            "bvn": bvn,
            "disbursement_date": disbursement_date,
            "due_date": due_date,
            "loan_amount_ngn": loan_amount_ngn,
            "outcome": outcome,
            "outcome_date": outcome_date,
            "score_at_origination": score_at_origination,
        }

        data = self._request("POST", "/v1/outcomes", json=body)

        return OutcomeResult(
            loan_id=data["loan_id"],
            status=data["status"],
            message=data["message"],
        )

    # ── Data Subject Rights ─────────────────────────────────────────────

    def get_subject_data(self, bvn: str) -> SubjectDataResult:
        """
        Retrieve all data held about a borrower (DSAR). PRD FR-017.

        Returns profile, consents, features, and score history.
        """
        data = self._request("GET", f"/v1/subject/{bvn}/data")

        return SubjectDataResult(
            bvn_hash=data["bvn_hash"],
            profile=data["profile"],
            consent_records=data["consent_records"],
            feature_summary=data["feature_summary"],
            score_history=data["score_history"],
            compiled_at=self._parse_datetime(data["compiled_at"]),
        )

    # ── Utility ─────────────────────────────────────────────────────────

    def health(self) -> dict:
        """Check API health."""
        return self._request("GET", "/health")

    def _extract_lender_id(self) -> str:
        """
        Extract lender ID from the API key prefix.
        Format: credaly_{timestamp}_{lender_id}_{random}
        In production, this is resolved server-side from the API key.
        We send a placeholder — the server looks up the actual lender.
        """
        return "auto"  # Resolved server-side from the API key
