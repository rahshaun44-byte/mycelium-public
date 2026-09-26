#!/usr/bin/env python3
"""Exercise QuantumFlex Runtime Admission Binding (QF-A6) 11-case matrix.

Tests:
  1. Clean signed A5 release + signed runtime -> RUNTIME_ADMITTED
  2. Runtime executable byte changed -> DENY_RUNTIME_HASH_MISMATCH
  3. Runtime changed + binding regenerated unsigned -> DENY_SIGNATURE_MISSING
  4. Runtime changed + binding signed by rogue Ed25519 key -> DENY_SIGNATURE_INVALID
  5. Runtime binding JSON altered after signing -> DENY_SIGNATURE_INVALID
  6. Runtime signature altered -> DENY_SIGNATURE_INVALID
  7. Binding points to different A5 manifest digest -> DENY_A5_MANIFEST_MISMATCH
  8. A5 artifact fails underneath valid A6 binding -> DENY_A5_PROVENANCE_REJECTED
  9. Executable path swapped after verification -> Verified FD executed (TOCTOU defeated)
 10. Environment injection (LD_PRELOAD) -> Sanitized cleanly, executed uninfected
  11. Unsigned A5 manifest with a freshly signed A6 binding -> DENY_A5_PROVENANCE_REJECTED
"""

import base64
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from scripts.create_quantumflex_runtime_binding import create_runtime_binding
from scripts.sign_quantumflex_runtime import sign_runtime_binding
from scripts.build_external_verifier import install_verifier


def expect_ok(label: str, proc: subprocess.CompletedProcess[str], needle: str = None) -> None:
    if proc.returncode != 0:
        raise SystemExit(f"[FAIL] {label}: command failed with exit {proc.returncode}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
    if needle and needle not in (proc.stdout + proc.stderr):
        raise SystemExit(f"[FAIL] {label}: missing expected needle {needle!r}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
    print(f"[PASS] {label}")


def expect_fail(label: str, proc: subprocess.CompletedProcess[str], needle: str) -> None:
    if proc.returncode == 0:
        raise SystemExit(f"[FAIL] {label}: command succeeded, expected fail-closed DENY\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
    combined = proc.stdout + proc.stderr
    if needle not in combined:
        raise SystemExit(f"[FAIL] {label}: missing error needle {needle!r}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
    print(f"[PASS] {label}")


def sign_a5_release(manifest: Path, key: Path):
    raw_signature = manifest.with_suffix(".rawsig")
    subprocess.run([
        "openssl", "pkeyutl", "-sign", "-rawin", "-inkey", str(key),
        "-in", str(manifest), "-out", str(raw_signature)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    signature_b64 = base64.b64encode(raw_signature.read_bytes()).decode("ascii")
    manifest.with_suffix(".sig").write_text(
        "SIGNATURE_ALGORITHM=Ed25519\n"
        "KEY_ID=mycelium-a5-ed25519-v1\n"
        f"SIGNATURE_B64={signature_b64}\n"
    )
    raw_signature.unlink()


def setup_test_environment(tmp_path: Path):
    """Set up an isolated A5 release, pinned judge, and runtime launcher."""
    authority_dir = tmp_path / "authority"
    authority_dir.mkdir(parents=True, exist_ok=True)
    test_key = authority_dir / "test_key.pem"
    test_pub = authority_dir / "release_signing_key.pub"

    subprocess.run(["openssl", "genpkey", "-algorithm", "Ed25519", "-out", str(test_key)],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["openssl", "pkey", "-in", str(test_key), "-pubout", "-out", str(test_pub)],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.chmod(test_pub, stat.S_IRUSR)

    # Install the current repo judge into a separate pinned trust domain.
    test_verifier = authority_dir / "verify-provenance"
    shutil.copy2(WORKSPACE / "host-trust" / "verify-provenance", test_verifier)
    os.chmod(test_verifier, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)

    # Install launcher into authority dir
    src_launcher = WORKSPACE / "scripts" / "qf_runtime_admit.py"
    launcher_code = src_launcher.read_text(encoding="utf-8")
    test_launcher = authority_dir / "qf-runtime-admit"
    install_verifier(launcher_code, str(test_launcher), str(authority_dir))

    release_root = tmp_path / "release_root"
    release_dir = release_root / "release"
    release_dir.mkdir(parents=True)
    sample_artifact = release_root / "sample-artifact.bin"
    sample_artifact.write_bytes(b"known-good release artifact\n")
    a5_manifest = release_dir / "PROVENANCE_MANIFEST.json"
    a5_manifest.write_text(json.dumps({
        "schema_version": "2.2.0",
        "signing": {
            "key_id": "mycelium-a5-ed25519-v1",
            "plane": "host-release-a5",
        },
        "artifacts": {
            sample_artifact.name: {
                "sha256": hashlib.sha256(sample_artifact.read_bytes()).hexdigest(),
                "size_bytes": sample_artifact.stat().st_size,
            }
        },
    }, indent=2, sort_keys=True) + "\n")
    sign_a5_release(a5_manifest, test_key)

    return {
        "authority_dir": authority_dir,
        "test_key": test_key,
        "test_pub": test_pub,
        "test_verifier": test_verifier,
        "test_launcher": test_launcher,
        "release_root": release_root,
        "a5_manifest": a5_manifest,
        "sample_artifact": sample_artifact,
    }


def compile_test_runtime(dir_path: Path, name: str = "quantum_flex_engine") -> Path:
    """Compile a minimal standalone test binary that reports its args and env."""
    src = dir_path / f"{name}.c"
    src.write_text(r"""
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char** argv) {
    const char* lp = getenv("LD_PRELOAD");
    if (lp && *lp) {
        printf("COMPROMISED_INJECTED: %s\n", lp);
        return 42;
    }
    printf("RUNTIME_EXECUTING_CLEAN: %s\n", argv[0]);
    for (int i = 1; i < argc; i++) {
        printf("ARG: %s\n", argv[i]);
    }
    return 0;
}
""")
    bin_path = dir_path / name
    subprocess.run(["gcc", "-O2", str(src), "-o", str(bin_path)], check=True)
    return bin_path


def main() -> int:
    print("QuantumFlex Runtime Admission Gate (QF-A6: 11-Case Matrix)")

    with tempfile.TemporaryDirectory(prefix="qf-a6-") as tmp:
        tmp_path = Path(tmp)
        env = setup_test_environment(tmp_path)

        # Compile authentic runtime binary
        bin_dir = tmp_path / "runtime_bin"
        bin_dir.mkdir()
        authentic_exe = compile_test_runtime(bin_dir, "quantum_flex_engine")

        # Generate and sign authentic runtime binding
        binding_file = bin_dir / "QuantumFlexRuntimeBinding.json"
        create_runtime_binding(
            executable_path=str(authentic_exe),
            a5_manifest_path=str(env["a5_manifest"]),
            output_path=str(binding_file),
            mycelium_dir=str(WORKSPACE),
            quantumflex_dir=str(WORKSPACE / "quantumflex")
        )
        sig_file = bin_dir / "QuantumFlexRuntimeBinding.sig"
        sign_runtime_binding(str(binding_file), str(env["test_key"]), str(sig_file))

        launcher = str(env["test_launcher"])
        provenance_args = [
            "--a5-manifest", str(env["a5_manifest"]),
            "--repo-root", str(env["release_root"]),
        ]

        # ── Case 1: Clean signed A5 release + signed runtime ──
        cmd1 = [
            launcher,
            "--executable", str(authentic_exe),
            *provenance_args,
            "--", "status", "--check"
        ]
        res1 = subprocess.run(cmd1, capture_output=True, text=True)
        expect_ok("Case 1: Clean signed A5 release + signed runtime", res1, "RUNTIME_EXECUTING_CLEAN")

        # ── Case 2: Runtime executable byte changed -> DENY_RUNTIME_HASH_MISMATCH ──
        c2_dir = tmp_path / "c2"
        shutil.copytree(bin_dir, c2_dir)
        c2_exe = c2_dir / "quantum_flex_engine"
        data2 = bytearray(c2_exe.read_bytes())
        data2[-1] ^= 0xFF
        c2_exe.write_bytes(data2)

        cmd2 = [
            launcher,
            "--executable", str(c2_exe),
            *provenance_args,
        ]
        res2 = subprocess.run(cmd2, capture_output=True, text=True)
        expect_fail("Case 2: Runtime executable byte changed", res2, "DENY_RUNTIME_HASH_MISMATCH")

        # ── Case 3: Runtime changed + binding regenerated unsigned -> DENY_SIGNATURE_MISSING ──
        c3_dir = tmp_path / "c3"
        shutil.copytree(bin_dir, c3_dir)
        c3_exe = c3_dir / "quantum_flex_engine"
        data3 = bytearray(c3_exe.read_bytes())
        data3[-1] ^= 0xFF
        c3_exe.write_bytes(data3)

        # Regenerate binding to match new binary, but do not sign
        c3_binding = c3_dir / "QuantumFlexRuntimeBinding.json"
        create_runtime_binding(
            executable_path=str(c3_exe),
            a5_manifest_path=str(env["a5_manifest"]),
            output_path=str(c3_binding)
        )
        (c3_dir / "QuantumFlexRuntimeBinding.sig").unlink()

        cmd3 = [
            launcher,
            "--executable", str(c3_exe),
            *provenance_args,
        ]
        res3 = subprocess.run(cmd3, capture_output=True, text=True)
        expect_fail("Case 3: Runtime changed + binding unsigned", res3, "DENY_SIGNATURE_MISSING")

        # ── Case 4: Runtime changed + binding signed by rogue Ed25519 key -> DENY_SIGNATURE_INVALID ──
        c4_dir = tmp_path / "c4"
        shutil.copytree(bin_dir, c4_dir)
        c4_exe = c4_dir / "quantum_flex_engine"
        data4 = bytearray(c4_exe.read_bytes())
        data4[-1] ^= 0xFF
        c4_exe.write_bytes(data4)

        c4_binding = c4_dir / "QuantumFlexRuntimeBinding.json"
        create_runtime_binding(
            executable_path=str(c4_exe),
            a5_manifest_path=str(env["a5_manifest"]),
            output_path=str(c4_binding)
        )
        rogue_key = tmp_path / "rogue_key.pem"
        subprocess.run(["openssl", "genpkey", "-algorithm", "Ed25519", "-out", str(rogue_key)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        c4_sig = c4_dir / "QuantumFlexRuntimeBinding.sig"
        sign_runtime_binding(str(c4_binding), str(rogue_key), str(c4_sig))

        cmd4 = [
            launcher,
            "--executable", str(c4_exe),
            *provenance_args,
        ]
        res4 = subprocess.run(cmd4, capture_output=True, text=True)
        expect_fail("Case 4: Binding signed by rogue Ed25519 key", res4, "DENY_SIGNATURE_INVALID")

        # ── Case 5: Runtime binding JSON altered after signing -> DENY_SIGNATURE_INVALID ──
        c5_dir = tmp_path / "c5"
        shutil.copytree(bin_dir, c5_dir)
        c5_binding = c5_dir / "QuantumFlexRuntimeBinding.json"
        b5_data = json.loads(c5_binding.read_text())
        b5_data["package"]["version"] = "9.9.9"
        c5_binding.write_text(json.dumps(b5_data, indent=2) + "\n")

        cmd5 = [
            launcher,
            "--executable", str(c5_dir / "quantum_flex_engine"),
            *provenance_args,
        ]
        res5 = subprocess.run(cmd5, capture_output=True, text=True)
        expect_fail("Case 5: Runtime binding JSON altered after signing", res5, "DENY_SIGNATURE_INVALID")

        # ── Case 6: Runtime signature altered -> DENY_SIGNATURE_INVALID ──
        c6_dir = tmp_path / "c6"
        shutil.copytree(bin_dir, c6_dir)
        c6_sig = c6_dir / "QuantumFlexRuntimeBinding.sig"
        sig_bytes = bytearray(c6_sig.read_bytes())
        sig_bytes[0] ^= 0xFF
        c6_sig.write_bytes(sig_bytes)

        cmd6 = [
            launcher,
            "--executable", str(c6_dir / "quantum_flex_engine"),
            *provenance_args,
        ]
        res6 = subprocess.run(cmd6, capture_output=True, text=True)
        expect_fail("Case 6: Runtime signature altered", res6, "DENY_SIGNATURE_INVALID")

        # ── Case 7: Binding points to different A5 manifest digest -> DENY_A5_MANIFEST_MISMATCH ──
        c7_dir = tmp_path / "c7"
        c7_dir.mkdir()
        c7_exe = compile_test_runtime(c7_dir, "quantum_flex_engine")
        c7_binding = c7_dir / "QuantumFlexRuntimeBinding.json"
        create_runtime_binding(
            executable_path=str(c7_exe),
            a5_manifest_path=str(env["a5_manifest"]),
            output_path=str(c7_binding)
        )
        b7_data = json.loads(c7_binding.read_text())
        b7_data["package"]["a5_manifest_sha256"] = "00" * 32
        c7_binding.write_text(json.dumps(b7_data, indent=2) + "\n")
        c7_sig = c7_dir / "QuantumFlexRuntimeBinding.sig"
        sign_runtime_binding(str(c7_binding), str(env["test_key"]), str(c7_sig))

        cmd7 = [
            launcher,
            "--executable", str(c7_exe),
            *provenance_args,
        ]
        res7 = subprocess.run(cmd7, capture_output=True, text=True)
        expect_fail("Case 7: Binding points to different A5 manifest digest", res7, "DENY_A5_MANIFEST_MISMATCH")

        # ── Case 8: A5 artifact fails underneath valid A6 binding ──
        c8_root = tmp_path / "c8_release_root"
        shutil.copytree(env["release_root"], c8_root)
        artifact8 = c8_root / env["sample_artifact"].name
        d8 = bytearray(artifact8.read_bytes())
        d8[0] ^= 0xFF
        artifact8.write_bytes(d8)

        cmd8 = [
            launcher,
            "--executable", str(authentic_exe),
            "--a5-manifest", str(c8_root / "release" / "PROVENANCE_MANIFEST.json"),
            "--repo-root", str(c8_root),
        ]
        res8 = subprocess.run(cmd8, capture_output=True, text=True)
        expect_fail("Case 8: A5 artifact tampered under valid A6 binding", res8, "DENY_A5_PROVENANCE_REJECTED")

        # ── Case 9: Swap path inside the actual launcher immediately before exec ──
        c9_dir = tmp_path / "c9"
        shutil.copytree(bin_dir, c9_dir)
        c9_exe = c9_dir / "quantum_flex_engine"

        toctou_tester = tmp_path / "toctou_test.py"
        toctou_tester.write_text(f"""
import os, sys
sys.path.insert(0, {str(WORKSPACE / 'scripts')!r})
import qf_runtime_admit as qf
original_execve = os.execve
def swap_and_exec(fd_path, argv, clean_env):
    os.unlink({str(c9_exe)!r})
    with open({str(c9_exe)!r}, "w") as attacker:
        attacker.write("#!/bin/sh\\necho ATTACKER_TOCTOU_MALWARE\\nexit 99\\n")
    os.chmod({str(c9_exe)!r}, 0o755)
    return original_execve(fd_path, argv, clean_env)
qf.os.execve = swap_and_exec
sys.exit(qf.verify_and_launch(
    executable_path={str(c9_exe)!r},
    a5_manifest_path={str(env['a5_manifest'])!r},
    repo_root={str(env['release_root'])!r},
    trust_anchor_path={str(env['test_pub'])!r},
    a5_verifier_path={str(env['test_verifier'])!r},
))
""")
        res9 = subprocess.run(["python3", str(toctou_tester)], capture_output=True, text=True)
        expect_ok("Case 9: Launcher executes verified FD after pathname swap", res9, "RUNTIME_EXECUTING_CLEAN")
        if "ATTACKER_TOCTOU_MALWARE" in res9.stdout:
            raise SystemExit("[FAIL] Case 9: replacement pathname executed")

        # ── Case 10: Environment injection (LD_PRELOAD) -> Sanitized cleanly ──
        clean_env = dict(os.environ)
        clean_env["LD_PRELOAD"] = "/tmp/evil_shim.so"
        clean_env["LD_LIBRARY_PATH"] = "/tmp/evil_lib"
        clean_env["GLIBC_TUNABLES"] = "glibc.malloc.check=1"

        res10 = subprocess.run(cmd1, capture_output=True, text=True, env=clean_env)
        expect_ok("Case 10: Dynamic loader injection stripped (LD_PRELOAD sanitized)", res10, "RUNTIME_EXECUTING_CLEAN")
        if "COMPROMISED_INJECTED" in res10.stdout:
            raise SystemExit("[FAIL] Case 10: LD_PRELOAD was not stripped by launcher!")

        # ── Case 11: A6 signature must not substitute for an A5 signature ──
        c11_root = tmp_path / "c11_unsigned_release"
        shutil.copytree(env["release_root"], c11_root)
        unsigned_manifest = c11_root / "release" / "PROVENANCE_MANIFEST.json"
        unsigned_manifest.with_suffix(".sig").unlink()
        c11_dir = tmp_path / "c11_runtime"
        shutil.copytree(bin_dir, c11_dir)
        c11_binding = c11_dir / "QuantumFlexRuntimeBinding.json"
        create_runtime_binding(
            executable_path=str(c11_dir / "quantum_flex_engine"),
            a5_manifest_path=str(unsigned_manifest),
            output_path=str(c11_binding),
        )
        sign_runtime_binding(str(c11_binding), str(env["test_key"]), str(c11_dir / "QuantumFlexRuntimeBinding.sig"))
        res11 = subprocess.run([
            launcher,
            "--executable", str(c11_dir / "quantum_flex_engine"),
            "--a5-manifest", str(unsigned_manifest),
            "--repo-root", str(c11_root),
        ], capture_output=True, text=True)
        expect_fail("Case 11: Unsigned A5 manifest rejected", res11, "DENY_A5_PROVENANCE_REJECTED")

    print("[ALL PASS] QuantumFlex runtime admission: QF-A6 11-case adversarial matrix verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
