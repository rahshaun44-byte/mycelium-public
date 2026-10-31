#!/usr/bin/env python3
"""
Unit & Adversarial Verification Suite for the QuantumFlex Operating Constitution.
Tests all four permanent Mycelium controls:
  - QF-CAPITAL-01 : Six-month reserve gate (R >= 6O), post-allocation floor, Bucket 1 lock
  - QF-PRIVACY-01 : Local-only inference ($0.00 cloud), provenance, zero dollar leak
  - QF-AUTH-01    : Mandatory human authorization for consequential financial actions
  - QF-OPS-01     : Operator & helper workload sustainability monitoring
Verifies bit-for-bit decision parity between Python and compiled OPA Wasm (`operating_constitution.wasm`).
"""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any, Dict

import pytest

from src.operating_constitution import (
    evaluate_operating_constitution,
    evaluate_qf_auth_01,
    evaluate_qf_capital_01,
    evaluate_qf_ops_01,
    evaluate_qf_privacy_01,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _baseline_context() -> Dict[str, Any]:
    return {
        "capital": {
            "reserves": 90_000.0,
            "monthly_obligations": 10_000.0,
            "allocation_amount": 15_000.0,
            "funding_bucket": "CASH_FLOW_ENGINE",
            "financial_shock": False,
            "discretionary_expansion": True,
        },
        "privacy": {
            "inference_endpoint": "127.0.0.1:11434",
            "cloud_spend_usd": 0.0,
            "external_egress": False,
            "data_classification": "proprietary_research",
            "provenance_verified": True,
            "raw_household_dollars_exposed": False,
            "ambient_identifiers_present": False,
        },
        "auth": {
            "consequential_financial_action": True,
            "human_authorized": True,
            "actor_type": "human_operator",
            "authorizer_id": "rahshaun_chambers",
            "auth_credential": "CredTwoManAttestation",
            "idempotency_key": str(uuid.uuid4()),
            "usdc_decimals": 6,
        },
        "ops": {
            "continuous_block_minutes": 75,
            "daily_deep_work_hours": 6.0,
            "named_objects_in_block": 1,
            "rest_hours_last_24h": 8.0,
            "operator_fatigue_flag": False,
            "helper_fairness_verified": True,
        },
    }


def test_nominal_constitution_admits_with_wasm_parity():
    ctx = _baseline_context()
    res = evaluate_operating_constitution(ctx)
    assert res["allow"] is True
    assert res["verdict"] == "ADMIT"
    assert res["wasm_verified"] is True
    assert res["parity_verified"] is True

    # Verify dollars stay off the page: raw figures (90000, 10000, 15000) never echoed
    serialized = json.dumps(res)
    assert "90000" not in serialized
    assert "15000" not in serialized
    cap_details = res["controls"]["QF-CAPITAL-01"]["details"]
    assert cap_details["coverage_months"] == 9.0
    assert cap_details["post_allocation_months"] == 7.5


def test_empty_and_malformed_inputs_fail_closed_with_wasm_parity():
    for bad in ({}, None, {"capital": None, "privacy": [], "auth": "bad", "ops": 123}):
        res = evaluate_operating_constitution(bad)  # type: ignore[arg-type]
        assert res["allow"] is False
        assert res["verdict"] == "DENY"
        assert res["wasm_verified"] is True
        assert res["parity_verified"] is True


# ── QF-CAPITAL-01 Boundary Tests ─────────────────────────────────────────────
@pytest.mark.parametrize(
    "patch,expected_allow,expected_decision",
    [
        ({"reserves": 55_000.0, "allocation_amount": 0.0, "discretionary_expansion": False}, False, "PROTECT_AND_REBUILD_RESERVES"),
        ({"reserves": 60_000.0, "allocation_amount": 0.0, "discretionary_expansion": True}, False, "MAINTAIN_RESERVE_RESTRICT_EXPANSION"),
        ({"reserves": 60_000.0, "allocation_amount": 1.0, "discretionary_expansion": False}, False, "MAINTAIN_RESERVE_RESTRICT_EXPANSION"),
        ({"reserves": 60_000.0, "allocation_amount": 0.0, "discretionary_expansion": False}, True, "MAINTAIN_RESERVE_RESTRICT_EXPANSION"),
        ({"reserves": 70_000.0, "allocation_amount": 15_000.0}, False, "POST_ALLOCATION_RESERVE_BREACH"),
        ({"reserves": 75_000.0, "allocation_amount": 15_000.0}, True, "EVALUATE_FUNDED_OPPORTUNITY"),
        ({"funding_bucket": "IRON_RESERVE", "allocation_amount": 100.0}, False, "IRON_RESERVE_SACRED_LOCK"),
        ({"funding_bucket": "IRON_RESERVE", "allocation_amount": 0.0, "discretionary_expansion": True}, False, "IRON_RESERVE_SACRED_LOCK"),
        ({"financial_shock": True}, False, "FREEZE_DISCRETIONARY_SPENDING"),
        ({"monthly_obligations": 0.0}, False, "INVALID_CAPITAL_INPUTS"),
        ({"reserves": -1.0}, False, "INVALID_CAPITAL_INPUTS"),
        ({"reserves": True}, False, "INVALID_CAPITAL_INPUTS"),
        ({"reserves": float("nan")}, False, "INVALID_CAPITAL_INPUTS"),
    ],
)
def test_qf_capital_01_matrix(patch, expected_allow, expected_decision):
    ctx = _baseline_context()
    ctx["capital"].update(patch)
    res = evaluate_operating_constitution(ctx)
    assert res["parity_verified"] is True
    ctrl = res["controls"]["QF-CAPITAL-01"]
    assert ctrl["allow"] is expected_allow
    assert ctrl["decision"] == expected_decision
    assert res["allow"] is expected_allow


# ── QF-PRIVACY-01 Boundary Tests ─────────────────────────────────────────────
@pytest.mark.parametrize(
    "patch,expected_allow,expected_decision",
    [
        ({"inference_endpoint": "http://127.0.0.1:11434"}, True, "ADMIT_SOVEREIGN_LOCAL"),
        ({"inference_endpoint": "https://api.openai.com/v1"}, False, "NON_LOOPBACK_ENDPOINT_DENIED"),
        ({"inference_endpoint": "0.0.0.0:11434"}, False, "NON_LOOPBACK_ENDPOINT_DENIED"),
        ({"cloud_spend_usd": 0.0001}, False, "ZERO_CLOUD_SPEND_VIOLATION"),
        ({"raw_household_dollars_exposed": True}, False, "HOUSEHOLD_FINANCIAL_EXPOSURE_DENIED"),
        ({"ambient_identifiers_present": True}, False, "AMBIENT_DATA_COLLECTION_DENIED"),
        ({"data_classification": "household_financial", "external_egress": True}, False, "CONFIDENTIAL_EGRESS_DENIED"),
        ({"data_classification": "client_confidential", "external_egress": True}, False, "CONFIDENTIAL_EGRESS_DENIED"),
        ({"data_classification": "public", "external_egress": True}, True, "ADMIT_SOVEREIGN_LOCAL"),
        ({"provenance_verified": False}, False, "UNVERIFIED_DOCUMENT_PROVENANCE"),
        (
            {"telemetry_frame": {"bssid": "AA:BB:CC:00:11:22", "ssid": "NeighborWiFi"}},
            False,
            "AMBIENT_DATA_COLLECTION_DENIED",
        ),
    ],
)
def test_qf_privacy_01_matrix(patch, expected_allow, expected_decision):
    ctx = _baseline_context()
    ctx["privacy"].update(patch)
    res = evaluate_operating_constitution(ctx)
    assert res["parity_verified"] is True
    ctrl = res["controls"]["QF-PRIVACY-01"]
    assert ctrl["allow"] is expected_allow
    assert ctrl["decision"] == expected_decision
    assert res["allow"] is expected_allow


# ── QF-AUTH-01 Boundary Tests ────────────────────────────────────────────────
@pytest.mark.parametrize(
    "patch,expected_allow,expected_decision",
    [
        ({"consequential_financial_action": False, "actor_type": "autonomous_agent", "human_authorized": False}, True, "NON_FINANCIAL_ACTION_PERMITTED"),
        ({"actor_type": "autonomous_agent"}, False, "AUTONOMOUS_FINANCIAL_EXECUTION_FORBIDDEN"),
        ({"human_authorized": False}, False, "MISSING_HUMAN_OPERATOR_APPROVAL"),
        ({"authorizer_id": "unverified_user"}, False, "UNVERIFIED_AUTHORIZER_IDENTITY"),
        ({"auth_credential": "CredNone"}, False, "INSUFFICIENT_CRYPTOGRAPHIC_CREDENTIAL"),
        ({"idempotency_key": "not-a-uuid"}, False, "MISSING_DETERMINISTIC_IDEMPOTENCY_KEY"),
        ({"usdc_decimals": 18}, False, "USDC_SIX_DECIMAL_INVARIANT_VIOLATION"),
        ({"authorizer_id": "qf-operator-key", "auth_credential": "TitanM2StrongBox"}, True, "HUMAN_AUTHORIZATION_VERIFIED"),
    ],
)
def test_qf_auth_01_matrix(patch, expected_allow, expected_decision):
    ctx = _baseline_context()
    ctx["auth"].update(patch)
    res = evaluate_operating_constitution(ctx)
    assert res["parity_verified"] is True
    ctrl = res["controls"]["QF-AUTH-01"]
    assert ctrl["allow"] is expected_allow
    assert ctrl["decision"] == expected_decision
    assert res["allow"] is expected_allow


# ── QF-OPS-01 Boundary Tests ─────────────────────────────────────────────────
@pytest.mark.parametrize(
    "patch,expected_allow,expected_decision",
    [
        ({"continuous_block_minutes": 90, "daily_deep_work_hours": 8.0, "rest_hours_last_24h": 7.0}, True, "SUSTAINABLE_CADENCE_VERIFIED"),
        ({"operator_fatigue_flag": True}, False, "OPERATOR_FATIGUE_RECOVERY_REQUIRED"),
        ({"helper_fairness_verified": False}, False, "HELPER_PROTECTION_VIOLATION"),
        ({"rest_hours_last_24h": 5.5}, False, "REST_DEFICIT_RECOVERY_REQUIRED"),
        ({"daily_deep_work_hours": 9.5}, False, "DAILY_WORKLOAD_CEILING_EXCEEDED"),
        ({"continuous_block_minutes": 120}, False, "DEEP_WORK_BLOCK_LIMIT_EXCEEDED"),
        ({"named_objects_in_block": 2}, False, "SINGLE_OBJECT_FOCUS_VIOLATION"),
        ({"continuous_block_minutes": -5}, False, "INVALID_OPS_INPUTS"),
    ],
)
def test_qf_ops_01_matrix(patch, expected_allow, expected_decision):
    ctx = _baseline_context()
    ctx["ops"].update(patch)
    res = evaluate_operating_constitution(ctx)
    assert res["parity_verified"] is True
    ctrl = res["controls"]["QF-OPS-01"]
    assert ctrl["allow"] is expected_allow
    assert ctrl["decision"] == expected_decision
    assert res["allow"] is expected_allow


def test_missing_wasm_engine_fails_closed(monkeypatch):
    import src.operating_constitution as const_mod

    monkeypatch.setattr(const_mod, "get_constitution_wasm_gatekeeper", lambda: None)
    res = evaluate_operating_constitution(_baseline_context(), require_wasm=True)
    assert res["allow"] is False
    assert res["verdict"] == "DENY"
    assert res["reason"] == "FAIL_CLOSED_WASM_ENGINE_UNAVAILABLE"


def test_opa_rego_unit_suite_passes():
    opa_bin = shutil.which("opa") or "/home/quant/.local/bin/opa"
    assert Path(opa_bin).is_file(), f"OPA binary missing at {opa_bin}"
    proc = subprocess.run(
        [
            opa_bin,
            "test",
            str(REPO_ROOT / "sentinel" / "policies" / "operating_constitution.rego"),
            str(REPO_ROOT / "sentinel" / "policies" / "operating_constitution_test.rego"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"OPA Rego test suite failed:\n{proc.stdout}\n{proc.stderr}"
    assert "PASS: 23/23" in proc.stdout
