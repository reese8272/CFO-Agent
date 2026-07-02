"""Encryption boundary for sensitive vault data.

A single Fernet key from VAULT_ENCRYPTION_KEY backs three SQLAlchemy
TypeDecorators that transparently encrypt on write and decrypt on read,
keeping bytea in Postgres and clean Python types in code.
"""
import json
import logging
from decimal import Decimal
from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet, MultiFernet, InvalidToken
from sqlalchemy import LargeBinary
from sqlalchemy.types import TypeDecorator

from config import get_settings

logger = logging.getLogger(__name__)


class FernetDecryptionError(ValueError):
    """Raised when ciphertext fails to decrypt (wrong key or tampered data)."""


@lru_cache(maxsize=1)
def _fernet() -> MultiFernet:
    """Build the encryption primitive, supporting key rotation.

    VAULT_ENCRYPTION_KEYS (comma-separated) supersedes VAULT_ENCRYPTION_KEY: the
    FIRST key encrypts, and ANY listed key can decrypt. To rotate: prepend the
    new key, redeploy (new writes use it, old ciphertext still decrypts), then
    re-encrypt at leisure and drop the retired key. A single key still works.
    """
    settings = get_settings()
    raw = settings.vault_encryption_keys or settings.vault_encryption_key
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    return MultiFernet([Fernet(k.encode("utf-8")) for k in keys])


def encrypt(plaintext: str) -> bytes:
    return _fernet().encrypt(plaintext.encode("utf-8"))


def decrypt(ciphertext: bytes) -> str:
    try:
        return _fernet().decrypt(ciphertext).decode("utf-8")
    except InvalidToken as exc:
        raise FernetDecryptionError(
            "Fernet decryption failed; key mismatch or tampered ciphertext"
        ) from exc


class EncryptedString(TypeDecorator):
    impl = LargeBinary
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: Any) -> bytes | None:
        if value is None:
            return None
        return encrypt(value)

    def process_result_value(self, value: bytes | None, dialect: Any) -> str | None:
        if value is None:
            return None
        return decrypt(bytes(value))


class EncryptedNumeric(TypeDecorator):
    impl = LargeBinary
    cache_ok = True

    def process_bind_param(self, value: Decimal | None, dialect: Any) -> bytes | None:
        if value is None:
            return None
        if not isinstance(value, Decimal):
            raise TypeError(f"EncryptedNumeric requires Decimal, got {type(value).__name__}")
        return encrypt(str(value))

    def process_result_value(self, value: bytes | None, dialect: Any) -> Decimal | None:
        if value is None:
            return None
        return Decimal(decrypt(bytes(value)))


def _json_default(obj: Any) -> str:
    """Serialize types json doesn't handle natively. Decimal → str preserves
    exact precision and matches EncryptedNumeric's storage convention."""
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class EncryptedJSON(TypeDecorator):
    impl = LargeBinary
    cache_ok = True

    def process_bind_param(self, value: dict | None, dialect: Any) -> bytes | None:
        if value is None:
            return None
        return encrypt(json.dumps(value, sort_keys=True, separators=(",", ":"), default=_json_default))

    def process_result_value(self, value: bytes | None, dialect: Any) -> dict | None:
        if value is None:
            return None
        return json.loads(decrypt(bytes(value)))
