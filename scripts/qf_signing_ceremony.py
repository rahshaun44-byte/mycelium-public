#!/usr/bin/env python3
"""One signing ceremony, multiple artifact classes.

Hash → (manifest) → Ed25519 over canonical bytes → detached sidecar →
pinned verify → gate. Planes are separated by key_id so a leak in one
monetization vector does not resign another.

This module is the in-repo ceremony helper. The host judge
(host-trust/verify-provenance) stays self-contained and must not import it.
"""

from __future__ import annotations

import base64
import json
from typing import Any

# One monetization/vector boundary → one key_id namespace.
PLANES: dict[str, dict[str, str]] = {
    "host-release-a5": {
        "key_id": "mycelium-a5-ed25519-v1",
        "pin": "release/release_signing_key.pub",
        "signed_object": "release/PROVENANCE_MANIFEST.json",
        "gate": "~/.local/libexec/quantumflex/verify-provenance",
    },
    "mobile-ota": {
        "key_id": "mobile-ed25519-v1",
        "pin": "mobile/release_signing_key.pub",
        "signed_object": "mobile/RELEASE_MANIFEST.json",
        "gate": "mobile/setup-mobile.sh (hash today; detached sig is the gap)",
    },
    "quantumflex-admission": {
        "key_id": "quantumflex-admission-ed25519-v1",
        "pin": "same as host-release only after an export ceremony",
        "signed_object": "QuantumFlexAdmission.json",
        "gate": "cmake/AdmitQuantumFlex.cmake (hash binding until signed:true)",
    },
}

HOST_A5_KEY_ID = PLANES["host-release-a5"]["key_id"]
HOST_A5_PLANE = "host-release-a5"

# Verifier whitelist: exact (plane, key_id). Never a keyring.
ALLOWED_PINS: frozenset[tuple[str, str]] = frozenset(
    {
        (HOST_A5_PLANE, HOST_A5_KEY_ID),
    }
)


def canonical_manifest_bytes(obj: Any) -> bytes:
    """Frozen encoding: sorted keys, indent 2, trailing newline, UTF-8.

    Timestamps belong in unsigned sidecar fields or in a field frozen
    *before* this function runs. Do not pretty-print twice.
    """
    text = json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    return text.encode("utf-8")


def parse_sidecar(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        fields[key.strip()] = value.strip()
    return fields


def encode_sidecar(
    *,
    signature_b64: str,
    key_id: str | None,
    public_key_pin: str = "release_signing_key.pub",
    timestamp: str | None = None,
) -> str:
    lines = [
        "SIGNATURE_ALGORITHM=Ed25519",
        f"PUBLIC_KEY_PIN={public_key_pin}",
    ]
    if key_id:
        lines.append(f"KEY_ID={key_id}")
    lines.append(f"SIGNATURE_B64={signature_b64}")
    if timestamp:
        lines.append(f"TIMESTAMP={timestamp}")
    return "\n".join(lines) + "\n"


def declared_key_id(manifest: dict[str, Any], sidecar: dict[str, str]) -> str | None:
    signing = manifest.get("signing")
    mid = None
    if isinstance(signing, dict):
        raw = signing.get("key_id")
        mid = raw if isinstance(raw, str) and raw else None
    sid = sidecar.get("KEY_ID") or None
    if mid and sid and mid != sid:
        raise ValueError(f"key_id mismatch: manifest={mid!r} sidecar={sid!r}")
    return mid or sid


def pin_matches(declared: str | None, pinned: str) -> bool:
    """Historical 2.1.0 manifests omit key_id; the file pin is the authority.

    When a key_id is declared it must equal the verifier's single pin.
    Never iterate a keyring.
    """
    if declared is None:
        return True
    return declared == pinned


def vault_sign_input_b64(message: bytes) -> str:
    """Vault transit/sign input: Base64 of the *raw* message.

    Ed25519 (RFC 8032) is not Ed25519ph. Do not SHA-256 the manifest first.
    """
    return base64.b64encode(message).decode("ascii")


def parse_vault_signature(signature_field: str) -> bytes:
    """Vault returns vault:<key-version>:<payload>. Payload is Base64 of 64 raw bytes."""
    parts = signature_field.strip().split(":")
    if len(parts) < 3 or parts[0] != "vault":
        raise ValueError(f"unexpected Vault signature field: {signature_field!r}")
    raw = base64.b64decode(parts[-1])
    if len(raw) != 64:
        raise ValueError(f"Vault Ed25519 signature is not 64 bytes ({len(raw)})")
    return raw


def schema_enforces_key_id(schema: object) -> bool:
    return schema == "2.2.0"
