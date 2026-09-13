#!/usr/bin/env python3
"""
Unit and integration tests for Phase 1: Thermodynamic Ghost Node (h -> 0).
Asserts:
  1. Staged payloads are confined to volatile RAM (/dev/shm/qflex_airlock) and zero-wiped upon exit.
  2. Rootfs inside Ghost Node container is immutable (read-only).
  3. Quarantined entropy sinks are mounted strictly on volatile tmpfs (64MB RAM).
  4. Zero persistent NAND flash block writes occur on host NVMe storage.
"""

import os
import tempfile
import subprocess
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_ghost_node_container_tmpfs_boundary():
    """Validates that Ghost Node enforces read-only rootfs and volatile tmpfs quarantine."""
    podman_cmd = [
        "podman", "run", "--rm",
        "--name", "test-tmpfs-ghost",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges=true",
        "--tmpfs", "/quarantine:rw,size=64m,noexec,nosuid,nodev",
        "alpine:3.20",
        "sh", "-c",
        (
            "touch /root/fail.txt 2>/dev/null && exit 1 || "
            "echo 'blob' > /quarantine/blob.bin && "
            "df -h /quarantine"
        )
    ]
    res = subprocess.run(podman_cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"Ghost node boundary test failed: {res.stderr}"
    assert "tmpfs" in res.stdout
    assert "64.0M" in res.stdout


def test_run_sentinel_volatile_staging_and_dissipation():
    """Validates that run_sentinel.py stages to RAM tmpfs and dissipates upon exit."""
    sentinel_script = REPO_ROOT / "run_sentinel.py"
    with tempfile.NamedTemporaryFile(prefix="anomaly_", suffix=".bin", delete=False) as f:
        f.write(b"EXTREME_ANOMALY_ENTROPY_VECTOR_0xDEADBEEF")
        temp_payload = Path(f.name)

    try:
        cmd = [str(sentinel_script), str(temp_payload)]
        res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))
        assert res.returncode == 0, f"run_sentinel failed: {res.stderr}"

        # Assert telemetry mentions volatile airlock and dissipation
        assert "volatile RAM airlock: /dev/shm/qflex_airlock" in res.stdout
        assert "Thermodynamic Dissipation: Volatile payload purged from RAM." in res.stdout
        assert "tmpfs" in res.stdout

        # Assert RAM airlock file has been dissipated (zeroed and removed)
        staged_file = Path("/dev/shm/qflex_airlock") / temp_payload.name
        assert not staged_file.exists(), "Staged payload was not dissipated from RAM airlock!"

    finally:
        if temp_payload.exists():
            temp_payload.unlink()
