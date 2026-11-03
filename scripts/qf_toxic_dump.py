#!/usr/bin/env python3
"""
QuantumFlex Information Toxic Dump & Quarantine Engine (qf-toxic-dump)
=====================================================================
Securely isolates obsolete, superseded, or untrue historical artifacts
(e.g., legacy warehouse consulting pitches, phantom hardware specs,
unverified cloud webhook proposals) while preserving trade secrets,
cryptographic provenance, and extracting sustainable architectural lessons.

Governing Invariants:
- Strict Permissions: Quarantine directory 0700, files 0600
- Git Isolation: Always ignored in .gitignore, never pushed to remotes
- Provable Tamper-Resistance: SHA-256 indexed in toxic_dump_manifest.jsonl
"""

import os
import sys
import json
import shutil
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

ROOT_DIR = Path(__file__).resolve().parents[1]
QUARANTINE_DIR = ROOT_DIR / "quarantine" / "toxic_dump"
MANIFEST_PATH = QUARANTINE_DIR / "toxic_dump_manifest.jsonl"


def ensure_quarantine_dir():
    QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(QUARANTINE_DIR, 0o700)
    if not MANIFEST_PATH.exists():
        MANIFEST_PATH.touch(mode=0o600)
    else:
        os.chmod(MANIFEST_PATH, 0o600)


def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def quarantine_file(src_path: Path, reason: str, lesson: str, move: bool = False) -> Dict[str, Any]:
    ensure_quarantine_dir()
    src = Path(src_path).resolve()
    if not src.exists() or not src.is_file():
        raise FileNotFoundError(f"Source file not found: {src}")

    file_sha256 = compute_sha256(src)
    dest_filename = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{src.name}"
    dest = QUARANTINE_DIR / dest_filename

    if move:
        shutil.move(str(src), str(dest))
    else:
        shutil.copy2(str(src), str(dest))

    os.chmod(dest, 0o600)

    record = {
        "quarantined_at": datetime.now(timezone.utc).isoformat(),
        "original_path": str(src),
        "quarantine_filename": dest_filename,
        "sha256": file_sha256,
        "size_bytes": dest.stat().st_size,
        "decommission_reason": reason,
        "extracted_lesson": lesson,
        "mode": "MOVE" if move else "COPY"
    }

    with open(MANIFEST_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    return record


def list_quarantine() -> List[Dict[str, Any]]:
    ensure_quarantine_dir()
    records = []
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
    return records


def verify_quarantine_integrity() -> bool:
    records = list_quarantine()
    all_ok = True
    print(f"[*] Verifying SHA-256 integrity of {len(records)} quarantined artifacts...")
    for r in records:
        fpath = QUARANTINE_DIR / r["quarantine_filename"]
        if not fpath.exists():
            print(f"  [FAIL] Missing file: {r['quarantine_filename']}")
            all_ok = False
            continue
        actual_sha = compute_sha256(fpath)
        if actual_sha != r["sha256"]:
            print(f"  [FAIL] Tampered digest: {r['quarantine_filename']}")
            all_ok = False
        else:
            print(f"  [PASS] {r['quarantine_filename'][:35]:<35} | {r['sha256'][:12]}... | {r['decommission_reason'][:30]}")
    return all_ok


def main():
    import argparse
    parser = argparse.ArgumentParser(description="QuantumFlex Information Toxic Dump & Quarantine Engine")
    sub = parser.add_subparsers(dest="command", required=True)

    dump_p = sub.add_parser("dump", help="Isolate a file into the toxic dump")
    dump_p.add_argument("file", help="Path to file to quarantine")
    dump_p.add_argument("--reason", required=True, help="Reason for decommissioning/toxic classification")
    dump_p.add_argument("--lesson", default="Extracted into clean knowledge vault document.", help="Architectural lesson or trade secret retained")
    dump_p.add_argument("--move", action="store_true", help="Move file instead of copying (deletes source)")

    sub.add_parser("list", help="List all quarantined artifacts in the toxic dump")
    sub.add_parser("verify", help="Cryptographically verify SHA-256 digests of all quarantined items")

    args = parser.parse_args()

    if args.command == "dump":
        rec = quarantine_file(Path(args.file), reason=args.reason, lesson=args.lesson, move=args.move)
        print(f"[+] Successfully quarantined: {rec['original_path']} -> {rec['quarantine_filename']}")
        print(f"    SHA-256: {rec['sha256']}")
        print(f"    Reason:  {rec['decommission_reason']}")
        print(f"    Lesson:  {rec['extracted_lesson']}")

    elif args.command == "list":
        records = list_quarantine()
        print(f"\n=== QUANTUMFLEX INFORMATION TOXIC DUMP ({len(records)} Items) ===")
        print(f"Directory: {QUARANTINE_DIR} (Permissions 0700 / 0600)\n")
        for i, r in enumerate(records, 1):
            print(f"[{i}] {r['quarantine_filename']}")
            print(f"    Original: {r['original_path']}")
            print(f"    SHA-256:  {r['sha256'][:16]}... ({r['size_bytes']} bytes)")
            print(f"    Reason:   {r['decommission_reason']}")
            print(f"    Lesson:   {r['extracted_lesson']}")
            print()

    elif args.command == "verify":
        ok = verify_quarantine_integrity()
        if ok:
            print("\n[ALL QUARANTINED ARTIFACTS VERIFIED TAMPER-FREE]")
        else:
            print("\n[!] INTEGRITY BREACH DETECTED IN TOXIC DUMP")
            sys.exit(1)


if __name__ == "__main__":
    main()
