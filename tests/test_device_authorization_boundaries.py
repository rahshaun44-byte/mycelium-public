"""Focused Adversarial Verification Suite: Device Authorization Boundaries & Replay Protection

Verifies the 8 core adversarial security properties defined in the QuantumFlex architectural review:
1. An unsigned request cannot perform a mutation (403 Forbidden).
2. A signed request with an invalid signature is rejected (403 Forbidden).
3. A signed request with a modified body is rejected (tamper detection -> 403 Forbidden).
4. A replayed request (duplicate nonce) is rejected (replay attack prevention -> 403 Forbidden).
5. An expired request (timestamp skew > 60s) is rejected (403 Forbidden).
6. An un-enrolled device key is rejected (untrusted identity -> 403 Forbidden).
7. A valid, authorized request passes the security boundary.
8. A corrupted/unavailable key directory causes a safe fail-closed denial.
"""

import base64
import os
import secrets
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from mcp_layer.qf_bot import bot_server, device_auth


@pytest.fixture
def auth_fixture(tmp_path, monkeypatch):
    """Sets up an isolated device keys directory with a valid enrolled ECDSA P-256 keypair."""
    keys_dir = tmp_path / "devices"
    keys_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("QF_DEVICE_KEYS_DIR", str(keys_dir))

    # Generate enrolled operator key (e.g. simulating Titan M2 StrongBox enrolled key)
    operator_privkey = ec.generate_private_key(ec.SECP256R1())
    operator_pubkey_pem = operator_privkey.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    device_id = "qfx-pixel-operator"
    (keys_dir / f"{device_id}.pem").write_bytes(operator_pubkey_pem)

    client = TestClient(bot_server.app)

    return {
        "client": client,
        "keys_dir": keys_dir,
        "device_id": device_id,
        "operator_privkey": operator_privkey,
    }


def make_signed_headers(device_id: str, privkey, method: str, path: str, body: bytes,
                        timestamp: int = None, nonce: str = None) -> dict:
    ts = str(int(time.time())) if timestamp is None else str(timestamp)
    n = secrets.token_hex(16) if nonce is None else nonce
    canonical = device_auth.canonical_message(method, path, ts, n, body)
    sig = privkey.sign(canonical, ec.ECDSA(hashes.SHA256()))
    return {
        "x-qf-device": device_id,
        "x-qf-timestamp": ts,
        "x-qf-nonce": n,
        "x-qf-signature": base64.b64encode(sig).decode("ascii"),
        "content-type": "application/json",
    }


# Target mutating endpoint: draft discard or service action
MUTATING_PATH = "/api/drafts/test_draft_nonexistent/discard"


def test_1_unsigned_request_cannot_perform_mutation(auth_fixture):
    """Property 1: An unsigned request receives 403 Forbidden."""
    client = auth_fixture["client"]
    res = client.post(MUTATING_PATH, json={})
    assert res.status_code == 403
    assert "SECURITY LOCKOUT" in res.json()["detail"]


def test_2_invalid_signature_is_rejected(auth_fixture):
    """Property 2: A signed request with a corrupted signature is rejected."""
    client = auth_fixture["client"]
    device_id = auth_fixture["device_id"]
    privkey = auth_fixture["operator_privkey"]

    headers = make_signed_headers(device_id, privkey, "POST", MUTATING_PATH, b"{}")
    # Corrupt the signature bytes
    sig_raw = base64.b64decode(headers["x-qf-signature"])
    corrupted_sig = bytes([sig_raw[0] ^ 0xFF]) + sig_raw[1:]
    headers["x-qf-signature"] = base64.b64encode(corrupted_sig).decode("ascii")

    res = client.post(MUTATING_PATH, json={}, headers=headers)
    assert res.status_code == 403
    assert "SECURITY LOCKOUT" in res.json()["detail"]


def test_3_modified_body_is_rejected(auth_fixture):
    """Property 3: Modifying request body after signing breaks canonical hash -> 403."""
    client = auth_fixture["client"]
    device_id = auth_fixture["device_id"]
    privkey = auth_fixture["operator_privkey"]

    original_body = b'{"action":"discard","target":"draft_1"}'
    tampered_body = b'{"action":"discard","target":"draft_ADMIN_OVERRIDE"}'

    headers = make_signed_headers(device_id, privkey, "POST", MUTATING_PATH, original_body)
    # Send tampered body with original headers
    res = client.post(MUTATING_PATH, content=tampered_body, headers=headers)
    assert res.status_code == 403
    assert "SECURITY LOCKOUT" in res.json()["detail"]


def test_4_replayed_request_is_rejected(auth_fixture):
    """Property 4: A replayed request (identical nonce) is rejected on second presentation."""
    client = auth_fixture["client"]
    device_id = auth_fixture["device_id"]
    privkey = auth_fixture["operator_privkey"]

    headers = make_signed_headers(device_id, privkey, "POST", MUTATING_PATH, b"{}")

    # First presentation passes auth (returns 404 because draft doesn't exist, proving gate passed)
    res1 = client.post(MUTATING_PATH, content=b"{}", headers=headers)
    assert res1.status_code == 404, f"First request should pass auth gate, got {res1.status_code}"

    # Replay identical request with identical nonce
    res2 = client.post(MUTATING_PATH, content=b"{}", headers=headers)
    assert res2.status_code == 403, f"Replayed request must be rejected with 403, got {res2.status_code}"
    assert "SECURITY LOCKOUT" in res2.json()["detail"]


def test_5_expired_request_is_rejected(auth_fixture):
    """Property 5: A request with timestamp skewed > 60s is rejected."""
    client = auth_fixture["client"]
    device_id = auth_fixture["device_id"]
    privkey = auth_fixture["operator_privkey"]

    # 120 seconds in the past
    stale_ts = int(time.time()) - 120
    headers = make_signed_headers(device_id, privkey, "POST", MUTATING_PATH, b"{}", timestamp=stale_ts)

    res = client.post(MUTATING_PATH, content=b"{}", headers=headers)
    assert res.status_code == 403
    assert "SECURITY LOCKOUT" in res.json()["detail"]


def test_6_unenrolled_device_is_rejected(auth_fixture):
    """Property 6: A valid signature from a key not enrolled on the server is rejected."""
    client = auth_fixture["client"]
    rogue_privkey = ec.generate_private_key(ec.SECP256R1())
    rogue_device_id = "rogue-untrusted-phone"

    headers = make_signed_headers(rogue_device_id, rogue_privkey, "POST", MUTATING_PATH, b"{}")

    res = client.post(MUTATING_PATH, content=b"{}", headers=headers)
    assert res.status_code == 403
    assert "SECURITY LOCKOUT" in res.json()["detail"]


def test_7_valid_authorized_request_succeeds(auth_fixture):
    """Property 7: A validly signed request from an enrolled device passes the gate."""
    client = auth_fixture["client"]
    device_id = auth_fixture["device_id"]
    privkey = auth_fixture["operator_privkey"]

    headers = make_signed_headers(device_id, privkey, "POST", MUTATING_PATH, b"{}")

    res = client.post(MUTATING_PATH, content=b"{}", headers=headers)
    # The gate is passed; endpoint logic executes and returns 404 for nonexistent draft
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_8_unavailable_keys_directory_fails_closed(auth_fixture, monkeypatch):
    """Property 8: If keys directory is missing or unreadable, fails closed to 403."""
    client = auth_fixture["client"]
    device_id = auth_fixture["device_id"]
    privkey = auth_fixture["operator_privkey"]

    headers = make_signed_headers(device_id, privkey, "POST", MUTATING_PATH, b"{}")

    # Point to nonexistent directory
    monkeypatch.setenv("QF_DEVICE_KEYS_DIR", "/tmp/nonexistent_keys_dir_qf_99999")

    res = client.post(MUTATING_PATH, content=b"{}", headers=headers)
    assert res.status_code == 403
    assert "SECURITY LOCKOUT" in res.json()["detail"]


def test_9_concurrent_nonce_replay_race_condition(auth_fixture):
    """Property 9: Submitting the identical signed request concurrently across 10 threads admits exactly 1."""
    import concurrent.futures
    client = auth_fixture["client"]
    device_id = auth_fixture["device_id"]
    privkey = auth_fixture["operator_privkey"]

    headers = make_signed_headers(device_id, privkey, "POST", MUTATING_PATH, b"{}")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(client.post, MUTATING_PATH, content=b"{}", headers=dict(headers)) for _ in range(10)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result().status_code)

    # Exactly one request must pass the gate (yielding 404 for nonexistent draft)
    # The remaining 9 must be rejected with 403 Forbidden
    success_count = results.count(404)
    denied_count = results.count(403)
    assert success_count == 1, f"Expected exactly 1 request to pass, but {success_count} passed: {results}"
    assert denied_count == 9, f"Expected exactly 9 requests to be rejected with 403, but {denied_count} were: {results}"


def test_10_restart_persistence_preserves_nonce_rejection(auth_fixture):
    """Property 10: Nonces consumed before a simulated worker restart remain rejected."""
    client = auth_fixture["client"]
    device_id = auth_fixture["device_id"]
    privkey = auth_fixture["operator_privkey"]

    headers = make_signed_headers(device_id, privkey, "POST", MUTATING_PATH, b"{}")

    # First presentation consumes the nonce and persists to SQLite journal
    res1 = client.post(MUTATING_PATH, content=b"{}", headers=headers)
    assert res1.status_code == 404

    # Simulate worker restart by wiping in-memory dictionary
    device_auth._seen_nonces.clear()

    # Create new fresh client simulating new worker process
    new_client = TestClient(bot_server.app)

    # Replayed presentation must still be rejected from the SQLite persistent journal
    res2 = new_client.post(MUTATING_PATH, content=b"{}", headers=headers)
    assert res2.status_code == 403
    assert "SECURITY LOCKOUT" in res2.json()["detail"]

