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

if __name__ == "__main__":
    sys.exit(verify())
