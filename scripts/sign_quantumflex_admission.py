#!/usr/bin/env python3
"""
QuantumFlex Admission Provenance Signer (QF-A5)

Generates and cryptographically signs a detached Ed25519 provenance manifest
binding an installed QuantumFlexAdmission.json receipt:
  QuantumFlexAdmission.provenance.json
  QuantumFlexAdmission.provenance.sig

Chain of Custody:
  Installed Artifacts -> SHA-256 -> QuantumFlexAdmission.json (A4)
  QuantumFlexAdmission.json -> SHA-256 -> QuantumFlexAdmission.provenance.json (A5)
  QuantumFlexAdmission.provenance.json -> Ed25519 Signature -> release_signing_key.pub
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys


def sign_admission_receipt(receipt_path: str, private_key_path: str,
                           output_dir: str = None, commit: str = None) -> tuple[str, str]:
    if not os.path.isfile(receipt_path):
        raise FileNotFoundError(f"Receipt file not found: {receipt_path}")
    if not os.path.isfile(private_key_path):
        raise FileNotFoundError(f"Private signing key not found: {private_key_path}")

    # 1. Read exact raw bytes of receipt
    with open(receipt_path, "rb") as f:
        receipt_bytes = f.read()

    receipt_sha256 = hashlib.sha256(receipt_bytes).hexdigest()

    # 2. Extract metadata from receipt JSON if present
    package_name = "QuantumFlex"
    package_version = "2.1.0"
    try:
        data = json.loads(receipt_bytes.decode("utf-8"))
        package_name = data.get("package", package_name)
        package_version = data.get("version", package_version)
        if commit is None:
            commit = data.get("source_commit", "UNKNOWN")
    except Exception:
        pass

    if commit is None:
        commit = "UNKNOWN"

    receipt_filename = os.path.basename(receipt_path)

    # 3. Formulate canonical A5 provenance document
    provenance_doc = {
        "schema": "quantumflex-admission-provenance-v1",
        "package": package_name,
        "version": package_version,
        "receipt": {
            "path": receipt_filename,
            "sha256": receipt_sha256
        },
        "source_commit": commit
    }

    provenance_bytes = json.dumps(provenance_doc, indent=2, sort_keys=True).encode("utf-8") + b"\n"

    # 4. Resolve output paths
    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(receipt_path))
    os.makedirs(output_dir, exist_ok=True)

    manifest_path = os.path.join(output_dir, "QuantumFlexAdmission.provenance.json")
    sig_path = os.path.join(output_dir, "QuantumFlexAdmission.provenance.sig")

    with open(manifest_path, "wb") as f:
        f.write(provenance_bytes)

    # 5. Sign raw bytes with Ed25519 private key
    res = subprocess.run([
        "openssl", "pkeyutl", "-sign", "-rawin",
        "-inkey", private_key_path,
        "-in", manifest_path,
        "-out", sig_path
    ], capture_output=True, text=True)

    if res.returncode != 0:
        raise RuntimeError(f"OpenSSL signing failed: {res.stderr.strip()}")

    return manifest_path, sig_path


def main():
    parser = argparse.ArgumentParser(description="Sign QuantumFlex Admission Receipt (QF-A5)")
    parser.add_argument("--receipt", required=True, help="Path to QuantumFlexAdmission.json")
    parser.add_argument("--key", required=True, help="Path to Ed25519 private key")
    parser.add_argument("--output-dir", help="Directory to emit manifest and signature (default: receipt directory)")
    parser.add_argument("--commit", help="Source git commit hash")
    args = parser.parse_args()

    try:
        manifest_path, sig_path = sign_admission_receipt(
            receipt_path=args.receipt,
            private_key_path=args.key,
            output_dir=args.output_dir,
            commit=args.commit
        )
        print(f"[+] Provenance Manifest: {manifest_path}")
        print(f"[+] Detached Signature:  {sig_path}")
        return 0
    except Exception as e:
        print(f"[-] Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
