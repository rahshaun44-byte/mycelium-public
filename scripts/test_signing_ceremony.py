#!/usr/bin/env python3
"""Canonical encode, key_id pin, no keyring search."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from qf_signing_ceremony import (
    HOST_A5_KEY_ID,
    canonical_manifest_bytes,
    declared_key_id,
    encode_sidecar,
    parse_sidecar,
    pin_matches,
)


def expect(label: str, ok: bool, detail: str = "") -> None:
    if not ok:
        raise SystemExit(f"[FAIL] {label}{': ' + detail if detail else ''}")
    print(f"[PASS] {label}")


def main() -> int:
    obj = {"b": 1, "a": {"z": 2, "m": 3}}
    first = canonical_manifest_bytes(obj)
    second = canonical_manifest_bytes(obj)
    expect("canonical bytes are stable", first == second)
    expect("canonical is UTF-8 JSON with trailing newline", first.endswith(b"\n"))
    expect("canonical sorts keys", first.find(b'"a"') < first.find(b'"b"'))

    sidecar = encode_sidecar(signature_b64="QQ==", key_id=HOST_A5_KEY_ID, timestamp="t")
    fields = parse_sidecar(sidecar)
    expect("sidecar records KEY_ID", fields.get("KEY_ID") == HOST_A5_KEY_ID)
    expect("TIMESTAMP stays in sidecar (unsigned)", fields.get("TIMESTAMP") == "t")

    expect(
        "historical 2.1.0 without key_id matches any pin file",
        pin_matches(None, HOST_A5_KEY_ID),
    )
    expect("declared A5 key_id matches A5 pin", pin_matches(HOST_A5_KEY_ID, HOST_A5_KEY_ID))
    expect(
        "mobile key_id does not match A5 pin (no try-all)",
        not pin_matches("mobile-ed25519-v1", HOST_A5_KEY_ID),
    )

    try:
        declared_key_id(
            {"signing": {"key_id": HOST_A5_KEY_ID}},
            {"KEY_ID": "mobile-ed25519-v1"},
        )
        expect("manifest vs sidecar key_id mismatch raises", False)
    except ValueError as exc:
        expect("manifest vs sidecar key_id mismatch raises", "mismatch" in str(exc))

    print("[+] signing ceremony tests complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
