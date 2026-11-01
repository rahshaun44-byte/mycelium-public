# tests/test_edge_replay_protection.py
"""
Adversarial Verification Suite: Edge Heartbeat Replay Protection (Phase 2.1)
=============================================================================
Validates:
1. Valid signed QF-EDGE-TRUST-v2 heartbeat -> HTTP 202 Accepted
2. Identical heartbeat replay -> HTTP 401 Replay Detected
3. Duplicate nonce reuse -> HTTP 401 Replay Detected
4. Tampered payload body -> HTTP 401 Signature Verification Failed
5. Tampered node identity -> HTTP 401 Signature Verification Failed
6. Tampered nonce -> HTTP 401 Signature Verification Failed
7. Failed authentication does not burn nonce (replay cache exhaustion prevention)
8. Concurrent duplicate requests -> Exactly one accepted
9. SQLite storage failure -> Fails closed
"""

import concurrent.futures
import os
import secrets
import tempfile
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

from api_node.main import app
from src.edge_verification import sign_heartbeat_v2, compute_request_body_digest

client = TestClient(app)


@pytest.fixture
def replay_env(tmp_path, monkeypatch):
    """Sets up an isolated test environment with enrolled key and fresh SQLite replay DB."""
    keys_dir = tmp_path / "devices"
    keys_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("QF_DEVICE_KEYS_DIR", str(keys_dir))

    # Enrolled Pixel Key (ECDSA P-256)
    pixel_priv = ec.generate_private_key(ec.SECP256R1())
    (keys_dir / "qfx-pixel.pem").write_bytes(
        pixel_priv.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )

    return {
        "keys_dir": keys_dir,
        "pixel_priv": pixel_priv,
    }


def test_valid_signed_heartbeat_accepted(replay_env):
    """Verify nominal QF-EDGE-TRUST-v2 signed heartbeat succeeds with HTTP 202."""
    priv = replay_env["pixel_priv"]
    now = int(time.time())
    nonce = secrets.token_hex(16)
    body = {
        "node_id": "qfx-pixel",
        "timestamp": now,
        "nonce": nonce,
        "hardware_claim": "Titan-M3",
        "tailscale_ip": "100.64.1.16",
        "pqc_algorithm": "ML-KEM-768",
        "entropy_h": 0.05,
    }
    sig, _, _ = sign_heartbeat_v2("qfx-pixel", priv, body, timestamp=now, nonce=nonce)
    body["pqc_signature"] = sig

    response = client.post("/api/v1/telemetry/heartbeat", json=body)
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "ACCEPTED"
    assert data["node_id"] == "qfx-pixel"


def test_identical_heartbeat_replay_rejected(replay_env):
    """Verify an identical signed heartbeat submitted a second time is rejected as replay."""
    priv = replay_env["pixel_priv"]
    now = int(time.time())
    nonce = secrets.token_hex(16)
    body = {
        "node_id": "qfx-pixel",
        "timestamp": now,
        "nonce": nonce,
        "hardware_claim": "Titan-M3",
        "tailscale_ip": "100.64.1.16",
        "entropy_h": 0.05,
    }
    sig, _, _ = sign_heartbeat_v2("qfx-pixel", priv, body, timestamp=now, nonce=nonce)
    body["pqc_signature"] = sig

    # First attempt: nominal acceptance
    resp1 = client.post("/api/v1/telemetry/heartbeat", json=body)
    assert resp1.status_code == 202

    # Second attempt: exact replay attack
    resp2 = client.post("/api/v1/telemetry/heartbeat", json=body)
    assert resp2.status_code == 401
    assert "Replay detected" in resp2.json()["detail"]


def test_duplicate_nonce_rejected(replay_env):
    """Verify reusing a consumed nonce even with a new timestamp is rejected as replay."""
    priv = replay_env["pixel_priv"]
    now = int(time.time())
    reused_nonce = secrets.token_hex(16)

    # 1. First valid transmission
    body1 = {
        "node_id": "qfx-pixel",
        "timestamp": now,
        "nonce": reused_nonce,
        "hardware_claim": "Titan-M3",
        "entropy_h": 0.01,
    }
    sig1, _, _ = sign_heartbeat_v2("qfx-pixel", priv, body1, timestamp=now, nonce=reused_nonce)
    body1["pqc_signature"] = sig1
    resp1 = client.post("/api/v1/telemetry/heartbeat", json=body1)
    assert resp1.status_code == 202

    # 2. Second transmission attempting to reuse the same nonce
    body2 = {
        "node_id": "qfx-pixel",
        "timestamp": now + 2,
        "nonce": reused_nonce,
        "hardware_claim": "Titan-M3",
        "entropy_h": 0.02,
    }
    sig2, _, _ = sign_heartbeat_v2("qfx-pixel", priv, body2, timestamp=now + 2, nonce=reused_nonce)
    body2["pqc_signature"] = sig2
    resp2 = client.post("/api/v1/telemetry/heartbeat", json=body2)
    assert resp2.status_code == 401
    assert "Replay detected" in resp2.json()["detail"]


def test_tampered_payload_rejected(replay_env):
    """Verify modifying any payload field after signing invalidates the signature."""
    priv = replay_env["pixel_priv"]
    now = int(time.time())
    nonce = secrets.token_hex(16)
    body = {
        "node_id": "qfx-pixel",
        "timestamp": now,
        "nonce": nonce,
        "hardware_claim": "Titan-M3",
        "entropy_h": 0.05,
    }
    sig, _, _ = sign_heartbeat_v2("qfx-pixel", priv, body, timestamp=now, nonce=nonce)
    body["pqc_signature"] = sig

    # Adversarial tampering: modify entropy_h
    body["entropy_h"] = 0.999
    response = client.post("/api/v1/telemetry/heartbeat", json=body)
    assert response.status_code == 401
    assert "signature verification failed" in response.json()["detail"]


def test_tampered_node_id_rejected(replay_env):
    """Verify spoofing node_id on a signed payload is rejected."""
    priv = replay_env["pixel_priv"]
    now = int(time.time())
    nonce = secrets.token_hex(16)
    body = {
        "node_id": "qfx-pixel",
        "timestamp": now,
        "nonce": nonce,
        "hardware_claim": "Titan-M3",
    }
    sig, _, _ = sign_heartbeat_v2("qfx-pixel", priv, body, timestamp=now, nonce=nonce)
    body["pqc_signature"] = sig

    # Adversarial tampering: change node_id to qfx-yoga
    body["node_id"] = "qfx-yoga"
    response = client.post("/api/v1/telemetry/heartbeat", json=body)
    assert response.status_code == 401


def test_tampered_nonce_rejected(replay_env):
    """Verify modifying the nonce after signing is rejected."""
    priv = replay_env["pixel_priv"]
    now = int(time.time())
    nonce = secrets.token_hex(16)
    body = {
        "node_id": "qfx-pixel",
        "timestamp": now,
        "nonce": nonce,
        "hardware_claim": "Titan-M3",
    }
    sig, _, _ = sign_heartbeat_v2("qfx-pixel", priv, body, timestamp=now, nonce=nonce)
    body["pqc_signature"] = sig

    # Adversarial tampering: modify nonce
    body["nonce"] = secrets.token_hex(16)
    response = client.post("/api/v1/telemetry/heartbeat", json=body)
    assert response.status_code == 401
    assert "signature verification failed" in response.json()["detail"]


def test_unauthenticated_request_does_not_burn_nonce(replay_env):
    """Verify an invalid signature does NOT consume the nonce (prevents replay-cache exhaustion)."""
    priv = replay_env["pixel_priv"]
    now = int(time.time())
    target_nonce = secrets.token_hex(16)

    # 1. Attacker sends forged signature with target_nonce
    forged_body = {
        "node_id": "qfx-pixel",
        "timestamp": now,
        "nonce": target_nonce,
        "pqc_signature": "dGVzdF9mb3JnZWRfc2lnbmF0dXJl",
        "hardware_claim": "Titan-M3",
    }
    resp1 = client.post("/api/v1/telemetry/heartbeat", json=forged_body)
    assert resp1.status_code == 401

    # 2. Legitimate node transmits valid heartbeat using the same target_nonce
    valid_body = {
        "node_id": "qfx-pixel",
        "timestamp": now,
        "nonce": target_nonce,
        "hardware_claim": "Titan-M3",
    }
    sig, _, _ = sign_heartbeat_v2("qfx-pixel", priv, valid_body, timestamp=now, nonce=target_nonce)
    valid_body["pqc_signature"] = sig
    resp2 = client.post("/api/v1/telemetry/heartbeat", json=valid_body)
    assert resp2.status_code == 202
    assert resp2.json()["status"] == "ACCEPTED"


def test_concurrent_duplicate_requests_exactly_one_accepted(replay_env):
    """Verify 10 simultaneous concurrent requests with the identical nonce result in exactly 1 acceptance."""
    priv = replay_env["pixel_priv"]
    now = int(time.time())
    nonce = secrets.token_hex(16)
    body = {
        "node_id": "qfx-pixel",
        "timestamp": now,
        "nonce": nonce,
        "hardware_claim": "Titan-M3",
        "tailscale_ip": "100.64.1.16",
    }
    sig, _, _ = sign_heartbeat_v2("qfx-pixel", priv, body, timestamp=now, nonce=nonce)
    body["pqc_signature"] = sig

    def _send_request():
        return client.post("/api/v1/telemetry/heartbeat", json=body)

    # Fire 10 parallel requests
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(_send_request) for _ in range(10)]
        results = [f.result() for f in futures]

    statuses = [r.status_code for r in results]
    accepted_count = statuses.count(202)
    rejected_count = statuses.count(401)

    assert accepted_count == 1, f"Expected exactly 1 accepted request, got {accepted_count}"
    assert rejected_count == 9, f"Expected 9 rejected requests, got {rejected_count}"


def test_sqlite_unavailable_fails_closed(replay_env, monkeypatch):
    """Verify that if SQLite nonce storage fails, the system fails closed with 500 error."""
    priv = replay_env["pixel_priv"]
    now = int(time.time())
    nonce = secrets.token_hex(16)
    body = {
        "node_id": "qfx-pixel",
        "timestamp": now,
        "nonce": nonce,
        "hardware_claim": "Titan-M3",
    }
    sig, _, _ = sign_heartbeat_v2("qfx-pixel", priv, body, timestamp=now, nonce=nonce)
    body["pqc_signature"] = sig

    # Monkeypatch sqlite3.connect to simulate filesystem I/O / disk failure
    from unittest.mock import patch
    with patch("src.edge_verification.sqlite3.connect", side_effect=OSError("Read-only file system")):
        response = client.post("/api/v1/telemetry/heartbeat", json=body)
        assert response.status_code == 500
        assert "replay cache storage failure" in response.json()["detail"]
