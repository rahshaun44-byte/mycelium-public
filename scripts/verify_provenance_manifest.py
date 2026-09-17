#!/usr/bin/env python3
"""
QuantumFlex Provenance Manifest Verifier & Startup Gate
Verifies live on-disk binaries, Wasm policies, and formal specs against
the cryptographically bound release manifest.
Enforces Sentinel Policy:
  - All hashes match: Verdict TRUSTED -> ACTIVE
  - Any hash mismatch: Verdict MISMATCH -> FAIL-CLOSED / QUARANTINE
"""

import hashlib
import json
import os
import sys

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RELEASE_DIR = os.path.join(WORKSPACE, "release")
MANIFEST_PATH = os.path.join(RELEASE_DIR, "PROVENANCE_MANIFEST.json")
SIG_PATH = os.path.join(RELEASE_DIR, "PROVENANCE_MANIFEST.sig")

def compute_hashes(abs_path):
    if not os.path.exists(abs_path):
        return None
    h_sha256 = hashlib.sha256()
    h_sha3 = hashlib.sha3_256()
    h_blake2 = hashlib.blake2b()
    with open(abs_path, "rb") as f:
        while chunk := f.read(65536):
            h_sha256.update(chunk)
            h_sha3.update(chunk)
            h_blake2.update(chunk)
    return {
        "sha256": h_sha256.hexdigest(),
        "sha3_256": h_sha3.hexdigest(),
        "blake2b": h_blake2.hexdigest()
    }

def verify():
    if not os.path.exists(MANIFEST_PATH):
        print(f"[FAIL-CLOSED] Missing manifest at {MANIFEST_PATH}")
        return 1

    if not os.path.exists(SIG_PATH):
        print(f"[FAIL-CLOSED] Missing seal at {SIG_PATH}")
        return 1

    with open(MANIFEST_PATH, "r") as f:
        manifest_raw = f.read()

    try:
        manifest = json.loads(manifest_raw)
    except Exception as e:
        print(f"[FAIL-CLOSED] Corrupted manifest JSON: {e}")
        return 1

    # Check manifest seal
    expected_seal = None
    with open(SIG_PATH, "r") as f:
        for line in f:
            if line.startswith("PROVENANCE_SEAL_SHA256="):
                expected_seal = line.strip().split("=")[1]
                break

    actual_seal = hashlib.sha256(manifest_raw.strip().encode("utf-8")).hexdigest()
    # Also check without strip in case of trailing newline
    actual_seal_raw = hashlib.sha256(manifest_raw.encode("utf-8")).hexdigest()
    
    if expected_seal not in (actual_seal, actual_seal_raw):
        print("[FAIL-CLOSED] Manifest integrity violation: seal does not match manifest content!")
        return 1

    print("[*] Manifest cryptographic seal: VALID")
    artifacts = manifest.get("artifacts", {})
    if not artifacts:
        print("[FAIL-CLOSED] Manifest contains empty artifact set.")
        return 1

    mismatches = []
    missing = []
    verified_count = 0

    for rel_path, expected in artifacts.items():
        abs_path = os.path.join(WORKSPACE, rel_path)
        actual = compute_hashes(abs_path)
        if actual is None:
            missing.append(rel_path)
            continue

        if actual["sha256"] != expected["sha256"]:
            mismatches.append((rel_path, "sha256", expected["sha256"], actual["sha256"]))
        elif actual["sha3_256"] != expected["sha3_256"]:
            mismatches.append((rel_path, "sha3_256", expected["sha3_256"], actual["sha3_256"]))
        elif actual["blake2b"] != expected["blake2b"]:
            mismatches.append((rel_path, "blake2b", expected["blake2b"], actual["blake2b"]))
        else:
            verified_count += 1

    if missing:
        print(f"[FAIL-CLOSED] Missing artifacts: {missing}")
        return 1

    if mismatches:
        print(f"[FAIL-CLOSED] Cryptographic mismatch detected in {len(mismatches)} artifacts:")
        for path, alg, exp, act in mismatches:
            print(f"  - {path} [{alg}]: expected {exp[:16]}..., got {act[:16]}...")
        return 1

    print(f"[+] All {verified_count}/{verified_count} artifacts verified 100% byte-accurate.")
    print("[+] VERDICT: TRUSTED -> ALLOW (System transition to ACTIVE permitted)")
    return 0

if __name__ == "__main__":
    sys.exit(verify())
