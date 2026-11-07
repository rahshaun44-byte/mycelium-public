#!/usr/bin/env python3
"""Verify the engine's TLS and Ed25519 challenge-response admission."""

import os
import socket
import ssl
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))
from qf_ipc_auth import authenticate

TARGET_HOST = "127.0.0.1"
TARGET_PORT = 9444
CLIENT_ID = os.environ.get("QF_IPC_CLIENT_ID", "qfx-yoga-local")
KEY_PATH = os.environ.get(
    "QF_IPC_SIGNING_KEY",
    str(Path.home() / "quantum-flex/keys/ed25519_private.pem"),
)
MTLS_DIR = Path.home() / ".local/share/quantum-flex-mycelium/mtls"
CA_CERT = MTLS_DIR / "ca.crt"
CLIENT_CERT = MTLS_DIR / "client.crt"
CLIENT_KEY = MTLS_DIR / "client.key"


def send_authenticated_status() -> int:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.load_verify_locations(cafile=str(CA_CERT))
    context.load_cert_chain(certfile=str(CLIENT_CERT), keyfile=str(CLIENT_KEY))

    try:
        with socket.create_connection((TARGET_HOST, TARGET_PORT), timeout=5.0) as sock:
            with context.wrap_socket(sock, server_hostname=TARGET_HOST) as tls_sock:
                tls_sock.settimeout(5.0)
                authenticate(tls_sock, KEY_PATH, CLIENT_ID)
                tls_sock.sendall(b"STATUS\n")
                response = tls_sock.recv(4096).decode("ascii", errors="strict").strip()
                if response != "ACK|ACTIVE":
                    print(f"[-] Engine rejected status request: {response}", file=sys.stderr)
                    return 1
                print("[+] TLSv1.3 and Ed25519 challenge-response accepted.")
                print(f"[+] Authenticated status response: {response}")
                return 0
    except (OSError, ssl.SSLError, ValueError) as exc:
        print(f"[-] Authenticated engine request failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(send_authenticated_status())
