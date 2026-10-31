"""
Hardware-anchored operator authority for QF-Bot.

A device holds mutation authority only if it signs the request with a private key
that never leaves its secure element (Android Keystore / StrongBox on the Pixel).
The server pins each enrolled device's public key under QF_DEVICE_KEYS_DIR
(default ~/.config/quantumflex/devices/<device_id>.pem).

Nothing a caller can merely assert grants authority: not the source IP (tailscale
serve delivers every tailnet peer as 127.0.0.1), not X-Forwarded-For, not model /
serial headers, not a shared key shipped inside the client. No enrolled key means
no device can mutate through the API — fail closed.

Signed request headers:
  X-QF-Device     device id (file stem of the pinned key)
  X-QF-Timestamp  unix seconds
  X-QF-Nonce      random, single use, 16-128 chars [A-Za-z0-9_-]
  X-QF-Signature  base64 DER ECDSA P-256 / SHA-256 over canonical_message()
"""

import base64
import hashlib
import os
import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

MAX_SKEW_SECONDS = 60
_DEVICE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_NONCE_RE = re.compile(r"^[A-Za-z0-9_-]{16,128}$")

_seen_nonces: Dict[str, float] = {}
_nonce_lock = threading.Lock()


def keys_dir() -> Path:
    return Path(os.environ.get(
        "QF_DEVICE_KEYS_DIR",
        str(Path.home() / ".config" / "quantumflex" / "devices"),
    ))


def canonical_message(method: str, path_and_query: str, timestamp: str, nonce: str, body: bytes) -> bytes:
    return "\n".join([
        "QF1",
        method.upper(),
        path_and_query,
        timestamp,
        nonce,
        hashlib.sha256(body).hexdigest(),
    ]).encode("utf-8")


def _load_device_key(device_id: str) -> Optional[ec.EllipticCurvePublicKey]:
    if not _DEVICE_ID_RE.match(device_id):
        return None
    path = keys_dir() / f"{device_id}.pem"
    try:
        key = serialization.load_pem_public_key(path.read_bytes())
    except (OSError, ValueError):
        return None
    if not isinstance(key, ec.EllipticCurvePublicKey) or not isinstance(key.curve, ec.SECP256R1):
        return None
    return key


def _consume_nonce(nonce: str, now: float) -> bool:
    """
    Atomically consumes a nonce with in-process thread serialization, cross-worker
    SQLite WAL concurrency safety, and fail-closed error handling.
    """
    db_path = keys_dir() / "consumed_nonces.sqlite"
    with _nonce_lock:
        for n, expiry in list(_seen_nonces.items()):
            if expiry < now:
                del _seen_nonces[n]
        cache_key = f"{db_path}:{nonce}"
        if cache_key in _seen_nonces:
            return False

        conn: Optional[sqlite3.Connection] = None
        try:
            keys_dir().mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(db_path), timeout=30.0, isolation_level=None)
            conn.execute("PRAGMA busy_timeout=30000")
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS consumed_nonces (
                    nonce TEXT PRIMARY KEY,
                    expires_at REAL NOT NULL
                )
                """
            )
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute("DELETE FROM consumed_nonces WHERE expires_at < ?", (now,))
                conn.execute(
                    "INSERT INTO consumed_nonces (nonce, expires_at) VALUES (?, ?)",
                    (nonce, now + 2 * MAX_SKEW_SECONDS),
                )
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            _seen_nonces[cache_key] = now + 2 * MAX_SKEW_SECONDS
            return True
        except sqlite3.IntegrityError:
            return False
        except (sqlite3.Error, OSError):
            return False
        finally:
            if conn is not None:
                conn.close()


def verify(method: str, path_and_query: str, headers: Dict[str, str], body: bytes,
           now: Optional[float] = None) -> Optional[str]:
    """Returns the enrolled device id if the request carries a valid signature, else None."""
    device_id = headers.get("x-qf-device", "")
    timestamp = headers.get("x-qf-timestamp", "")
    nonce = headers.get("x-qf-nonce", "")
    signature_b64 = headers.get("x-qf-signature", "")
    if not (device_id and timestamp and nonce and signature_b64):
        return None
    if not _NONCE_RE.match(nonce) or not timestamp.isdigit():
        return None

    now = time.time() if now is None else now
    if abs(now - int(timestamp)) > MAX_SKEW_SECONDS:
        return None

    key = _load_device_key(device_id)
    if key is None:
        return None
    try:
        signature = base64.b64decode(signature_b64, validate=True)
        key.verify(signature, canonical_message(method, path_and_query, timestamp, nonce, body),
                   ec.ECDSA(hashes.SHA256()))
    except (InvalidSignature, ValueError):
        return None

    # Only a verified request may burn a nonce, so garbage cannot fill the cache.
    if not _consume_nonce(nonce, now):
        return None
    return device_id


def observer_authority(reason: str) -> Dict[str, Any]:
    return {
        "node_id": "observer",
        "model": "Unverified device",
        "role": "FIELD_OBSERVER",
        "authority": "None (no valid hardware-key signature)",
        "can_mutate": False,
        "policy": "SECURITY_TELEMETRY_ONLY",
        "message": reason,
    }


def operator_authority(device_id: str) -> Dict[str, Any]:
    return {
        "node_id": device_id,
        "model": device_id,
        "role": "CHIEF_ARCHITECT",
        "authority": "Enrolled hardware-backed key (signature verified)",
        "can_mutate": True,
        "policy": "FULL_AUTHORITY",
        "message": "Request signed by an enrolled device key.",
    }
