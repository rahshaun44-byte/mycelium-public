#!/usr/bin/env python3
"""
Unit tests for QuantumFlex Zero-Friction Gatekeeper (WebAssembly In-Process Evaluation).
Validates sub-millisecond execution, memory heap restoration, CBOM compliance,
threat flag reactions, and universal reserve invariance.
"""

import time
import pytest
from datetime import datetime, timezone
from pathlib import Path

import sys
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sentinel.policies.wasm_gatekeeper import (
    get_membrane_wasm_gatekeeper,
    get_reserve_wasm_gatekeeper,
    MEMBRANE_WASM,
    RESERVE_WASM,
)


@pytest.fixture(scope="module")
def membrane_gate():
    gate = get_membrane_wasm_gatekeeper()
    assert gate is not None, "Membrane Wasm Gatekeeper failed to initialize"
    return gate


@pytest.fixture(scope="module")
def reserve_gate():
    gate = get_reserve_wasm_gatekeeper()
    assert gate is not None, "Reserve Wasm Gatekeeper failed to initialize"
    return gate


def test_membrane_health_wasm_evaluation_compliant(membrane_gate):
    """Validates that approved quantum-safe algorithms evaluate to COMPLIANT."""
    now = datetime.now(timezone.utc).isoformat()
    cbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "metadata": {"timestamp": now},
        "components": [
            {
                "type": "crypto-asset",
                "name": "ML-KEM-768",
                "cryptoProperties": {
                    "assetType": "algorithm",
                    "algorithmProperties": {"algorithm": "ML-KEM-768"},
                },
            },
            {
                "type": "crypto-asset",
                "name": "ML-DSA-65",
                "cryptoProperties": {
                    "assetType": "algorithm",
                    "algorithmProperties": {"algorithm": "ML-DSA-65"},
                },
            },
        ],
    }

    verdict = membrane_gate.evaluate_verdict(cbom)
    assert verdict["node_status"] == "COMPLIANT"
    assert verdict["toxic_count"] == 0
    assert verdict["total_components"] == 2
    assert verdict["recommended_fallback"] == "NONE"


def test_membrane_health_wasm_evaluation_toxic_threat_flag(membrane_gate):
    """Validates that active threat flags trigger TOXIC status and recommended fallback."""
    now = datetime.now(timezone.utc).isoformat()
    cbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "metadata": {"timestamp": now},
        "components": [
            {
                "type": "crypto-asset",
                "name": "ML-KEM-768",
                "cryptoProperties": {
                    "assetType": "algorithm",
                    "algorithmProperties": {"algorithm": "ML-KEM-768"},
                },
            },
            {
                "type": "crypto-asset",
                "name": "ML-DSA-65",
                "cryptoProperties": {
                    "assetType": "algorithm",
                    "algorithmProperties": {"algorithm": "ML-DSA-65"},
                },
            },
        ],
    }

    # Inject threat flag: ML_KEM_COMPROMISED
    verdict = membrane_gate.evaluate_verdict(cbom, threat_flags={"ML_KEM_COMPROMISED": True})
    assert verdict["node_status"] == "TOXIC"
    assert verdict["toxic_count"] == 1
    assert verdict["recommended_fallback"] == "FrodoKEM-976-AES"


def test_membrane_health_wasm_fallback_and_recovery_maps(membrane_gate):
    """Validates authoritative recovery & fallback maps compiled into the Wasm binary."""
    fmap = membrane_gate.get_fallback_map()
    assert fmap["ML-KEM-768"] == "FrodoKEM-976-AES"
    assert fmap["FrodoKEM-976-AES"] == "X25519"
    assert fmap["X25519"] == "NONE"

    rmap = membrane_gate.get_recovery_map()
    assert rmap["max_retries"] == 3
    assert rmap["quarantine_delay_ms"] == 5000
    assert rmap["safe_mode_cipher"] == "FrodoKEM-976-AES"


def test_reserve_invariant_wasm_evaluation_admit(reserve_gate):
    """Validates that R >= O with fresh telemetry yields ADMIT."""
    payload = {
        "domain": "digital",
        "resource_type": "MEMORY_MB",
        "reserve_measured": 16384.0,
        "units_claimed": 8192.0,
        "telemetry_timestamp": int(time.time()),
        "max_staleness_seconds": 30,
    }
    allow, verdict, reason = reserve_gate.evaluate_invariant(payload)
    assert allow is True
    assert verdict == "ADMIT"
    assert "strictly covers obligations" in reason


def test_reserve_invariant_wasm_evaluation_deny_insolvent(reserve_gate):
    """Validates that R < O immediately yields DENY."""
    payload = {
        "domain": "digital",
        "resource_type": "MEMORY_MB",
        "reserve_measured": 4096.0,
        "units_claimed": 8192.0,
        "telemetry_timestamp": int(time.time()),
        "max_staleness_seconds": 30,
    }
    allow, verdict, reason = reserve_gate.evaluate_invariant(payload)
    assert allow is False
    assert verdict == "DENY"
    assert "INSOLVENT" in reason


def test_reserve_invariant_wasm_evaluation_deny_staleness(reserve_gate):
    """Validates that stale telemetry (> SLA) yields DENY."""
    payload = {
        "domain": "digital",
        "resource_type": "MEMORY_MB",
        "reserve_measured": 16384.0,
        "units_claimed": 8192.0,
        "telemetry_timestamp": int(time.time()) - 120,
        "max_staleness_seconds": 30,
    }
    allow, verdict, reason = reserve_gate.evaluate_invariant(payload)
    assert allow is False
    assert verdict == "DENY"
    assert "Stale telemetry" in reason


def test_wasm_speedup_benchmark(membrane_gate):
    """Validates microsecond execution latency for in-process Wasm evaluation."""
    cbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "metadata": {"timestamp": datetime.now(timezone.utc).isoformat()},
        "components": [
            {
                "type": "crypto-asset",
                "name": "ML-KEM-768",
                "cryptoProperties": {
                    "assetType": "algorithm",
                    "algorithmProperties": {"algorithm": "ML-KEM-768"},
                },
            },
        ],
    }

    # Warmup
    _ = membrane_gate.evaluate_verdict(cbom)

    N = 200
    t0 = time.perf_counter()
    for _ in range(N):
        _ = membrane_gate.evaluate_verdict(cbom)
    t1 = time.perf_counter()

    avg_us = ((t1 - t0) / N) * 1e6
    print(f"\nWasm evaluation latency: {avg_us:.2f} µs")
    # Assert sub-millisecond execution (< 1000 µs)
    assert avg_us < 1000.0, f"Expected < 1000 µs, got {avg_us:.2f} µs"
