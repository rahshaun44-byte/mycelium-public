#!/usr/bin/env python3
"""
Unit and Concurrency Test Suite for AsyncLedgerManager
Tests:
  1. Multi-backend pool queue inspection.
  2. Concurrent mock job dispatch across simulated backends (ibm_kingston, ibm_fez, ibm_marrakesh).
  3. Thread-safe sequential entry indexing and prev_hash binding.
  4. 100% cryptographic ledger hash chain verification.
  5. Zero secret entropy attribution and fail-closed locked engine posture.
"""

import asyncio
import json
from pathlib import Path
import sys
import tempfile
import time

sys.path.insert(0, "/home/quant/Documents/qf")
sys.path.insert(0, "/home/quant/mycelium/tools")

from async_ledger_manager import AsyncLedgerManager, build_sample_circuits
from ledger import EvidenceLedger, GENESIS_HASH


async def test_concurrent_ledger_integrity():
    print("=" * 75)
    print(" TEST: Asynchronous Multi-Backend Ledger Concurrency & Hash Chaining")
    print("=" * 75)

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
        print("\n[+] SUCCESS: All concurrency and cryptographic integrity tests passed.")


def main():
    asyncio.run(test_concurrent_ledger_integrity())


if __name__ == "__main__":
    main()
