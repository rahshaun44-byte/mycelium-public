"""
Verification Suite for Milestone QF-M5.1 (Track 0 Reserve Reconciliation & Guarded QF-A5 Boundary)
and QF-SOVEREIGN-BOUNTY Assurance Gates (QF-BOUNTY-01..03 & Technical Corrections A–D).
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import subprocess
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Tuple

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from scripts.generate_research_dossier import PrivacyFilter, SecurityBoundaryError
from scripts.prepare_qf_a5_ceremony import (
    REQUIRED_CONFIRMATION_PHRASE,
    build_qf_a5_preflight_manifest,
    execute_guarded_qf_a5_ceremony,
)
from scripts.reconcile_track0_reserves import (
    Track0ValidationError,
    build_unreconciled_status_snapshot,
    load_private_worksheet,
    reconcile_track0_worksheet,
)
from src.admission_receipt import ensure_or_load_release_keypair, verify_admission_receipt
from src.bounty_assurance import (
    BountyGateError,
    SignerAttestation,
    assess_contextual_severity,
    build_two_person_signing_payload,
    derive_contextual_idempotency_key,
    evaluate_qf_bounty_01_authorization,
    evaluate_qf_bounty_02_evidence,
    evaluate_qf_bounty_03_disclosure,
    evaluate_sovereign_bounty_gates,
    verify_token_decimal_precision,
    verify_two_person_authorization,
)


def _sample_worksheet(
    *,
    checking: float = 18423.17,
    savings: float = 12306.66,
    tbills: float = 11000.00,
    pending_bounties: float = 75000.00,
    anticipated_grants: float = 35000.00,
    speculative: float = 42000.00,
    debt_monthly: float = 1189.47,
    living_monthly: float = 2785.53,
    cloud_llm_spend: float = 0.0,
    llc_overhead: float = 0.0,
    reconciled_at_utc: str = "2026-10-30T22:00:00Z",
) -> Dict[str, Any]:
    return {
        "schema": "qf.track0_worksheet.v1",
        "reconciled_at_utc": reconciled_at_utc,
        "operator_attestation": {
            "operator_id": "rahshaun_chambers",
            "operator_attested": True,
            "statements_verified_against_primary_institutions": True,
            "pending_awards_and_speculative_assets_excluded": True,
        },
        "verified_liquid_accounts_usd": {
            "checking_fdic": checking,
            "savings_or_money_market_fdic": savings,
            "settled_short_term_tbills": tbills,
        },
        "excluded_non_reserve_items_usd": {
            "pending_bounties": pending_bounties,
            "anticipated_grants": anticipated_grants,
            "speculative_or_illiquid_assets": speculative,
        },
        "outstanding_debts": [
            {
                "name": "primary_housing_note",
                "principal_balance_usd": 149281.55,
                "monthly_payment_usd": debt_monthly,
            }
        ],
        "monthly_household_living_expenses_usd": {
            "housing_non_debt": 450.00,
            "utilities_and_connectivity": 310.00,
            "groceries_and_essentials": 925.53,
            "healthcare_and_insurance": 500.00,
            "transportation": 300.00,
            "family_and_contingency": living_monthly - 2485.53,
        },
        "committed_quantumflex_operating_expenses_usd": {
            "external_cloud_llm_spend": cloud_llm_spend,
            "corporate_llc_overhead": llc_overhead,
            "local_compute_electricity": 10.00,
            "network_and_hardware_reserve": 15.00,
        },
    }


# ==============================================================================
# Part 1: Milestone QF-M5.1 — Track 0 Reserve Reconciliation & QF-A5 Boundary
# ==============================================================================
def test_unreconciled_track0_snapshot_preserves_exact_boundary():
    snap = build_unreconciled_status_snapshot()
    boundary = snap["cryptographic_boundary"]
    assert boundary["HS-PX"] == "CLOSED"
    assert boundary["AS-01..03"] == "CLOSED"
    assert boundary["PA-LLC"] == "RETIRED"
    assert boundary["TRACK_0"] == "OPEN"
    assert boundary["PERSONAL_HARD_STOPS_CLEARED"] is False
    assert boundary["ALL_HARD_STOPS"] is False
    assert boundary["QF_A5_SIGNING"] == "GATED"
    assert boundary["ADMISSION_SIGNED"] is False


def test_track0_private_file_permissions_enforced(tmp_path: Path):
    ws_path = tmp_path / "private_ws.json"
    ws_path.write_text(json.dumps(_sample_worksheet()), encoding="utf-8")
    ws_path.chmod(0o644)
    with pytest.raises(PermissionError, match="expected 0o600"):
        load_private_worksheet(ws_path)

    ws_path.chmod(0o600)
    loaded = load_private_worksheet(ws_path)
    assert loaded["schema"] == "qf.track0_worksheet.v1"


def test_track0_reconciliation_omits_all_raw_dollars_and_keeps_signing_false():
    now = dt.datetime(2026, 10, 31, 2, 30, tzinfo=dt.timezone.utc)
    # Total liquid = 18423.17 + 12306.66 + 11000.00 = 41729.83
    # Monthly O = 1189.47 (debt) + 2785.53 (living) + 25.00 (operating) = 4000.00
    # Coverage = 41729.83 / 4000.00 = 10.4324575 -> 10.43 months (>= 6.0)
    ws = _sample_worksheet()
    receipt = reconcile_track0_worksheet(ws, reference_now_utc=now)

    assert receipt["raw_dollar_figures_omitted"] is True
    assert receipt["track_0_gate"]["status"] == "CLOSED"
    assert receipt["track_0_gate"]["invariant_satisfied"] is True
    assert receipt["track_0_gate"]["wasm_parity_verified"] is True
    assert receipt["dimensionless_ratios"]["verified_liquid_coverage_months"] == 10.43

    # Closing Track 0 STILL does NOT auto-sign QF-A5
    boundary = receipt["cryptographic_boundary"]
    assert boundary["TRACK_0"] == "CLOSED"
    assert boundary["PERSONAL_HARD_STOPS_CLEARED"] is True
    assert boundary["ALL_HARD_STOPS"] is False
    assert boundary["QF_A5_SIGNING"] == "READY_FOR_HUMAN_CEREMONY"
    assert boundary["ADMISSION_SIGNED"] is False

    # Zero-dollar-leakage proof: none of the sensitive raw figures appear in serialized output
    serialized = json.dumps(receipt)
    for raw_figure in ("18423.17", "12306.66", "41729.83", "149281.55", "1189.47", "75000"):
        assert raw_figure not in serialized


def test_track0_excludes_pending_bounties_grants_and_speculative_assets():
    now = dt.datetime(2026, 10, 31, 2, 30, tzinfo=dt.timezone.utc)
    # Settled liquid = 12,000 (< 24,000 required for 4,000/mo), despite $152,000 pending/speculative
    ws = _sample_worksheet(checking=5000.0, savings=7000.0, tbills=0.0)
    receipt = reconcile_track0_worksheet(ws, reference_now_utc=now)

    assert receipt["dimensionless_ratios"]["verified_liquid_coverage_months"] == 3.0
    assert receipt["track_0_gate"]["status"] == "OPEN"
    assert receipt["track_0_gate"]["invariant_satisfied"] is False
    assert receipt["track_0_gate"]["discretionary_capex_decision"] == "DENY"
    assert receipt["cryptographic_boundary"]["QF_A5_SIGNING"] == "GATED"
    assert receipt["cryptographic_boundary"]["ADMISSION_SIGNED"] is False


def test_track0_rejects_cloud_spend_stale_date_and_missing_attestation():
    now = dt.datetime(2026, 10, 31, 2, 30, tzinfo=dt.timezone.utc)

    ws_cloud = _sample_worksheet(cloud_llm_spend=0.01)
    with pytest.raises(SecurityBoundaryError, match="Zero-Cloud-Spend Invariant Violation"):
        reconcile_track0_worksheet(ws_cloud, reference_now_utc=now)

    ws_stale = _sample_worksheet(reconciled_at_utc="2026-09-15T00:00:00Z")
    with pytest.raises(Track0ValidationError, match="stale"):
        reconcile_track0_worksheet(ws_stale, reference_now_utc=now)

    ws_unattested = _sample_worksheet()
    ws_unattested["operator_attestation"]["operator_attested"] = False
    with pytest.raises(Track0ValidationError, match="operator_attested"):
        reconcile_track0_worksheet(ws_unattested, reference_now_utc=now)


def test_qf_a5_preflight_and_guarded_ceremony_boundary(tmp_path: Path):
    # Set up isolated temporary git repository for ceremony tests
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "rock@quantumflex.local"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Rocky"], check=True)

    artifacts = ("src/privacy_filter.py", "src/bounty_assurance.py")
    for rel in artifacts:
        f = repo / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(f"# {rel}\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "init"], check=True, stdout=subprocess.DEVNULL)

    priv_path = tmp_path / "keys" / "release.pem"
    pub_path = tmp_path / "keys" / "release.pub.pem"
    _, pub_key = ensure_or_load_release_keypair(priv_path, pub_path, auto_generate_if_missing=True)
    signed_out = tmp_path / "out" / "signed_receipt.json"

    # 1. Preflight with missing Track 0 receipt -> TRACK_0 = OPEN, ADMISSION_SIGNED = False
    preflight_open = build_qf_a5_preflight_manifest(
        repo_root=repo,
        track0_receipt_path=tmp_path / "missing_track0.json",
        required_artifacts=artifacts,
    )
    assert preflight_open["ledger_state"]["TRACK_0"] == "OPEN"
    assert preflight_open["ledger_state"]["QF_A5_SIGNING"] == "GATED"
    assert preflight_open["ledger_state"]["ADMISSION_SIGNED"] is False

    # 2. Attempting to execute ceremony while TRACK_0 is OPEN -> blocked fail-closed
    with pytest.raises(PermissionError, match="TRACK_0 financial reserve gate is OPEN"):
        execute_guarded_qf_a5_ceremony(
            repo_root=repo,
            track0_receipt_path=tmp_path / "missing_track0.json",
            private_key_path=priv_path,
            public_key_path=pub_path,
            output_receipt_path=signed_out,
            operator_confirmation=REQUIRED_CONFIRMATION_PHRASE,
            required_artifacts=artifacts,
        )
    assert not signed_out.exists()

    # 3. Write passing Track 0 ratio receipt; preflight STILL keeps ADMISSION_SIGNED = False
    now = dt.datetime(2026, 10, 31, 2, 30, tzinfo=dt.timezone.utc)
    track0_receipt_path = tmp_path / "track0_pass.json"
    track0_receipt_path.write_text(
        json.dumps(reconcile_track0_worksheet(_sample_worksheet(), reference_now_utc=now)),
        encoding="utf-8",
    )
    preflight_ready = build_qf_a5_preflight_manifest(
        repo_root=repo,
        track0_receipt_path=track0_receipt_path,
        required_artifacts=artifacts,
    )
    assert preflight_ready["ledger_state"]["TRACK_0"] == "CLOSED"
    assert preflight_ready["ledger_state"]["QF_A5_SIGNING"] == "READY_FOR_HUMAN_CEREMONY"
    assert preflight_ready["ledger_state"]["ADMISSION_SIGNED"] is False

    # 4. Without human confirmation phrase, ceremony STILL fails closed
    with pytest.raises(PermissionError, match="Explicit human authorization phrase"):
        execute_guarded_qf_a5_ceremony(
            repo_root=repo,
            track0_receipt_path=track0_receipt_path,
            private_key_path=priv_path,
            public_key_path=pub_path,
            output_receipt_path=signed_out,
            operator_confirmation="",
            required_artifacts=artifacts,
        )
    assert not signed_out.exists()

    # 5. With passing Track 0 AND explicit human confirmation AND 0600 key -> valid Ed25519 receipt
    signed = execute_guarded_qf_a5_ceremony(
        repo_root=repo,
        track0_receipt_path=track0_receipt_path,
        private_key_path=priv_path,
        public_key_path=pub_path,
        output_receipt_path=signed_out,
        operator_confirmation=REQUIRED_CONFIRMATION_PHRASE,
        required_artifacts=artifacts,
    )
    assert signed_out.is_file()
    assert verify_admission_receipt(signed, repo_root=repo, trusted_public_key=pub_key) is True


# ==============================================================================
# Part 2: Technical Corrections A–D & QF-BOUNTY-01..03 Acceptance Gates
# ==============================================================================
def _make_ed25519_keypair() -> Tuple[Ed25519PrivateKey, str]:
    priv = Ed25519PrivateKey.generate()
    pub_raw = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return priv, base64.b64encode(pub_raw).decode("ascii")


def test_technical_correction_a_two_person_authorization_all_six_invariants():
    priv_a, pub_a_b64 = _make_ed25519_keypair()
    priv_b, pub_b_b64 = _make_ed25519_keypair()
    priv_a2, pub_a2_b64 = _make_ed25519_keypair()

    authorized_identities = {
        "rahshaun_chambers": ["cred-titan-m2", "cred-pluton-backup"],
        "co_signer_guardian": ["cred-guardian-yubikey"],
    }
    trusted_pubkeys = {
        "cred-titan-m2": pub_a_b64,
        "cred-pluton-backup": pub_a2_b64,
        "cred-guardian-yubikey": pub_b_b64,
    }
    tx_params = {
        "chain_id": 8453,
        "contract_address": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "operation_type": "escrow_release",
        "destination": "0x1111111111111111111111111111111111111111",
        "amount_base_units": 5_000_000,
        "nonce": "quorum-nonce-001",
        "issued_at_unix": 1793400000,
        "expires_at_unix": 1793400300,
    }
    tx_bytes = build_two_person_signing_payload(**tx_params)
    sig_a = base64.b64encode(priv_a.sign(tx_bytes)).decode("ascii")
    sig_b = base64.b64encode(priv_b.sign(tx_bytes)).decode("ascii")
    sig_a2 = base64.b64encode(priv_a2.sign(tx_bytes)).decode("ascii")

    att_a = SignerAttestation("rahshaun_chambers", "cred-titan-m2", pub_a_b64, sig_a)
    att_b = SignerAttestation("co_signer_guardian", "cred-guardian-yubikey", pub_b_b64, sig_b)
    att_a_second_hw = SignerAttestation("rahshaun_chambers", "cred-pluton-backup", pub_a2_b64, sig_a2)

    replay_store: set[str] = set()

    # 1. Single person using TWO hardware credentials fails closed!
    with pytest.raises(BountyGateError, match="distinct identities required"):
        verify_two_person_authorization(
            **tx_params,
            current_unix=1793400100,
            attestation_a=att_a,
            attestation_b=att_a_second_hw,
            authorized_identities=authorized_identities,
            trusted_credential_pubkeys_b64=trusted_pubkeys,
            consumed_replay_keys=replay_store,
        )

    # 2. Revoked credential fails closed without burning nonce
    with pytest.raises(BountyGateError, match="credential has been revoked"):
        verify_two_person_authorization(
            **tx_params,
            current_unix=1793400100,
            attestation_a=att_a,
            attestation_b=att_b,
            authorized_identities=authorized_identities,
            trusted_credential_pubkeys_b64=trusted_pubkeys,
            consumed_replay_keys=replay_store,
            revoked_credentials=["cred-guardian-yubikey"],
        )
    assert len(replay_store) == 0

    # 3. Expired timestamp fails closed
    with pytest.raises(BountyGateError, match="expired"):
        verify_two_person_authorization(
            **tx_params,
            current_unix=1793400999,
            attestation_a=att_a,
            attestation_b=att_b,
            authorized_identities=authorized_identities,
            trusted_credential_pubkeys_b64=trusted_pubkeys,
            consumed_replay_keys=replay_store,
        )

    # 4. Tampered transaction binding (different amount) fails signature verification
    tampered_params = dict(tx_params, amount_base_units=9_000_000)
    with pytest.raises(BountyGateError, match="invalid Ed25519 signature"):
        verify_two_person_authorization(
            **tampered_params,
            current_unix=1793400100,
            attestation_a=att_a,
            attestation_b=att_b,
            authorized_identities=authorized_identities,
            trusted_credential_pubkeys_b64=trusted_pubkeys,
            consumed_replay_keys=replay_store,
        )

    # 5. Valid two-person quorum succeeds
    res = verify_two_person_authorization(
        **tx_params,
        current_unix=1793400100,
        attestation_a=att_a,
        attestation_b=att_b,
        authorized_identities=authorized_identities,
        trusted_credential_pubkeys_b64=trusted_pubkeys,
        consumed_replay_keys=replay_store,
    )
    assert res["authorized"] is True

    # 6. Replaying identical authorization fails closed
    with pytest.raises(BountyGateError, match="replay detected"):
        verify_two_person_authorization(
            **tx_params,
            current_unix=1793400120,
            attestation_a=att_a,
            attestation_b=att_b,
            authorized_identities=authorized_identities,
            trusted_credential_pubkeys_b64=trusted_pubkeys,
            consumed_replay_keys=replay_store,
        )


def test_technical_correction_b_token_decimal_precision():
    # Canonical Base Mainnet USDC: 1.00 USDC == 1_000_000 base units
    usdc_res = verify_token_decimal_precision(
        chain_id=8453,
        token_address="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        human_amount=Decimal("1.00"),
        onchain_queried_decimals=6,
        assumed_decimals=6,
    )
    assert usdc_res["is_canonical_usdc"] is True
    assert usdc_res["base_units"] == 1_000_000

    # Unverified decimal assumption (None) fails closed
    with pytest.raises(BountyGateError, match="never assume ERC-20 decimals"):
        verify_token_decimal_precision(
            chain_id=8453,
            token_address="0x2222222222222222222222222222222222222222",
            human_amount="10.0",
            onchain_queried_decimals=None,
        )

    # Assuming 6 decimals on an 18-decimal ERC-20 token fails closed
    with pytest.raises(BountyGateError, match="Token Precision Mismatch"):
        verify_token_decimal_precision(
            chain_id=8453,
            token_address="0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb",
            human_amount="10.0",
            onchain_queried_decimals=18,
            assumed_decimals=6,
        )

    # Verified 18-decimal ERC-20 scales accurately when queried decimals match
    dai_res = verify_token_decimal_precision(
        chain_id=8453,
        token_address="0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb",
        human_amount="2.5",
        onchain_queried_decimals=18,
        assumed_decimals=18,
    )
    assert dai_res["is_canonical_usdc"] is False
    assert dai_res["base_units"] == 2_500_000_000_000_000_000


def test_technical_correction_c_full_context_idempotency_key():
    block_hash = "0x" + ("ab" * 32)
    base_ctx = {
        "chain_id": 84532,
        "contract_address": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
        "operation_type": "usdc_transfer",
        "nonce": 42,
        "destination": "0x3333333333333333333333333333333333333333",
        "amount_base_units": 1_000_000,
        "proof_block_hash": block_hash,
    }
    key_1 = derive_contextual_idempotency_key(**base_ctx)
    key_retry = derive_contextual_idempotency_key(**base_ctx)
    assert key_1 == key_retry

    parsed_uuid = uuid.UUID(key_1)
    assert parsed_uuid.version == 4
    assert parsed_uuid.variant == uuid.RFC_4122

    # Separate operations inside the SAME block hash MUST produce distinct UUIDv4 keys
    assert key_1 != derive_contextual_idempotency_key(**dict(base_ctx, nonce=43))
    assert key_1 != derive_contextual_idempotency_key(**dict(base_ctx, amount_base_units=2_000_000))
    assert key_1 != derive_contextual_idempotency_key(
        **dict(base_ctx, destination="0x4444444444444444444444444444444444444444")
    )
    assert key_1 != derive_contextual_idempotency_key(**dict(base_ctx, chain_id=8453))
    assert key_1 != derive_contextual_idempotency_key(**dict(base_ctx, operation_type="escrow_sweep"))


def test_technical_correction_d_context_dependent_severity():
    # Missing dual control with single compromised operator + 2 compensating controls != Critical
    guarded = assess_contextual_severity(
        reachable_functionality="timelocked_or_guarded",
        required_attacker_privilege="compromised_single_operator",
        compensating_controls=["48h_timelock_delay", "per_epoch_velocity_cap"],
        theoretical_max_exposure_usd=1_000_000.0,
        realistic_reachable_exposure_usd=25_000.0,
        exploitability="conditional_multi_step",
    )
    assert guarded["severity"] == "Medium"

    # Unauthenticated, unmitigated, deterministic $500k drain -> Critical (unless capped by program rubric)
    unmitigated = assess_contextual_severity(
        reachable_functionality="unrestricted_external",
        required_attacker_privilege="unauthenticated",
        compensating_controls=[],
        theoretical_max_exposure_usd=500_000.0,
        realistic_reachable_exposure_usd=500_000.0,
        exploitability="deterministic_single_tx",
    )
    assert unmitigated["severity"] == "Critical"

    # Program rubric cap overrides raw technical severity
    capped = assess_contextual_severity(
        reachable_functionality="unrestricted_external",
        required_attacker_privilege="unauthenticated",
        compensating_controls=[],
        theoretical_max_exposure_usd=500_000.0,
        realistic_reachable_exposure_usd=500_000.0,
        exploitability="deterministic_single_tx",
        program_max_severity_for_class="High",
    )
    assert capped["severity"] == "High"


def test_qf_bounty_01_02_03_acceptance_gates_and_template_compliance():
    source_bytes = b"contract Vault { function sweep(address to, uint256 amt) external {} }"
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    receipt_bytes = b'{"dossier_id":"QF-BOUNTY-TEST","signed":false}'
    receipt_sha = hashlib.sha256(receipt_bytes).hexdigest()
    run_digest = hashlib.sha256(b"PASS: local fork invariant reproduced").hexdigest()

    template_md = Path("sovereign_missions/01_BUG_BOUNTY_PROOF_DOSSIER_TEMPLATE.md").read_text(
        encoding="utf-8"
    )
    assert "evidence-generation framework" in template_md
    assert "SYNTHETIC_DEMO" in template_md
    assert "## 6. Independent Validation" in template_md
    _, template_redactions = PrivacyFilter.sanitize(template_md)
    assert template_redactions == 0

    auth_ok = {
        "program_name": "Immunefi-Vault-Program",
        "program_scope_url": "https://immunefi.com/bug-bounty/example-vault/",
        "scope_verified_at_utc": "2026-10-30T21:00:00Z",
        "target_identifier": "contracts/Vault.sol",
        "authorized_targets": ["contracts/Vault.sol", "contracts/Escrow.sol"],
        "testing_environment": "local_foundry_fork",
        "permitted_methods_verified": True,
        "autonomous_exploitation_enabled": False,
    }
    evidence_ok = {
        "source_files_bytes": {"contracts/Vault.sol": source_bytes},
        "claimed_source_sha256": {"contracts/Vault.sol": source_sha},
        "vulnerable_function": "Vault.sweep(address,uint256)",
        "missing_security_invariant": "validTwoPersonQuorum(txContext, sigA, sigB)",
        "reproducer_run_digests": [run_digest, run_digest],
        "baseline_behavior_established": True,
        "remediation_regression_restores_invariant": True,
        "theoretical_max_exposure_usd": 250_000.0,
        "realistic_reachable_exposure_usd": 50_000.0,
        "provenance_receipt_bytes": receipt_bytes,
        "claimed_provenance_receipt_sha256": receipt_sha,
    }
    disclosure_ok = {
        "dossier_markdown": template_md,
        "third_party_pii_cleared": True,
        "program_disclosure_rules_confirmed": True,
        "human_submission_approved": True,
        "human_approver_id": "rahshaun_chambers",
        "approved_at_utc": "2026-10-30T22:30:00Z",
    }

    admitted = evaluate_sovereign_bounty_gates(
        authorization_kwargs=auth_ok,
        evidence_kwargs=evidence_ok,
        disclosure_kwargs=disclosure_ok,
    )
    assert admitted["submission_admitted"] is True

    # QF-BOUNTY-01 blocks live mainnet testing environment
    with pytest.raises(BountyGateError, match="QF-BOUNTY-01 FAIL"):
        evaluate_qf_bounty_01_authorization(**dict(auth_ok, testing_environment="mainnet_live"))

    # QF-BOUNTY-02 blocks non-deterministic reproducer or tampered source hash
    other_digest = hashlib.sha256(b"flaky run").hexdigest()
    with pytest.raises(BountyGateError, match="non-deterministic"):
        evaluate_qf_bounty_02_evidence(**dict(evidence_ok, reproducer_run_digests=[run_digest, other_digest]))

    with pytest.raises(BountyGateError, match="recomputed SHA-256 mismatch"):
        evaluate_qf_bounty_02_evidence(
            **dict(evidence_ok, claimed_source_sha256={"contracts/Vault.sol": "0" * 64})
        )

    # QF-BOUNTY-03 blocks missing human approval, unsanitized secrets, and live-drain commands
    with pytest.raises(BountyGateError, match="mandatory human submission approval"):
        evaluate_qf_bounty_03_disclosure(**dict(disclosure_ok, human_submission_approved=False))

    with pytest.raises(BountyGateError, match="unsanitized"):
        evaluate_qf_bounty_03_disclosure(
            **dict(disclosure_ok, dossier_markdown="Leaked token ghp_1234567890abcdefghijklmnopqrstuv")
        )

    with pytest.raises(BountyGateError, match="FORGE_LIVE_BROADCAST"):
        evaluate_qf_bounty_03_disclosure(
            **dict(
                disclosure_ok,
                dossier_markdown="forge script script/Drain.s.sol --rpc-url https://mainnet.base.org --broadcast",
            )
        )

