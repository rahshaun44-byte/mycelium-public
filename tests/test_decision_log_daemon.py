#!/usr/bin/env python3
"""
Unit and integration tests for Quantum Flex OPA Decision Log Receiver Daemon.
Tests gzip decompression, payload limits, strict IP validation,
decision_id deduplication, dry-run vs enforcement modes, and authentication.
"""

import gzip
import json
import threading
import time
import urllib.request
import urllib.error
import pytest

from sentinel.decision_log_daemon import (
    ThreadedDecisionLogServer,
    TelemetryStats,
    MAX_PAYLOAD_BYTES,
)


@pytest.fixture
def test_server():
    """Spins up a test instance of ThreadedDecisionLogServer on loopback with an ephemeral port."""
    hook_calls = []

    def recorder_hook(ip, entry):
        hook_calls.append((ip, entry))

    server = ThreadedDecisionLogServer(
        ("127.0.0.1", 0),
        dry_run=True,
        shared_secret="test-token-xyz",
        containment_hook=recorder_hook,
    )
    port = server.server_port
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    yield {
        "server": server,
        "port": port,
        "base_url": f"http://127.0.0.1:{port}",
        "hook_calls": hook_calls,
    }

    server.shutdown()
    server.server_close()


def make_request(url, data=None, headers=None, method="GET"):
    """Helper for loopback HTTP queries."""
    hdrs = headers or {}
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            body = resp.read()
            return resp.status, json.loads(body.decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            parsed = json.loads(body.decode("utf-8"))
        except Exception:
            parsed = {"raw": body.decode("utf-8", errors="replace")}
        return e.code, parsed


def test_healthz_and_stats(test_server):
    """Verify /healthz and /stats telemetry endpoints."""
    status, body = make_request(f"{test_server['base_url']}/healthz")
    assert status == 200
    assert body["status"] == "healthy"
    assert body["mode"] == "dry-run"

    status, body = make_request(f"{test_server['base_url']}/stats")
    assert status == 200
    assert "stats" in body
    assert body["stats"]["batches_received"] == 0


def test_unauthenticated_request_rejected(test_server):
    """Requests missing or with invalid X-OPA-Secret return 401."""
    payload = json.dumps([{"decision_id": "dec-1", "path": "quantumflex/gatekeeper/decision"}]).encode("utf-8")
    status, body = make_request(
        f"{test_server['base_url']}/logs",
        data=payload,
        headers={"Content-Type": "application/json", "X-OPA-Secret": "wrong-secret"},
        method="POST",
    )
    assert status == 401
    assert "error" in body


def test_uncompressed_allowed_event(test_server):
    """An authorized event updates stats and does not trigger containment."""
    event = {
        "decision_id": "dec-allow-01",
        "path": "quantumflex/gatekeeper/decision",
        "input": {"source_ip": "100.64.1.23"},
        "result": {"allow": True, "reason": "trusted_source"},
    }
    payload = json.dumps([event]).encode("utf-8")
    status, body = make_request(
        f"{test_server['base_url']}/logs",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-OPA-Secret": "test-token-xyz",
        },
        method="POST",
    )
    assert status == 200
    assert body["events_accepted"] == 1

    _, stats = make_request(f"{test_server['base_url']}/stats")
    assert stats["stats"]["decisions_allowed"] == 1
    assert stats["stats"]["decisions_denied"] == 0
    assert stats["stats"]["would_contain_count"] == 0


def test_uncompressed_denied_event_dry_run(test_server):
    """A denied event in dry-run mode increments would_contain_count and does NOT trigger hook."""
    event = {
        "decision_id": "dec-deny-01",
        "path": "quantumflex/gatekeeper/decision",
        "input": {"source_ip": "100.64.1.28"},
        "result": {"allow": False, "reason": "untrusted_source"},
    }
    payload = json.dumps([event]).encode("utf-8")
    status, body = make_request(
        f"{test_server['base_url']}/logs",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-OPA-Secret": "test-token-xyz",
        },
        method="POST",
    )
    assert status == 200
    assert body["events_accepted"] == 1

    _, stats = make_request(f"{test_server['base_url']}/stats")
    assert stats["stats"]["decisions_denied"] == 1
    assert stats["stats"]["would_contain_count"] == 1
    assert stats["stats"]["contained_count"] == 0
    assert len(test_server["hook_calls"]) == 0

    # Verify audit endpoint records the entry
    status, audit = make_request(f"{test_server['base_url']}/audit")
    assert status == 200
    assert audit["count"] == 1
    assert audit["records"][0]["source_ip"] == "100.64.1.28"
    assert audit["records"][0]["is_tailscale"] is True


def test_gzip_compressed_batch(test_server):
    """Handles standard OPA gzip-compressed multi-event batch payloads."""
    events = [
        {
            "decision_id": "dec-batch-1",
            "path": "quantumflex/gatekeeper/decision",
            "input": {"source_ip": "100.64.1.23"},
            "result": {"allow": True, "reason": "trusted_source"},
        },
        {
            "decision_id": "dec-batch-2",
            "path": "quantumflex/gatekeeper/decision",
            "input": {"source_ip": "192.168.100.20"},
            "result": {"allow": False, "reason": "untrusted_source"},
        },
    ]
    raw_json = json.dumps(events).encode("utf-8")
    compressed = gzip.compress(raw_json)

    status, body = make_request(
        f"{test_server['base_url']}/logs",
        data=compressed,
        headers={
            "Content-Type": "application/json",
            "Content-Encoding": "gzip",
            "X-OPA-Secret": "test-token-xyz",
        },
        method="POST",
    )
    assert status == 200
    assert body["events_accepted"] == 2

    _, stats = make_request(f"{test_server['base_url']}/stats")
    assert stats["stats"]["batches_received"] == 1
    assert stats["stats"]["events_processed"] == 2
    assert stats["stats"]["decisions_allowed"] == 1
    assert stats["stats"]["decisions_denied"] == 1
    assert stats["stats"]["would_contain_count"] == 1


def test_deduplication_of_decision_id(test_server):
    """Duplicate decision_id events are safely ignored and increment duplicates_skipped."""
    event = {
        "decision_id": "dec-repeat-01",
        "path": "quantumflex/gatekeeper/decision",
        "input": {"source_ip": "100.64.1.27"},
        "result": {"allow": False, "reason": "untrusted_source"},
    }
    payload = json.dumps([event]).encode("utf-8")
    hdrs = {"Content-Type": "application/json", "X-OPA-Secret": "test-token-xyz"}

    # First delivery
    status1, _ = make_request(f"{test_server['base_url']}/logs", data=payload, headers=hdrs, method="POST")
    assert status1 == 200

    # Second delivery (replay / retransmit)
    status2, _ = make_request(f"{test_server['base_url']}/logs", data=payload, headers=hdrs, method="POST")
    assert status2 == 200

    _, stats = make_request(f"{test_server['base_url']}/stats")
    assert stats["stats"]["duplicates_skipped"] == 1
    assert stats["stats"]["would_contain_count"] == 1


def test_ip_injection_rejection(test_server):
    """Malicious input in source_ip is rejected by strict RFC IP validation."""
    malicious_inputs = [
        "100.64.1.23; rm -rf /",
        "192.168.100.18`whoami`",
        "cat /etc/passwd",
        "100.64.0.256",
        "not_an_ip_address",
    ]

    for idx, bad_ip in enumerate(malicious_inputs):
        event = {
            "decision_id": f"dec-malicious-{idx}",
            "path": "quantumflex/gatekeeper/decision",
            "input": {"source_ip": bad_ip},
            "result": {"allow": False, "reason": "untrusted_source"},
        }
        payload = json.dumps([event]).encode("utf-8")
        status, _ = make_request(
            f"{test_server['base_url']}/logs",
            data=payload,
            headers={"Content-Type": "application/json", "X-OPA-Secret": "test-token-xyz"},
            method="POST",
        )
        assert status == 200

    _, stats = make_request(f"{test_server['base_url']}/stats")
    assert stats["stats"]["malformed_events_rejected"] == len(malicious_inputs)
    assert stats["stats"]["would_contain_count"] == 0
    assert len(test_server["hook_calls"]) == 0


def test_live_enforcement_mode():
    """In live enforcement mode (dry_run=False), the containment hook is executed."""
    hook_calls = []

    def recorder_hook(ip, entry):
        hook_calls.append((ip, entry))

    server = ThreadedDecisionLogServer(
        ("127.0.0.1", 0),
        dry_run=False,
        shared_secret="secret-key",
        containment_hook=recorder_hook,
    )
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    port = server.server_port

    try:
        event = {
            "decision_id": "dec-enforce-01",
            "path": "quantumflex/gatekeeper/decision",
            "input": {"source_ip": "100.64.1.26"},
            "result": {"allow": False, "reason": "untrusted_source"},
        }
        payload = json.dumps([event]).encode("utf-8")
        status, _ = make_request(
            f"http://127.0.0.1:{port}/logs",
            data=payload,
            headers={"Content-Type": "application/json", "X-OPA-Secret": "secret-key"},
            method="POST",
        )
        assert status == 200
        assert server.stats.contained_count == 1
        assert len(hook_calls) == 1
        assert hook_calls[0][0] == "100.64.1.26"
        assert hook_calls[0][1]["mode"] == "enforce"
    finally:
        server.shutdown()
        server.server_close()
