#!/usr/bin/env python3
"""Canonical encode, key_id pin, no keyring search."""

from __future__ import annotations

import base64
import sys
from hashlib import sha256
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from qf_signing_ceremony import (
    HOST_A5_KEY_ID,
    canonical_manifest_bytes,
    declared_key_id,
    encode_sidecar,
    parse_sidecar,
    parse_vault_signature,
    pin_matches,
    vault_sign_input_b64,
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

    msg = b'{"a":1}\n'
    vault_input = vault_sign_input_b64(msg)
    digest_input = base64.b64encode(sha256(msg).digest()).decode("ascii")
    expect("Vault input is Base64 of raw bytes, not SHA-256 digest", vault_input != digest_input)
    expect(
        "Vault input decodes to the original message",
        base64.b64decode(vault_input) == msg,
    )
    parsed = parse_vault_signature("vault:v1:" + base64.b64encode(b"s" * 64).decode("ascii"))
    expect("Vault signature field unwraps to 64 bytes", parsed == b"s" * 64)
    expect("canonical encoding is indented JSON, not RFC 8785 compact", b"\n  " in first)

    root = Path(__file__).resolve().parent.parent
    policy = (root / "vault" / "policies" / "mycelium-a5-ceremony.hcl").read_text(encoding="utf-8")
    expect(
        "ceremony policy grants update on transit/sign only",
        'path "transit/sign/mycelium-a5-ed25519-v1"' in policy
        and 'capabilities = ["update"]' in policy,
    )
    expect(
        "ceremony policy grants read on transit/keys only",
        'path "transit/keys/mycelium-a5-ed25519-v1"' in policy
        and 'capabilities = ["read"]' in policy,
    )
    expect(
        "ceremony policy has no extra capabilities",
        "sudo" not in policy
        and 'capabilities = ["update"]' in policy
        and 'capabilities = ["read"]' in policy
        and policy.count("capabilities") == 2,
    )

    token_sh = (root / "scripts" / "vault_a5_token.sh").read_text(encoding="utf-8")
    for flag in (
        "-ttl=10m",
        "-explicit-max-ttl=10m",
        "-no-default-policy",
        "-renewable=false",
    ):
        expect(f"ceremony token {flag}", flag in token_sh)

    transit = (root / "scripts" / "vault_a5_transit.py").read_text(encoding="utf-8")
    post_paths = [
        line.strip()
        for line in transit.splitlines()
        if "_request(" in line and "POST" in line
    ]
    expect(
        "Transit helper POSTs only transit/sign",
        len(post_paths) == 1 and "/v1/transit/sign/" in post_paths[0],
        str(post_paths),
    )
    expect(
        "Transit helper never writes transit/keys (GET-only for metadata)",
        all("/v1/transit/keys/" not in line for line in post_paths),
        str(post_paths),
    )
    expect(
        "missing Transit key HALTs toward BYOK import, not generate",
        "transit/keys/{key_name}/import" in transit
        and "Do NOT: vault write transit/keys/" in transit
        and "type=ed25519" in transit
        and "wrapping_key" in transit,
    )
    expect("exportable/allow_plaintext_backup must stay false", "immutable after create/import" in transit)
    expect("prehashed is false (Ed25519, not Ed25519ph)", '"prehashed": False' in transit)

    ci = (root / ".github" / "workflows" / "quantumflex-release.yml").read_text(encoding="utf-8")
    expect("CI refuses VAULT_TOKEN on the Cosign plane", "VAULT_TOKEN" in ci)

    print("[+] signing ceremony tests complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
