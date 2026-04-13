"""Credaly SDK — custom exception hierarchy."""

from __future__ import annotations

from typing import Optional


class CredalyError(Exception):
    """Base exception for all Credaly SDK errors."""

    def __init__(self, message: str, code: Optional[str] = None, trace_id: Optional[str] = None):
        super().__init__(message)
        self.code = code
        self.trace_id = trace_id


class AuthenticationError(CredalyError):
    """Invalid, expired, or missing API key (HTTP 401/403)."""
    pass


class RateLimitError(CredalyError):
    """Too many requests — retry after the given seconds (HTTP 429)."""

    def __init__(self, message: str, retry_after: int = 60, **kwargs):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class ValidationError(CredalyError):
    """Request validation failed (HTTP 400/422)."""
    pass


class ConsentError(CredalyError):
    """Consent-related error — missing, revoked, or duplicate (HTTP 403/409)."""
    pass


class NotFoundError(CredalyError):
    """Requested resource does not exist (HTTP 404)."""
    pass


class ServerError(CredalyError):
    """Internal server error — retry later (HTTP 500/502/503)."""
    pass
