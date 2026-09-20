#!/usr/bin/env python3
"""
QuantumFlex Provenance Manifest Verifier & Startup Gate
Verifies live on-disk binaries, Wasm policies, and formal specs against
the cryptographically signed release manifest using a pinned Ed25519 public key.

Enforces Sentinel Policy:
  - Cryptographic signature valid AND all SHA-256 hashes match:
      VERDICT: TRUSTED -> ALLOW (System transition to ACTIVE permitted)
  - Signature invalid OR any hash mismatch:
      VERDICT: MISMATCH -> FAIL-CLOSED / QUARANTINE (Exit Code 1)
"""

import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RELEASE_DIR = os.path.join(WORKSPACE, "release")
MANIFEST_PATH = os.path.join(RELEASE_DIR, "PROVENANCE_MANIFEST.json")
SIG_PATH = os.path.join(RELEASE_DIR, "PROVENANCE_MANIFEST.sig")
PUB_KEY_PATH = os.path.join(RELEASE_DIR, "release_signing_key.pub")

def compute_sha256(abs_path):
    if not os.path.exists(abs_path):
        return None
    h = hashlib.sha256()
    with open(abs_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def verify_file_ed25519(file_path, sig_bytes):
    if not os.path.exists(PUB_KEY_PATH):
        raise FileNotFoundError(f"Pinned public key missing at {PUB_KEY_PATH}")

    with tempfile.NamedTemporaryFile("wb", delete=False) as f_sig:
        f_sig.write(sig_bytes)
        f_sig.flush()
        sig_name = f_sig.name

    try:
        res = subprocess.run([
            "openssl", "pkeyutl", "-verify", "-rawin",
            "-pubin", "-inkey", PUB_KEY_PATH,
            "-in", file_path,
            "-sigfile", sig_name
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return res.returncode == 0
    finally:
        if os.path.exists(sig_name):
            os.remove(sig_name)

def verify():
    if not os.path.exists(MANIFEST_PATH):
        print(f"[FAIL-CLOSED] Missing manifest at {MANIFEST_PATH}")
        return 1

    if not os.path.exists(SIG_PATH):
        print(f"[FAIL-CLOSED] Missing signature file at {SIG_PATH}")
        return 1

    if not os.path.exists(PUB_KEY_PATH):
        print(f"[FAIL-CLOSED] Missing pinned public key at {PUB_KEY_PATH}")
        return 1

    with open(MANIFEST_PATH, "rb") as f:
        manifest_bytes = f.read()

    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except Exception as e:
        print(f"[FAIL-CLOSED] Corrupted manifest JSON: {e}")
        return 1

    # 1. Parse signature file
    sig_b64 = None
    with open(SIG_PATH, "r") as f:
        for line in f:
            if line.startswith("SIGNATURE_B64="):
                sig_b64 = line.strip().split("=", 1)[1]
                break

    if not sig_b64:
        print("[FAIL-CLOSED] Signature file does not contain valid SIGNATURE_B64")
        return 1

    try:
        sig_bytes = base64.b64decode(sig_b64)
    except Exception as e:
        print(f"[FAIL-CLOSED] Malformed base64 signature: {e}")
        return 1

    # 2. Cryptographic Ed25519 Signature Verification
    if not verify_file_ed25519(MANIFEST_PATH, sig_bytes):
        print("[FAIL-CLOSED] Cryptographic signature invalid! Manifest was forged, altered, or unsigned.")
        return 1

    print("[*] Cryptographic Ed25519 Digital Signature: VALID (Verified against pinned release_signing_key.pub)")

    # 3. Artifact Hash Verification (Single SHA-256 Policy)
    artifacts = manifest.get("artifacts", {})
    if not artifacts:
        print("[FAIL-CLOSED] Manifest contains empty artifact set.")
        return 1

    mismatches = []
    missing = []
    verified_count = 0

    for rel_path, data in artifacts.items():
        abs_path = os.path.join(WORKSPACE, rel_path)
        actual_hash = compute_sha256(abs_path)
        if actual_hash is None:
            missing.append(rel_path)
            continue

        expected_hash = data.get("sha256")
        if actual_hash != expected_hash:
            mismatches.append((rel_path, expected_hash, actual_hash))
        else:
            verified_count += 1

    if missing:
        print(f"[FAIL-CLOSED] Missing artifacts on disk: {missing}")
        return 1

    if mismatches:
        print(f"[FAIL-CLOSED] Cryptographic mismatch detected in {len(mismatches)} artifacts:")
        for path, exp, act in mismatches:
            print(f"  - {path}: expected {exp[:16]}..., got {act[:16]}...")
        return 1

    print(f"[+] All {verified_count}/{verified_count} artifacts verified 100% byte-accurate against signed manifest.")
    print("[+] VERDICT: TRUSTED -> ALLOW (QF-A5 Provenance-Authenticated verified)")
    return 0


def verify_package_admission(prefix=None, receipt_path=None, manifest_path=None, sig_path=None):
    """
    Verify installed QuantumFlex package admission (QF-A5).
    Enforces that:
      1. Pinned trust anchor exists.
      2. Admission receipt, provenance manifest, and detached signature exist.
      3. Provenance manifest Ed25519 signature is valid against the pinned trust anchor.
      4. Exact SHA-256 of the receipt matches the signed provenance manifest.
    """
    if not os.path.exists(PUB_KEY_PATH):
        print(f"[FAIL-CLOSED] Missing pinned trust anchor at {PUB_KEY_PATH}")
        return 1

    if not receipt_path and prefix:
        for candidate_sub in ["lib64/cmake/QuantumFlex", "lib/cmake/QuantumFlex"]:
            cand = os.path.join(prefix, candidate_sub, "QuantumFlexAdmission.json")
            if os.path.exists(cand):
                receipt_path = cand
                break
        if not receipt_path:
            receipt_path = os.path.join(prefix, "lib64/cmake/QuantumFlex/QuantumFlexAdmission.json")

    if receipt_path and not manifest_path:
        manifest_path = os.path.join(os.path.dirname(receipt_path), "QuantumFlexAdmission.provenance.json")
    if receipt_path and not sig_path:
        sig_path = os.path.join(os.path.dirname(receipt_path), "QuantumFlexAdmission.provenance.sig")

    if not receipt_path or not os.path.exists(receipt_path):
        print(f"[FAIL-CLOSED] Missing receipt file at {receipt_path}")
        return 1

    if not manifest_path or not os.path.exists(manifest_path):
        print(f"[FAIL-CLOSED] Missing provenance manifest at {manifest_path}")
        return 1

    if not sig_path or not os.path.exists(sig_path):
        print(f"[FAIL-CLOSED] Missing provenance signature file at {sig_path}")
        return 1

    # Read manifest bytes
    with open(manifest_path, "rb") as f:
        manifest_bytes = f.read()

    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except Exception as e:
        print(f"[FAIL-CLOSED] Corrupted provenance manifest JSON: {e}")
        return 1

    if manifest.get("schema") != "quantumflex-admission-provenance-v1":
        print(f"[FAIL-CLOSED] Unsupported provenance schema: {manifest.get('schema')}")
        return 1

    # Read signature bytes
    with open(sig_path, "rb") as f:
        sig_bytes = f.read()

    # Cryptographic Ed25519 signature verification over exact manifest raw bytes
    if not verify_file_ed25519(manifest_path, sig_bytes):
        print("[FAIL-CLOSED] Cryptographic signature invalid! Provenance manifest was forged, altered, or unsigned.")
        return 1

    print("[*] Cryptographic Ed25519 Digital Signature: VALID (Verified against pinned release_signing_key.pub)")

    # Verify receipt hash binding
    expected_receipt_hash = manifest.get("receipt", {}).get("sha256")
    if not expected_receipt_hash:
        print("[FAIL-CLOSED] Provenance manifest missing receipt.sha256 digest")
        return 1

    with open(receipt_path, "rb") as f:
        receipt_bytes = f.read()
    actual_receipt_hash = hashlib.sha256(receipt_bytes).hexdigest()

    if actual_receipt_hash != expected_receipt_hash:
        print(f"[FAIL-CLOSED] Receipt SHA-256 mismatch! Expected {expected_receipt_hash}, got {actual_receipt_hash}. Package artifacts may have been altered.")
        return 1

    print("[*] Admission receipt SHA-256: VALID (Verified against signed provenance manifest)")

    # 7. Verify A4 artifact hashes from receipt against disk
    try:
        receipt_data = json.loads(receipt_bytes.decode("utf-8"))
        artifacts = receipt_data.get("artifacts", [])
        if not artifacts:
            print("[FAIL-CLOSED] Admission receipt contains empty artifact set")
            return 1

        pkg_root = prefix if prefix else os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(receipt_path))))
        mismatches = []
        for art in artifacts:
            rel = art.get("path")
            exp_h = art.get("sha256")
            abs_art = os.path.join(pkg_root, rel)
            if not os.path.isfile(abs_art):
                print(f"[FAIL-CLOSED] Missing package artifact on disk: {abs_art}")
                return 1
            with open(abs_art, "rb") as f_art:
                act_h = hashlib.sha256(f_art.read()).hexdigest()
            if act_h != exp_h:
                mismatches.append((rel, exp_h, act_h))

        if mismatches:
            print(f"[FAIL-CLOSED] Artifact hash mismatch detected in package ({len(mismatches)} files):")
            for r, exp, act in mismatches:
                print(f"  - {r}: expected {exp[:16]}..., got {act[:16]}...")
            return 1
    except Exception as e:
        print(f"[FAIL-CLOSED] Corrupted admission receipt JSON: {e}")
        return 1

    print(f"[+] All {len(artifacts)} installed package artifacts verified byte-accurate.")
    print("[+] VERDICT: ATTESTED -> ALLOW (QF-A5 Package Provenance Verified)")
    return 0


def main():
    import argparse
    parser = argparse.ArgumentParser(description="QuantumFlex Provenance & Package Admission Verifier")
    parser.add_argument("workspace", nargs="?", default=None, help="Target workspace / repository path")
    parser.add_argument("--admit-package", action="store_true", help="Verify installed QuantumFlex package admission (QF-A5)")
    parser.add_argument("--prefix", help="Package install prefix")
    parser.add_argument("--receipt", help="Path to QuantumFlexAdmission.json")
    parser.add_argument("--manifest", help="Path to QuantumFlexAdmission.provenance.json")
    parser.add_argument("--signature", help="Path to QuantumFlexAdmission.provenance.sig")
    args = parser.parse_args()

    if args.admit_package or args.prefix or args.receipt or args.manifest or args.signature:
        return verify_package_admission(
            prefix=args.prefix,
            receipt_path=args.receipt,
            manifest_path=args.manifest,
            sig_path=args.signature
        )

    return verify()


if __name__ == "__main__":
    sys.exit(main())
