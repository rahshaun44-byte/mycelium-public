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
    _build_demo_corpus,
    evaluate_golden_financial_invariant,
    execute_dossier_pipeline,
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
