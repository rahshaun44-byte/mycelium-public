#!/usr/bin/env python3
"""Thin mTLS transport for the Quantum Flex engine's IPC socket.

Carries no Shamir crypto logic. Secret-bearing commands must arrive through
stdin, so share values are not passed in process arguments. Only known response
codes are printed. This does not guarantee complete Python/TLS memory erasure.

Usage:
  qf_ipc_client.py --host 127.0.0.1 --port 9444 \
      --cert client.crt --key client.key --ca ca.crt \
      --stdin --expect-response 'ACK|NODE_UNLOCKED'
"""
import argparse
import ssl
import socket
import sys

MAX_INPUT_BYTES = 65536
ACK_CODES = {'ACK|HARVESTER_KEY_SET', 'ACK|EVIDENCE_ACCEPTED',
             'ACK|REPLICATION_ACCEPTED', 'ACK|ENROLL_ACCEPTED',
             'ACK|GOSSUB_ACCEPTED', 'ACK|GENESIS_SECURED', 'ACK|NODE_UNLOCKED',
             'ACK|ACTIVE'}
ERROR_CODES = {'ERR|UNAUTHORIZED_HARVESTER_MUTATION', 'ERR|HARVESTER_KEY_REJECTED',
               'ERR|EVIDENCE_REJECTED', 'ERR|MALFORMED_TELEMETRY',
               'ERR|REPLICATION_REJECTED', 'ERR|ENROLL_REJECTED',
               'ERR|MALFORMED_ENROLL', 'ERR|GOSSUB_REJECTED', 'ERR|UNKNOWN_COMMAND',
               'ERR|UNAUTHORIZED_OPERATOR', 'ERR|GENESIS_NOT_ALLOWED', 'ERR|INIT_FAILED',
               'ERR|UNLOCK_LOCKED_OUT', 'ERR|UNLOCK_FAILED',
               'ERR|NODE_UNINITIALIZED_CALL_INIT', 'ERR|NODE_LOCKED', 'ERR|INVALID_STATE'}


def transmit(payload, host, port, cert, key, ca, expected) -> int:
    """Send a checked bytes-like request; the caller owns payload memory wiping."""
    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        context.load_verify_locations(cafile=ca)
        context.load_cert_chain(certfile=cert, keyfile=key)

        with socket.create_connection((host, port), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=host) as tls_sock:
                tls_sock.sendall(memoryview(payload))
                response_bytes = bytearray()
                while len(response_bytes) <= 4096:
                    block = tls_sock.recv(min(1024, 4097 - len(response_bytes)))
                    if not block:
                        break
                    response_bytes.extend(block)
                if response_bytes.endswith(b'\n'):
                    del response_bytes[-1:]
                    if response_bytes.endswith(b'\r'):
                        del response_bytes[-1:]
                response = response_bytes.decode('ascii')

        if response in ERROR_CODES:
            print(response)
            return 1
        if response not in ACK_CODES:
            print('ERR|INVALID_RESPONSE')
            return 1
        if expected is not None and response != expected:
            print('ERR|UNEXPECTED_RESPONSE')
            return 1
        print(response)
        return 0
    except (OSError, UnicodeError):
        print('[!] IPC transport failed.', file=sys.stderr)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(prog='qf_ipc_client.py', description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--cert", required=True, help="Client certificate PEM")
    parser.add_argument("--key", required=True, help="Client private key PEM")
    parser.add_argument("--ca", required=True, help="Root CA PEM used to verify the server")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--stdin', action='store_true', help='Read one protocol line from protected stdin')
    source.add_argument('--interactive-unlock', action='store_true', help=argparse.SUPPRESS)
    source.add_argument('--line', help='Non-secret protocol command only; never INIT, UNLOCK or TELEMETRY')
    parser.add_argument('--expect-response', choices=sorted(ACK_CODES), help='Require this exact acknowledgement')
    args = parser.parse_args()

    if args.interactive_unlock:
        print('[!] Use the checked recovery helper; direct interactive unlock is disabled.', file=sys.stderr)
        return 2

    if args.line is not None and args.line.startswith(('INIT|', 'UNLOCK|', 'TELEMETRY|')):
        print('[!] Secret-bearing commands require --stdin.', file=sys.stderr)
        return 2

    payload = bytearray()
    try:
        payload.extend(sys.stdin.buffer.read(MAX_INPUT_BYTES + 1) if args.stdin else args.line.encode('utf-8'))
        if len(payload) > MAX_INPUT_BYTES:
            print('[!] Input is too large.', file=sys.stderr)
            return 2
        if payload.endswith(b'\n'):
            del payload[-1:]
            if payload.endswith(b'\r'):
                del payload[-1:]
        if not payload or any(c in payload for c in (0, 10, 13)):
            print('[!] Expected one nonempty protocol line.', file=sys.stderr)
            return 2
        expected = args.expect_response
        if expected is None:
            if payload.startswith(b'UNLOCK|'):
                expected = 'ACK|NODE_UNLOCKED'
            elif payload.startswith(b'INIT|'):
                expected = 'ACK|GENESIS_SECURED'

        return transmit(payload, args.host, args.port, args.cert, args.key, args.ca, expected)
    except (OSError, UnicodeError):
        print('[!] IPC transport failed.', file=sys.stderr)
        return 1
    finally:
        payload[:] = b'\x00' * len(payload)


if __name__ == "__main__":
    sys.exit(main())
