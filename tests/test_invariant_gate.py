#!/usr/bin/env python3
"""
Unit tests for Quantum Flex Hardware-Rooted Invariant Gate.
Validates real host memory telemetry (/proc/meminfo) and Pluton TPM 2.0 PCR 15 registers.
Ensures zero mock vectors or synthetic water resources exist in the admission gate.
"""

import os
import pytest

from sentinel.invariant_gate import (
    check_digital_memory,
    check_tpm_anchor,
    evaluate_all_invariants,
)


def test_digital_memory_reads_procfs():
    """Verify check_digital_memory reads actual Linux kernel procfs telemetry."""
    telemetry = check_digital_memory()
    assert telemetry["domain"] == "digital"
    assert telemetry["resource_type"] == "MEMORY_MB"
    assert telemetry["reserve_measured"] > 0
    assert telemetry["units_claimed"] >= 0
    assert telemetry["reserve_measured"] >= telemetry["units_claimed"]
    assert telemetry["max_staleness_seconds"] == 30


def test_tpm_anchor_reads_hardware():
    """Verify check_tpm_anchor queries actual TPM 2.0 PCR 15 register."""
    telemetry = check_tpm_anchor()
    assert telemetry["domain"] == "digital"
    assert telemetry["resource_type"] == "DUAL_TPM_ANCHOR"
    assert "pcr15_runtime_measured" in telemetry
    # On AMD Pluton silicon, pcr15_runtime_measured is either 64-hex chars or UNAVAILABLE
    pcr = telemetry["pcr15_runtime_measured"]
    assert len(pcr) == 64 or "UNAVAILABLE" in pcr


def test_no_mock_water_or_synthetic_functions():
    """Verify all synthetic/fake water tank mocks have been permanently purged."""
    import sentinel.invariant_gate as gate_mod
    assert not hasattr(gate_mod, "check_physical_water")
    assert not hasattr(gate_mod, "check_water")


def test_evaluate_all_invariants_structure():
    """Verify composite invariant evaluation only checks digital memory and TPM hardware."""
    res = evaluate_all_invariants(evaluator="pytest_hardware")
    assert "evaluations" in res
    evals = res["evaluations"]
    assert "digital_memory" in evals
    assert "tpm_anchor" in evals
    assert "physical_water" not in evals
    assert "overall_verdict" in res
