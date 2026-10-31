#!/usr/bin/env python3
"""
QF-M4 Independent Research Assurance Test Suite
===============================================
Tests all QF-M4 P0 and P1 acceptance gates + strengthened Golden Financial Invariant:
  1. Strengthened `evaluate_golden_financial_invariant`:
     - Verified liquid assets only (excludes speculative valuations; unverified -> DENY)
     - Household + committed operating obligations combined
     - Unavailable/missing financial assessment defaults fail-closed to DENY
  2. P0.1: Timed 500-page benchmark completes well within 600 seconds
  3. P0.2: Independent citation & Merkle root verifier reproduces all citations from disk
     and catches tampered Markdown or citations fail-closed
  4. P0.3: Cross-run reproducibility (MerkleRoot_1 == MerkleRoot_2) and single-document
     modification sensitivity (MerkleRoot_1 != MerkleRoot_3)
  5. P0.4: Internal-data isolation (Zero `sovereign_internal` chunks in client outputs)
  6. P1.1: Printable PDF-1.4 dossier production & SHA-256 verification
  7. P1.2: Recovery rebuild from preserved source corpus snapshot reproduces identical Merkle root
  8. P1.3: Commercial cost accounting (labor, hardware allocation, $0.00 cloud spend, gross margin)
"""

from pathlib import Path
import pytest

from scripts.benchmark_500page_dossier import build_500_page_corpus
from scripts.generate_research_dossier import (
    AthenaDossierStore,
    HardStopGateStatus,
    SecurityBoundaryError,
    _build_demo_corpus,
    evaluate_golden_financial_invariant,
    execute_dossier_pipeline,
    verify_authorized_bounty_scope,
)
from scripts.verify_dossier_independent import (
    IndependentAssuranceError,
    verify_cross_run_reproducibility_and_sensitivity,
    verify_dossier_artifacts_independently,
    verify_recovery_rebuild_from_snapshot,
)


def test_strengthened_golden_financial_invariant_conditions():
    """
    Tests the 3 additional QF-M4 financial invariant conditions:
      1. Speculative assets are excluded; unverified liquid reserves -> DENY.
      2. Monthly obligations combine household + committed operating expenses.
      3. Unavailable assessment (None or assessment_available=False) -> fail-closed DENY.
    """
    # Condition 1: $20k liquid + $50k speculative against $4k/mo obligations ($24k required) -> DENY
    eval_spec = evaluate_golden_financial_invariant(
        reserves_usd=20000.0,
        monthly_obligations_usd=4000.0,
        speculative_assets_usd=50000.0,
    )
    assert eval_spec.invariant_satisfied is False
    assert eval_spec.discretionary_capex_decision == "DENY"
    assert eval_spec.speculative_assets_excluded_usd == 50000.0

    # Unverified liquid flag -> fail-closed DENY even if nominal amount is high
    eval_unverified = evaluate_golden_financial_invariant(
        reserves_usd=100000.0,
        monthly_obligations_usd=4000.0,
        verified_liquid_only=False,
    )
    assert eval_unverified.invariant_satisfied is False
    assert eval_unverified.discretionary_capex_decision == "DENY"

    # Condition 2: Household ($3,500) + Committed Operating ($1,500) = $5,000/mo -> requires $30,000
    eval_combined_fail = evaluate_golden_financial_invariant(
        reserves_usd=25000.0,
        monthly_obligations_usd=3500.0,
        committed_operating_obligations_usd=1500.0,
    )
    assert eval_combined_fail.required_reserves_usd == 30000.0
    assert eval_combined_fail.invariant_satisfied is False
    assert eval_combined_fail.discretionary_capex_decision == "DENY"

    eval_combined_pass = evaluate_golden_financial_invariant(
        reserves_usd=36000.0,
        monthly_obligations_usd=3500.0,
        committed_operating_obligations_usd=1500.0,
    )
    assert eval_combined_pass.invariant_satisfied is True
    assert eval_combined_pass.discretionary_capex_decision == "ALLOW"

    # Condition 3: Unavailable / None assessment -> fail-closed DENY
    eval_unavailable = evaluate_golden_financial_invariant(
        reserves_usd=None,
        monthly_obligations_usd=4000.0,
        assessment_available=False,
    )
    assert eval_unavailable.invariant_satisfied is False
    assert eval_unavailable.discretionary_capex_decision == "DENY"

    # Condition 4: Stale reconciliation timestamp (> 30 days old) -> fail-closed DENY
    eval_stale = evaluate_golden_financial_invariant(
        reserves_usd=50000.0,
        monthly_obligations_usd=4000.0,
        reconciled_at_utc="2026-08-01T00:00:00Z",
        reference_now_utc="2026-10-30T21:00:00Z",
        max_reconciliation_age_days=30.0,
    )
    assert eval_stale.reconciliation_fresh is False
    assert eval_stale.invariant_satisfied is False
    assert eval_stale.discretionary_capex_decision == "DENY"

    # Fresh reconciliation timestamp (within 30 days) -> ALLOW
    eval_fresh = evaluate_golden_financial_invariant(
        reserves_usd=50000.0,
        monthly_obligations_usd=4000.0,
        reconciled_at_utc="2026-10-25T00:00:00Z",
        reference_now_utc="2026-10-30T21:00:00Z",
        max_reconciliation_age_days=30.0,
        require_reconciled_timestamp=True,
    )
    assert eval_fresh.reconciliation_fresh is True
    assert eval_fresh.invariant_satisfied is True
    assert eval_fresh.discretionary_capex_decision == "ALLOW"


def test_qf_m4_cross_run_reproducibility_and_modification_sensitivity(tmp_path: Path):
    """P0.3: Identical corpus -> MerkleRoot_1 == MerkleRoot_2; modified doc -> MerkleRoot_1 != MerkleRoot_3."""
    res = verify_cross_run_reproducibility_and_sensitivity(tmp_path)
    assert res["run1_equals_run2"] is True
    assert res["run1_not_equals_run3"] is True
    assert res["dossier_sha256_identical"] is True


def test_qf_m4_independent_verifier_and_tamper_rejection(tmp_path: Path):
    """P0.2, P0.4, P1.1, P1.3: Independent verifier reproduces Merkle root, citations, PDF, and catches edits."""
    md_path, receipt_path, receipt = execute_dossier_pipeline(
        dossier_id="QF-M4-IND-001",
        client_name="Independent Audit Counsel",
        title="Municipal Zoning, Post-Quantum Cryptography & Escrow Liability Dossier",
        corpus_documents=_build_demo_corpus(),
        output_dir=tmp_path,
    )
    pdf_path = Path(str(receipt.provenance["dossier_pdf_path"]))
    snapshot_path = Path(str(receipt.provenance["preserved_corpus_snapshot_path"]))

    res = verify_dossier_artifacts_independently(
        md_path=md_path,
        receipt_path=receipt_path,
        corpus_snapshot_path=snapshot_path,
        pdf_path=pdf_path,
    )
    assert res["independent_verification_pass"] is True
    assert res["recomputed_merkle_root"] == receipt.provenance["corpus_merkle_root_sha256"]
    assert res["gross_margin_pct"] > 90.0

    # Tamper with Markdown on disk -> Independent verifier must fail closed
    original_md = md_path.read_text(encoding="utf-8")
    md_path.write_text(original_md + "\n- Uncited injected claim.\n", encoding="utf-8")
    with pytest.raises(IndependentAssuranceError, match="Markdown SHA-256 mismatch"):
        verify_dossier_artifacts_independently(
            md_path=md_path,
            receipt_path=receipt_path,
            corpus_snapshot_path=snapshot_path,
            pdf_path=pdf_path,
        )


def test_qf_m4_recovery_rebuild_from_preserved_corpus(tmp_path: Path):
    """P1.2: Rebuilds dossier from preserved source corpus snapshot and verifies identical Merkle root & SHA-256."""
    out_dir = tmp_path / "primary"
    recovery_dir = tmp_path / "recovery"
    _, receipt_path, receipt = execute_dossier_pipeline(
        dossier_id="QF-M4-REC-001",
        client_name="Recovery Test Client",
        title="Municipal Zoning, Post-Quantum Cryptography & Escrow Liability Dossier",
        corpus_documents=_build_demo_corpus(),
        output_dir=out_dir,
        generated_at_override="2026-10-30T21:15:00Z",
    )
    snapshot_path = Path(str(receipt.provenance["preserved_corpus_snapshot_path"]))

    rec = verify_recovery_rebuild_from_snapshot(
        corpus_snapshot_path=snapshot_path,
        original_receipt_path=receipt_path,
        recovery_dir=recovery_dir,
    )
    assert rec["recovery_rebuild_pass"] is True
    assert rec["recovered_merkle_root"] == receipt.provenance["corpus_merkle_root_sha256"]
    assert rec["recovered_dossier_sha256"] == receipt.provenance["dossier_sha256"]


def test_qf_m4_timed_500_page_workload_under_600s(tmp_path: Path):
    """P0.1: Timed 500-page workload completes within 600s and passes independent verification."""
    corpus = build_500_page_corpus()
    md_path, receipt_path, receipt = execute_dossier_pipeline(
        dossier_id="QF-M4-500P-TEST",
        client_name="500-Page Timed SLA Gate",
        title="Municipal Zoning, Post-Quantum Cryptography & Escrow Liability Dossier",
        corpus_documents=corpus,
        output_dir=tmp_path,
    )
    assert int(receipt.performance["pages_ingested"]) == 501
    assert int(receipt.performance["chunks_indexed"]) == 500
    assert float(receipt.performance["elapsed_seconds"]) <= 600.0
    assert receipt.performance["at_rdos_01_sla_pass"] is True

    ind = verify_dossier_artifacts_independently(
        md_path=md_path,
        receipt_path=receipt_path,
        corpus_snapshot_path=Path(str(receipt.provenance["preserved_corpus_snapshot_path"])),
        pdf_path=Path(str(receipt.provenance["dossier_pdf_path"])),
    )
    assert ind["independent_verification_pass"] is True


def test_qf_m5_sovereign_safeguards_and_boundaries():
    """
    QF-M5 Sovereign Operational Readiness Safeguards:
      - Safeguard A: Individual tax/reporting/program-eligibility compliance preserved when PA-LLC is retired.
      - Safeguard B: Clearing personal hard stops does NOT auto-sign (`signed: True`) without explicit QF-A5 signing ceremony.
      - Safeguard C: Pending bug bounties and pending grants are strictly excluded from R_verified_liquid.
      - Pillar I: `verify_authorized_bounty_scope` blocks out-of-scope targets and autonomous exploitation.
      - Pillar III: `household_financial` chunks are isolated from external/public dossier retrieval.
    """
    # Safeguard B: All 3 personal hard stops cleared + LLC retired, but QF-A5 ceremony False -> all_cleared False
    gate_unsigned = HardStopGateStatus(
        hs_px_pixel_cve_2026_58704_patched=True,
        as_01_03_account_security_verified=True,
        pa_llc_finallyfungus_subsistence_verified=False,
        track_0_reserve_ratio_gte_6m=True,
        sovereign_non_corporate_mode=True,
        individual_tax_and_program_compliance_verified=True,
        qf_a5_signing_ceremony_completed=False,
    )
    assert gate_unsigned.personal_hard_stops_cleared is True
    assert gate_unsigned.all_cleared is False

    # Safeguard A: If individual tax/program compliance is False, personal hard stops also fail closed
    gate_tax_unverified = HardStopGateStatus(
        hs_px_pixel_cve_2026_58704_patched=True,
        as_01_03_account_security_verified=True,
        pa_llc_finallyfungus_subsistence_verified=False,
        track_0_reserve_ratio_gte_6m=True,
        sovereign_non_corporate_mode=True,
        individual_tax_and_program_compliance_verified=False,
        qf_a5_signing_ceremony_completed=True,
    )
    assert gate_tax_unverified.personal_hard_stops_cleared is False
    assert gate_tax_unverified.all_cleared is False

    # Only when personal hard stops AND explicit QF-A5 signing ceremony complete -> all_cleared True
    gate_signed = HardStopGateStatus(
        hs_px_pixel_cve_2026_58704_patched=True,
        as_01_03_account_security_verified=True,
        pa_llc_finallyfungus_subsistence_verified=False,
        track_0_reserve_ratio_gte_6m=True,
        sovereign_non_corporate_mode=True,
        individual_tax_and_program_compliance_verified=True,
        qf_a5_signing_ceremony_completed=True,
    )
    assert gate_signed.all_cleared is True

    # Safeguard C: $15k settled liquid + $50k pending bounty + $30k pending grant vs $4k/mo ($24k required) -> DENY
    eval_pending = evaluate_golden_financial_invariant(
        reserves_usd=15000.0,
        monthly_obligations_usd=4000.0,
        pending_bounties_usd=50000.0,
        pending_grants_usd=30000.0,
    )
    assert eval_pending.reserves_usd == 15000.0
    assert eval_pending.pending_bounties_excluded_usd == 50000.0
    assert eval_pending.pending_grants_excluded_usd == 30000.0
    assert eval_pending.invariant_satisfied is False
    assert eval_pending.discretionary_capex_decision == "DENY"

    # Pillar I: Authorized scope verification
    scope_ok = verify_authorized_bounty_scope(
        program_name="Immunefi-Authorized-Vault",
        target_in_authorized_scope=True,
        autonomous_exploitation_enabled=False,
    )
    assert scope_ok["authorized_scope_decision"] == "ALLOW"

    with pytest.raises(SecurityBoundaryError, match="not within explicitly authorized program scope"):
        verify_authorized_bounty_scope(
            program_name="Out-Of-Scope-Protocol",
            target_in_authorized_scope=False,
        )

    with pytest.raises(SecurityBoundaryError, match="autonomous exploitation"):
        verify_authorized_bounty_scope(
            program_name="Immunefi-Authorized-Vault",
            target_in_authorized_scope=True,
            autonomous_exploitation_enabled=True,
        )

    # Pillar III: Physical & logical separation of household_financial records
    store = AthenaDossierStore()
    store.ingest_document(
        source_ref="household/family_budget_2026.md",
        pages=["Household financial reserve ledger: T-Bill balance and monthly mortgage."],
        role="household_financial",
    )
    store.ingest_document(
        source_ref="bounty/public_protocol_spec.md",
        pages=["Public protocol escrow specification for 6-decimal USDC settlement."],
        role="public",
    )
    hits = store.retrieve_for_dossier("Household financial reserve ledger public protocol escrow")
    assert len(hits) == 1
    assert hits[0].role == "public"

    with pytest.raises(SecurityBoundaryError, match="Role Isolation Violation"):
        store.retrieve_for_dossier("ledger", allowed_roles={"household_financial", "public"})


def test_track0_reconciler_and_qf_a5_ceremony_boundary(tmp_path: Path):
    """
    QF-M5.1 Track 0 Reconciler & QF-A5 Ceremony Boundary:
      - Unreconciled snapshot keeps TRACK_0=OPEN, PERSONAL_HARD_STOPS_CLEARED=False,
        ALL_HARD_STOPS=False, QF_A5_SIGNING=GATED, ADMISSION_SIGNED=False.
      - Reconciling a passing 0600 worksheet (>= 6O) closes TRACK_0 and emits dimensionless
        ratios only (zero raw dollar figures), while keeping ALL_HARD_STOPS=False and
        ADMISSION_SIGNED=False until explicit QF-A5 ceremony confirmation.
      - Guarded QF-A5 ceremony blocks signing when TRACK_0 is OPEN or confirmation phrase is absent.
    """
    import datetime as dt
    from scripts.prepare_qf_a5_ceremony import (
        build_qf_a5_preflight_manifest,
        execute_guarded_qf_a5_ceremony,
    )
    from scripts.reconcile_track0_reserves import (
        build_unreconciled_status_snapshot,
        reconcile_track0_worksheet,
    )

    unrec = build_unreconciled_status_snapshot()
    assert unrec["track_0_gate"]["status"] == "OPEN"
    assert unrec["cryptographic_boundary"]["HS-PX"] == "CLOSED"
    assert unrec["cryptographic_boundary"]["AS-01..03"] == "CLOSED"
    assert unrec["cryptographic_boundary"]["PA-LLC"] == "RETIRED"
    assert unrec["cryptographic_boundary"]["TRACK_0"] == "OPEN"
    assert unrec["cryptographic_boundary"]["PERSONAL_HARD_STOPS_CLEARED"] is False
    assert unrec["cryptographic_boundary"]["ALL_HARD_STOPS"] is False
    assert unrec["cryptographic_boundary"]["QF_A5_SIGNING"] == "GATED"
    assert unrec["cryptographic_boundary"]["ADMISSION_SIGNED"] is False

    # Passing Track 0 worksheet (7.50 months coverage; pending bounties/grants excluded)
    ref_now = dt.datetime(2026, 10, 30, 22, 30, tzinfo=dt.timezone.utc)
    passing_ws = {
        "schema": "qf.track0_worksheet.v1",
        "reconciled_at_utc": "2026-10-30T22:00:00Z",
        "operator_attestation": {
            "operator_id": "rahshaun_chambers",
            "operator_attested": True,
            "statements_verified_against_primary_institutions": True,
            "pending_awards_and_speculative_assets_excluded": True,
        },
        "verified_liquid_accounts_usd": {
            "checking_fdic": 10000.0,
            "savings_or_money_market_fdic": 10000.0,
            "settled_short_term_tbills": 10000.0,
        },
        "excluded_non_reserve_items_usd": {
            "pending_bounties": 50000.0,
            "anticipated_grants": 25000.0,
            "speculative_or_illiquid_assets": 15000.0,
        },
        "outstanding_debts": [
            {
                "name": "primary_housing",
                "principal_balance_usd": 120000.0,
                "monthly_payment_usd": 1500.0,
            }
        ],
        "monthly_household_living_expenses_usd": {
            "utilities_and_connectivity": 500.0,
            "groceries_and_essentials": 1000.0,
            "healthcare_and_insurance": 500.0,
            "transportation": 300.0,
            "family_and_contingency": 175.0,
        },
        "committed_quantumflex_operating_expenses_usd": {
            "external_cloud_llm_spend": 0.0,
            "corporate_llc_overhead": 0.0,
            "local_compute_electricity": 10.0,
            "network_and_hardware_reserve": 15.0,
        },
    }
    receipt = reconcile_track0_worksheet(passing_ws, reference_now_utc=ref_now)
    assert receipt["raw_dollar_figures_omitted"] is True
    assert receipt["dimensionless_ratios"]["verified_liquid_coverage_months"] == 7.5
    assert receipt["track_0_gate"]["status"] == "CLOSED"
    assert receipt["cryptographic_boundary"]["TRACK_0"] == "CLOSED"
    assert receipt["cryptographic_boundary"]["PERSONAL_HARD_STOPS_CLEARED"] is True
    assert receipt["cryptographic_boundary"]["ALL_HARD_STOPS"] is False
    assert receipt["cryptographic_boundary"]["QF_A5_SIGNING"] == "READY_FOR_HUMAN_CEREMONY"
    assert receipt["cryptographic_boundary"]["ADMISSION_SIGNED"] is False

    # Guarded QF-A5 ceremony blocks execution when Track 0 receipt is missing/OPEN
    with pytest.raises(PermissionError, match="TRACK_0 financial reserve gate is OPEN"):
        execute_guarded_qf_a5_ceremony(
            track0_receipt_path=tmp_path / "nonexistent_track0.json",
            output_receipt_path=tmp_path / "signed.json",
            operator_confirmation="I_AUTHORIZE_QF_A5_SIGNING",
        )

    # Even with passing Track 0 receipt, missing human confirmation phrase blocks signing
    t0_path = tmp_path / "track0_pass.json"
    import json

    t0_path.write_text(json.dumps(receipt), encoding="utf-8")
    preflight = build_qf_a5_preflight_manifest(track0_receipt_path=t0_path)
    assert preflight["ledger_state"]["TRACK_0"] == "CLOSED"
    assert preflight["ledger_state"]["ALL_HARD_STOPS"] is False
    assert preflight["ledger_state"]["ADMISSION_SIGNED"] is False

    with pytest.raises(PermissionError, match="Explicit human authorization phrase"):
        execute_guarded_qf_a5_ceremony(
            track0_receipt_path=t0_path,
            output_receipt_path=tmp_path / "signed.json",
            operator_confirmation="",
        )

    # Full guarded ceremony pass using isolated tmp_path 0600 Ed25519 keypair
    from src.admission_receipt import ensure_or_load_release_keypair, verify_admission_receipt

    tmp_priv = tmp_path / "test_release_ed25519.pem"
    tmp_pub = tmp_path / "test_release_ed25519.pub.pem"
    _, pub_key = ensure_or_load_release_keypair(
        private_key_path=tmp_priv,
        public_key_path=tmp_pub,
        auto_generate_if_missing=True,
    )
    signed_out = tmp_path / "qf_m5_signed_admission_receipt.json"
    signed_receipt = execute_guarded_qf_a5_ceremony(
        track0_receipt_path=t0_path,
        private_key_path=tmp_priv,
        public_key_path=tmp_pub,
        output_receipt_path=signed_out,
        operator_confirmation="I_AUTHORIZE_QF_A5_SIGNING",
    )
    assert signed_out.is_file()
    assert verify_admission_receipt(signed_receipt, trusted_public_key=pub_key) is True
    boundary = signed_receipt["payload"]["qf_m5_ceremony_boundary"]
    assert boundary["TRACK_0"] == "CLOSED"
    assert boundary["PERSONAL_HARD_STOPS_CLEARED"] is True
    assert boundary["ALL_HARD_STOPS"] is True
    assert boundary["QF_A5_SIGNING"] == "PASS"
    assert boundary["ADMISSION_SIGNED"] is True



