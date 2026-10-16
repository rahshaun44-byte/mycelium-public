#!/usr/bin/env python3
"""
QuantumFlex Physical Quantum Experiment Runner: QAOA Portfolio & Multi-Basis GHZ
Target QPU: ibm_kingston (Heron Revision 2, 156 Physical Transmon Qubits)
Epistemic Boundary: Physical research testbed; zero entropy admitted to engine.
Engine Posture: LOCKED (fail-closed zero-trust boundary maintained).
"""

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


def build_ghz_3q_circuit() -> tuple[QuantumCircuit, dict]:
    """Construct a 3-qubit GHZ state (|000> + |111>) / sqrt(2) circuit in computational Z-basis."""
    qc = QuantumCircuit(3, 3, name="ghz_3q_z_basis")
    qc.h(0)
    qc.cx(0, 1)
    qc.cx(1, 2)
    qc.measure(range(3), range(3))

    meta = {
        "algorithm": "GHZ_Tripartite_State",
        "target_state": "(|000> + |111>) / sqrt(2)",
        "measurement_basis": "Pauli_Z (Computational)",
        "num_qubits": 3
    }
    return qc, meta


def build_ghz_x_basis_circuit() -> tuple[QuantumCircuit, dict]:
    r"""
    Construct a 3-qubit GHZ state circuit with basis rotations to measure in the Pauli X basis (X \otimes X \otimes X).
    
    In the X basis, an ideal GHZ state produces only even parity bitstrings ('000', '011', '101', '110')
    with equal probability (25% each), giving <X0 X1 X2> = +1.0.
    
    SCIENTIFIC QUALIFICATION:
      Measuring all three qubits in the X-basis alone produces <X0 X1 X2> = +1 and verifies phase
      coherence between |000> and |111>. However, a single X-basis measurement setting is NOT sufficient
      on its own to certify genuine tripartite entanglement. A classical mixture can reproduce Z-basis
      correlations, and other non-GHZ quantum states can reproduce specific single-basis correlations.
      
      To certify genuine tripartite entanglement, one must evaluate an entanglement witness across multiple
      bases, such as:
          W = 0.5 * I - |GHZ_3><GHZ_3|
      A negative expectation value (<W> < 0) under appropriate calibration assumptions certifies genuine
      tripartite entanglement. Until multi-basis witness or tomography data is collected,
      entanglement_certified must remain False.
    """
    qc = QuantumCircuit(3, 3, name="ghz_3q_x_basis")
    qc.h(0)
    qc.cx(0, 1)
    qc.cx(1, 2)
    for i in range(3):
        qc.h(i)
    qc.measure(range(3), range(3))

    meta = {
        "algorithm": "GHZ_Tripartite_State_X_Basis",
        "target_state": "(|000> + |111>) / sqrt(2)",
        "measurement_basis": "Pauli_X",
        "num_qubits": 3,
        "ideal_x_parity_expectation": 1.0,
        "purpose": "Phase coherence verification (single basis; insufficient alone to certify tripartite entanglement)",
        "entanglement_certified": False,
        "entanglement_note": "Multi-basis witness evaluation (e.g. W = 0.5*I - |GHZ><GHZ|) required for tripartite certification."
    }
    return qc, meta


def build_ghz_yyx_circuit() -> tuple[QuantumCircuit, dict]:
    r"""
    Construct a 3-qubit GHZ state circuit with rotations to measure in the X_0 \otimes Y_1 \otimes Y_2 basis.
    On ideal GHZ state, <X_0 Y_1 Y_2> = -1.0.
    Rotation mapping:
      Qubit 0 (X basis): H
      Qubits 1, 2 (Y basis): S^\dagger then H
    """
    qc = QuantumCircuit(3, 3, name="ghz_3q_yyx_basis")
    qc.h(0)
    qc.cx(0, 1)
    qc.cx(1, 2)
    # Qubit 0 -> X
    qc.h(0)
    # Qubits 1, 2 -> Y
    qc.sdg(1)
    qc.h(1)
    qc.sdg(2)
    qc.h(2)
    qc.measure(range(3), range(3))

    meta = {
        "algorithm": "GHZ_Tripartite_State_YYX_Basis",
        "target_state": "(|000> + |111>) / sqrt(2)",
        "measurement_basis": "Pauli_X0_Y1_Y2",
        "num_qubits": 3,
        "ideal_expectation": -1.0,
        "purpose": "Multi-basis witness term component <X0 Y1 Y2>",
        "entanglement_certified": False
    }
    return qc, meta


def run_experiment(backend_name: str = "ibm_kingston", shots: int = 256):
    print("=" * 75)
    print(" QUANTUMFLEX PHYSICAL QPU RESEARCH: QAOA PORTFOLIO & MULTI-BASIS GHZ")
    print(f" Target Silicon : {backend_name} (156 Physical Transmons, Heron r2)")
    print(f" Requested Shots: {shots} per circuit (Validation Run)")
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

    print(f"\n[2/5] Building Quantum Research Circuits (4-Circuit Validation Suite)...")
    qc_qaoa, meta_qaoa = build_qaoa_portfolio_circuit()
    qc_ghz_z, meta_ghz_z = build_ghz_3q_circuit()
    qc_ghz_x, meta_ghz_x = build_ghz_x_basis_circuit()
    qc_ghz_yyx, meta_ghz_yyx = build_ghz_yyx_circuit()

    circuits = [qc_qaoa, qc_ghz_z, qc_ghz_x, qc_ghz_yyx]
    print(f"      Circuit 0: {qc_qaoa.name} (QAOA Markowitz Portfolio, Depth: {qc_qaoa.depth()})")
    print(f"      Circuit 1: {qc_ghz_z.name} (GHZ Z-Basis Populations, Depth: {qc_ghz_z.depth()})")
    print(f"      Circuit 2: {qc_ghz_x.name} (GHZ X-Basis <XXX> Coherence, Depth: {qc_ghz_x.depth()})")
    print(f"      Circuit 3: {qc_ghz_yyx.name} (GHZ YYX-Basis <XYY> Witness Term, Depth: {qc_ghz_yyx.depth()})")

    print(f"\n[3/5] Transpiling to Physical Heron ISA Architecture...")
    pm = generate_preset_pass_manager(backend=backend, optimization_level=1)
    isa_circuits = [pm.run(qc) for qc in circuits]
    
    transpiled_meta = []
    for i, (orig, isa) in enumerate(zip(circuits, isa_circuits)):
        layout = isa.layout.final_index_layout() if hasattr(isa, "layout") and isa.layout else None
        print(f"      ISA Circuit {i} ({orig.name}): Depth {isa.depth()} | Layout: {layout} | Ops: {dict(isa.count_ops())}")
        transpiled_meta.append({
            "name": orig.name,
            "depth": isa.depth(),
            "ops": dict(isa.count_ops()),
            "physical_layout": layout
        })

    total_batch_shots = shots * len(circuits)
    print(f"\n[4/5] Submitting Batched PUB Execution ({len(circuits)} Circuits, {total_batch_shots} Total Shots)...")
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

    print(f"\n[5/5] Extracting Real Measurement Histograms & Epistemic Analysis...")
    result = job.result()
    retrieval_time_utc = datetime.now(timezone.utc).isoformat()

    job_metrics = {}
    try:
        job_metrics = job.metrics()
    except Exception as e:
        print(f"      Note: Could not retrieve server job metrics: {e}")

    # Extract Counts
    counts_qaoa = list(result[0].data.values())[0].get_counts()
    counts_ghz_z = list(result[1].data.values())[0].get_counts()
    counts_ghz_x = list(result[2].data.values())[0].get_counts()
    counts_ghz_yyx = list(result[3].data.values())[0].get_counts()

    total_qaoa = sum(counts_qaoa.values())
    total_ghz_z = sum(counts_ghz_z.values())
    total_ghz_x = sum(counts_ghz_x.values())
    total_ghz_yyx = sum(counts_ghz_yyx.values())

    # --- Comprehensive QAOA Analysis ---
    print("\n" + "-" * 75)
    print(" [ANALYSIS A] QAOA QUANTUM PORTFOLIO SELECTION RESULTS (ibm_kingston)")
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

    # --- Comprehensive GHZ Multi-Basis Analysis ---
    print("\n" + "-" * 75)
    print(" [ANALYSIS B] GHZ MULTI-BASIS ENTANGLEMENT ANALYSIS (ibm_kingston)")
    print("-" * 75)
    c000 = counts_ghz_z.get("000", 0)
    c111 = counts_ghz_z.get("111", 0)
    target_shots = c000 + c111
    target_population_pct = (target_shots / total_ghz_z) * 100
    other_population_pct = ((total_ghz_z - target_shots) / total_ghz_z) * 100

    # Pairwise Z correlations from Z-basis counts
    def calc_2body_z(counts, total, q_i, q_j):
        # bit q is at index (2 - q)
        return sum((+1 if (int(s[2-q_i]) + int(s[2-q_j])) % 2 == 0 else -1) * cnt for s, cnt in counts.items()) / total

    exp_z0z1 = calc_2body_z(counts_ghz_z, total_ghz_z, 0, 1)
    exp_z1z2 = calc_2body_z(counts_ghz_z, total_ghz_z, 1, 2)
    exp_z0z2 = calc_2body_z(counts_ghz_z, total_ghz_z, 0, 2)

    # 3-body parity from X-basis counts
    exp_xxx = sum((+1 if (int(s[0]) + int(s[1]) + int(s[2])) % 2 == 0 else -1) * cnt for s, cnt in counts_ghz_x.items()) / total_ghz_x
    # 3-body parity from YYX-basis counts (<X0 Y1 Y2>)
    exp_yyx = sum((+1 if (int(s[0]) + int(s[1]) + int(s[2])) % 2 == 0 else -1) * cnt for s, cnt in counts_ghz_yyx.items()) / total_ghz_yyx

    print(f"   1. Computational Z-Basis:")
    print(f"      Target Population (|000> + |111>): {target_population_pct:.2f}% ({target_shots}/{total_ghz_z})")
    print(f"      Noise / Non-Target Population    : {other_population_pct:.2f}%")
    print(f"      Correlations: <Z0 Z1> = {exp_z0z1:+.4f}, <Z1 Z2> = {exp_z1z2:+.4f}, <Z0 Z2> = {exp_z0z2:+.4f}")
    print(f"   2. Pauli X-Basis:")
    print(f"      Parity Contrast <X0 X1 X2>       : {exp_xxx:+.4f} (Ideal: +1.0000)")
    print(f"   3. Pauli YYX-Basis:")
    print(f"      Expectation <X0 Y1 Y2>           : {exp_yyx:+.4f} (Ideal: -1.0000)")
    print(f"\n   Scientific Certification Note:")
    print(f"      Entanglement Certified: False")
    print(f"      Reason: Full tripartite witness certification requires complete set of 5 basis settings")
    print(f"              or tomography. Single and partial basis data demonstrate state correlations only.")

    # --- Structured Scientific Provenance Archiving ---
    prov_dir = Path("/home/quant/qf-research") / f"ibm-qaoa-ghz-kingston-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    prov_dir.mkdir(parents=True, exist_ok=True)

    # 1. Immutable Raw Acquisition Record
    raw_file = prov_dir / "raw_acquisition.json"
    raw_data = {
        "record_type": "raw_acquisition_record",
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
            "pub_1_ghz_z": counts_ghz_z,
            "pub_2_ghz_x": counts_ghz_x,
            "pub_3_ghz_yyx": counts_ghz_yyx
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
        "option_b_ghz_analysis": {
            "target_basis_population_pct": round(target_population_pct, 4),
            "other_basis_population_pct": round(other_population_pct, 4),
            "pairwise_z_correlations": {
                "z0_z1": round(exp_z0z1, 4),
                "z1_z2": round(exp_z1z2, 4),
                "z0_z2": round(exp_z0z2, 4)
            },
            "xxx_parity_contrast": round(exp_xxx, 4),
            "yyx_witness_expectation": round(exp_yyx, 4),
            "entanglement_certified": False,
            "entanglement_certification_note": (
                "Computational Z-basis measurements alone cannot distinguish a genuine GHZ state "
                "from a classical statistical mixture. Furthermore, a single X-basis measurement "
                "setting is insufficient to certify genuine tripartite entanglement. "
                "Certification requires multi-basis measurements evaluating an entanglement witness "
                "(e.g., W = 0.5*I - |GHZ><GHZ|) across all 5 settings or quantum state tomography. "
                "Zero entanglement is certified from single or partial basis data."
            )
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
    run_experiment(backend_name="ibm_kingston", shots=256)
