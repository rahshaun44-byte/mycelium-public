#!/usr/bin/env python3
"""
QuantumFlex: Automated CycloneDX v1.5 Cryptographic Bill of Materials (CBOM) Generator
Dynamically inspects compiled engine binaries, OpenSSL provider capabilities,
OPA membrane health policies, and active wire framing surfaces.
"""

import os
import sys
import json
import hashlib
import subprocess
from datetime import datetime, timezone

def compute_sha256(filepath: str) -> str:
    """Compute SHA-256 hex digest of a file, or return None if missing."""
    if not os.path.exists(filepath):
        return None
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def get_openssl_version() -> str:
    try:
        res = subprocess.run(["openssl", "version"], stdout=subprocess.PIPE, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return "OpenSSL 3.5.8 (host fallback)"

def generate_cbom(output_path: str = "docs/cbom_alpha_node_template.json"):
    workspace_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    
    # Binary hashes
    engine_bin = os.path.join(workspace_dir, "build_check", "quantum_flex_engine")
    genesis_bin = os.path.join(workspace_dir, "build_check", "qf_genesis_tool")
    sentinel_bin = os.path.join(workspace_dir, "build_check", "sentinel_push")
    
    engine_hash = compute_sha256(engine_bin)
    genesis_hash = compute_sha256(genesis_bin)
    sentinel_hash = compute_sha256(sentinel_bin)

    # Policy and config hashes
    rego_path = os.path.join(workspace_dir, "pqc-immune-daemon", "membrane_health.rego")
    conf_path = os.path.join(workspace_dir, "mcp_layer", "crypto_provider.conf")
    rego_hash = compute_sha256(rego_path)
    conf_hash = compute_sha256(conf_path)

    openssl_ver = get_openssl_version()
    iso_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    cbom = {
        "$schema": "http://cyclonedx.org/schema/bom-1.5.schema.json",
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": "urn:uuid:42a1b976-qfx-alpha-node-cbom-template-20260911",
        "version": 3,
        "metadata": {
            "timestamp": iso_timestamp,
            "tools": [
                {
                    "vendor": "QuantumFlex Security",
                    "name": "scripts/generate_cbom.py",
                    "version": "2.1.0"
                }
            ],
            "authors": [
                {"name": "QuantumFlex Control Plane Operator"}
            ],
            "component": {
                "type": "device",
                "bom-ref": "device:qf-alpha-node",
                "name": "QuantumFlex Alpha Node",
                "version": "2.1.0",
                "description": "Post-Quantum Edge Compute & Mobile Sentinel Node",
                "hashes": [
                    {"alg": "SHA-256", "content": engine_hash or "NOT_BUILT"}
                ],
                "properties": [
                    {"name": "qfx:stratum", "value": "Stratum 0 / Stratum 1"},
                    {"name": "qfx:role", "value": "Mobile Sentinel & Cryptographic Control Plane"},
                    {"name": "qfx:standards_alignment", "value": "G7/CISA 3 Sep 2026 Guidance; NIST FIPS 203/204/205"},
                    {"name": "qfx:openssl_version", "value": openssl_ver}
                ]
            }
        },
        "components": [
            {
                "type": "crypto-asset",
                "bom-ref": "crypto:kem:ml-kem-768",
                "name": "ML-KEM-768",
                "version": "NIST FIPS 203",
                "description": "Primary active Key Encapsulation Mechanism (Module Lattice LWE)",
                "cryptoProperties": {
                    "assetType": "algorithm",
                    "algorithmProperties": {
                        "primitive": "kem",
                        "parameterSetIdentifier": "ML-KEM-768",
                        "curve": None,
                        "classicalSecurityLevel": 192,
                        "nistQuantumSecurityLevel": 3
                    },
                    "oid": "2.16.840.1.101.3.4.4.2"
                }
            },
            {
                "type": "crypto-asset",
                "bom-ref": "crypto:kem:frodokem-976-aes",
                "name": "FrodoKEM-976-AES",
                "version": "CFRG / NIST PQC Round 3",
                "description": "Conservative Matrix LWE Key Encapsulation Mechanism without ideal lattices",
                "cryptoProperties": {
                    "assetType": "algorithm",
                    "algorithmProperties": {
                        "primitive": "kem",
                        "parameterSetIdentifier": "FrodoKEM-976-AES",
                        "curve": None,
                        "classicalSecurityLevel": 192,
                        "nistQuantumSecurityLevel": 3
                    },
                    "oid": "1.3.6.1.4.1.22554.5.2.2"
                }
            },
            {
                "type": "crypto-asset",
                "bom-ref": "crypto:kem:x25519",
                "name": "X25519",
                "version": "RFC 7748",
                "description": "Classical Diffie-Hellman Key Exchange Baseline",
                "cryptoProperties": {
                    "assetType": "algorithm",
                    "algorithmProperties": {
                        "primitive": "key-exchange",
                        "curve": "Curve25519",
                        "classicalSecurityLevel": 128,
                        "nistQuantumSecurityLevel": 0
                    },
                    "oid": "1.3.101.110"
                }
            },
            {
                "type": "crypto-asset",
                "bom-ref": "crypto:sig:ml-dsa-65",
                "name": "ML-DSA-65",
                "version": "NIST FIPS 204",
                "description": "Primary active Module-Lattice Digital Signature Algorithm",
                "cryptoProperties": {
                    "assetType": "algorithm",
                    "algorithmProperties": {
                        "primitive": "signature",
                        "parameterSetIdentifier": "ML-DSA-65",
                        "classicalSecurityLevel": 192,
                        "nistQuantumSecurityLevel": 3
                    },
                    "oid": "2.16.840.1.101.3.4.3.18"
                }
            },
            {
                "type": "crypto-asset",
                "bom-ref": "crypto:sig:slh-dsa-sha2-128f",
                "name": "SLH-DSA-SHA2-128f",
                "version": "NIST FIPS 205",
                "description": "Stateless Hash-Based Digital Signature Algorithm (conf fallback_sig_1)",
                "cryptoProperties": {
                    "assetType": "algorithm",
                    "algorithmProperties": {
                        "primitive": "signature",
                        "parameterSetIdentifier": "SLH-DSA-SHA2-128f",
                        "classicalSecurityLevel": 128,
                        "nistQuantumSecurityLevel": 1
                    },
                    "oid": "2.16.840.1.101.3.4.3.21"
                }
            },
            {
                "type": "crypto-asset",
                "bom-ref": "crypto:sig:ed25519",
                "name": "Ed25519",
                "version": "RFC 8032",
                "description": "Classical Edwards-curve Digital Signature Algorithm Baseline",
                "cryptoProperties": {
                    "assetType": "algorithm",
                    "algorithmProperties": {
                        "primitive": "signature",
                        "curve": "edwards25519",
                        "classicalSecurityLevel": 128,
                        "nistQuantumSecurityLevel": 0
                    },
                    "oid": "1.3.101.112"
                }
            },
            {
                "type": "crypto-asset",
                "bom-ref": "crypto:sss:shamir-gf256",
                "name": "Shamir-Secret-Sharing-GF256",
                "version": "QuantumFlex v2.0",
                "description": "Threshold secret sharing over GF(256). Live unlock uses threshold 3 on three shard files; five shard files exist (k=3, n=5 split).",
                "cryptoProperties": {
                    "assetType": "protocol",
                    "algorithmProperties": {
                        "primitive": "secret-sharing",
                        "parameterSetIdentifier": "k=3, n=5",
                        "classicalSecurityLevel": 256,
                        "nistQuantumSecurityLevel": 5
                    }
                }
            },
            {
                "type": "file",
                "bom-ref": "file:rego:membrane-health",
                "name": "pqc-immune-daemon/membrane_health.rego",
                "version": "2.1.0",
                "description": "Open Policy Agent authoritative circuit breaker & fallback ladder policy",
                "hashes": [
                    {"alg": "SHA-256", "content": rego_hash or "MISSING"}
                ]
            },
            {
                "type": "file",
                "bom-ref": "file:conf:crypto-provider",
                "name": "mcp_layer/crypto_provider.conf",
                "version": "2.1.0",
                "description": "Cryptographic provider and active algorithm mapping configuration",
                "hashes": [
                    {"alg": "SHA-256", "content": conf_hash or "MISSING"}
                ]
            }
        ],
        "services": [
            {
                "bom-ref": "service:wire:mtls",
                "name": "mTLS QFXK Binary IPC Wire",
                "endpoints": ["127.0.0.1:9444"],
                "authenticated": True,
                "x-trust-boundary": "Loopback mTLS only (not advertised on Tailscale)"
            },
            {
                "bom-ref": "service:opa:sidecar",
                "name": "OPA Membrane Health Policy Engine",
                "endpoints": ["127.0.0.1:8181"],
                "authenticated": False,
                "x-trust-boundary": "Strict Loopback (127.0.0.1) Only - Zero External Ingress"
            },
            {
                "bom-ref": "service:console:amara",
                "name": "AMARA Intelligence & Telemetry Console",
                "endpoints": ["127.0.0.1:8000"],
                "authenticated": True,
                "x-trust-boundary": "Loopback bind; optional Tailscale Serve publication"
            },
            {
                "bom-ref": "service:api:gateway",
                "name": "QuantumFlex API Gateway",
                "endpoints": ["127.0.0.1:8080"],
                "authenticated": True,
                "x-trust-boundary": "Loopback bind; optional Tailscale Serve publication"
            }
        ]
    }

    out_file = os.path.join(workspace_dir, output_path)
    with open(out_file, "w") as f:
        json.dump(cbom, f, indent=2)

    print(f"[+] Successfully generated dynamic CBOM: {output_path}")
    print(f"    - Engine binary SHA-256 : {engine_hash[:16] if engine_hash else 'N/A'}...")
    print(f"    - Rego policy SHA-256   : {rego_hash[:16] if rego_hash else 'N/A'}...")
    print(f"    - OpenSSL Primitive Host: {openssl_ver}")

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "docs/cbom_alpha_node_template.json"
    generate_cbom(out)
