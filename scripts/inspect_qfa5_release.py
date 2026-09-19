#!/usr/bin/env python3
"""Read-only QF-A5 inspection. Not the judge. Writes nothing under libexec.

Prints the authoritative schema, every signed artifact, independent openssl
signature check, and sha256/size comparison. Exit codes:

  0  signature valid and every artifact byte-accurate (known-good tree)
  2  signature valid, but hashes/paths failed (HARD-STOP — do not lock)
  1  signature missing/invalid, or the manifest is unreadable (HARD-STOP)
"""

from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
MANIFEST = WORKSPACE / "release" / "PROVENANCE_MANIFEST.json"
SIDECAR = WORKSPACE / "release" / "PROVENANCE_MANIFEST.sig"
BOOTSTRAP_KEY = WORKSPACE / "release" / "release_signing_key.pub"

# systemd/Quadlet templates are inspected by the operator. They are not
# QF-A5 artifacts today — listing them here keeps that gap visible.
UNSIGNED_UNITS = [
    "systemd-backup/quantum-flex-engine-mycelium.service",
    "systemd-backup/quantumflex-runner.container",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def openssl_verify(manifest: Path, sig_bytes: bytes, key: Path) -> bool:
    with tempfile.NamedTemporaryFile("wb", delete=False) as handle:
        handle.write(sig_bytes)
        sig_name = handle.name
    try:
        result = subprocess.run(
            [
                "openssl",
                "pkeyutl",
                "-verify",
                "-rawin",
                "-pubin",
                "-inkey",
                str(key),
                "-in",
                str(manifest),
                "-sigfile",
                sig_name,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        Path(sig_name).unlink(missing_ok=True)
    return result.returncode == 0


def main() -> int:
    print("QF-A5 inspection (read-only). This is not admission.")
    print(f"repo     : {WORKSPACE}")
    print(f"manifest : {MANIFEST}")
    print(f"sidecar  : {SIDECAR}")
    print(f"bootstrap: {BOOTSTRAP_KEY}")
    print()
    print("Authoritative on-disk contract (schema 2.1.0):")
    print("  artifacts[rel_path] = {sha256, size_bytes, assurance_level, description}")
    print("  PROVENANCE_MANIFEST.sig contains SIGNATURE_B64= (Ed25519 over raw bytes)")
    print("  openssl pkeyutl -sign/-verify -rawin")
    print("  release/MANIFEST.json (schema 1.5.0) is a different policy-bundle file.")
    print()

    if not MANIFEST.is_file() or not SIDECAR.is_file() or not BOOTSTRAP_KEY.is_file():
        print("[HARD-STOP] Manifest, sidecar, or bootstrap public key missing.")
        return 1

    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[HARD-STOP] Manifest JSON unreadable: {exc}")
        return 1

    if manifest.get("schema_version") != "2.1.0":
        print(f"[HARD-STOP] Unexpected schema_version={manifest.get('schema_version')!r}")
        return 1

    source = manifest.get("build_definition", {}).get("source", {})
    print(
        "Signed source: "
        f"commit={source.get('commit')} "
        f"branch={source.get('branch')} "
        f"dirty={source.get('dirty_working_tree')}"
    )
    print(f"Signed at    : {manifest.get('build_definition', {}).get('timestamp_utc')}")
    print()

    sig_bytes = None
    for line in SIDECAR.read_text(encoding="utf-8").splitlines():
        if line.startswith("SIGNATURE_B64="):
            sig_bytes = base64.b64decode(line.split("=", 1)[1].strip())
            break
    if not sig_bytes or len(sig_bytes) != 64:
        print("[HARD-STOP] Sidecar has no 64-byte Ed25519 SIGNATURE_B64.")
        return 1

    if not openssl_verify(MANIFEST, sig_bytes, BOOTSTRAP_KEY):
        print("[HARD-STOP] openssl pkeyutl rejected the signature. Do not install.")
        return 1
    print("[+] Independent openssl signature: VALID")
    print()

    artifacts = manifest.get("artifacts", {})
    if not isinstance(artifacts, dict) or not artifacts:
        print("[HARD-STOP] Manifest declares zero artifacts.")
        return 1

    mismatches = 0
    print(f"{'status':<10} {'assurance':<8} {'path'}")
    for rel, entry in artifacts.items():
        if not isinstance(entry, dict) or not isinstance(entry.get("sha256"), str):
            print(f"{'BAD-ENTRY':<10} {'?':<8} {rel}")
            mismatches += 1
            continue
        target = WORKSPACE / rel
        expected = entry["sha256"]
        if not target.is_file():
            print(f"{'MISSING':<10} {str(entry.get('assurance_level', '?')):<8} {rel}")
            mismatches += 1
            continue
        actual = sha256_file(target)
        size_ok = target.stat().st_size == entry.get("size_bytes")
        if actual == expected and size_ok:
            print(f"{'MATCH':<10} {str(entry.get('assurance_level', '?')):<8} {rel}")
        else:
            print(f"{'MISMATCH':<10} {str(entry.get('assurance_level', '?')):<8} {rel}")
            print(f"           expected {expected}")
            print(f"           actual   {actual}")
            mismatches += 1

    print()
    print("Not in the signed artifact set (inspect by eye; do not call them QF-A5):")
    for rel in UNSIGNED_UNITS:
        path = WORKSPACE / rel
        state = "present" if path.is_file() else "MISSING"
        print(f"  [{state}] {rel}")
    print("  [absent] container image digest (QF-R3 OPEN)")
    print("  [absent] runner.py / Quadlet runtime (not a signed artifact)")
    print()

    if mismatches:
        print(
            f"[HARD-STOP] {mismatches}/{len(artifacts)} artifacts failed. "
            "Signature-valid + hash mismatch is DENY. Do not lock a trust "
            "anchor from this tree. Restore signed bytes or mint a new "
            "signed release with the offline key."
        )
        return 2

    print(
        f"[+] {len(artifacts)}/{len(artifacts)} artifacts byte-accurate. "
        "This tree is a known-good dry-run target. You may install the host judge."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
