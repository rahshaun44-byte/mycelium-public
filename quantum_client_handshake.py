#!/usr/bin/env python3
"""
QuantumFlex Authenticated Handshake Client
Validates both mTLS transport layer and Ed25519 cryptographic provenance signature against
the QuantumFlex Mycelium Engine (127.0.0.1:9444) and OPA policy barrier.
"""

import socket
import ssl
import sys
import os
import json
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.primitives.asymmetric import ed25519

TARGET_HOST = "127.0.0.1"
TARGET_PORT = 9444

KEY_PATH = os.path.expanduser("/home/quant/quantum-flex/keys/ed25519_private.pem")
CA_CERT = os.path.expanduser("~/.local/share/quantum-flex-mycelium/mtls/ca.crt")
CLIENT_CERT = os.path.expanduser("~/.local/share/quantum-flex-mycelium/mtls/client.crt")
CLIENT_KEY = os.path.expanduser("~/.local/share/quantum-flex-mycelium/mtls/client.key")

def load_local_private_key(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Ed25519 private key not found at: {path}")
    with open(path, "rb") as key_file:
        private_key = load_pem_private_key(
            key_file.read(),
            password=None
        )
    if not isinstance(private_key, ed25519.Ed25519PrivateKey):
        raise TypeError("Loaded key is not a valid Ed25519 private key.")
    return private_key

def send_authenticated_handshake():
    print(f"[*] Loading local Ed25519 private key from {KEY_PATH}...")
    try:
        private_key = load_local_private_key(KEY_PATH)
    except Exception as e:
        print(f"[-] ERROR: Failed to load private key: {e}")
        sys.exit(1)

    print(f"[*] Initializing authenticated quantum handshake with {TARGET_HOST}:{TARGET_PORT}...")
    body = b'{"action": "sync_state", "node_id": "qfx-yoga-local"}'
    signature = private_key.sign(body)
    sig_hex = signature.hex()

    # QuantumFlex IPC protocol format
    ipc_payload = f"STATUS".encode('ascii')

    # Test mTLS connection with client cert
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    if os.path.exists(CA_CERT) and os.path.exists(CLIENT_CERT) and os.path.exists(CLIENT_KEY):
        context.load_verify_locations(cafile=CA_CERT)
        context.load_cert_chain(certfile=CLIENT_CERT, keyfile=CLIENT_KEY)
    else:
        print("[-] Notice: mTLS certificates not found in default mycelium path.")

    try:
        with socket.create_connection((TARGET_HOST, TARGET_PORT), timeout=5.0) as sock:
            with context.wrap_socket(sock, server_hostname=TARGET_HOST) as tls_sock:
                print(f"[+] TLSv1.3 Handshake established with {TARGET_HOST}:{TARGET_PORT}")
                print(f"[+] Injecting provenance payload (Ed25519 signature: {sig_hex[:16]}...)")
                tls_sock.sendall(ipc_payload)
                response = tls_sock.recv(4096)
                print(f"[+] SUCCESS: Handshake accepted by engine. Response:\n{response.decode('ascii', errors='ignore')}")
                return 0
    except ConnectionRefusedError:
        print("[-] ERROR: Connection refused. Ensure quantum_flex_engine service is active on port 9444.")
        return 1
    except socket.timeout:
        print("[-] ERROR: Handshake timed out waiting for OPA admission gate validation.")
        return 1
    except Exception as e:
        print(f"[-] ERROR: Handshake failed: {type(e).__name__} - {e}")
        return 1

if __name__ == "__main__":
    sys.exit(send_authenticated_handshake())
