#!/usr/bin/env python3
# scripts/sign_admission_receipt.py
"""
CLI Harness to sign and verify the QuantumFlex P1 Admission Receipt (artifacts/qf_admission_receipt_v1.json).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.admission_receipt import (
    DEFAULT_PRIVATE_KEY_PATH,
    DEFAULT_PUBLIC_KEY_PATH,
    build_admission_payload,
    ensure_or_load_release_keypair,
    sign_admission_receipt,
    verify_admission_receipt,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sign and verify the QuantumFlex Admission Receipt.")
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "artifacts" / "qf_admission_receipt_v1.json",
        help="Output path for signed admission receipt JSON",
    )
    parser.add_argument(
        "--private-key",
        type=Path,
        default=Path(os.environ.get("QF_RELEASE_KEY_PATH", str(DEFAULT_PRIVATE_KEY_PATH))),
        help="Path to Ed25519 release private key PEM (mode 0600)",
    )
    parser.add_argument(
        "--public-key",
        type=Path,
        default=Path(os.environ.get("QF_RELEASE_PUB_PATH", str(DEFAULT_PUBLIC_KEY_PATH))),
        help="Path to Ed25519 release public key PEM",
    )
    parser.add_argument(
        "--init-key",
        action="store_true",
        help="Generate the Ed25519 release keypair (0600) if not already present",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify an existing admission receipt against trusted public key and live disk files",
    )
    args = parser.parse_args()

    priv_key, pub_key = ensure_or_load_release_keypair(
        private_key_path=args.private_key,
        public_key_path=args.public_key,
        auto_generate_if_missing=args.init_key,
    )

    if args.verify_only:
        receipt_data = json.loads(args.output.read_text(encoding="utf-8"))
        verify_admission_receipt(receipt_data, repo_root=REPO_ROOT, trusted_public_key=pub_key)
        print(f"[PASS] Admission Receipt verified: {args.output}")
        return 0

    payload = build_admission_payload(repo_root=REPO_ROOT)
    signed_receipt = sign_admission_receipt(payload=payload, private_key=priv_key)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(signed_receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # Immediately verify signature and live disk hashes before returning success
    verify_admission_receipt(signed_receipt, repo_root=REPO_ROOT, trusted_public_key=pub_key)

    seal = signed_receipt["cryptographic_seal"]
    print(f"[+] QF Admission Receipt signed and verified: {args.output}")
    print(f"    Git Commit         : {payload['git_commit']} ({payload['git_branch']})")
    print(f"    Manifest Root SHA  : {payload['manifest_root_sha256']}")
    print(f"    Payload SHA-256    : {seal['payload_sha256']}")
    print(f"    Release Key Finger : {seal['public_key_fingerprint_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
