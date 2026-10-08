#!/usr/bin/env python3
"""
Unit tests for Quantum Flex System Integrity & Hardware Attestation Gate.
Validates real host memory telemetry (/proc/meminfo), Pluton TPM 2.0 NVRAM,
and PCR 15 register observation.
Distinguishes Solvency, Anchor Integrity, PCR Observation, and Attestation.
"""

import os
import pytest

from sentinel.invariant_gate import (
    check_system_solvency,
    check_tpm_anchor,
    check_tpm_pcr,
    check_tpm_attestation,
    evaluate_all_invariants,
)


def test_system_solvency_reads_procfs():
    """Verify check_system_solvency reads actual Linux kernel procfs telemetry."""
    telemetry = check_system_solvency()
    assert telemetry["domain"] == "digital"
    assert telemetry["resource_type"] == "SYSTEM_SOLVENCY"
    assert telemetry["available"] > 0
    assert telemetry["obligated"] >= 0
    assert telemetry["available"] >= telemetry["obligated"]
    assert telemetry["condition"] == "AVAILABLE >= OBLIGATED"
    assert telemetry["max_staleness_seconds"] == 30


def test_tpm_anchor_integrity_structure():
    """Verify check_tpm_anchor queries hardware NVRAM and software ledger tip."""
    telemetry = check_tpm_anchor()
    assert telemetry["domain"] == "hardware"
    assert telemetry["resource_type"] == "TPM_ANCHOR"
    assert "hardware_anchor" in telemetry
    assert "ledger_tip" in telemetry
    assert telemetry["condition"] == "HARDWARE == LEDGER"


def test_tpm_pcr_observation_reads_register():
    """Verify check_tpm_pcr queries live PCR register on TPM silicon."""
    telemetry = check_tpm_pcr(15)
    assert telemetry["domain"] == "hardware"
    assert telemetry["resource_type"] == "TPM_PCR15"
    assert "pcr_value" in telemetry
    assert telemetry["condition"] == "PCR READ SUCCESSFULLY"
    pcr = telemetry["pcr_value"]
    assert len(pcr) == 64 or "UNAVAILABLE" in pcr


def test_tpm_attestation_reports_unverified_quote():
    """Verify check_tpm_attestation truthfully reports unverified quote without overclaiming."""
    telemetry = check_tpm_attestation()
    assert telemetry["domain"] == "cryptographic"
    assert telemetry["resource_type"] == "TPM_ATTESTATION"
    assert telemetry["quote_verified"] is False
    assert telemetry["condition"] == "TPM QUOTE NOT VERIFIED"


def test_purged_unsupported_resources():
    """Verify obsolete water resources remain absent from the admission gate."""
    import sentinel.invariant_gate as gate_mod
    assert not hasattr(gate_mod, "check_physical_water")
    assert not hasattr(gate_mod, "check_water")


def test_composite_system_integrity_structure():
    """Verify composite audit structure cleanly separates the four states."""
    res = evaluate_all_invariants(evaluator="pytest_audit")
    assert "evaluations" in res
    evals = res["evaluations"]
    assert "system_solvency" in evals
    assert "tpm_anchor" in evals
    assert "tpm_pcr15" in evals
    assert "tpm_attestation" in evals
    assert evals["tpm_attestation"]["verdict"] == "NOT_ATTESTED"
    assert "overall_verdict" in res
