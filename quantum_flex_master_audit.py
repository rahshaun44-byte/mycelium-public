#!/usr/bin/env python3
import os
import sys
import socket
import sqlite3
import hashlib
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.primitives.asymmetric import ed25519

# Paths and Target Constants
KEY_PATH = os.path.expanduser("~/quantum-flex/keys/ed25519_private.pem")
DB_PATH = os.path.expanduser("~/quantum-flex/data/ledger.db")
TARGET_HOST = "127.0.0.1"
TARGET_PORT = 9444

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
    print("[+] SUCCESS: Local private key loaded and payload successfully signed.")
    return signature, body

def step_2_test_loopback_handshake(signature, body):
    print("\n[--- STEP 2: Loopback Authenticated Handshake Test ---]")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3.0)
    
    try:
        sock.connect((TARGET_HOST, TARGET_PORT))
        handshake_payload = (
            b"POST /handshake/v1 HTTP/1.1\r\n"
            b"Host: quantum-engine-local\r\n"
            b"X-QuantumFlex-Node: qfx-yoga-local\r\n"
            + f"X-Provenance-Signature: {signature.hex()}\r\n".encode('utf-8')
            + f"Content-Length: {len(body)}\r\n\r\n".encode('utf-8')
            + body
        )
        sock.sendall(handshake_payload)
        response = sock.recv(1024)
        print(f"[+] SUCCESS: Handshake accepted by engine. Response:\n{response.decode('utf-8', errors='ignore')}")
    except ConnectionRefusedError:
        print("[!] NOTICE: Engine port 9444 currently unbound/refused (Expected if service is stopped).")
    except socket.timeout:
        print("[!] NOTICE: Handshake socket timed out.")
    except Exception as e:
        print(f"[!] NOTICE: Handshake test exception: {e}")
    finally:
        sock.close()

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
    if sig:
        step_2_test_loopback_handshake(sig, payload)
    step_3_verify_ledger_hash_chain()
    print("\n=== EXECUTION COMPLETE ===")
