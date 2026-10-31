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


# ==============================================================================
# QF-M6 Phase M6-A: Hybrid Ed25519 + ML-DSA-65 (NIST FIPS 204) & SHA-256/SHA-384
# ==============================================================================
DEFAULT_MLDSA65_PRIVATE_KEY_PATH = DEFAULT_RELEASE_KEY_DIR / "qf_release_mldsa65.pem"
DEFAULT_MLDSA65_PUBLIC_KEY_PATH = DEFAULT_RELEASE_KEY_DIR / "qf_release_mldsa65.pub.pem"
VALID_KEY_ENVIRONMENTS = frozenset({"dev", "test", "prod"})


def compute_file_sha384(file_path: Path) -> str:
    """Computes the real SHA-384 hex digest of a file on disk for long-term hash agility."""
    if not file_path.is_file():
        raise FileNotFoundError(f"[QF-RECEIPT-V2] Required artifact missing on disk: {file_path}")
    h = hashlib.sha384()
    with open(file_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_or_load_mldsa65_keypair(
    private_key_path: Path = DEFAULT_MLDSA65_PRIVATE_KEY_PATH,
    public_key_path: Path = DEFAULT_MLDSA65_PUBLIC_KEY_PATH,
    auto_generate_if_missing: bool = False,
) -> Tuple[bytes, bytes]:
    """
    Loads or generates a NIST FIPS 204 ML-DSA-65 keypair via OpenSSL 3.5+,
    strictly enforcing 0600 permissions on the private key PEM.
    """
    if not private_key_path.exists():
        if not auto_generate_if_missing:
            raise FileNotFoundError(
                f"[QF-RECEIPT-V2] ML-DSA-65 release private key not found at {private_key_path}."
            )
        private_key_path.parent.mkdir(parents=True, exist_ok=True)
        private_key_path.parent.chmod(0o700)
        priv_pem = subprocess.check_output(
            ["openssl", "genpkey", "-algorithm", "ML-DSA-65"],
            stderr=subprocess.DEVNULL,
        )
        fd = os.open(str(private_key_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(priv_pem)
        pub_pem = subprocess.check_output(
            ["openssl", "pkey", "-in", str(private_key_path), "-pubout"],
            stderr=subprocess.DEVNULL,
        )
        public_key_path.write_bytes(pub_pem)
        public_key_path.chmod(0o644)
        return priv_pem, pub_pem

    mode = private_key_path.stat().st_mode & 0o777
    if mode & 0o077:
        raise PermissionError(
            f"[QF-RECEIPT-V2] ML-DSA-65 private key {private_key_path} has insecure mode {oct(mode)}; expected 0o600"
        )
    priv_pem = private_key_path.read_bytes()
    if public_key_path.is_file():
        pub_pem = public_key_path.read_bytes()
    else:
        pub_pem = subprocess.check_output(
            ["openssl", "pkey", "-in", str(private_key_path), "-pubout"],
            stderr=subprocess.DEVNULL,
        )
    return priv_pem, pub_pem


def _mldsa65_sign_bytes(data: bytes, private_key_path: Path) -> bytes:
    """Signs raw message bytes using NIST FIPS 204 ML-DSA-65 (`openssl pkeyutl -rawin`)."""
    import tempfile

    mode = private_key_path.stat().st_mode & 0o777
    if mode & 0o077:
        raise PermissionError(
            f"[QF-RECEIPT-V2] ML-DSA-65 private key {private_key_path} has insecure mode {oct(mode)}; expected 0o600"
        )
    with tempfile.TemporaryDirectory() as tmpdir:
        msg_file = Path(tmpdir) / "msg.bin"
        sig_file = Path(tmpdir) / "sig.bin"
        msg_file.write_bytes(data)
        subprocess.run(
            [
                "openssl",
                "pkeyutl",
                "-sign",
                "-inkey",
                str(private_key_path),
                "-rawin",
                "-in",
                str(msg_file),
                "-out",
                str(sig_file),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return sig_file.read_bytes()


def _mldsa65_verify_bytes(data: bytes, signature: bytes, public_key_pem: bytes) -> bool:
    """Verifies raw message bytes against a NIST FIPS 204 ML-DSA-65 signature."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        msg_file = Path(tmpdir) / "msg.bin"
        sig_file = Path(tmpdir) / "sig.bin"
        pub_file = Path(tmpdir) / "pub.pem"
        msg_file.write_bytes(data)
        sig_file.write_bytes(signature)
        pub_file.write_bytes(public_key_pem)
        proc = subprocess.run(
            [
                "openssl",
                "pkeyutl",
                "-verify",
                "-pubin",
                "-inkey",
                str(pub_file),
                "-rawin",
                "-in",
                str(msg_file),
                "-sigfile",
                str(sig_file),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return proc.returncode == 0


def build_hybrid_admission_payload_v2(
    repo_root: Path,
    required_artifacts: Iterable[str] = DEFAULT_REQUIRED_ARTIFACTS,
    release_version: str = "QF-M6.0.0",
    anti_rollback_counter: int = 2,
    key_environment: str = "prod",
    sbom_rel_path: str = "cbom_alpha_node_template.json",
    previous_checkpoint_rel_path: Optional[str] = "build_check/qf_m5_signed_admission_receipt.json",
    node_id: str = "qfx-yoga",
    timestamp: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Constructs the QF-M6-A `qf.admission_receipt.v2` canonical payload with:
      - Dual SHA-256 and SHA-384 artifact digests
      - Signed SBOM/CBOM digests (SHA-256 + SHA-384)
      - Release version & anti-rollback counter
      - Cryptographic link to the preserved QF-M5 historical checkpoint
    """
    if key_environment not in VALID_KEY_ENVIRONMENTS:
        raise ValueError(f"[QF-RECEIPT-V2] Invalid key_environment {key_environment!r}; must be one of {sorted(VALID_KEY_ENVIRONMENTS)}")
    if isinstance(anti_rollback_counter, bool) or not isinstance(anti_rollback_counter, int) or anti_rollback_counter < 1:
        raise ValueError("[QF-RECEIPT-V2] anti_rollback_counter must be a positive integer")

    artifact_sha256: Dict[str, str] = {}
    artifact_sha384: Dict[str, str] = {}
    for rel_path in required_artifacts:
        full_path = repo_root / rel_path
        artifact_sha256[rel_path] = compute_file_sha256(full_path)
        artifact_sha384[rel_path] = compute_file_sha384(full_path)

    if not artifact_sha256:
        raise ValueError("[QF-RECEIPT-V2] artifact_sha256 cannot be empty")

    sbom_full = repo_root / sbom_rel_path
    sbom_sha256 = compute_file_sha256(sbom_full)
    sbom_sha384 = compute_file_sha384(sbom_full)

    prev_checkpoint_sha256: Optional[str] = None
    if previous_checkpoint_rel_path:
        prev_full = repo_root / previous_checkpoint_rel_path
        if prev_full.is_file():
            prev_checkpoint_sha256 = compute_file_sha256(prev_full)

    git_info = resolve_git_state(repo_root)
    issued_at = int(timestamp if timestamp is not None else time.time())

    manifest_root_sha256 = hashlib.sha256(canonical_json_bytes(artifact_sha256)).hexdigest()
    manifest_root_sha384 = hashlib.sha384(canonical_json_bytes(artifact_sha384)).hexdigest()

    return {
        "schema": "qf.admission_receipt.v2",
        "release_version": release_version,
        "anti_rollback_counter": anti_rollback_counter,
        "previous_checkpoint_sha256": prev_checkpoint_sha256,
        "key_environment": key_environment,
        "node_id": node_id,
        "issued_at_unix": issued_at,
        "git_branch": git_info["git_branch"],
        "git_commit": git_info["git_commit"],
        "sbom": {
            "path": sbom_rel_path,
            "sha256": sbom_sha256,
            "sha384": sbom_sha384,
        },
        "artifact_sha256": artifact_sha256,
        "artifact_sha384": artifact_sha384,
        "manifest_root_sha256": manifest_root_sha256,
        "manifest_root_sha384": manifest_root_sha384,
    }


def sign_hybrid_admission_receipt_v2(
    payload: Dict[str, Any],
    ed25519_private_key: Ed25519PrivateKey,
    mldsa65_private_key_path: Path,
    mldsa65_public_key_pem: bytes,
) -> Dict[str, Any]:
    """
    Produces a hybrid classical (Ed25519) + post-quantum (NIST FIPS 204 ML-DSA-65)
    cryptographic seal over the canonical JSON bytes of `payload`.
    """
    if payload.get("schema") != "qf.admission_receipt.v2":
        raise ValueError("[QF-RECEIPT-V2] Payload schema must be 'qf.admission_receipt.v2'")

    raw_bytes = canonical_json_bytes(payload)
    payload_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    payload_sha384 = hashlib.sha384(raw_bytes).hexdigest()

    # 1. Classical Ed25519 signature
    ed_sig = ed25519_private_key.sign(raw_bytes)
    ed_pub_raw = ed25519_private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    ed_fp = hashlib.sha256(ed_pub_raw).hexdigest()

    # 2. Post-Quantum NIST FIPS 204 ML-DSA-65 signature
    pq_sig = _mldsa65_sign_bytes(raw_bytes, mldsa65_private_key_path)
    pq_fp = hashlib.sha256(mldsa65_public_key_pem).hexdigest()

    return {
        "payload": payload,
        "cryptographic_seal": {
            "scheme": "HYBRID-ED25519-ML-DSA-65",
            "payload_sha256": payload_sha256,
            "payload_sha384": payload_sha384,
            "ed25519": {
                "algorithm": "Ed25519",
                "public_key_raw_b64": base64.b64encode(ed_pub_raw).decode("ascii"),
                "public_key_fingerprint_sha256": ed_fp,
                "signature_b64": base64.b64encode(ed_sig).decode("ascii"),
            },
            "ml_dsa_65": {
                "algorithm": "ML-DSA-65",
                "standard": "NIST-FIPS-204",
                "oid": "2.16.840.1.101.3.4.3.18",
                "public_key_pem_b64": base64.b64encode(mldsa65_public_key_pem).decode("ascii"),
                "public_key_fingerprint_sha256": pq_fp,
                "signature_b64": base64.b64encode(pq_sig).decode("ascii"),
            },
        },
    }


def issue_key_delegation_certificate(
    cert_id: str,
    key_environment: str,
    delegated_ed25519_public_key: Ed25519PublicKey,
    delegated_mldsa65_public_key_pem: bytes,
    root_ed25519_private_key: Ed25519PrivateKey,
    root_mldsa65_private_key_path: Path,
    root_mldsa65_public_key_pem: bytes,
    not_before_unix: int,
    not_after_unix: int,
) -> Dict[str, Any]:
    """
    Tier 0 Offline Root Ceremony (`QF-KEY-01` / `M6-B`):
    Issues a conjunctive Hybrid Root-signed Key Delegation Certificate (`qf.key_delegation_cert.v1`)
    binding a Tier 1 Release Signing Keypair (Ed25519 + ML-DSA-65) to a specific `key_environment`
    (`dev` | `test` | `prod`) and validity window `[not_before_unix, not_after_unix]`.
    """
    if not cert_id or not isinstance(cert_id, str):
        raise ValueError("[QF-KEY-01] cert_id must be a non-empty string")
    if key_environment not in VALID_KEY_ENVIRONMENTS:
        raise ValueError(f"[QF-KEY-01] Invalid key_environment {key_environment!r}; must be in {sorted(VALID_KEY_ENVIRONMENTS)}")
    if not isinstance(not_before_unix, int) or not isinstance(not_after_unix, int) or not_after_unix <= not_before_unix:
        raise ValueError("[QF-KEY-01] Invalid certificate validity window")

    del_ed_raw = delegated_ed25519_public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    del_ed_fp = hashlib.sha256(del_ed_raw).hexdigest()
    del_pq_fp = hashlib.sha256(delegated_mldsa65_public_key_pem).hexdigest()

    cert_payload = {
        "schema": "qf.key_delegation_cert.v1",
        "cert_id": cert_id,
        "key_environment": key_environment,
        "not_before_unix": int(not_before_unix),
        "not_after_unix": int(not_after_unix),
        "delegated_ed25519_public_key_raw_b64": base64.b64encode(del_ed_raw).decode("ascii"),
        "delegated_ed25519_fingerprint_sha256": del_ed_fp,
        "delegated_mldsa65_public_key_pem_b64": base64.b64encode(delegated_mldsa65_public_key_pem).decode("ascii"),
        "delegated_mldsa65_fingerprint_sha256": del_pq_fp,
    }
    raw_bytes = canonical_json_bytes(cert_payload)
    root_ed_sig = root_ed25519_private_key.sign(raw_bytes)
    root_ed_pub_raw = root_ed25519_private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    root_pq_sig = _mldsa65_sign_bytes(raw_bytes, root_mldsa65_private_key_path)

    return {
        "payload": cert_payload,
        "root_cryptographic_seal": {
            "scheme": "HYBRID-ROOT-ED25519-ML-DSA-65",
            "payload_sha256": hashlib.sha256(raw_bytes).hexdigest(),
            "payload_sha384": hashlib.sha384(raw_bytes).hexdigest(),
            "root_ed25519_public_key_raw_b64": base64.b64encode(root_ed_pub_raw).decode("ascii"),
            "root_ed25519_fingerprint_sha256": hashlib.sha256(root_ed_pub_raw).hexdigest(),
            "root_ed25519_signature_b64": base64.b64encode(root_ed_sig).decode("ascii"),
            "root_mldsa65_public_key_pem_b64": base64.b64encode(root_mldsa65_public_key_pem).decode("ascii"),
            "root_mldsa65_fingerprint_sha256": hashlib.sha256(root_mldsa65_public_key_pem).hexdigest(),
            "root_mldsa65_signature_b64": base64.b64encode(root_pq_sig).decode("ascii"),
        },
    }


def issue_key_revocation_list(
    krl_sequence: int,
    issued_at_unix: int,
    root_ed25519_private_key: Ed25519PrivateKey,
    root_mldsa65_private_key_path: Path,
    root_mldsa65_public_key_pem: bytes,
    revoked_cert_ids: Optional[Sequence[str]] = None,
    revoked_ed25519_fingerprints_sha256: Optional[Sequence[str]] = None,
    revoked_mldsa65_fingerprints_sha256: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """
    Tier 0 Offline Root Ceremony (`QF-KEY-01` / `M6-B`):
    Issues a conjunctive Hybrid Root-signed Key Revocation List (`qf.key_revocation_list.v1`)
    with monotonic `krl_sequence`.
    """
    if isinstance(krl_sequence, bool) or not isinstance(krl_sequence, int) or krl_sequence < 1:
        raise ValueError("[QF-KEY-01] krl_sequence must be a positive integer")

    krl_payload = {
        "schema": "qf.key_revocation_list.v1",
        "krl_sequence": int(krl_sequence),
        "issued_at_unix": int(issued_at_unix),
        "revoked_cert_ids": sorted(set(revoked_cert_ids or [])),
        "revoked_ed25519_fingerprints_sha256": sorted(set(revoked_ed25519_fingerprints_sha256 or [])),
        "revoked_mldsa65_fingerprints_sha256": sorted(set(revoked_mldsa65_fingerprints_sha256 or [])),
    }
    raw_bytes = canonical_json_bytes(krl_payload)
    root_ed_sig = root_ed25519_private_key.sign(raw_bytes)
    root_ed_pub_raw = root_ed25519_private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    root_pq_sig = _mldsa65_sign_bytes(raw_bytes, root_mldsa65_private_key_path)

    return {
        "payload": krl_payload,
        "root_cryptographic_seal": {
            "scheme": "HYBRID-ROOT-ED25519-ML-DSA-65",
            "payload_sha256": hashlib.sha256(raw_bytes).hexdigest(),
            "payload_sha384": hashlib.sha384(raw_bytes).hexdigest(),
            "root_ed25519_public_key_raw_b64": base64.b64encode(root_ed_pub_raw).decode("ascii"),
            "root_ed25519_fingerprint_sha256": hashlib.sha256(root_ed_pub_raw).hexdigest(),
            "root_ed25519_signature_b64": base64.b64encode(root_ed_sig).decode("ascii"),
            "root_mldsa65_public_key_pem_b64": base64.b64encode(root_mldsa65_public_key_pem).decode("ascii"),
            "root_mldsa65_fingerprint_sha256": hashlib.sha256(root_mldsa65_public_key_pem).hexdigest(),
            "root_mldsa65_signature_b64": base64.b64encode(root_pq_sig).decode("ascii"),
        },
    }


def _verify_root_seal(
    signed_obj: Dict[str, Any],
    expected_schema: str,
    trusted_root_ed25519_public_key: Ed25519PublicKey,
    trusted_root_mldsa65_public_key_pem: bytes,
) -> Dict[str, Any]:
    if not isinstance(signed_obj, dict):
        raise PermissionError(f"[QF-KEY-01] Expected dict for {expected_schema}")
    payload = signed_obj.get("payload")
    seal = signed_obj.get("root_cryptographic_seal")
    if not isinstance(payload, dict) or not isinstance(seal, dict):
        raise PermissionError(f"[QF-KEY-01] Missing payload or root_cryptographic_seal in {expected_schema}")
    if payload.get("schema") != expected_schema:
        raise PermissionError(f"[QF-KEY-01] Schema mismatch: expected {expected_schema!r}, got {payload.get('schema')!r}")
    if seal.get("scheme") != "HYBRID-ROOT-ED25519-ML-DSA-65":
        raise PermissionError(f"[QF-KEY-01] Invalid root seal scheme in {expected_schema}")

    raw_bytes = canonical_json_bytes(payload)
    if hashlib.sha256(raw_bytes).hexdigest() != seal.get("payload_sha256"):
        raise PermissionError(f"[QF-KEY-01] Root payload SHA-256 mismatch in {expected_schema}")
    if hashlib.sha384(raw_bytes).hexdigest() != seal.get("payload_sha384"):
        raise PermissionError(f"[QF-KEY-01] Root payload SHA-384 mismatch in {expected_schema}")

    trusted_root_ed_raw = trusted_root_ed25519_public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    if base64.b64decode(seal.get("root_ed25519_public_key_raw_b64", "")) != trusted_root_ed_raw:
        raise PermissionError(f"[QF-KEY-01] Untrusted Root Ed25519 key in {expected_schema}")

    try:
        trusted_root_ed25519_public_key.verify(
            base64.b64decode(seal.get("root_ed25519_signature_b64", "")),
            raw_bytes,
        )
    except (ValueError, InvalidSignature) as exc:
        raise PermissionError(f"[QF-KEY-01] Root Ed25519 signature verification FAILED on {expected_schema}") from exc

    if base64.b64decode(seal.get("root_mldsa65_public_key_pem_b64", "")) != trusted_root_mldsa65_public_key_pem:
        raise PermissionError(f"[QF-KEY-01] Untrusted Root ML-DSA-65 key in {expected_schema}")

    if not _mldsa65_verify_bytes(
        raw_bytes,
        base64.b64decode(seal.get("root_mldsa65_signature_b64", "")),
        trusted_root_mldsa65_public_key_pem,
    ):
        raise PermissionError(f"[QF-KEY-01] Root ML-DSA-65 signature verification FAILED on {expected_schema}")

    return payload


def verify_key_sovereignty_chain(
    delegation_cert: Dict[str, Any],
    krl: Dict[str, Any],
    trusted_root_ed25519_public_key: Ed25519PublicKey,
    trusted_root_mldsa65_public_key_pem: bytes,
    expected_key_environment: str,
    evaluation_time_unix: int,
    min_krl_sequence: int = 1,
) -> Tuple[Ed25519PublicKey, bytes]:
    """
    Verifies the Two-Tier Sovereign Key Hierarchy (`QF-KEY-01` / `M6-B`):
      1. Conjunctively verifies the Offline Root seal (`Ed25519` + `ML-DSA-65`) on `delegation_cert`.
      2. Conjunctively verifies the Offline Root seal (`Ed25519` + `ML-DSA-65`) on `krl`.
      3. Enforces anti-replay on the KRL (`krl_sequence >= min_krl_sequence`).
      4. Enforces strict environment separation (`cert.key_environment == expected_key_environment`).
      5. Enforces delegation validity window (`not_before_unix <= evaluation_time_unix <= not_after_unix`).
      6. Rejects any certificate or delegated public key (`Ed25519` or `ML-DSA-65`) present in the KRL.
    Returns `(delegated_ed25519_public_key, delegated_mldsa65_public_key_pem)`.
    """
    cert_payload = _verify_root_seal(
        delegation_cert,
        "qf.key_delegation_cert.v1",
        trusted_root_ed25519_public_key,
        trusted_root_mldsa65_public_key_pem,
    )
    krl_payload = _verify_root_seal(
        krl,
        "qf.key_revocation_list.v1",
        trusted_root_ed25519_public_key,
        trusted_root_mldsa65_public_key_pem,
    )

    krl_seq = krl_payload.get("krl_sequence")
    if isinstance(krl_seq, bool) or not isinstance(krl_seq, int) or krl_seq < min_krl_sequence:
        raise PermissionError(
            f"[QF-KEY-01] Stale KRL sequence {krl_seq!r} < min_krl_sequence {min_krl_sequence}"
        )

    if cert_payload.get("key_environment") != expected_key_environment:
        raise PermissionError(
            f"[QF-KEY-01] Delegated key environment {cert_payload.get('key_environment')!r} != expected {expected_key_environment!r}"
        )

    not_before = cert_payload.get("not_before_unix")
    not_after = cert_payload.get("not_after_unix")
    if not isinstance(not_before, int) or not isinstance(not_after, int):
        raise PermissionError("[QF-KEY-01] Invalid validity timestamps in delegation certificate")
    if evaluation_time_unix < not_before or evaluation_time_unix > not_after:
        raise PermissionError(
            f"[QF-KEY-01] Delegation certificate expired or not yet valid at {evaluation_time_unix} "
            f"(window [{not_before}, {not_after}])"
        )

    cert_id = cert_payload.get("cert_id")
    del_ed_fp = cert_payload.get("delegated_ed25519_fingerprint_sha256")
    del_pq_fp = cert_payload.get("delegated_mldsa65_fingerprint_sha256")

    if cert_id in set(krl_payload.get("revoked_cert_ids", [])):
        raise PermissionError(f"[QF-KEY-01] Delegation certificate {cert_id!r} has been REVOKED by Root KRL")
    if del_ed_fp in set(krl_payload.get("revoked_ed25519_fingerprints_sha256", [])):
        raise PermissionError(f"[QF-KEY-01] Delegated Ed25519 key {del_ed_fp!r} has been REVOKED by Root KRL")
    if del_pq_fp in set(krl_payload.get("revoked_mldsa65_fingerprints_sha256", [])):
        raise PermissionError(f"[QF-KEY-01] Delegated ML-DSA-65 key {del_pq_fp!r} has been REVOKED by Root KRL")

    del_ed_raw = base64.b64decode(cert_payload["delegated_ed25519_public_key_raw_b64"])
    del_pq_pem = base64.b64decode(cert_payload["delegated_mldsa65_public_key_pem_b64"])
    if hashlib.sha256(del_ed_raw).hexdigest() != del_ed_fp:
        raise PermissionError("[QF-KEY-01] Delegated Ed25519 public key fingerprint mismatch")
    if hashlib.sha256(del_pq_pem).hexdigest() != del_pq_fp:
        raise PermissionError("[QF-KEY-01] Delegated ML-DSA-65 public key fingerprint mismatch")

    return Ed25519PublicKey.from_public_bytes(del_ed_raw), del_pq_pem


def verify_hybrid_admission_receipt_v2(
    signed_receipt: Dict[str, Any],
    repo_root: Optional[Path] = None,
    trusted_ed25519_public_key: Optional[Ed25519PublicKey] = None,
    trusted_mldsa65_public_key_pem: Optional[bytes] = None,
    min_accepted_counter: int = 1,
    expected_key_environment: str = "prod",
    delegation_cert: Optional[Dict[str, Any]] = None,
    krl: Optional[Dict[str, Any]] = None,
    trusted_root_ed25519_public_key: Optional[Ed25519PublicKey] = None,
    trusted_root_mldsa65_public_key_pem: Optional[bytes] = None,
    min_krl_sequence: int = 1,
) -> bool:
    """
    Conjunctive fail-closed verifier for `qf.admission_receipt.v2` (`QF-CRYPTO-01`, `QF-KEY-01`, `QF-RELEASE-01`).
    Requires BOTH Ed25519 AND NIST FIPS 204 ML-DSA-65 signatures to verify, BOTH SHA-256 and
    SHA-384 digests to match, SBOM digests to match, and anti_rollback_counter > min_accepted_counter.
    When `delegation_cert` or `trusted_root_*` keys are supplied, enforces full Two-Tier Offline Root
    Key Sovereignty (`QF-KEY-01`) and KRL revocation checks prior to trusting the release keys.
    """
    if not isinstance(signed_receipt, dict):
        raise ValueError("[QF-RECEIPT-V2] Receipt must be a JSON object")

    payload = signed_receipt.get("payload")
    seal = signed_receipt.get("cryptographic_seal")
    if not isinstance(payload, dict) or not isinstance(seal, dict):
        raise ValueError("[QF-RECEIPT-V2] Missing 'payload' or 'cryptographic_seal'")

    if payload.get("schema") != "qf.admission_receipt.v2":
        raise ValueError(f"[QF-RECEIPT-V2] Unsupported schema: {payload.get('schema')!r}")
    if seal.get("scheme") != "HYBRID-ED25519-ML-DSA-65":
        raise PermissionError(f"[QF-RECEIPT-V2] Invalid hybrid seal scheme: {seal.get('scheme')!r}")

    counter = payload.get("anti_rollback_counter")
    if isinstance(counter, bool) or not isinstance(counter, int) or counter <= min_accepted_counter:
        raise PermissionError(
            f"[QF-RECEIPT-V2] Anti-rollback violation: counter {counter!r} <= min_accepted_counter {min_accepted_counter}"
        )

    if payload.get("key_environment") != expected_key_environment:
        raise PermissionError(
            f"[QF-RECEIPT-V2] Key environment mismatch: expected {expected_key_environment!r}, got {payload.get('key_environment')!r}"
        )

    # QF-KEY-01 (M6-B): Verify Offline Root Delegation Certificate + KRL Chain if Root trust is configured
    if any(
        x is not None
        for x in (delegation_cert, krl, trusted_root_ed25519_public_key, trusted_root_mldsa65_public_key_pem)
    ):
        if (
            delegation_cert is None
            or krl is None
            or trusted_root_ed25519_public_key is None
            or trusted_root_mldsa65_public_key_pem is None
        ):
            raise PermissionError(
                "[QF-KEY-01] Incomplete key sovereignty chain: delegation_cert, krl, "
                "trusted_root_ed25519_public_key, and trusted_root_mldsa65_public_key_pem must all be supplied"
            )
        issued_at_unix = payload.get("issued_at_unix")
        if not isinstance(issued_at_unix, int):
            raise PermissionError("[QF-KEY-01] Receipt missing valid integer issued_at_unix")
        delegated_ed_pub, delegated_pq_pem = verify_key_sovereignty_chain(
            delegation_cert=delegation_cert,
            krl=krl,
            trusted_root_ed25519_public_key=trusted_root_ed25519_public_key,
            trusted_root_mldsa65_public_key_pem=trusted_root_mldsa65_public_key_pem,
            expected_key_environment=expected_key_environment,
            evaluation_time_unix=issued_at_unix,
            min_krl_sequence=min_krl_sequence,
        )
        trusted_ed25519_public_key = delegated_ed_pub
        trusted_mldsa65_public_key_pem = delegated_pq_pem

    raw_bytes = canonical_json_bytes(payload)
    if hashlib.sha256(raw_bytes).hexdigest() != seal.get("payload_sha256"):
        raise PermissionError("[QF-RECEIPT-V2] Payload SHA-256 mismatch")
    if hashlib.sha384(raw_bytes).hexdigest() != seal.get("payload_sha384"):
        raise PermissionError("[QF-RECEIPT-V2] Payload SHA-384 mismatch")

    artifact_sha256 = payload.get("artifact_sha256")
    artifact_sha384 = payload.get("artifact_sha384")
    if not isinstance(artifact_sha256, dict) or not isinstance(artifact_sha384, dict) or not artifact_sha256:
        raise ValueError("[QF-RECEIPT-V2] Missing artifact_sha256 or artifact_sha384 map")
    if set(artifact_sha256.keys()) != set(artifact_sha384.keys()):
        raise PermissionError("[QF-RECEIPT-V2] Artifact key mismatch between SHA-256 and SHA-384 maps")

    if hashlib.sha256(canonical_json_bytes(artifact_sha256)).hexdigest() != payload.get("manifest_root_sha256"):
        raise PermissionError("[QF-RECEIPT-V2] Manifest root SHA-256 mismatch")
    if hashlib.sha384(canonical_json_bytes(artifact_sha384)).hexdigest() != payload.get("manifest_root_sha384"):
        raise PermissionError("[QF-RECEIPT-V2] Manifest root SHA-384 mismatch")

    # 1. Verify Classical Ed25519 Signature
    ed_block = seal.get("ed25519")
    if not isinstance(ed_block, dict) or ed_block.get("algorithm") != "Ed25519":
        raise PermissionError("[QF-RECEIPT-V2] Missing or invalid Ed25519 seal block")
    embedded_ed_pub = base64.b64decode(ed_block["public_key_raw_b64"])
    if trusted_ed25519_public_key is not None:
        trusted_ed_raw = trusted_ed25519_public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        if trusted_ed_raw != embedded_ed_pub:
            raise PermissionError("[QF-RECEIPT-V2] Ed25519 public key does not match trusted release key")
        ed_pub = trusted_ed25519_public_key
    else:
        ed_pub = Ed25519PublicKey.from_public_bytes(embedded_ed_pub)

    try:
        ed_pub.verify(base64.b64decode(ed_block["signature_b64"]), raw_bytes)
    except (ValueError, InvalidSignature) as exc:
        raise PermissionError("[QF-RECEIPT-V2] Ed25519 signature verification FAILED") from exc

    # 2. Verify Post-Quantum NIST FIPS 204 ML-DSA-65 Signature
    pq_block = seal.get("ml_dsa_65")
    if not isinstance(pq_block, dict) or pq_block.get("algorithm") != "ML-DSA-65":
        raise PermissionError("[QF-RECEIPT-V2] Missing or invalid ML-DSA-65 seal block")
    embedded_pq_pub = base64.b64decode(pq_block["public_key_pem_b64"])
    if trusted_mldsa65_public_key_pem is not None and trusted_mldsa65_public_key_pem != embedded_pq_pub:
        raise PermissionError("[QF-RECEIPT-V2] ML-DSA-65 public key does not match trusted release key")

    pq_sig = base64.b64decode(pq_block["signature_b64"])
    if not _mldsa65_verify_bytes(raw_bytes, pq_sig, embedded_pq_pub):
        raise PermissionError("[QF-RECEIPT-V2] NIST FIPS 204 ML-DSA-65 signature verification FAILED")

    # 3. Verify On-Disk Artifacts & SBOM (SHA-256 + SHA-384)
    if repo_root is not None:
        sbom = payload.get("sbom", {})
        if not isinstance(sbom, dict) or not sbom.get("path"):
            raise PermissionError("[QF-RECEIPT-V2] Missing SBOM block in payload")
        sbom_path = repo_root / str(sbom["path"])
        if compute_file_sha256(sbom_path) != sbom.get("sha256") or compute_file_sha384(sbom_path) != sbom.get("sha384"):
            raise PermissionError("[QF-RECEIPT-V2] On-disk SBOM digest mismatch")

        for rel_path in artifact_sha256:
            full_p = repo_root / rel_path
            if compute_file_sha256(full_p) != artifact_sha256[rel_path]:
                raise PermissionError(f"[QF-RECEIPT-V2] On-disk SHA-256 drift detected for '{rel_path}'")
            if compute_file_sha384(full_p) != artifact_sha384[rel_path]:
                raise PermissionError(f"[QF-RECEIPT-V2] On-disk SHA-384 drift detected for '{rel_path}'")

    return True


