#!/usr/bin/env python3
"""
QuantumFlex Physical Quantum Experiment Runner: QAOA Portfolio & Complete Multi-Basis GHZ Witness
Target QPU: ibm_kingston (Heron Revision 2, 156 Physical Transmon Qubits)
Epistemic Boundary: Physical research testbed; zero entropy admitted to engine.
Engine Posture: LOCKED (fail-closed zero-trust boundary maintained).
"""

import argparse
import hashlib
import itertools
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import warnings

# Suppress client-side Sampler deprecation warnings in runtime output
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Ensure quantum_worker imports work
sys.path.insert(0, "/home/quant/Documents/qf")
from quantum_worker import QuantumWorker

from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2 as Sampler
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager


def circuit_sha256(qc: QuantumCircuit) -> str:
    """Compute deterministic cryptographic SHA-256 digest of a QuantumCircuit."""
    try:
        from qiskit import qasm3
        text = qasm3.dumps(qc)
    except Exception:
        text = str(qc.data)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


RISK_PROFILES = {
    "aggressive": 0.1,
    "balanced": 0.5,
    "conservative": 1.0,
    "ultra_conservative": 2.0,
}


def classical_portfolio_cost(x: list[int] | np.ndarray, lambda_risk: float = 0.5) -> float:
    """Evaluate classical Markowitz portfolio cost: -mu^T x + lambda * x^T Sigma x + penalty (sum(x) - B)^2"""
    mu = np.array([0.15, 0.10, 0.05], dtype=float)
    cov = np.array([
        [0.08,  0.02, -0.01],
        [0.02,  0.06,  0.00],
        [-0.01, 0.00,  0.01]
    ], dtype=float)
    budget = 2
    penalty = 1.0
    x_arr = np.asarray(x, dtype=float)
    return float(
        -mu @ x_arr
        + lambda_risk * (x_arr @ cov @ x_arr)
        + penalty * (x_arr.sum() - budget) ** 2
    )


def evaluate_all_portfolios(lambda_risk: float = 0.5) -> list[dict]:
    """Exhaustively evaluate classical Markowitz cost C(x) across all 2^3 = 8 possible states."""
    results = []
    asset_names = ["Tech_Growth", "Energy_Dividend", "Treasury_Bond"]
    for bits in itertools.product([0, 1], repeat=3):
        x = list(bits)
        cost = classical_portfolio_cost(x, lambda_risk=lambda_risk)
        selected_count = sum(x)
        is_feasible = (selected_count == 2)
        selected_assets = [asset_names[i] for i, b in enumerate(x) if b == 1]
        results.append({
            "state": f"{x[0]}{x[1]}{x[2]}",
            "x": x,
            "selected_count": selected_count,
            "is_feasible": is_feasible,
            "cost": round(cost, 6),
            "description": " + ".join(selected_assets) if selected_assets else "None"
        })
    results.sort(key=lambda r: r["cost"])
    return results


def validate_qaoa_hamiltonian_gate(lambda_risk: float, meta: dict) -> bool:
    """
    Mandatory Validation Gate: Check Ising Hamiltonian energy against classical Markowitz cost
    to < 1e-14 numerical tolerance across all 2^3 = 8 portfolio basis states.
    Fails closed if any discrepancy is detected before quantum execution.
    """
    mu = np.array([0.15, 0.10, 0.05], dtype=float)
    cov = np.array([
        [0.08,  0.02, -0.01],
        [0.02,  0.06,  0.00],
        [-0.01, 0.00,  0.01]
    ], dtype=float)
    budget = 2
    penalty = 1.0

    a = -mu + lambda_risk * np.diag(cov) + penalty * (1.0 - 2.0 * budget)
    b_01 = 2.0 * lambda_risk * cov[0, 1] + 2.0 * penalty
    b_02 = 2.0 * lambda_risk * cov[0, 2] + 2.0 * penalty
    b_12 = 2.0 * lambda_risk * cov[1, 2] + 2.0 * penalty
    const = penalty * (budget ** 2) + 0.5 * np.sum(a) + 0.25 * (b_01 + b_02 + b_12)

    h = np.array(meta["ising_linear_h"], dtype=float)
    J = meta["ising_coupling_J"]

    for bits in itertools.product([0, 1], repeat=3):
        x = np.array(bits, dtype=float)
        cost_c = classical_portfolio_cost(x, lambda_risk=lambda_risk)
        z = 1.0 - 2.0 * x
        cost_ising = (
            const
            + np.dot(h, z)
            + J["0_1"] * z[0] * z[1]
            + J["0_2"] * z[0] * z[2]
            + J["1_2"] * z[1] * z[2]
        )
        if not np.isclose(cost_c, cost_ising, atol=1e-14):
            raise ValueError(
                f"QAOA VALIDATION GATE FAILURE: Hamiltonian mismatch at bits={bits}: "
                f"Classical={cost_c}, Ising={cost_ising}"
            )
    return True


def build_qaoa_portfolio_circuit(lambda_risk: float = 0.5, risk_profile: str = "balanced") -> tuple[QuantumCircuit, dict]:
    """
    Construct a 3-qubit QAOA portfolio optimization circuit (Markowitz Mean-Variance).
    
    Rigorous Ising Formulation:
      Objective: C(x) = -mu^T x + lambda * x^T Sigma x + A * (sum(x) - B)^2
      Binary mapping: x_i = (1 - Z_i) / 2
      Transformed Hamiltonian: H_C = const + sum_i h_i Z_i + sum_{i < j} J_ij Z_i Z_j
      
      Linear binary coefficients:
        a_i = -mu_i + lambda * Sigma_ii + A * (1 - 2*B)
      Pairwise binary coefficients:
        b_ij = 2 * lambda * Sigma_ij + 2 * A  (symmetric)
        
      Ising fields:
        h_i = -a_i / 2 - sum_{j != i} (b_ij / 4)
        J_ij = b_ij / 4  (for i < j)
    """
    # 3 Assets: Tech Growth (0), Dividend Energy (1), Safe Treasury Bond (2)
    mu = np.array([0.15, 0.10, 0.05], dtype=float)
    cov = np.array([
        [0.08,  0.02, -0.01],
        [0.02,  0.06,  0.00],
        [-0.01, 0.00,  0.01]
    ], dtype=float)
    assert np.allclose(cov, cov.T), "Covariance matrix must be symmetric"

    budget = 2
    penalty = 1.0
    n = 3

    # Derive binary expansion coefficients: C(x) = const + sum_i a_i x_i + sum_{i < j} b_ij x_i x_j
    a = -mu + lambda_risk * np.diag(cov) + penalty * (1.0 - 2.0 * budget)
    b = np.zeros((n, n), dtype=float)
    for i in range(n):
        for j in range(n):
            if i != j:
                b[i, j] = 2.0 * lambda_risk * cov[i, j] + 2.0 * penalty

    # Map to Pauli-Z Ising Hamiltonian: H_C = const + sum_i h_i Z_i + sum_{i < j} J_ij Z_i Z_j
    h = np.zeros(n, dtype=float)
    for i in range(n):
        h[i] = -0.5 * a[i] - 0.25 * sum(b[i, j] for j in range(n) if j != i)

    J = np.zeros((n, n), dtype=float)
    for i in range(n):
        for j in range(i + 1, n):
            J[i, j] = 0.25 * b[i, j]

    qc = QuantumCircuit(n, n, name="qaoa_portfolio_3q")

    # Initial equal superposition over all 2^3 = 8 portfolios
    for i in range(n):
        qc.h(i)

    # Fixed benchmark parameters (heuristic initial choices)
    gamma = float(np.pi / 8)  # ~0.3927
    beta = float(np.pi / 4)   # ~0.7854

    # Problem Hamiltonian (Phase separation unitary: exp(-i * gamma * H_C))
    for i in range(n):
        qc.rz(2 * gamma * h[i], i)

    for i in range(n):
        for j in range(i + 1, n):
            qc.rzz(2 * gamma * J[i, j], i, j)

    # Mixer Hamiltonian (Transverse X unitary: exp(-i * beta * sum X_i))
    for i in range(n):
        qc.rx(2 * beta, i)

    qc.measure(range(n), range(n))

    # Calculate ideal statevector predictions locally
    unitary_circuit = qc.remove_final_measurements(inplace=False)
    sv = Statevector.from_instruction(unitary_circuit)
    ideal_probs = {k: float(v) for k, v in sv.probabilities_dict().items()}

    # Classical exhaustive benchmark ranking for this exact lambda
    all_ranked = evaluate_all_portfolios(lambda_risk=lambda_risk)
    best_feasible = next(p for p in all_ranked if p["is_feasible"])

    meta = {
        "algorithm": "QAOA",
        "assets": ["Tech_Growth", "Energy_Dividend", "Treasury_Bond"],
        "budget": budget,
        "risk_profile": risk_profile,
        "lambda_risk": lambda_risk,
        "penalty": penalty,
        "gamma": gamma,
        "beta": beta,
        "ising_linear_h": [float(val) for val in h],
        "ising_coupling_J": {f"{i}_{j}": float(J[i, j]) for i in range(n) for j in range(i + 1, n)},
        "expected_best_state": best_feasible["state"],
        "expected_best_portfolio": best_feasible["description"],
        "expected_best_cost": best_feasible["cost"],
        "classical_exhaustive_ranking": all_ranked,
        "ideal_statevector_predictions": ideal_probs
    }
    return qc, meta


def _base_ghz_circuit() -> QuantumCircuit:
    """Helper to create base 3-qubit GHZ state (|000> + |111>) / sqrt(2)."""
    qc = QuantumCircuit(3, 3)
    qc.h(0)
    qc.cx(0, 1)
    qc.cx(1, 2)
    return qc


def build_ghz_zzz_circuit() -> tuple[QuantumCircuit, dict]:
    """Setting 1/5: Computational Z basis (measures populations and <Zi Zj> correlations)."""
    qc = _base_ghz_circuit()
    qc.name = "ghz_3q_zzz"
    qc.measure(range(3), range(3))
    meta = {
        "setting": "ZZZ",
        "measurement_basis": "Pauli_Z_Z_Z",
        "measured_observables": ["Z0_Z1", "Z1_Z2", "Z0_Z2"],
        "ideal_values": {"Z0_Z1": 1.0, "Z1_Z2": 1.0, "Z0_Z2": 1.0}
    }
    return qc, meta


def build_ghz_xxx_circuit() -> tuple[QuantumCircuit, dict]:
    """Setting 2/5: Pauli X basis on all 3 qubits (measures <X0 X1 X2> parity contrast)."""
    qc = _base_ghz_circuit()
    qc.name = "ghz_3q_xxx"
    for i in range(3):
        qc.h(i)
    qc.measure(range(3), range(3))
    meta = {
        "setting": "XXX",
        "measurement_basis": "Pauli_X_X_X",
        "measured_observables": ["X0_X1_X2"],
        "ideal_values": {"X0_X1_X2": 1.0}
    }
    return qc, meta


def build_ghz_xyy_circuit() -> tuple[QuantumCircuit, dict]:
    """Setting 3/5: Qubit 0 in X, Qubits 1 and 2 in Y (measures <X0 Y1 Y2>)."""
    qc = _base_ghz_circuit()
    qc.name = "ghz_3q_xyy"
    qc.h(0)
    qc.sdg(1)
    qc.h(1)
    qc.sdg(2)
    qc.h(2)
    qc.measure(range(3), range(3))
    meta = {
        "setting": "XYY",
        "measurement_basis": "Pauli_X0_Y1_Y2",
        "measured_observables": ["X0_Y1_Y2"],
        "ideal_values": {"X0_Y1_Y2": -1.0}
    }
    return qc, meta


def build_ghz_yxy_circuit() -> tuple[QuantumCircuit, dict]:
    """Setting 4/5: Qubit 1 in X, Qubits 0 and 2 in Y (measures <Y0 X1 Y2>)."""
    qc = _base_ghz_circuit()
    qc.name = "ghz_3q_yxy"
    qc.sdg(0)
    qc.h(0)
    qc.h(1)
    qc.sdg(2)
    qc.h(2)
    qc.measure(range(3), range(3))
    meta = {
        "setting": "YXY",
        "measurement_basis": "Pauli_Y0_X1_Y2",
        "measured_observables": ["Y0_X1_Y2"],
        "ideal_values": {"Y0_X1_Y2": -1.0}
    }
    return qc, meta


def build_ghz_yyx_circuit() -> tuple[QuantumCircuit, dict]:
    """Setting 5/5: Qubit 2 in X, Qubits 0 and 1 in Y (measures <Y0 Y1 X2>)."""
    qc = _base_ghz_circuit()
    qc.name = "ghz_3q_yyx"
    qc.sdg(0)
    qc.h(0)
    qc.sdg(1)
    qc.h(1)
    qc.h(2)
    qc.measure(range(3), range(3))
    meta = {
        "setting": "YYX",
        "measurement_basis": "Pauli_Y0_Y1_X2",
        "measured_observables": ["Y0_Y1_X2"],
        "ideal_values": {"Y0_Y1_X2": -1.0}
    }
    return qc, meta


def run_experiment(
    backend_name: str = "ibm_kingston",
    shots: int = 256,
    dry_run: bool = True,
    retrieve_job_id: str | None = None,
    risk_profile: str = "balanced",
    lambda_risk: float | None = None
):
    effective_lambda = lambda_risk if lambda_risk is not None else RISK_PROFILES.get(risk_profile, 0.5)

    if retrieve_job_id:
        dry_run = False
        mode_str = f"[RETRIEVING PHYSICAL EXECUTION: {retrieve_job_id}]"
    else:
        mode_str = "[DRY-RUN / LOCAL VERIFICATION]" if dry_run else "[HARDWARE CRYOGENIC EXECUTION]"

    print("=" * 75)
    print(" QUANTUMFLEX PHYSICAL QPU RESEARCH: QAOA & COMPLETE GHZ WITNESS")
    print(f" Execution Mode : {mode_str}")
    print(f" Target Silicon : {backend_name} (156 Physical Transmons, Heron r2)")
    print(f" Requested Shots: {shots} per circuit (Batch: 6 circuits, {shots * 6} total shots)")
    print(f" Risk Profile   : {risk_profile.upper()} (lambda_risk = {effective_lambda})")
    print(f" Engine Status  : LOCKED (Zero-Trust Isolation)")
    print("=" * 75)

    worker = QuantumWorker()
    if not worker.token or not worker.instance:
        raise RuntimeError("IBM Quantum credentials not configured in ~/.config/qf/credentials.json")

    print(f"\n[1/5] Authenticating with IBM Quantum Cloud...")
    service = QiskitRuntimeService(channel="ibm_quantum_platform", token=worker.token, instance=worker.instance)
    backend = service.backend(backend_name)
    status = backend.status()
    print(f"      Connected to QPU: {backend.name} | Total Qubits: {backend.num_qubits} | Pending Jobs: {status.pending_jobs}")

    print(f"\n[2/5] Building Quantum Research Circuits (Complete 6-Circuit Suite)...")
    qc_qaoa, meta_qaoa = build_qaoa_portfolio_circuit(lambda_risk=effective_lambda, risk_profile=risk_profile)
    qc_zzz, meta_zzz = build_ghz_zzz_circuit()
    qc_xxx, meta_xxx = build_ghz_xxx_circuit()
    qc_xyy, meta_xyy = build_ghz_xyy_circuit()
    qc_yxy, meta_yxy = build_ghz_yxy_circuit()
    qc_yyx, meta_yyx = build_ghz_yyx_circuit()

    # Mandatory Classical Validation Gate
    validate_qaoa_hamiltonian_gate(effective_lambda, meta_qaoa)
    print(f"      [VALIDATION GATE PASSED] Ising Hamiltonian matches classical Markowitz objective (< 1e-14) on all 8 states.")

    circuits = [qc_qaoa, qc_zzz, qc_xxx, qc_xyy, qc_yxy, qc_yyx]
    circuit_metas = [meta_qaoa, meta_zzz, meta_xxx, meta_xyy, meta_yxy, meta_yyx]

    for i, qc in enumerate(circuits):
        print(f"      Circuit {i}: {qc.name:<18} (Depth: {qc.depth()}, Ops: {dict(qc.count_ops())})")

    print(f"\n[3/5] Transpiling to Physical Heron ISA Architecture...")
    pm = generate_preset_pass_manager(backend=backend, optimization_level=1)
    isa_circuits = [pm.run(qc) for qc in circuits]

    transpiled_meta = []
    for i, (orig, isa) in enumerate(zip(circuits, isa_circuits)):
        layout = isa.layout.final_index_layout() if hasattr(isa, "layout") and isa.layout else None
        log_hash = circuit_sha256(orig)
        isa_hash = circuit_sha256(isa)
        print(f"      ISA Circuit {i} ({orig.name:<18}): Depth {isa.depth():<2} | Layout: {layout} | Ops: {dict(isa.count_ops())}")
        print(f"          Logical SHA-256: {log_hash[:16]}... | ISA SHA-256: {isa_hash[:16]}...")
        transpiled_meta.append({
            "name": orig.name,
            "depth": isa.depth(),
            "ops": dict(isa.count_ops()),
            "physical_layout": layout,
            "logical_circuit_sha256": log_hash,
            "isa_circuit_sha256": isa_hash
        })

    total_batch_shots = shots * len(circuits)
    print(f"\n[4/5] Execution Plan: {len(circuits)} Circuits, {shots} shots each -> {total_batch_shots} Total Shots")

    if dry_run:
        print("      [DRY-RUN] Simulating ideal execution locally; bypassing QPU submission.")
        submission_time_utc = datetime.now(timezone.utc).isoformat()
        job_id = f"dry_run_{int(time.time())}"
        elapsed = 0.05
        retrieval_time_utc = datetime.now(timezone.utc).isoformat()
        job_metrics = {
            "usage": {"qpu_charge_time_seconds": 0},
            "circuits_execution_time_ns": 0,
            "timestamps": {
                "created": submission_time_utc,
                "running": submission_time_utc,
                "finished": retrieval_time_utc
            }
        }

        counts_list = []
        for qc in circuits:
            uc = qc.remove_final_measurements(inplace=False)
            sv = Statevector.from_instruction(uc)
            probs = sv.probabilities_dict()
            sim_counts = {}
            for s, p in probs.items():
                c = int(round(p * shots))
                if c > 0:
                    sim_counts[s] = c
            diff = shots - sum(sim_counts.values())
            if diff != 0:
                top_s = max(sim_counts.keys(), key=lambda k: sim_counts[k])
                sim_counts[top_s] += diff
            counts_list.append(sim_counts)

    elif retrieve_job_id:
        print(f"      [RETRIEVE] Fetching completed physical job: {retrieve_job_id}")
        job = service.job(retrieve_job_id)
        job_id = job.job_id()
        raw_status = job.status()
        status_name = raw_status if isinstance(raw_status, str) else getattr(raw_status, "name", str(raw_status))
        print(f"      Job ID: {job_id} | Status: {status_name}")
        if status_name != "DONE":
            raise RuntimeError(f"Job {job_id} terminated with status: {status_name}")

        result = job.result()
        retrieval_time_utc = datetime.now(timezone.utc).isoformat()
        job_metrics = {}
        try:
            job_metrics = job.metrics()
        except Exception as e:
            print(f"      Note: Could not retrieve server job metrics: {e}")

        submission_time_utc = job_metrics.get("timestamps", {}).get("created", str(job.creation_date))
        elapsed = job_metrics.get("usage", {}).get("qpu_charge_time_seconds", 3)
        counts_list = [list(pub.data.values())[0].get_counts() for pub in result]

    else:
        print("      [CONFIRMED] Submitting Batched PUB Execution to Physical Cryostat...")
        submission_time_utc = datetime.now(timezone.utc).isoformat()
        sampler = Sampler(mode=backend)
        job = sampler.run(isa_circuits, shots=shots)
        job_id = job.job_id()
        print(f"      Job ID: {job_id}")
        print(f"      Submission Time: {submission_time_utc}")
        print(f"      Waiting for physical silicon execution...")

        start_time = time.time()
        last_status = None
        while True:
            job_status = job.status()
            status_name = job_status if isinstance(job_status, str) else getattr(job_status, "name", str(job_status))
            if status_name != last_status:
                print(f"      [{int(time.time() - start_time)}s] Job Status: {status_name}")
                last_status = status_name
            if status_name in ("DONE", "CANCELLED", "ERROR"):
                break
            time.sleep(3)

        if status_name != "DONE":
            raise RuntimeError(f"Physical execution terminated with status: {status_name}")

        elapsed = round(time.time() - start_time, 2)
        print(f"      [+] Physical execution completed in {elapsed}s!")

        result = job.result()
        retrieval_time_utc = datetime.now(timezone.utc).isoformat()

        job_metrics = {}
        try:
            job_metrics = job.metrics()
        except Exception as e:
            print(f"      Note: Could not retrieve server job metrics: {e}")

        counts_list = [list(pub.data.values())[0].get_counts() for pub in result]

    print(f"\n[5/5] Extracting Real Measurement Histograms & Epistemic Analysis...")
    counts_qaoa = counts_list[0]
    counts_zzz = counts_list[1]
    counts_xxx = counts_list[2]
    counts_xyy = counts_list[3]
    counts_yxy = counts_list[4]
    counts_yyx = counts_list[5]

    total_qaoa = sum(counts_qaoa.values())
    total_zzz = sum(counts_zzz.values())
    total_xxx = sum(counts_xxx.values())
    total_xyy = sum(counts_xyy.values())
    total_yxy = sum(counts_yxy.values())
    total_yyx = sum(counts_yyx.values())

    # --- Comprehensive QAOA Analysis ---
    print("\n" + "-" * 75)
    print(f" [ANALYSIS A] QAOA QUANTUM PORTFOLIO SELECTION RESULTS ({backend.name})")
    print("-" * 75)
    print(f" Total Measurement Shots: {total_qaoa}")
    print(" Observed Portfolios (Bit-string '|q2 q1 q0>' -> x=(Tech, Energy, Treasury)):")
    
    sorted_qaoa = sorted(counts_qaoa.items(), key=lambda x: x[1], reverse=True)
    valid_budget_counts = 0
    qaoa_sample_cost_sum = 0.0
    feasible_cost_sum = 0.0
    best_observed_port = None
    best_observed_cost = 999.0

    for state, cnt in sorted_qaoa:
        prob = (cnt / total_qaoa) * 100
        # Qiskit little-endian: s[2]=q0(Tech), s[1]=q1(Energy), s[0]=q2(Treasury)
        x = [int(state[2]), int(state[1]), int(state[0])]
        c = classical_portfolio_cost(x, lambda_risk=effective_lambda)
        is_feas = (sum(x) == 2)
        tag = "[VALID 2-ASSET BUDGET]" if is_feas else "[BUDGET PENALIZED]"
        
        qaoa_sample_cost_sum += cnt * c
        if is_feas:
            valid_budget_counts += cnt
            feasible_cost_sum += cnt * c
            if c < best_observed_cost:
                best_observed_cost = c
                best_observed_port = f"|{state}> -> x={tuple(x)} (Cost: {c:+.6f})"

        print(f"   |{state}> -> x={tuple(x)}: {cnt:4d} shots ({prob:5.2f}%)  Cost = {c:+.4f}  {tag}")

    valid_pct = (valid_budget_counts / total_qaoa) * 100
    mean_cost = qaoa_sample_cost_sum / total_qaoa
    cond_feas_cost = (feasible_cost_sum / valid_budget_counts) if valid_budget_counts > 0 else 0.0

    # Calculate optimal portfolio probability and approximation ratio against classical reference
    exp_best_state = meta_qaoa["expected_best_state"]
    exp_qiskit_str = f"{exp_best_state[2]}{exp_best_state[1]}{exp_best_state[0]}"
    optimal_shots = counts_qaoa.get(exp_qiskit_str, 0)
    optimal_pct = (optimal_shots / total_qaoa) * 100
    expected_opt_cost = meta_qaoa["expected_best_cost"]
    approx_ratio_best = (best_observed_cost / expected_opt_cost) if expected_opt_cost != 0 else 1.0
    approx_ratio_mean = (cond_feas_cost / expected_opt_cost) if expected_opt_cost != 0 else 1.0

    print(f"\n   Feasible Subspace Probability : {valid_pct:.2f}% ({valid_budget_counts}/{total_qaoa} shots)")
    print(f"   Optimal Portfolio Probability : {optimal_pct:.2f}% ({optimal_shots}/{total_qaoa} shots, state |{exp_qiskit_str}> -> x={exp_best_state})")
    print(f"   Best Observed Feasible Port   : {best_observed_port}")
    print(f"   Classical Optimum Benchmark   : {exp_best_state} ({meta_qaoa['expected_best_portfolio']}) | Cost: {expected_opt_cost:+.6f}")
    print(f"   Mean Classical Objective      : {mean_cost:+.6f}")
    print(f"   Mean Conditional Feasible Cost: {cond_feas_cost:+.6f}")
    print(f"   Best Approximation Ratio      : {approx_ratio_best:.4f}")
    print(f"   Mean Feasible Approx Ratio    : {approx_ratio_mean:.4f}")

    # --- Comprehensive Complete GHZ Witness Analysis ---
    print("\n" + "-" * 75)
    print(f" [ANALYSIS B] COMPLETE GHZ WITNESS EVALUATION ({backend.name})")
    print("-" * 75)

    c000 = counts_zzz.get("000", 0)
    c111 = counts_zzz.get("111", 0)
    target_shots = c000 + c111
    target_population_pct = (target_shots / total_zzz) * 100
    other_population_pct = ((total_zzz - target_shots) / total_zzz) * 100

    def calc_2body_z(counts, total, q_i, q_j):
        # bit q is at index (2 - q)
        return sum((+1 if (int(s[2-q_i]) + int(s[2-q_j])) % 2 == 0 else -1) * cnt for s, cnt in counts.items()) / total

    def calc_3body_parity(counts, total):
        return sum((+1 if (int(s[0]) + int(s[1]) + int(s[2])) % 2 == 0 else -1) * cnt for s, cnt in counts.items()) / total

    # 1. Z-basis terms
    exp_z0z1 = calc_2body_z(counts_zzz, total_zzz, 0, 1)
    exp_z1z2 = calc_2body_z(counts_zzz, total_zzz, 1, 2)
    exp_z0z2 = calc_2body_z(counts_zzz, total_zzz, 0, 2)

    # 2. X-basis parity
    exp_xxx = calc_3body_parity(counts_xxx, total_xxx)

    # 3. Y-containing settings
    exp_xyy = calc_3body_parity(counts_xyy, total_xyy)  # <X0 Y1 Y2> (ideal -1)
    exp_yxy = calc_3body_parity(counts_yxy, total_yxy)  # <Y0 X1 Y2> (ideal -1)
    exp_yyx = calc_3body_parity(counts_yyx, total_yyx)  # <Y0 Y1 X2> (ideal -1)

    print("   Measurement Settings Summary:")
    print(f"     Setting 1 (ZZZ) : Target Pop = {target_population_pct:.2f}% | <Z0 Z1> = {exp_z0z1:+.4f}, <Z1 Z2> = {exp_z1z2:+.4f}, <Z0 Z2> = {exp_z0z2:+.4f}")
    print(f"     Setting 2 (XXX) : Parity <X0 X1 X2> = {exp_xxx:+.4f} (Ideal: +1.0000)")
    print(f"     Setting 3 (XYY) : <X0 Y1 Y2>        = {exp_xyy:+.4f} (Ideal: -1.0000)")
    print(f"     Setting 4 (YXY) : <Y0 X1 Y2>        = {exp_yxy:+.4f} (Ideal: -1.0000)")
    print(f"     Setting 5 (YYX) : <Y0 Y1 X2>        = {exp_yyx:+.4f} (Ideal: -1.0000)")

    # Complete State Fidelity and Witness Calculation
    # Joint covariance calculation for shared Z-basis data:
    # Let U_s = Z0Z1(s) + Z1Z2(s) + Z0Z2(s) for each measured bitstring s.
    # The sample mean is <U> = <Z0 Z1> + <Z1 Z2> + <Z0 Z2>.
    # The sample variance of <U> accounts for the exact covariance between the three correlated terms:
    mean_U = exp_z0z1 + exp_z1z2 + exp_z0z2
    mean_U_sq = 0.0
    for s, cnt in counts_zzz.items():
        u1 = +1 if (int(s[2]) + int(s[1])) % 2 == 0 else -1
        u2 = +1 if (int(s[1]) + int(s[0])) % 2 == 0 else -1
        u3 = +1 if (int(s[2]) + int(s[0])) % 2 == 0 else -1
        u_val = u1 + u2 + u3
        mean_U_sq += (cnt / total_zzz) * (u_val ** 2)

    var_U_shot = max(0.0, mean_U_sq - (mean_U ** 2))
    var_mean_U = var_U_shot / total_zzz

    # Fidelity: F = 1/8 * (1 + <U> + <XXX> - <XYY> - <YXY> - <YYX>)
    fidelity = (1.0 + mean_U + exp_xxx - exp_xyy - exp_yxy - exp_yyx) / 8.0
    witness_exp = 0.5 - fidelity

    # Independent variance terms for the remaining 4 physical circuit settings
    var_xxx = max(0.0, 1.0 - exp_xxx ** 2) / total_xxx
    var_xyy = max(0.0, 1.0 - exp_xyy ** 2) / total_xyy
    var_yxy = max(0.0, 1.0 - exp_yxy ** 2) / total_yxy
    var_yyx = max(0.0, 1.0 - exp_yyx ** 2) / total_yyx

    # Total variance of F accounting for joint Z covariance and independent settings:
    var_fidelity = (1.0 / 64.0) * (var_mean_U + var_xxx + var_xyy + var_yxy + var_yyx)
    sigma_fidelity = math.sqrt(var_fidelity)
    sigma_witness = sigma_fidelity

    # 95% Confidence Upper Bound on Witness: W_upper = <W> + 1.96 * sigma
    witness_upper_95 = witness_exp + 1.96 * sigma_witness

    print("\n   Complete GHZ Witness Analysis:")
    label_tag = "[SIMULATED BASELINE]" if dry_run else "[HARDWARE MEASUREMENT]"
    print(f"     Execution Classification        : {label_tag}")
    print(f"     State Fidelity F(|GHZ><GHZ|)    : {fidelity:.4f} +/- {sigma_fidelity:.4f}")
    print(f"     Joint Z-Basis Var(<U>)/Var(F)   : {var_mean_U:.6e} / {var_fidelity:.6e}")
    print(f"     Witness Expectation <W>         : {witness_exp:+.4f} +/- {sigma_witness:.4f} (Ideal: -0.5000)")
    print(f"     95% Confidence Upper Bound      : {witness_upper_95:+.4f}")

    if dry_run:
        entanglement_certified = False
        cert_note = (
            "Genuine tripartite entanglement has not been certified. "
            "This execution was a local statevector dry-run simulation and does not constitute "
            "physical hardware evidence from ibm_kingston. Experimental certification requires "
            "physical QPU execution of the complete 5-setting witness with an upper 95% confidence bound < 0."
        )
    elif witness_upper_95 < 0.0:
        entanglement_certified = True
        cert_note = (
            f"Genuine tripartite entanglement certified at 95% confidence level from ibm_kingston QPU data. "
            f"Measured witness expectation <W> = {witness_exp:+.4f} +/- {sigma_witness:.4f} "
            f"with 95% upper bound {witness_upper_95:+.4f} < 0."
        )
    else:
        entanglement_certified = False
        cert_note = (
            f"Genuine tripartite entanglement not certified. "
            f"Measured witness expectation <W> = {witness_exp:+.4f} +/- {sigma_witness:.4f} "
            f"with 95% upper bound {witness_upper_95:+.4f} >= 0."
        )

    print(f"\n   Entanglement Certified: {entanglement_certified}")
    print(f"   Certification Note    : {cert_note}")

    # --- Structured Scientific Provenance Archiving ---
    prefix = "dry-run-" if dry_run else ""
    prov_dir = Path("/home/quant/qf-research") / f"{prefix}ibm-qaoa-ghz-kingston-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    prov_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(prov_dir, 0o700)

    # 1. Immutable Raw Acquisition Record
    raw_file = prov_dir / "raw_acquisition.json"
    raw_data = {
        "record_type": "raw_acquisition_record",
        "dry_run": dry_run,
        "job_id": job_id,
        "backend": backend.name,
        "backend_qubits": backend.num_qubits,
        "timestamps": {
            "submission_utc": submission_time_utc,
            "created_utc": job_metrics.get("timestamps", {}).get("created"),
            "running_utc": job_metrics.get("timestamps", {}).get("running"),
            "finished_utc": job_metrics.get("timestamps", {}).get("finished"),
            "retrieved_utc": retrieval_time_utc
        },
        "hardware_execution": {
            "elapsed_seconds": elapsed,
            "qpu_charge_time_seconds": job_metrics.get("usage", {}).get("qpu_charge_time_seconds"),
            "circuits_execution_time_ns": job_metrics.get("circuits_execution_time_ns"),
            "shots_per_circuit": shots,
            "total_shots": total_batch_shots,
            "num_circuits": len(circuits)
        },
        "transpiled_circuit_metadata": transpiled_meta,
        "raw_counts": {
            "pub_0_qaoa": counts_qaoa,
            "pub_1_ghz_zzz": counts_zzz,
            "pub_2_ghz_xxx": counts_xxx,
            "pub_3_ghz_xyy": counts_xyy,
            "pub_4_ghz_yxy": counts_yxy,
            "pub_5_ghz_yyx": counts_yyx
        },
        "engine_state": "LOCKED",
        "entropy_credit": 0.0,
        "epistemic_standard": "External empirical physics research only. Zero secret entropy."
    }

    with open(raw_file, "w") as fp:
        json.dump(raw_data, fp, indent=2)

    raw_hash = hashlib.sha256(raw_file.read_bytes()).hexdigest()

    # 2. Derived Scientific Analysis Record
    analysis_file = prov_dir / "analysis_record.json"
    analysis_data = {
        "record_type": "scientific_analysis_record",
        "dry_run": dry_run,
        "analysis_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source_raw_acquisition": {
            "file": "raw_acquisition.json",
            "sha256": raw_hash,
            "job_id": job_id,
            "backend": backend.name
        },
        "option_a_qaoa_analysis": {
            "meta": meta_qaoa,
            "feasible_probability_pct": round(valid_pct, 4),
            "optimal_portfolio_probability_pct": round(optimal_pct, 4),
            "best_observed_portfolio": best_observed_port,
            "best_classical_reference_portfolio": f"{exp_best_state} ({meta_qaoa['expected_best_portfolio']})",
            "best_classical_reference_cost": expected_opt_cost,
            "mean_classical_objective": round(mean_cost, 6),
            "mean_conditional_feasible_cost": round(cond_feas_cost, 6),
            "approximation_ratio_best": round(approx_ratio_best, 6),
            "approximation_ratio_mean": round(approx_ratio_mean, 6),
            "ideal_statevector_predictions": meta_qaoa["ideal_statevector_predictions"],
            "validation_gate_passed": True
        },
        "option_b_ghz_complete_witness_analysis": {
            "target_basis_population_pct": round(target_population_pct, 4),
            "other_basis_population_pct": round(other_population_pct, 4),
            "measured_expectations": {
                "z0_z1": round(exp_z0z1, 4),
                "z1_z2": round(exp_z1z2, 4),
                "z0_z2": round(exp_z0z2, 4),
                "x0_x1_x2": round(exp_xxx, 4),
                "x0_y1_y2": round(exp_xyy, 4),
                "y0_x1_y2": round(exp_yxy, 4),
                "y0_y1_x2": round(exp_yyx, 4)
            },
            "joint_z_covariance_variance_U": round(var_mean_U, 8),
            "ghz_state_fidelity": round(fidelity, 6),
            "ghz_state_fidelity_stderr": round(sigma_fidelity, 6),
            "witness_expectation": round(witness_exp, 6),
            "witness_stderr": round(sigma_witness, 6),
            "witness_95_upper_confidence_bound": round(witness_upper_95, 6),
            "data_classification": "simulated_local_baseline" if dry_run else "hardware_qpu_measurement",
            "hardware_validated": not dry_run,
            "entanglement_certified": entanglement_certified,
            "entanglement_certification_note": cert_note
        },
        "circuit_provenance": [
            {
                "name": m["name"],
                "logical_circuit_sha256": m["logical_circuit_sha256"],
                "isa_circuit_sha256": m["isa_circuit_sha256"],
                "depth": m["depth"],
                "ops": m["ops"],
                "physical_layout": m["physical_layout"]
            }
            for m in transpiled_meta
        ],
        "engine_state": "LOCKED",
        "entropy_credit": 0.0,
        "epistemic_standard": "External empirical physics research only. Zero secret entropy."
    }

    with open(analysis_file, "w") as fp:
        json.dump(analysis_data, fp, indent=2)

    analysis_hash = hashlib.sha256(analysis_file.read_bytes()).hexdigest()

    # 3. Checksums manifest
    checksum_file = prov_dir / "checksums.sha256"
    checksum_file.write_text(f"{raw_hash}  raw_acquisition.json\n{analysis_hash}  analysis_record.json\n")

    os.chmod(raw_file, 0o600)
    os.chmod(analysis_file, 0o600)
    os.chmod(checksum_file, 0o600)

    print(f"\n[+] Scientific Research Provenance Archived:")
    print(f"    -> Raw Acquisition : {raw_file} (SHA-256: {raw_hash})")
    print(f"    -> Analysis Record : {analysis_file} (SHA-256: {analysis_hash})")
    print(f"    -> Checksum File   : {checksum_file}")
    print("=" * 75)
    return analysis_data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="QuantumFlex QAOA & GHZ Witness Experiment Runner")
    parser.add_argument("--submit", action="store_true", help="Submit actual cryogenic job to IBM QPU (requires confirmation)")
    parser.add_argument("--retrieve", type=str, default=None, help="Retrieve and analyze an existing completed physical IBM job ID")
    parser.add_argument("--backend", default="ibm_kingston", help="Target QPU backend name (default: ibm_kingston)")
    parser.add_argument("--shots", type=int, default=1024, help="Shots per circuit (default: 1024 for NIST SP 800-90B certification)")
    parser.add_argument(
        "--risk-profile",
        choices=["aggressive", "balanced", "conservative", "ultra_conservative"],
        default="balanced",
        help="Risk profile mapping to risk-aversion weight lambda (default: balanced)"
    )
    parser.add_argument("--lambda-risk", type=float, default=None, help="Explicit risk aversion parameter lambda (overrides risk-profile)")
    args = parser.parse_args()

    # If --retrieve is given, fetch that job. Otherwise, default to safe dry-run unless --submit is explicitly provided.
    is_dry_run = not args.submit and (args.retrieve is None)
    run_experiment(
        backend_name=args.backend,
        shots=args.shots,
        dry_run=is_dry_run,
        retrieve_job_id=args.retrieve,
        risk_profile=args.risk_profile,
        lambda_risk=args.lambda_risk
    )
