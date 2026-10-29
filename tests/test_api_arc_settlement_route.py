# tests/test_api_arc_settlement_route.py
"""
Integration Tests for Circle Arc L1 Settlement Route on API Gateway (:8080).
"""

from fastapi.testclient import TestClient
import pytest

from api_node.main import app

client = TestClient(app)


def test_arc_settlement_route_nominal_dry_run():
    import uuid
    unique_hash = f"0xabc123{uuid.uuid4().hex}"
    payload = {
        "recipient_address": "0x1234567890abcdef1234567890abcdef12345678",
        "amount_usdc": "10.50",
        "block_hash": unique_hash,
        "nonce": 1,
    }
    response = client.post("/api/v1/settlement/arc", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SETTLEMENT_COMMITTED_DRY_RUN"
    assert data["chain"] == "Circle Arc Mainnet"
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


def test_arc_settlement_route_duplicate_request_idempotency():
    """Verify duplicate settlement requests are detected and safely deduplicated."""
    import uuid
    unique_hash = f"0xdeadbeef{uuid.uuid4().hex}"
    payload = {
        "recipient_address": "0x1234567890abcdef1234567890abcdef12345678",
        "amount_usdc": "50.00",
        "block_hash": unique_hash,
        "nonce": 99,
    }
    # Initial request
    res1 = client.post("/api/v1/settlement/arc", json=payload)
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["action"] == "COMMITTED_NEW"
    key1 = data1["idempotency"]["idempotency_key"]

    # Duplicate retry request
    res2 = client.post("/api/v1/settlement/arc", json=payload)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["action"] == "ALREADY_COMMITTED_IDEMPOTENT_RETRY"
    key2 = data2["idempotency"]["idempotency_key"]

    # Verify keys match and payload is identical (zero duplicate mutation)
    assert key1 == key2
    assert data1["settlement"] == data2["settlement"]


def test_arc_settlement_route_payload_mismatch_returns_409_conflict():
    """Verify reusing an intent key with a conflicting amount returns HTTP 409 Conflict."""
    import uuid
    unique_hash = f"0xconflictpayloadhash{uuid.uuid4().hex}"
    payload1 = {
        "recipient_address": "0x1234567890abcdef1234567890abcdef12345678",
        "amount_usdc": "25.00",
        "block_hash": unique_hash,
        "nonce": 10,
    }
    res1 = client.post("/api/v1/settlement/arc", json=payload1)
    assert res1.status_code == 200

    # Conflicting amount on same intent
    payload_conflicting = {
        "recipient_address": "0x1234567890abcdef1234567890abcdef12345678",
        "amount_usdc": "100.00",
        "block_hash": unique_hash,
        "nonce": 10,
    }
    res2 = client.post("/api/v1/settlement/arc", json=payload_conflicting)
    assert res2.status_code == 409
    assert "Conflict" in res2.json()["detail"]
    assert "previously bound" in res2.json()["detail"]
