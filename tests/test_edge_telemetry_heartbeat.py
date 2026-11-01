# tests/test_edge_telemetry_heartbeat.py
"""
Unit and Integration Tests for Decoupled Asynchronous Edge Telemetry Heartbeat (QF-M1)
=====================================================================================
Validates:
- Security Weakness A: Mandatory pqc_signature authentication & cryptographic verification
- Security Weakness B: Separation of hardware_claim from hardware_verified attestation
- Security Weakness C: Untrusted IP boundary (transport_peer_ip vs reported_ip)
- Reliability: Durable PostgreSQL commit before HTTP 202 Accepted
"""

import base64
import os
import tempfile
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives.asymmetric import ec, ed25519
from cryptography.hazmat.primitives import serialization

from api_node.main import app
from src.edge_verification import sign_heartbeat_payload

client = TestClient(app)


@pytest.fixture
def test_keys_env(tmp_path, monkeypatch):
    """Sets up an isolated device keys directory with enrolled test keys."""
    keys_dir = tmp_path / "devices"
    keys_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("QF_DEVICE_KEYS_DIR", str(keys_dir))

    # 1. Enrolled Pixel Key (ECDSA P-256)
    pixel_privkey = ec.generate_private_key(ec.SECP256R1())
    (keys_dir / "qfx-pixel.pem").write_bytes(
        pixel_privkey.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )

    # 2. Enrolled Yoga Key (Ed25519)
    yoga_privkey = ed25519.Ed25519PrivateKey.generate()
    (keys_dir / "qfx-yoga.pem").write_bytes(
        yoga_privkey.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )

    return {
        "keys_dir": keys_dir,
        "pixel_privkey": pixel_privkey,
        "yoga_privkey": yoga_privkey,
    }


def test_edge_heartbeat_missing_signature_rejected():
    """Verify heartbeat without pqc_signature is rejected by schema (HTTP 422)."""
    payload = {
        "node_id": "qfx-pixel",
        "tailscale_ip": "100.64.1.16",
        "hardware_claim": "Titan-M3",
    }
    response = client.post("/api/v1/telemetry/heartbeat", json=payload)
    assert response.status_code == 422


def test_edge_heartbeat_empty_signature_rejected():
    """Verify heartbeat with empty pqc_signature is rejected with HTTP 401."""
    payload = {
        "node_id": "qfx-pixel",
        "timestamp": int(time.time()),
        "nonce": "test_nonce_empty_sig",
        "pqc_signature": "   ",
        "hardware_claim": "Titan-M3",
    }
    response = client.post("/api/v1/telemetry/heartbeat", json=payload)
    assert response.status_code == 401
    assert "missing or empty" in response.json()["detail"].lower()


def test_edge_heartbeat_invalid_signature_rejected(test_keys_env):
    """Verify heartbeat with invalid/corrupted cryptographic signature is rejected with HTTP 401."""
    now = int(time.time())
    nonce = "test_nonce_inv_sig"
    payload = {
        "node_id": "qfx-pixel",
        "timestamp": now,
        "nonce": nonce,
        "pqc_signature": "dGVzdF9pbnZhbGlkX3NpZw==",
        "hardware_claim": "Titan-M3",
        "entropy_h": 0.05,
    }
    response = client.post("/api/v1/telemetry/heartbeat", json=payload)
    assert response.status_code == 401
    assert "signature verification failed" in response.json()["detail"]


def test_edge_heartbeat_valid_ecdsa_signature_accepted(test_keys_env):
    """Verify valid ECDSA signature for qfx-pixel returns 202 Accepted and records claim without auto-promotion."""
    from src.edge_verification import sign_heartbeat_v2
    pixel_priv = test_keys_env["pixel_privkey"]
    now = int(time.time())
    nonce = "test_nonce_ecdsa_valid"
    payload = {
        "node_id": "qfx-pixel",
        "timestamp": now,
        "nonce": nonce,
        "hardware_claim": "Titan-M3",
        "tailscale_ip": "100.64.1.16",
        "pqc_algorithm": "ML-KEM-768",
        "entropy_h": 0.05,
    }
    sig, _, _ = sign_heartbeat_v2("qfx-pixel", pixel_priv, payload, timestamp=now, nonce=nonce)
    payload["pqc_signature"] = sig

    response = client.post("/api/v1/telemetry/heartbeat", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "ACCEPTED"
    assert data["node_id"] == "qfx-pixel"
    assert data["node_status"] == "ACTIVE"
    # Hardware claim alone must NOT set hardware_verified to True
    assert data["hardware_verified"] is False
    assert "epoch" in data


def test_edge_heartbeat_valid_ed25519_signature_accepted(test_keys_env):
    """Verify valid Ed25519 signature for qfx-yoga on loopback succeeds and verifies hardware."""
    from src.edge_verification import sign_heartbeat_v2
    yoga_priv = test_keys_env["yoga_privkey"]
    now = int(time.time())
    nonce = "test_nonce_ed25519_valid"
    payload = {
        "node_id": "qfx-yoga",
        "timestamp": now,
        "nonce": nonce,
        "hardware_claim": "Pluton-TPM2",
        "tailscale_ip": "100.64.1.31",
        "entropy_h": 0.0,
    }
    sig, _, _ = sign_heartbeat_v2("qfx-yoga", yoga_priv, payload, timestamp=now, nonce=nonce)
    payload["pqc_signature"] = sig

    response = client.post("/api/v1/telemetry/heartbeat", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "ACCEPTED"
    assert data["node_id"] == "qfx-yoga"
    assert data["node_status"] == "ACTIVE"
    assert data["hardware_verified"] is True


def test_edge_heartbeat_fallback_ip_handling(test_keys_env):
    """Verify non-standard reported IP string is safely recorded without throwing INET DB error."""
    from src.edge_verification import sign_heartbeat_v2
    pixel_priv = test_keys_env["pixel_privkey"]
    now = int(time.time())
    nonce = "test_nonce_fallback_ip"
    payload = {
        "node_id": "qfx-pixel",
        "timestamp": now,
        "nonce": nonce,
        "hardware_claim": "Titan-M3",
        "tailscale_ip": "not_an_ip",
    }
    sig, _, _ = sign_heartbeat_v2("qfx-pixel", pixel_priv, payload, timestamp=now, nonce=nonce)
    payload["pqc_signature"] = sig

    response = client.post("/api/v1/telemetry/heartbeat", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "ACCEPTED"
    assert data["reported_ip"] is None


def test_edge_heartbeat_spoofed_peer_ip_quarantined(test_keys_env):
    """Verify heartbeat from an unauthorized network transport IP is quarantined."""
    from src.edge_verification import sign_heartbeat_v2
    spoofed_client = TestClient(app, client=("198.51.100.42", 44321))
    pixel_priv = test_keys_env["pixel_privkey"]
    now = int(time.time())
    nonce = "test_nonce_spoofed_peer"
    payload = {
        "node_id": "qfx-pixel",
        "timestamp": now,
        "nonce": nonce,
        "hardware_claim": "Titan-M3",
        "tailscale_ip": "100.64.1.16",
    }
    sig, _, _ = sign_heartbeat_v2("qfx-pixel", pixel_priv, payload, timestamp=now, nonce=nonce)
    payload["pqc_signature"] = sig

    response = spoofed_client.post("/api/v1/telemetry/heartbeat", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "ACCEPTED"
    assert data["node_id"] == "qfx-pixel"
    assert data["node_status"] == "QUARANTINED"
    assert data["hardware_verified"] is False
    assert data["transport_ip"] == "198.51.100.42"


def test_edge_heartbeat_durable_commit_verified(test_keys_env):
    """Verify database write is synchronously durable upon return."""
    from src.edge_verification import sign_heartbeat_v2
    pixel_priv = test_keys_env["pixel_privkey"]
    now = int(time.time())
    nonce = "test_nonce_durable_commit"
    payload = {
        "node_id": "qfx-pixel",
        "timestamp": now,
        "nonce": nonce,
        "hardware_claim": "Titan-M3",
        "tailscale_ip": "100.64.1.16",
        "entropy_h": 0.07,
    }
    sig, _, _ = sign_heartbeat_v2("qfx-pixel", pixel_priv, payload, timestamp=now, nonce=nonce)
    payload["pqc_signature"] = sig

    response = client.post("/api/v1/telemetry/heartbeat", json=payload)
    assert response.status_code == 202

    from src.db_credentials import DatabaseRole, open_role_connection
    conn = open_role_connection(role=DatabaseRole.VERIFIER, dbname="telemetry")
    with conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT node_id, hardware_claim, hardware_verified, status, entropy_delta_h, reported_ip
                FROM node_registry WHERE node_id = 'qfx-pixel';
            """)
            row = cur.fetchone()
            assert row is not None
            assert row[0] == "qfx-pixel"
            assert row[1] == "Titan-M3"
            assert row[2] is False  # Hardware claim is not auto-promoted to verified
            assert row[3] == "ACTIVE"
            assert row[4] == 0.07
            assert str(row[5]) == "100.64.1.16"
    conn.close()


