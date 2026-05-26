"""Encryption boundary tests — round-trip + tamper detection + missing key."""
import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from crypto import (
    EncryptedJSON,
    EncryptedNumeric,
    EncryptedString,
    FernetDecryptionError,
    decrypt,
    encrypt,
)


def test_string_round_trip() -> None:
    plaintext = "sensitive value with unicode — émojis 🔐"
    ciphertext = encrypt(plaintext)
    assert isinstance(ciphertext, bytes)
    assert plaintext.encode() not in ciphertext
    assert decrypt(ciphertext) == plaintext


def test_encryption_uses_random_iv() -> None:
    plaintext = "same value twice"
    assert encrypt(plaintext) != encrypt(plaintext)


def test_decrypt_rejects_tampered_ciphertext() -> None:
    ciphertext = bytearray(encrypt("real"))
    ciphertext[-1] ^= 0x01
    with pytest.raises(FernetDecryptionError):
        decrypt(bytes(ciphertext))


def test_encrypted_string_type_decorator_round_trip() -> None:
    decorator = EncryptedString()
    bound = decorator.process_bind_param("hello", dialect=None)
    assert isinstance(bound, bytes)
    assert decorator.process_result_value(bound, dialect=None) == "hello"
    assert decorator.process_bind_param(None, dialect=None) is None
    assert decorator.process_result_value(None, dialect=None) is None


def test_encrypted_numeric_round_trip() -> None:
    decorator = EncryptedNumeric()
    value = Decimal("12345.6789")
    bound = decorator.process_bind_param(value, dialect=None)
    assert isinstance(bound, bytes)
    assert decorator.process_result_value(bound, dialect=None) == value


def test_encrypted_numeric_rejects_float() -> None:
    with pytest.raises(TypeError):
        EncryptedNumeric().process_bind_param(123.45, dialect=None)  # type: ignore[arg-type]


def test_encrypted_json_round_trip() -> None:
    decorator = EncryptedJSON()
    value = {"asset_class": "equity", "amount": "10000.00", "nested": {"k": [1, 2, 3]}}
    bound = decorator.process_bind_param(value, dialect=None)
    assert isinstance(bound, bytes)
    assert json.dumps(value, sort_keys=True).encode() not in bound
    assert decorator.process_result_value(bound, dialect=None) == value


def test_missing_vault_encryption_key_fails_app_start() -> None:
    """Booting config without VAULT_ENCRYPTION_KEY must raise at import-time validation."""
    # Use Settings(_env_file=None) so pydantic-settings cannot fall back to the
    # .env file. Also pop VAULT_ENCRYPTION_KEY from the inherited subprocess env
    # so only os.environ is consulted and the missing-key validation fires.
    script = (
        "import os\n"
        "os.environ.pop('VAULT_ENCRYPTION_KEY', None)\n"
        "os.environ.update({\n"
        "    'ANTHROPIC_API_KEY':'k','DATABASE_URL':'postgresql://u:p@h/d',"
        "'REDIS_URL':'redis://h:1/0',\n"
        "    'JWT_SECRET_KEY':'x'*40,'DIGEST_RECIPIENT':'t@e.com','SMTP_HOST':'h',"
        "'SMTP_PORT':'1','SMTP_USER':'u','SMTP_PASSWORD':'p','SMTP_FROM':'f@e.com',\n"
        "})\n"
        "from config import Settings\n"
        "Settings(_env_file=None)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).parent.parent),
    )
    assert result.returncode != 0
    assert "vault_encryption_key" in result.stderr.lower() or "field required" in result.stderr.lower()
