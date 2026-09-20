#!/usr/bin/env python3
"""
QuantumFlex Runtime Binding Signer (QF-A6)

Cryptographically signs an exact QuantumFlexRuntimeBinding.json using an Ed25519 private key,
emitting a detached signature: QuantumFlexRuntimeBinding.sig
"""

import argparse
import os
import subprocess
import sys


def sign_runtime_binding(binding_path: str, private_key_path: str, output_path: str = None) -> str:
    if not os.path.isfile(binding_path):
        raise FileNotFoundError(f"Binding file not found: {binding_path}")
    if not os.path.isfile(private_key_path):
        raise FileNotFoundError(f"Private signing key not found: {private_key_path}")

    if output_path is None:
        output_path = os.path.join(os.path.dirname(os.path.abspath(binding_path)), "QuantumFlexRuntimeBinding.sig")

    res = subprocess.run([
        "openssl", "pkeyutl", "-sign", "-rawin",
        "-inkey", private_key_path,
        "-in", binding_path,
        "-out", output_path
    ], capture_output=True, text=True)

    if res.returncode != 0:
        raise RuntimeError(f"OpenSSL runtime signing failed: {res.stderr.strip()}")

    return output_path


def main():
    parser = argparse.ArgumentParser(description="Sign QuantumFlex Runtime Binding (QF-A6)")
    parser.add_argument("--binding", required=True, help="Path to QuantumFlexRuntimeBinding.json")
    parser.add_argument("--key", required=True, help="Path to Ed25519 private key")
    parser.add_argument("--output", help="Path to output QuantumFlexRuntimeBinding.sig")
    args = parser.parse_args()

    try:
        sig_path = sign_runtime_binding(
            binding_path=args.binding,
            private_key_path=args.key,
            output_path=args.output
        )
        print(f"[+] Detached runtime signature: {sig_path}")
        return 0
    except Exception as e:
        print(f"[-] Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
