# tests/test_edge_timestamp_freshness.py
"""
Adversarial Verification Suite: Edge Timestamp Freshness & Clock Skew (Phase 2.1)
==================================================================================
Validates:
1. Fresh timestamp within 60-second window -> HTTP 202 Accepted
2. Timestamp older than 60 seconds -> HTTP 401 Expired
3. Timestamp more than 60 seconds ahead -> HTTP 401 Future invalid
4. Boundary condition tests (+55s, -55s) -> HTTP 202 Accepted
5. Tampered timestamp -> HTTP 401 Signature verification failed
6. Missing nonce -> HTTP 422 Unprocessable Content
7. Missing timestamp -> HTTP 422 Unprocessable Content
"""

import secrets
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

from api_node.main import app
from src.edge_verification import sign_heartbeat_v2

client = TestClient(app)


@pytest.fixture
def freshness_env(tmp_path, monkeypatch):
    """Sets up an isolated test environment with enrolled key."""
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


def test_fresh_timestamp_nominal(freshness_env):
    """Verify fresh timestamp within normal operation succeeds with HTTP 202."""
    priv = freshness_env["pixel_priv"]
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

    response = client.post("/api/v1/telemetry/heartbeat", json=body)
    assert response.status_code == 202
    assert response.json()["status"] == "ACCEPTED"


def test_timestamp_older_than_60s_rejected(freshness_env):
    """Verify heartbeat with timestamp 65 seconds in the past is rejected as expired."""
    priv = freshness_env["pixel_priv"]
    now = int(time.time())
    stale_ts = now - 65
    nonce = secrets.token_hex(16)
    body = {
        "node_id": "qfx-pixel",
        "timestamp": stale_ts,
        "nonce": nonce,
        "hardware_claim": "Titan-M3",
    }
    sig, _, _ = sign_heartbeat_v2("qfx-pixel", priv, body, timestamp=stale_ts, nonce=nonce)
    body["pqc_signature"] = sig

    response = client.post("/api/v1/telemetry/heartbeat", json=body)
    assert response.status_code == 401
    assert "Timestamp expired" in response.json()["detail"]


def test_timestamp_more_than_60s_ahead_rejected(freshness_env):
    """Verify heartbeat with timestamp 65 seconds in the future is rejected."""
    priv = freshness_env["pixel_priv"]
    now = int(time.time())
    future_ts = now + 65
    nonce = secrets.token_hex(16)
    body = {
        "node_id": "qfx-pixel",
        "timestamp": future_ts,
        "nonce": nonce,
        "hardware_claim": "Titan-M3",
    }
    sig, _, _ = sign_heartbeat_v2("qfx-pixel", priv, body, timestamp=future_ts, nonce=nonce)
    body["pqc_signature"] = sig

    response = client.post("/api/v1/telemetry/heartbeat", json=body)
    assert response.status_code == 401
    assert "Timestamp invalid" in response.json()["detail"]


def test_boundary_timestamp_past_accepted(freshness_env):
    """Verify heartbeat at boundary (55s in past, within 60s) succeeds."""
    priv = freshness_env["pixel_priv"]
    now = int(time.time())
    valid_past_ts = now - 55
    nonce = secrets.token_hex(16)
    body = {
        "node_id": "qfx-pixel",
        "timestamp": valid_past_ts,
        "nonce": nonce,
        "hardware_claim": "Titan-M3",
    }
    sig, _, _ = sign_heartbeat_v2("qfx-pixel", priv, body, timestamp=valid_past_ts, nonce=nonce)
    body["pqc_signature"] = sig

    response = client.post("/api/v1/telemetry/heartbeat", json=body)
    assert response.status_code == 202


def test_boundary_timestamp_future_accepted(freshness_env):
    """Verify heartbeat at boundary (55s in future, within 60s) succeeds."""
    priv = freshness_env["pixel_priv"]
    now = int(time.time())
    valid_future_ts = now + 55
    nonce = secrets.token_hex(16)
    body = {
        "node_id": "qfx-pixel",
        "timestamp": valid_future_ts,
        "nonce": nonce,
        "hardware_claim": "Titan-M3",
    }
    sig, _, _ = sign_heartbeat_v2("qfx-pixel", priv, body, timestamp=valid_future_ts, nonce=nonce)
    body["pqc_signature"] = sig

    response = client.post("/api/v1/telemetry/heartbeat", json=body)
    assert response.status_code == 202


def test_tampered_timestamp_rejected(freshness_env):
    """Verify altering timestamp after signing fails signature verification."""
    priv = freshness_env["pixel_priv"]
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

    # Attacker alters timestamp to now - 5 seconds
    body["timestamp"] = now - 5
    response = client.post("/api/v1/telemetry/heartbeat", json=body)
    assert response.status_code == 401
    assert "signature verification failed" in response.json()["detail"]


def test_missing_nonce_rejected_422():
    """Verify request with missing nonce is rejected with HTTP 422 Unprocessable Content."""
    now = int(time.time())
    body = {
        "node_id": "qfx-pixel",
        "timestamp": now,
        "pqc_signature": "dummy_signature",
        "hardware_claim": "Titan-M3",
    }
    response = client.post("/api/v1/telemetry/heartbeat", json=body)
    assert response.status_code == 422


def test_missing_timestamp_rejected_422():
    """Verify request with missing timestamp is rejected with HTTP 422 Unprocessable Content."""
    body = {
        "node_id": "qfx-pixel",
        "nonce": secrets.token_hex(16),
        "pqc_signature": "dummy_signature",
        "hardware_claim": "Titan-M3",
    }
    response = client.post("/api/v1/telemetry/heartbeat", json=body)
    assert response.status_code == 422
