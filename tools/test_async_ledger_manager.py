#!/usr/bin/env python3
"""
Comprehensive Concurrency, Stress, and Fault-Tolerance Test Suite for AsyncLedgerManager & EvidenceLedger

Test Coverage:
  1. Multi-backend asynchronous concurrent dispatch and sequential hash-chaining.
  2. Multi-process cross-process concurrency stress testing with fcntl.flock & os.fsync.
  3. Job ID deduplication and idempotency safeguards (fail-safe replay prevention).
  4. Failure-injection and cryptographic tampering detection (bit-flip resilience).
  5. Epistemic verification: Fail-closed daemon posture (LOCKED) & zero secret entropy credit (0.0).
"""

from __future__ import annotations
import asyncio
import concurrent.futures
import json
import multiprocessing as mp
from pathlib import Path
import random
import sys
import tempfile
import time
from typing import List

sys.path.insert(0, "/home/quant/Documents/qf")
sys.path.insert(0, "/home/quant/mycelium/tools")

from async_ledger_manager import AsyncLedgerManager, build_sample_circuits
from ledger import EvidenceLedger, GENESIS_HASH, compute_hash


def _worker_process_write_batch(ledger_path_str: str, worker_id: int, num_entries: int) -> int:
    """Helper worker run in an independent OS process to stress cross-process locking."""
    ledger = EvidenceLedger(filepath=ledger_path_str)
    written = 0
    for i in range(num_entries):
        job_id = f"proc_{worker_id}_job_{i}_{time.time_ns()}_{random.randint(100, 999)}"
        ledger.record_attestation(
            experiment_name=f"Multiprocess_Stress_w{worker_id}",
            requested_by=f"WorkerProcess_{worker_id}",
            authorization={"decision": "ALLOW", "worker_id": worker_id},
            target_type="LOCAL_VALIDATION",
            backend_name=random.choice(["ibm_kingston", "ibm_fez", "ibm_marrakesh"]),
            job_id=job_id,
            shots=256,
            counts={"00": 128, "11": 128},
            circuit_info={"num_qubits": 2},
            result_sha256="0" * 64,
            verification={"stress_test": True},
            metadata={"worker_id": worker_id, "seq": i},
        )
        written += 1
        time.sleep(random.uniform(0.002, 0.01))  # random delay to maximize lock contention
    return written


async def test_concurrent_ledger_integrity():
    print("\n" + "=" * 78)
    print(" TEST 1: Asynchronous Multi-Backend Ledger Concurrency & Hash Chaining")
    print("=" * 78)

    with tempfile.TemporaryDirectory() as tmpdir:
        test_ledger_path = Path(tmpdir) / "test_evidence_ledger.jsonl"
        
        manager = AsyncLedgerManager(
            ledger_path=test_ledger_path,
            dry_run=True,
            backend_pool=["ibm_kingston", "ibm_fez", "ibm_marrakesh"]
        )

        circuits = build_sample_circuits()
        print(f"[*] Dispatching {len(circuits)} circuits concurrently across 3 mock backends...")
        
        start = time.time()
        committed_entries = await manager.dispatch_batch(
            circuits=circuits,
            experiment_name="Async_Concurrency_Test",
            shots=256
        )
        elapsed = time.time() - start
        print(f"[+] All {len(committed_entries)} concurrent tasks resolved in {elapsed:.2f}s.")

        assert len(committed_entries) == len(circuits), f"Expected {len(circuits)} entries, got {len(committed_entries)}"

        # Verify entry indexing and prev_hash chaining as committed on disk
        print("\n[*] Verifying On-Disk Sequential Hash Chaining:")
        expected_prev = GENESIS_HASH
        disk_entries = []
        with open(test_ledger_path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                entry = json.loads(line.strip())
                disk_entries.append(entry)
                print(f"    Line {line_no} | Entry #{entry['entry_index']}: prev_hash={entry['prev_hash'][:16]}... -> entry_hash={entry['entry_hash'][:16]}... [{entry['backend_name']}]")
                assert entry["entry_index"] == line_no, f"Entry index mismatch at line {line_no}: expected {line_no}, got {entry['entry_index']}"
                assert entry["prev_hash"] == expected_prev, f"Hash chain break at line {line_no}!"
                assert entry["metadata"]["engine_state"] == "LOCKED"
                assert entry["metadata"]["entropy_credit"] == 0.0
                expected_prev = entry["entry_hash"]

        assert len(disk_entries) == len(circuits)

        # Run EvidenceLedger cryptographic audit on disk file
        print("\n[*] Running Complete Cryptographic Hash-Chain Verification on disk:")
        l = EvidenceLedger(filepath=test_ledger_path)
        is_valid, msgs = l.verify_integrity()
        for m in msgs:
            print(f"    -> {m}")
        
        assert is_valid is True, "Cryptographic ledger hash chain verification failed!"
        print("[+] TEST 1 PASSED: Async concurrency and hash chain integrity verified.")


def test_multiprocess_stress_and_cross_process_locking():
    print("\n" + "=" * 78)
    print(" TEST 2: Multi-Process Stress & Cross-Process Locking (fcntl.flock & fsync)")
    print("=" * 78)

    with tempfile.TemporaryDirectory() as tmpdir:
        test_ledger_path = Path(tmpdir) / "stress_evidence_ledger.jsonl"
        num_workers = 5
        entries_per_worker = 6
        expected_total = num_workers * entries_per_worker

        print(f"[*] Spawning {num_workers} concurrent OS processes (each writing {entries_per_worker} entries)...")
        print(f"[*] Target ledger: {test_ledger_path}")

        ctx = mp.get_context("spawn")
        start = time.time()
        with concurrent.futures.ProcessPoolExecutor(max_workers=num_workers, mp_context=ctx) as executor:
            futures = [
                executor.submit(
                    _worker_process_write_batch,
                    str(test_ledger_path),
                    worker_id,
                    entries_per_worker
                )
                for worker_id in range(num_workers)
            ]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        elapsed = time.time() - start
        total_written = sum(results)
        print(f"[+] All {num_workers} processes finished in {elapsed:.2f}s. Total writes reported: {total_written}")
        assert total_written == expected_total, f"Expected {expected_total} writes, got {total_written}"

        # Verify on-disk file integrity
        ledger = EvidenceLedger(filepath=test_ledger_path)
        is_valid, msgs = ledger.verify_integrity()
        print(f"[*] Cryptographic Verification: is_valid={is_valid}")
        for m in msgs:
            print(f"    -> {m}")

        assert is_valid is True, f"Multi-process hash chain corrupted! Details: {msgs}"

        # Verify entry count and strict 1..N contiguous indexing
        lines = [line.strip() for line in open(test_ledger_path, "r", encoding="utf-8") if line.strip()]
        assert len(lines) == expected_total, f"Expected {expected_total} lines in ledger, found {len(lines)}"

        for expected_idx, line in enumerate(lines, start=1):
            e = json.loads(line)
            assert e["entry_index"] == expected_idx, f"Index gap/fork detected at line {expected_idx}: {e['entry_index']}"

        print(f"[+] TEST 2 PASSED: Successfully serialized {expected_total} writes across {num_workers} processes with zero forks or corruption.")


def test_idempotency_and_duplicate_handling():
    print("\n" + "=" * 78)
    print(" TEST 3: Idempotency & Duplicate Job Protection")
    print("=" * 78)

    with tempfile.TemporaryDirectory() as tmpdir:
        test_ledger_path = Path(tmpdir) / "idempotency_ledger.jsonl"
        ledger = EvidenceLedger(filepath=test_ledger_path)

        # 1. Commit first attestation
        fixed_job_id = "real_qpu_job_db8nsvob_test"
        entry1 = ledger.record_attestation(
            experiment_name="Idempotency_Run_1",
            requested_by="TestRunner",
            authorization={"decision": "ALLOW"},
            target_type="REAL_QPU",
            backend_name="ibm_kingston",
            job_id=fixed_job_id,
            shots=256,
            counts={"00": 128, "11": 128},
            circuit_info={"num_qubits": 2},
            result_sha256="a" * 64,
            verification={"test": True},
        )
        assert entry1["entry_index"] == 1
        assert ledger.has_job_id(fixed_job_id) is True

        # 2. Attempt duplicate commit with same job_id on REAL_QPU -> Must raise ValueError
        try:
            ledger.record_attestation(
                experiment_name="Idempotency_Run_Duplicate",
                requested_by="AttackerOrDoubleSubmit",
                authorization={"decision": "ALLOW"},
                target_type="REAL_QPU",
                backend_name="ibm_kingston",
                job_id=fixed_job_id,
                shots=256,
                counts={"00": 128, "11": 128},
                circuit_info={"num_qubits": 2},
                result_sha256="b" * 64,
                verification={"test": True},
            )
            assert False, "Failed to reject duplicate REAL_QPU job submission!"
        except ValueError as ex:
            print(f"[✓] Correctly rejected duplicate REAL_QPU job submission: {ex}")

        # 3. Verify ledger still has exactly 1 valid entry
        is_valid, msgs = ledger.verify_integrity()
        assert is_valid is True
        lines = [line.strip() for line in open(test_ledger_path, "r", encoding="utf-8") if line.strip()]
        assert len(lines) == 1

        print("[+] TEST 3 PASSED: Idempotency protections successfully prevented duplicate job commit.")


def test_tamper_detection_failure_injection():
    print("\n" + "=" * 78)
    print(" TEST 4: Cryptographic Tamper Detection & Failure Injection")
    print("=" * 78)

    with tempfile.TemporaryDirectory() as tmpdir:
        test_ledger_path = Path(tmpdir) / "tamper_ledger.jsonl"
        ledger = EvidenceLedger(filepath=test_ledger_path)

        # Commit 3 legitimate entries
        for i in range(1, 4):
            ledger.record_attestation(
                experiment_name=f"Tamper_Run_{i}",
                requested_by="TamperTest",
                authorization={"decision": "ALLOW"},
                target_type="LOCAL_VALIDATION",
                backend_name="ibm_fez",
                job_id=f"legit_job_{i}",
                shots=100,
                counts={"00": 50, "11": 50},
                circuit_info={"num_qubits": 2},
                result_sha256="c" * 64,
                verification={"test": True},
            )

        is_valid, msgs = ledger.verify_integrity()
        assert is_valid is True
        print(f"[✓] Clean ledger validated: {msgs[0]}")

        # Inject failure: tamper with counts in line 2
        lines = open(test_ledger_path, "r", encoding="utf-8").readlines()
        entry2 = json.loads(lines[1])
        entry2["counts"]["00"] = 999  # Malicious count tampering!
        lines[1] = json.dumps(entry2) + "\n"

        with open(test_ledger_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        # Re-verify -> MUST detect tampering at entry 2
        is_valid_after_tamper, errors = ledger.verify_integrity()
        print(f"[✓] Verification after payload tampering: is_valid={is_valid_after_tamper}")
        print(f"    Detected errors: {errors}")
        assert is_valid_after_tamper is False
        assert any("Tampering detected" in err and "Entry #2" in err for err in errors)

        print("[+] TEST 4 PASSED: Cryptographic ledger caught simulated payload tampering with 100% precision.")


def main():
    print("=" * 78)
    print(" QUANTUMFLEX ASYNC MULTI-BACKEND LEDGER AUDIT & VERIFICATION SUITE")
    print("=" * 78)

    # Run tests
    asyncio.run(test_concurrent_ledger_integrity())
    test_multiprocess_stress_and_cross_process_locking()
    test_idempotency_and_duplicate_handling()
    test_tamper_detection_failure_injection()

    print("\n" + "=" * 78)
    print(" [✓] ALL CONCURRENCY, MULTI-PROCESS, AND TAMPER-DETECTION TESTS PASSED")
    print("=" * 78)


if __name__ == "__main__":
    main()
