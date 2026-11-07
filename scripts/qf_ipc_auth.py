"""Ed25519 challenge-response for the QuantumFlex mTLS IPC protocol."""

from __future__ import annotations

import json
import re
import socket
import time
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

PROTOCOL = "qf-ipc-auth-v1"
MAX_LINE_BYTES = 4096
AUTH_ACK = "ACK|AUTHENTICATED|v1"
_NONCE_RE = re.compile(r"^[0-9a-f]{64}$")
_CLIENT_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class AuthenticationError(ConnectionError):
    """The peer explicitly rejected the IPC authentication exchange."""


def read_line(sock: socket.socket, max_bytes: int = MAX_LINE_BYTES) -> bytes:
    data = bytearray()
    while len(data) < max_bytes:
        block = sock.recv(1)
        if not block:
            raise ConnectionError("IPC peer closed before completing a line")
        if block == b"\n":
            return bytes(data)
        data.extend(block)
    raise ConnectionError("IPC line exceeded the configured limit")


def parse_challenge(sock: socket.socket) -> dict[str, Any]:
    try:
        line = read_line(sock).decode("ascii")
        prefix, version, timestamp_text, nonce = line.split("|")
        timestamp = int(timestamp_text)
    except (UnicodeError, ValueError) as exc:
        raise ConnectionError("IPC peer returned a malformed authentication challenge") from exc

    if prefix != "QF_AUTH_CHALLENGE" or version != "v1" or not _NONCE_RE.fullmatch(nonce):
        raise ConnectionError("IPC peer returned an unsupported authentication challenge")
    if abs(int(time.time()) - timestamp) > 60:
        raise ConnectionError("IPC authentication challenge is expired")
    return {"server_timestamp": timestamp, "nonce": nonce}


def auth_message(client_id: str, challenge: dict[str, Any], client_timestamp: int | None = None) -> dict[str, Any]:
    if not _CLIENT_ID_RE.fullmatch(client_id) or client_id in {".", ".."}:
        raise ValueError("Invalid QuantumFlex client identity")
    return {
        "client_id": client_id,
        "client_timestamp": int(time.time()) if client_timestamp is None else client_timestamp,
        "nonce": challenge["nonce"],
        "protocol": PROTOCOL,
        "server_timestamp": challenge["server_timestamp"],
    }


def canonical_message(message: dict[str, Any]) -> bytes:
    return json.dumps(message, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def signed_auth_request(
    private_key: Ed25519PrivateKey,
    client_id: str,
    challenge: dict[str, Any],
    client_timestamp: int | None = None,
) -> bytes:
    message = auth_message(client_id, challenge, client_timestamp)
    envelope = {"message": message, "signature": private_key.sign(canonical_message(message)).hex()}
    return json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii") + b"\n"


def authenticate(
    sock: socket.socket,
    signing_key_path: str | Path,
    client_id: str,
) -> dict[str, Any]:
    challenge = parse_challenge(sock)
    try:
        private_key = serialization.load_pem_private_key(
            Path(signing_key_path).read_bytes(),
            password=None,
        )
    except (OSError, ValueError, TypeError) as exc:
        raise AuthenticationError("Unable to load the configured Ed25519 signing key") from exc
    if not isinstance(private_key, Ed25519PrivateKey):
        raise AuthenticationError("Configured IPC signing key is not Ed25519")

    sock.sendall(signed_auth_request(private_key, client_id, challenge))
    response = read_line(sock).decode("ascii", errors="strict")
    if response != AUTH_ACK:
        if response.startswith("ERR|AUTHENTICATION_FAILED|"):
            raise AuthenticationError(response)
        raise ConnectionError("IPC peer returned an unexpected authentication response")
    return challenge
