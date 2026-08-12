#!/usr/bin/env python3
"""Thin mTLS transport for the Quantum Flex engine's IPC socket.

Carries no crypto logic of its own -- shard generation/recovery and INIT|/
UNLOCK|/TELEMETRY| line construction happen in tools/genesis_tool.cpp (built
as qf_genesis_tool) so the Shamir GF(256) math only ever exists once, in the
engine's own implementation. This script just opens a client-cert TLS
connection, sends one line, and prints the ACK|/ERR| response.

Usage:
  qf_ipc_client.py --host 127.0.0.1 --port 9444 \
      --cert client.crt --key client.key --ca ca.crt \
      --line "INIT|1:aa..,2:bb..,3:cc.."
"""
import argparse
import ssl
import socket
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--cert", required=True, help="Client certificate PEM")
    parser.add_argument("--key", required=True, help="Client private key PEM")
    parser.add_argument("--ca", required=True, help="Root CA PEM used to verify the server")
    parser.add_argument("--line", required=True, help="Raw protocol line to send, e.g. 'INIT|1:..,2:..'")
    args = parser.parse_args()

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.load_verify_locations(cafile=args.ca)
    context.load_cert_chain(certfile=args.cert, keyfile=args.key)

    with socket.create_connection((args.host, args.port), timeout=10) as sock:
        with context.wrap_socket(sock, server_hostname=args.host) as tls_sock:
            tls_sock.sendall(args.line.encode("utf-8"))
            response = tls_sock.recv(4096).decode("utf-8", errors="replace")

    print(response.strip())
    return 0 if response.startswith("ACK|") else 1


if __name__ == "__main__":
    sys.exit(main())
