"""Unwired tasks must not acquire COMPLETED status or dispatch requests.

All inputs are isolated test fixtures; no live queue or credentials are used.
"""

import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def worker(monkeypatch):
    monkeypatch.setenv("GHOSTNODE_DB_USER", "test-only")
    monkeypatch.setenv("GHOSTNODE_DB_PASSWORD", "test-only")
    path = Path(__file__).resolve().parents[1] / "mcp_layer/swarm_worker.py"
    spec = importlib.util.spec_from_file_location("isolated_swarm_worker", path)
    module = importlib.util.module_from_spec(spec)
    with patch("dotenv.load_dotenv"):
        spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("target", ["amara", "AMARA", "iac", "unknown", "unregistered"])
def test_unwired_task_fails_without_actuation(worker, target):
    with patch("requests.post") as request, patch.object(worker, "get_db") as db:
        status, outcome = worker.execute_task({
            "id": 1,
            "task_payload": {"target_node": target, "action": "deploy"},
        })
    assert status == "FAILED"
    assert "not wired" in outcome or "no actuator" in outcome
    request.assert_not_called()
    db.assert_not_called()


def test_missing_target_fails(worker):
    status, _ = worker.execute_task({"id": 2, "task_payload": {"action": "deploy"}})
    assert status == "FAILED"


def test_athena_http_failure_is_not_completed(worker):
    with patch("requests.post") as request:
        request.return_value.status_code = 401
        request.return_value.text = "Unauthorized"
        status, _ = worker.execute_task({
            "id": 3,
            "task_payload": {"target_node": "athena", "action": "query"},
        })
    assert status == "FAILED"
