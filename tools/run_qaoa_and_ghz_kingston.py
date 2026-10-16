#!/usr/bin/env python3
"""
QuantumFlex Physical Quantum Experiment Runner: QAOA Portfolio & GHZ 3Q
Target QPU: ibm_kingston (Heron Revision 2, 156 Physical Transmon Qubits)
Epistemic Boundary: Physical research testbed; zero entropy admitted to engine.
Engine Posture: LOCKED (fail-closed zero-trust boundary maintained).
"""

import hashlib
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
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2 as Sampler
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager


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
        "expected_best_portfolio": "Asset 0 (Tech) + Asset 2 (Treasury)"
    }
    return qc, meta


def build_ghz_3q_circuit() -> tuple[QuantumCircuit, dict]:
    """Construct a 3-qubit GHZ state (|000> + |111>) / sqrt(2) circuit in computational Z-basis."""
    qc = QuantumCircuit(3, 3, name="ghz_3q_tripartite")
    qc.h(0)
    qc.cx(0, 1)
    qc.cx(1, 2)
    qc.measure(range(3), range(3))

    meta = {
        "algorithm": "GHZ_Tripartite_Entanglement",
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
    This measurement measures off-diagonal coherence terms needed to distinguish true entanglement
    from classical statistical mixtures.
    """
    qc = QuantumCircuit(3, 3, name="ghz_3q_x_basis")
    qc.h(0)
    qc.cx(0, 1)
    qc.cx(1, 2)
    for i in range(3):
        qc.h(i)
    qc.measure(range(3), range(3))

    meta = {
        "algorithm": "GHZ_Tripartite_Entanglement_X_Basis",
        "target_state": "(|000> + |111>) / sqrt(2)",
        "measurement_basis": "Pauli_X",
        "num_qubits": 3,
        "ideal_x_parity_expectation": 1.0,
        "purpose": "Phase coherence and multi-basis entanglement certification"
    }
    return qc, meta


def run_experiment(backend_name: str = "ibm_kingston", shots: int = 1024):
    print("=" * 75)
    print(" QUANTUMFLEX PHYSICAL QPU RESEARCH: QAOA PORTFOLIO & GHZ 3Q")
    print(f" Target Silicon : {backend_name} (156 Physical Transmons, Heron r2)")
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

    print(f"\n[2/5] Building Quantum Research Circuits...")
    qc_qaoa, meta_qaoa = build_qaoa_portfolio_circuit()
    qc_ghz, meta_ghz = build_ghz_3q_circuit()
    print(f"      Circuit A: {qc_qaoa.name} (QAOA Markowitz Portfolio, Depth: {qc_qaoa.depth()})")
    print(f"      Circuit B: {qc_ghz.name} (Tripartite GHZ Entanglement, Depth: {qc_ghz.depth()})")

    print(f"\n[3/5] Transpiling to Physical Heron ISA Architecture...")
    pm = generate_preset_pass_manager(backend=backend, optimization_level=1)
    isa_qaoa = pm.run(qc_qaoa)
    isa_ghz = pm.run(qc_ghz)
    print(f"      ISA Circuit A: Depth {isa_qaoa.depth()} | Ops: {dict(isa_qaoa.count_ops())}")
    print(f"      ISA Circuit B: Depth {isa_ghz.depth()} | Ops: {dict(isa_ghz.count_ops())}")

    print(f"\n[4/5] Submitting Batched PUB Execution to Physical Cryostat...")
    sampler = Sampler(mode=backend)
    job = sampler.run([isa_qaoa, isa_ghz], shots=shots)
    job_id = job.job_id()
    print(f"      Job ID: {job_id}")
    print(f"      Submission Time: {datetime.now(timezone.utc).isoformat()}")
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
    
    # Process Circuit A: QAOA
    pub_qaoa = result[0]
    counts_qaoa = list(pub_qaoa.data.values())[0].get_counts()
    total_qaoa = sum(counts_qaoa.values())

    # Process Circuit B: GHZ
    pub_ghz = result[1]
    counts_ghz = list(pub_ghz.data.values())[0].get_counts()
    total_ghz = sum(counts_ghz.values())

    # --- Analysis Option A: QAOA Portfolio ---
    print("\n" + "-" * 75)
    print(" [OPTION A] QAOA QUANTUM PORTFOLIO SELECTION RESULTS (ibm_kingston)")
    print("-" * 75)
    print(f" Total Measurement Shots: {total_qaoa}")
    print(" Observed Portfolios (Binary string = [Asset2, Asset1, Asset0]):")
    
    # Sort by probability
    sorted_qaoa = sorted(counts_qaoa.items(), key=lambda x: x[1], reverse=True)
    valid_budget_counts = 0
    for state, cnt in sorted_qaoa:
        prob = (cnt / total_qaoa) * 100
        # Check budget constraint (sum of bits == 2)
        ones_count = state.count("1")
        valid_tag = "[VALID 2-ASSET BUDGET]" if ones_count == 2 else "[BUDGET PENALIZED]"
        if ones_count == 2:
            valid_budget_counts += cnt
        print(f"   |{state}> : {cnt:4d} shots ({prob:5.2f}%)  {valid_tag}")

    valid_pct = (valid_budget_counts / total_qaoa) * 100
    print(f"\n Quantum Budget Constraint Convergence: {valid_pct:.2f}% ({valid_budget_counts}/{total_qaoa} shots)")

    # --- Analysis Option B: GHZ State Analysis ---
    print("\n" + "-" * 75)
    print(" [OPTION B] 3-QUBIT GHZ STATE MEASUREMENT (ibm_kingston, Z-Basis)")
    print("-" * 75)
    print(f" Total Measurement Shots: {total_ghz}")
    sorted_ghz = sorted(counts_ghz.items(), key=lambda x: x[1], reverse=True)
    for state, cnt in sorted_ghz:
        prob = (cnt / total_ghz) * 100
        print(f"   |{state}> : {cnt:4d} shots ({prob:5.2f}%)")

    c000 = counts_ghz.get("000", 0)
    c111 = counts_ghz.get("111", 0)
    target_shots = c000 + c111
    target_population_pct = (target_shots / total_ghz) * 100
    other_shots = total_ghz - target_shots
    other_population_pct = (other_shots / total_ghz) * 100

    # ZZZ expectation value: <Z0 Z1 Z2> = sum_s (-1)^{parity(s)} P(s)
    # Even number of 1s -> +1, Odd number of 1s -> -1
    zzz_exp = sum((+1 if s.count("1") % 2 == 0 else -1) * cnt for s, cnt in counts_ghz.items()) / total_ghz

    print(f"\n Computational Basis Target Population (|000> + |111>): {target_population_pct:.2f}% ({target_shots}/{total_ghz})")
    print(f" Non-Target / Noise Population: {other_population_pct:.2f}% ({other_shots}/{total_ghz})")
    print(f" ZZZ Expectation <Z0 Z1 Z2>: {zzz_exp:+.4f}")
    print(" Note: Computational-basis (Z) statistics demonstrate population alignment")
    print("       but cannot certify entanglement without complementary basis measurements (e.g. X-basis).")

    # Provenance Archiving
    prov_dir = Path("/home/quant/qf-research") / f"ibm-qaoa-ghz-kingston-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    prov_dir.mkdir(parents=True, exist_ok=True)
    prov_file = prov_dir / "provenance.json"

    prov_data = {
        "provenance_type": "research_provenance_record",
        "job_id": job_id,
        "backend": backend.name,
        "backend_qubits": backend.num_qubits,
        "utc_timestamp": datetime.now(timezone.utc).isoformat(),
        "shots_per_circuit": shots,
        "total_shots": shots * 2,
        "elapsed_seconds": elapsed,
        "option_a_qaoa": {
            "meta": meta_qaoa,
            "counts": counts_qaoa,
            "valid_budget_pct": round(valid_pct, 4),
            "best_classical_portfolio": "101 (Tech_Growth + Treasury_Bond)"
        },
        "option_b_ghz": {
            "meta": meta_ghz,
            "counts": counts_ghz,
            "target_basis_population_pct": round(target_population_pct, 4),
            "other_basis_population_pct": round(other_population_pct, 4),
            "zzz_expectation": round(zzz_exp, 4),
            "entanglement_certified": False,
            "entanglement_note": "Z-basis measurement alone cannot distinguish GHZ state from classical mixture. Multi-basis measurement (e.g., X-basis) is required to certify entanglement."
        },
        "engine_state": "LOCKED",
        "entropy_credit": 0.0,
        "epistemic_standard": "External empirical physics research only. Zero secret entropy."
    }

    with open(prov_file, "w") as fp:
        json.dump(prov_data, fp, indent=2)

    sha256_hash = hashlib.sha256(prov_file.read_bytes()).hexdigest()
    sha_file = prov_dir / "provenance.sha256"
    sha_file.write_text(f"{sha256_hash}  provenance.json\n")

    os.chmod(sha_file, 0o600)
    os.chmod(prov_file, 0o600)
    print(f"\n[+] Research Provenance Record Saved:")
    print(f"    -> {prov_file} (mode 0600)")
    print(f"    -> {sha_file} (SHA-256: {sha256_hash})")
    print("=" * 75)
    return prov_data


if __name__ == "__main__":
    run_experiment(backend_name="ibm_kingston", shots=1024)
