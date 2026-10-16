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

# Ensure quantum_worker imports work
sys.path.insert(0, "/home/quant/Documents/qf")
from quantum_worker import QuantumWorker

from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2 as Sampler
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager


def classical_portfolio_cost(x: list[int] | np.ndarray) -> float:
    """Evaluate classical Markowitz portfolio cost: -mu^T x + lambda x^T Sigma x + penalty (sum(x) - B)^2"""
    mu = np.array([0.15, 0.10, 0.05], dtype=float)
    cov = np.array([
        [0.08,  0.02, -0.01],
        [0.02,  0.06,  0.00],
        [-0.01, 0.00,  0.01]
    ], dtype=float)
    risk_weight = 0.5
    budget = 2
    penalty = 1.0
    x_arr = np.asarray(x, dtype=float)
    return float(
        -mu @ x_arr
        + risk_weight * (x_arr @ cov @ x_arr)
        + penalty * (x_arr.sum() - budget) ** 2
    )


def build_qaoa_portfolio_circuit() -> tuple[QuantumCircuit, dict]:
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

    risk_weight = 0.5
    budget = 2
    penalty = 1.0
    n = 3

    # Derive binary expansion coefficients: C(x) = const + sum_i a_i x_i + sum_{i < j} b_ij x_i x_j
    a = -mu + risk_weight * np.diag(cov) + penalty * (1.0 - 2.0 * budget)
    b = np.zeros((n, n), dtype=float)
    for i in range(n):
        for j in range(n):
            if i != j:
                b[i, j] = 2.0 * risk_weight * cov[i, j] + 2.0 * penalty

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

    meta = {
        "algorithm": "QAOA",
        "assets": ["Tech_Growth", "Energy_Dividend", "Treasury_Bond"],
        "budget": budget,
        "risk_weight": risk_weight,
        "penalty": penalty,
        "gamma": gamma,
        "beta": beta,
        "ising_linear_h": [float(val) for val in h],
        "ising_coupling_J": {f"{i}_{j}": float(J[i, j]) for i in range(n) for j in range(i + 1, n)},
        "expected_best_state": "101",
        "expected_best_portfolio": "Asset 0 (Tech) + Asset 2 (Treasury)",
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


def run_experiment(backend_name: str = "ibm_kingston", shots: int = 256, dry_run: bool = True):
    mode_str = "[DRY-RUN / LOCAL VERIFICATION]" if dry_run else "[HARDWARE CRYOGENIC EXECUTION]"
    print("=" * 75)
    print(" QUANTUMFLEX PHYSICAL QPU RESEARCH: QAOA & COMPLETE GHZ WITNESS")
    print(f" Execution Mode : {mode_str}")
    print(f" Target Silicon : {backend_name} (156 Physical Transmons, Heron r2)")
    print(f" Requested Shots: {shots} per circuit (Batch: 6 circuits, {shots * 6} total shots)")
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
    qc_qaoa, meta_qaoa = build_qaoa_portfolio_circuit()
    qc_zzz, meta_zzz = build_ghz_zzz_circuit()
    qc_xxx, meta_xxx = build_ghz_xxx_circuit()
    qc_xyy, meta_xyy = build_ghz_xyy_circuit()
    qc_yxy, meta_yxy = build_ghz_yxy_circuit()
    qc_yyx, meta_yyx = build_ghz_yyx_circuit()

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
        print(f"      ISA Circuit {i} ({orig.name:<18}): Depth {isa.depth():<2} | Layout: {layout} | Ops: {dict(isa.count_ops())}")
        transpiled_meta.append({
            "name": orig.name,
            "depth": isa.depth(),
            "ops": dict(isa.count_ops()),
            "physical_layout": layout
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

        # Simulate ideal counts for each circuit
        counts_list = []
        for qc in circuits:
            uc = qc.remove_final_measurements(inplace=False)
            sv = Statevector.from_instruction(uc)
            probs = sv.probabilities_dict()
            # Generate deterministic sample counts matching probabilities
            sim_counts = {}
            for s, p in probs.items():
                c = int(round(p * shots))
                if c > 0:
                    sim_counts[s] = c
            # Adjust rounding difference on largest state
            diff = shots - sum(sim_counts.values())
            if diff != 0:
                top_s = max(sim_counts.keys(), key=lambda k: sim_counts[k])
                sim_counts[top_s] += diff
            counts_list.append(sim_counts)
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
            if job_status != last_status:
                print(f"      [{int(time.time() - start_time)}s] Job Status: {job_status.name}")
                last_status = job_status
            if job_status.name in ("DONE", "CANCELLED", "ERROR"):
                break
            time.sleep(3)

        if job_status.name != "DONE":
            raise RuntimeError(f"Physical execution terminated with status: {job_status.name}")

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
        c = classical_portfolio_cost(x)
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

    print(f"\n   Feasible Subspace Probability : {valid_pct:.2f}% ({valid_budget_counts}/{total_qaoa} shots)")
    print(f"   Best Observed Feasible Port   : {best_observed_port}")
    print(f"   Mean Classical Objective      : {mean_cost:+.6f}")
    print(f"   Mean Conditional Feasible Cost: {cond_feas_cost:+.6f}")

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
            "best_observed_portfolio": best_observed_port,
            "best_classical_reference_portfolio": "101 (Tech + Treasury)",
            "best_classical_reference_cost": -0.165000,
            "mean_classical_objective": round(mean_cost, 6),
            "mean_conditional_feasible_cost": round(cond_feas_cost, 6),
            "ideal_statevector_predictions": meta_qaoa["ideal_statevector_predictions"]
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
    parser.add_argument("--backend", default="ibm_kingston", help="Target QPU backend name (default: ibm_kingston)")
    parser.add_argument("--shots", type=int, default=256, help="Shots per circuit (default: 256)")
    args = parser.parse_args()

    # Default to safe dry-run unless --submit is explicitly provided
    is_dry_run = not args.submit
    run_experiment(backend_name=args.backend, shots=args.shots, dry_run=is_dry_run)
