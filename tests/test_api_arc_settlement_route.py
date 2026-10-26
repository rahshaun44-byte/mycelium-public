# tests/test_api_arc_settlement_route.py
"""
Integration Tests for Circle Arc L1 Settlement Route on API Gateway (:8080).
"""

from fastapi.testclient import TestClient
import pytest

from api_node.main import app

client = TestClient(app)


def test_arc_settlement_route_nominal_dry_run():
    payload = {
        "recipient_address": "0x1234567890abcdef1234567890abcdef12345678",
        "amount_usdc": "10.50",
        "block_hash": "0xabc123def456abc123def456abc123def456abc123def456abc123def456abc1",
        "nonce": 1,
    }
    response = client.post("/api/v1/settlement/arc", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SETTLEMENT_COMMITTED_DRY_RUN"
    assert data["chain"] == "Circle Arc L1"
    assert data["gas_token"] == "NATIVE_USDC"
    assert data["settlement"]["amount_micro_usdc"] == 10_500_000
    assert data["settlement"]["amount_usdc_display"] == 10.5
    assert "idempotency_key" in data["idempotency"]


def test_arc_settlement_route_rejects_negative_amount():
    payload = {
        "recipient_address": "0x1234567890abcdef1234567890abcdef12345678",
        "amount_usdc": -5.0,
        "block_hash": "0xabc123def456abc123def456abc123def456abc123def456abc123def456abc1",
        "nonce": 1,
    }
    response = client.post("/api/v1/settlement/arc", json=payload)
    assert response.status_code == 400
    assert "negative" in response.json()["detail"]


def test_arc_settlement_route_rejects_malformed_address():
    payload = {
        "recipient_address": "not_an_evm_address",
        "amount_usdc": "1.00",
        "block_hash": "0xabc123def456abc123def456abc123def456abc123def456abc123def456abc1",
        "nonce": 1,
    }
    response = client.post("/api/v1/settlement/arc", json=payload)
    assert response.status_code == 400
    assert "recipient address" in response.json()["detail"].lower()


def test_arc_settlement_route_fails_closed_on_privacy_optout():
    payload = {
        "recipient_address": "0x1234567890abcdef1234567890abcdef12345678",
        "amount_usdc": "1.00",
        "block_hash": "0xabc123def456_optout_abc123def456",
        "nonce": 1,
    }
    response = client.post("/api/v1/settlement/arc", json=payload)
    assert response.status_code == 403
    assert "Privacy opt-out tag detected" in response.json()["detail"]
