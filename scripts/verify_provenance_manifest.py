#!/usr/bin/env python3
"""In-repo pointer — not the judge.

The defendant cannot evaluate itself. This script only execs the host trust
anchor at ~/.local/libexec/quantumflex/verify-provenance. Editing this file
cannot change the verdict of a service that already points at the libexec copy.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def judge_path() -> Path:
    override = os.environ.get("QF_TRUST_ANCHOR")
    root = Path(override).expanduser() if override else Path.home() / ".local/libexec/quantumflex"
    return root / "verify-provenance"


def main() -> int:
    judge = judge_path()
    if not judge.is_file() or not os.access(judge, os.X_OK):
        print(
            "[FAIL-CLOSED] Host trust anchor missing or not executable:\n"
            f"  {judge}\n"
            "Install once from a trusted checkout:\n"
            "  ./scripts/install_host_trust_anchor.sh",
            file=sys.stderr,
        )
        return 1

    repo_root = Path(__file__).resolve().parent.parent
    default_manifest = repo_root / "release" / "PROVENANCE_MANIFEST.json"

    args = [str(judge)]
    if len(sys.argv) == 1:
        args.extend([str(default_manifest), "--repo-root", str(repo_root)])
    else:
        args.extend(sys.argv[1:])
        if "--repo-root" not in sys.argv:
            args.extend(["--repo-root", str(repo_root)])

    os.execv(str(judge), args)
    return 1



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
