#!/usr/bin/env python3
import os
import sys
import socket
import sqlite3
import hashlib
import ssl
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))
from qf_ipc_auth import authenticate
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.primitives.asymmetric import ed25519

# Paths and Target Constants
KEY_PATH = os.path.expanduser("~/quantum-flex/keys/ed25519_private.pem")
DB_PATH = os.path.expanduser("~/quantum-flex/data/ledger.db")
TARGET_HOST = "127.0.0.1"
TARGET_PORT = 9444
MTLS_DIR = Path.home() / ".local/share/quantum-flex-mycelium/mtls"
CA_CERT = MTLS_DIR / "ca.crt"
CLIENT_CERT = MTLS_DIR / "client.crt"
CLIENT_TLS_KEY = MTLS_DIR / "client.key"
CLIENT_ID = os.environ.get("QF_IPC_CLIENT_ID", "qfx-yoga-local")

def step_1_verify_and_sign():
    print("\n[--- STEP 1: Ed25519 Key Validation & Payload Signing ---]")
    if not os.path.exists(KEY_PATH):
        print(f"[-] ERROR: Private key missing at {KEY_PATH}")
        return None, None
        
    with open(KEY_PATH, "rb") as f:
        private_key = load_pem_private_key(f.read(), password=None)
        
    if not isinstance(private_key, ed25519.Ed25519PrivateKey):
        print("[-] ERROR: Loaded key is not a valid Ed25519 private key.")
        return None, None
        
    body = b'{"action": "sync_state", "node": "qfx-yoga-local"}'
    signature = private_key.sign(body)
    print("[+] Local Ed25519 key is valid; the IPC helper signs and transmits the server challenge.")
    return signature, body

def step_2_test_loopback_handshake(signature, body):
    print("\n[--- STEP 2: TLS + Ed25519 Challenge-Response Test ---]")
    del signature, body
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.load_verify_locations(cafile=str(CA_CERT))
    context.load_cert_chain(certfile=str(CLIENT_CERT), keyfile=str(CLIENT_TLS_KEY))
    try:
        with socket.create_connection((TARGET_HOST, TARGET_PORT), timeout=5) as raw:
            with context.wrap_socket(raw, server_hostname=TARGET_HOST) as peer:
                peer.settimeout(5)
                authenticate(peer, KEY_PATH, CLIENT_ID)
                peer.sendall(b"STATUS\n")
                response = peer.recv(1024).decode("ascii", errors="strict").strip()
                if response != "ACK|ACTIVE":
                    print(f"[-] Engine rejected authenticated status request: {response}")
                    return False
                print("[+] TLS and Ed25519 challenge-response accepted.")
                print(f"[+] Authenticated engine response: {response}")
                return True
    except (OSError, ssl.SSLError, ValueError) as e:
        print(f"[-] Authenticated handshake failed: {type(e).__name__}: {e}")
        return False

def step_3_verify_ledger_hash_chain():
    print("\n[--- STEP 3: SQLite Ledger Hash Chain Verification ---]")
    if not os.path.exists(DB_PATH):
        print(f"[!] NOTICE: Ledger database not found at {DB_PATH} (Skipping ledger check).")
        return
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT id, timestamp, event_data, prev_hash, current_hash FROM audit_runs ORDER BY id ASC;")
        rows = cursor.fetchall()
    except Exception as e:
        print(f"[-] ERROR querying ledger table: {e}")
        conn.close()
        return
        
    if not rows:
        print("[!] Ledger table is empty. No hash chain to verify.")
        conn.close()
        return
        
    expected_prev_hash = "0" * 64
    chain_intact = True
    
    for row in rows:
        row_id, timestamp, event_data, prev_hash, stored_hash = row
        if prev_hash != expected_prev_hash:
            print(f"[-] BROKEN LINK at Entry ID {row_id}")
            chain_intact = False
            break
            
        hasher = hashlib.sha256()
        record_payload = f"{row_id}|{timestamp}|{event_data}|{prev_hash}"
        hasher.update(record_payload.encode('utf-8'))
        calculated_hash = hasher.hexdigest()
        
        if calculated_hash != stored_hash:
            print(f"[-] HASH MISMATCH at Entry ID {row_id}")
            chain_intact = False
            break
            
        expected_prev_hash = stored_hash
        
    if chain_intact:
        print(f"[+] SUCCESS: SQLite ledger hash chain across {len(rows)} entries is 100% intact.")
    else:
        print("[-] CRITICAL: Ledger integrity failure detected!")
        
    conn.close()

if __name__ == "__main__":
    print("=== QUANTUMFLEX LOCAL MASTER AUDIT & EXECUTION SCRIPT ===")
    sig, payload = step_1_verify_and_sign()
    if sig and not step_2_test_loopback_handshake(sig, payload):
        sys.exit(1)
    step_3_verify_ledger_hash_chain()
    print("\n=== EXECUTION COMPLETE ===")
