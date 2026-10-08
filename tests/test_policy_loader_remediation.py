#!/usr/bin/env python3
"""
QuantumFlex Policy Loader & Admission Architecture Regression Suite.
Validates the 11 authoritative failure-mode and admission conditions:
  1. Missing Rego module -> POLICY_MISSING, no admission
  2. Invalid Rego syntax -> POLICY_INVALID, no admission
  3. OPA executable unavailable -> POLICY_UNAVAILABLE, no admission
  4. OPA evaluation failure -> POLICY_EVALUATION_ERROR, no admission
  5. Empty CBOM -> DENIED / UNVERIFIED
  6. Missing requested_profile -> DENIED / INVALID
  7. Unknown requested_profile -> DENIED / INVALID
  8. Missing threat_flags -> UNVERIFIED, never safe
  9. Valid FIPS CBOM -> VERIFIED and COMPLIANT
  10. Toxic algorithm -> TOXIC / DENIED
  11. Python mirror enabled (QF_ALLOW_POLICY_MIRROR=true) -> DEVELOPMENT_ONLY, never VERIFIED/ADMITTED.

Core Governance Rule:
  ABSENCE OF EVIDENCE MUST NEVER BECOME VERIFIED.
  PRESENCE IS NOT PROOF.
"""

import os
import sys
import tempfile
import subprocess
from pathlib import Path
import pytest

# Ensure qf repository is accessible for policy_engine tests
QF_DIR = Path("/home/quant/Documents/qf")
if str(QF_DIR) not in sys.path:
    sys.path.insert(0, str(QF_DIR))

from policy_engine import (
    QuantumPolicyEngine,
    STATE_POLICY_MISSING,
    STATE_POLICY_INVALID,
    STATE_POLICY_UNAVAILABLE,
    STATE_POLICY_EVALUATION_ERROR,
    STATE_POLICY_VERIFIED,
    STATE_DEVELOPMENT_ONLY,
)
from sentinel.policies.wasm_gatekeeper import get_membrane_wasm_gatekeeper


@pytest.fixture
def membrane_gate():
    gate = get_membrane_wasm_gatekeeper()
    assert gate is not None, "Failed to load MembraneHealthWasmGatekeeper"
    return gate


@pytest.fixture
def valid_quantum_input():
    return {
        "caller": "Quantum_Flex_Mission_Control",
        "shots": 1024,
        "qubits": 4,
        "depth": 20,
        "backend": "ibm_marrakesh",
    }


# ── Scenario 1: Missing Rego module ───────────────────────────────────────────
def test_scenario_1_missing_rego_module(valid_quantum_input):
    """Missing policy file yields POLICY_MISSING and DENY (no admission)."""
    engine = QuantumPolicyEngine(policy_path=Path("/tmp/nonexistent_policy_module.rego"))
    res = engine.authorize_job(valid_quantum_input)
    assert res["verification_state"] == STATE_POLICY_MISSING
    assert res["allow"] is False
    assert res["decision"] == "DENY"
    assert any("missing" in r.lower() for r in res["reasons"])


# ── Scenario 2: Invalid Rego syntax ───────────────────────────────────────────
def test_scenario_2_invalid_rego_syntax(tmp_path, valid_quantum_input):
    """Malformed/syntactically invalid Rego policy yields POLICY_INVALID and DENY."""
    bad_policy = tmp_path / "bad_syntax.rego"
    bad_policy.write_text("package quantum.admission\ndefault allow := {{{\n")
    engine = QuantumPolicyEngine(policy_path=bad_policy)
    res = engine.authorize_job(valid_quantum_input)
    assert res["verification_state"] == STATE_POLICY_INVALID
    assert res["allow"] is False
    assert res["decision"] == "DENY"


# ── Scenario 3: OPA executable unavailable ────────────────────────────────────
def test_scenario_3_opa_unavailable(monkeypatch, valid_quantum_input):
    """Missing OPA binary yields POLICY_UNAVAILABLE and DENY."""
    import policy_engine
    monkeypatch.setattr(policy_engine, "OPA_BINARY", Path("/tmp/nonexistent_opa_bin"))
    engine = QuantumPolicyEngine()
    res = engine.authorize_job(valid_quantum_input)
    assert res["verification_state"] == STATE_POLICY_UNAVAILABLE
    assert res["allow"] is False
    assert res["decision"] == "DENY"
    assert any("unavailable" in r.lower() for r in res["reasons"])


# ── Scenario 4: OPA evaluation failure ─────────────────────────────────────────
def test_scenario_4_opa_eval_error(monkeypatch, valid_quantum_input):
    """OPA runtime evaluation error yields POLICY_EVALUATION_ERROR and DENY."""
    import policy_engine

    def mock_eval(*args, **kwargs):
        raise subprocess.CalledProcessError(
            1, ["opa"], stderr="Internal OPA evaluation engine crash"
        )

    engine = QuantumPolicyEngine()
    monkeypatch.setattr(engine, "evaluate_with_opa_cli", mock_eval)
    res = engine.authorize_job(valid_quantum_input)
    assert res["verification_state"] == STATE_POLICY_EVALUATION_ERROR
    assert res["allow"] is False
    assert res["decision"] == "DENY"


# ── Scenario 5: Empty CBOM ────────────────────────────────────────────────────
def test_scenario_5_empty_cbom(membrane_gate):
    """Empty or unpopulated CBOM fails closed to TOXIC/MISSING, never COMPLIANT."""
    cbom = {}
    verdict = membrane_gate.evaluate_verdict(cbom, threat_flags={"ML_KEM_COMPROMISED": False})
    assert verdict["node_status"] in {"DENIED", "TOXIC"}
    assert verdict["verification_state"] in {"MISSING", "UNVERIFIED"}
    assert verdict["node_status"] != "COMPLIANT"
    assert any("missing" in r.lower() for r in verdict.get("deny_reasons", []))


# ── Scenario 6: Missing requested_profile ─────────────────────────────────────
def test_scenario_6_missing_requested_profile(membrane_gate):
    """CBOM without requested_profile denies admission with explicit reason."""
    cbom = {
        "metadata": {"timestamp": 1728390000},
        "components": [
            {
                "type": "crypto-asset",
                "name": "ML-KEM-768",
                "cryptoProperties": {
                    "assetType": "algorithm",
                    "algorithmProperties": {"algorithm": "ML-KEM-768"},
                },
            }
        ],
    }
    verdict = membrane_gate.evaluate_verdict(cbom, threat_flags={"ML_KEM_COMPROMISED": False})
    assert verdict["node_status"] in {"DENIED", "TOXIC"}
    assert "Missing compliance profile" in verdict.get("deny_reasons", [])
    assert verdict["node_status"] != "COMPLIANT"


# ── Scenario 7: Unknown requested_profile ─────────────────────────────────────
def test_scenario_7_unknown_requested_profile(membrane_gate):
    """CBOM with unsupported compliance profile denies admission."""
    cbom = {
        "requested_profile": "unsupported_futuristic_profile",
        "metadata": {"timestamp": 1728390000},
        "components": [
            {
                "type": "crypto-asset",
                "name": "ML-KEM-768",
                "cryptoProperties": {
                    "assetType": "algorithm",
                    "algorithmProperties": {"algorithm": "ML-KEM-768"},
                },
            }
        ],
    }
    verdict = membrane_gate.evaluate_verdict(cbom, threat_flags={"ML_KEM_COMPROMISED": False})
    assert verdict["node_status"] in {"DENIED", "TOXIC"}
    assert "Unknown compliance profile" in verdict.get("deny_reasons", [])
    assert verdict["node_status"] != "COMPLIANT"


# ── Scenario 8: Missing threat_flags ──────────────────────────────────────────
def test_scenario_8_missing_threat_flags(membrane_gate):
    """Absence of threat feed telemetry fails closed to UNVERIFIED (never assumed safe)."""
    cbom = {
        "requested_profile": "agility",
        "metadata": {"timestamp": 1728390000},
        "components": [
            {
                "type": "crypto-asset",
                "name": "ML-KEM-768",
                "cryptoProperties": {
                    "assetType": "algorithm",
                    "algorithmProperties": {"algorithm": "ML-KEM-768"},
                },
            }
        ],
    }
    # Pass empty threat flags
    verdict = membrane_gate.evaluate_verdict(cbom, threat_flags={})
    assert verdict["node_status"] in {"DENIED", "TOXIC"}
    assert any("threat feed unverified" in r.lower() for r in verdict.get("deny_reasons", []))
    assert verdict["node_status"] != "COMPLIANT"


# ── Scenario 9: Valid FIPS CBOM ───────────────────────────────────────────────
def test_scenario_9_valid_fips_cbom(membrane_gate):
    """Conforming agility/FIPS CBOM with active clean threat feed yields COMPLIANT / VERIFIED."""
    cbom = {
        "requested_profile": "agility",
        "metadata": {"timestamp": 1728390000},
        "components": [
            {
                "type": "crypto-asset",
                "name": "ML-KEM-768",
                "cryptoProperties": {
                    "assetType": "algorithm",
                    "algorithmProperties": {"algorithm": "ML-KEM-768"},
                },
            }
        ],
    }
    verdict = membrane_gate.evaluate_verdict(
        cbom,
        threat_flags={"ML_KEM_COMPROMISED": False, "FRODOKEM_COMPROMISED": False},
    )
    assert verdict["node_status"] == "COMPLIANT"
    assert verdict["verification_state"] == "VERIFIED"
    assert verdict["toxic_count"] == 0


# ── Scenario 10: Toxic algorithm ──────────────────────────────────────────────
def test_scenario_10_toxic_algorithm(membrane_gate):
    """Compromised/prohibited algorithm (RSA-1024) trips status to TOXIC."""
    cbom = {
        "requested_profile": "agility",
        "metadata": {"timestamp": 1728390000},
        "components": [
            {
                "type": "crypto-asset",
                "name": "RSA-1024",
                "cryptoProperties": {
                    "assetType": "algorithm",
                    "algorithmProperties": {"algorithm": "RSA-1024"},
                },
            }
        ],
    }
    verdict = membrane_gate.evaluate_verdict(
        cbom,
        threat_flags={"ML_KEM_COMPROMISED": False, "FRODOKEM_COMPROMISED": False},
    )
    assert verdict["node_status"] == "TOXIC"
    assert verdict["toxic_count"] > 0


# ── Scenario 11: Python mirror enabled (QF_ALLOW_POLICY_MIRROR=true) ───────────
def test_scenario_11_python_mirror_enabled(monkeypatch, valid_quantum_input):
    """Enabling QF_ALLOW_POLICY_MIRROR=true marks DEVELOPMENT_ONLY and strictly DENIES admission."""
    import policy_engine
    monkeypatch.setattr(policy_engine, "OPA_BINARY", Path("/tmp/nonexistent_opa_bin"))
    monkeypatch.setenv("QF_ALLOW_POLICY_MIRROR", "true")

    engine = QuantumPolicyEngine()
    res = engine.authorize_job(valid_quantum_input)

    assert res["verification_state"] == STATE_DEVELOPMENT_ONLY
    assert res["allow"] is False
    assert res["decision"] == "DENY"
    assert res["evaluator"] == "python_mirror_DEVELOPMENT_ONLY"
    assert res["degraded"] is True
    assert any("admission prohibited" in r for r in res["reasons"])


# ── Scenario 12: Stale telemetry fails closed ─────────────────────────────────
def test_scenario_12_stale_telemetry_fails_closed():
    """Stale telemetry exceeding freshness SLA strictly fails closed to DENY."""
    import time
    from sentinel.policies.wasm_gatekeeper import get_reserve_wasm_gatekeeper
    reserve_gate = get_reserve_wasm_gatekeeper()
    assert reserve_gate is not None

    payload = {
        "domain": "digital",
        "resource_type": "SYSTEM_SOLVENCY",
        "available": 16384.0,
        "obligated": 8192.0,
        "telemetry_timestamp": int(time.time()) - 300,  # 5 minutes stale
        "max_staleness_seconds": 30,
    }
    allow, verdict, reason = reserve_gate.evaluate_invariant(payload)
    assert allow is False
    assert verdict == "DENY"
    assert "stale" in reason.lower()


# ── Scenario 13: Nonexistent and empty ledger fail closed (LDG-01) ─────────────
def test_scenario_13_absent_and_empty_ledger_fail_closed(tmp_path):
    """Nonexistent and zero-entry ledgers strictly return valid=False (LDG-01)."""
    from ledger import EvidenceLedger

    # 1. Nonexistent file
    absent_path = tmp_path / "nonexistent_ledger.jsonl"
    ledger_absent = EvidenceLedger(filepath=absent_path)
    valid, errors = ledger_absent.verify_integrity()
    assert valid is False
    assert any("does not exist" in e.lower() for e in errors)

    # 2. Empty file (0 entries)
    empty_path = tmp_path / "empty_ledger.jsonl"
    empty_path.write_text("")
    ledger_empty = EvidenceLedger(filepath=empty_path)
    valid, errors = ledger_empty.verify_integrity()
    assert valid is False
    assert any("zero entries" in e.lower() for e in errors)


# ── Scenario 14: Database offline fails closed (INV-01) ───────────────────────
def test_scenario_14_database_offline_fails_closed(monkeypatch):
    """Database offline conditions produce ERROR_DB_OFFLINE and fail closed to DENY."""
    import sentinel.invariant_gate as ig

    def mock_db_conn(*args, **kwargs):
        raise ig.DatabaseUnavailableError("Simulated database network partition")

    monkeypatch.setattr(ig, "get_db_connection", mock_db_conn)
    telemetry = ig.check_tpm_anchor()
    assert telemetry["ledger_tip"] == "ERROR_DB_OFFLINE"

    # Evaluate against invariant policy
    allow, verdict, reason = ig.query_opa_invariant(telemetry)
    assert allow is False
    assert verdict in {"DENY", "ANCHOR_DESYNC"}


# ── Scenario 15: PCR 15 extension failure fails closed (QFX-01) ───────────────
def test_scenario_15_pcr_extension_failure_fails_closed(monkeypatch, tmp_path):
    """Failure to extend Pluton TPM PCR 15 must raise RuntimeError and prevent completion."""
    import qflex_quantum

    orig_run = subprocess.run

    def mock_run(cmd, *args, **kwargs):
        if len(cmd) > 0 and "tpm2_pcrextend" in cmd[0]:
            raise subprocess.CalledProcessError(1, cmd, stderr="Simulated TPM NV/PCR error")
        return orig_run(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", mock_run)
    out_file = str(tmp_path / "entropy_test.hex")

    with pytest.raises(RuntimeError) as exc_info:
        qflex_quantum.extract_quantum_entropy(
            target="local",
            shots=64,
            qubits=2,
            extend_pcr=True,
            out_file=out_file,
        )

    assert "TPM PCR 15 extension failed" in str(exc_info.value)
