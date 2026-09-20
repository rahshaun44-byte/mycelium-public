#!/usr/bin/env python3
"""Vault Transit helpers for mycelium-a5-ed25519-v1.

Signs RFC 8032 Ed25519 over raw message bytes (Vault `input` = Base64 of
the on-disk manifest). Never SHA-256-then-sign (that would be a different
message; verifiers of the file would fail).

Does not mint keys. A name collision with a new random keypair is an
identity mismatch. Import the pinned key (BYOK) if the Transit key is
missing. See docs/VAULT_TRANSIT_A5.md.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from qf_signing_ceremony import HOST_A5_KEY_ID, parse_vault_signature, vault_sign_input_b64

VAULT_KEY_NAME = HOST_A5_KEY_ID


def _vault_addr_token() -> tuple[str, str]:
    addr = os.environ.get("VAULT_ADDR", "").rstrip("/")
    token = os.environ.get("VAULT_TOKEN", "")
    if not addr or not token:
        raise FileNotFoundError(
            "VAULT_ADDR and VAULT_TOKEN are required for vault-transit. "
            "Use an ephemeral ceremony token (ttl=10m, renewable=false)."
        )
    return addr, token


def _request(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    addr, token = _vault_addr_token()
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{addr}{path}",
        data=data,
        method=method,
        headers={
            "X-Vault-Token": token,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        if exc.code == 404:
            raise FileNotFoundError(f"Vault 404 {path}: {detail}") from exc
        raise RuntimeError(f"Vault {method} {path} failed ({exc.code}): {detail}") from exc


def sign_raw_manifest_bytes(message: bytes, key_name: str = VAULT_KEY_NAME) -> bytes:
    """Transit sign of the exact file bytes. prehashed=false. No digest substitution."""
    payload = {
        "input": vault_sign_input_b64(message),
        "prehashed": False,
    }
    result = _request("POST", f"/v1/transit/sign/{key_name}", payload)
    field = result.get("data", {}).get("signature")
    if not isinstance(field, str):
        raise RuntimeError("Vault sign response missing data.signature")
    return parse_vault_signature(field)


def read_transit_key(key_name: str = VAULT_KEY_NAME) -> dict[str, Any]:
    return _request("GET", f"/v1/transit/keys/{key_name}")


def pem_raw_ed25519(pub_pem: bytes) -> bytes:
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, load_pem_public_key
    except ImportError as exc:
        raise RuntimeError("cryptography is required to compare the pinned PEM to Vault") from exc
    loaded = load_pem_public_key(pub_pem)
    if not isinstance(loaded, Ed25519PublicKey):
        raise RuntimeError("pinned public key is not Ed25519")
    return loaded.public_bytes(Encoding.Raw, PublicFormat.Raw)


def vault_raw_ed25519(key_data: dict[str, Any]) -> bytes:
    inner = key_data.get("data") if "data" in key_data else key_data
    latest = inner.get("latest_version")
    keys = inner.get("keys") or {}
    entry = keys.get(str(latest)) or keys.get(latest)
    if not isinstance(entry, dict) or "public_key" not in entry:
        raise RuntimeError("Vault key metadata missing keys[latest].public_key")
    raw = base64.b64decode(entry["public_key"])
    if len(raw) != 32:
        raise RuntimeError(f"Vault Ed25519 public_key is not 32 bytes ({len(raw)})")
    return raw


def halt_if_generate_would_replace_pin(key_name: str, pin_path: Path) -> int:
    """Inspect Transit. Missing key → BYOK, never type=ed25519 generate."""
    try:
        blob = read_transit_key(key_name)
    except FileNotFoundError:
        print(
            "[HARD-STOP] Transit key "
            f"{key_name!r} is missing.\n"
            "Do NOT: vault write transit/keys/"
            f"{key_name} type=ed25519\n"
            "That mints a new keypair under the same name. Verifiers that "
            "already pin release/release_signing_key.pub would see an "
            "identity mismatch.\n"
            "Import the existing private key via "
            f"transit/keys/{key_name}/import (BYOK) using a temporary "
            "wrapping key (vault read transit/wrapping_key). "
            "See docs/VAULT_TRANSIT_A5.md.",
            file=sys.stderr,
        )
        return 1
    except RuntimeError as exc:
        print(f"[HARD-STOP] {exc}", file=sys.stderr)
        return 1

    inner = blob.get("data", blob)
    exportable = bool(inner.get("exportable"))
    backup = bool(inner.get("allow_plaintext_backup"))
    print(f"[+] transit key {key_name}: exportable={exportable} allow_plaintext_backup={backup}")
    if exportable or backup:
        print(
            "[HARD-STOP] exportable/allow_plaintext_backup must be false. "
            "These flags are immutable after create/import.",
            file=sys.stderr,
        )
        return 1

    pin = pem_raw_ed25519(pin_path.read_bytes())
    vault_raw = vault_raw_ed25519(blob)
    if pin != vault_raw:
        print(
            "[HARD-STOP] Vault public key does not match "
            f"{pin_path}. Label {key_name} is not this identity. "
            "Do not generate a replacement under the same name.",
            file=sys.stderr,
        )
        return 1
    print(f"[+] Vault Transit public key matches pin {pin_path}")
    return 0


def main() -> int:
    pin = Path(__file__).resolve().parent.parent / "release" / "release_signing_key.pub"
    return halt_if_generate_would_replace_pin(VAULT_KEY_NAME, pin)


if __name__ == "__main__":
    sys.exit(main())
