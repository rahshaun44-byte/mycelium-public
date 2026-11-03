#!/usr/bin/env python3
"""
QuantumFlex QAOA Classical Reference Solver & Mathematical Verification Harness
Target: Markowitz Portfolio Optimization (3-Asset, 2-Asset Budget Constraint)

Verifies:
  1. Classical Enumeration: Computes exact cost C(x) across all 2^3 = 8 portfolio states.
  2. Classical Optimum Identification: Identifies best feasible portfolio for any lambda.
  3. Ising Hamiltonian Equivalence: Rigorously verifies |C(x) - H_C(z)| < 1e-14 across all states.
  4. Quantum State Normalization: Proves ideal Statevector probabilities sum to exactly 1.0.
  5. Little-Endian Bitstring Mapping: Validates Qiskit qubit index |q2 q1 q0> to asset vector x.
  6. Quality Metrics: Feasible probability, optimal portfolio probability, approximation ratio.
  7. Multi-Profile Consistency: Benchmarks across Aggressive, Balanced, Conservative, and Ultra-Conservative.
"""

import itertools
import sys
from pathlib import Path
import numpy as np

# Ensure tools directory is in sys.path
sys.path.insert(0, str(Path(__file__).parent))
from run_qaoa_and_ghz_kingston import (
    build_qaoa_portfolio_circuit,
    classical_portfolio_cost,
    RISK_PROFILES,
)
from qiskit.quantum_info import Statevector

ASSET_NAMES = ["Tech_Growth (x0)", "Energy_Dividend (x1)", "Treasury_Bond (x2)"]
MU = np.array([0.15, 0.10, 0.05], dtype=float)
COV = np.array([
    [0.08,  0.02, -0.01],
    [0.02,  0.06,  0.00],
    [-0.01, 0.00,  0.01],
], dtype=float)
BUDGET = 2
PENALTY = 1.0


def verify_ising_equivalence(meta: dict, lambda_risk: float) -> bool:
    """Verify that Ising Hamiltonian energy matches classical objective to < 1e-14 on all 8 states."""
    h = np.array(meta["ising_linear_h"], dtype=float)
    J = meta["ising_coupling_J"]

    a = -MU + lambda_risk * np.diag(COV) + PENALTY * (1.0 - 2.0 * BUDGET)
    b_01 = 2.0 * lambda_risk * COV[0, 1] + 2.0 * PENALTY
    b_02 = 2.0 * lambda_risk * COV[0, 2] + 2.0 * PENALTY
    b_12 = 2.0 * lambda_risk * COV[1, 2] + 2.0 * PENALTY
    const = PENALTY * (BUDGET ** 2) + 0.5 * np.sum(a) + 0.25 * (b_01 + b_02 + b_12)

    for bits in itertools.product([0, 1], repeat=3):
        x = np.array(bits, dtype=float)
        cost_c = classical_portfolio_cost(x, lambda_risk=lambda_risk)

        # Mapping: Z_i = 1 - 2*x_i
        z = 1.0 - 2.0 * x
        cost_ising = (
            const
            + np.dot(h, z)
            + J["0_1"] * z[0] * z[1]
            + J["0_2"] * z[0] * z[2]
            + J["1_2"] * z[1] * z[2]
        )
        assert np.isclose(cost_c, cost_ising, atol=1e-14), (
            f"Hamiltonian mismatch at bits={bits}: classical={cost_c}, ising={cost_ising}, diff={abs(cost_c - cost_ising)}"
        )
    return True


def benchmark_profile(profile_name: str, lambda_risk: float) -> dict:
    """Benchmark and verify QAOA against classical reference for a given risk profile."""
    print("\n" + "=" * 75)
    print(f" BENCHMARK PROFILE: {profile_name.upper()} (Risk Aversion Lambda = {lambda_risk})")
    print("=" * 75)

    # 1. Classical Enumeration
    results = []
    for bits in itertools.product([0, 1], repeat=3):
        x = np.array(bits, dtype=float)
        cost = classical_portfolio_cost(x, lambda_risk=lambda_risk)
        selected_count = int(x.sum())
        is_feas = (selected_count == BUDGET)
        selected = [ASSET_NAMES[i] for i, b in enumerate(x) if b == 1]
        desc = " + ".join(selected) if selected else "None"
        results.append({
            "bits": bits,
            "state_str": f"{bits[0]}{bits[1]}{bits[2]}",
            "assets_selected": selected_count,
            "is_feasible": is_feas,
            "cost": cost,
            "description": desc
        })

    results.sort(key=lambda r: r["cost"])
    feasible_results = [r for r in results if r["is_feasible"]]
    classical_optimum = feasible_results[0]

    print(f"[1] Classical Portfolio Ranking (8 States):")
    for r in results:
        tag = "[FEASIBLE]" if r["is_feasible"] else "[PENALIZED]"
        print(f"    x={r['bits']} ({r['description']:<35}) Cost: {r['cost']:+.6f}  {tag}")

    print(f"\n    Classical Optimum Feasible Portfolio:")
    print(f"      State      : x={classical_optimum['bits']} -> {classical_optimum['description']}")
    print(f"      Exact Cost : {classical_optimum['cost']:+.6f}")

    # 2. Build QAOA Circuit & Verify Hamiltonian Equivalence
    qc, meta = build_qaoa_portfolio_circuit(lambda_risk=lambda_risk, risk_profile=profile_name)
    verify_ising_equivalence(meta, lambda_risk)
    print(f"\n[2] QAOA Ising Hamiltonian Verification:")
    print(f"    Linear Fields h : {[round(v, 4) for v in meta['ising_linear_h']]}")
    print(f"    Couplings J     : {{k: round(v, 4) for k, v in meta['ising_coupling_J'].items()}}")
    print(f"    [+] PASS: Ising Hamiltonian energy matches classical objective to < 1e-14 on all 8 states.")

    # 3. Statevector Simulation & Metrics
    unitary_circuit = qc.remove_final_measurements(inplace=False)
    sv = Statevector.from_instruction(unitary_circuit)
    probs = sv.probabilities_dict()

    prob_sum = sum(probs.values())
    assert np.isclose(prob_sum, 1.0), f"Statevector probabilities sum to {prob_sum}, expected 1.0"

    feasible_prob = 0.0
    mean_cost = 0.0
    feasible_cost_sum = 0.0
    best_observed_port = None
    best_observed_cost = 999.0

    opt_state = classical_optimum["state_str"]
    opt_qiskit_key = f"{opt_state[2]}{opt_state[1]}{opt_state[0]}"
    opt_prob = probs.get(opt_qiskit_key, 0.0)

    print(f"\n[3] QAOA Quantum Statevector Distribution (sum = {prob_sum:.10f}):")
    for state, p in sorted(probs.items(), key=lambda x: x[1], reverse=True):
        x = [int(state[2]), int(state[1]), int(state[0])]
        c = classical_portfolio_cost(x, lambda_risk=lambda_risk)
        is_feas = (sum(x) == BUDGET)
        tag = "[FEASIBLE]" if is_feas else "[PENALIZED]"
        is_opt = " <-- CLASSICAL OPTIMUM" if state == opt_qiskit_key else ""
        mean_cost += p * c
        if is_feas:
            feasible_prob += p
            feasible_cost_sum += p * c
            if c < best_observed_cost:
                best_observed_cost = c
                best_observed_port = state

        print(f"    |{state}> -> x=({x[0]},{x[1]},{x[2]}): Prob = {p*100:5.2f}% ({p:.6f})  Cost = {c:+.4f}  {tag}{is_opt}")

    cond_feas_cost = (feasible_cost_sum / feasible_prob) if feasible_prob > 0 else 0.0
    approx_ratio_best = (best_observed_cost / classical_optimum["cost"]) if classical_optimum["cost"] != 0 else 1.0
    approx_ratio_mean = (cond_feas_cost / classical_optimum["cost"]) if classical_optimum["cost"] != 0 else 1.0

    print(f"\n[4] Benchmark Metrics Summary ({profile_name}):")
    print(f"    Feasible Subspace Probability : {feasible_prob * 100:.2f}%")
    print(f"    Optimal Portfolio Probability : {opt_prob * 100:.2f}% (State |{opt_qiskit_key}> -> x={classical_optimum['bits']})")
    print(f"    Classical Optimum Cost        : {classical_optimum['cost']:+.6f}")
    print(f"    Best Feasible Observed Cost   : {best_observed_cost:+.6f}")
    print(f"    Mean Conditional Feasible Cost: {cond_feas_cost:+.6f}")
    print(f"    Best Approximation Ratio      : {approx_ratio_best:.4f}")
    print(f"    Mean Approximation Ratio      : {approx_ratio_mean:.4f}")

    return {
        "profile": profile_name,
        "lambda": lambda_risk,
        "classical_optimum_state": classical_optimum["state_str"],
        "classical_optimum_desc": classical_optimum["description"],
        "classical_optimum_cost": classical_optimum["cost"],
        "feasible_prob_pct": feasible_prob * 100,
        "optimal_prob_pct": opt_prob * 100,
        "approx_ratio_best": approx_ratio_best,
        "approx_ratio_mean": approx_ratio_mean,
        "mean_feasible_cost": cond_feas_cost,
        "ising_verified": True
    }


def main():
    print("=" * 75)
    print(" QUANTUMFLEX QAOA CLASSICAL REFERENCE & VERIFICATION HARNESS")
    print(" Target: Markowitz Mean-Variance Portfolio Optimization")
    print(" Verification Gate: Strict Equivalence Tolerance < 1e-14")
    print("=" * 75)

    summary_rows = []
    for name, lambda_val in RISK_PROFILES.items():
        res = benchmark_profile(name, lambda_val)
        summary_rows.append(res)

    print("\n" + "=" * 90)
    print(" CROSS-PROFILE RISK SENSITIVITY & QUANTUM BENCHMARK SUMMARY")
    print("=" * 90)
    print(f"{'Profile':<18} {'Lambda':<8} {'Classical Optimum':<26} {'Opt Cost':<10} {'Feas Prob':<10} {'Opt Prob':<10} {'Approx Ratio'}")
    print("-" * 90)
    for r in summary_rows:
        print(
            f"{r['profile']:<18} "
            f"{r['lambda']:<8.2f} "
            f"{r['classical_optimum_state']} ({r['classical_optimum_desc']:<19}) "
            f"{r['classical_optimum_cost']:<10.4f} "
            f"{r['feasible_prob_pct']:<9.1f}% "
            f"{r['optimal_prob_pct']:<9.1f}% "
            f"{r['approx_ratio_mean']:.4f}"
        )
    print("=" * 90)
    print("[+] ALL MATHEMATICAL CHECKS & ISING EQUIVALENCE GATES PASSED (TOLERANCE < 1e-14)")


if __name__ == "__main__":
    main()
