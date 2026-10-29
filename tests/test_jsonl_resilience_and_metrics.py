# tests/test_jsonl_resilience_and_metrics.py
"""
P1 #3 (Metrics Validation) & P1 #4 (Resilience Testing) Verification Suite.
Covers JSONL enqueue/fsync latency SLOs, power-loss torn-write recovery,
and simulated EIO / ENOSPC kernel fault handling on qfx-yoga.
"""

import errno
import json
import os
import pytest

from src.jsonl_resilience import DurableJsonlQueue, run_jsonl_fsync_benchmark


def test_p1_metrics_validation_jsonl_fsync_latency_and_burst_capacity(tmp_path):
    """
    P1 #3 Metrics Validation:
    Benchmarks 80 durable fsync batches x 50 frames (4,000 frames) on qfx-yoga.
    Verifies p99 fsync latency < 50 ms and zero dropped or corrupted lines.
    """
    ledger_path = tmp_path / "qfx_yoga_benchmark.jsonl"
    report = run_jsonl_fsync_benchmark(target_path=ledger_path, batches=80, batch_size=50)

    print(
        f"\n[P1-METRICS] Batches={report.total_batches} Records={report.total_records} | "
        f"p50={report.p50_ms}ms p95={report.p95_ms}ms p99={report.p99_ms}ms max={report.max_ms}ms | "
        f"Throughput={report.throughput_records_per_sec} rec/s"
    )

    assert report.total_records == 4000
    assert report.p50_ms < 25.0, f"p50 fsync latency too high: {report.p50_ms}ms"
    assert report.p99_ms < 50.0, f"p99 fsync latency exceeded 50ms budget: {report.p99_ms}ms"
    assert report.throughput_records_per_sec > 500.0

    # Confirm all 4,000 lines are valid and intact on disk
    queue = DurableJsonlQueue(ledger_path)
    valid_count, truncated_bytes = queue.recover_torn_tail()
    assert valid_count == 4000
    assert truncated_bytes == 0


def test_power_loss_torn_write_recovery_preserves_committed_prefix(tmp_path):
    """
    P1 #4 Resilience: Simulates power loss mid-write (unterminated JSON fragment at EOF).
    Verifies recover_torn_tail() truncates the exact corrupted byte tail and preserves prior lines.
    """
    ledger_path = tmp_path / "power_loss.jsonl"
    queue = DurableJsonlQueue(ledger_path)

    # Commit 3 valid durable frames
    written = queue.enqueue_batch(
        [
            {"node_id": "qfx-yoga", "cpu_load_1m": 0.41, "seq": 1},
            {"node_id": "qfx-yoga", "cpu_load_1m": 0.43, "seq": 2},
            {"node_id": "qfx-yoga", "cpu_load_1m": 0.47, "seq": 3},
        ]
    )
    assert written == 3
    clean_size = ledger_path.stat().st_size

    # Inject a 37-byte torn tail (simulating kernel panic / power loss before '\n')
    torn_fragment = b'{"node_id":"qfx-yoga","cpu_load_1m":0.50,"s'
    with open(ledger_path, "ab") as fh:
        fh.write(torn_fragment)
        fh.flush()

    assert ledger_path.stat().st_size == clean_size + len(torn_fragment)

    # Execute recovery
    valid_records, truncated_bytes = queue.recover_torn_tail()
    assert valid_records == 3
    assert truncated_bytes == len(torn_fragment)
    assert ledger_path.stat().st_size == clean_size

    # Verify next durable write appends cleanly as line 4
    queue.enqueue_batch([{"node_id": "qfx-yoga", "cpu_load_1m": 0.50, "seq": 4}])
    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 4
    assert json.loads(lines[3])["node_id"] == "qfx-yoga"


def test_simulated_enospc_mid_batch_rolls_back_partial_write(tmp_path):
    """
    P1 #4 Resilience: Simulates ENOSPC (errno 28) after writing the first 25 bytes of a new batch.
    Verifies atomic rollback via os.ftruncate so the previously committed ledger remains 100% clean.
    """
    ledger_path = tmp_path / "enospc_rollback.jsonl"
    baseline_queue = DurableJsonlQueue(ledger_path)
    baseline_queue.enqueue_batch([{"node_id": "qfx-yoga", "cpu_load_1m": 0.39, "seq": 1}])
    baseline_size = ledger_path.stat().st_size

    def faulty_enospc_write(fd: int, data: bytes) -> int:
        # Write 20 partial bytes to disk, then raise ENOSPC on the remainder
        os.write(fd, data[:20])
        raise OSError(errno.ENOSPC, "No space left on device (simulated ENOSPC)")

    fault_queue = DurableJsonlQueue(ledger_path, write_fn=faulty_enospc_write)
    with pytest.raises(OSError) as exc_info:
        fault_queue.enqueue_batch(
            [
                {"node_id": "qfx-yoga", "cpu_load_1m": 0.51, "seq": 2},
                {"node_id": "qfx-yoga", "cpu_load_1m": 0.53, "seq": 3},
            ]
        )

    assert exc_info.value.errno == errno.ENOSPC
    # File size MUST be rolled back to exact pre-batch size (no 20-byte torn tail left behind)
    assert ledger_path.stat().st_size == baseline_size
    valid_records, truncated = baseline_queue.recover_torn_tail()
    assert valid_records == 1
    assert truncated == 0


def test_simulated_eio_on_fsync_rolls_back_and_propagates_errno_5(tmp_path):
    """
    P1 #4 Resilience: Simulates physical I/O error (EIO, errno 5) during os.fsync().
    Verifies batch rollback and exact errno propagation.
    """
    ledger_path = tmp_path / "eio_fsync.jsonl"
    baseline_queue = DurableJsonlQueue(ledger_path)
    baseline_queue.enqueue_batch([{"node_id": "qfx-yoga", "cpu_load_1m": 0.40, "seq": 1}])
    baseline_size = ledger_path.stat().st_size

    def faulty_eio_fsync(_fd: int) -> None:
        raise OSError(errno.EIO, "Input/output error during NVMe flush (simulated EIO)")

    fault_queue = DurableJsonlQueue(ledger_path, fsync_fn=faulty_eio_fsync)
    with pytest.raises(OSError) as exc_info:
        fault_queue.enqueue_batch([{"node_id": "qfx-yoga", "cpu_load_1m": 0.60, "seq": 2}])

    assert exc_info.value.errno == errno.EIO
    assert ledger_path.stat().st_size == baseline_size


def test_optout_frame_in_batch_aborts_before_touching_disk(tmp_path):
    """
    Defense-in-Depth: Any batch containing an _optout or _nomap frame must raise PermissionError
    without creating or modifying the JSONL file.
    """
    ledger_path = tmp_path / "privacy_abort.jsonl"
    queue = DurableJsonlQueue(ledger_path)

    with pytest.raises(PermissionError, match="opt-out"):
        queue.enqueue_batch(
            [
                {"node_id": "qfx-yoga", "cpu_load_1m": 0.42},
                {"node_id": "qfx-yoga_nomap", "cpu_load_1m": 0.65},
            ]
        )

    assert not ledger_path.exists()
