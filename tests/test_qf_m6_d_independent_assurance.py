# tests/test_qf_m6_d_independent_assurance.py
"""
Verification Suite for Milestone QF-M6-D:
Independent Assurance, Key-Compromise Recovery Drills & Sovereign Economic Return Gates (M6-01 .. M6-07).
Controls: QF-KEY-01, QF-RELEASE-01, QF-CAPITAL-01, QF-OPS-01.
"""

from __future__ import annotations

import base64
import copy
import subprocess
from pathlib import Path
from typing import Any, Dict

import pytest

from src.admission_receipt import (
    build_hybrid_admission_payload_v2,
    build_signed_cyclonedx_16_inventories,
    build_signed_slsa_provenance_v1,
    ensure_or_load_mldsa65_keypair,
    ensure_or_load_release_keypair,
    issue_key_delegation_certificate,
    issue_key_revocation_list,
    sign_hybrid_admission_receipt_v2,
    verify_hybrid_admission_receipt_v2,
)
from src.bounty_assurance import (
    BountyGateError,
    evaluate_qf_m6_economic_return_gates,
)


@pytest.fixture()
def m6d_git_repo(tmp_path):
    """Creates a deterministic repository tree for M6-D verification testing."""
    repo_dir = tmp_path / "repo"
    subprocess.run(["git", "init", str(repo_dir)], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "-C", str(repo_dir), "config", "user.email", "rock@quantumflex.local"], check=True)
    subprocess.run(["git", "-C", str(repo_dir), "config", "user.name", "Rocky"], check=True)

    artifacts = ["src/privacy_filter.py", "mcp_layer/circuit_breaker.py"]
    for rel in artifacts:
        p = repo_dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# verified sovereign content for {rel}\n", encoding="utf-8")

    subprocess.run(["git", "-C", str(repo_dir), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo_dir), "commit", "-m", "sovereign release commit"], check=True, stdout=subprocess.DEVNULL)
    return repo_dir, artifacts


# ==============================================================================
# SECTION 1: Key-Compromise Recovery Drill (QF-KEY-01 & QF-RELEASE-01)
# ==============================================================================


def test_key_compromise_emergency_revocation_and_re_delegation_drill(m6d_git_repo, tmp_path):
    """
    QF-KEY-01 / QF-M6-D: Key-Compromise Recovery Drill.
    Simulates:
      1. Active Tier 1 Prod Key (Keypair A) signs a valid release under Delegation Cert 001.
      2. Compromise of Keypair A is detected.
      3. Tier 0 Offline Root executes emergency revocation ceremony:
         - Issues monotonic KRL (krl_sequence=2) revoking Cert 001.
      4. Verifier fails closed on any release signed with compromised Keypair A.
      5. Tier 0 Offline Root provisions new Tier 1 Prod Key (Keypair B) and issues Delegation Cert 002.
      6. Verifier admits release signed with new Keypair B under Cert 002 and KRL sequence 2.
    """
    repo_root, artifacts = m6d_git_repo

    # Step 1: Provision Tier 0 Offline Root Hybrid Keypair
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

    # Step 2: Provision Initial Tier 1 Prod Keypair A
    rel_a_dir = tmp_path / "release_keys_a"
    rel_a_ed_priv, rel_a_ed_pub = ensure_or_load_release_keypair(
        rel_a_dir / "qf_rel_a_ed25519.key",
        rel_a_dir / "qf_rel_a_ed25519.pub.pem",
        auto_generate_if_missing=True,
    )
    rel_a_pq_priv_path = rel_a_dir / "qf_rel_a_mldsa65.key"
    _, rel_a_pq_pub_pem = ensure_or_load_mldsa65_keypair(
        rel_a_pq_priv_path,
        rel_a_dir / "qf_rel_a_mldsa65.pub.pem",
        auto_generate_if_missing=True,
    )

    # Issue Initial Delegation Certificate 001 and KRL v1
    cert_a = issue_key_delegation_certificate(
        cert_id="QF-CERT-PROD-2026-001",
        key_environment="prod",
        delegated_ed25519_public_key=rel_a_ed_pub,
        delegated_mldsa65_public_key_pem=rel_a_pq_pub_pem,
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

    # Build and sign release with Keypair A
    sbom_rel = "build_check/cbom_manifest.json"
    sbom_path = repo_root / sbom_rel
    sbom_path.parent.mkdir(parents=True, exist_ok=True)
    sbom_path.write_text('{"bomFormat":"CycloneDX","specVersion":"1.6"}\n', encoding="utf-8")

    payload_a = build_hybrid_admission_payload_v2(
        repo_root=repo_root,
        required_artifacts=artifacts,
        sbom_rel_path=sbom_rel,
        release_version="QF-M6.0.0",
        anti_rollback_counter=2,
        key_environment="prod",
        timestamp=1793401000,
    )
    receipt_a = sign_hybrid_admission_receipt_v2(
        payload=payload_a,
        ed25519_private_key=rel_a_ed_priv,
        mldsa65_private_key_path=rel_a_pq_priv_path,
        mldsa65_public_key_pem=rel_a_pq_pub_pem,
    )

    # Pre-compromise: Keypair A passes verification
    assert verify_hybrid_admission_receipt_v2(
        receipt_a,
        repo_root=repo_root,
        min_accepted_counter=1,
        expected_key_environment="prod",
        delegation_cert=cert_a,
        krl=krl_v1,
        trusted_root_ed25519_public_key=root_ed_pub,
        trusted_root_mldsa65_public_key_pem=root_pq_pub_pem,
        min_krl_sequence=1,
    ) is True

    # =========================================================================
    # COMPROMISE DETECTED: Execute Step 1 (Issue Monotonic KRL v2)
    # =========================================================================
    krl_v2 = issue_key_revocation_list(
        krl_sequence=2,
        issued_at_unix=1793402000,
        root_ed25519_private_key=root_ed_priv,
        root_mldsa65_private_key_path=root_pq_priv_path,
        root_mldsa65_public_key_pem=root_pq_pub_pem,
        revoked_cert_ids=["QF-CERT-PROD-2026-001"],
    )

    # Verifier MUST fail closed on receipt_a with KRL v2
    with pytest.raises(PermissionError, match="REVOKED by Root KRL"):
        verify_hybrid_admission_receipt_v2(
            receipt_a,
            repo_root=repo_root,
            min_accepted_counter=1,
            expected_key_environment="prod",
            delegation_cert=cert_a,
            krl=krl_v2,
            trusted_root_ed25519_public_key=root_ed_pub,
            trusted_root_mldsa65_public_key_pem=root_pq_pub_pem,
            min_krl_sequence=2,
        )

    # Anti-rollback on KRL: Trying to present stale krl_v1 when min_krl_sequence=2 fails closed
    with pytest.raises(PermissionError, match="Stale KRL sequence"):
        verify_hybrid_admission_receipt_v2(
            receipt_a,
            repo_root=repo_root,
            min_accepted_counter=1,
            expected_key_environment="prod",
            delegation_cert=cert_a,
            krl=krl_v1,
            trusted_root_ed25519_public_key=root_ed_pub,
            trusted_root_mldsa65_public_key_pem=root_pq_pub_pem,
            min_krl_sequence=2,
        )

    # =========================================================================
    # RECOVERY DRILL: Step 2 & 3 (Provision Keypair B & Re-delegate Cert 002)
    # =========================================================================
    rel_b_dir = tmp_path / "release_keys_b"
    rel_b_ed_priv, rel_b_ed_pub = ensure_or_load_release_keypair(
        rel_b_dir / "qf_rel_b_ed25519.key",
        rel_b_dir / "qf_rel_b_ed25519.pub.pem",
        auto_generate_if_missing=True,
    )
    rel_b_pq_priv_path = rel_b_dir / "qf_rel_b_mldsa65.key"
    _, rel_b_pq_pub_pem = ensure_or_load_mldsa65_keypair(
        rel_b_pq_priv_path,
        rel_b_dir / "qf_rel_b_mldsa65.pub.pem",
        auto_generate_if_missing=True,
    )

    cert_b = issue_key_delegation_certificate(
        cert_id="QF-CERT-PROD-2026-002",
        key_environment="prod",
        delegated_ed25519_public_key=rel_b_ed_pub,
        delegated_mldsa65_public_key_pem=rel_b_pq_pub_pem,
        root_ed25519_private_key=root_ed_priv,
        root_mldsa65_private_key_path=root_pq_priv_path,
        root_mldsa65_public_key_pem=root_pq_pub_pem,
        not_before_unix=1790000000,
        not_after_unix=1800000000,
    )

    # Build and sign fresh release with Keypair B (counter incremented to 3)
    payload_b = build_hybrid_admission_payload_v2(
        repo_root=repo_root,
        required_artifacts=artifacts,
        sbom_rel_path=sbom_rel,
        release_version="QF-M6.0.1",
        anti_rollback_counter=3,
        key_environment="prod",
        timestamp=1793403000,
    )
    receipt_b = sign_hybrid_admission_receipt_v2(
        payload=payload_b,
        ed25519_private_key=rel_b_ed_priv,
        mldsa65_private_key_path=rel_b_pq_priv_path,
        mldsa65_public_key_pem=rel_b_pq_pub_pem,
    )

    # Step 4: Verification under new KRL v2 and new Cert B passes cleanly
    assert verify_hybrid_admission_receipt_v2(
        receipt_b,
        repo_root=repo_root,
        min_accepted_counter=2,
        expected_key_environment="prod",
        delegation_cert=cert_b,
        krl=krl_v2,
        trusted_root_ed25519_public_key=root_ed_pub,
        trusted_root_mldsa65_public_key_pem=root_pq_pub_pem,
        min_krl_sequence=2,
    ) is True


# ==============================================================================
# SECTION 2: Sovereign Economic Return Gates (M6-01 .. M6-07)
# ==============================================================================


def test_qf_m6_d_nominal_settled_bug_bounty_admission():
    """
    M6-01..M6-07 Nominal Case:
      - Pillar 1 Bug Bounty proof on Immunefi.
      - 100% offline reproducible finding.
      - Independent evidence verified.
      - Compliant submission approved by Operator.
      - Confirmed $25,000 award.
      - Settled via on-chain USDC (Base Mainnet).
      - Liquid reserves > 6 months.
    Expectation:
      - Full admission admitted.
      - 30% tax reserve ($7,500) set aside.
      - 70% ($17,500) routed to reserve reinvestment.
      - Unsettled capital flag is False.
    """
    res = evaluate_qf_m6_economic_return_gates(
        mission_slot=1,
        pillar="PILLAR_1_BUG_BOUNTY_PROOF",
        target_scope="Immunefi / Circle Perimeter Smart Contracts",
        local_reproducible=True,
        evidence_verified=True,
        compliant_submission=True,
        human_authorized=True,
        human_authorizer_id="rahshaun_chambers",
        award_confirmed=True,
        award_amount_usd=25000.00,
        funds_settled=True,
        settlement_network_or_method="BASE_MAINNET_USDC",
        settlement_tx_hash_or_ref="0x4d5a9b1c2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b",
        current_liquid_reserves_usd=41729.83,
        monthly_obligations_usd=3975.00,
        tax_reserve_rate=0.30,
    )

    assert res["m6_economic_return_admitted"] is True
    assert res["gates"]["M6-01_authorized_target"] == "PASS"
    assert res["gates"]["M6-02_local_reproducible"] == "PASS"
    assert res["gates"]["M6-03_evidence_verified"] == "PASS"
    assert res["gates"]["M6-04_compliant_submission"] == "PASS"
    assert res["gates"]["M6-05_verified_award"] == "PASS"
    assert res["gates"]["M6-06_settled_funds_reconciled"] == "PASS"
    assert "PASS" in res["gates"]["M6-07_reserve_protected"]

    recon = res["financial_reconciliation"]
    assert recon["gross_settled_award_usd"] == 25000.00
    assert recon["tax_reserve_set_aside_usd"] == 7500.00
    assert recon["net_routed_to_reserve_reinvestment_usd"] == 17500.00
    assert recon["prior_liquid_reserves_usd"] == 41729.83
    assert recon["post_settlement_liquid_reserves_usd"] == 59229.83
    assert recon["reserve_coverage_months"] == round(59229.83 / 3975.00, 2)
    assert recon["unsettled_award_counted_as_income"] is False


def test_qf_m6_d_unsettled_award_fails_closed_gate_m6_06():
    """
    CRITICAL INVARIANT: Unsettled awards or anticipated grants must NEVER count as realized income.
    Gate M6-06 must fail closed if funds_settled=False.
    """
    with pytest.raises(BountyGateError, match="M6-06 FAIL: unsettled awards cannot be recognized"):
        evaluate_qf_m6_economic_return_gates(
            mission_slot=2,
            pillar="PILLAR_2_PUBLIC_GOOD_GRANT",
            target_scope="NLnet NGI Zero Entrust",
            local_reproducible=True,
            evidence_verified=True,
            compliant_submission=True,
            human_authorized=True,
            human_authorizer_id="rocky",
            award_confirmed=True,
            award_amount_usd=50000.00,
            funds_settled=False,  # Unsettled grant
            settlement_network_or_method="PENDING_SEPA",
            settlement_tx_hash_or_ref="PENDING_TRANSFER",
            current_liquid_reserves_usd=41729.83,
            monthly_obligations_usd=3975.00,
        )


def test_qf_m6_d_reserve_coverage_breach_fails_closed_gate_m6_07():
    """
    Gate M6-07: Liquid reserve coverage must be at least 6 months (R >= 6O).
    If prior liquid reserves do not meet 6 * monthly_obligations_usd, fail closed.
    """
    with pytest.raises(BountyGateError, match="M6-07 FAIL: reserve coverage breach"):
        evaluate_qf_m6_economic_return_gates(
            mission_slot=1,
            pillar="PILLAR_1_BUG_BOUNTY_PROOF",
            target_scope="Code4rena Audit Contest",
            local_reproducible=True,
            evidence_verified=True,
            compliant_submission=True,
            human_authorized=True,
            human_authorizer_id="rahshaun_chambers",
            award_confirmed=True,
            award_amount_usd=10000.00,
            funds_settled=True,
            settlement_network_or_method="BASE_MAINNET_USDC",
            settlement_tx_hash_or_ref="0xabc123...",
            current_liquid_reserves_usd=15000.00,  # Less than 6 * 3975 = 23,850.00
            monthly_obligations_usd=3975.00,
        )


def test_qf_m6_d_unauthorized_scope_fails_closed_gate_m6_01():
    """Gate M6-01: Invalid mission slot or pillar or empty scope must fail closed."""
    with pytest.raises(BountyGateError, match="M6-01 FAIL: invalid mission_slot"):
        evaluate_qf_m6_economic_return_gates(
            mission_slot=4,  # Out of range 1..3
            pillar="PILLAR_1_BUG_BOUNTY_PROOF",
            target_scope="Authorized Scope",
            local_reproducible=True,
            evidence_verified=True,
            compliant_submission=True,
            human_authorized=True,
            human_authorizer_id="rahshaun_chambers",
            award_confirmed=True,
            award_amount_usd=10000.00,
            funds_settled=True,
            settlement_network_or_method="BASE_MAINNET_USDC",
            settlement_tx_hash_or_ref="0x123",
            current_liquid_reserves_usd=40000.00,
            monthly_obligations_usd=3975.00,
        )

    with pytest.raises(BountyGateError, match="M6-01 FAIL: target_scope cannot be empty"):
        evaluate_qf_m6_economic_return_gates(
            mission_slot=1,
            pillar="PILLAR_1_BUG_BOUNTY_PROOF",
            target_scope="   ",  # Blank
            local_reproducible=True,
            evidence_verified=True,
            compliant_submission=True,
            human_authorized=True,
            human_authorizer_id="rahshaun_chambers",
            award_confirmed=True,
            award_amount_usd=10000.00,
            funds_settled=True,
            settlement_network_or_method="BASE_MAINNET_USDC",
            settlement_tx_hash_or_ref="0x123",
            current_liquid_reserves_usd=40000.00,
            monthly_obligations_usd=3975.00,
        )


def test_qf_m6_d_live_exploitation_fails_closed_gate_m6_02():
    """Gate M6-02: Live target execution without local reproduction fails closed."""
    with pytest.raises(BountyGateError, match="M6-02 FAIL: local reproducible finding required"):
        evaluate_qf_m6_economic_return_gates(
            mission_slot=1,
            pillar="PILLAR_1_BUG_BOUNTY_PROOF",
            target_scope="Immunefi / Compound V3",
            local_reproducible=False,  # Attempted live exploitation
            evidence_verified=True,
            compliant_submission=True,
            human_authorized=True,
            human_authorizer_id="rahshaun_chambers",
            award_confirmed=True,
            award_amount_usd=10000.00,
            funds_settled=True,
            settlement_network_or_method="BASE_MAINNET_USDC",
            settlement_tx_hash_or_ref="0x123",
            current_liquid_reserves_usd=40000.00,
            monthly_obligations_usd=3975.00,
        )


def test_qf_m6_d_unauthorized_human_approver_fails_closed_gate_m6_04():
    """Gate M6-04: Non-operator human authorizer fails closed."""
    with pytest.raises(BountyGateError, match="M6-04 FAIL: authorizer 'mallory' not in authorized Operator list"):
        evaluate_qf_m6_economic_return_gates(
            mission_slot=1,
            pillar="PILLAR_1_BUG_BOUNTY_PROOF",
            target_scope="Immunefi",
            local_reproducible=True,
            evidence_verified=True,
            compliant_submission=True,
            human_authorized=True,
            human_authorizer_id="mallory",  # Rogue identity
            award_confirmed=True,
            award_amount_usd=10000.00,
            funds_settled=True,
            settlement_network_or_method="BASE_MAINNET_USDC",
            settlement_tx_hash_or_ref="0x123",
            current_liquid_reserves_usd=40000.00,
            monthly_obligations_usd=3975.00,
        )
