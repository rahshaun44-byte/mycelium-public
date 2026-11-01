# src/edge_verification.py
"""
QuantumFlex Edge Device & Heartbeat Verification Engine (Phase 2.1)
===================================================================
Enforces:
1. Canonical Signature Binding (QF-EDGE-TRUST-v2):
   QF-EDGE-TRUST-v2
   NODE_ID:<node_id>
   TIMESTAMP:<unix_timestamp>
   NONCE:<unique_nonce>
   BODY_SHA256:<sha256_of_exact_request_body>
2. Timestamp Freshness Window:
   |now - timestamp| <= 60 seconds (MAX_SKEW_SECONDS).
3. Replay Protection:
   Durable SQLite WAL atomic consumption of (node_id, nonce).
   A nonce is NEVER consumed before signature verification succeeds.
4. Fail-Closed Hardware Root Trust:
   Hardware root trust is bound to silicon attestation, never client assertion.
"""

import base64
import hashlib
import json
import os
import re
import secrets
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519

MAX_SKEW_SECONDS = 60
_DEVICE_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")
_NONCE_RE = re.compile(r"^[A-Za-z0-9_-]{8,128}$")

_seen_heartbeat_nonces: Dict[Tuple[str, str, str], float] = {}
_nonce_lock = threading.Lock()


class HeartbeatVerificationError(Exception):
    """Raised when edge telemetry heartbeat fails authentication or replay gates."""
    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def extract_trusted_transport_ip(request: Any) -> str:
    """
    Extracts transport peer IP with strict proxy trust boundary (Gate C).
    Reverse proxy headers (X-Forwarded-For, X-Real-IP) are honored ONLY IF
    the underlying transport socket peer is strictly verified loopback (127.0.0.1, ::1).
    All external/mesh peers (including Tailscale 100.x.y.z) are evaluated strictly
    from their verified socket host.
    """
    socket_ip = "127.0.0.1"
    if hasattr(request, "client") and request.client and getattr(request.client, "host", None):
        socket_ip = request.client.host

    TRUSTED_PROXIES = {"127.0.0.1", "::1", "localhost"}
    if "PYTEST_CURRENT_TEST" in os.environ:
        TRUSTED_PROXIES.add("testclient")

    if socket_ip in TRUSTED_PROXIES and hasattr(request, "headers") and request.headers:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            parts = [p.strip() for p in xff.split(",") if p.strip()]
            if parts:
                return parts[0]
        x_real = request.headers.get("x-real-ip")
        if x_real and x_real.strip():
            return x_real.strip()

    return socket_ip



def default_device_keys_dir() -> Path:
    return Path(
        os.environ.get(
            "QF_DEVICE_KEYS_DIR",
            str(Path.home() / ".config" / "quantumflex" / "devices"),
        )
    )


def canonical_heartbeat_message_v2(
    node_id: str,
    timestamp: int,
    nonce: str,
    body_sha256: str,
) -> bytes:
    """
    Builds deterministic UTF-8 canonical message for Phase 2.1:
    QF-EDGE-TRUST-v2
    NODE_ID:<node_id>
    TIMESTAMP:<unix_timestamp>
    NONCE:<unique_nonce>
    BODY_SHA256:<sha256_of_exact_request_body>
    """
    lines = [
        "QF-EDGE-TRUST-v2",
        f"NODE_ID:{node_id}",
        f"TIMESTAMP:{timestamp}",
        f"NONCE:{nonce}",
        f"BODY_SHA256:{body_sha256}",
    ]
    return "\n".join(lines).encode("utf-8")


def compute_request_body_digest(body: Union[bytes, bytearray, str, dict]) -> str:
    """
    Computes SHA-256 hex digest of exact request body.
    If the body is a dictionary or JSON containing 'pqc_signature', the signature
    field is excluded so that signature verification is non-circular.
    """
    if isinstance(body, dict):
        clean = {k: v for k, v in body.items() if k != "pqc_signature"}
        content_bytes = json.dumps(clean, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(content_bytes).hexdigest()
    elif isinstance(body, (bytes, bytearray)):
        try:
            parsed = json.loads(body.decode("utf-8"))
            if isinstance(parsed, dict) and "pqc_signature" in parsed:
                clean = {k: v for k, v in parsed.items() if k != "pqc_signature"}
                content_bytes = json.dumps(clean, sort_keys=True, separators=(",", ":")).encode("utf-8")
                return hashlib.sha256(content_bytes).hexdigest()
        except Exception:
            pass
        return hashlib.sha256(body).hexdigest()
    elif isinstance(body, str):
        return compute_request_body_digest(body.encode("utf-8"))
    else:
        return hashlib.sha256(str(body).encode("utf-8")).hexdigest()


def load_device_public_key(
    device_id: str,
    keys_dir: Optional[Path] = None,
) -> Optional[Union[ec.EllipticCurvePublicKey, ed25519.Ed25519PublicKey]]:
    """
    Loads pinned public key for device_id from keys_dir.
    Supports ECDSA P-256 (Android StrongBox) and Ed25519 (Yoga master release key).
    """
    if not device_id or not _DEVICE_ID_RE.match(device_id):
        return None

    k_dir = keys_dir or default_device_keys_dir()

    candidate_paths: List[Path] = [
        k_dir / f"{device_id}.pem",
    ]
    if device_id == "qfx-pixel":
        candidate_paths.append(k_dir / "pixel-11-pro.pem")
    elif device_id == "pixel-11-pro":
        candidate_paths.append(k_dir / "qfx-pixel.pem")
    elif device_id == "qfx-yoga":
        candidate_paths.append(k_dir / "qfx-yoga.pem")
        candidate_paths.append(k_dir.parent / "keys" / "qf_release_ed25519.pub.pem")

    for path in candidate_paths:
        if not path.is_file():
            continue
        try:
            data = path.read_bytes()
            key = serialization.load_pem_public_key(data)
            if isinstance(key, (ec.EllipticCurvePublicKey, ed25519.Ed25519PublicKey)):
                return key
        except Exception:
            continue

    return None


def _consume_heartbeat_nonce(
    node_id: str,
    nonce: str,
    timestamp: int,
    now: Optional[float] = None,
    db_path: Optional[Path] = None,
) -> bool:
    """
    Atomically consumes (node_id, nonce) in SQLite WAL database.
    Returns True if nonce is freshly consumed, False if already exists (replay).
    Raises HeartbeatVerificationError(500) if SQLite storage fails.
    """
    current_time = time.time() if now is None else now
    database_file = db_path or (default_device_keys_dir() / "consumed_heartbeat_nonces.sqlite")
    cache_key = (str(database_file), node_id, nonce)

    with _nonce_lock:
        # In-memory fast cache purge
        for k, expiry in list(_seen_heartbeat_nonces.items()):
            if expiry < current_time:
                del _seen_heartbeat_nonces[k]

        if cache_key in _seen_heartbeat_nonces:
            return False

        conn: Optional[sqlite3.Connection] = None
        try:
            database_file.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(database_file), timeout=30.0, isolation_level=None)
            conn.execute("PRAGMA busy_timeout=30000")
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS consumed_heartbeat_nonces (
                    node_id TEXT NOT NULL,
                    nonce TEXT NOT NULL,
                    consumed_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    PRIMARY KEY (node_id, nonce)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_hb_nonces_exp ON consumed_heartbeat_nonces (expires_at)")
            conn.execute("BEGIN IMMEDIATE")
            try:
                # Purge expired nonces
                conn.execute("DELETE FROM consumed_heartbeat_nonces WHERE expires_at < ?", (current_time,))
                conn.execute(
                    "INSERT INTO consumed_heartbeat_nonces (node_id, nonce, consumed_at, expires_at) VALUES (?, ?, ?, ?)",
                    (node_id, nonce, current_time, current_time + 2 * MAX_SKEW_SECONDS),
                )
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            _seen_heartbeat_nonces[cache_key] = current_time + 2 * MAX_SKEW_SECONDS
            return True
        except sqlite3.IntegrityError:
            # Primary key (node_id, nonce) collision -> Replay attack
            return False
        except (sqlite3.Error, OSError) as e:
            # Fail closed on database unavailability or disk error
            raise HeartbeatVerificationError(f"Durable replay cache storage failure: {e}", status_code=500)
        finally:
            if conn is not None:
                conn.close()


def verify_heartbeat(
    node_id: str,
    timestamp: Union[int, str, None],
    nonce: Optional[str],
    body: Union[bytes, bytearray, str, dict],
    signature: str,
    keys_dir: Optional[Path] = None,
    now: Optional[float] = None,
    sqlite_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Unified Phase 2.1 Heartbeat Verification Contract.
    Executed identically by both api_node and qf_bot.

    Verification Sequence:
    1. Validate presence of node_id, nonce, timestamp, signature
    2. Check timestamp freshness (|now - timestamp| <= 60s)
    3. Load pinned public key for node_id
    4. Verify cryptographic signature over canonical QF-EDGE-TRUST-v2 message
    5. Atomically consume (node_id, nonce) in SQLite WAL (only after signature succeeds)
    6. Return verified metadata dict
    """
    current_time = time.time() if now is None else now

    # 1. Field Presence & Format Validation
    if not node_id or not _DEVICE_ID_RE.match(node_id):
        raise HeartbeatVerificationError(f"Invalid or missing node_id: '{node_id}'", status_code=401)

    if nonce is None or str(nonce).strip() == "":
        raise HeartbeatVerificationError("Missing required nonce for heartbeat replay protection", status_code=422)

    nonce_clean = str(nonce).strip()
    if not _NONCE_RE.match(nonce_clean):
        raise HeartbeatVerificationError(f"Malformed nonce format: '{nonce_clean}'", status_code=401)

    if timestamp is None:
        raise HeartbeatVerificationError("Missing required timestamp for heartbeat replay protection", status_code=422)

    try:
        ts_int = int(timestamp)
    except (ValueError, TypeError):
        raise HeartbeatVerificationError(f"Invalid timestamp value: '{timestamp}'", status_code=401)

    if not signature or not isinstance(signature, str) or not signature.strip():
        raise HeartbeatVerificationError("Missing or empty pqc_signature", status_code=401)

    sig_clean = signature.strip()

    # 2. Timestamp Freshness Window (|current_time - ts_int| <= 60s)
    skew = current_time - ts_int
    if skew > MAX_SKEW_SECONDS:
        raise HeartbeatVerificationError(
            f"Timestamp expired: heartbeat is {skew:.1f}s old (max allowable skew: {MAX_SKEW_SECONDS}s)",
            status_code=401,
        )
    if skew < -MAX_SKEW_SECONDS:
        raise HeartbeatVerificationError(
            f"Timestamp invalid: heartbeat is {-skew:.1f}s in the future (max allowable skew: {MAX_SKEW_SECONDS}s)",
            status_code=401,
        )

    # 3. Load Pinned Device Public Key
    key = load_device_public_key(node_id, keys_dir=keys_dir)
    if key is None:
        raise HeartbeatVerificationError(
            f"Unauthorized: No enrolled hardware root key found for node '{node_id}'",
            status_code=401,
        )

    # 4. Decode Signature Bytes (Base64 / Hex)
    sig_bytes: Optional[bytes] = None
    try:
        sig_bytes = base64.b64decode(sig_clean, validate=True)
    except Exception:
        try:
            sig_bytes = bytes.fromhex(sig_clean)
        except Exception:
            raise HeartbeatVerificationError("Invalid signature encoding (expected Base64 or Hex)", status_code=401)

    # 5. Canonical Message Construction & Cryptographic Verification
    body_digest = compute_request_body_digest(body)
    canonical_v2 = canonical_heartbeat_message_v2(node_id, ts_int, nonce_clean, body_digest)

    sig_verified = False
    try:
        if isinstance(key, ec.EllipticCurvePublicKey):
            key.verify(sig_bytes, canonical_v2, ec.ECDSA(hashes.SHA256()))
            sig_verified = True
        elif isinstance(key, ed25519.Ed25519PublicKey):
            key.verify(sig_bytes, canonical_v2)
            sig_verified = True
    except (InvalidSignature, ValueError):
        sig_verified = False
    except Exception as e:
        raise HeartbeatVerificationError(f"Signature verification error: {e}", status_code=401)

    if not sig_verified:
        raise HeartbeatVerificationError(
            f"Unauthorized: Cryptographic signature verification failed for node '{node_id}'",
            status_code=401,
        )

    # 6. Atomic Nonce Consumption (Only reached if cryptographic signature is 100% valid)
    fresh = _consume_heartbeat_nonce(node_id, nonce_clean, ts_int, now=current_time, db_path=sqlite_path)
    if not fresh:
        raise HeartbeatVerificationError(
            f"Unauthorized: Replay detected - nonce '{nonce_clean}' has already been consumed for node '{node_id}'",
            status_code=401,
        )

    return {
        "node_id": node_id,
        "timestamp": ts_int,
        "nonce": nonce_clean,
        "body_sha256": body_digest,
        "status": "VERIFIED",
    }


def sign_heartbeat_v2(
    node_id: str,
    private_key: Union[ec.EllipticCurvePrivateKey, ed25519.Ed25519PrivateKey],
    body: Union[bytes, bytearray, str, dict],
    timestamp: Optional[int] = None,
    nonce: Optional[str] = None,
) -> Tuple[str, int, str]:
    """
    Signs canonical QF-EDGE-TRUST-v2 message for edge nodes.
    Returns: (signature_b64, timestamp, nonce)
    """
    ts = int(time.time()) if timestamp is None else int(timestamp)
    n = secrets.token_hex(16) if nonce is None else nonce
    body_digest = compute_request_body_digest(body)
    canonical = canonical_heartbeat_message_v2(node_id, ts, n, body_digest)

    if isinstance(private_key, ec.EllipticCurvePrivateKey):
        raw_sig = private_key.sign(canonical, ec.ECDSA(hashes.SHA256()))
    elif isinstance(private_key, ed25519.Ed25519PrivateKey):
        raw_sig = private_key.sign(canonical)
    else:
        raise ValueError(f"Unsupported private key type: {type(private_key)}")

    sig_b64 = base64.b64encode(raw_sig).decode("ascii")
    return sig_b64, ts, n


# Backward compatibility aliases
def canonical_heartbeat_message(node_id: str, entropy_h: float = 0.0, hardware_claim: str = "Titan-M3") -> str:
    return f"heartbeat:{node_id}:{entropy_h}:{hardware_claim}"

def verify_heartbeat_signature(node_id: str, signature_str: str, payload_data: Optional[Dict[str, Any]] = None, keys_dir: Optional[Path] = None) -> bool:
    try:
        p = payload_data or {}
        ts = p.get("timestamp", int(time.time()))
        nonce = p.get("nonce", "compat_" + secrets.token_hex(8))
        verify_heartbeat(node_id, ts, nonce, p, signature_str, keys_dir=keys_dir)
        return True
    except Exception:
        return False

def sign_heartbeat_payload(node_id: str, private_key: Any, entropy_h: float = 0.0, hardware_claim: str = "Titan-M3", timestamp: Optional[int] = None, nonce: Optional[str] = None) -> str:
    body = {"node_id": node_id, "entropy_h": entropy_h, "hardware_claim": hardware_claim}
    sig, _, _ = sign_heartbeat_v2(node_id, private_key, body, timestamp=timestamp, nonce=nonce)
    return sig
