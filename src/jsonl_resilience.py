# src/jsonl_resilience.py
"""
QuantumFlex P1 #3 & #4: Durable JSONL Enqueue/Fsync Engine, Torn-Write Recovery,
and Latency Benchmark Harness.
"""

from __future__ import annotations

import errno
import json
import math
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from src.privacy_filter import PrivacyFilter


@dataclass(frozen=True)
class FsyncBenchmarkResult:
    total_batches: int
    total_records: int
    batch_size: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float
    mean_ms: float
    throughput_records_per_sec: float


class DurableJsonlQueue:
    """
    Append-only JSONL persistence queue with:
    1. Edge PrivacyFilter enforcement (fails closed on _optout / _nomap)
    2. Power-loss torn-write tail recovery (os.ftruncate to last valid newline boundary)
    3. Explicit os.fsync() durability per batch commit
    """

    def __init__(
        self,
        file_path: Path | str,
        fsync_fn: Callable[[int], None] = os.fsync,
        write_fn: Callable[[int, bytes], int] = os.write,
    ) -> None:
        self.file_path = Path(file_path)
        self._fsync_fn = fsync_fn
        self._write_fn = write_fn

    def recover_torn_tail(self) -> Tuple[int, int]:
        """
        Scans the JSONL file from offset 0. Any trailing line lacking a terminating '\\n',
        failing JSON deserialization, or containing an opt-out tag is truncated at the
        exact byte offset of the last valid committed record.
        Returns (valid_records_count, truncated_bytes_count).
        """
        if not self.file_path.exists():
            return (0, 0)

        total_size = self.file_path.stat().st_size
        valid_offset = 0
        valid_records = 0

        with open(self.file_path, "rb") as fh:
            while True:
                line_bytes = fh.readline()
                if not line_bytes:
                    break
                if not line_bytes.endswith(b"\n"):
                    # Torn write (power loss before newline commit)
                    break
                try:
                    decoded = line_bytes.decode("utf-8")
                    obj = json.loads(decoded)
                    if not isinstance(obj, dict) or PrivacyFilter.contains_optout(obj):
                        break
                except Exception:
                    # Corrupted JSON or invalid UTF-8 tail
                    break

                valid_offset += len(line_bytes)
                valid_records += 1

        truncated_bytes = max(0, total_size - valid_offset)
        if truncated_bytes > 0:
            fd = os.open(str(self.file_path), os.O_RDWR)
            try:
                os.ftruncate(fd, valid_offset)
                self._fsync_fn(fd)
            finally:
                os.close(fd)

        return (valid_records, truncated_bytes)

    def enqueue_batch(self, frames: Iterable[Dict[str, Any]]) -> int:
        """
        Sanitizes, serializes, writes, and fsyncs a batch of telemetry frames atomically.
        If a partial write (short write), EIO, or ENOSPC occurs mid-batch, rolls back the
        file length to the pre-batch offset so zero torn lines remain on disk.
        """
        sanitized_lines: List[bytes] = []
        for frame in frames:
            if not isinstance(frame, dict):
                raise PermissionError("Fail-closed: non-dict telemetry frame rejected")
            if PrivacyFilter.contains_optout(frame):
                raise PermissionError("Fail-closed: privacy opt-out marker rejected at JSONL sink")
            clean = PrivacyFilter.sanitize_telemetry_frame(frame)
            if clean is None:
                raise PermissionError("Fail-closed: frame rejected by PrivacyFilter")
            line_str = json.dumps(clean, sort_keys=True, separators=(",", ":")) + "\n"
            sanitized_lines.append(line_str.encode("utf-8"))

        if not sanitized_lines:
            return 0

        payload = b"".join(sanitized_lines)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        fd = os.open(str(self.file_path), os.O_CREAT | os.O_RDWR | os.O_APPEND, 0o600)
        pre_write_size = os.fstat(fd).st_size
        try:
            total_written = 0
            while total_written < len(payload):
                n = self._write_fn(fd, payload[total_written:])
                if n <= 0:
                    raise OSError(errno.EIO, "Short write returned 0 bytes during JSONL enqueue")
                total_written += n

            self._fsync_fn(fd)
            return len(sanitized_lines)
        except OSError:
            # Roll back any partial/torn bytes written during the failed batch
            try:
                os.ftruncate(fd, pre_write_size)
            except OSError:
                pass
            raise
        finally:
            os.close(fd)


def run_jsonl_fsync_benchmark(
    target_path: Path,
    batches: int = 100,
    batch_size: int = 25,
) -> FsyncBenchmarkResult:
    """
    Executes a live disk enqueue + os.fsync() benchmark on qfx-yoga and computes
    p50, p95, p99, max latency (ms) and sustained burst throughput (records/sec).
    """
    if target_path.exists():
        target_path.unlink()

    queue = DurableJsonlQueue(target_path)
    latencies_ms: List[float] = []

    sample_batch = [
        {
            "node_id": "qfx-yoga",
            "seq": i,
            "cpu_load_1m": 0.25 + (i % 10) * 0.05,
            "ram_used_pct": 40.0 + (i % 20),
            "temp_c": 45.0 + (i % 5),
            "timestamp": 1761518000 + i,
        }
        for i in range(batch_size)
    ]

    t_start_wall = time.perf_counter()
    for _ in range(batches):
        t0 = time.perf_counter()
        queue.enqueue_batch(sample_batch)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        latencies_ms.append(elapsed_ms)
    total_wall_sec = max(1e-9, time.perf_counter() - t_start_wall)

    latencies_ms.sort()

    def _pct(p: float) -> float:
        idx = min(len(latencies_ms) - 1, max(0, math.ceil((p / 100.0) * len(latencies_ms)) - 1))
        return round(latencies_ms[idx], 4)

    total_records = batches * batch_size
    return FsyncBenchmarkResult(
        total_batches=batches,
        total_records=total_records,
        batch_size=batch_size,
        p50_ms=_pct(50.0),
        p95_ms=_pct(95.0),
        p99_ms=_pct(99.0),
        max_ms=round(latencies_ms[-1], 4),
        mean_ms=round(sum(latencies_ms) / len(latencies_ms), 4),
        throughput_records_per_sec=round(total_records / total_wall_sec, 2),
    )
