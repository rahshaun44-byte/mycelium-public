#!/usr/bin/env python3
"""
QuantumFlex Provenance Seal (QFX-SEAL) v1.0.0
Canonical structural provenance seal for micro-DePIN telemetry and artifacts.

Envelope fields:
- seal_version: "1.0.0"
- node_id: QFX node identifier (e.g. QFX-CORE-YOGA7-01)
- content_sha256: SHA-256 of raw message payload (lowercase hex)
- policy_epoch: Hash or version identifier of active membrane policy
- kem_suite: Active KEM suite (ML-KEM-768, FrodoKEM-976-AES, X25519) - NEVER "NONE"
- ts_unix: Monotonic/UTC timestamp in seconds
- nonce: Random 16-byte hex nonce
- alg: Signature/MAC algorithm ("HMAC-SHA256" Phase-1, "Ed25519", etc.)
- sig: Signature or MAC over canonical ordered message
"""

import argparse
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
from typing import Any, Dict, Tuple


CANONICAL_FIELDS = [
    "seal_version",
    "node_id",
    "content_sha256",
    "policy_epoch",
    "kem_suite",
    "ts_unix",
    "nonce",
    "alg",
]


def canonical_message(seal: Dict[str, Any]) -> bytes:
    """Computes ordered newline-joined canonical message representation."""
    lines = [f"{k}={seal[k]}" for k in CANONICAL_FIELDS]
    return "\n".join(lines).encode("utf-8")


def compute_content_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def compute_policy_epoch(policy_path: str, provider_conf_path: str = None) -> str:
    """Computes composite hash of active OPA policy and provider configuration."""
    h = hashlib.sha256()
    with open(policy_path, "rb") as f:
        h.update(f.read())
    if provider_conf_path and os.path.isfile(provider_conf_path):
        with open(provider_conf_path, "rb") as f:
            h.update(f.read())
    return h.hexdigest()[:16]


def create_seal(
    content: bytes,
    node_id: str,
    key: bytes,
    policy_epoch: str,
    kem_suite: str = "ML-KEM-768",
    alg: str = "HMAC-SHA256",
) -> Dict[str, Any]:
    if kem_suite.upper() == "NONE":
        raise ValueError("Fail-secure: KEM suite cannot be NONE (node halted)")
    if len(key) < 32:
        raise ValueError("Key length must be at least 32 bytes (256 bits)")

    seal = {
        "seal_version": "1.0.0",
        "node_id": node_id,
        "content_sha256": compute_content_sha256(content),
        "policy_epoch": policy_epoch,
        "kem_suite": kem_suite,
        "ts_unix": int(time.time()),
        "nonce": secrets.token_hex(16),
        "alg": alg,
    }

    msg = canonical_message(seal)
    sig = hmac.new(key, msg, hashlib.sha256).hexdigest()
    seal["sig"] = sig
    return seal


def verify_seal(
    content: bytes,
    seal: Dict[str, Any],
    key: bytes,
    expected_node_id: str = None,
    max_skew_sec: int = 300,
) -> Tuple[bool, str]:
    # 1. Structural check
    for f in CANONICAL_FIELDS + ["sig"]:
        if f not in seal:
            return False, f"missing_field_{f}"

    if seal.get("kem_suite", "").upper() == "NONE":
        return False, "kem_suite_none_halt"

    # 2. Node bind check
    if expected_node_id and seal["node_id"] != expected_node_id:
        return False, "node_id_mismatch"

    # 3. Clock skew check
    now = int(time.time())
    ts = seal["ts_unix"]
    if abs(now - ts) > max_skew_sec:
        return False, "timestamp_skew_exceeded"

    # 4. Content payload hash check
    actual_content_hash = compute_content_sha256(content)
    if not hmac.compare_digest(actual_content_hash, seal["content_sha256"]):
        return False, "content_hash_mismatch"

    # 5. Cryptographic signature check
    msg = canonical_message(seal)
    expected_sig = hmac.new(key, msg, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_sig, seal["sig"]):
        return False, "signature_verification_failed"

    return True, "ok"


def main():
    parser = argparse.ArgumentParser(description="QuantumFlex Provenance Seal CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    seal_p = subparsers.add_parser("seal", help="Seal a payload")
    seal_p.add_argument("--payload", required=True, help="Path to payload file")
    seal_p.add_argument("--node-id", default=os.getenv("QFX_NODE_ID", "QFX-CORE-YOGA7-01"))
    seal_p.add_argument("--key", default=os.getenv("QFX_SEAL_KEY"))
    seal_p.add_argument("--policy", help="Path to membrane_health.rego")
    seal_p.add_argument("--kem-suite", default="ML-KEM-768")
    seal_p.add_argument("--output", help="Path to output seal JSON")

    verify_p = subparsers.add_parser("verify", help="Verify a sealed payload")
    verify_p.add_argument("--payload", required=True, help="Path to payload file")
    verify_p.add_argument("--seal", required=True, help="Path to seal JSON")
    verify_p.add_argument("--key", default=os.getenv("QFX_SEAL_KEY"))
    verify_p.add_argument("--expected-node-id", default=os.getenv("QFX_NODE_ID"))

    args = parser.parse_args()

    if not args.key:
        print("[!] Error: --key or QFX_SEAL_KEY environment variable is required", file=sys.stderr)
        sys.exit(2)

    key_bytes = bytes.fromhex(args.key) if len(args.key) == 64 else args.key.encode("utf-8")

    if args.command == "seal":
        with open(args.payload, "rb") as f:
            content = f.read()

        policy_epoch = "default_epoch"
        if args.policy and os.path.isfile(args.policy):
            policy_epoch = compute_policy_epoch(args.policy)

        seal_obj = create_seal(
            content=content,
            node_id=args.node_id,
            key=key_bytes,
            policy_epoch=policy_epoch,
            kem_suite=args.kem_suite,
        )

        seal_json = json.dumps(seal_obj, indent=2)
        if args.output:
            with open(args.output, "w") as f:
                f.write(seal_json + "\n")
            print(f"[+] Seal written to {args.output}")
        else:
            print(seal_json)

    elif args.command == "verify":
        with open(args.payload, "rb") as f:
            content = f.read()
        with open(args.seal, "r") as f:
            seal_obj = json.load(f)

        ok, reason = verify_seal(
            content=content,
            seal=seal_obj,
            key=key_bytes,
            expected_node_id=args.expected_node_id,
        )
        if ok:
            print(f"[PASS] Provenance seal verified: {reason}")
            sys.exit(0)
        else:
            print(f"[FAIL] Seal verification rejected: {reason}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
