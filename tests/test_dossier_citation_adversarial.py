#!/usr/bin/env python3
"""
QF-M3 / AT-RDOS-01..03: Adversarial Citation, Role Isolation, PrivacyFilter & Financial Invariant Test Suite
============================================================================================================
Verifies all governing invariants in `scripts/generate_research_dossier.py`:
  1. Law 0 & Law 2: `evaluate_golden_financial_invariant` (R >= O * 6 months)
  2. Stage 2: `PrivacyFilter.sanitize` scrubs private keys, credentials, SSNs, host paths,
     Operator identity ('Rahshaun Chambers'), and family financial accounts
  3. Stage 1 & 3: `AthenaDossierStore` idempotent `delete_by_source` & strict role isolation
     (blocks `sovereign_internal` in client queries)
  4. Stage 4: `CitationVerifier.verify_sections` fails closed on:
     - Uncited claims
     - Nonexistent chunk_id
     - Restricted `sovereign_internal` role citation
     - Page offset mismatch
     - SHA-256 content tamper
  5. Stage 5: `verify_loopback_inference_endpoint` blocks non-loopback cloud URLs ($0.00 spend)
     and `execute_dossier_pipeline` emits `signed: False` (`GATED`) until all 4 P0 Hard Stops clear.
"""

from dataclasses import replace
from pathlib import Path
import pytest

from scripts.generate_research_dossier import (
    AthenaDossierStore,
    CitationVerificationError,
    CitationVerifier,
    HardStopGateStatus,
    PrivacyFilter,
    SecurityBoundaryError,
    evaluate_golden_financial_invariant,
    execute_dossier_pipeline,
    verify_loopback_inference_endpoint,
    _build_demo_corpus,
)


def test_golden_financial_invariant_r_gte_6o():
    """Law 2: Reserves (R) >= Obligations (O) * 6 months."""
    passing = evaluate_golden_financial_invariant(reserves_usd=30000.0, monthly_obligations_usd=4000.0)
    assert passing.invariant_satisfied is True
    assert passing.required_reserves_usd == 24000.0
    assert passing.coverage_months == 7.5

    failing = evaluate_golden_financial_invariant(reserves_usd=18000.0, monthly_obligations_usd=4000.0)
    assert failing.invariant_satisfied is False
    assert failing.coverage_months == 4.5

    with pytest.raises(ValueError):
        evaluate_golden_financial_invariant(reserves_usd=-100.0, monthly_obligations_usd=4000.0)


def test_privacy_filter_scrubs_operator_and_secrets():
    """Stage 2: Zero Ambient Data Sanitizer scrubs Operator identity, paths, tokens, keys, SSN, and accounts."""
    raw = (
        "Operator Rahshaun Chambers stored key at /home/quant/secrets/key.pem "
        "with token ghp_1234567890abcdefghijklmnopqrstuv, SSN 123-45-6789, "
        "and routing number: 021000021."
    )
    sanitized, count = PrivacyFilter.sanitize(raw)
    assert count >= 5
    assert "Rahshaun" not in sanitized
    assert "/home/quant" not in sanitized
    assert "ghp_" not in sanitized
    assert "123-45-6789" not in sanitized
    assert "021000021" not in sanitized
    assert "[REDACTED_OPERATOR_IDENTITY]" in sanitized
    assert "/opt/quantumflex/workspace" in sanitized
    assert "[REDACTED_CREDENTIAL]" in sanitized
    assert "[REDACTED_SSN]" in sanitized
    assert "[REDACTED_FAMILY_FINANCIAL_ACCT]" in sanitized


def test_role_isolation_blocks_sovereign_internal():
    """Stage 3: Client dossier retrieval strictly rejects `sovereign_internal` chunks."""
    store = AthenaDossierStore()
    store.ingest_document(
        source_ref="vault/internal.md",
        pages=["Sovereign internal reserve worksheet for Rahshaun Chambers."],
        role="sovereign_internal",
    )
    store.ingest_document(
        source_ref="filings/public_zoning.pdf",
        pages=["Section 402.1 Light Industrial permitted up to 15 kW load."],
        role="public",
    )

    # Default client retrieval never returns sovereign_internal
    hits = store.retrieve_for_dossier("Sovereign internal reserve worksheet Light Industrial")
    assert len(hits) == 1
    assert hits[0].role == "public"

    # Explicitly requesting sovereign_internal in client dossier raises SecurityBoundaryError
    with pytest.raises(SecurityBoundaryError, match="Role Isolation Violation"):
        store.retrieve_for_dossier("worksheet", allowed_roles={"sovereign_internal", "public"})


def test_idempotent_delete_by_source():
    """Stage 1: Re-ingesting a source document purges stale chunks without duplication."""
    store = AthenaDossierStore()
    first = store.ingest_document("filings/doc1.pdf", ["Page 1 initial text"], role="public")
    assert len(first) == 1
    second = store.ingest_document("filings/doc1.pdf", ["Page 1 updated text"], role="public")
    assert len(second) == 1
    assert len(store.all_client_SAFE_chunks) == 1
    assert store.get_chunk(first[0].chunk_id) is None


def test_citation_verifier_adversarial_failures():
    """Stage 4 (AT-RDOS-02): Rejects uncited claims, nonexistent chunks, page mismatches, role violations, and SHA-256 tamper."""
    store = AthenaDossierStore()
    pub_chunks = store.ingest_document("filings/zoning.pdf", ["Setback is strictly 45 feet."], role="public")
    internal_chunks = store.ingest_document("vault/secret.md", ["Internal family reserve data."], role="sovereign_internal")
    c_pub = pub_chunks[0]
    c_int = internal_chunks[0]

    # 1. Nominal pass
    verified = CitationVerifier.verify_sections(
        {"Section 1": [f"Setback is 45 feet [{c_pub.chunk_id}:p{c_pub.page_offset}]."]},
        store,
    )
    assert len(verified) == 1
    assert verified[0].chunk_sha256 == c_pub.chunk_sha256

    # 2. Uncited claim -> FAIL-CLOSED
    with pytest.raises(CitationVerificationError, match="Uncited claim"):
        CitationVerifier.verify_sections({"Section 1": ["Claim with zero citations."]}, store)

    # 3. Nonexistent chunk_id -> FAIL-CLOSED
    with pytest.raises(CitationVerificationError, match="nonexistent chunk_id"):
        CitationVerifier.verify_sections({"Section 1": ["Fake citation [ghost_c0001_deadbeef:p1]."]}, store)

    # 4. Page offset mismatch -> FAIL-CLOSED
    with pytest.raises(CitationVerificationError, match="Page offset mismatch"):
        CitationVerifier.verify_sections({"Section 1": [f"Wrong page [{c_pub.chunk_id}:p99]."]}, store)

    # 5. Restricted sovereign_internal chunk cited in client dossier -> FAIL-CLOSED
    with pytest.raises(SecurityBoundaryError, match="restricted role"):
        CitationVerifier.verify_sections({"Section 1": [f"Leaked internal [{c_int.chunk_id}:p1]."]}, store)

    # 6. Post-ingestion in-memory SHA-256 chunk content tamper -> FAIL-CLOSED
    tampered_chunk = replace(c_pub, content="Setback is strictly 15 feet (TAMPERED).")
    store._chunks_by_id[c_pub.chunk_id] = tampered_chunk
    with pytest.raises(CitationVerificationError, match="SHA-256 tamper detected"):
        CitationVerifier.verify_sections(
            {"Section 1": [f"Tampered claim [{c_pub.chunk_id}:p{c_pub.page_offset}]."]},
            store,
        )


def test_loopback_endpoint_and_end_to_end_pipeline(tmp_path: Path):
    """Stage 5 (AT-RDOS-03): Enforces loopback-only endpoint and fail-closed `signed: False` receipt."""
    with pytest.raises(SecurityBoundaryError, match="Zero-Cloud-Spend Invariant Violation"):
        verify_loopback_inference_endpoint("https://api.openai.com/v1")

    md_path, receipt_path, receipt = execute_dossier_pipeline(
        dossier_id="QF-RDOS-TEST-001",
        client_name="Test Counsel LLP",
        title="Municipal Zoning, Post-Quantum Cryptography & Escrow Liability Dossier",
        corpus_documents=_build_demo_corpus(),
        output_dir=tmp_path,
        hard_stops=HardStopGateStatus(),  # All 4 P0 hard stops False -> GATED
    )
    assert md_path.is_file()
    assert receipt_path.is_file()
    assert receipt.invariants["signed"] is False
    assert receipt.invariants["operating_constitution_wasm_verified"] is True
    assert receipt.assurance["qf_a5_signed_provenance"] == "GATED"
    assert receipt.assurance["hard_stops"]["hs_px_pixel_cve_2026_58704_patched"] is True
    assert receipt.assurance["hard_stops"]["as_01_03_account_security_verified"] is True
    assert receipt.assurance["hard_stops"]["pa_llc_finallyfungus_subsistence_verified"] is False
    assert receipt.assurance["hard_stops"]["track_0_reserve_ratio_gte_6m"] is False
    const_wasm = receipt.assurance["operating_constitution_wasm"]
    assert const_wasm["verdict"] == "ADMIT"
    assert const_wasm["wasm_verified"] is True
    assert const_wasm["parity_verified"] is True
    assert receipt.provenance["citations_verified_pct"] == 100.0
    assert receipt.provenance["privacy_filter_redactions"] >= 3
    md_text = md_path.read_text(encoding="utf-8")
    assert "Rahshaun" not in md_text
    assert "/home/quant" not in md_text
    assert "ghp_" not in md_text


def test_dossier_pipeline_enforces_operating_constitution_wasm_fail_closed(tmp_path: Path, monkeypatch):
    """Verifies execute_dossier_pipeline() rejects QF-CAPITAL-01 / QF-OPS-01 breaches and Wasm unavailability."""
    # 1. Under-reserved capital context (R < 6O) -> denied by operating_constitution.wasm
    with pytest.raises(SecurityBoundaryError, match="PROTECT_AND_REBUILD_RESERVES"):
        execute_dossier_pipeline(
            dossier_id="QF-RDOS-CAP-DENY",
            client_name="Test Counsel LLP",
            title="Municipal Zoning, Post-Quantum Cryptography & Escrow Liability Dossier",
            corpus_documents=_build_demo_corpus(),
            output_dir=tmp_path / "cap_deny",
            capital_context={
                "reserves": 4.0,
                "monthly_obligations": 1.0,
                "allocation_amount": 0.0,
                "funding_bucket": "CASH_FLOW_ENGINE",
                "financial_shock": False,
                "discretionary_expansion": False,
            },
        )

    # 2. Sacred Bucket 1 (IRON_RESERVE) drawdown -> denied by operating_constitution.wasm
    with pytest.raises(SecurityBoundaryError, match="IRON_RESERVE_SACRED_LOCK"):
        execute_dossier_pipeline(
            dossier_id="QF-RDOS-IRON-DENY",
            client_name="Test Counsel LLP",
            title="Municipal Zoning, Post-Quantum Cryptography & Escrow Liability Dossier",
            corpus_documents=_build_demo_corpus(),
            output_dir=tmp_path / "iron_deny",
            capital_context={
                "reserves": 10.0,
                "monthly_obligations": 1.0,
                "allocation_amount": 1.0,
                "funding_bucket": "IRON_RESERVE",
                "financial_shock": False,
                "discretionary_expansion": False,
            },
        )

    # 3. Operator fatigue flag -> denied by operating_constitution.wasm (QF-OPS-01)
    with pytest.raises(SecurityBoundaryError, match="OPERATOR_FATIGUE_RECOVERY_REQUIRED"):
        execute_dossier_pipeline(
            dossier_id="QF-RDOS-OPS-DENY",
            client_name="Test Counsel LLP",
            title="Municipal Zoning, Post-Quantum Cryptography & Escrow Liability Dossier",
            corpus_documents=_build_demo_corpus(),
            output_dir=tmp_path / "ops_deny",
            ops_context={
                "continuous_block_minutes": 45,
                "daily_deep_work_hours": 4.0,
                "named_objects_in_block": 1,
                "rest_hours_last_24h": 8.0,
                "operator_fatigue_flag": True,
                "helper_fairness_verified": True,
            },
        )

    # 4. Missing Wasm engine -> fail-closed denial
    import src.operating_constitution as const_mod

    monkeypatch.setattr(const_mod, "get_constitution_wasm_gatekeeper", lambda: None)
    with pytest.raises(SecurityBoundaryError, match="FAIL_CLOSED_WASM_ENGINE_UNAVAILABLE"):
        execute_dossier_pipeline(
            dossier_id="QF-RDOS-NOWASM-DENY",
            client_name="Test Counsel LLP",
            title="Municipal Zoning, Post-Quantum Cryptography & Escrow Liability Dossier",
            corpus_documents=_build_demo_corpus(),
            output_dir=tmp_path / "nowasm_deny",
        )
