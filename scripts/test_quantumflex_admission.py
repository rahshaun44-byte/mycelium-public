#!/usr/bin/env python3
"""Exercise QuantumFlex admission: missing prefix, verifying install, tamper.

Mycelium governs. A prefix that cannot present a matching hash receipt must
not configure. In-tree add_subdirectory is DEV only.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
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
        raise SystemExit(f"[FAIL] {label}: configure succeeded, expected FAIL-CLOSED\n{proc.stdout}\n{proc.stderr}")
    blob = proc.stdout + proc.stderr
    if needle not in blob:
        raise SystemExit(f"[FAIL] {label}: missing {needle!r} in cmake output\n{blob}")
    print(f"[PASS] {label}")


def expect_ok(label: str, proc: subprocess.CompletedProcess[str], needle: str) -> None:
    if proc.returncode != 0:
        raise SystemExit(f"[FAIL] {label}: configure failed\n{proc.stdout}\n{proc.stderr}")
    blob = proc.stdout + proc.stderr
    if needle not in blob:
        raise SystemExit(f"[FAIL] {label}: missing {needle!r} in cmake output\n{blob}")
    print(f"[PASS] {label}")


def main() -> int:
    print("QuantumFlex admission gate")

    with tempfile.TemporaryDirectory(prefix="qf-admit-") as tmp:
        tmp_path = Path(tmp)
        prefix = tmp_path / "prefix"
        qf_build = tmp_path / "qf-build"
        myc_dev = tmp_path / "myc-dev"
        myc_attested = tmp_path / "myc-attested"
        myc_missing = tmp_path / "myc-missing"
        myc_tamper = tmp_path / "myc-tamper"

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

        # 3. Standalone install emits a receipt; ATTESTED admits it.
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
            # Debian/Ubuntu is lib; some prefixes use lib64
            receipt = prefix / "lib64" / "cmake" / "QuantumFlex" / "QuantumFlexAdmission.json"
        if not receipt.is_file():
            raise SystemExit(f"[FAIL] admission receipt missing under {prefix}")
        print(f"[PASS] install receipt at {receipt}")

        proc = cmake_configure(
            myc_attested,
            [
                "-DQUANTUMFLEX_REQUIRE_ATTESTED=ON",
                f"-DCMAKE_PREFIX_PATH={prefix}",
            ],
        )
        expect_ok("ATTESTED, verifying prefix", proc, "QuantumFlex admission: ATTESTED")

        # 4. Tamper a lib; ATTESTED fail-closes on sha256 mismatch.
        tamper_prefix = tmp_path / "tamper-prefix"
        shutil.copytree(prefix, tamper_prefix)
        lib = tamper_prefix / "lib" / "libquantumflex_crypto.a"
        if not lib.is_file():
            lib = tamper_prefix / "lib64" / "libquantumflex_crypto.a"
        data = bytearray(lib.read_bytes())
        data[0] ^= 0xFF
        lib.write_bytes(data)

        proc = cmake_configure(
            myc_tamper,
            [
                "-DQUANTUMFLEX_REQUIRE_ATTESTED=ON",
                f"-DCMAKE_PREFIX_PATH={tamper_prefix}",
            ],
        )
        expect_fail("ATTESTED, tampered lib", proc, "mismatch")

    print("[ALL PASS] QuantumFlex admission: DEV / ATTESTED / tamper")
    return 0


if __name__ == "__main__":
    sys.exit(main())
