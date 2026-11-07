from __future__ import annotations

from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from mcp_layer.qf_bot.context_crypto import (
    ContextCryptoError,
    decrypt_context,
    encrypt_context,
)


def _write_key(path: Path) -> None:
    path.write_bytes(Fernet.generate_key() + b"\n")
    path.chmod(0o600)


def test_context_encrypts_and_authenticates_with_private_key(tmp_path):
    key_path = tmp_path / "context.key"
    _write_key(key_path)

    ciphertext = encrypt_context("private conversation", key_path)

    assert b"private conversation" not in ciphertext
    assert decrypt_context(ciphertext, key_path) == "private conversation"


def test_context_key_must_be_owner_only(tmp_path):
    key_path = tmp_path / "context.key"
    _write_key(key_path)
    key_path.chmod(0o640)

    with pytest.raises(ContextCryptoError, match="mode 0600"):
        encrypt_context("private conversation", key_path)


def test_context_key_must_not_be_a_symlink(tmp_path):
    real_key = tmp_path / "real.key"
    _write_key(real_key)
    link = tmp_path / "context.key"
    link.symlink_to(real_key)

    with pytest.raises(ContextCryptoError):
        encrypt_context("private conversation", link)


def test_context_decryption_rejects_tampered_ciphertext(tmp_path):
    key_path = tmp_path / "context.key"
    _write_key(key_path)
    ciphertext = bytearray(encrypt_context("private conversation", key_path))
    ciphertext[-1] ^= 1

    with pytest.raises(ContextCryptoError, match="cannot be authenticated"):
        decrypt_context(bytes(ciphertext), key_path)
