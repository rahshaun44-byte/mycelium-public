"""Lock in swarm worker recovery so claimed tasks cannot stay RUNNING forever.

poll_task used to commit status=RUNNING and then only re-select PENDING.
A crash, SIGKILL, complete_task DB blip, or JSONB-as-str payload crash left
the row invisible to every subsequent worker.
"""
from __future__ import annotations

import json
import os

os.environ.setdefault("GHOSTNODE_DB_USER", "test")
os.environ.setdefault("GHOSTNODE_DB_PASSWORD", "test")

import mcp_layer.swarm_worker as swarm_worker


class _FakeCursor:
    def __init__(self, row=None):
        self.row = row
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchone(self):
        return self.row

    def close(self):
        return None


class _FakeConn:
    def __init__(self, cursor):
        self._cursor = cursor
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self, cursor_factory=None):
        return self._cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_decode_task_payload_accepts_psycopg2_jsonb_string():
    payload = swarm_worker.decode_task_payload(
        '{"target_node": "amara", "action": "ping", "parameters": {}}'
    )
    assert payload["target_node"] == "amara"
    assert payload["action"] == "ping"


def test_execute_task_does_not_crash_on_jsonb_string():
    status, outcome = swarm_worker.execute_task({
        "id": 7,
        "task_payload": json.dumps({
            "target_node": "amara",
            "action": "evaluate",
            "parameters": {"k": "v"},
        }),
    })
    assert status == "COMPLETED"
    assert "evaluate" in outcome


def test_execute_task_malformed_payload_is_failed_not_raised():
    status, outcome = swarm_worker.execute_task({
        "id": 8,
        "task_payload": ["not", "an", "object"],
    })
    assert status == "FAILED"
    assert "task_payload" in outcome


def test_poll_task_sql_reclaims_stale_running(monkeypatch):
    cur = _FakeCursor(row=None)
    conn = _FakeConn(cur)
    monkeypatch.setattr(swarm_worker, "get_db", lambda: conn)

    assert swarm_worker.poll_task() is None
    assert conn.rolled_back is True

    select_sql = cur.executed[0][0]
    assert "status = 'PENDING'" in select_sql
    assert "status = 'RUNNING'" in select_sql
    assert "INTERVAL '1 second'" in select_sql
    assert cur.executed[0][1] == (swarm_worker.TASK_LEASE_SECONDS,)


def test_process_claimed_task_releases_on_complete_failure(monkeypatch):
    released = []

    monkeypatch.setattr(
        swarm_worker,
        "execute_task",
        lambda task: ("COMPLETED", "ok"),
    )

    def _boom(task_id, status, outcome):
        raise RuntimeError("telemetry db unavailable")

    monkeypatch.setattr(swarm_worker, "complete_task", _boom)
    monkeypatch.setattr(
        swarm_worker,
        "release_claimed_task",
        lambda task_id: released.append(task_id),
    )

    try:
        swarm_worker.process_claimed_task({"id": 42, "task_payload": {}})
        raise AssertionError("complete_task failure should propagate")
    except RuntimeError as exc:
        assert "telemetry db unavailable" in str(exc)

    assert released == [42]


def test_release_claimed_task_only_touches_running_rows(monkeypatch):
    cur = _FakeCursor()
    conn = _FakeConn(cur)
    monkeypatch.setattr(swarm_worker, "get_db", lambda: conn)

    swarm_worker.release_claimed_task(99)

    sql, params = cur.executed[0]
    assert "status = 'PENDING'" in sql
    assert "status = 'RUNNING'" in sql
    assert params[1] == 99
    assert "password" not in params[0].lower()
    assert conn.committed is True
