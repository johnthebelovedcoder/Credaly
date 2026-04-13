"""initial schema — all tables for Phase 0/1

Revision ID: 001_initial
Revises:
Create Date: 2026-04-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables defined in the ORM models."""

    # ── borrower_profile ──────────────────────────────────────────────
    op.create_table(
        "borrower_profile",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("bvn_hash", sa.String(64), nullable=False),
        sa.Column("phone_hash", sa.String(64), nullable=True),
        sa.Column("data_coverage_pct", sa.Float(), nullable=True),
        sa.Column("bvn_vault_ref", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bvn_hash"),
    )
    op.create_index("ix_borrower_profile_phone_hash", "borrower_profile", ["phone_hash"])

    # ── consent_record ────────────────────────────────────────────────
    op.create_table(
        "consent_record",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("borrower_bvn_hash", sa.String(64), nullable=False),
        sa.Column("data_category", sa.String(50), nullable=False),
        sa.Column("purpose", sa.String(500), nullable=False),
        sa.Column("authorized_lenders", sa.Text(), nullable=True),
        sa.Column("expiry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("token_signature", sa.String(128), nullable=False),
        sa.Column("policy_version", sa.String(20), nullable=False, server_default="1.0"),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["borrower_bvn_hash"], ["borrower_profile.bvn_hash"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("borrower_bvn_hash", "data_category", "purpose", name="uq_consent_borrower_category_purpose"),
    )
    op.create_index("ix_consent_record_borrower_bvn_hash", "consent_record", ["borrower_bvn_hash"])

    # ── consent_audit_log ─────────────────────────────────────────────
    op.create_table(
        "consent_audit_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("consent_id", sa.String(36), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("actor_id", sa.String(36), nullable=True),
        sa.Column("previous_row_hash", sa.String(64), nullable=False, server_default="genesis"),
        sa.Column("row_hash", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["consent_id"], ["consent_record.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_consent_audit_log_consent_id", "consent_audit_log", ["consent_id"])

    # ── lender_client ─────────────────────────────────────────────────
    op.create_table(
        "lender_client",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("api_key_hash", sa.String(128), nullable=False),
        sa.Column("api_key_raw", sa.String(128), nullable=True),
        sa.Column("tier_access", sa.Text(), nullable=True),
        sa.Column("rate_limit", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("dpa_signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("environment", sa.String(20), nullable=False, server_default="sandbox"),
        sa.Column("ip_allowlist", sa.Text(), nullable=True),
        sa.Column("webhook_url", sa.String(500), nullable=True),
        sa.Column("webhook_events", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("api_key_hash"),
    )

    # ── feature_snapshot ──────────────────────────────────────────────
    op.create_table(
        "feature_snapshot",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("borrower_bvn_hash", sa.String(64), nullable=False),
        sa.Column("feature_name", sa.String(100), nullable=False),
        sa.Column("feature_value", sa.Float(), nullable=False),
        sa.Column("source_tier", sa.String(50), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("data_snapshot_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["borrower_bvn_hash"], ["borrower_profile.bvn_hash"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("borrower_bvn_hash", "feature_name", "data_snapshot_at", name="uq_feature_borrower_name_snapshot"),
    )
    op.create_index("ix_feature_snapshot_borrower_bvn_hash", "feature_snapshot", ["borrower_bvn_hash"])
    op.create_index("ix_feature_snapshot_feature_name", "feature_snapshot", ["feature_name"])

    # ── credit_score ──────────────────────────────────────────────────
    op.create_table(
        "credit_score",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("borrower_bvn_hash", sa.String(64), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("confidence_lower", sa.Integer(), nullable=False),
        sa.Column("confidence_upper", sa.Integer(), nullable=False),
        sa.Column("confidence_band", sa.String(10), nullable=False),
        sa.Column("data_coverage_pct", sa.Float(), nullable=False),
        sa.Column("model_version", sa.String(20), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("consent_token_ref", sa.String(36), nullable=True),
        sa.Column("trace_id", sa.String(20), nullable=False),
        sa.Column("positive_factors", sa.Text(), nullable=True),
        sa.Column("negative_factors", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["borrower_bvn_hash"], ["borrower_profile.bvn_hash"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_credit_score_borrower_bvn_hash", "credit_score", ["borrower_bvn_hash"])

    # ── loan_outcome ──────────────────────────────────────────────────
    op.create_table(
        "loan_outcome",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("loan_id", sa.String(100), nullable=False),
        sa.Column("borrower_bvn_hash", sa.String(64), nullable=False),
        sa.Column("lender_id", sa.String(36), nullable=False),
        sa.Column("disbursement_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("loan_amount_ngn", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(30), nullable=False),
        sa.Column("outcome_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("score_at_origination", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["borrower_bvn_hash"], ["borrower_profile.bvn_hash"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("loan_id"),
    )
    op.create_index("ix_loan_outcome_loan_id", "loan_outcome", ["loan_id"])
    op.create_index("ix_loan_outcome_borrower_bvn_hash", "loan_outcome", ["borrower_bvn_hash"])
    op.create_index("ix_loan_outcome_lender_id", "loan_outcome", ["lender_id"])

    # ── data_pipeline_run ─────────────────────────────────────────────
    op.create_table(
        "data_pipeline_run",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("source_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("records_ingested", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_log", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_data_pipeline_run_source_name", "data_pipeline_run", ["source_name"])

    # ── webhook_subscription ──────────────────────────────────────────
    op.create_table(
        "webhook_subscription",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("lender_id", sa.String(36), nullable=False),
        sa.Column("endpoint_url", sa.String(500), nullable=False),
        sa.Column("events", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("secret", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["lender_id"], ["lender_client.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── webhook_event ─────────────────────────────────────────────────
    op.create_table(
        "webhook_event",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("subscription_id", sa.String(36), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("delivery_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("delivery_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("response_code", sa.Integer(), nullable=True),
        sa.Column("response_body", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["subscription_id"], ["webhook_subscription.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── api_key ───────────────────────────────────────────────────────
    op.create_table(
        "api_key",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("client_id", sa.String(36), nullable=False),
        sa.Column("key_hash", sa.String(128), nullable=False),
        sa.Column("key_prefix", sa.String(20), nullable=False),
        sa.Column("key_name", sa.String(200), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.String(36), nullable=True),
        sa.Column("ip_allowlist", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash"),
    )
    op.create_index("ix_api_key_client_id", "api_key", ["client_id"])

    # ── human_review_request (added for human review service) ─────────
    op.create_table(
        "human_review_request",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("borrower_bvn_hash", sa.String(64), nullable=False),
        sa.Column("loan_id", sa.String(100), nullable=True),
        sa.Column("score_at_decision", sa.Integer(), nullable=True),
        sa.Column("decision_outcome", sa.String(30), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("lender_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("outcome", sa.String(30), nullable=True),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("sla_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_human_review_request_borrower_bvn_hash", "human_review_request", ["borrower_bvn_hash"])
    op.create_index("ix_human_review_request_lender_id", "human_review_request", ["lender_id"])
    op.create_index("ix_human_review_request_status", "human_review_request", ["status"])


def downgrade() -> None:
    """Drop all tables in reverse dependency order."""
    op.drop_table("api_key")
    op.drop_table("webhook_event")
    op.drop_table("webhook_subscription")
    op.drop_table("data_pipeline_run")
    op.drop_table("loan_outcome")
    op.drop_table("credit_score")
    op.drop_table("feature_snapshot")
    op.drop_table("lender_client")
    op.drop_table("consent_audit_log")
    op.drop_table("consent_record")
    op.drop_table("borrower_profile")
    op.drop_table("human_review_request")
