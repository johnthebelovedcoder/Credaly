"""
Security utilities — HMAC API key auth, BVN encryption, bcrypt, Fernet.
"""

import hashlib
import hmac
import time
from typing import Optional

import bcrypt
from cryptography.fernet import Fernet

from src.core.config import settings
from src.models import _hash_bvn as _canonical_hash_bvn


def _get_fernet() -> Fernet:
    """
    Get a Fernet cipher instance.
    Fernet uses AES-128-CBC with HMAC-SHA256 authentication.
    The key must be a valid 32-byte URL-safe base64-encoded key.
    """
    # Derive a 32-byte Fernet key from the config key via SHA-256
    key_material = settings.bvn_encryption_key.encode()
    derived_key = hashlib.sha256(key_material).digest()
    # Fernet expects base64 — encode on the fly
    import base64
    b64_key = base64.urlsafe_b64encode(derived_key)
    return Fernet(b64_key)


def encrypt_bvn(bvn: str) -> str:
    """Encrypt a raw BVN using Fernet (AES-128-CBC). Returns base64 string."""
    fernet = _get_fernet()
    return fernet.encrypt(bvn.encode()).decode()


def decrypt_bvn(encrypted_bvn: str) -> str:
    """Decrypt an encrypted BVN. Raises InvalidToken if key doesn't match."""
    fernet = _get_fernet()
    return fernet.decrypt(encrypted_bvn.encode()).decode()


def hash_bvn(bvn: str) -> str:
    """Convenience wrapper: hash BVN using the canonical function with settings salt.

    This is the version to use when you don't have the salt readily available
    (e.g. routers, admin services). It reads the salt from settings.
    """
    return _canonical_hash_bvn(bvn, settings.bvn_encryption_key)


def hash_phone(phone: str) -> str:
    """Hash phone number for deduplication without storing raw PII."""
    return hashlib.sha256(phone.encode()).hexdigest()


def generate_api_key() -> tuple[str, str]:
    """
    Generate a new API key pair.
    Returns (raw_key, hashed_key).
    Raw key is shown once at creation, then discarded.
    Hashed key is stored in DB.
    """
    raw = f"credaly_{int(time.time())}_{hashlib.sha256(hmac.new(
        settings.hmac_secret_key.encode(),
        str(time.time_ns()).encode(),
        hashlib.sha256,
    ).hexdigest())[:32]}"
    hashed = bcrypt.hashpw(raw.encode(), bcrypt.gensalt(rounds=settings.bcrypt_rounds)).decode()
    return raw, hashed


def verify_api_key(raw_key: str, hashed_key: str) -> bool:
    """Verify a raw API key against its bcrypt hash."""
    try:
        return bcrypt.checkpw(raw_key.encode(), hashed_key.encode())
    except (ValueError, TypeError):
        return False


def verify_hmac_signature(payload: str, signature: str, secret: str) -> bool:
    """Verify HMAC-SHA256 signature of a request payload."""
    expected = hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def generate_trace_id() -> str:
    """Generate a trace ID for request debugging."""
    import uuid
    return f"trc_{uuid.uuid4().hex[:8]}"
