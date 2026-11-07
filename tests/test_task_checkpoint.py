"""Checkpoint serialization, privacy, and recovery use repository-local test files."""

from __future__ import annotations

import os
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from mcp_layer import task_checkpoint as checkpoints


@pytest.fixture
def checkpoint_dir(monkeypatch):
    path = Path(__file__).resolve().parents[1] / "data" / f".checkpoint-test-{os.getpid()}-{uuid.uuid4().hex}"
    monkeypatch.setattr(checkpoints, "CHECKPOINT_DIR", path)
    yield path
    shutil.rmtree(path, ignore_errors=True)


def _record(updated_at):
    return {
        "id": 71,
        "status": "COMPLETED",
        "created_at": updated_at - timedelta(seconds=2),
        "updated_at": updated_at,
        "task_payload": {"target_node": "athena", "question": "private prompt"},
        "result": "private answer",
    }


def test_checkpoint_persists_only_hashes_with_private_permissions(monkeypatch, checkpoint_dir):
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(checkpoints, "get_task_record", lambda task_id: _record(now))

    saved = checkpoints.checkpoint_task(71)
    restored = checkpoints.read_checkpoint(71)
    data = (checkpoint_dir / "71.json").read_text(encoding="utf-8")

    assert saved == restored
    assert "private prompt" not in data
    assert "private answer" not in data
    assert "task_payload_sha256" in data
    assert checkpoint_dir.stat().st_mode & 0o777 == 0o700
    assert (checkpoint_dir / "71.json").stat().st_mode & 0o777 == 0o600


def test_recovery_rebuilds_missing_or_stale_local_checkpoint(monkeypatch, checkpoint_dir):
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(checkpoints, "get_task_record", lambda task_id: _record(now))

    restored, source = checkpoints.recover_task(71)
    assert source == "postgresql-restored"
    assert restored["status"] == "COMPLETED"

    stale = checkpoints._make_snapshot(_record(now - timedelta(seconds=10)))
    checkpoints.write_checkpoint(stale, force=True)
    reconciled, source = checkpoints.recover_task(71)
    assert source == "postgresql-reconciled"
    assert reconciled["updated_at"] == now.isoformat()
    assert checkpoints.read_checkpoint(71) == reconciled
