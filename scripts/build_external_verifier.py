#!/usr/bin/env python3
"""
QuantumFlex External Provenance Verifier Build & Installation Pipeline

Implements safe, assertion-driven transformation of scripts/verify_provenance_manifest.py
into an external, trust-anchored verifier binary at:
  ~/.local/libexec/quantumflex/verify-provenance

Security Invariant & Trust Separation:
  - Source Object (untrusted/replaceable): /home/quant/mycelium (or target repo)
  - Manifest & Signature (untrusted): <target>/release/PROVENANCE_MANIFEST.{json,sig}
  - Trust Anchor (trusted): ~/.local/libexec/quantumflex/release_signing_key.pub
  
Invariant:
  "The repository supplies the object being verified.
   It does not supply the key that determines whether that object is trusted."

Boundary Notice:
  Isolating the verifier and trust anchor in ~/.local/libexec/ eliminates
  repository-controlled trust-anchor substitution. It is not an OS sandbox
  against arbitrary same-user (UID 1000) compromise.
"""

import argparse
import ast
import difflib
import os
import stat
import sys
import tempfile

DEFAULT_REPO_ROOT = "/home/quant/mycelium"
SOURCE_SCRIPT_REL = "scripts/verify_provenance_manifest.py"
TARGET_DIR = os.path.expanduser("~/.local/libexec/quantumflex")
TARGET_BINARY = os.path.join(TARGET_DIR, "verify-provenance")
TRUST_ANCHOR_PUBKEY = os.path.join(TARGET_DIR, "release_signing_key.pub")

OLD_PATTERN = (
    'WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\n'
    'RELEASE_DIR = os.path.join(WORKSPACE, "release")\n'
    'MANIFEST_PATH = os.path.join(RELEASE_DIR, "PROVENANCE_MANIFEST.json")\n'
    'SIG_PATH = os.path.join(RELEASE_DIR, "PROVENANCE_MANIFEST.sig")\n'
    'PUB_KEY_PATH = os.path.join(RELEASE_DIR, "release_signing_key.pub")'
)

NEW_PATTERN = (
    '# --- QuantumFlex External Trust Anchor Boundary ---\n'
    '# Untrusted target repository resolution (supplied by caller or runtime)\n'
    'if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):\n'
    '    WORKSPACE = os.path.abspath(sys.argv[1])\n'
    'elif os.environ.get("QF_WORKSPACE"):\n'
    '    WORKSPACE = os.path.abspath(os.environ["QF_WORKSPACE"])\n'
    'elif os.path.exists(os.path.join(os.getcwd(), "release", "PROVENANCE_MANIFEST.json")):\n'
    '    WORKSPACE = os.path.abspath(os.getcwd())\n'
    'else:\n'
    '    WORKSPACE = "/home/quant/mycelium"\n'
    '\n'
    'RELEASE_DIR = os.path.join(WORKSPACE, "release")\n'
    'MANIFEST_PATH = os.path.join(RELEASE_DIR, "PROVENANCE_MANIFEST.json")\n'
    'SIG_PATH = os.path.join(RELEASE_DIR, "PROVENANCE_MANIFEST.sig")\n'
    '\n'
    '# Trust anchor: strictly pinned external to untrusted repository\n'
    'TRUST_ANCHOR_DIR = os.path.dirname(os.path.abspath(__file__))\n'
    'PUB_KEY_PATH = os.path.join(TRUST_ANCHOR_DIR, "release_signing_key.pub")\n'
    '# ---------------------------------------------------'
)


def transform_verifier(source_path: str) -> str:
    """Read source, assert preconditions, apply transformation, assert postconditions, and compile AST."""
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"[HALT] Source verifier does not exist: {source_path}")

    with open(source_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Pre-condition Assertion 1: Old pattern must be present exactly once
    occurrences = content.count(OLD_PATTERN)
    if occurrences == 0:
        raise ValueError("[HALT] Expected old path pattern NOT FOUND in source verifier. Aborting with zero mutations.")
    if occurrences > 1:
        raise ValueError(f"[HALT] Expected old path pattern found {occurrences} times (expected 1). Aborting.")

    # Transformation
    transformed = content.replace(OLD_PATTERN, NEW_PATTERN, 1)

    # Post-condition Assertions: New trust boundary must be strictly established
    if OLD_PATTERN in transformed:
        raise AssertionError("[HALT] Old path pattern still present after replacement.")
    if NEW_PATTERN not in transformed:
        raise AssertionError("[HALT] New trust boundary block missing in transformed code.")
    if 'PUB_KEY_PATH = os.path.join(RELEASE_DIR, "release_signing_key.pub")' in transformed:
        raise AssertionError("[HALT] Verifier still binds trust anchor to repository RELEASE_DIR.")
    if 'PUB_KEY_PATH = os.path.join(TRUST_ANCHOR_DIR, "release_signing_key.pub")' not in transformed:
        raise AssertionError("[HALT] Verifier does not bind trust anchor to external TRUST_ANCHOR_DIR.")

    # Syntax and AST Compilation Validation
    try:
        ast.parse(transformed)
    except SyntaxError as e:
        raise SyntaxError(f"[HALT] Transformed verifier failed AST parsing: {e}") from e

    try:
        compile(transformed, "<external-verifier>", "exec")
    except Exception as e:
        raise RuntimeError(f"[HALT] Transformed verifier failed compilation: {e}") from e

    return transformed


def install_verifier(transformed_code: str, target_bin: str, target_dir: str):
    """Atomically install the transformed verifier into target_bin with mode 0755."""
    if not os.path.isdir(target_dir):
        os.makedirs(target_dir, mode=0o700, exist_ok=True)

    target_anchor = os.path.join(target_dir, "release_signing_key.pub")
    # Assert trust anchor exists in target dir
    if not os.path.isfile(target_anchor):
        raise FileNotFoundError(f"[HALT] Trust anchor public key missing at {target_anchor}")

    # Stage atomic write in same filesystem directory
    tmp_fd, tmp_path = tempfile.mkstemp(prefix=".verify-provenance.tmp.", dir=target_dir)
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            f.write(transformed_code)

        # Set permissions: executable (rwxr-xr-x / 0755)
        os.chmod(tmp_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)

        # Atomic replacement
        os.replace(tmp_path, target_bin)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise

    print(f"[+] Atomic installation successful: {target_bin}")
    print(f"[+] Permissions: {oct(stat.S_IMODE(os.stat(target_bin).st_mode))}")
    print(f"[+] Verified Trust Anchor: {target_anchor}")


def main():
    parser = argparse.ArgumentParser(description="QuantumFlex Verifier Build & Install Transformation")
    parser.add_argument("--source", default=os.path.join(DEFAULT_REPO_ROOT, SOURCE_SCRIPT_REL),
                        help="Path to repository source verifier")
    parser.add_argument("--dry-run", action="store_true",
                        help="Perform assertions and AST validation without writing to disk")
    parser.add_argument("--install", action="store_true",
                        help="Atomically install to ~/.local/libexec/quantumflex/verify-provenance")
    args = parser.parse_args()

    print("[*] Stage 1: Reading source verifier and evaluating pre-condition assertions...")
    print(f"    Source: {args.source}")
    try:
        transformed = transform_verifier(args.source)
        print("[+] Stage 1 PASSED: Source pattern matched and validated.")
        print("[+] Stage 2 PASSED: New trust boundary successfully established.")
        print("[+] Stage 3 PASSED: Python AST and bytecode compilation verified clean.")
    except Exception as e:
        print(f"[-] FAILED: {e}", file=sys.stderr)
        return 1

    if args.dry_run:
        print("[*] DRY RUN: Printing unified diff of proposed transformation:")
        with open(args.source, "r", encoding="utf-8") as f:
            src_lines = f.readlines()
        dst_lines = transformed.splitlines(keepends=True)
        diff = difflib.unified_diff(src_lines, dst_lines, fromfile="source_verifier", tofile="external_verifier")
        sys.stdout.writelines(diff)
        print("[*] Dry run complete. Zero disk mutations made.")
        return 0

    if args.install:
        print("[*] Stage 4: Executing atomic install into target directory...")
        try:
            install_verifier(transformed, TARGET_BINARY, TARGET_DIR)
        except Exception as e:
            print(f"[-] Installation FAILED: {e}", file=sys.stderr)
            return 1
        return 0

    print("[!] No action specified. Use --dry-run or --install.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
