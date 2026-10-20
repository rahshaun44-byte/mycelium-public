#!/usr/bin/env python3
"""Execute and analyze physical IBM Quantum experiments with real-time feedback."""

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path

# Add qf directory to sys.path
sys.path.insert(0, "/home/quant/quantumflex/qf")
from quantum_worker import QuantumWorker, get_worker_credentials, calculate_entropy_metrics


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


def run_option1(backend_name: str = "ibm_fez", shots: int = 1024, num_qubits: int = 4):
    """Option 1: 4-Qubit Hadamard QRNG Physical Entropy Execution."""
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

    # Build Circuit
    qc, qasm_str, circuit_sha256 = worker.build_entropy_circuit(num_qubits=num_qubits)
    print(f"[+] Circuit constructed: {qc.name} (4 Hadamard gates, 4 computational basis measurements)")
    print(f"    Circuit SHA-256: {circuit_sha256[:16]}...")

    # Transpile to hardware ISA
    print("[*] Transpiling circuit to Heron ISA coupling map...")
    pm = generate_preset_pass_manager(backend=backend, optimization_level=1)
    isa_circuit = pm.run(qc)
    print(f"[+] Hardware transpilation complete (ISA depth: {isa_circuit.depth()}, gates: {dict(isa_circuit.count_ops())})")

    # Dispatch to hardware
    print(f"[*] Dispatching job to physical dilution refrigerator ({backend.name})...")
    sampler = Sampler(mode=backend)
    job = sampler.run([isa_circuit], shots=shots)
    job_id = job.job_id()
    print(f"[+] JOB DISPATCHED! Job ID: {job_id}")
    print(f"    Track URL: https://quantum.ibm.com/jobs/{job_id}")

    # Monitor status
    print("[*] Monitoring hardware execution progress...")
    last_status = None
    while True:
        status = job.status()
        status_str = str(status).upper()
        if status_str != last_status:
            elapsed = time.time() - start_time
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
    data_bin = pub_result.data
    first_reg = list(data_bin.keys())[0]
    bit_array = getattr(data_bin, first_reg)
    counts = bit_array.get_counts()

    # Calculate metrics
    full_shannon = calculate_full_shannon_entropy(counts)
    max_possible_entropy = math.log2(2 ** num_qubits)  # 4.0 bits for 16 outcomes

    # Raw bitstream diagnostics
    from quantum_worker import ordered_raw_bits, condition_entropy
    raw_bits = ordered_raw_bits(bit_array, shots, num_qubits)
    metrics = calculate_entropy_metrics(raw_bits)
    raw_sha256 = hashlib.sha256(raw_bits.encode("utf-8")).hexdigest()
    conditioned_bytes, conditioned_hex = condition_entropy(raw_bits, job_id=job_id, backend_name=backend.name)

    print("\n" + "=" * 70)
    print(" PHYSICAL QUANTUM ENTROPY RESULTS")
    print("=" * 70)
    print(f"QPU Backend:              {backend.name} (Heron r2)")
    print(f"Job ID:                   {job_id}")
    print(f"Physical Qubits Used:     {num_qubits}")
    print(f"Total Shots:              {shots}")
    print(f"Total Raw Bits Sampled:   {len(raw_bits)}")
    print(f"Observed Outcome States:  {len(counts)} / 16 possible states")
    print(f"\nMeasurement Counts Distribution (Top 8):")
    sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    for state, cnt in sorted_counts[:8]:
        pct = (cnt / shots) * 100
        bar = "█" * int(pct // 2)
        print(f"  |{state}⟩: {cnt:4d} shots ({pct:5.2f}%) {bar}")

    print("\nCryptographic & Entropy Verification:")
    print(f"  - Full Distribution Shannon Entropy: {full_shannon:.4f} / {max_possible_entropy:.1f} bits")
    print(f"  - Per-Bit Shannon Entropy:           {metrics['shannon_entropy_per_bit']:.4f} bits/bit")
    print(f"  - Per-Bit Min-Entropy (H_inf):       {metrics['min_entropy_per_bit']:.4f} bits/bit")
    print(f"  - Raw Bitstream SHA-256 Digest:      {raw_sha256}")
    print(f"  - Conditioned Seed Digest:           {hashlib.sha256(conditioned_bytes).hexdigest()}")
    print("=" * 70)
    print("[+] Evidence logged cleanly without persisting plaintext secrets.")
    return True


def run_option2(backend_name: str = "ibm_fez", shots: int = 1024):
    """Option 2: 2-Qubit Bell State Entanglement Attestation."""
    print("=" * 70)
    print(" OPTION 2: PHYSICAL QUANTUM ENTANGLEMENT (|Φ+⟩ BELL STATE ATTESTATION)")
    print("=" * 70)
    print(f"[*] Target QPU: {backend_name}")
    print(f"[*] Configuration: 2 Qubits | {shots} Shots")
    print("[*] Loading credentials and connecting to IBM Quantum Platform...")

    worker = QuantumWorker()
    from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2 as Sampler
    from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager

    service = QiskitRuntimeService(channel="ibm_quantum_platform", token=worker.token, instance=worker.instance)
    backend = service.backend(backend_name)
    print(f"[+] Connected to {backend.name} (Total Physical Qubits: {backend.num_qubits})")

    # Build Bell Circuit: (|00> + |11>) / sqrt(2)
    qc, qasm_str, circuit_sha256 = worker.build_bell_circuit()
    print(f"[+] Circuit constructed: {qc.name} (H(0) + CNOT(0,1) -> (|00⟩ + |11⟩)/√2)")
    print(f"    Circuit SHA-256: {circuit_sha256[:16]}...")

    # Transpile to hardware ISA
    print("[*] Transpiling circuit to Heron ISA coupling map...")
    pm = generate_preset_pass_manager(backend=backend, optimization_level=1)
    isa_circuit = pm.run(qc)
    print(f"[+] Hardware transpilation complete (ISA depth: {isa_circuit.depth()}, gates: {dict(isa_circuit.count_ops())})")

    # Dispatch to hardware
    print(f"[*] Dispatching entanglement job to physical dilution refrigerator ({backend.name})...")
    sampler = Sampler(mode=backend)
    job = sampler.run([isa_circuit], shots=shots)
    job_id = job.job_id()
    print(f"[+] JOB DISPATCHED! Job ID: {job_id}")
    print(f"    Track URL: https://quantum.ibm.com/jobs/{job_id}")

    # Monitor status
    print("[*] Monitoring hardware execution progress...")
    last_status = None
    start_time = time.time()
    while True:
        status = job.status()
        status_str = str(status).upper()
        if status_str != last_status:
            elapsed = time.time() - start_time
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
    data_bin = pub_result.data
    first_reg = list(data_bin.keys())[0]
    bit_array = getattr(data_bin, first_reg)
    counts = bit_array.get_counts()

    # Calculate Bell entanglement fidelity
    n00 = counts.get("00", 0)
    n11 = counts.get("11", 0)
    n01 = counts.get("01", 0)
    n10 = counts.get("10", 0)
    entangled_shots = n00 + n11
    error_shots = n01 + n10
    fidelity_proxy = (entangled_shots / shots) * 100

    print("\n" + "=" * 70)
    print(" PHYSICAL QUANTUM ENTANGLEMENT RESULTS")
    print("=" * 70)
    print(f"QPU Backend:              {backend.name} (Heron r2)")
    print(f"Job ID:                   {job_id}")
    print(f"Total Shots:              {shots}")
    print(f"\nMeasured Correlation:")
    print(f"  |00⟩ (Correlated):       {n00:4d} shots ({(n00/shots)*100:5.2f}%)")
    print(f"  |11⟩ (Correlated):       {n11:4d} shots ({(n11/shots)*100:5.2f}%)")
    print(f"  |01⟩ (Readout/Noise):    {n01:4d} shots ({(n01/shots)*100:5.2f}%)")
    print(f"  |10⟩ (Readout/Noise):    {n10:4d} shots ({(n10/shots)*100:5.2f}%)")
    print(f"\nEntanglement Correlation: {fidelity_proxy:.2f}% (Total Entangled: {entangled_shots}/{shots})")
    print(f"Hardware Noise / Leak:    {(error_shots/shots)*100:.2f}%")
    print("=" * 70)
    return True


def main():
    parser = argparse.ArgumentParser(description="Run IBM Quantum experiments.")
    parser.add_argument("option", choices=["1", "2", "all"], help="Option to run (1: Entropy, 2: Entanglement, all: Both)")
    parser.add_argument("--backend", default="ibm_fez", help="Target QPU backend name (default: ibm_fez)")
    parser.add_argument("--shots", type=int, default=1024, help="Shots per circuit (default: 1024)")
    parser.add_argument("--submit", action="store_true", help="Actually dispatch to QPU hardware (default: dry-run)")
    args = parser.parse_args()

    if not args.submit:
        print(f"[DRY-RUN] Would run option {args.option} on {args.backend} with {args.shots} shots.")
        print("[DRY-RUN] No job submitted. Re-run with --submit to dispatch to hardware.")
        return

    if args.option in ["1", "all"]:
        ok1 = run_option1(backend_name=args.backend, shots=args.shots)
        if not ok1:
            sys.exit(1)
        if args.option == "all":
            print("\nWaiting 5 seconds before launching Option 2...\n")
            time.sleep(5)

    if args.option in ["2", "all"]:
        ok2 = run_option2(backend_name=args.backend, shots=args.shots)
        if not ok2:
            sys.exit(1)


if __name__ == "__main__":
    main()
