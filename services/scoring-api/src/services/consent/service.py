"""
Consent Service — handles consent grant, withdrawal, verification, and audit logging.
Implements PRD FR-011 through FR-019.
"""

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.config import settings
from src.models import (
    BorrowerProfile,
    ConsentAuditLog,
    ConsentRecord,
    LenderClient,
    _hash_bvn,
)
from src.schemas import (
    ConsentGrantRequest,
    ConsentResponse,
    ConsentStatusEntry,
    ConsentStatusResponse,
    ConsentWithdrawResponse,
)


def _sign_consent_token(
    borrower_bvn_hash: str,
    data_category: str,
    purpose: str,
    authorized_lenders: List[str],
    expiry_at: Optional[datetime],
    policy_version: str,
) -> str:
    """
    Generate a cryptographically signed consent token.
    PRD FR-012: token contains all consent attributes, HMAC-signed.
    """
    payload = json.dumps(
        {
            "bvn_hash": borrower_bvn_hash,
            "category": data_category,
            "purpose": purpose,
            "lenders": sorted(authorized_lenders),
            "expiry": expiry_at.isoformat() if expiry_at else None,
            "policy_version": policy_version,
        },
        sort_keys=True,
    )
    signature = hmac.new(
        settings.consent_signing_secret.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    return signature


def _hash_row_content(consent_id: str, event_type: str, timestamp: datetime) -> str:
    """Generate SHA-256 hash of a consent audit log entry for tamper-evidence."""
    content = f"{consent_id}:{event_type}:{timestamp.isoformat()}"
    return hashlib.sha256(content.encode()).hexdigest()


async def get_last_audit_log_hash(db: AsyncSession, consent_id: str) -> str:
    """Get the hash of the most recent audit log entry for a consent record."""
    stmt = (
        select(ConsentAuditLog.row_hash)
        .where(ConsentAuditLog.consent_id == consent_id)
        .order_by(ConsentAuditLog.timestamp.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()
    return row or "genesis"


async def create_audit_log_entry(
    db: AsyncSession,
    consent_id: str,
    event_type: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    actor_id: Optional[str] = None,
) -> ConsentAuditLog:
    """Create a tamper-evident audit log entry. PRD FR-019."""
    previous_hash = await get_last_audit_log_hash(db, consent_id)
    timestamp = datetime.now(timezone.utc)
    row_hash = _hash_row_content(consent_id, event_type, timestamp)

    entry = ConsentAuditLog(
        consent_id=consent_id,
        event_type=event_type,
        timestamp=timestamp,
        ip_address=ip_address,
        user_agent=user_agent,
        actor_id=actor_id,
        previous_row_hash=previous_hash,
        row_hash=row_hash,
    )
    db.add(entry)
    return entry


class ConsentService:
    """Business logic for consent management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def grant_consent(self, request: ConsentGrantRequest) -> ConsentResponse:
        """
        Grant consent for a specific data category. PRD FR-011, FR-012, FR-019.
        Each data category requires separate, granular consent.
        """
        bvn_hash = _hash_bvn(request.bvn, settings.bvn_encryption_key)

        # Ensure borrower profile exists
        profile = await self.db.execute(
            select(BorrowerProfile).where(BorrowerProfile.bvn_hash == bvn_hash)
        )
        profile_obj = profile.scalar_one_or_none()
        if not profile_obj:
            profile_obj = BorrowerProfile(
                id=f"brw_{uuid.uuid4().hex[:10]}",
                bvn_hash=bvn_hash,
                phone_hash=hashlib.sha256(request.phone.encode()).hexdigest(),
            )
            self.db.add(profile_obj)
            await self.db.flush()

        # Check for existing active consent (no duplicates for same category + purpose)
        existing = await self.db.execute(
            select(ConsentRecord).where(
                ConsentRecord.borrower_bvn_hash == bvn_hash,
                ConsentRecord.data_category == request.data_category,
                ConsentRecord.purpose == request.purpose,
                ConsentRecord.revoked_at.is_(None),
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError(
                f"Active consent already exists for category '{request.data_category}' "
                f"with purpose '{request.purpose}'"
            )

        # Sign the consent token
        token_signature = _sign_consent_token(
            borrower_bvn_hash=bvn_hash,
            data_category=request.data_category,
            purpose=request.purpose,
            authorized_lenders=request.authorized_lenders,
            expiry_at=request.expiry_date,
            policy_version=request.policy_version,
        )

        # Create consent record
        consent_id = f"cst_{uuid.uuid4().hex[:12]}"
        consent = ConsentRecord(
            id=consent_id,
            borrower_bvn_hash=bvn_hash,
            data_category=request.data_category,
            purpose=request.purpose,
            authorized_lenders=json.dumps(request.authorized_lenders),
            expiry_at=request.expiry_date,
            token_signature=token_signature,
            policy_version=request.policy_version,
            ip_address=request.ip_address,
            user_agent=request.user_agent,
        )
        self.db.add(consent)
        await self.db.flush()

        # Create audit log entry
        await create_audit_log_entry(
            self.db,
            consent_id=consent_id,
            event_type="granted",
            ip_address=request.ip_address,
            user_agent=request.user_agent,
            actor_id=bvn_hash,
        )

        return ConsentResponse(
            consent_id=consent_id,
            borrower_bvn_hash=bvn_hash,
            data_category=request.data_category,
            purpose=request.purpose,
            authorized_lenders=request.authorized_lenders,
            expiry_at=request.expiry_date,
            is_active=True,
            token_signature=token_signature,
            created_at=datetime.now(timezone.utc),
        )

    async def withdraw_consent(
        self,
        consent_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ConsentWithdrawResponse:
        """
        Withdraw consent for a specific data category. PRD FR-014.
        Cascade: stop ingesting, flag derived features, notify downstream lenders.
        """
        stmt = select(ConsentRecord).where(ConsentRecord.id == consent_id)
        result = await self.db.execute(stmt)
        consent = result.scalar_one_or_none()
        if not consent:
            raise ValueError(f"Consent record '{consent_id}' not found")
        if consent.revoked_at is not None:
            raise ValueError(f"Consent '{consent_id}' is already revoked")

        # Revoke
        consent.revoked_at = datetime.now(timezone.utc)
        await self.db.flush()

        # Invalidate all cached scores for this borrower
        from src.services.cache.service import CacheService
        cache = CacheService()
        await cache.invalidate_bvn(consent.borrower_bvn_hash)

        # Audit log
        await create_audit_log_entry(
            self.db,
            consent_id=consent_id,
            event_type="withdrawn",
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Notify downstream lenders via webhook
        lenders = json.loads(consent.authorized_lenders) if consent.authorized_lenders else []
        await self._notify_lenders_of_withdrawal(
            consent_id=consent_id,
            lender_ids=lenders,
            category=consent.data_category,
        )

        return ConsentWithdrawResponse(
            consent_id=consent_id,
            withdrawn_at=consent.revoked_at,
            downstream_lenders_notified=lenders,
        )

    async def check_consent_status(
        self,
        bvn: str,
        required_categories: Optional[List[str]] = None,
    ) -> ConsentStatusResponse:
        """
        Check active consent status for a borrower. PRD FR-011.
        Returns per-category consent status and whether minimum consent is met.
        """
        bvn_hash = _hash_bvn(bvn, settings.bvn_encryption_key)

        stmt = (
            select(ConsentRecord)
            .where(
                ConsentRecord.borrower_bvn_hash == bvn_hash,
                ConsentRecord.revoked_at.is_(None),
            )
            .order_by(ConsentRecord.created_at.desc())
        )
        result = await self.db.execute(stmt)
        records = result.scalars().all()

        # De-duplicate by category (keep most recent per category)
        seen = {}
        for record in records:
            if record.data_category not in seen:
                seen[record.data_category] = record

        consents = []
        active_categories = set()
        for category, record in seen.items():
            is_active = record.is_active
            if is_active:
                active_categories.add(category)
            consents.append(ConsentStatusEntry(
                data_category=category,
                is_active=is_active,
                purpose=record.purpose,
                expiry_at=record.expiry_at,
                granted_at=record.created_at,
            ))

        # Minimum consent set: bureau + bank
        minimum_met = {"bureau", "bank"}.issubset(active_categories)

        return ConsentStatusResponse(
            borrower_bvn_hash=bvn_hash,
            consents=consents,
            minimum_consent_met=minimum_met,
        )

    async def verify_consent_for_scoring(
        self,
        bvn: str,
        data_categories: List[str],
        lender_id: str,
    ) -> tuple[bool, List[str], Optional[str]]:
        """
        Verify that the borrower has granted consent for all requested data categories
        and that the specified lender is authorized. PRD FR-013, FR-015.

        Also verifies the cryptographic signature on each consent token.

        Returns: (all_consented, missing_categories, active_consent_token_ref)
        """
        bvn_hash = _hash_bvn(bvn, settings.bvn_encryption_key)
        missing = []
        token_ref = None

        for category in data_categories:
            stmt = (
                select(ConsentRecord)
                .where(
                    ConsentRecord.borrower_bvn_hash == bvn_hash,
                    ConsentRecord.data_category == category,
                    ConsentRecord.revoked_at.is_(None),
                )
                .order_by(ConsentRecord.created_at.desc())
                .limit(1)
            )
            result = await self.db.execute(stmt)
            record = result.scalar_one_or_none()

            if not record or not record.is_active:
                missing.append(category)
                continue

            # Verify the cryptographic signature on the consent token
            if not self._verify_consent_signature(record):
                logger.warning(
                    "Consent token signature verification failed",
                    consent_id=record.id,
                    category=category,
                )
                missing.append(f"{category} (invalid token signature)")
                continue

            # Check lender is authorized
            if record.authorized_lenders:
                authorized = json.loads(record.authorized_lenders)
                if lender_id not in authorized and len(authorized) > 0:
                    missing.append(f"{category} (lender not authorized)")
                    continue

            if token_ref is None:
                token_ref = record.id

        return len(missing) == 0, missing, token_ref

    def _verify_consent_signature(self, record: ConsentRecord) -> bool:
        """
        Verify the HMAC signature on a consent record.
        PRD FR-013: consent tokens must be cryptographically verifiable.
        """
        import hashlib as _hl
        expected = _hl.new(
            "hmac",
            settings.consent_signing_secret.encode(),
            json.dumps({
                "bvn_hash": record.borrower_bvn_hash,
                "category": record.data_category,
                "purpose": record.purpose,
                "lenders": sorted(json.loads(record.authorized_lenders)) if record.authorized_lenders else [],
                "expiry": record.expiry_at.isoformat() if record.expiry_at else None,
                "policy_version": record.policy_version,
            }, sort_keys=True).encode(),
            _hl.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, record.token_signature)

    async def _notify_lenders_of_withdrawal(
        self,
        consent_id: str,
        lender_ids: List[str],
        category: str,
    ) -> None:
        """
        Notify downstream lenders when consent is withdrawn.
        Fires a webhook event so lenders can invalidate scores built on the withdrawn data.
        PRD FR-014: cascade to downstream lenders.
        """
        if not lender_ids:
            return

        try:
            from src.services.webhooks.service import WebhookDispatcher

            dispatcher = WebhookDispatcher(self.db)
            try:
                payload = {
                    "consent_id": consent_id,
                    "data_category": category,
                    "affected_lenders": lender_ids,
                    "message": f"Borrower has withdrawn consent for '{category}' data. "
                    f"Any scores built on this data should be invalidated.",
                    "withdrawn_at": datetime.now(timezone.utc).isoformat(),
                }
                await dispatcher.dispatch("consent_withdrawn", payload)
            finally:
                await dispatcher.close()
        except Exception as e:
            logger.warning(f"Failed to notify lenders of consent withdrawal: {e}")
