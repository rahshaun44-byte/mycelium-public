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


def test_qf_m6_a_hybrid_ed25519_mldsa65_sign_and_conjunctive_verify(temp_git_repo, tmp_path):
    """
    QF-M6-A (`QF-CRYPTO-01` & `QF-RELEASE-01`):
    Verifies hybrid Ed25519 + NIST FIPS 204 ML-DSA-65 signing and conjunctive fail-closed
    verification over SHA-256 + SHA-384 artifact digests, SBOM, and anti-rollback counter.
    """
    import base64
    from src.admission_receipt import (
        build_hybrid_admission_payload_v2,
        ensure_or_load_mldsa65_keypair,
        sign_hybrid_admission_receipt_v2,
        verify_hybrid_admission_receipt_v2,
    )

    repo_root, artifacts = temp_git_repo
    sbom_path = repo_root / "cbom_alpha_node_template.json"
    sbom_path.write_text('{"bomFormat": "CycloneDX", "specVersion": "1.6"}\n', encoding="utf-8")

    ed_priv_path = tmp_path / "keys" / "ed25519.pem"
    ed_pub_path = tmp_path / "keys" / "ed25519.pub.pem"
    pq_priv_path = tmp_path / "keys" / "mldsa65.pem"
    pq_pub_path = tmp_path / "keys" / "mldsa65.pub.pem"

    ed_priv, ed_pub = ensure_or_load_release_keypair(ed_priv_path, ed_pub_path, auto_generate_if_missing=True)
    _, pq_pub_pem = ensure_or_load_mldsa65_keypair(pq_priv_path, pq_pub_path, auto_generate_if_missing=True)
    assert (pq_priv_path.stat().st_mode & 0o777) == 0o600

    payload_v2 = build_hybrid_admission_payload_v2(
        repo_root=repo_root,
        required_artifacts=artifacts,
        release_version="QF-M6.0.0",
        anti_rollback_counter=2,
        key_environment="prod",
        sbom_rel_path="cbom_alpha_node_template.json",
        previous_checkpoint_rel_path=None,
    )
    receipt_v2 = sign_hybrid_admission_receipt_v2(
        payload=payload_v2,
        ed25519_private_key=ed_priv,
        mldsa65_private_key_path=pq_priv_path,
        mldsa65_public_key_pem=pq_pub_pem,
    )

    # 1. Both Ed25519 and ML-DSA-65 valid -> PASS
    assert (
        verify_hybrid_admission_receipt_v2(
            receipt_v2,
            repo_root=repo_root,
            trusted_ed25519_public_key=ed_pub,
            trusted_mldsa65_public_key_pem=pq_pub_pem,
            min_accepted_counter=1,
            expected_key_environment="prod",
        )
        is True
    )

    # 2. Tamper ONLY Ed25519 signature while ML-DSA-65 remains valid -> FAIL-CLOSED
    bad_ed = copy.deepcopy(receipt_v2)
    raw_ed_sig = bytearray(base64.b64decode(bad_ed["cryptographic_seal"]["ed25519"]["signature_b64"]))
    raw_ed_sig[0] ^= 0xFF
    bad_ed["cryptographic_seal"]["ed25519"]["signature_b64"] = base64.b64encode(bytes(raw_ed_sig)).decode("ascii")
    with pytest.raises(PermissionError, match="Ed25519 signature verification FAILED"):
        verify_hybrid_admission_receipt_v2(
            bad_ed,
            repo_root=repo_root,
            trusted_ed25519_public_key=ed_pub,
            trusted_mldsa65_public_key_pem=pq_pub_pem,
        )

    # 3. Tamper ONLY ML-DSA-65 signature while Ed25519 remains valid -> FAIL-CLOSED
    bad_pq = copy.deepcopy(receipt_v2)
    raw_pq_sig = bytearray(base64.b64decode(bad_pq["cryptographic_seal"]["ml_dsa_65"]["signature_b64"]))
    raw_pq_sig[0] ^= 0xFF
    bad_pq["cryptographic_seal"]["ml_dsa_65"]["signature_b64"] = base64.b64encode(bytes(raw_pq_sig)).decode("ascii")
    with pytest.raises(PermissionError, match="ML-DSA-65 signature verification FAILED"):
        verify_hybrid_admission_receipt_v2(
            bad_pq,
            repo_root=repo_root,
            trusted_ed25519_public_key=ed_pub,
            trusted_mldsa65_public_key_pem=pq_pub_pem,
        )

    # 4. Anti-rollback violation (counter <= min_accepted_counter) -> FAIL-CLOSED
    with pytest.raises(PermissionError, match="Anti-rollback violation"):
        verify_hybrid_admission_receipt_v2(
            receipt_v2,
            repo_root=repo_root,
            trusted_ed25519_public_key=ed_pub,
            trusted_mldsa65_public_key_pem=pq_pub_pem,
            min_accepted_counter=2,
        )

    # 5. Key environment mismatch (dev/test key used for prod verification) -> FAIL-CLOSED
    with pytest.raises(PermissionError, match="Key environment mismatch"):
        verify_hybrid_admission_receipt_v2(
            receipt_v2,
            repo_root=repo_root,
            trusted_ed25519_public_key=ed_pub,
            trusted_mldsa65_public_key_pem=pq_pub_pem,
            expected_key_environment="dev",
        )


def test_qf_m5_historical_checkpoint_preserved():
    """Verifies that build_check/qf_m5_signed_admission_receipt.json is preserved untouched as a v1 checkpoint."""
    import json
    from pathlib import Path
    from cryptography.hazmat.primitives import serialization
    from src.admission_receipt import DEFAULT_PUBLIC_KEY_PATH

    m5_path = Path(__file__).resolve().parent.parent / "build_check" / "qf_m5_signed_admission_receipt.json"
    assert m5_path.is_file()
    m5_receipt = json.loads(m5_path.read_text(encoding="utf-8"))
    assert m5_receipt["payload"]["schema"] == "qf.admission_receipt.v1"
    assert m5_receipt["payload"]["qf_m5_ceremony_boundary"]["ADMISSION_SIGNED"] is True
    pub_key = serialization.load_pem_public_key(DEFAULT_PUBLIC_KEY_PATH.read_bytes())
    assert verify_admission_receipt(m5_receipt, trusted_public_key=pub_key) is True


def test_qf_m6_b_offline_root_delegation_env_separation_and_krl_revocation(temp_git_repo, tmp_path):
    """
    Verifies QF-M6 Phase M6-B (`QF-KEY-01` Key Sovereignty):
      - Tier 0 Offline Root hybrid (Ed25519 + ML-DSA-65) delegation certificate issuance
      - Strict `dev` / `test` / `prod` environment separation
      - Conjunctive Root seal tamper detection
      - Root Key Revocation List (KRL) revocation and monotonic sequence anti-replay
    """
    import base64
    import copy
    from src.admission_receipt import (
        build_hybrid_admission_payload_v2,
        ensure_or_load_mldsa65_keypair,
        issue_key_delegation_certificate,
        issue_key_revocation_list,
        sign_hybrid_admission_receipt_v2,
        verify_hybrid_admission_receipt_v2,
    )

    repo_root, artifacts = temp_git_repo
    sbom_rel = "build_check/cbom_manifest.json"
    sbom_path = repo_root / sbom_rel
    sbom_path.parent.mkdir(parents=True, exist_ok=True)
    sbom_path.write_text('{"bomFormat":"CycloneDX","specVersion":"1.6"}\n', encoding="utf-8")

    # 1. Provision Tier 0 Offline Root Hybrid Keypair
    root_dir = tmp_path / "offline_root"
    root_ed_priv, root_ed_pub = ensure_or_load_release_keypair(
        root_dir / "qf_root_ed25519.key",
        root_dir / "qf_root_ed25519.pub.pem",
        auto_generate_if_missing=True,
    )
    root_pq_priv_path = root_dir / "qf_root_mldsa65.key"
    _, root_pq_pub_pem = ensure_or_load_mldsa65_keypair(
        root_pq_priv_path,
        root_dir / "qf_root_mldsa65.pub.pem",
        auto_generate_if_missing=True,
    )

    # 2. Provision Tier 1 Prod Release Hybrid Keypair
    rel_dir = tmp_path / "release_keys"
    rel_ed_priv, rel_ed_pub = ensure_or_load_release_keypair(
        rel_dir / "qf_rel_prod_ed25519.key",
        rel_dir / "qf_rel_prod_ed25519.pub.pem",
        auto_generate_if_missing=True,
    )
    rel_pq_priv_path = rel_dir / "qf_rel_prod_mldsa65.key"
    _, rel_pq_pub_pem = ensure_or_load_mldsa65_keypair(
        rel_pq_priv_path,
        rel_dir / "qf_rel_prod_mldsa65.pub.pem",
        auto_generate_if_missing=True,
    )

    # 3. Issue Root-Signed Delegation Certificate (`prod`) and KRL (`krl_sequence=1`)
    prod_cert = issue_key_delegation_certificate(
        cert_id="QF-CERT-PROD-2026-001",
        key_environment="prod",
        delegated_ed25519_public_key=rel_ed_pub,
        delegated_mldsa65_public_key_pem=rel_pq_pub_pem,
        root_ed25519_private_key=root_ed_priv,
        root_mldsa65_private_key_path=root_pq_priv_path,
        root_mldsa65_public_key_pem=root_pq_pub_pem,
        not_before_unix=1790000000,
        not_after_unix=1800000000,
    )
    krl_v1 = issue_key_revocation_list(
        krl_sequence=1,
        issued_at_unix=1793400000,
        root_ed25519_private_key=root_ed_priv,
        root_mldsa65_private_key_path=root_pq_priv_path,
        root_mldsa65_public_key_pem=root_pq_pub_pem,
    )

    payload_v2 = build_hybrid_admission_payload_v2(
        repo_root=repo_root,
        required_artifacts=artifacts,
        sbom_rel_path=sbom_rel,
        release_version="QF-M6.0.0",
        anti_rollback_counter=2,
        key_environment="prod",
        timestamp=1793405000,
    )
    signed_v2 = sign_hybrid_admission_receipt_v2(
        payload=payload_v2,
        ed25519_private_key=rel_ed_priv,
        mldsa65_private_key_path=rel_pq_priv_path,
        mldsa65_public_key_pem=rel_pq_pub_pem,
    )

    # Full Two-Tier Sovereign Chain Verification -> PASS
    assert verify_hybrid_admission_receipt_v2(
        signed_v2,
        repo_root=repo_root,
        min_accepted_counter=1,
        expected_key_environment="prod",
        delegation_cert=prod_cert,
        krl=krl_v1,
        trusted_root_ed25519_public_key=root_ed_pub,
        trusted_root_mldsa65_public_key_pem=root_pq_pub_pem,
        min_krl_sequence=1,
    ) is True

    # Environment Separation Violation: `dev` certificate cannot authorize a `prod` release
    dev_cert = issue_key_delegation_certificate(
        cert_id="QF-CERT-DEV-2026-001",
        key_environment="dev",
        delegated_ed25519_public_key=rel_ed_pub,
        delegated_mldsa65_public_key_pem=rel_pq_pub_pem,
        root_ed25519_private_key=root_ed_priv,
        root_mldsa65_private_key_path=root_pq_priv_path,
        root_mldsa65_public_key_pem=root_pq_pub_pem,
        not_before_unix=1790000000,
        not_after_unix=1800000000,
    )
    with pytest.raises(PermissionError, match="Delegated key environment"):
        verify_hybrid_admission_receipt_v2(
            signed_v2,
            repo_root=repo_root,
            min_accepted_counter=1,
            expected_key_environment="prod",
            delegation_cert=dev_cert,
            krl=krl_v1,
            trusted_root_ed25519_public_key=root_ed_pub,
            trusted_root_mldsa65_public_key_pem=root_pq_pub_pem,
        )

    # Root ML-DSA-65 Signature Tamper -> FAIL CLOSED
    bad_root_pq_cert = copy.deepcopy(prod_cert)
    sig_bytes = bytearray(base64.b64decode(bad_root_pq_cert["root_cryptographic_seal"]["root_mldsa65_signature_b64"]))
    sig_bytes[0] ^= 0xFF
    bad_root_pq_cert["root_cryptographic_seal"]["root_mldsa65_signature_b64"] = base64.b64encode(bytes(sig_bytes)).decode("ascii")
    with pytest.raises(PermissionError, match="Root ML-DSA-65 signature verification FAILED"):
        verify_hybrid_admission_receipt_v2(
            signed_v2,
            repo_root=repo_root,
            min_accepted_counter=1,
            expected_key_environment="prod",
            delegation_cert=bad_root_pq_cert,
            krl=krl_v1,
            trusted_root_ed25519_public_key=root_ed_pub,
            trusted_root_mldsa65_public_key_pem=root_pq_pub_pem,
        )

    # Emergency Key Revocation via Root KRL v2 -> FAIL CLOSED
    krl_v2_revoked = issue_key_revocation_list(
        krl_sequence=2,
        issued_at_unix=1793406000,
        root_ed25519_private_key=root_ed_priv,
        root_mldsa65_private_key_path=root_pq_priv_path,
        root_mldsa65_public_key_pem=root_pq_pub_pem,
        revoked_cert_ids=["QF-CERT-PROD-2026-001"],
    )
    with pytest.raises(PermissionError, match="REVOKED by Root KRL"):
        verify_hybrid_admission_receipt_v2(
            signed_v2,
            repo_root=repo_root,
            min_accepted_counter=1,
            expected_key_environment="prod",
            delegation_cert=prod_cert,
            krl=krl_v2_revoked,
            trusted_root_ed25519_public_key=root_ed_pub,
            trusted_root_mldsa65_public_key_pem=root_pq_pub_pem,
            min_krl_sequence=2,
        )

    # Stale KRL Replay (`krl_v1` when `min_krl_sequence=2`) -> FAIL CLOSED
    with pytest.raises(PermissionError, match="Stale KRL sequence"):
        verify_hybrid_admission_receipt_v2(
            signed_v2,
            repo_root=repo_root,
            min_accepted_counter=1,
            expected_key_environment="prod",
            delegation_cert=prod_cert,
            krl=krl_v1,
            trusted_root_ed25519_public_key=root_ed_pub,
            trusted_root_mldsa65_public_key_pem=root_pq_pub_pem,
            min_krl_sequence=2,
        )


def test_qf_m6_c_supply_chain_integrity_and_adversarial_tamper_matrix(temp_git_repo, tmp_path):
    """
    QF-RELEASE-01 / Phase M6-C Supply-Chain Integrity & Adversarial Tamper Matrix:
      TV-M6C-01: Nominal full conjunctive chain (Root + KRL + Repro Build + CycloneDX SBOM/CBOM + SLSA v1.0) -> PASS
      TV-M6C-02: Reproducible build divergence (1 byte difference) -> FAIL-CLOSED
      TV-M6C-03: Incomplete supply-chain evidence -> FAIL-CLOSED
      TV-M6C-04: in-toto subject digest substitution -> FAIL-CLOSED
      TV-M6C-05: SLSA provenance parameter / commit replay -> FAIL-CLOSED
      TV-M6C-06: SLSA ML-DSA-65 signature tamper -> FAIL-CLOSED
      TV-M6C-07: CycloneDX manifest root mismatch -> FAIL-CLOSED
      TV-M6C-08: CycloneDX Ed25519 signature tamper -> FAIL-CLOSED
    """
    import base64
    import copy
    import shutil
    from src.admission_receipt import (
        build_hybrid_admission_payload_v2,
        build_signed_cyclonedx_16_inventories,
        build_signed_slsa_provenance_v1,
        ensure_or_load_mldsa65_keypair,
        issue_key_delegation_certificate,
        issue_key_revocation_list,
        sign_hybrid_admission_receipt_v2,
        verify_hybrid_admission_receipt_v2,
        verify_reproducible_build_artifacts,
        verify_signed_cyclonedx_16_inventory,
        verify_signed_slsa_provenance_v1,
    )

    repo_root, artifacts = temp_git_repo

    # 1. Setup Independent Clean-Room Rebuild Tree
    rebuild_root = tmp_path / "clean_room_rebuild"
    rebuild_root.mkdir(parents=True, exist_ok=True)
    for rel_path in artifacts:
        dest = rebuild_root / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo_root / rel_path, dest)

    # 2. Provision Tier 0 Offline Root & Tier 1 Prod Keys
    root_dir = tmp_path / "offline_root"
    root_ed_priv, root_ed_pub = ensure_or_load_release_keypair(
        root_dir / "root_ed.key",
        root_dir / "root_ed.pub.pem",
        auto_generate_if_missing=True,
    )
    root_pq_priv = root_dir / "root_pq.key"
    _, root_pq_pub_pem = ensure_or_load_mldsa65_keypair(
        root_pq_priv,
        root_dir / "root_pq.pub.pem",
        auto_generate_if_missing=True,
    )

    rel_dir = tmp_path / "release_keys"
    rel_ed_priv, rel_ed_pub = ensure_or_load_release_keypair(
        rel_dir / "rel_ed.key",
        rel_dir / "rel_ed.pub.pem",
        auto_generate_if_missing=True,
    )
    rel_pq_priv = rel_dir / "rel_pq.key"
    _, rel_pq_pub_pem = ensure_or_load_mldsa65_keypair(
        rel_pq_priv,
        rel_dir / "rel_pq.pub.pem",
        auto_generate_if_missing=True,
    )

    prod_cert = issue_key_delegation_certificate(
        cert_id="QF-CERT-PROD-2026-002",
        key_environment="prod",
        delegated_ed25519_public_key=rel_ed_pub,
        delegated_mldsa65_public_key_pem=rel_pq_pub_pem,
        root_ed25519_private_key=root_ed_priv,
        root_mldsa65_private_key_path=root_pq_priv,
        root_mldsa65_public_key_pem=root_pq_pub_pem,
        not_before_unix=1790000000,
        not_after_unix=1800000000,
    )
    krl = issue_key_revocation_list(
        krl_sequence=1,
        issued_at_unix=1793400000,
        root_ed25519_private_key=root_ed_priv,
        root_mldsa65_private_key_path=root_pq_priv,
        root_mldsa65_public_key_pem=root_pq_pub_pem,
    )

    # 3. Build CycloneDX 1.6 SBOM and CBOM
    sbom_path = repo_root / "build_check" / "cyclonedx_sbom.json"
    cbom_path = repo_root / "build_check" / "cyclonedx_cbom.json"
    slsa_path = repo_root / "build_check" / "slsa_provenance.json"
    sbom_path.parent.mkdir(parents=True, exist_ok=True)
    sbom_path.write_text('{"placeholder": "sbom"}\n', encoding="utf-8")
    cbom_path.write_text('{"placeholder": "cbom"}\n', encoding="utf-8")
    slsa_path.write_text('{"placeholder": "slsa"}\n', encoding="utf-8")

    initial_payload = build_hybrid_admission_payload_v2(
        repo_root=repo_root,
        required_artifacts=artifacts,
        release_version="QF-M6.0.0",
        anti_rollback_counter=3,
        key_environment="prod",
        sbom_rel_path="build_check/cyclonedx_sbom.json",
        cbom_rel_path="build_check/cyclonedx_cbom.json",
        slsa_provenance_rel_path="build_check/slsa_provenance.json",
        reproducible_build_verified=True,
        timestamp=1793405000,
    )

    signed_sbom, signed_cbom = build_signed_cyclonedx_16_inventories(
        repo_root=repo_root,
        artifact_sha256=initial_payload["artifact_sha256"],
        artifact_sha384=initial_payload["artifact_sha384"],
        release_version=initial_payload["release_version"],
        git_commit=initial_payload["git_commit"],
        ed25519_private_key=rel_ed_priv,
        mldsa65_private_key_path=rel_pq_priv,
        mldsa65_public_key_pem=rel_pq_pub_pem,
    )
    import json
    sbom_path.write_text(json.dumps(signed_sbom, indent=2), encoding="utf-8")
    cbom_path.write_text(json.dumps(signed_cbom, indent=2), encoding="utf-8")

    signed_slsa = build_signed_slsa_provenance_v1(
        payload_v2=initial_payload,
        ed25519_private_key=rel_ed_priv,
        mldsa65_private_key_path=rel_pq_priv,
        mldsa65_public_key_pem=rel_pq_pub_pem,
        reproducible_build_verified=True,
    )
    slsa_path.write_text(json.dumps(signed_slsa, indent=2), encoding="utf-8")

    # Re-compute payload now that files on disk contain actual signed contents
    final_payload = build_hybrid_admission_payload_v2(
        repo_root=repo_root,
        required_artifacts=artifacts,
        release_version="QF-M6.0.0",
        anti_rollback_counter=3,
        key_environment="prod",
        sbom_rel_path="build_check/cyclonedx_sbom.json",
        cbom_rel_path="build_check/cyclonedx_cbom.json",
        slsa_provenance_rel_path="build_check/slsa_provenance.json",
        reproducible_build_verified=True,
        timestamp=1793405000,
    )
    signed_receipt = sign_hybrid_admission_receipt_v2(
        payload=final_payload,
        ed25519_private_key=rel_ed_priv,
        mldsa65_private_key_path=rel_pq_priv,
        mldsa65_public_key_pem=rel_pq_pub_pem,
    )

    # TV-M6C-01: Nominal Full Conjunctive Admission
    assert verify_hybrid_admission_receipt_v2(
        signed_receipt,
        repo_root=repo_root,
        min_accepted_counter=2,
        expected_key_environment="prod",
        delegation_cert=prod_cert,
        krl=krl,
        trusted_root_ed25519_public_key=root_ed_pub,
        trusted_root_mldsa65_public_key_pem=root_pq_pub_pem,
        min_krl_sequence=1,
        enforce_supply_chain_integrity=True,
        slsa_provenance=signed_slsa,
        signed_sbom=signed_sbom,
        signed_cbom=signed_cbom,
        rebuild_repo_root=rebuild_root,
    ) is True

    # TV-M6C-02: Reproducible Build Divergence (1 byte altered in clean-room rebuild)
    tampered_rebuild_file = rebuild_root / artifacts[0]
    tampered_rebuild_file.write_bytes(tampered_rebuild_file.read_bytes() + b"\x00")
    with pytest.raises(PermissionError, match="Reproducible build verification FAILED"):
        verify_hybrid_admission_receipt_v2(
            signed_receipt,
            repo_root=repo_root,
            min_accepted_counter=2,
            expected_key_environment="prod",
            delegation_cert=prod_cert,
            krl=krl,
            trusted_root_ed25519_public_key=root_ed_pub,
            trusted_root_mldsa65_public_key_pem=root_pq_pub_pem,
            enforce_supply_chain_integrity=True,
            slsa_provenance=signed_slsa,
            signed_sbom=signed_sbom,
            signed_cbom=signed_cbom,
            rebuild_repo_root=rebuild_root,
        )
    # Restore clean rebuild artifact
    shutil.copy2(repo_root / artifacts[0], rebuild_root / artifacts[0])

    # TV-M6C-03: Missing Supply-Chain Evidence when enforce_supply_chain_integrity=True
    with pytest.raises(PermissionError, match="Incomplete supply-chain evidence"):
        verify_hybrid_admission_receipt_v2(
            signed_receipt,
            repo_root=repo_root,
            min_accepted_counter=2,
            expected_key_environment="prod",
            delegation_cert=prod_cert,
            krl=krl,
            trusted_root_ed25519_public_key=root_ed_pub,
            trusted_root_mldsa65_public_key_pem=root_pq_pub_pem,
            enforce_supply_chain_integrity=True,
            slsa_provenance=None,
            signed_sbom=signed_sbom,
            signed_cbom=signed_cbom,
            rebuild_repo_root=rebuild_root,
        )

    # TV-M6C-04: in-toto Subject Digest Substitution
    bad_slsa_payload = copy.deepcopy(final_payload)
    bad_slsa_payload["artifact_sha256"][artifacts[0]] = "0" * 64
    bad_slsa = build_signed_slsa_provenance_v1(
        payload_v2=bad_slsa_payload,
        ed25519_private_key=rel_ed_priv,
        mldsa65_private_key_path=rel_pq_priv,
        mldsa65_public_key_pem=rel_pq_pub_pem,
        reproducible_build_verified=True,
    )
    with pytest.raises(PermissionError, match="SLSA subject digest mismatch"):
        verify_signed_slsa_provenance_v1(
            signed_envelope=bad_slsa,
            receipt_payload=final_payload,
            trusted_ed25519_public_key=rel_ed_pub,
            trusted_mldsa65_public_key_pem=rel_pq_pub_pem,
        )

    # TV-M6C-05: SLSA Provenance Parameter / Commit Replay
    replay_slsa_payload = copy.deepcopy(final_payload)
    replay_slsa_payload["anti_rollback_counter"] = 2  # Replay older counter
    replayed_slsa = build_signed_slsa_provenance_v1(
        payload_v2=replay_slsa_payload,
        ed25519_private_key=rel_ed_priv,
        mldsa65_private_key_path=rel_pq_priv,
        mldsa65_public_key_pem=rel_pq_pub_pem,
        reproducible_build_verified=True,
    )
    with pytest.raises(PermissionError, match="SLSA provenance parameter mismatch: anti_rollback_counter"):
        verify_signed_slsa_provenance_v1(
            signed_envelope=replayed_slsa,
            receipt_payload=final_payload,
            trusted_ed25519_public_key=rel_ed_pub,
            trusted_mldsa65_public_key_pem=rel_pq_pub_pem,
        )

    # TV-M6C-06: SLSA ML-DSA-65 Signature Tamper
    bad_pq_slsa = copy.deepcopy(signed_slsa)
    pq_sig_bytes = bytearray(base64.b64decode(bad_pq_slsa["cryptographic_seal"]["ml_dsa_65"]["signature_b64"]))
    pq_sig_bytes[0] ^= 0xFF
    bad_pq_slsa["cryptographic_seal"]["ml_dsa_65"]["signature_b64"] = base64.b64encode(bytes(pq_sig_bytes)).decode("ascii")
    with pytest.raises(PermissionError, match="ML-DSA-65 signature verification FAILED"):
        verify_signed_slsa_provenance_v1(
            signed_envelope=bad_pq_slsa,
            receipt_payload=final_payload,
            trusted_ed25519_public_key=rel_ed_pub,
            trusted_mldsa65_public_key_pem=rel_pq_pub_pem,
        )

    # TV-M6C-07: CycloneDX Manifest Root Mismatch
    with pytest.raises(PermissionError, match="CycloneDX inventory manifest_root_sha256 mismatch"):
        verify_signed_cyclonedx_16_inventory(
            signed_envelope=signed_sbom,
            trusted_ed25519_public_key=rel_ed_pub,
            trusted_mldsa65_public_key_pem=rel_pq_pub_pem,
            expected_manifest_root_sha256="1" * 64,
            expected_manifest_root_sha384=final_payload["manifest_root_sha384"],
        )

    # TV-M6C-08: CycloneDX Ed25519 Signature Tamper
    bad_ed_cbom = copy.deepcopy(signed_cbom)
    ed_sig_bytes = bytearray(base64.b64decode(bad_ed_cbom["cryptographic_seal"]["ed25519"]["signature_b64"]))
    ed_sig_bytes[0] ^= 0xFF
    bad_ed_cbom["cryptographic_seal"]["ed25519"]["signature_b64"] = base64.b64encode(bytes(ed_sig_bytes)).decode("ascii")
    with pytest.raises(PermissionError, match="Ed25519 signature verification FAILED"):
        verify_signed_cyclonedx_16_inventory(
            signed_envelope=bad_ed_cbom,
            trusted_ed25519_public_key=rel_ed_pub,
            trusted_mldsa65_public_key_pem=rel_pq_pub_pem,
        )


