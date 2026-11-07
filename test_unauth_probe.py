#!/usr/bin/env python3
"""Verify an mTLS client without a valid Ed25519 proof is denied."""

import json
import socket
import ssl
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))
from qf_ipc_auth import auth_message, parse_challenge, read_line

TARGET_HOST = "127.0.0.1"
TARGET_PORT = 9444
CLIENT_ID = "qfx-yoga-local"
MTLS_DIR = Path.home() / ".local/share/quantum-flex-mycelium/mtls"
CA_CERT = MTLS_DIR / "ca.crt"
CLIENT_CERT = MTLS_DIR / "client.crt"
CLIENT_KEY = MTLS_DIR / "client.key"


def main() -> int:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    try:
        context.load_verify_locations(cafile=str(CA_CERT))
        context.load_cert_chain(certfile=str(CLIENT_CERT), keyfile=str(CLIENT_KEY))
        with socket.create_connection((TARGET_HOST, TARGET_PORT), timeout=5) as raw:
            with context.wrap_socket(raw, server_hostname=TARGET_HOST) as peer:
                peer.settimeout(5)
                challenge = parse_challenge(peer)
                message = auth_message(CLIENT_ID, challenge, int(time.time()))
                invalid_proof = {
                    "message": message,
                    "signature": "00" * 64,
                }
                peer.sendall(
                    json.dumps(
                        invalid_proof,
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=True,
                    ).encode("ascii") + b"\n"
                )
                response = read_line(peer).decode("ascii", errors="strict")
                if response != "ERR|AUTHENTICATION_FAILED|INVALID_SIGNATURE_OR_UNKNOWN_CLIENT":
                    print(f"[FAIL] Expected explicit invalid-signature denial, received {response!r}")
                    return 1
                print("[PASS] Invalid Ed25519 proof received explicit authentication denial.")
                try:
                    trailing = peer.recv(1024)
                except (ConnectionResetError, ssl.SSLError):
                    trailing = b""
                if trailing:
                    print(f"[FAIL] Server returned data after denial: {trailing!r}")
                    return 1
                print("[PASS] No authenticated operation acknowledgement followed the denial.")
                return 0
    except (OSError, ssl.SSLError, ValueError, ConnectionError) as exc:
        print(f"[FAIL] Probe could not verify an explicit authentication denial: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
