#!/usr/bin/env python3
"""
QuantumFlex Runtime Admission Launcher (QF-A6)

Enforces atomic runtime admission:
  RUNTIME_ADMITTED =
    A5_PROVENANCE_ADMITTED
    ∧ RUNTIME_BINDING_SIGNATURE_VALID
    ∧ H(actual_A5_manifest) = binding.package.a5_manifest_sha256
    ∧ H(opened_executable) = binding.runtime.sha256
    ∧ EXECUTED_FD = VERIFIED_FD

The launcher verifies the current signed QF-A5 release manifest and its declared
artifacts, checks a signed binding to that manifest, then opens the executable
with O_RDONLY | O_NOFOLLOW | O_CLOEXEC. It hashes the open descriptor and
executes that descriptor via /proc/self/fd/<fd> on Linux. This closes the
executable pathname swap window; it does not attest dynamic libraries or the
rest of the host.
"""

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys

DANGEROUS_ENV_VARS = {
    "LD_PRELOAD",
    "LD_LIBRARY_PATH",
    "LD_AUDIT",
    "LD_DEBUG",
    "LD_PROFILE",
    "LD_ASSUME_KERNEL",
    "GLIBC_TUNABLES",
    "DYLD_LIBRARY_PATH",
    "DYLD_INSERT_LIBRARIES",
}


def sanitize_environment(env: dict[str, str]) -> dict[str, str]:
    """Strip dangerous dynamic linker / loader control variables."""
    return {k: v for k, v in env.items() if k not in DANGEROUS_ENV_VARS}


def verify_and_launch(
    executable_path: str,
    binding_path: str = None,
    sig_path: str = None,
    a5_manifest_path: str = None,
    repo_root: str = None,
    trust_anchor_path: str = None,
    a5_verifier_path: str = None,
    engine_args: list[str] = None
) -> int:
    if engine_args is None:
        engine_args = []

    launcher_dir = os.path.dirname(os.path.abspath(__file__))

    # 1. Pinned Trust Anchor Check
    if trust_anchor_path is None:
        trust_anchor_path = os.path.join(launcher_dir, "release_signing_key.pub")
    if not os.path.isfile(trust_anchor_path):
        print(f"[FAIL-CLOSED] DENY_TRUST_ANCHOR_MISSING: Pinned trust anchor not found at {trust_anchor_path}", file=sys.stderr)
        return 1

    # 2. A5 Verifier Existence Check
    if a5_verifier_path is None:
        a5_verifier_path = os.path.join(launcher_dir, "verify-provenance")
    if not os.path.isfile(a5_verifier_path):
        print(f"[FAIL-CLOSED] DENY_A5_VERIFIER_MISSING: A5 verifier missing at {a5_verifier_path}", file=sys.stderr)
        return 1

    # 3. Current QF-A5 release verification. A digest alone does not prove
    # that the manifest was signed or that its declared artifacts still match.
    if not a5_manifest_path or not os.path.isfile(a5_manifest_path):
        print(f"[FAIL-CLOSED] DENY_A5_MANIFEST_MISSING: A5 provenance manifest not found at {a5_manifest_path}", file=sys.stderr)
        return 1

    verify_cmd = [a5_verifier_path, a5_manifest_path, "--key", trust_anchor_path]
    if repo_root:
        verify_cmd.extend(["--repo-root", repo_root])
    res = subprocess.run(verify_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[FAIL-CLOSED] DENY_A5_PROVENANCE_REJECTED:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}", file=sys.stderr)
        return 1

    # 4. Resolve Runtime Binding & Signature Paths
    exe_dir = os.path.dirname(os.path.abspath(executable_path))
    if not binding_path:
        binding_path = os.path.join(exe_dir, "QuantumFlexRuntimeBinding.json")
    if not sig_path:
        sig_path = os.path.join(exe_dir, "QuantumFlexRuntimeBinding.sig")

    if not os.path.isfile(binding_path):
        print(f"[FAIL-CLOSED] DENY_BINDING_MISSING: Runtime binding file missing at {binding_path}", file=sys.stderr)
        return 1

    if not os.path.isfile(sig_path):
        print(f"[FAIL-CLOSED] DENY_SIGNATURE_MISSING: Runtime signature missing at {sig_path}", file=sys.stderr)
        return 1

    # 5. Verify Ed25519 Signature on Runtime Binding
    res = subprocess.run([
        "openssl", "pkeyutl", "-verify", "-rawin",
        "-pubin", "-inkey", trust_anchor_path,
        "-in", binding_path,
        "-sigfile", sig_path
    ], capture_output=True, text=True)

    if res.returncode != 0:
        print("[FAIL-CLOSED] DENY_SIGNATURE_INVALID: Runtime binding signature invalid against pinned trust anchor", file=sys.stderr)
        return 1

    # 6. Parse and Validate Runtime Binding JSON
    try:
        with open(binding_path, "r", encoding="utf-8") as f:
            binding = json.load(f)
    except Exception as e:
        print(f"[FAIL-CLOSED] DENY_SCHEMA_INVALID: Corrupted JSON in {binding_path}: {e}", file=sys.stderr)
        return 1

    if binding.get("schema") != "quantumflex-runtime-binding-v1":
        print(f"[FAIL-CLOSED] DENY_SCHEMA_INVALID: Unsupported schema {binding.get('schema')}", file=sys.stderr)
        return 1
    if binding.get("purpose") != "quantumflex-runtime-admission":
        print(f"[FAIL-CLOSED] DENY_SCHEMA_INVALID: Invalid purpose {binding.get('purpose')}", file=sys.stderr)
        return 1

    # 7. Assert Binding References Current A5 Manifest Digest
    with open(a5_manifest_path, "rb") as f:
        actual_a5_bytes = f.read()
    actual_a5_sha256 = hashlib.sha256(actual_a5_bytes).hexdigest()
    expected_a5_sha256 = binding.get("package", {}).get("a5_manifest_sha256")

    if actual_a5_sha256 != expected_a5_sha256:
        print(f"[FAIL-CLOSED] DENY_A5_MANIFEST_MISMATCH: Binding expected A5 manifest {expected_a5_sha256}, got {actual_a5_sha256}", file=sys.stderr)
        return 1

    # 8. Open Runtime Executable without following symlinks (O_RDONLY | O_NOFOLLOW | O_CLOEXEC)
    try:
        flags = os.O_RDONLY | os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(executable_path, flags)
    except Exception as e:
        print(f"[FAIL-CLOSED] DENY_OPEN_FAILED: Could not open {executable_path}: {e}", file=sys.stderr)
        return 1

    try:
        # 9. Ensure opened target is a regular file
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            print(f"[FAIL-CLOSED] DENY_NOT_REGULAR_FILE: {executable_path} is not a regular file", file=sys.stderr)
            os.close(fd)
            return 1

        # 10. Hash bytes directly from opened file descriptor
        h_fd = hashlib.sha256()
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            h_fd.update(chunk)
        fd_sha256 = h_fd.hexdigest()
        expected_exe_sha256 = binding.get("runtime", {}).get("sha256")

        if fd_sha256 != expected_exe_sha256:
            print(f"[FAIL-CLOSED] DENY_RUNTIME_HASH_MISMATCH: Opened binary SHA-256 {fd_sha256} != expected {expected_exe_sha256}", file=sys.stderr)
            os.close(fd)
            return 1

        # 11. Sanitize Environment
        clean_env = sanitize_environment(dict(os.environ))

        print("[*] QF-A6: Cryptographic Runtime Binding Signature: VALID")
        print(f"[*] QF-A6: Bound A5 Manifest SHA-256: {actual_a5_sha256[:16]}...")
        print(f"[*] QF-A6: Verified Executable FD SHA-256: {fd_sha256[:16]}...")
        print("[+] VERDICT: RUNTIME_ADMITTED -> EXECUTE (Atomic FD Handoff)")

        # 12. Execute SAME file descriptor via /proc/self/fd/<fd>
        exe_name = os.path.basename(executable_path)
        argv = [exe_name, *engine_args]
        fd_path = f"/proc/self/fd/{fd}"

        # Flush streams before execve replaces process image
        sys.stdout.flush()
        sys.stderr.flush()

        os.execve(fd_path, argv, clean_env)

    except Exception as e:
        print(f"[FAIL-CLOSED] Execution error: {e}", file=sys.stderr)
        try:
            os.close(fd)
        except Exception:
            pass
        return 1

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="QuantumFlex Runtime Admission Launcher (QF-A6)",
        usage="qf-runtime-admit --executable BINARY [options] [-- ARGS...]"
    )
    parser.add_argument("--executable", required=True, help="Path to runtime executable binary")
    parser.add_argument("--binding", help="Path to QuantumFlexRuntimeBinding.json")
    parser.add_argument("--sig", help="Path to QuantumFlexRuntimeBinding.sig")
    parser.add_argument("--a5-manifest", required=True, help="Path to signed PROVENANCE_MANIFEST.json")
    parser.add_argument("--repo-root", help="Root containing artifacts declared by the A5 manifest")
    parser.add_argument("--trust-anchor", help="Override path to release_signing_key.pub")
    parser.add_argument("--verifier", help="Override path to verify-provenance")
    parser.add_argument("engine_args", nargs="*", help="Arguments passed to admitted executable")

    # Split args around '--' if present
    argv = sys.argv[1:]
    engine_extra = []
    if "--" in argv:
        idx = argv.index("--")
        engine_extra = argv[idx + 1:]
        argv = argv[:idx]

    args = parser.parse_args(argv)
    combined_args = (args.engine_args or []) + engine_extra

    return verify_and_launch(
        executable_path=args.executable,
        binding_path=args.binding,
        sig_path=args.sig,
        a5_manifest_path=args.a5_manifest,
        repo_root=args.repo_root,
        trust_anchor_path=args.trust_anchor,
        a5_verifier_path=args.verifier,
        engine_args=combined_args
    )


if __name__ == "__main__":
    sys.exit(main())
