#!/usr/bin/env python3
"""Exercise QuantumFlex Runtime Admission with Customer-Held Signing Identity.

Demonstrates that QuantumFlex admission gates support customer-controlled keys:
  1. Default key pin rejects customer-signed manifest (fail-closed).
  2. Customer key pin (via QF_SIGNING_KEY_ID & QF_SIGNING_PLANE) cleanly admits authentic release.
  3. Customer-signed release with tampered executable fails closed.
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


def compile_test_bin(dir_path: Path, name: str = "customer_service") -> Path:
    src = dir_path / f"{name}.c"
    src.write_text(r"""
#include <stdio.h>
int main(int argc, char** argv) {
    printf("CUSTOMER_SERVICE_RUNNING_OK\n");
    return 0;
}
""")
    exe = dir_path / name
    subprocess.run(["gcc", "-O2", str(src), "-o", str(exe)], check=True)
    return exe


def sign_a5_manifest(manifest: Path, key: Path, key_id: str, plane: str):
    raw_signature = manifest.with_suffix(".rawsig")
    subprocess.run([
        "openssl", "pkeyutl", "-sign", "-rawin", "-inkey", str(key),
        "-in", str(manifest), "-out", str(raw_signature)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    sig_b64 = base64.b64encode(raw_signature.read_bytes()).decode("ascii")
    manifest.with_suffix(".sig").write_text(
        "SIGNATURE_ALGORITHM=Ed25519\n"
        f"KEY_ID={key_id}\n"
        f"PLANE={plane}\n"
        f"SIGNATURE_B64={sig_b64}\n"
    )
    raw_signature.unlink()


def main() -> int:
    customer_key_id = "customer-acme-a5-v1"
    customer_plane = "customer-release-a5"

    with tempfile.TemporaryDirectory(prefix="qf-cust-test-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        authority_dir = tmp_path / "authority"
        authority_dir.mkdir(parents=True)

        # Generate customer-controlled keypair
        customer_priv = authority_dir / "customer_key.pem"
        customer_pub = authority_dir / "release_signing_key.pub"
        subprocess.run(["openssl", "genpkey", "-algorithm", "Ed25519", "-out", str(customer_priv)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["openssl", "pkey", "-in", str(customer_priv), "-pubout", "-out", str(customer_pub)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.chmod(customer_pub, stat.S_IRUSR)

        # Install verifier and launcher into authority dir
        test_verifier = authority_dir / "verify-provenance"
        shutil.copy2(WORKSPACE / "host-trust" / "verify-provenance", test_verifier)
        os.chmod(test_verifier, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)

        src_launcher = WORKSPACE / "scripts" / "qf_runtime_admit.py"
        launcher_code = src_launcher.read_text(encoding="utf-8")
        test_launcher = authority_dir / "qf-runtime-admit"
        install_verifier(launcher_code, str(test_launcher), str(authority_dir))

        # Build customer release payload
        release_root = tmp_path / "customer_release"
        release_dir = release_root / "release"
        release_dir.mkdir(parents=True)
        artifact = release_root / "firmware.bin"
        artifact.write_bytes(b"customer-proprietary-firmware-payload\n")

        manifest_path = release_dir / "PROVENANCE_MANIFEST.json"
        manifest_path.write_text(json.dumps({
            "schema_version": "2.2.0",
            "signing": {
                "key_id": customer_key_id,
                "plane": customer_plane,
            },
            "artifacts": {
                artifact.name: {
                    "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                    "size_bytes": artifact.stat().st_size,
                }
            },
        }, indent=2, sort_keys=True) + "\n")
        sign_a5_manifest(manifest_path, customer_priv, customer_key_id, customer_plane)

        # Build customer executable and runtime binding
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir(parents=True)
        exe = compile_test_bin(bin_dir, "customer_service")
        binding_path = bin_dir / "QuantumFlexRuntimeBinding.json"
        create_runtime_binding(str(exe), str(manifest_path), str(binding_path))
        sign_runtime_binding(str(binding_path), str(customer_priv), str(bin_dir / "QuantumFlexRuntimeBinding.sig"))

        launcher_args = [
            str(test_launcher),
            "--executable", str(exe),
            "--a5-manifest", str(manifest_path),
            "--repo-root", str(release_root),
            "--trust-anchor", str(customer_pub),
            "--verifier", str(test_verifier),
        ]

        # Case 1: Default environment without QF_SIGNING_KEY_ID configured -> REJECTED (fail-closed)
        env_default = dict(os.environ)
        env_default.pop("QF_SIGNING_KEY_ID", None)
        env_default.pop("QF_SIGNING_PLANE", None)
        res1 = subprocess.run(launcher_args, env=env_default, capture_output=True, text=True)
        if res1.returncode == 0:
            raise SystemExit("[FAIL] Customer key admitted under default mycelium key pin")
        print("[PASS] Default pin rejects customer-held key identity (fail-closed)")

        # Case 2: Configured customer key environment -> ADMITTED
        env_customer = dict(os.environ)
        env_customer["QF_SIGNING_KEY_ID"] = customer_key_id
        env_customer["QF_SIGNING_PLANE"] = customer_plane
        res2 = subprocess.run(launcher_args, env=env_customer, capture_output=True, text=True)
        if res2.returncode != 0 or "CUSTOMER_SERVICE_RUNNING_OK" not in res2.stdout:
            raise SystemExit(f"[FAIL] Customer key not admitted with matching environment:\nSTDOUT:\n{res2.stdout}\nSTDERR:\n{res2.stderr}")
        print("[PASS] Configured customer key identity admitted and executed cleanly")

        # Case 3: Customer-signed release with tampered executable -> REJECTED
        d = bytearray(exe.read_bytes())
        d[-1] ^= 0x55
        exe.write_bytes(d)
        res3 = subprocess.run(launcher_args, env=env_customer, capture_output=True, text=True)
        if res3.returncode == 0:
            raise SystemExit("[FAIL] Tampered customer executable admitted")
        print("[PASS] Tampered executable rejected under customer-held key identity")

    print("[ALL PASS] Customer signing identity verification successful")
    return 0


if __name__ == "__main__":
    sys.exit(main())
