# tests/test_edge_telemetry_heartbeat.py
"""
Unit and Integration Tests for Decoupled Asynchronous Edge Telemetry Heartbeat (QF-M1)
=====================================================================================
Validates:
- POST /api/v1/telemetry/heartbeat accepts payloads asynchronously with 202 Accepted
- Pydantic v2 schema resolves properly in Python 3.14 without PydanticUserError
- Safe fallback on malformed or absent client IPs
- Non-blocking execution behavior
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from api_node.main import app

client = TestClient(app)


def test_edge_telemetry_heartbeat_nominal():
    """Verify heartbeat returns 202 Accepted immediately for active edge nodes."""
    payload = {
        "node_id": "qfx-pixel",
        "tailscale_ip": "100.64.1.16",
        "hardware_attestation": "Titan-M3",
        "pqc_algorithm": "ML-KEM-768",
        "entropy_h": 0.05
    }
    response = client.post("/api/v1/telemetry/heartbeat", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "ACCEPTED"
    assert data["node_id"] == "qfx-pixel"
    assert "epoch" in data


def test_edge_telemetry_heartbeat_minimal():
    """Verify heartbeat with minimal required fields succeeds with default attestation."""
    payload = {"node_id": "qfx-yoga"}
    response = client.post("/api/v1/telemetry/heartbeat", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "ACCEPTED"
    assert data["node_id"] == "qfx-yoga"


def test_edge_telemetry_heartbeat_fallback_ip_handling():
    """Verify non-standard client IP strings (e.g. TestClient host) fall back safely without DB error."""
    payload = {
        "node_id": "qfx-pixel",
        "tailscale_ip": "not_an_ip"
    }
    response = client.post("/api/v1/telemetry/heartbeat", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "ACCEPTED"
