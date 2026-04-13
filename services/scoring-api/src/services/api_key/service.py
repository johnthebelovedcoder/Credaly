"""
API Key Management Service — handles API key CRUD operations for clients.
Per PRD FR-032: API key authentication and management.
"""

import json
import secrets
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import ApiKey
from src.schemas import ApiKeyInfo


class ApiKeyService:
    """Business logic for API key management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    def _generate_api_key(self) -> str:
        """Generate a new API key with timestamp and random suffix."""
        timestamp = int(datetime.now(timezone.utc).timestamp())
        random_suffix = secrets.token_urlsafe(24)
        return f"credaly_{timestamp}_{random_suffix}"

    def _hash_api_key(self, raw_key: str) -> str:
        """Hash API key using bcrypt."""
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(raw_key.encode('utf-8'), salt).decode('utf-8')

    def _to_api_key_info(self, api_key: ApiKey) -> ApiKeyInfo:
        """Convert ApiKey entity to ApiKeyInfo schema (never includes hash)."""
        return ApiKeyInfo(
            id=api_key.id,
            name=api_key.key_name or f"Key {api_key.key_prefix}",
            key_prefix=api_key.key_prefix,
            environment='sandbox',  # Default, can be extended later
            created_at=api_key.created_at,
            last_used=api_key.last_used_at,
            is_active=api_key.is_active,
            ip_allowlist=json.loads(api_key.ip_allowlist) if api_key.ip_allowlist else [],
        )

    async def get_api_keys(self) -> List[ApiKeyInfo]:
        """Get all API keys."""
        stmt = select(ApiKey).order_by(ApiKey.created_at.desc())
        result = await self.db.execute(stmt)
        keys = result.scalars().all()
        
        return [self._to_api_key_info(key) for key in keys]

    async def create_api_key(
        self,
        name: str,
        environment: str = 'sandbox',
    ) -> Tuple[ApiKeyInfo, str]:
        """
        Create a new API key.
        Returns (ApiKeyInfo, raw_key) — raw key shown only once.
        """
        # Generate and hash the key
        raw_key = self._generate_api_key()
        key_hash = self._hash_api_key(raw_key)
        key_prefix = raw_key[:20]

        # Create entity
        api_key = ApiKey(
            id=f"key_{uuid.uuid4().hex[:10]}",
            client_id='default',
            key_hash=key_hash,
            key_prefix=key_prefix,
            key_name=name,
            is_active=True,
            last_used_at=None,
            ip_allowlist=None,
        )
        
        self.db.add(api_key)
        await self.db.flush()
        
        return self._to_api_key_info(api_key), raw_key

    async def rotate_api_key(self, key_id: str) -> Tuple[ApiKeyInfo, str]:
        """
        Rotate an API key — deactivate old one and create new one.
        Returns (ApiKeyInfo, new_raw_key).
        """
        # Find existing key
        stmt = select(ApiKey).where(ApiKey.id == key_id)
        result = await self.db.execute(stmt)
        existing_key = result.scalar_one_or_none()
        
        if not existing_key:
            raise ValueError(f"API key '{key_id}' not found")
        
        if not existing_key.is_active:
            raise ValueError("Cannot rotate an already revoked key")
        
        # Revoke old key
        existing_key.is_active = False
        existing_key.revoked_at = datetime.now(timezone.utc)
        await self.db.flush()
        
        # Create new key with same name
        return await self.create_api_key(name=existing_key.key_name or "Rotated Key")

    async def revoke_api_key(self, key_id: str) -> ApiKeyInfo:
        """Revoke an API key."""
        stmt = select(ApiKey).where(ApiKey.id == key_id)
        result = await self.db.execute(stmt)
        api_key = result.scalar_one_or_none()
        
        if not api_key:
            raise ValueError(f"API key '{key_id}' not found")
        
        if not api_key.is_active:
            raise ValueError("API key is already revoked")
        
        api_key.is_active = False
        api_key.revoked_at = datetime.now(timezone.utc)
        await self.db.flush()
        
        return self._to_api_key_info(api_key)

    async def verify_api_key(self, raw_key: str) -> Optional[ApiKey]:
        """
        Verify an API key and return the associated entity.
        Used for authentication.
        """
        stmt = select(ApiKey).where(ApiKey.is_active == True)
        result = await self.db.execute(stmt)
        active_keys = result.scalars().all()
        
        for key in active_keys:
            if bcrypt.checkpw(raw_key.encode('utf-8'), key.key_hash.encode('utf-8')):
                key.last_used_at = datetime.now(timezone.utc)
                await self.db.flush()
                return key
        
        return None
