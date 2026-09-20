#!/usr/bin/env python3
"""
QuantumFlex Runtime Admission Binding Generator (QF-A6)

Generates an unsigned QuantumFlexRuntimeBinding.json linking a built runtime executable
to its cryptographically admitted QF-A5 package provenance manifest and commit lineage.

Invariant:
  RUNTIME_ADMITTED =
    A5_PACKAGE_ADMITTED
    ∧ RUNTIME_BINDING_SIGNATURE_VALID
    ∧ H(actual_A5_manifest) = binding.package.a5_manifest_sha256
    ∧ H(opened_executable) = binding.runtime.sha256
    ∧ EXECUTED_FD = VERIFIED_FD
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys


def get_git_commit(cwd: str) -> str:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True
        )
        return res.stdout.strip()
    except Exception:
        return "UNKNOWN"


def create_runtime_binding(
    executable_path: str,
    a5_manifest_path: str,
    output_path: str = None,
    package_name: str = "QuantumFlex",
    package_version: str = "2.1.0",
    mycelium_dir: str = None,
    quantumflex_dir: str = None
) -> str:
    if not os.path.isfile(executable_path):
        raise FileNotFoundError(f"Executable not found: {executable_path}")
    if not os.path.isfile(a5_manifest_path):
        raise FileNotFoundError(f"A5 provenance manifest not found: {a5_manifest_path}")

    # 1. Compute exact SHA-256 of runtime executable binary
    h_exe = hashlib.sha256()
    with open(executable_path, "rb") as f:
        while chunk := f.read(65536):
            h_exe.update(chunk)
    exe_sha256 = h_exe.hexdigest()

    # 2. Compute exact SHA-256 of A5 provenance manifest raw bytes
    with open(a5_manifest_path, "rb") as f:
        a5_manifest_bytes = f.read()
    a5_manifest_sha256 = hashlib.sha256(a5_manifest_bytes).hexdigest()

    # 3. Read package metadata from manifest if present
    try:
        a5_data = json.loads(a5_manifest_bytes.decode("utf-8"))
        package_name = a5_data.get("package", package_name)
        package_version = a5_data.get("version", package_version)
    except Exception:
        pass

    # 4. Resolve commit hashes
    if mycelium_dir is None:
        mycelium_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    mycelium_commit = get_git_commit(mycelium_dir)

    if quantumflex_dir is None:
        quantumflex_dir = os.path.join(mycelium_dir, "quantumflex")
    qf_commit = get_git_commit(quantumflex_dir)

    executable_name = os.path.basename(executable_path)

    # 5. Formulate canonical QF-A6 runtime binding document
    binding_doc = {
        "schema": "quantumflex-runtime-binding-v1",
        "purpose": "quantumflex-runtime-admission",
        "runtime": {
            "name": executable_name,
            "sha256": exe_sha256
        },
        "package": {
            "name": package_name,
            "version": package_version,
            "a5_manifest_sha256": a5_manifest_sha256
        },
        "source": {
            "mycelium_commit": mycelium_commit,
            "quantumflex_commit": qf_commit
        }
    }

    binding_bytes = json.dumps(binding_doc, indent=2, sort_keys=True).encode("utf-8") + b"\n"

    if output_path is None:
        output_path = os.path.join(os.path.dirname(os.path.abspath(executable_path)), "QuantumFlexRuntimeBinding.json")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(binding_bytes)

    return output_path


def main():
    parser = argparse.ArgumentParser(description="Create QuantumFlex Runtime Binding (QF-A6)")
    parser.add_argument("--executable", required=True, help="Path to compiled runtime executable binary")
    parser.add_argument("--a5-manifest", required=True, help="Path to QuantumFlexAdmission.provenance.json")
    parser.add_argument("--output", help="Path to output QuantumFlexRuntimeBinding.json")
    parser.add_argument("--name", default="QuantumFlex", help="Package name")
    parser.add_argument("--version", default="2.1.0", help="Package version")
    parser.add_argument("--mycelium-dir", help="Mycelium repository root")
    parser.add_argument("--quantumflex-dir", help="QuantumFlex repository root")
    args = parser.parse_args()

    try:
        out = create_runtime_binding(
            executable_path=args.executable,
            a5_manifest_path=args.a5_manifest,
            output_path=args.output,
            package_name=args.name,
            package_version=args.version,
            mycelium_dir=args.mycelium_dir,
            quantumflex_dir=args.quantumflex_dir
        )
        print(f"[+] Runtime binding created: {out}")
        return 0
    except Exception as e:
        print(f"[-] Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
