"""
Credaly — Predictive Behavioral Credit & Insurance Platform
Application configuration and settings.
"""

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment / .env files."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        protected_namespaces=("settings_",),  # Allow 'model_' prefix fields
    )

    def validate_production(self) -> None:
        """
        Validate that all required settings are properly configured for production.
        Called on startup when ENVIRONMENT=production. Fails fast if misconfigured.
        """
        errors = []

        # Security keys must not be default values
        for field_name in ["hmac_secret_key", "consent_signing_secret", "bvn_encryption_key"]:
            value = getattr(self, field_name)
            if value.startswith("dev-") or value == "change-me":
                errors.append(f"{field_name} must not use a development value in production")

        # CORS must be restricted in production
        if not self.cors_allowed_origins:
            errors.append("CORS_ALLOWED_ORIGINS must be set in production")

        # Database must not be SQLite in production
        if self.database_url.startswith("sqlite"):
            errors.append("DATABASE_URL must not be SQLite in production — use PostgreSQL")

        if errors:
            raise RuntimeError(
                f"Production configuration validation failed:\n"
                + "\n".join(f"  • {e}" for e in errors)
            )

    # ── Application ──────────────────────────────────────────
    app_name: str = "Credaly Scoring API"
    app_version: str = "1.0.0"
    debug: bool = False
    api_prefix: str = "/v1"
    cors_allowed_origins: str = ""  # Comma-separated. Empty = wildcard (dev only)

    # ── Database ─────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./credaly.db"
    pool_size: int = 5
    max_overflow: int = 10

    # ── Redis (feature store online + caching + rate limiting) ─
    redis_url: str = "redis://localhost:6379/0"
    score_cache_ttl_seconds: int = 86400  # 24h cached score validity

    # ── Security ─────────────────────────────────────────────
    hmac_secret_key: str = Field(..., description="HMAC secret for API key signing")
    bcrypt_rounds: int = 12
    consent_signing_secret: str = Field(
        ..., description="Cryptographic secret for consent token signatures"
    )
    bvn_encryption_key: str = Field(
        ..., description="AES key for BVN encryption at rest"
    )

    # ── Rate Limiting ────────────────────────────────────────
    default_rate_limit_per_minute: int = 100

    # ── ML Model ─────────────────────────────────────────────
    model_registry_uri: str = "./mlruns"
    model_artifacts_path: str = "./models"
    min_data_coverage_pct: float = 30.0  # minimum % features needed for a score

    # ── Scoring ──────────────────────────────────────────────
    score_min: int = 300
    score_max: int = 850
    confidence_level: float = 0.95

    # ── Data Retention (months) ──────────────────────────────
    raw_transaction_retention_months: int = 24
    derived_feature_retention_months: int = 36
    audit_log_retention_years: int = 7

    # ── External APIs (Phase 0/1 — bureau only) ─────────────
    crc_api_url: Optional[str] = None
    crc_api_key: Optional[str] = None
    firstcentral_api_url: Optional[str] = None
    firstcentral_api_key: Optional[str] = None
    creditregistry_api_url: Optional[str] = None
    creditregistry_api_key: Optional[str] = None

    # Phase 2 — telco / mobile money
    mtn_api_url: Optional[str] = None
    airtel_api_url: Optional[str] = None
    opay_api_url: Optional[str] = None
    opay_api_key: Optional[str] = None
    palmpay_api_url: Optional[str] = None
    palmpay_api_key: Optional[str] = None

    # Open Banking partners
    mono_api_url: Optional[str] = None
    mono_api_key: Optional[str] = None
    okra_api_url: Optional[str] = None
    okra_api_key: Optional[str] = None
    onepipe_api_url: Optional[str] = None
    onepipe_api_key: Optional[str] = None

    # ── Webhook ──────────────────────────────────────────────
    webhook_timeout_seconds: int = 10
    webhook_max_retries: int = 3
    webhook_retry_backoff_seconds: int = 30

    # ── Environment ──────────────────────────────────────────
    environment: str = "development"  # development | sandbox | production


settings = Settings()
