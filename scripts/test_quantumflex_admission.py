#!/usr/bin/env python3
"""Exercise QuantumFlex admission: DEV, missing prefix, and 7-case A4/A5 matrix.

Enforces QF-A4 (artifact integrity) and QF-A5 (external provenance authority).
An installed package is ATTESTED if and only if:
  1. All installed artifact hashes match QuantumFlexAdmission.json (A4)
  2. The exact receipt bytes match QuantumFlexAdmission.provenance.json (A5)
  3. The provenance manifest is signed by the pinned external trust anchor (A5)
"""

from __future__ import annotations

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

OPENSSL_ROOT = os.environ.get("OPENSSL_ROOT_DIR", "/opt/openssl-3.5")
PKG_CONFIG = os.environ.get(
    "PKG_CONFIG_PATH",
    "/usr/local/lib/pkgconfig" + (":" + os.environ["PKG_CONFIG_PATH"] if os.environ.get("PKG_CONFIG_PATH") else ""),
)


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["CC"] = "gcc"
    env["CXX"] = "g++"
    env["PKG_CONFIG_PATH"] = PKG_CONFIG
    kwargs.setdefault("env", env)
    kwargs.setdefault("text", True)
    kwargs.setdefault("capture_output", True)
    return subprocess.run(cmd, **kwargs)


def cmake_configure(build: Path, extra: list[str]) -> subprocess.CompletedProcess[str]:
    cmd = [
        "cmake",
        "-S",
        str(WORKSPACE),
        "-B",
        str(build),
        f"-DOPENSSL_ROOT_DIR={OPENSSL_ROOT}",
        *extra,
    ]
    return run(cmd)


def expect_fail(label: str, proc: subprocess.CompletedProcess[str], needle: str) -> None:
    if proc.returncode == 0:
        raise SystemExit(f"[FAIL] {label}: configure succeeded, expected FAIL-CLOSED\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
    blob = proc.stdout + proc.stderr
    if needle not in blob:
        raise SystemExit(f"[FAIL] {label}: missing {needle!r} in cmake output\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
    print(f"[PASS] {label}")


def expect_ok(label: str, proc: subprocess.CompletedProcess[str], needle: str) -> None:
    if proc.returncode != 0:
        raise SystemExit(f"[FAIL] {label}: configure failed\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
    blob = proc.stdout + proc.stderr
    if needle not in blob:
        raise SystemExit(f"[FAIL] {label}: missing {needle!r} in cmake output\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
    print(f"[PASS] {label}")


def setup_test_verifier(authority_dir: Path) -> tuple[Path, Path]:
    """Generate ephemeral test Ed25519 keypair and build a pinned test verifier."""
    authority_dir.mkdir(parents=True, exist_ok=True)
    test_key = authority_dir / "test_release_key.pem"
    test_pub = authority_dir / "release_signing_key.pub"

    subprocess.run(["openssl", "genpkey", "-algorithm", "Ed25519", "-out", str(test_key)],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["openssl", "pkey", "-in", str(test_key), "-pubout", "-out", str(test_pub)],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.chmod(test_pub, stat.S_IRUSR)  # mode 0400

    from scripts.build_external_verifier import transform_verifier, install_verifier
    source_verifier = WORKSPACE / "scripts" / "verify_provenance_manifest.py"
    transformed = transform_verifier(str(source_verifier))
    test_verifier = authority_dir / "verify-provenance"
    install_verifier(transformed, str(test_verifier), str(authority_dir))

    return test_key, test_verifier


def main() -> int:
    print("QuantumFlex admission gate (QF-A4 / QF-A5)")

    with tempfile.TemporaryDirectory(prefix="qf-admit-") as tmp:
        tmp_path = Path(tmp)
        prefix = tmp_path / "prefix"
        qf_build = tmp_path / "qf-build"
        myc_dev = tmp_path / "myc-dev"
        myc_missing = tmp_path / "myc-missing"

        # 0. Set up ephemeral test signing authority and test verifier
        test_authority = tmp_path / "test_authority"
        test_key, test_verifier = setup_test_verifier(test_authority)

        # 1. DEV in-tree (default) still configures.
        proc = cmake_configure(myc_dev, [])
        expect_ok("DEV in-tree", proc, "QuantumFlex admission: DEV")
        dev_receipt = myc_dev / "QuantumFlexAdmission.dev.json"
        if not dev_receipt.is_file():
            raise SystemExit("[FAIL] DEV receipt was not written")
        print("[PASS] DEV receipt written")

        # 2. ATTESTED without a prefix fail-closes.
        proc = cmake_configure(myc_missing, ["-DQUANTUMFLEX_REQUIRE_ATTESTED=ON"])
        expect_fail("ATTESTED, no prefix", proc, "FAIL-CLOSED")

        # 3. Standalone install emits a receipt
        proc = run(
            [
                "cmake",
                "-S",
                str(WORKSPACE / "quantumflex"),
                "-B",
                str(qf_build),
                f"-DOPENSSL_ROOT_DIR={OPENSSL_ROOT}",
                f"-DCMAKE_INSTALL_PREFIX={prefix}",
                "-DQUANTUMFLEX_BUILD_TESTS=OFF",
            ]
        )
        if proc.returncode != 0:
            raise SystemExit(f"[FAIL] standalone configure\n{proc.stdout}\n{proc.stderr}")
        proc = run(["cmake", "--build", str(qf_build), "-j", str(os.cpu_count() or 2)])
        if proc.returncode != 0:
            raise SystemExit(f"[FAIL] standalone build\n{proc.stdout}\n{proc.stderr}")
        proc = run(["cmake", "--install", str(qf_build)])
        if proc.returncode != 0:
            raise SystemExit(f"[FAIL] standalone install\n{proc.stdout}\n{proc.stderr}")

        receipt = prefix / "lib" / "cmake" / "QuantumFlex" / "QuantumFlexAdmission.json"
        if not receipt.is_file():
            receipt = prefix / "lib64" / "cmake" / "QuantumFlex" / "QuantumFlexAdmission.json"
        if not receipt.is_file():
            raise SystemExit(f"[FAIL] admission receipt missing under {prefix}")
        print(f"[PASS] install receipt at {receipt}")

        # 4. Sign the install using ephemeral test authority (QF-A5)
        from scripts.sign_quantumflex_admission import sign_admission_receipt
        sign_admission_receipt(str(receipt), str(test_key))

        attested_flags = [
            "-DQUANTUMFLEX_REQUIRE_ATTESTED=ON",
            f"-DQUANTUMFLEX_PROVENANCE_VERIFIER={test_verifier}",
        ]

        # ── Case 1: Clean signed install -> ATTESTED ──
        proc = cmake_configure(
            tmp_path / "case1-clean",
            [*attested_flags, f"-DCMAKE_PREFIX_PATH={prefix}"],
        )
        expect_ok("Case 1: Clean signed install", proc, "QuantumFlex admission: ATTESTED")

        # ── Case 2: Library byte flipped, old receipt -> FATAL at A4 ──
        p_case2 = tmp_path / "case2-prefix"
        shutil.copytree(prefix, p_case2)
        lib = p_case2 / "lib" / "libquantumflex_crypto.a"
        if not lib.is_file():
            lib = p_case2 / "lib64" / "libquantumflex_crypto.a"
        data = bytearray(lib.read_bytes())
        data[0] ^= 0xFF
        lib.write_bytes(data)

        proc = cmake_configure(
            tmp_path / "case2-build",
            [*attested_flags, f"-DCMAKE_PREFIX_PATH={p_case2}"],
        )
        expect_fail("Case 2: Library byte flipped, old receipt (A4 failure)", proc, "artifact receipt rejected")

        # ── Case 3: Library modified AND receipt regenerated -> FATAL at A5 ──
        p_case3 = tmp_path / "case3-prefix"
        shutil.copytree(prefix, p_case3)
        lib3 = p_case3 / "lib" / "libquantumflex_crypto.a"
        if not lib3.is_file():
            lib3 = p_case3 / "lib64" / "libquantumflex_crypto.a"
        data3 = bytearray(lib3.read_bytes())
        data3[0] ^= 0xFF
        lib3.write_bytes(data3)

        # Regenerate receipt hashes so A4 passes
        rec3 = p_case3 / "lib" / "cmake" / "QuantumFlex" / "QuantumFlexAdmission.json"
        if not rec3.is_file():
            rec3 = p_case3 / "lib64" / "cmake" / "QuantumFlex" / "QuantumFlexAdmission.json"
        rec3_data = json.loads(rec3.read_text())
        new_lib_hash = hashlib.sha256(lib3.read_bytes()).hexdigest()
        for art in rec3_data.get("artifacts", []):
            if "libquantumflex_crypto.a" in art.get("path", ""):
                art["sha256"] = new_lib_hash
        rec3.write_text(json.dumps(rec3_data, indent=2) + "\n")

        proc = cmake_configure(
            tmp_path / "case3-build",
            [*attested_flags, f"-DCMAKE_PREFIX_PATH={p_case3}"],
        )
        expect_fail("Case 3: Library modified and receipt regenerated (A5 failure)", proc, "Receipt SHA-256 mismatch")

        # ── Case 4: Signed A5 manifest altered -> FATAL at A5 ──
        p_case4 = tmp_path / "case4-prefix"
        shutil.copytree(prefix, p_case4)
        m4 = p_case4 / "lib" / "cmake" / "QuantumFlex" / "QuantumFlexAdmission.provenance.json"
        if not m4.is_file():
            m4 = p_case4 / "lib64" / "cmake" / "QuantumFlex" / "QuantumFlexAdmission.provenance.json"
        m4_data = json.loads(m4.read_text())
        m4_data["version"] = "9.9.9"
        m4.write_text(json.dumps(m4_data, indent=2) + "\n")

        proc = cmake_configure(
            tmp_path / "case4-build",
            [*attested_flags, f"-DCMAKE_PREFIX_PATH={p_case4}"],
        )
        expect_fail("Case 4: Signed A5 manifest altered", proc, "Cryptographic signature invalid")

        # ── Case 5: Detached signature altered -> FATAL at A5 ──
        p_case5 = tmp_path / "case5-prefix"
        shutil.copytree(prefix, p_case5)
        s5 = p_case5 / "lib" / "cmake" / "QuantumFlex" / "QuantumFlexAdmission.provenance.sig"
        if not s5.is_file():
            s5 = p_case5 / "lib64" / "cmake" / "QuantumFlex" / "QuantumFlexAdmission.provenance.sig"
        s5_bytes = bytearray(s5.read_bytes())
        s5_bytes[0] ^= 0xFF
        s5.write_bytes(s5_bytes)

        proc = cmake_configure(
            tmp_path / "case5-build",
            [*attested_flags, f"-DCMAKE_PREFIX_PATH={p_case5}"],
        )
        expect_fail("Case 5: Detached signature altered", proc, "Cryptographic signature invalid")

        # ── Case 6: Pinned public trust anchor absent -> FATAL at A5 ──
        no_anchor_authority = tmp_path / "no_anchor_authority"
        shutil.copytree(test_authority, no_anchor_authority)
        (no_anchor_authority / "release_signing_key.pub").unlink()
        no_anchor_verifier = no_anchor_authority / "verify-provenance"

        proc = cmake_configure(
            tmp_path / "case6-build",
            [
                "-DQUANTUMFLEX_REQUIRE_ATTESTED=ON",
                f"-DQUANTUMFLEX_PROVENANCE_VERIFIER={no_anchor_verifier}",
                f"-DCMAKE_PREFIX_PATH={prefix}",
            ],
        )
        expect_fail("Case 6: Pinned public trust anchor absent", proc, "Missing pinned trust anchor")

        # ── Case 7: Manifest signed by rogue valid Ed25519 key -> FATAL at A5 ──
        p_case7 = tmp_path / "case7-prefix"
        shutil.copytree(prefix, p_case7)
        rec7 = p_case7 / "lib" / "cmake" / "QuantumFlex" / "QuantumFlexAdmission.json"
        if not rec7.is_file():
            rec7 = p_case7 / "lib64" / "cmake" / "QuantumFlex" / "QuantumFlexAdmission.json"

        rogue_key = tmp_path / "rogue_key.pem"
        subprocess.run(["openssl", "genpkey", "-algorithm", "Ed25519", "-out", str(rogue_key)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        sign_admission_receipt(str(rec7), str(rogue_key))

        proc = cmake_configure(
            tmp_path / "case7-build",
            [*attested_flags, f"-DCMAKE_PREFIX_PATH={p_case7}"],
        )
        expect_fail("Case 7: Manifest signed by rogue valid Ed25519 key", proc, "Cryptographic signature invalid")

    print("[ALL PASS] QuantumFlex admission: DEV / A4 integrity / A5 provenance 7-case matrix")
    return 0


if __name__ == "__main__":
    sys.exit(main())
