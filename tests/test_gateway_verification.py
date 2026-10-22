#!/usr/bin/env python3
import requests
import json
from cryptography.hazmat.primitives.asymmetric import ed25519

import os
import pytest

GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://127.0.0.1:8080/api/v1/telemetry/submit")

def is_gateway_reachable():
    try:
        r = requests.get(GATEWAY_URL.replace("/api/v1/telemetry/submit", "/status"), timeout=1.0)
        return r.status_code < 500
    except Exception:
        return False

@pytest.mark.skipif(not is_gateway_reachable(), reason="Remote gateway endpoint unreachable")
def test_gateway():
    print("[*] Testing Layer 2 / Layer 3 Ingestion Gateway Verification Pipeline...")

    # 1. Generate real Ed25519 keypair
    priv_key = ed25519.Ed25519PrivateKey.generate()
    pub_key = priv_key.public_key()
    pub_hex = pub_key.public_bytes_raw().hex()
    node_id = f"qf-alpha-{pub_hex[:8]}"

    seq = 101
    timestamp = 1788065000000
    valid_payload = json.dumps({"bssid": "AA:BB:CC:00:00:00", "rssi": -55, "channel": 6})
    
    # Sign deterministic message: "node_id:seq:payload"
    message_bytes = f"{node_id}:{seq}:{valid_payload}".encode("utf-8")
    valid_sig_hex = priv_key.sign(message_bytes).hex()

    # --- TEST 1: Valid Signature (Expected: 200 OK) ---
    req_valid = {
        "node_id": node_id,
        "seq": seq,
        "timestamp": timestamp,
        "payload": valid_payload,
        "signature": valid_sig_hex,
        "public_key": pub_hex
    }
    r1 = requests.post(GATEWAY_URL, json=req_valid)
    print(f"  [Test 1] Valid Ed25519 Signature -> HTTP {r1.status_code}: {r1.text}")
    assert r1.status_code == 200, f"Expected 200, got {r1.status_code}"
    receipt = r1.json()
    assert receipt["status"] == "VERIFIED"
    assert receipt["trust_score"] == 100

    # --- TEST 2: Tampered / Invalid Signature (Expected: 401 Unauthorized) ---
    req_tampered = dict(req_valid)
    req_tampered["signature"] = ("00" * 64) # Invalid signature
    r2 = requests.post(GATEWAY_URL, json=req_tampered)
    print(f"  [Test 2] Tampered Signature -> HTTP {r2.status_code}: {r2.text}")
    assert r2.status_code == 401, f"Expected 401, got {r2.status_code}"

    # --- TEST 3: Privacy Opt-Out Flag (_optout) (Expected: 403 Forbidden) ---
    optout_payload = json.dumps({"ssid": "NeighborWiFi_optout", "bssid": "11:22:33:00:00:00"})
    optout_msg = f"{node_id}:{seq+1}:{optout_payload}".encode("utf-8")
    optout_sig = priv_key.sign(optout_msg).hex()

    req_optout = {
        "node_id": node_id,
        "seq": seq + 1,
        "timestamp": timestamp,
        "payload": optout_payload,
        "signature": optout_sig,
        "public_key": pub_hex
    }
    r3 = requests.post(GATEWAY_URL, json=req_optout)
    print(f"  [Test 3] Opt-Out Tagged Frame (_optout) -> HTTP {r3.status_code}: {r3.text}")
    assert r3.status_code == 403, f"Expected 403, got {r3.status_code}"

    # --- TEST 4: Privacy Nomap Flag (_nomap) (Expected: 403 Forbidden) ---
    nomap_payload = json.dumps({"ssid": "CoffeeShop_nomap", "bssid": "44:55:66:00:00:00"})
    nomap_msg = f"{node_id}:{seq+2}:{nomap_payload}".encode("utf-8")
    nomap_sig = priv_key.sign(nomap_msg).hex()

    req_nomap = {
        "node_id": node_id,
        "seq": seq + 2,
        "timestamp": timestamp,
        "payload": nomap_payload,
        "signature": nomap_sig,
        "public_key": pub_hex
    }
    r4 = requests.post(GATEWAY_URL, json=req_nomap)
    print(f"  [Test 4] Nomap Tagged Frame (_nomap) -> HTTP {r4.status_code}: {r4.text}")
    assert r4.status_code == 403, f"Expected 403, got {r4.status_code}"

    print("\n[+] ALL 4 GATEWAY DPI & CRYPTOGRAPHIC TESTS PASSED WITH 100% SUCCESS!")

if __name__ == "__main__":
    test_gateway()
