#!/usr/bin/env python3
"""One signing ceremony, multiple artifact classes.

Hash → (manifest) → Ed25519 over canonical bytes → detached sidecar →
pinned verify → gate. Planes are separated by key_id so a leak in one
monetization vector does not resign another.

This module is the in-repo ceremony helper. The host judge
(host-trust/verify-provenance) stays self-contained and must not import it.
"""

from __future__ import annotations

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
