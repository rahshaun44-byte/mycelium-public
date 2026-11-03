#!/usr/bin/env python3
"""
QuantumFlex Asynchronous Multi-Backend Cryptographic Ledger Manager
Tracks concurrent IBM Quantum jobs across multiple backends (e.g. ibm_kingston, ibm_fez, ibm_marrakesh),
decouples job submission from verification, and commits tamper-evident hash-chained entries to the evidence ledger.

Key Principles:
  1. Cryptographic Hash Chaining: Every ledger block binds to prev_hash from the preceding entry.
  2. Concurrency Safety: asyncio.Lock serializes ledger writes, preventing chain forks.
  3. Safe-by-Default Execution: Defaults to simulated/dry-run mode to protect physical QPU minutes.
  4. Per-Backend Transpilation: Generates ISA circuits customized to each backend's coupling map.
  5. Epistemic Posture: Enforces fail-closed engine state (LOCKED) and zero secret entropy credit.
"""

from __future__ import annotations
import argparse
import asyncio
from datetime import datetime, timezone
import functools
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Add repo paths for local imports
sys.path.insert(0, "/home/quant/Documents/qf")
sys.path.insert(0, "/home/quant/mycelium/tools")

from ledger import EvidenceLedger, canonical_json, compute_hash, DEFAULT_LEDGER_PATH, GENESIS_HASH
from quantum_worker import QuantumWorker

from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector
from qiskit.qasm2 import dumps as qasm_dumps
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2 as Sampler
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager


DEFAULT_BACKEND_POOL = ["ibm_kingston", "ibm_fez", "ibm_marrakesh"]
DEFAULT_POLICY_PATH = Path(DEFAULT_LEDGER_PATH).parent / "policies" / "quantum_admission.rego"
DEFAULT_CALLER = "Quantum_Flex_Async_Manager"
OPA_TIMEOUT_SEC = 10.0


def not_evaluated_authorization(reason: str) -> Dict[str, Any]:
    """Honest authorization record for paths where no policy engine was consulted."""
    return {
        "decision": "NOT_EVALUATED",
        "verification_state": "NO_POLICY_EVALUATION",
        "reason": reason,
        "evaluator": None,
    }


class MockIBMJob:
    """Simulates an asynchronous IBM Quantum job lifecycle for safe local testing."""
    def __init__(self, job_id: str, backend_name: str, circuit: QuantumCircuit, shots: int = 256, delay_sec: float = 2.0):
        self._job_id = job_id
        self._backend_name = backend_name
        self._circuit = circuit
        self._shots = shots
        self._delay_sec = delay_sec
        self._start_time = time.time()
        self._status = "QUEUED"

    def job_id(self) -> str:
        return self._job_id

    def status(self):
        elapsed = time.time() - self._start_time
        if elapsed < self._delay_sec * 0.4:
            self._status = "QUEUED"
        elif elapsed < self._delay_sec:
            self._status = "RUNNING"
        else:
            self._status = "DONE"
        
        class _StatusObj:
            def __init__(self, name):
                self.name = name
            def __str__(self):
                return self.name
        return _StatusObj(self._status)

    def result(self):
        # Calculate simulated counts using local statevector
        uc = self._circuit.remove_final_measurements(inplace=False)
        sv = Statevector.from_instruction(uc)
        probs = sv.probabilities_dict()
        
        sim_counts = {}
        for bitstr, p in probs.items():
            cnt = int(round(p * self._shots))
            if cnt > 0:
                sim_counts[bitstr] = cnt
        diff = self._shots - sum(sim_counts.values())
        if diff != 0 and sim_counts:
            top_k = max(sim_counts.keys(), key=lambda k: sim_counts[k])
            sim_counts[top_k] += diff
        
        # Emulate PubResult structure
        class _PubData:
            def __init__(self, counts):
                self._counts = counts
            def get_counts(self):
                return self._counts

        class _PubResult:
            def __init__(self, counts):
                self.data = {"meas": _PubData(counts)}

        return [_PubResult(sim_counts)]


class AsyncLedgerManager:
    """Manages asynchronous QPU job dispatch, monitoring, and cryptographic ledger commit."""

    def __init__(
        self,
        ledger_path: Path | str = DEFAULT_LEDGER_PATH,
        dry_run: bool = True,
        backend_pool: Optional[List[str]] = None,
        policy_path: Path | str = DEFAULT_POLICY_PATH,
        opa_bin: str = "opa",
        caller: str = DEFAULT_CALLER,
    ):
        self.ledger = EvidenceLedger(filepath=ledger_path)
        self.dry_run = dry_run
        self.backend_pool = backend_pool or list(DEFAULT_BACKEND_POOL)
        self.policy_path = Path(policy_path)
        self.opa_bin = opa_bin
        self.caller = caller
        self._commit_lock = asyncio.Lock()
        self._service: Optional[QiskitRuntimeService] = None

    async def evaluate_admission(self, backend_name: str, circuit: QuantumCircuit, shots: int) -> Dict[str, Any]:
        """
        Evaluate quantum_admission.rego via the local OPA binary.
        Fail-closed: any error (missing binary, missing policy, timeout, bad output) yields DENY.
        """
        policy_input = {
            "caller": self.caller,
            "shots": shots,
            "qubits": circuit.num_qubits,
            "depth": circuit.depth(),
            "backend": backend_name,
        }
        base = {
            "policy_file": str(self.policy_path),
            "evaluator": f"opa eval ({self.opa_bin})",
            "input": policy_input,
        }

        def _deny(reason: str) -> Dict[str, Any]:
            return {**base, "decision": "DENY", "verification_state": "OPA_EVALUATION_FAILED", "reasons": [reason]}

        if not self.policy_path.is_file():
            return _deny(f"Policy file not found: {self.policy_path}")
        try:
            proc = await asyncio.create_subprocess_exec(
                self.opa_bin, "eval", "--format", "json", "--stdin-input",
                "-d", str(self.policy_path), "data.quantum.admission",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(json.dumps(policy_input).encode("utf-8")), timeout=OPA_TIMEOUT_SEC
            )
        except FileNotFoundError:
            return _deny(f"OPA binary not found: {self.opa_bin}")
        except asyncio.TimeoutError:
            proc.kill()
            return _deny(f"OPA evaluation timed out after {OPA_TIMEOUT_SEC}s")

        if proc.returncode != 0:
            return _deny(f"OPA exited {proc.returncode}: {stderr.decode(errors='replace').strip()[:200]}")
        try:
            value = json.loads(stdout)["result"][0]["expressions"][0]["value"]
        except (ValueError, KeyError, IndexError, TypeError) as e:
            return _deny(f"Unparseable OPA output: {e}")

        allowed = value.get("allow") is True
        return {
            **base,
            "decision": "ALLOW" if allowed else "DENY",
            "verification_state": "OPA_POLICY_EVALUATED",
            "reasons": sorted(value.get("reasons", [])),
        }

    def _get_runtime_service(self) -> QiskitRuntimeService:
        """Lazily initialize IBM Quantum runtime service using QuantumWorker credentials."""
        if self._service is None:
            worker = QuantumWorker()
            if not worker.token or not worker.instance:
                raise RuntimeError("IBM Quantum credentials not configured in ~/.config/qf/credentials.json")
            self._service = QiskitRuntimeService(
                channel="ibm_quantum_platform",
                token=worker.token,
                instance=worker.instance,
            )
        return self._service

    async def get_backend_status(self, backend_name: str) -> Dict[str, Any]:
        """Query backend queue and status asynchronously."""
        if self.dry_run:
            return {
                "backend_name": backend_name,
                "operational": True,
                "pending_jobs": random.randint(0, 5),
                "simulated": True,
            }
        
        loop = asyncio.get_running_loop()
        service = self._get_runtime_service()
        backend = await loop.run_in_executor(None, service.backend, backend_name)
        status = await loop.run_in_executor(None, backend.status)
        return {
            "backend_name": backend_name,
            "operational": status.operational,
            "pending_jobs": status.pending_jobs,
            "status_msg": status.status_msg,
            "simulated": False,
        }

    async def select_best_backend(self, preferred_backends: Optional[List[str]] = None) -> str:
        """Select available backend with lowest pending job queue."""
        pool = preferred_backends or self.backend_pool
        print(f"[*] Evaluating backend pool for optimal queue: {pool}")
        
        statuses = await asyncio.gather(*(self.get_backend_status(b) for b in pool), return_exceptions=True)
        valid_backends = []
        for s in statuses:
            if isinstance(s, dict) and s.get("operational", False):
                valid_backends.append(s)
                print(f"    -> {s['backend_name']:<16} | Pending Jobs: {s['pending_jobs']}")
            elif isinstance(s, Exception):
                print(f"    -> Backend error: {s}")

        if not valid_backends:
            # Fail-closed: never dispatch to a backend whose operational status was not confirmed.
            raise RuntimeError(f"No operational backend confirmed in pool {pool}; refusing to dispatch.")

        # Sort by pending jobs ascending
        valid_backends.sort(key=lambda x: x["pending_jobs"])
        selected = valid_backends[0]["backend_name"]
        print(f"[+] Selected optimal backend: {selected} (Pending queue: {valid_backends[0]['pending_jobs']})")
        return selected

    async def monitor_and_commit_job(
        self,
        job_id: str,
        backend_name: Optional[str],
        circuit_info: Dict[str, Any],
        experiment_name: str = "Async_Quantum_Workload",
        shots: int = 256,
        poll_interval_sec: float = 5.0,
        mock_job: Optional[MockIBMJob] = None,
        authorization: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Poll an individual quantum job until completion and commit result to evidence ledger.
        Uses asyncio.Lock to ensure thread-safe, non-forking hash chaining.

        For physical jobs, the backend recorded in the ledger is the one reported by IBM for the
        job itself. If `backend_name` is given and disagrees, the commit is refused (fail-closed).
        """
        if authorization is None:
            authorization = not_evaluated_authorization("No admission decision supplied to commit path")
        print(f"[*] Tracking Job {job_id} on [{backend_name or 'backend from job'}]...")
        start_time = time.time()

        while True:
            if mock_job:
                raw_status = mock_job.status()
                status_name = raw_status.name if hasattr(raw_status, "name") else str(raw_status)
            else:
                loop = asyncio.get_running_loop()
                service = self._get_runtime_service()
                job = await loop.run_in_executor(None, service.job, job_id)
                raw_status = await loop.run_in_executor(None, job.status)
                status_name = raw_status.name if hasattr(raw_status, "name") else str(raw_status)

            elapsed = int(time.time() - start_time)
            print(f"    [{job_id[:12]}] Status: {status_name:<10} ({elapsed}s elapsed)")

            if status_name in ("DONE", "CANCELLED", "ERROR", "FAILED"):
                break
            await asyncio.sleep(poll_interval_sec)

        if status_name != "DONE":
            raise RuntimeError(f"Job {job_id} terminated with failure status: {status_name}")

        # Extract counts and resolve the backend that actually executed the job
        if mock_job:
            result = mock_job.result()
            counts = list(result[0].data.values())[0].get_counts()
            actual_backend = backend_name or mock_job._backend_name
        else:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, job.result)
            counts = list(result[0].data.values())[0].get_counts()
            job_backend = await loop.run_in_executor(None, job.backend)
            actual_backend = getattr(job_backend, "name", None)
            if not actual_backend:
                raise RuntimeError(f"Job {job_id}: IBM did not report an executing backend; refusing to commit.")
            if backend_name and actual_backend != backend_name:
                raise RuntimeError(
                    f"Job {job_id}: backend mismatch (expected {backend_name}, IBM reports {actual_backend}); "
                    "refusing to commit mislabeled evidence."
                )

        total_shots = sum(counts.values())
        result_sha256 = compute_hash(counts)

        # Thread-safe ledger commit under lock
        async with self._commit_lock:
            with self.ledger.file_lock():
                if self.ledger.has_job_id(job_id):
                    print(f"[!] Idempotency warning: Job {job_id} already committed in ledger. Skipping duplicate write.")
                    with open(self.ledger.filepath, "r", encoding="utf-8") as f:
                        for line in f:
                            stripped = line.strip()
                            if not stripped:
                                continue
                            try:
                                e = json.loads(stripped)
                                if e.get("job_id") == job_id:
                                    return e
                            except Exception:
                                continue
                    return self.ledger.get_last_entry()

                last_entry = self.ledger.get_last_entry()
                prev_hash = last_entry["entry_hash"] if last_entry else GENESIS_HASH
                entry_index = (last_entry["entry_index"] + 1) if last_entry else 1

                payload = {
                    "entry_index": entry_index,
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "experiment_name": experiment_name,
                    "requested_by": self.caller,
                    "authorization": authorization,
                    "target_type": "LOCAL_VALIDATION" if (self.dry_run or mock_job) else "REAL_QPU",
                    "provider": "Local Qiskit Reference Engine" if (self.dry_run or mock_job) else "IBM Quantum Platform",
                    "backend_name": actual_backend,
                    "job_id": job_id,
                    "shots": total_shots,
                    "counts": counts,
                    "circuit_info": circuit_info,
                    "result_sha256": result_sha256,
                    "verification": {
                        "hardware_confirmed": not (self.dry_run or mock_job),
                        "simulator": bool(self.dry_run or mock_job),
                        "async_monitored": True
                    },
                    "metadata": {
                        "engine_state": "LOCKED",
                        "entropy_credit": 0.0,
                        "epistemic_standard": "External empirical physics research only. Zero secret entropy.",
                        "elapsed_polling_seconds": elapsed
                    },
                    "prev_hash": prev_hash,
                }

                entry_hash = compute_hash(payload)
                full_entry = {**payload, "entry_hash": entry_hash}

                with open(self.ledger.filepath, "a", encoding="utf-8") as f:
                    f.write(json.dumps(full_entry) + "\n")
                    f.flush()
                    os.fsync(f.fileno())

                print(f"[✓] Committed Ledger Entry #{entry_index} for Job {job_id[:16]}...")
                print(f"    -> Block Hash : {entry_hash}")
                print(f"    -> Prev Hash  : {prev_hash[:16]}...")
                return full_entry

    async def dispatch_circuit(
        self,
        circuit: QuantumCircuit,
        experiment_name: str = "Async_Quantum_Workload",
        shots: int = 256,
        preferred_backend: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Dispatch a single circuit to best backend and monitor until committed."""
        backend_name = preferred_backend or await self.select_best_backend()
        circuit_info = {
            "name": circuit.name or "unnamed_circuit",
            "num_qubits": circuit.num_qubits,
            "depth": circuit.depth(),
            "gates": dict(circuit.count_ops()),
            "circuit_sha256": compute_hash({"qasm": qasm_dumps(circuit)})
        }

        if self.dry_run:
            job_id = f"mock_{backend_name}_{int(time.time())}_{random.randint(1000, 9999)}"
            mock_job = MockIBMJob(job_id, backend_name, circuit, shots=shots, delay_sec=random.uniform(1.0, 2.5))
            return await self.monitor_and_commit_job(
                job_id=job_id,
                backend_name=backend_name,
                circuit_info=circuit_info,
                experiment_name=experiment_name,
                shots=shots,
                poll_interval_sec=0.5,
                mock_job=mock_job,
                authorization=not_evaluated_authorization("Dry-run simulation; no QPU admission required"),
            )
        else:
            # Fail-closed admission gate: no physical submission without an explicit OPA ALLOW.
            authorization = await self.evaluate_admission(backend_name, circuit, shots)
            if authorization["decision"] != "ALLOW":
                raise PermissionError(
                    f"Admission DENIED for {circuit.name or 'unnamed_circuit'} on {backend_name}: "
                    f"{authorization.get('reasons')}"
                )

            loop = asyncio.get_running_loop()
            service = self._get_runtime_service()
            backend = await loop.run_in_executor(None, service.backend, backend_name)
            
            # Transpile specifically for this backend's physical topology
            pm = generate_preset_pass_manager(backend=backend, optimization_level=1)
            isa_circuit = await loop.run_in_executor(None, pm.run, circuit)
            
            sampler = Sampler(mode=backend)
            # SamplerV2.run(pubs, *, shots=...) -- shots is keyword-only, so bind it explicitly.
            job = await loop.run_in_executor(None, functools.partial(sampler.run, [isa_circuit], shots=shots))
            job_id = job.job_id()
            print(f"[+] Physical QPU Job Submitted: {job_id} on {backend_name}")
            
            return await self.monitor_and_commit_job(
                job_id=job_id,
                backend_name=backend_name,
                circuit_info=circuit_info,
                experiment_name=experiment_name,
                shots=shots,
                poll_interval_sec=10.0,
                authorization=authorization,
            )

    async def retrieve_and_commit(
        self,
        job_id: str,
        expected_backend: Optional[str] = None,
        shots: int = 256,
        poll_interval_sec: float = 2.0,
    ) -> Dict[str, Any]:
        """
        Retrieve an existing physical IBM job and commit it. The backend is taken from IBM's job
        record; `expected_backend`, if given, must match. Circuit details are not reconstructed,
        so they are recorded as unknown rather than guessed.
        """
        if self.dry_run:
            raise RuntimeError("retrieve_and_commit requires a non-dry-run manager (physical job lookup).")
        circuit_info = {"name": "retrieved_job", "retrieved": True, "num_qubits": None, "circuit_sha256": None}
        return await self.monitor_and_commit_job(
            job_id=job_id,
            backend_name=expected_backend,
            circuit_info=circuit_info,
            experiment_name="Async_Retrieved_Hardware_Run",
            shots=shots,
            poll_interval_sec=poll_interval_sec,
            authorization=not_evaluated_authorization("Retrieved pre-existing job; admission occurred outside this manager"),
        )

    async def dispatch_batch(
        self,
        circuits: List[QuantumCircuit],
        experiment_name: str = "Async_Batch_Workload",
        shots: int = 256,
        backends: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Dispatch multiple circuits concurrently across backend pool."""
        target_backends = backends or self.backend_pool
        print("=" * 78)
        print(f" ASYNCHRONOUS MULTI-BACKEND WORKER POOL DISPATCH")
        print(f" Circuits to Dispatch : {len(circuits)}")
        print(f" Target Backend Pool  : {target_backends}")
        print(f" Mode                 : {'[MOCK / DRY-RUN (ZERO QPU COST)]' if self.dry_run else '[LIVE QPU CRYOGENIC]'}")
        print("=" * 78)

        tasks = []
        for i, qc in enumerate(circuits):
            assigned_backend = target_backends[i % len(target_backends)]
            tasks.append(
                self.dispatch_circuit(
                    circuit=qc,
                    experiment_name=f"{experiment_name}_c{i}_{qc.name}",
                    shots=shots,
                    preferred_backend=assigned_backend,
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)
        committed = []
        for i, res in enumerate(results):
            if isinstance(res, dict):
                committed.append(res)
            else:
                print(f"[!] Error in task {i}: {res}")

        print(f"\n[+] Batch complete: {len(committed)}/{len(circuits)} circuits committed to ledger.")
        return committed


def build_sample_circuits() -> List[QuantumCircuit]:
    """Create sample research circuits for multi-backend demonstration."""
    # 1. 3-qubit GHZ State
    ghz = QuantumCircuit(3, 3, name="ghz_3q")
    ghz.h(0)
    ghz.cx(0, 1)
    ghz.cx(1, 2)
    ghz.measure(range(3), range(3))

    # 2. 2-qubit Bell Pair
    bell = QuantumCircuit(2, 2, name="bell_2q")
    bell.h(0)
    bell.cx(0, 1)
    bell.measure(range(2), range(2))

    # 3. 3-qubit Superposition & Parity
    sup = QuantumCircuit(3, 3, name="superposition_3q")
    sup.h(range(3))
    sup.measure(range(3), range(3))

    return [ghz, bell, sup]


async def main_async():
    parser = argparse.ArgumentParser(description="QuantumFlex Async Multi-Backend Ledger Manager")
    parser.add_argument("--live", action="store_true", help="Submit actual jobs to IBM Quantum hardware (requires confirmation)")
    parser.add_argument("--retrieve", type=str, default=None, help="Retrieve and commit an existing physical job ID")
    parser.add_argument("--backend", type=str, default=None, help="Expected backend for --retrieve; commit is refused if IBM reports a different one (default: accept IBM's reported backend)")
    parser.add_argument("--ledger-path", type=str, default=str(DEFAULT_LEDGER_PATH), help="Path to evidence_ledger.jsonl")
    parser.add_argument("--verify-ledger", action="store_true", help="Verify cryptographic hash chain of the ledger file")
    parser.add_argument("--shots", type=int, default=256, help="Shots per circuit (default: 256)")
    args = parser.parse_args()

    ledger_path = Path(args.ledger_path)

    # If --verify-ledger is requested
    if args.verify_ledger:
        print(f"[*] Verifying ledger integrity at: {ledger_path}")
        l = EvidenceLedger(filepath=ledger_path)
        valid, msgs = l.verify_integrity()
        print(f"    Valid: {valid}")
        for m in msgs:
            print(f"    -> {m}")
        sys.exit(0 if valid else 1)

    manager = AsyncLedgerManager(
        ledger_path=ledger_path,
        dry_run=not args.live and (args.retrieve is None),
        backend_pool=DEFAULT_BACKEND_POOL,
    )

    if args.retrieve:
        print(f"[*] Asynchronously retrieving existing job: {args.retrieve} (expected backend: {args.backend or 'any'})")
        entry = await manager.retrieve_and_commit(
            job_id=args.retrieve,
            expected_backend=args.backend,
            shots=args.shots,
        )
        print(f"[+] Successfully committed retrieved job {args.retrieve} to ledger entry #{entry['entry_index']}.")
    else:
        # Batch dispatch demonstration across 3 backends
        circuits = build_sample_circuits()
        await manager.dispatch_batch(
            circuits=circuits,
            experiment_name="Async_Multi_Backend_Pool_Demo",
            shots=args.shots,
        )

        # Verify ledger integrity post-execution
        print("\n[*] Post-Execution Cryptographic Hash Chain Audit:")
        valid, msgs = manager.ledger.verify_integrity()
        print(f"    Ledger Chain Status: {'[100% VALID]' if valid else '[CORRUPTED]'}")
        for m in msgs:
            print(f"    -> {m}")


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
