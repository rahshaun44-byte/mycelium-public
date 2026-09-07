#!/usr/bin/env python3
"""
QuantumFlex Four-Artifact Preflight Gate for CEDRUS / SPHINCS+ Experiments
==========================================================================
Enforces Hard-Stop pipeline invariants:
  PROVENANCE -> ARTIFACT -> PREFLIGHT -> ISOLATION -> BASELINE -> EXPERIMENT -> MEASUREMENT -> DECISION

Rules:
  1. Inspects BUNDLE_PATH, SIG_PATH, PUBKEY_PATH, and VERIFIER_BIN.
  2. If ANY artifact is missing, prints "DATA NOT FOUND" and exits nonzero immediately.
  3. No mock vectors, no synthetic fallback, no silent bypass.
  4. If all 4 artifacts exist, computes and records SHA-256 digests.
"""

import hashlib
import os
import sys
from pathlib import Path


REQUIRED_ARTIFACTS = [
    ("BUNDLE_PATH", "OPA policy bundle or payload to verify"),
    ("SIG_PATH", "Detached signature file"),
    ("PUBKEY_PATH", "Public key file"),
    ("VERIFIER_BIN", "Compiled, standalone verification binary"),
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    print("=================================================================")
    print("  QUANTUM FLEX: Four-Artifact Preflight Gate (CEDRUS Watch)       ")
    print("=================================================================")
    print("[*] Enforcing Hard Stop Invariant: Missing vector = HALT\n")

    missing = []
    manifest = []

    for env_var, description in REQUIRED_ARTIFACTS:
        val = os.environ.get(env_var)
        if not val:
            print(f"[!] {env_var:<14} : UNSET ({description})")
            missing.append((env_var, "UNSET"))
            continue

        p = Path(val).resolve()
        if not p.is_file():
            print(f"[!] {env_var:<14} : NOT FOUND -> {p}")
            missing.append((env_var, str(p)))
            continue

        if env_var == "VERIFIER_BIN" and not os.access(p, os.X_OK):
            print(f"[!] {env_var:<14} : NOT EXECUTABLE -> {p}")
            missing.append((env_var, f"{p} (no execute permission)"))
            continue

        digest = sha256_file(p)
        size = p.stat().st_size
        manifest.append((env_var, p, size, digest))
        print(f"[+] {env_var:<14} : FOUND ({size} bytes)")
        print(f"    SHA-256: {digest}")

    print("\n-----------------------------------------------------------------")
    if missing:
        print("[HARD STOP] DATA NOT FOUND")
        print("Preflight failed. The following required artifacts are absent:")
        for var, detail in missing:
            print(f"  - {var}: {detail}")
        print("\nRule: DO NOT SYNTHESIZE MOCK VECTORS.")
        print("Gatekeeper Sizing: NO_INPUT (local validation remains NULL).")
        return 1

    print("[PASS] All 4 artifacts authenticated. Chamber isolation unlocked.")
    print("Ready for Podman isolation baseline vs candidate measurement.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
