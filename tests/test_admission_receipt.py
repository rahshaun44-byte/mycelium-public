# tests/test_admission_receipt.py
"""
P1 #5 Verification Suite: Cryptographic Admission Receipt Signing & Verification.
"""

import copy
import subprocess
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.admission_receipt import (
    build_admission_payload,
    ensure_or_load_release_keypair,
    sign_admission_receipt,
    verify_admission_receipt,
)


@pytest.fixture()
def temp_git_repo(tmp_path):
    """Creates a minimal real git repository with sample artifact files for deterministic testing."""
    subprocess.run(["git", "init", str(tmp_path)], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "rock@quantumflex.local"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Rocky"], check=True)

    artifacts = ["src/privacy_filter.py", "mcp_layer/circuit_breaker.py"]
    for rel in artifacts:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# verified content for {rel}\n", encoding="utf-8")

    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "initial commit"], check=True, stdout=subprocess.DEVNULL)
    return tmp_path, artifacts


def test_end_to_end_sign_and_verify_admission_receipt(temp_git_repo, tmp_path):
    """Valid Ed25519 signature over real git state and on-disk files verifies cleanly."""
    repo_root, artifacts = temp_git_repo
    priv_path = tmp_path / "keys" / "release.pem"
    pub_path = tmp_path / "keys" / "release.pub.pem"

    priv, pub = ensure_or_load_release_keypair(priv_path, pub_path, auto_generate_if_missing=True)
    assert (priv_path.stat().st_mode & 0o777) == 0o600

    payload = build_admission_payload(repo_root=repo_root, required_artifacts=artifacts, timestamp=1761520000)
    receipt = sign_admission_receipt(payload, priv)

    assert verify_admission_receipt(receipt, repo_root=repo_root, trusted_public_key=pub) is True


def test_insecure_private_key_permissions_fail_closed(tmp_path):
    """Release private key with 0644 permissions must raise PermissionError."""
    priv_path = tmp_path / "release.pem"
    pub_path = tmp_path / "release.pub.pem"
    ensure_or_load_release_keypair(priv_path, pub_path, auto_generate_if_missing=True)

    priv_path.chmod(0o644)
    with pytest.raises(PermissionError, match="insecure mode"):
        ensure_or_load_release_keypair(priv_path, pub_path, auto_generate_if_missing=False)


def test_tampered_payload_field_fails_verification(temp_git_repo):
    """Mutating any field in the signed payload (e.g. git_commit or node_id) fails closed."""
    repo_root, artifacts = temp_git_repo
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()

    payload = build_admission_payload(repo_root=repo_root, required_artifacts=artifacts)
    receipt = sign_admission_receipt(payload, priv)

    tampered = copy.deepcopy(receipt)
    tampered["payload"]["node_id"] = "rogue-node"

    with pytest.raises(PermissionError, match="Payload SHA-256 mismatch"):
        verify_admission_receipt(tampered, repo_root=repo_root, trusted_public_key=pub)


def test_untrusted_signing_key_rejected(temp_git_repo):
    """Receipt signed by an attacker's Ed25519 key is rejected when verified against the release public key."""
    repo_root, artifacts = temp_git_repo
    attacker_priv = Ed25519PrivateKey.generate()
    trusted_pub = Ed25519PrivateKey.generate().public_key()

    payload = build_admission_payload(repo_root=repo_root, required_artifacts=artifacts)
    forged_receipt = sign_admission_receipt(payload, attacker_priv)

    with pytest.raises(PermissionError, match="does not match trusted release public key"):
        verify_admission_receipt(forged_receipt, repo_root=repo_root, trusted_public_key=trusted_pub)


def test_post_signing_file_drift_on_disk_detected(temp_git_repo):
    """Modifying a covered source file on disk after signing triggers an on-disk drift PermissionError."""
    repo_root, artifacts = temp_git_repo
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()

    payload = build_admission_payload(repo_root=repo_root, required_artifacts=artifacts)
    receipt = sign_admission_receipt(payload, priv)

    # Modify src/privacy_filter.py on disk after signing
    target_file = repo_root / "src/privacy_filter.py"
    target_file.write_text("# silently modified after signing\n", encoding="utf-8")

    with pytest.raises(PermissionError, match="On-disk drift detected"):
        verify_admission_receipt(receipt, repo_root=repo_root, trusted_public_key=pub)


def test_missing_artifact_fails_closed_before_signing(temp_git_repo):
    """Requesting a non-existent artifact in build_admission_payload raises FileNotFoundError."""
    repo_root, _ = temp_git_repo
    with pytest.raises(FileNotFoundError, match="Required artifact missing"):
        build_admission_payload(repo_root=repo_root, required_artifacts=["src/non_existent_module.py"])
