#!/usr/bin/env python3
"""
Unit tests for QuantumFlex Zero-Waste IBM Quantum Pre-Flight Verification Gate.
Guarantees fail-closed local verification before any QPU submission.
"""

import json
import subprocess
import sys
import pytest
from qiskit import QuantumCircuit

from tools.preflight_quantum_circuit import (
    preflight_circuit,
    build_canonical_benchmark_circuit,
    is_clifford_circuit,
    HERON_BASIS_GATES,
    PERMITTED_BACKENDS,
)


def test_canonical_bell_circuit_passes():
    qc = build_canonical_benchmark_circuit("bell_2q")
    cert = preflight_circuit(qc, backend_name="ibm_kingston", max_depth=32, shots=1024)
    assert cert["passed"] is True
    assert cert["status"] == "PREFLIGHT_PASS"
    assert cert["num_qubits"] == 2
    assert cert["clifford_verified"] is True
    assert cert["cz_count"] >= 1
    assert cert["zero_cloud_spend_verified"] is True
    assert len(cert["reasons"]) == 0


def test_canonical_ghz_circuit_passes():
    qc = build_canonical_benchmark_circuit("ghz_3q")
    cert = preflight_circuit(qc, backend_name="ibm_marrakesh", max_depth=32, shots=2048)
    assert cert["passed"] is True
    assert cert["status"] == "PREFLIGHT_PASS"
    assert cert["num_qubits"] == 3
    assert cert["clifford_verified"] is True
    assert cert["cz_count"] >= 2
    assert cert["isa_depth"] <= 32


def test_canonical_mermin_circuit_passes():
    qc = build_canonical_benchmark_circuit("mermin_xxx")
    cert = preflight_circuit(qc, backend_name="ibm_fez", max_depth=32, shots=4096)
    assert cert["passed"] is True
    assert cert["status"] == "PREFLIGHT_PASS"
    assert cert["num_qubits"] == 3
    assert cert["clifford_verified"] is True


def test_unauthorized_backend_rejected():
    qc = build_canonical_benchmark_circuit("bell_2q")
    cert = preflight_circuit(qc, backend_name="unauthorized_cloud_qpu", max_depth=32)
    assert cert["passed"] is False
    assert cert["status"] == "PREFLIGHT_REJECT"
    assert any("not in authorized list" in r for r in cert["reasons"])


def test_depth_threshold_exceeded_rejected():
    qc = build_canonical_benchmark_circuit("ghz_3q")
    # Setting threshold to 2 should fail since GHZ Heron transpiled depth is ~10
    cert = preflight_circuit(qc, backend_name="ibm_kingston", max_depth=2)
    assert cert["passed"] is False
    assert cert["status"] == "PREFLIGHT_REJECT"
    assert any("exceeds maximum allowable threshold" in r for r in cert["reasons"])


def test_excessive_shots_rejected():
    qc = build_canonical_benchmark_circuit("bell_2q")
    cert = preflight_circuit(qc, backend_name="ibm_kingston", shots=10000)
    assert cert["passed"] is False
    assert cert["status"] == "PREFLIGHT_REJECT"
    assert any("exceeds maximum budget quota" in r for r in cert["reasons"])


def test_non_clifford_circuit_detection():
    # T gate (pi/8 rotation) is non-Clifford
    qc = QuantumCircuit(2, 2)
    qc.h(0)
    qc.t(0)
    qc.cx(0, 1)
    qc.measure([0, 1], [0, 1])

    assert is_clifford_circuit(qc) is False
    cert = preflight_circuit(qc, backend_name="ibm_kingston", check_clifford=True)
    assert cert["clifford_verified"] is False
    # Preflight should still pass structural checks if depth/shots/backend are valid
    assert cert["passed"] is True


def test_cli_execution_json_output():
    cmd = [
        sys.executable,
        "tools/preflight_quantum_circuit.py",
        "--circuit",
        "ghz_3q",
        "--backend",
        "ibm_kingston",
        "--json",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(res.stdout)
    assert data["passed"] is True
    assert data["status"] == "PREFLIGHT_PASS"
    assert data["circuit_name"] == "ghz_3q_tripartite"


def test_cli_execution_rejection_exit_code():
    cmd = [
        sys.executable,
        "tools/preflight_quantum_circuit.py",
        "--circuit",
        "ghz_3q",
        "--backend",
        "invalid_backend",
        "--json",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 1
    data = json.loads(res.stdout)
    assert data["passed"] is False
    assert data["status"] == "PREFLIGHT_REJECT"
