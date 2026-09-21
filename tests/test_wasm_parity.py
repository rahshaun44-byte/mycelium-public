#!/usr/bin/env python3
"""
QuantumFlex Critical-State v1: Native Rego vs. Wasm Decision Parity Suite
==========================================================================
Executes the identical fixture corpus through both:
  1. Native OPA CLI (Go runtime evaluating bootgate.rego)
  2. In-Process Wasmtime (Wasmtime executing bootgate.wasm)

Enforces: Native Decision A == Wasm Decision B (ZERO DIVERGENCE TOLERATED)
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from sentinel.policies.wasm_gatekeeper import OPAWasmEngine

BOOTGATE_REGO = ROOT_DIR / "sentinel" / "policies" / "bootgate.rego"
BOOTGATE_WASM = ROOT_DIR / "sentinel" / "policies" / "bootgate.wasm"


def eval_native_opa(inp: dict, data: dict) -> bool:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f_in, \
         tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f_data:
        json.dump(inp, f_in)
        json.dump(data, f_data)
        in_path, data_path = f_in.name, f_data.name

    try:
        cmd = [
            "opa", "eval",
            "-i", in_path,
            "-d", data_path,
            "-d", str(BOOTGATE_REGO),
            "data.quantumflex.bootgate.allow"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        eval_data = json.loads(res.stdout)
        results = eval_data.get("result", [])
        if results and len(results) > 0:
            return bool(results[0].get("expressions", [{}])[0].get("value", False))
        return False
    finally:
        os.remove(in_path)
        os.remove(data_path)


def main():
    print("=" * 80)
    print("  QUANTUMFLEX CRITICAL-STATE v1: NATIVE REGO vs. WASM PARITY SUITE  ")
    print("=" * 80)

    wasm_engine = OPAWasmEngine(BOOTGATE_WASM)
    ep_id = wasm_engine.entrypoints.get("quantumflex/bootgate/allow", 0)

    good_input = {
        "attestation": {
            "payload": {
                "schema_version": "v1",
                "sequence": 42,
                "previous_state_digest": "sha3:STATE41",
                "policy_digest": "sha3:POLICY_A",
                "decision_id": "decision-42",
                "input_digest": "sha3:INPUT_A",
                "result": "ALLOW"
            }
        },
        "verification": {
            "canonical_digest_verified": True,
            "ed25519_verified": True,
            "ml_dsa_verified": True,
            "trusted_keyring": True
        }
    }

    base_data = {
        "anchor": {"sequence": 41, "state_digest": "sha3:STATE41"},
        "environment": {"active_policy_digest": "sha3:POLICY_A", "pending_input_digest": "sha3:INPUT_A"},
        "ledger": {"consumed_decisions": []}
    }

    test_cases = [
        ("01_valid_state", good_input, base_data, True),
        ("02_replayed_decision", good_input, {**base_data, "ledger": {"consumed_decisions": ["decision-42"]}}, False),
        ("03_wrong_previous_digest", good_input, {**base_data, "anchor": {"sequence": 41, "state_digest": "sha3:ATTACKER"}}, False),
        ("04_policy_swap", good_input, {**base_data, "environment": {**base_data["environment"], "active_policy_digest": "sha3:ROGUE_POL"}}, False),
        ("05_bad_ed25519", {**good_input, "verification": {**good_input["verification"], "ed25519_verified": False}}, base_data, False),
        ("06_bad_ml_dsa", {**good_input, "verification": {**good_input["verification"], "ml_dsa_verified": False}}, base_data, False),
        ("07_untrusted_keyring", {**good_input, "verification": {**good_input["verification"], "trusted_keyring": False}}, base_data, False),
        ("08_bad_canonical_digest", {**good_input, "verification": {**good_input["verification"], "canonical_digest_verified": False}}, base_data, False),
        ("09_sequence_rollback", good_input, {**base_data, "anchor": {"sequence": 42, "state_digest": "sha3:STATE41"}}, False),
        ("10_input_mismatch", good_input, {**base_data, "environment": {**base_data["environment"], "pending_input_digest": "sha3:DIFF_INPUT"}}, False),
        ("11_overflow_sequence_ieee754", {
            "attestation": {
                "payload": {
                    **good_input["attestation"]["payload"],
                    "sequence": 9007199254740992  # 2^53
                }
            },
            "verification": good_input["verification"]
        }, {**base_data, "anchor": {"sequence": 9007199254740991, "state_digest": "sha3:STATE41"}}, False),
        ("12_upper_bound_boundary_valid", {
            "attestation": {
                "payload": {
                    **good_input["attestation"]["payload"],
                    "sequence": 9007199254740991  # 2^53 - 1 exactly
                }
            },
            "verification": good_input["verification"]
        }, {**base_data, "anchor": {"sequence": 9007199254740990, "state_digest": "sha3:STATE41"}}, True)
    ]

    print(f"[*] Executing {len(test_cases)} parity test fixtures across Native OPA and Wasmtime...\n")

    divergence_count = 0

    for name, inp, data, expected in test_cases:
        native_res = eval_native_opa(inp, data)
        wasm_res = wasm_engine.evaluate(input_data=inp, data=data, entrypoint_id=ep_id)

        parity = (native_res == wasm_res)
        correct = (native_res == expected)

        status_str = "PARITY OK" if parity and correct else "DIVERGENCE DETECTED"
        if not parity or not correct:
            divergence_count += 1

        print(f"  [{name:<30}] Native: {str(native_res):<5} | Wasm: {str(wasm_res):<5} | Expected: {str(expected):<5} -> {status_str}")

    print("\n" + "=" * 80)
    if divergence_count == 0:
        print(f"  ALL {len(test_cases)}/{len(test_cases)} FIXTURES ACHIEVED 100% NATIVE / WASM DECISION PARITY")
        print("  ZERO DIVERGENCE DETECTED (A == B ∀ fixtures)")
    else:
        print(f"  FAIL: {divergence_count} divergences observed between Native and Wasm engines!")
        sys.exit(1)
    print("=" * 80)


if __name__ == "__main__":
    main()
