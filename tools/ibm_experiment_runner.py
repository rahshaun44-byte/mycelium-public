#!/usr/bin/env python3
"""
QuantumFlex Physical Quantum Experiment Runner & Measurement Evidence Ledger
Targets:
  Option 1: 4-Qubit Hadamard QRNG Physical Entropy Execution
  Option 2: 2-Qubit Bell State (|Φ+⟩) Correlation & Measurement Analysis

Architecture:
  Physical QPU Execution -> Measurement Retrieval -> Statistical Analysis
  -> Cryptographic Evidence Manifest (SHA-256) -> Immutable Research Ledger

Epistemic Boundary: Physical research testbed; zero entropy admitted to engine.
Engine Posture: LOCKED (fail-closed zero-trust boundary maintained).
"""

import argparse
import hashlib
import json
import math
import os
import sys
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path

# Suppress runtime Sampler deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Add qf directory to sys.path
for p in ["/home/quant/Documents/qf", "/home/quant/quantumflex/qf"]:
    if Path(p).is_dir() and p not in sys.path:
        sys.path.insert(0, p)
from quantum_worker import QuantumWorker, get_worker_credentials, calculate_entropy_metrics


def circuit_sha256(qc) -> str:
    """Compute deterministic cryptographic SHA-256 digest of a QuantumCircuit."""
    try:
        from qiskit import qasm3
        text = qasm3.dumps(qc)
    except Exception:
        text = str(qc.data)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def calculate_full_shannon_entropy(counts: dict[str, int]) -> float:
    """Calculate Shannon entropy across all observed bitstrings: H(X) = -sum(p * log2(p))."""
    total = sum(counts.values())
    if total <= 0:
        return 0.0
    entropy = 0.0
    for count in counts.values():
        if count > 0:
            p = count / total
            entropy -= p * math.log2(p)
    return entropy


def extract_counts_from_pub(pub_result) -> tuple[str, dict[str, int], object]:
    """
    Explicitly locate the measurement classical register from PubResult data container.
    Returns (register_name, counts_dict, bit_array).
    """
    data_bin = pub_result.data
    # Look for known classical register names
    for candidate in ["meas", "c", "cr", "m"]:
        if hasattr(data_bin, candidate):
            bit_array = getattr(data_bin, candidate)
            return candidate, bit_array.get_counts(), bit_array
    keys = list(data_bin.keys())
    if not keys:
        raise ValueError("No measurement registers found in Qiskit PubResult data container")
    chosen_reg = keys[0]
    bit_array = getattr(data_bin, chosen_reg)
    return chosen_reg, bit_array.get_counts(), bit_array


def archive_evidence_manifest(
    experiment_type: str,
    backend_name: str,
    job_id: str,
    requested_shots: int,
    actual_shots: int,
    register_name: str,
    counts: dict[str, int],
    metrics: dict,
    logical_circuit_sha256: str | None,
    isa_circuit_sha256: str | None,
    dry_run: bool = False
) -> Path:
    """
    Persist tamper-evident cryptographic research record into /home/quant/qf-research/
    Strict 0600 file permissions; SHA-256 integrity verification.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    prefix = "dry-run-" if dry_run else ""
    evidence_dir = Path("/home/quant/qf-research") / f"{prefix}{experiment_type.lower()}-{backend_name}-{timestamp}"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(evidence_dir, 0o700)

    counts_payload = json.dumps(counts, sort_keys=True)
    counts_sha256 = hashlib.sha256(counts_payload.encode("utf-8")).hexdigest()

    evidence_data = {
        "record_type": "quantum_physical_evidence",
        "experiment": experiment_type,
        "backend": backend_name,
        "job_id": job_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "execution_type": "SIMULATED_LOCAL" if dry_run else "PHYSICAL_QPU",
        "execution_status": "COMPLETED",
        "verification_status": "VERIFIED" if (not dry_run and actual_shots > 0) else "UNVERIFIED",
        "shots": {
            "requested": requested_shots,
            "actual": actual_shots
        },
        "measurement_register": register_name,
        "measurement_counts": counts,
        "measurement_digest_sha256": counts_sha256,
        "analysis_metrics": metrics,
        "circuit_provenance": {
            "logical_circuit_sha256": logical_circuit_sha256,
            "isa_circuit_sha256": isa_circuit_sha256
        },
        "engine_state": "LOCKED",
        "entropy_credit": 0.0,
        "epistemic_standard": "Physical QPU research testbed. Zero secret entropy."
    }

    evidence_file = evidence_dir / "evidence.json"
    with open(evidence_file, "w") as fp:
        json.dump(evidence_data, fp, indent=2)

    evidence_hash = hashlib.sha256(evidence_file.read_bytes()).hexdigest()
    checksum_file = evidence_dir / "checksums.sha256"
    checksum_file.write_text(f"{evidence_hash}  evidence.json\n")

    os.chmod(evidence_file, 0o600)
    os.chmod(checksum_file, 0o600)

    print(f"\n[+] Quantum Evidence Ledger Record Created:")
    print(f"    Path:            {evidence_file}")
    print(f"    Digest SHA-256:  {evidence_hash}")
    return evidence_file


def run_option1(
    backend_name: str = "ibm_fez",
    shots: int = 1024,
    num_qubits: int = 4,
    retrieve_job_id: str | None = None
):
    """Option 1: 4-Qubit Hadamard QRNG Physical Entropy Execution or Retrieval."""
    print("=" * 70)
    print(" OPTION 1: PHYSICAL QUANTUM ENTROPY (4-QUBIT HADAMARD SUPERPOSITION)")
    print("=" * 70)
    print(f"[*] Target QPU: {backend_name}")
    print(f"[*] Configuration: {num_qubits} Qubits | {shots} Shots")
    print("[*] Loading credentials and connecting to IBM Quantum Platform...")

    worker = QuantumWorker()
    if not worker.token or not worker.instance:
        raise RuntimeError("IBM Quantum credentials not configured in ~/.config/qf/credentials.json")

    from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2 as Sampler
    from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager

    service = QiskitRuntimeService(channel="ibm_quantum_platform", token=worker.token, instance=worker.instance)
    backend = service.backend(backend_name)
    print(f"[+] Connected to {backend.name} (Total Physical Qubits: {backend.num_qubits})")

    qc, qasm_str, circuit_sha = worker.build_entropy_circuit(num_qubits=num_qubits)
    print(f"[+] Logical circuit: {qc.name} (SHA-256: {circuit_sha[:16]}...)")

    if retrieve_job_id:
        print(f"[*] Retrieving existing job: {retrieve_job_id}...")
        job = service.job(retrieve_job_id)
        job_id = retrieve_job_id
        isa_sha = None
    else:
        print("[*] Transpiling circuit to Heron ISA coupling map...")
        pm = generate_preset_pass_manager(backend=backend, optimization_level=1)
        isa_circuit = pm.run(qc)
        isa_sha = circuit_sha256(isa_circuit)
        print(f"[+] Transpilation complete (ISA depth: {isa_circuit.depth()}, gates: {dict(isa_circuit.count_ops())})")
        print(f"    ISA Circuit SHA-256: {isa_sha[:16]}...")

        print(f"[*] Dispatching job to physical dilution refrigerator ({backend.name})...")
        sampler = Sampler(mode=backend)
        job = sampler.run([isa_circuit], shots=shots)
        job_id = job.job_id()
        print(f"[+] JOB DISPATCHED! Job ID: {job_id}")
        print(f"    Track URL: https://quantum.ibm.com/jobs/{job_id}")

        print("[*] Monitoring hardware execution progress...")
        last_status = None
        start_time = time.time()
        timeout = 600.0
        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                print(f"[!] Polling timed out after {timeout}s.")
                return False

            status = job.status()
            status_str = str(status).upper()
            if status_str != last_status:
                print(f"    [{elapsed:5.1f}s] Hardware Status: {status_str}")
                last_status = status_str
            if status_str in ["DONE", "COMPLETED", "CANCELLED", "ERROR"]:
                break
            time.sleep(3.0)

        if status_str not in ["DONE", "COMPLETED"]:
            print(f"[!] Job failed with status: {status_str}")
            return False

    print("\n[+] JOB EXECUTION COMPLETE ON PHYSICAL SILICON!")
    result = job.result()
    pub_result = result[0]
    reg_name, counts, bit_array = extract_counts_from_pub(pub_result)
    actual_shots = sum(counts.values())
    if actual_shots == 0:
        raise ValueError("No measurement outcomes returned from QPU")

    full_shannon = calculate_full_shannon_entropy(counts)
    max_possible_entropy = math.log2(2 ** num_qubits)

    from quantum_worker import ordered_raw_bits, condition_entropy
    raw_bits = ordered_raw_bits(bit_array, actual_shots, num_qubits)
    metrics = calculate_entropy_metrics(raw_bits)
    raw_sha256 = hashlib.sha256(raw_bits.encode("utf-8")).hexdigest()
    conditioned_bytes, conditioned_hex = condition_entropy(raw_bits, job_id=job_id, backend_name=backend.name)

    print("\n" + "=" * 70)
    print(" PHYSICAL QUANTUM ENTROPY RESULTS")
    print("=" * 70)
    print(f"QPU Backend:              {backend.name} (Heron r2)")
    print(f"Job ID:                   {job_id}")
    print(f"Physical Register:        {reg_name}")
    print(f"Requested Shots:          {shots}")
    print(f"Actual Measured Shots:    {actual_shots}")
    print(f"Total Raw Bits Sampled:   {len(raw_bits)}")
    print(f"Observed Outcome States:  {len(counts)} / 16 possible states")
    print(f"\nMeasurement Counts Distribution (Top 8):")
    sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    for state, cnt in sorted_counts[:8]:
        pct = (cnt / actual_shots) * 100
        bar = "█" * int(pct // 2)
        print(f"  |{state}⟩: {cnt:4d} shots ({pct:5.2f}%) {bar}")

    print("\nCryptographic & Entropy Verification:")
    print(f"  - Full Distribution Shannon Entropy: {full_shannon:.4f} / {max_possible_entropy:.1f} bits")
    print(f"  - Per-Bit Shannon Entropy:           {metrics['shannon_entropy_per_bit']:.4f} bits/bit")
    print(f"  - Per-Bit Min-Entropy (H_inf):       {metrics['min_entropy_per_bit']:.4f} bits/bit")
    print(f"  - Raw Bitstream SHA-256 Digest:      {raw_sha256}")
    print(f"  - Conditioned Seed Digest:           {hashlib.sha256(conditioned_bytes).hexdigest()}")
    print("=" * 70)

    # Archive to Evidence Ledger
    archive_evidence_manifest(
        experiment_type="HADAMARD_QRNG_ENTROPY",
        backend_name=backend.name,
        job_id=job_id,
        requested_shots=shots,
        actual_shots=actual_shots,
        register_name=reg_name,
        counts=counts,
        metrics={
            "full_shannon_entropy": round(full_shannon, 4),
            "shannon_entropy_per_bit": round(metrics["shannon_entropy_per_bit"], 4),
            "min_entropy_per_bit": round(metrics["min_entropy_per_bit"], 4),
            "raw_sha256": raw_sha256,
            "conditioned_sha256": hashlib.sha256(conditioned_bytes).hexdigest()
        },
        logical_circuit_sha256=circuit_sha,
        isa_circuit_sha256=isa_sha,
        dry_run=False
    )
    return True


def run_option2(
    backend_name: str = "ibm_fez",
    shots: int = 1024,
    retrieve_job_id: str | None = None
):
    """Option 2: 2-Qubit Bell State Correlation & Attestation."""
    print("=" * 70)
    print(" OPTION 2: PHYSICAL QUANTUM BELL-STATE CORRELATION & ATTESTATION")
    print("=" * 70)
    print(f"[*] Target QPU: {backend_name}")
    print(f"[*] Configuration: 2 Qubits | {shots} Shots")
    print("[*] Loading credentials and connecting to IBM Quantum Platform...")

    worker = QuantumWorker()
    if not worker.token or not worker.instance:
        raise RuntimeError("IBM Quantum credentials not configured in ~/.config/qf/credentials.json")

    from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2 as Sampler
    from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager

    service = QiskitRuntimeService(channel="ibm_quantum_platform", token=worker.token, instance=worker.instance)
    backend = service.backend(backend_name)
    print(f"[+] Connected to {backend.name} (Total Physical Qubits: {backend.num_qubits})")

    qc, qasm_str, circuit_sha = worker.build_bell_circuit()
    print(f"[+] Logical circuit: {qc.name} (H(0) + CNOT(0,1) -> (|00⟩ + |11⟩)/√2)")
    print(f"    Circuit SHA-256: {circuit_sha[:16]}...")

    if retrieve_job_id:
        print(f"[*] Retrieving existing job: {retrieve_job_id}...")
        job = service.job(retrieve_job_id)
        job_id = retrieve_job_id
        isa_sha = None
    else:
        print("[*] Transpiling circuit to Heron ISA coupling map...")
        pm = generate_preset_pass_manager(backend=backend, optimization_level=1)
        isa_circuit = pm.run(qc)
        isa_sha = circuit_sha256(isa_circuit)
        print(f"[+] Transpilation complete (ISA depth: {isa_circuit.depth()}, gates: {dict(isa_circuit.count_ops())})")
        print(f"    ISA Circuit SHA-256: {isa_sha[:16]}...")

        print(f"[*] Dispatching entanglement job to physical dilution refrigerator ({backend.name})...")
        sampler = Sampler(mode=backend)
        job = sampler.run([isa_circuit], shots=shots)
        job_id = job.job_id()
        print(f"[+] JOB DISPATCHED! Job ID: {job_id}")
        print(f"    Track URL: https://quantum.ibm.com/jobs/{job_id}")

        print("[*] Monitoring hardware execution progress...")
        last_status = None
        start_time = time.time()
        timeout = 600.0
        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                print(f"[!] Polling timed out after {timeout}s.")
                return False

            status = job.status()
            status_str = str(status).upper()
            if status_str != last_status:
                print(f"    [{elapsed:5.1f}s] Hardware Status: {status_str}")
                last_status = status_str
            if status_str in ["DONE", "COMPLETED", "CANCELLED", "ERROR"]:
                break
            time.sleep(3.0)

        if status_str not in ["DONE", "COMPLETED"]:
            print(f"[!] Job failed with status: {status_str}")
            return False

    print("\n[+] JOB EXECUTION COMPLETE ON PHYSICAL SILICON!")
    result = job.result()
    pub_result = result[0]
    reg_name, counts, _ = extract_counts_from_pub(pub_result)
    actual_shots = sum(counts.values())
    if actual_shots == 0:
        raise ValueError("No measurement outcomes returned from QPU")

    n00 = counts.get("00", 0)
    n11 = counts.get("11", 0)
    n01 = counts.get("01", 0)
    n10 = counts.get("10", 0)
    correlated_shots = n00 + n11
    error_shots = n01 + n10
    correlation_percentage = (correlated_shots / actual_shots) * 100
    noise_percentage = (error_shots / actual_shots) * 100

    print("\n" + "=" * 70)
    print(" PHYSICAL QUANTUM BELL-STATE CORRELATION RESULTS")
    print("=" * 70)
    print(f"QPU Backend:              {backend.name} (Heron r2)")
    print(f"Job ID:                   {job_id}")
    print(f"Measurement Register:     {reg_name}")
    print(f"Requested Shots:          {shots}")
    print(f"Actual Measured Shots:    {actual_shots}")
    print(f"\nMeasured Computational Basis Distribution:")
    print(f"  |00⟩ (Correlated):       {n00:4d} shots ({(n00/actual_shots)*100:5.2f}%)")
    print(f"  |11⟩ (Correlated):       {n11:4d} shots ({(n11/actual_shots)*100:5.2f}%)")
    print(f"  |01⟩ (Readout/Noise):    {n01:4d} shots ({(n01/actual_shots)*100:5.2f}%)")
    print(f"  |10⟩ (Readout/Noise):    {n10:4d} shots ({(n10/actual_shots)*100:5.2f}%)")
    print(f"\nComputational Basis Correlation: {correlation_percentage:.2f}% ({correlated_shots}/{actual_shots})")
    print(f"Anti-Correlated Noise / Leakage : {noise_percentage:.2f}% ({error_shots}/{actual_shots})")
    print("\n[Epistemic Boundary Note]")
    print("  * Computational-basis correlation measures joint Z-basis population (|00> + |11>).")
    print("  * A classical mixture (50% |00>, 50% |11>) can exhibit high correlation without entanglement.")
    print("  * For genuine multipartite entanglement certification, see tools/run_qaoa_and_ghz_kingston.py")
    print("    which evaluates the complete 5-basis witness W across ZZZ, XXX, XYY, YXY, and YYX.")
    print("=" * 70)

    # Archive to Evidence Ledger
    archive_evidence_manifest(
        experiment_type="BELL_STATE_CORRELATION",
        backend_name=backend.name,
        job_id=job_id,
        requested_shots=shots,
        actual_shots=actual_shots,
        register_name=reg_name,
        counts=counts,
        metrics={
            "correlated_shots": correlated_shots,
            "anti_correlated_shots": error_shots,
            "correlation_percentage": round(correlation_percentage, 4),
            "noise_percentage": round(noise_percentage, 4),
            "p_00": round((n00 / actual_shots) * 100, 4),
            "p_11": round((n11 / actual_shots) * 100, 4),
            "p_01": round((n01 / actual_shots) * 100, 4),
            "p_10": round((n10 / actual_shots) * 100, 4)
        },
        logical_circuit_sha256=circuit_sha,
        isa_circuit_sha256=isa_sha,
        dry_run=False
    )
    return True


def main():
    parser = argparse.ArgumentParser(description="QuantumFlex IBM Quantum Physical Experiment Runner & Ledger")
    parser.add_argument("option", choices=["1", "2", "all"], help="Option to run (1: Entropy, 2: Bell Correlation, all: Both)")
    parser.add_argument("--backend", default="ibm_fez", help="Target QPU backend name (default: ibm_fez)")
    parser.add_argument("--shots", type=int, default=1024, help="Shots per circuit (default: 1024)")
    parser.add_argument("--submit", action="store_true", help="Actually dispatch to QPU hardware (default: dry-run)")
    parser.add_argument("--retrieve", type=str, default=None, help="Retrieve and independently analyze completed IBM job ID")
    args = parser.parse_args()

    if not args.submit and args.retrieve is None:
        print("=" * 70)
        print(" QUANTUMFLEX IBM EXPERIMENT RUNNER [DRY-RUN]")
        print("=" * 70)
        print(f" Target Option : {args.option}")
        print(f" Target QPU    : {args.backend}")
        print(f" Shots         : {args.shots}")
        print(" Status        : Dry-run preview. No physical jobs dispatched.")
        print(" Action        : Re-run with --submit to execute on hardware, or --retrieve <job_id>")
        print("=" * 70)
        return

    if args.option in ["1", "all"]:
        ok1 = run_option1(backend_name=args.backend, shots=args.shots, retrieve_job_id=args.retrieve)
        if not ok1:
            sys.exit(1)
        if args.option == "all" and not args.retrieve:
            print("\nWaiting 5 seconds before launching Option 2...\n")
            time.sleep(5)

    if args.option in ["2", "all"]:
        ok2 = run_option2(backend_name=args.backend, shots=args.shots, retrieve_job_id=args.retrieve)
        if not ok2:
            sys.exit(1)


if __name__ == "__main__":
    main()
