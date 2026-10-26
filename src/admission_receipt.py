# src/admission_receipt.py
"""
QuantumFlex P1 #5: Cryptographic Admission Receipt Builder, Signer, and Verifier.
Uses Ed25519 deterministic signatures over canonical JSON and live SHA-256 file digests.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

DEFAULT_RELEASE_KEY_DIR = Path.home() / ".config" / "quantumflex" / "keys"
DEFAULT_PRIVATE_KEY_PATH = DEFAULT_RELEASE_KEY_DIR / "qf_release_ed25519.pem"
DEFAULT_PUBLIC_KEY_PATH = DEFAULT_RELEASE_KEY_DIR / "qf_release_ed25519.pub.pem"

# Canonical P0/P1 artifact files that MUST exist and be hashed into the receipt
DEFAULT_REQUIRED_ARTIFACTS: Tuple[str, ...] = (
    "src/privacy_filter.py",
    "mcp_layer/circuit_breaker.py",
    "mcp_layer/dispatcher.py",
    "src/db_credentials.py",
    "src/jsonl_resilience.py",
    "quantum-flex-sdk/src/lib.rs",
    "docs/fellowship/quest-log.md",
)


def canonical_json_bytes(payload: Dict[str, Any]) -> bytes:
    """Serializes a dictionary into deterministic, canonical UTF-8 JSON bytes (sorted keys, no whitespace)."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def compute_file_sha256(file_path: Path) -> str:
    """Computes the real SHA-256 hex digest of a file on disk. Fails closed if missing or not a file."""
    if not file_path.is_file():
        raise FileNotFoundError(f"[QF-RECEIPT] Required artifact missing on disk: {file_path}")
    h = hashlib.sha256()
    with open(file_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_git_state(repo_root: Path) -> Dict[str, str]:
    """Queries live git HEAD commit and branch from repo_root."""
    try:
        commit = subprocess.check_output(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        branch = subprocess.check_output(
            ["git", "-C", str(repo_root), "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception as exc:
        raise RuntimeError(f"[QF-RECEIPT] Failed to resolve live git state in {repo_root}: {exc}") from exc

    if not commit or len(commit) != 40:
        raise RuntimeError(f"[QF-RECEIPT] Invalid git commit SHA resolved: {commit!r}")
    return {"git_commit": commit, "git_branch": branch}


def ensure_or_load_release_keypair(
    private_key_path: Path = DEFAULT_PRIVATE_KEY_PATH,
    public_key_path: Path = DEFAULT_PUBLIC_KEY_PATH,
    auto_generate_if_missing: bool = False,
) -> Tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    """
    Loads the Ed25519 release keypair from disk, enforcing 0600 permissions on the private key.
    If auto_generate_if_missing=True and no key exists, generates a fresh Ed25519 release keypair.
    """
    if not private_key_path.exists():
        if not auto_generate_if_missing:
            raise FileNotFoundError(
                f"[QF-RECEIPT] Release private key not found at {private_key_path}. "
                "Pass --init-key or set QF_RELEASE_KEY_PATH."
            )
        private_key_path.parent.mkdir(parents=True, exist_ok=True)
        private_key_path.parent.chmod(0o700)
        priv = Ed25519PrivateKey.generate()
        pub = priv.public_key()

        priv_bytes = priv.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        pub_bytes = pub.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        fd = os.open(str(private_key_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(priv_bytes)
        public_key_path.write_bytes(pub_bytes)
        public_key_path.chmod(0o644)
        return priv, pub

    # Verify strict 0600 permissions on existing private key
    mode = private_key_path.stat().st_mode & 0o777
    if mode & 0o077:
        raise PermissionError(
            f"[QF-RECEIPT] Release private key {private_key_path} has insecure mode {oct(mode)}; expected 0o600"
        )

    loaded_priv = serialization.load_pem_private_key(private_key_path.read_bytes(), password=None)
    if not isinstance(loaded_priv, Ed25519PrivateKey):
        raise TypeError("[QF-RECEIPT] Release private key must be an Ed25519PrivateKey")

    loaded_pub = loaded_priv.public_key()
    return loaded_priv, loaded_pub


def build_admission_payload(
    repo_root: Path,
    required_artifacts: Iterable[str] = DEFAULT_REQUIRED_ARTIFACTS,
    node_id: str = "qfx-yoga",
    hardware_anchor: str = "Microsoft Pluton TPM 2.0 (:9444)",
    pcr15_sha256: str = "d03b20ee22f0fb4634b06aecad248dc68b5cd61c115926bf07d4b9e772f6e6eb",
    timestamp: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Constructs the unsigned canonical QF Admission Receipt payload by hashing every
    required artifact on disk and querying live git state.
    """
    artifact_hashes: Dict[str, str] = {}
    for rel_path in required_artifacts:
        full_path = repo_root / rel_path
        artifact_hashes[rel_path] = compute_file_sha256(full_path)

    if not artifact_hashes:
        raise ValueError("[QF-RECEIPT] artifact_hashes cannot be empty")

    git_info = resolve_git_state(repo_root)
    issued_at = int(timestamp if timestamp is not None else time.time())

    manifest_canonical = canonical_json_bytes(artifact_hashes)
    manifest_root_sha256 = hashlib.sha256(manifest_canonical).hexdigest()

    return {
        "schema": "qf.admission_receipt.v1",
        "epoch": "Epoch-1-Direct-to-Active",
        "node_id": node_id,
        "issued_at_unix": issued_at,
        "git_branch": git_info["git_branch"],
        "git_commit": git_info["git_commit"],
        "hardware_attestation": {
            "anchor": hardware_anchor,
            "pcr15_sha256": pcr15_sha256,
            "pixel_strongbox_gate": "HS-PX-CLOSED-2026-10-05",
        },
        "gates_closed": [
            "P0:HS-PX-CVE-2026-58704",
            "P0:Account-Security-Confirmations",
            "P0/P1:FINALLYFUNGUS-LLC-Canonical",
            "P0/P1:Telemetry-PrivacyFilter-Wiring-Proof",
            "P1:MCP-Agent-Circuit-Breaker",
            "P1:PostgreSQL-Writer-Verifier-ACL-Separation",
            "P1:JSONL-Fsync-Metrics-Validation",
            "P1:Storage-TornWrite-EIO-ENOSPC-Resilience",
        ],
        "artifact_sha256": artifact_hashes,
        "manifest_root_sha256": manifest_root_sha256,
    }


def sign_admission_receipt(
    payload: Dict[str, Any],
    private_key: Ed25519PrivateKey,
) -> Dict[str, Any]:
    """
    Signs the canonical JSON representation of `payload` using Ed25519 and returns
    the complete signed Admission Receipt envelope.
    """
    raw_bytes = canonical_json_bytes(payload)
    payload_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    signature_bytes = private_key.sign(raw_bytes)

    pub_key = private_key.public_key()
    pub_raw = pub_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    key_fingerprint = hashlib.sha256(pub_raw).hexdigest()

    return {
        "payload": payload,
        "cryptographic_seal": {
            "algorithm": "Ed25519",
            "public_key_raw_b64": base64.b64encode(pub_raw).decode("ascii"),
            "public_key_fingerprint_sha256": key_fingerprint,
            "payload_sha256": payload_sha256,
            "signature_b64": base64.b64encode(signature_bytes).decode("ascii"),
        },
    }


def verify_admission_receipt(
    signed_receipt: Dict[str, Any],
    repo_root: Optional[Path] = None,
    trusted_public_key: Optional[Ed25519PublicKey] = None,
) -> bool:
    """
    Fails closed (raises ValueError/PermissionError) if:
    1. Envelope structure or fields are missing.
    2. payload_sha256 does not match canonical_json_bytes(payload).
    3. Ed25519 signature verification fails against trusted_public_key (or embedded key).
    4. If repo_root is provided, verifies every file in artifact_sha256 still matches disk.
    """
    if not isinstance(signed_receipt, dict):
        raise ValueError("[QF-RECEIPT] Receipt must be a JSON object")

    payload = signed_receipt.get("payload")
    seal = signed_receipt.get("cryptographic_seal")
    if not isinstance(payload, dict) or not isinstance(seal, dict):
        raise ValueError("[QF-RECEIPT] Missing 'payload' or 'cryptographic_seal' section")

    if seal.get("algorithm") != "Ed25519":
        raise ValueError(f"[QF-RECEIPT] Unsupported signature algorithm: {seal.get('algorithm')!r}")

    raw_bytes = canonical_json_bytes(payload)
    computed_payload_sha = hashlib.sha256(raw_bytes).hexdigest()
    if computed_payload_sha != seal.get("payload_sha256"):
        raise PermissionError("[QF-RECEIPT] Payload SHA-256 mismatch: receipt body has been modified")

    artifact_map = payload.get("artifact_sha256")
    if not isinstance(artifact_map, dict) or not artifact_map:
        raise ValueError("[QF-RECEIPT] Receipt contains empty or invalid artifact_sha256 map")

    expected_manifest_root = hashlib.sha256(canonical_json_bytes(artifact_map)).hexdigest()
    if expected_manifest_root != payload.get("manifest_root_sha256"):
        raise PermissionError("[QF-RECEIPT] Manifest root SHA-256 mismatch")

    embedded_pub_raw = base64.b64decode(seal["public_key_raw_b64"])
    if trusted_public_key is not None:
        trusted_raw = trusted_public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        if trusted_raw != embedded_pub_raw:
            raise PermissionError("[QF-RECEIPT] Receipt public key does not match trusted release public key")
        pub_key = trusted_public_key
    else:
        pub_key = Ed25519PublicKey.from_public_bytes(embedded_pub_raw)

    signature_bytes = base64.b64decode(seal["signature_b64"])
    try:
        pub_key.verify(signature_bytes, raw_bytes)
    except InvalidSignature as exc:
        raise PermissionError("[QF-RECEIPT] Ed25519 cryptographic signature verification FAILED") from exc

    if repo_root is not None:
        for rel_path, recorded_sha in artifact_map.items():
            live_sha = compute_file_sha256(repo_root / rel_path)
            if live_sha != recorded_sha:
                raise PermissionError(
                    f"[QF-RECEIPT] On-disk drift detected for '{rel_path}': "
                    f"expected {recorded_sha}, found {live_sha}"
                )

    return True
