#!/usr/bin/env python3
"""
QuantumFlex Mobile Artifact Signer & Verifier (QF-M1)
=====================================================
Generates canonical, signed distribution manifests for mobile assets:
- Computes raw byte SHA-256 of artifact
- Creates <artifact>.manifest.json with schema quantumflex-mobile-distribution-v1
- Signs exact canonical bytes of manifest using Ed25519 private key to produce <artifact>.sig
- Verifies manifest signature against pinned mobile trust anchor (release_signing_key.pub)
- Verifies artifact SHA-256 matches manifest
"""

import os
import sys
import json
import time
import hashlib
import argparse
import subprocess
from typing import Tuple, Dict, Any, Optional

SCHEMA = "quantumflex-mobile-distribution-v1"
VERSION = "2.6.0-qf-m1"

def compute_file_sha256(path: str) -> Tuple[str, int]:
    hasher = hashlib.sha256()
    total_bytes = 0
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
            total_bytes += len(chunk)
    return hasher.hexdigest(), total_bytes

def generate_keypair(private_key_path: str, public_key_path: str):
    os.makedirs(os.path.dirname(os.path.abspath(private_key_path)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(public_key_path)), exist_ok=True)

    # Generate Ed25519 private key
    res = subprocess.run(
        ["openssl", "genpkey", "-algorithm", "Ed25519", "-out", private_key_path],
        capture_output=True, text=True
    )
    if res.returncode != 0:
        raise RuntimeError(f"Failed to generate Ed25519 key: {res.stderr.strip()}")
    os.chmod(private_key_path, 0o400)

    # Extract public key
    res2 = subprocess.run(
        ["openssl", "pkey", "-in", private_key_path, "-pubout", "-out", public_key_path],
        capture_output=True, text=True
    )
    if res2.returncode != 0:
        raise RuntimeError(f"Failed to extract public key: {res2.stderr.strip()}")
    os.chmod(public_key_path, 0o444)

def sign_mobile_artifact(
    artifact_path: str,
    private_key_path: str,
    output_dir: Optional[str] = None,
    version: str = VERSION,
    extra_metadata: Optional[Dict[str, Any]] = None
) -> Tuple[str, str]:
    if not os.path.isfile(artifact_path):
        raise FileNotFoundError(f"Artifact not found: {artifact_path}")
    if not os.path.isfile(private_key_path):
        raise FileNotFoundError(f"Private signing key not found: {private_key_path}")

    sha256, size_bytes = compute_file_sha256(artifact_path)
    filename = os.path.basename(artifact_path)

    manifest_doc = {
        "schema": SCHEMA,
        "version": version,
        "artifact": filename,
        "sha256": sha256,
        "size_bytes": size_bytes,
        "signed_at": int(time.time()),
    }
    if extra_metadata:
        manifest_doc.update(extra_metadata)

    manifest_bytes = json.dumps(manifest_doc, indent=2, sort_keys=True).encode("utf-8") + b"\n"

    target_dir = output_dir or os.path.dirname(os.path.abspath(artifact_path))
    os.makedirs(target_dir, exist_ok=True)

    manifest_path = os.path.join(target_dir, f"{filename}.manifest.json")
    sig_path = os.path.join(target_dir, f"{filename}.sig")

    with open(manifest_path, "wb") as f:
        f.write(manifest_bytes)

    # Sign manifest bytes with Ed25519 private key
    res = subprocess.run([
        "openssl", "pkeyutl", "-sign", "-rawin",
        "-inkey", private_key_path,
        "-in", manifest_path,
        "-out", sig_path
    ], capture_output=True, text=True)

    if res.returncode != 0:
        raise RuntimeError(f"OpenSSL Ed25519 signing failed: {res.stderr.strip()}")

    os.chmod(sig_path, 0o644)
    return manifest_path, sig_path

def verify_mobile_artifact(
    artifact_path: str,
    manifest_path: str,
    sig_path: str,
    public_key_path: str
) -> Tuple[bool, str]:
    if not os.path.isfile(artifact_path):
        return False, f"Artifact missing: {artifact_path}"
    if not os.path.isfile(manifest_path):
        return False, f"Manifest missing: {manifest_path}"
    if not os.path.isfile(sig_path):
        return False, f"Signature missing: {sig_path}"
    if not os.path.isfile(public_key_path):
        return False, f"Public key trust anchor missing: {public_key_path}"

    # 1. Verify manifest signature against pinned public key
    res = subprocess.run([
        "openssl", "pkeyutl", "-verify", "-rawin", "-pubin",
        "-inkey", public_key_path,
        "-in", manifest_path,
        "-sigfile", sig_path
    ], capture_output=True, text=True)

    if res.returncode != 0 or "Signature Verified Successfully" not in res.stdout:
        return False, f"Signature verification FAILED against trust anchor: {res.stderr.strip() or res.stdout.strip()}"

    # 2. Parse manifest
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception as e:
        return False, f"Malformed manifest JSON: {e}"

    if manifest.get("schema") != SCHEMA:
        return False, f"Invalid manifest schema: {manifest.get('schema')} (expected {SCHEMA})"

    expected_sha = manifest.get("sha256")
    actual_sha, actual_size = compute_file_sha256(artifact_path)

    if actual_sha.lower() != expected_sha.lower():
        return False, f"SHA-256 MISMATCH for {artifact_path}: expected {expected_sha}, actual {actual_sha}"

    return True, f"Verified against trust anchor ({manifest.get('artifact')}, {actual_size} bytes, SHA-256: {actual_sha[:16]}...)"

def main():
    parser = argparse.ArgumentParser(description="QuantumFlex Mobile Artifact Signer / Verifier")
    parser.add_argument("--artifact", help="Path to artifact file (e.g. qflex_cli.py or app-debug.apk)")
    parser.add_argument("--key", help="Path to Ed25519 private key for signing")
    parser.add_argument("--pubkey", help="Path to Ed25519 public key for verification")
    parser.add_argument("--verify", action="store_true", help="Verify artifact against manifest and sig")
    parser.add_argument("--manifest", help="Path to manifest file (for verify)")
    parser.add_argument("--sig", help="Path to signature file (for verify)")
    parser.add_argument("--output-dir", help="Output directory for generated manifest and sig")
    parser.add_argument("--generate-keypair", action="store_true", help="Generate a new Ed25519 keypair")
    parser.add_argument("--priv-out", help="Path for generated private key")
    parser.add_argument("--pub-out", help="Path for generated public key")
    args = parser.parse_args()

    if args.generate_keypair:
        if not args.priv_out or not args.pub_out:
            print("[!] Error: --priv-out and --pub-out required for --generate-keypair")
            sys.exit(1)
        generate_keypair(args.priv_out, args.pub_out)
        print(f"[+] Generated Ed25519 private key: {args.priv_out} (mode 0400)")
        print(f"[+] Generated Ed25519 public key:  {args.pub_out} (mode 0444)")
        sys.exit(0)

    if args.verify:
        if not args.artifact or not args.pubkey:
            print("[!] Error: --artifact and --pubkey required for verification")
            sys.exit(1)
        m_path = args.manifest or f"{args.artifact}.manifest.json"
        s_path = args.sig or f"{args.artifact}.sig"
        ok, reason = verify_mobile_artifact(args.artifact, m_path, s_path, args.pubkey)
        if ok:
            print(f"[PASS] {reason}")
            sys.exit(0)
        else:
            print(f"[FAIL] {reason}")
            sys.exit(1)

    if not args.artifact or not args.key:
        print("[!] Error: --artifact and --key required for signing")
        parser.print_help()
        sys.exit(1)

    try:
        m, s = sign_mobile_artifact(args.artifact, args.key, output_dir=args.output_dir)
        print(f"[+] Signed Manifest: {m}")
        print(f"[+] Detached Sig:   {s}")
    except Exception as e:
        print(f"[!] Signing failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
