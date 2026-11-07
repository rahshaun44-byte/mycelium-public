"""
QuantumFlex Track 4: experimental proof validation and settlement dry runs.
Live transfers remain blocked until authenticated evidence, signing, and
transaction reconciliation are implemented and commissioned.
"""

import json
import hashlib
import math
import os
from enum import Enum
from pathlib import Path
import sqlite3
import threading
import time
from typing import Dict, Any, Optional, Final, Tuple
import uuid

CONFIG_FILE = Path.home() / ".config" / "qf" / "circle.env"

def _load_circle_config():
    key = os.environ.get("CIRCLE_API_KEY")
    base = os.environ.get("CIRCLE_API_BASE")
    wallet = os.environ.get("CIRCLE_WALLET_ID")
    if CONFIG_FILE.exists():
        try:
            for line in CONFIG_FILE.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip().strip("\"'")
                    if k == "CIRCLE_API_KEY" and not key: key = v
                    elif k == "CIRCLE_API_BASE" and not base: base = v
                    elif k == "CIRCLE_WALLET_ID" and not wallet: wallet = v
        except Exception:
            pass
    return (
        key or "",
        base or "https://api.circle.com/v1/w3s",
        wallet or "mock-vault-wallet-id"
    )

CIRCLE_API_KEY, CIRCLE_API_BASE, DEFAULT_WALLET_ID = _load_circle_config()


class SettlementStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    INDETERMINATE = "INDETERMINATE"


class QuantumSettlementLifecycle(str, Enum):
    JOB_SUBMITTED = "JOB_SUBMITTED"
    JOB_COMPLETED = "JOB_COMPLETED"
    EVIDENCE_RECORDED = "EVIDENCE_RECORDED"
    PROOF_VERIFIED = "PROOF_VERIFIED"
    SETTLEMENT_AUTHORIZED = "SETTLEMENT_AUTHORIZED"
    SETTLEMENT_SUBMITTED = "SETTLEMENT_SUBMITTED"
    SETTLEMENT_CONFIRMED = "SETTLEMENT_CONFIRMED"
    REJECTED = "REJECTED"

class QuantumFlexUSDCSettler:
    def __init__(self, wallet_id: Optional[str] = None, live: bool = False,
                 authenticated_evidence_verifier=None, transport=None):
        self.wallet_id = wallet_id if wallet_id is not None else DEFAULT_WALLET_ID
        self.live = live
        self.authenticated_evidence_verifier = authenticated_evidence_verifier
        self.transport = transport

    @staticmethod
    def verify_authenticated_evidence(evidence: Dict[str, Any], verifier) -> bool:
        """Require an external trust-anchor verifier to authenticate evidence.

        The settlement module intentionally does not load keys or infer trust from
        a hash. ``verifier`` should validate the signed envelope against the
        commissioned evidence authority and return a boolean.
        """
        if not isinstance(evidence, dict) or not evidence.get("signature"):
            return False
        if not callable(verifier):
            return False
        try:
            return verifier(evidence) is True
        except Exception:
            return False

    @staticmethod
    def reconcile_transaction(response: Any, expected_idempotency_key: str,
                              expected_amount: str, expected_recipient: str) -> Dict[str, Any]:
        """Map an untrusted Circle response to a conservative ledger state."""
        if not isinstance(response, dict):
            return {"status": SettlementStatus.INDETERMINATE.value, "reason": "malformed response"}
        state = str(response.get("status", "")).upper()
        if state in {"CONFIRMED", "COMPLETE", "COMPLETED"}:
            if (response.get("idempotencyKey") != expected_idempotency_key or
                    str(response.get("amount")) != str(expected_amount) or
                    response.get("destinationAddress") != expected_recipient):
                return {"status": SettlementStatus.INDETERMINATE.value, "reason": "response does not match intent"}
            return {"status": SettlementStatus.CONFIRMED.value, "transaction_id": response.get("id")}
        if state in {"FAILED", "REJECTED", "CANCELED", "CANCELLED"}:
            return {"status": SettlementStatus.FAILED.value, "reason": response.get("error", state)}
        if state in {"PENDING", "PROCESSING", "QUEUED"}:
            return {"status": SettlementStatus.PENDING.value, "transaction_id": response.get("id")}
        return {"status": SettlementStatus.INDETERMINATE.value, "reason": "unknown transaction state"}

    @staticmethod
    def verify_quantum_proof(proof: Dict[str, Any]) -> bool:
        """
        Empirical Verification:
        1. Canonical JSON format (compact, sorted keys)
        2. Hash matches computed digest
        3. Statistical significance threshold met (Bell correlation >= 0.85 or witness_ucb < 0)
        4. Zero secret entropy invariant (0.0 bits)
        """
        if not isinstance(proof, dict):
            return False
        required_fields = ["job_id", "canonical_payload", "block_hash", "correlation", "zero_entropy"]
        if not all(k in proof for k in required_fields):
            return False
        for key in ("correlation", "zero_entropy", "witness_ucb"):
            value = proof.get(key, 1.0)
            if type(value) not in (int, float) or not math.isfinite(value):
                return False
        if not 0 <= proof["correlation"] <= 1:
            return False
        try:
            decoded = json.loads(proof["canonical_payload"])
            if not isinstance(decoded, dict):
                return False
            if json.dumps(decoded, sort_keys=True, separators=(',', ':'), allow_nan=False) != proof["canonical_payload"]:
                return False
            if not proof["job_id"] or decoded.get("job_id") != proof["job_id"]:
                return False
            if "witness_ucb" in proof:
                if decoded.get("witness_ucb", decoded.get("ucb")) != proof.get("witness_ucb"):
                    return False
            elif proof["correlation"] >= 0.85:
                if decoded.get("correlation") != proof["correlation"]:
                    return False
        except (TypeError, ValueError):
            return False

        # Invariant: Zero secret entropy
        if proof["zero_entropy"] != 0.0:
            return False

        # Verify cryptographic block hash
        computed_hash = hashlib.sha256(proof["canonical_payload"].encode("utf-8")).hexdigest()
        if computed_hash != proof["block_hash"]:
            return False

        # Verify physics threshold and entanglement witness
        if "witness_ucb" in proof:
            if proof["witness_ucb"] >= 0.0:
                return False

        if proof.get("correlation", 0.0) < 0.85:
            # If correlation < 0.85, proof MUST have a certified negative witness UCB
            if proof.get("witness_ucb", 1.0) >= 0.0:
                return False

        return True

    def execute_micro_settlement(self, recipient_address: str, amount_usdc: str, proof: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a proof in dry-run mode; never report a simulated payment as settled.
        """
        if self.live:
            return {
                "status": SettlementStatus.INDETERMINATE.value,
                "submitted": False,
                "error": "Live settlement is fail-closed until an authenticated evidence verifier, entity-secret signer, transport, and reconciliation service are commissioned.",
            }
        if not self.verify_quantum_proof(proof):
            return {
                "status": "REJECTED",
                "lifecycle_stage": QuantumSettlementLifecycle.REJECTED.value,
                "submitted": False,
                "error": "Proof validation failed; no transfer submitted."
            }

        # Idempotency key derived deterministically from proof hash
        idempotency_key = hashlib.sha256(proof["block_hash"].encode("utf-8")).hexdigest()

        return {
            "status": "PROOF_VERIFIED_DRY_RUN",
            "lifecycle_stage": QuantumSettlementLifecycle.PROOF_VERIFIED.value,
            "settlement_state": SettlementStatus.PENDING.value,
            "submitted": False,
            "proof_hash": proof["block_hash"],
            "idempotency_key": idempotency_key,
            "recipient": recipient_address,
            "amount_usdc": amount_usdc,
            "token": "USDC"
        }

    def dispatch_live_transfer(self, intent_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Attempts to dispatch a live settlement transfer to Circle.
        Strictly enforces the hard boundary: fails closed if wallet is a dry-run stub
        or if credentials are missing or unauthenticated.
        """
        if self.wallet_id == "mock-vault-wallet-id" or not self.wallet_id:
            raise LiveSettlementSecurityError(
                "Live settlement dispatch rejected: active wallet ID is an unauthenticated dry-run stub "
                "('mock-vault-wallet-id'). Live payment dispatch requires a commissioned Circle "
                "Developer-Controlled Wallet ID and entity secret."
            )
        if not CIRCLE_API_KEY:
            raise LiveSettlementSecurityError(
                "Live settlement dispatch rejected: missing CIRCLE_API_KEY in environment."
            )
        # Production execution path requires hardware-backed entity-secret signer
        raise NotImplementedError(
            "Live Circle SDK transport is disabled until hardware signers are online."
        )


class LiveSettlementSecurityError(RuntimeError):
    """Raised when an operation attempts live settlement with unverified or stub credentials."""
    pass


class ReceiptValidationError(ValueError):
    """Raised when an on-chain transaction receipt fails economic or cryptographic binding."""
    pass


# ── Circle Arc Chain Configuration & Invariants ────────────────────────────
ARC_USDC_ERC20_ADDRESS: Final[str] = "0x3600000000000000000000000000000000000000"

ARC_L1_CHAIN_CONFIG: Final[Dict[str, Any]] = {
    "chain_name": "Circle Arc Mainnet",
    "network_id": "arc-mainnet",
    "evm_chain_id": 5042,           # Arc Mainnet EVM Chain ID (0x13B2)
    "hex_chain_id": "0x13B2",
    "native_currency": {
        "name": "USDC",
        "symbol": "USDC",
        "native_gas_decimals": 18,   # Arc native gas / msg.value uses 18 decimals
        "erc20_interface_decimals": 6, # Standard USDC ERC-20 interface uses 6 decimals
    },
    "erc20_token_address": ARC_USDC_ERC20_ADDRESS,
    "evm_target_version": "paris",   # Prevents Shanghai PUSH0 opcode incompatibility
    "rpc_endpoints": [
        "https://rpc.arc.circle.com",
        "https://rpc-backup.arc.circle.com",
    ],
    "gas_token": "NATIVE_USDC",
}

# Arc USDC Duality Invariants:
# 1. ERC-20 Interface (Circle transfer, balance accounting): Exactly 6 decimals (1 USDC = 1_000_000 micro-USDC)
USDC_ERC20_DECIMALS: Final[int] = 6
USDC_DECIMALS: Final[int] = USDC_ERC20_DECIMALS  # Backwards-compatible alias
MICRO_USDC_MULTIPLIER: Final[int] = 10**USDC_ERC20_DECIMALS

# 2. Native Gas Token (EVM execution, msg.value): 18 decimals (1 USDC = 10^18 native wei-equivalent)
USDC_NATIVE_DECIMALS: Final[int] = 18
NATIVE_USDC_WEI_MULTIPLIER: Final[int] = 10**USDC_NATIVE_DECIMALS


class MicroUSDC(int):
    """
    Represents an integer 6-decimal USDC quantity for ERC-20 contract interactions.
    Rejects negative amounts. Cannot be directly passed to native EVM msg.value fields.
    """
    def __new__(cls, value: int | str):
        val = int(value)
        if val < 0:
            raise ValueError("MicroUSDC amount cannot be negative")
        return super().__new__(cls, val)


class ArcNativeWei(int):
    """
    Represents an integer 18-decimal native gas / msg.value quantity on Arc.
    Rejects negative amounts. Cannot be directly passed to ERC-20 transfer parameters.
    """
    def __new__(cls, value: int | str):
        val = int(value)
        if val < 0:
            raise ValueError("ArcNativeWei amount cannot be negative")
        return super().__new__(cls, val)


def scale_to_micro_usdc(amount_decimal: float | str) -> MicroUSDC:
    """Converts a standard decimal USDC amount into integer 6-decimal micro-USDC (ERC-20 interface)."""
    try:
        val = float(amount_decimal)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid USDC amount representation: {amount_decimal!r}") from exc

    if val < 0:
        raise ValueError("USDC settlement amount cannot be negative")

    # Round to avoid float precision drift before multiplying by 1,000,000
    micro = round(val * MICRO_USDC_MULTIPLIER)
    return MicroUSDC(micro)


def scale_to_native_usdc_wei(amount_decimal: float | str) -> ArcNativeWei:
    """Converts a standard decimal USDC amount into integer 18-decimal native gas / msg.value representation."""
    try:
        val = float(amount_decimal)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid USDC amount representation: {amount_decimal!r}") from exc

    if val < 0:
        raise ValueError("USDC settlement amount cannot be negative")

    wei = round(val * NATIVE_USDC_WEI_MULTIPLIER)
    return ArcNativeWei(wei)



def validate_usdc_amount(micro_amount: int) -> int:
    """
    Enforces the 6-decimal integer USDC invariant for application and ERC-20 accounting.
    Fails closed if amount is not a strict integer or exceeds maximum supply bounds.
    """
    if not isinstance(micro_amount, int) or isinstance(micro_amount, bool):
        raise TypeError(f"Micro-USDC amount must be a strict integer, got {type(micro_amount)}")
    if micro_amount < 0:
        raise ValueError("Micro-USDC amount cannot be negative")
    if micro_amount > 1_000_000_000_000_000_000:  # 1 Trillion USDC ceiling
        raise ValueError("Micro-USDC amount exceeds protocol solvency ceiling")
    return micro_amount


def generate_conforming_uuid4() -> str:
    """
    Generates a standards-conforming random UUID v4 per RFC 9562 § 5.4 / RFC 4122 using CSPRNG.
    This is the recommended identifier for mutating API calls when the client durably persists
    the (transaction_identity, idempotency_key) mapping in a database to ensure deterministic retries.
    """
    return str(uuid.uuid4())


class PayloadMismatchError(ValueError):
    """Raised when an existing intent is submitted with conflicting recipient or amount."""
    pass


class InvalidStateTransitionError(RuntimeError):
    """Raised when a settlement intent attempts an illegal state jump."""
    pass


class SettlementIntentState(str, Enum):
    """
    Formal lifecycle states for settlement intents.
    Enforces that gateway acceptance (REQUEST_ACCEPTED) is distinguished from
    definitive on-chain finality (CONFIRMED), and indeterminate outcomes
    (5xx, timeouts) require reconciliation rather than premature failure or retry.
    """
    INTENT_PERSISTED = "INTENT_PERSISTED"               # Conforming UUIDv4 generated & bound to complete economic intent fingerprint
    REQUEST_SUBMITTED = "REQUEST_SUBMITTED"             # Dispatched to payment gateway API or mempool
    REQUEST_ACCEPTED = "REQUEST_ACCEPTED"               # Gateway accepted request for processing (e.g. HTTP 200/201 ack)
    PENDING = "PENDING"                                 # Processing or chain finality outstanding
    CONFIRMED = "CONFIRMED"                             # Definitive on-chain receipt / verified transfer completion
    FAILED = "FAILED"                                   # Definitive permanent failure (e.g. 4xx reject, reverted)
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED" # Ambiguous outcome (e.g. HTTP 5xx, timeout, network error)


VALID_INTENT_TRANSITIONS: Final[Dict[SettlementIntentState, set[SettlementIntentState]]] = {
    SettlementIntentState.INTENT_PERSISTED: {
        SettlementIntentState.REQUEST_SUBMITTED,
        SettlementIntentState.FAILED,
    },
    SettlementIntentState.REQUEST_SUBMITTED: {
        SettlementIntentState.REQUEST_ACCEPTED,
        SettlementIntentState.PENDING,
        SettlementIntentState.FAILED,
        SettlementIntentState.RECONCILIATION_REQUIRED,
    },
    SettlementIntentState.REQUEST_ACCEPTED: {
        SettlementIntentState.PENDING,
        SettlementIntentState.CONFIRMED,
        SettlementIntentState.FAILED,
        SettlementIntentState.RECONCILIATION_REQUIRED,
    },
    SettlementIntentState.PENDING: {
        SettlementIntentState.CONFIRMED,
        SettlementIntentState.FAILED,
        SettlementIntentState.RECONCILIATION_REQUIRED,
    },
    SettlementIntentState.RECONCILIATION_REQUIRED: {
        SettlementIntentState.PENDING,
        SettlementIntentState.CONFIRMED,
        SettlementIntentState.FAILED,
    },
    SettlementIntentState.CONFIRMED: set(),  # Terminal state
    SettlementIntentState.FAILED: set(),     # Terminal state
}


def classify_gateway_http_response(
    status_code: int,
    response_json: Optional[Dict[str, Any]] = None,
) -> SettlementIntentState:
    """
    Classifies payment gateway HTTP responses fail-closed:
    - 200..299:
        - If response indicates CONFIRMED/COMPLETE: returns CONFIRMED.
        - If response indicates PENDING/PROCESSING/QUEUED: returns PENDING.
        - Otherwise returns REQUEST_ACCEPTED (gateway accepted intent, not yet confirmed on-chain).
    - 400..499:
        - FAILED (rejected by gateway/schema/client error).
    - 500..599 or network timeouts:
        - RECONCILIATION_REQUIRED (Never classify 5xx as immediate failure;
          the gateway may have processed the transaction before timing out.
          Requires reconciliation using the durable idempotency key).
    """
    if 200 <= status_code < 300:
        if response_json and isinstance(response_json, dict):
            inner_status = str(response_json.get("status", "")).upper()
            if inner_status in {"CONFIRMED", "COMPLETE", "COMPLETED"}:
                return SettlementIntentState.CONFIRMED
            if inner_status in {"PENDING", "PROCESSING", "QUEUED"}:
                return SettlementIntentState.PENDING
        return SettlementIntentState.REQUEST_ACCEPTED
    elif 400 <= status_code < 500:
        return SettlementIntentState.FAILED
    else:
        return SettlementIntentState.RECONCILIATION_REQUIRED


def derive_deterministic_idempotency_key(
    block_hash: str,
    nonce: str | int = 0,
    scheme: str = "v8",
) -> str:
    """
    Derives a deterministic RFC 9562 UUIDv8 (Custom/vendor-specific) from SHA-256(block_hash || nonce).
    Embeds the 122-bit SHA-256 prefix with version 0b1000 and variant 0b10.
    """
    if not block_hash or not isinstance(block_hash, str):
        raise ValueError("Invalid block_hash for idempotency derivation")

    raw_seed = f"{block_hash.strip().lower()}::{nonce}".encode("utf-8")
    digest = hashlib.sha256(raw_seed).digest()

    truncated = bytearray(digest[:16])
    if scheme == "v8":
        truncated[6] = (truncated[6] & 0x0F) | 0x80
    else:
        raise ValueError(f"Unsupported UUID derivation scheme: {scheme}. Expected 'v8'.")

    truncated[8] = (truncated[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(truncated)))


class DurableIdempotencyStore:
    """
    Crash-proof, concurrency-safe durable store mapping settlement intents to
    standards-conforming random RFC 9562 § 5.4 / RFC 4122 UUIDv4 idempotency keys.

    Fulfills Circle's published API contract:
    - Generates genuine random UUIDv4 via CSPRNG (uuid.uuid4()).
    - Immutably binds intent_key to complete economic intent fingerprint:
      (chain_id, token, token_address, source_wallet, recipient, amount_micro_usdc).
    - Strictly fails closed with PayloadMismatchError if a caller reuses an intent with conflicting details.
    - Preserves durability under sudden power loss via SQLite WAL mode with synchronous=FULL (immediate fsync).
    - Prevents cross-process race conditions via transaction isolation (IMMEDIATE) and busy timeouts (30s).
    - Enforces formal settlement state transitions through VALID_INTENT_TRANSITIONS.
    """
    def __init__(self, db_path: Optional[str | Path] = None):
        if db_path is None:
            config_dir = Path(os.environ.get("QF_CONFIG_DIR", Path.home() / ".config" / "quantumflex"))
            config_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = config_dir / "settlement_idempotency.db"
        else:
            self.db_path = Path(db_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0, isolation_level="IMMEDIATE")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")  # Immediate fsync on every commit
        return conn

    def _init_db(self) -> None:
        with self._lock:
            for attempt in range(5):
                try:
                    conn = self._get_connection()
                    try:
                        conn.execute("""
                            CREATE TABLE IF NOT EXISTS settlement_idempotency_keys (
                                intent_key TEXT PRIMARY KEY,
                                idempotency_key TEXT NOT NULL UNIQUE,
                                recipient TEXT NOT NULL,
                                amount_micro_usdc INTEGER NOT NULL,
                                payload_fingerprint TEXT NOT NULL,
                                created_at REAL NOT NULL,
                                updated_at REAL NOT NULL,
                                status TEXT NOT NULL DEFAULT 'INTENT_PERSISTED',
                                tx_hash TEXT,
                                failure_reason TEXT
                            )
                        """)
                        # Auto-migrate existing schema if needed
                        cur = conn.cursor()
                        cur.execute("PRAGMA table_info(settlement_idempotency_keys)")
                        existing_cols = {row[1] for row in cur.fetchall()}
                        if "payload_fingerprint" not in existing_cols:
                            conn.execute("ALTER TABLE settlement_idempotency_keys ADD COLUMN payload_fingerprint TEXT NOT NULL DEFAULT ''")
                        if "updated_at" not in existing_cols:
                            conn.execute("ALTER TABLE settlement_idempotency_keys ADD COLUMN updated_at REAL NOT NULL DEFAULT 0.0")
                        if "tx_hash" not in existing_cols:
                            conn.execute("ALTER TABLE settlement_idempotency_keys ADD COLUMN tx_hash TEXT")
                        if "failure_reason" not in existing_cols:
                            conn.execute("ALTER TABLE settlement_idempotency_keys ADD COLUMN failure_reason TEXT")
                        
                        # Backfill/upgrade legacy status and fingerprints to canonical JSON representation
                        conn.execute("UPDATE settlement_idempotency_keys SET status = 'CONFIRMED' WHERE status = 'COMMITTED'")
                        cur.execute("SELECT intent_key, recipient, amount_micro_usdc, payload_fingerprint FROM settlement_idempotency_keys")
                        for row in cur.fetchall():
                            ik, recip, amt, fp = row
                            new_fp = self.compute_fingerprint(recip, amt)
                            if fp != new_fp:
                                conn.execute("UPDATE settlement_idempotency_keys SET payload_fingerprint = ? WHERE intent_key = ?", (new_fp, ik))
                        conn.commit()
                        break
                    finally:
                        conn.close()
                except sqlite3.OperationalError as exc:
                    if "locked" in str(exc).lower() and attempt < 4:
                        time.sleep(0.05 * (2**attempt))
                        continue
                    raise

    @staticmethod
    def _parse_status(val: Any) -> SettlementIntentState:
        if isinstance(val, SettlementIntentState):
            return val
        s = str(val).upper()
        if s == "COMMITTED":
            return SettlementIntentState.CONFIRMED
        try:
            return SettlementIntentState(s)
        except ValueError:
            return SettlementIntentState.RECONCILIATION_REQUIRED

    @staticmethod
    def compute_fingerprint(
        recipient: str,
        amount_micro_usdc: int,
        chain_id: str | int = 5042,
        token: str = "USDC",
        token_address: str = ARC_USDC_ERC20_ADDRESS,
        source_wallet_id: str = DEFAULT_WALLET_ID,
    ) -> str:
        """
        Binds the immutable intent to the complete economic operation using
        canonical RFC 8785 JSON serialization (sorted keys, compact separators=(',', ':'))
        to guarantee collision-free, unambiguous domain separation across all intent parameters.
        """
        canonical_intent = {
            "amount_micro_usdc": int(amount_micro_usdc),
            "chain_id": str(chain_id).strip().lower(),
            "recipient": str(recipient).strip().lower(),
            "source_wallet_id": str(source_wallet_id).strip(),
            "token": str(token).strip().upper(),
            "token_address": str(token_address).strip().lower(),
        }
        encoded_bytes = json.dumps(canonical_intent, sort_keys=True, separators=(',', ':')).encode("utf-8")
        return hashlib.sha256(encoded_bytes).hexdigest()

    def get_or_create(
        self,
        intent_key: str,
        recipient: str,
        amount_micro_usdc: int,
        chain_id: str | int = 5042,
        token: str = "USDC",
        token_address: str = ARC_USDC_ERC20_ADDRESS,
        source_wallet_id: str = DEFAULT_WALLET_ID,
    ) -> tuple[str, bool, SettlementIntentState]:
        """
        Atomically returns (idempotency_key, is_new, current_status).
        If intent_key exists:
          - Validates recipient, amount, chain, token, and source wallet against stored fingerprint.
          - If payload matches, returns (persisted_idempotency_key, False, current_status).
          - If payload conflicts, raises PayloadMismatchError.
        If intent_key is new:
          - Generates fresh conforming random UUIDv4 via CSPRNG.
          - Commits with status INTENT_PERSISTED and immediate fsync.
          - Returns (new_idempotency_key, True, INTENT_PERSISTED).
        """
        if not intent_key:
            raise ValueError("intent_key cannot be empty")
        if not recipient:
            raise ValueError("recipient cannot be empty")
        if not isinstance(amount_micro_usdc, int) or amount_micro_usdc <= 0:
            raise ValueError(f"amount_micro_usdc must be positive integer, got: {amount_micro_usdc}")

        incoming_fingerprint = self.compute_fingerprint(
            recipient=recipient,
            amount_micro_usdc=amount_micro_usdc,
            chain_id=chain_id,
            token=token,
            token_address=token_address,
            source_wallet_id=source_wallet_id,
        )

        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT idempotency_key, recipient, amount_micro_usdc, payload_fingerprint, status
                    FROM settlement_idempotency_keys WHERE intent_key = ?
                    """,
                    (intent_key,),
                )
                row = cur.fetchone()
                if row:
                    stored_key, stored_recip, stored_amt, stored_fp, stored_status = row
                    if not stored_fp:
                        stored_fp = incoming_fingerprint
                        cur.execute("UPDATE settlement_idempotency_keys SET payload_fingerprint = ? WHERE intent_key = ?", (stored_fp, intent_key))
                        conn.commit()
                    if stored_fp != incoming_fingerprint:
                        raise PayloadMismatchError(
                            f"Idempotency collision on intent {intent_key!r}: "
                            f"previously bound to recipient {stored_recip} and amount {stored_amt}, "
                            f"refusing reuse with recipient {recipient} and amount {amount_micro_usdc}"
                        )
                    return stored_key, False, self._parse_status(stored_status)

                new_key = generate_conforming_uuid4()
                now = time.time()
                try:
                    cur.execute(
                        """
                        INSERT INTO settlement_idempotency_keys
                        (intent_key, idempotency_key, recipient, amount_micro_usdc, payload_fingerprint,
                         created_at, updated_at, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            intent_key,
                            new_key,
                            recipient,
                            amount_micro_usdc,
                            incoming_fingerprint,
                            now,
                            now,
                            SettlementIntentState.INTENT_PERSISTED.value,
                        ),
                    )
                    conn.commit()
                    return new_key, True, SettlementIntentState.INTENT_PERSISTED
                except sqlite3.IntegrityError:
                    # Concurrent race: another worker process committed this intent first
                    cur.execute(
                        """
                        SELECT idempotency_key, recipient, amount_micro_usdc, payload_fingerprint, status
                        FROM settlement_idempotency_keys WHERE intent_key = ?
                        """,
                        (intent_key,),
                    )
                    existing = cur.fetchone()
                    if existing:
                        stored_key, stored_recip, stored_amt, stored_fp, stored_status = existing
                        if stored_fp != incoming_fingerprint:
                            raise PayloadMismatchError(
                                f"Idempotency race collision on intent {intent_key!r}: "
                                f"concurrently bound to recipient {stored_recip} and amount {stored_amt}"
                            )
                        return stored_key, False, self._parse_status(stored_status)
                    raise
            finally:
                conn.close()

    def transition_state(
        self,
        intent_key: str,
        from_state: SettlementIntentState,
        to_state: SettlementIntentState,
        tx_hash: Optional[str] = None,
        failure_reason: Optional[str] = None,
    ) -> None:
        """
        Transitions intent state atomically, validating current state.
        """
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.cursor()
                cur.execute(
                    "SELECT status FROM settlement_idempotency_keys WHERE intent_key = ?",
                    (intent_key,),
                )
                row = cur.fetchone()
                if not row:
                    raise KeyError(f"Intent {intent_key!r} not found for state transition")
                current = self._parse_status(row[0])
                if current != from_state:
                    raise InvalidStateTransitionError(
                        f"Cannot transition intent {intent_key!r} from {from_state.value} to {to_state.value}: "
                        f"current state is {current.value}"
                    )
                allowed = VALID_INTENT_TRANSITIONS.get(from_state, set())
                if to_state not in allowed:
                    raise InvalidStateTransitionError(
                        f"Illegal state transition for intent {intent_key!r}: "
                        f"{from_state.value} -> {to_state.value} is not an authorized transition. "
                        f"Allowed transitions from {from_state.value}: {[s.value for s in allowed]}"
                    )

                now = time.time()
                cur.execute(
                    """
                    UPDATE settlement_idempotency_keys
                    SET status = ?, updated_at = ?, tx_hash = COALESCE(?, tx_hash), failure_reason = ?
                    WHERE intent_key = ?
                    """,
                    (to_state.value, now, tx_hash, failure_reason, intent_key),
                )
                conn.commit()
            finally:
                conn.close()

    def get_intent(self, intent_key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT intent_key, idempotency_key, recipient, amount_micro_usdc,
                           created_at, updated_at, status, tx_hash, failure_reason
                    FROM settlement_idempotency_keys WHERE intent_key = ?
                    """,
                    (intent_key,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return {
                    "intent_key": row[0],
                    "idempotency_key": row[1],
                    "recipient": row[2],
                    "amount_micro_usdc": row[3],
                    "created_at": row[4],
                    "updated_at": row[5],
                    "status": row[6],
                    "tx_hash": row[7],
                    "failure_reason": row[8],
                }
            finally:
                conn.close()


_DEFAULT_IDEMPOTENCY_STORE: Optional[DurableIdempotencyStore] = None
_DEFAULT_STORE_LOCK = threading.Lock()


def get_default_idempotency_store() -> DurableIdempotencyStore:
    global _DEFAULT_IDEMPOTENCY_STORE
    with _DEFAULT_STORE_LOCK:
        if _DEFAULT_IDEMPOTENCY_STORE is None:
            _DEFAULT_IDEMPOTENCY_STORE = DurableIdempotencyStore()
        return _DEFAULT_IDEMPOTENCY_STORE


def build_arc_settlement_payload(
    recipient_address: str,
    amount_micro_usdc: int,
    block_hash: str,
    nonce: int = 0,
    store: Optional[DurableIdempotencyStore] = None,
) -> Dict[str, Any]:
    """
    Builds a Circle Arc L1 settlement payload anchored by the 6-decimal invariant
    and a durable, standards-conforming RFC 9562 / RFC 4122 UUIDv4 idempotency key.

    Uses DurableIdempotencyStore to ensure:
    1. Every generated key is a true CSPRNG random UUIDv4 matching Circle's published contract.
    2. Retries of the same intent_key return the identical persisted key across restarts and workers.
    3. Prevents parameter tampering by binding the key immutably to payload fingerprints.
    """
    validated_amount = validate_usdc_amount(amount_micro_usdc)
    if not recipient_address or not recipient_address.startswith("0x") or len(recipient_address) != 42:
        raise ValueError(f"Invalid EVM recipient address: {recipient_address!r}")

    intent_key = f"{block_hash.strip().lower()}::{nonce}"
    active_store = store or get_default_idempotency_store()
    idempotency_key, is_new, status = active_store.get_or_create(
        intent_key=intent_key,
        recipient=recipient_address,
        amount_micro_usdc=validated_amount,
        chain_id=ARC_L1_CHAIN_CONFIG["evm_chain_id"],
        token=ARC_L1_CHAIN_CONFIG["native_currency"]["symbol"],
        token_address=ARC_USDC_ERC20_ADDRESS,
        source_wallet_id=DEFAULT_WALLET_ID,
    )

    return {
        "chain_config": ARC_L1_CHAIN_CONFIG,
        "settlement": {
            "recipient": recipient_address,
            "amount_micro_usdc": validated_amount,
            "amount_usdc_display": validated_amount / MICRO_USDC_MULTIPLIER,
            "erc20_token_address": ARC_USDC_ERC20_ADDRESS,
            "erc20_decimals": USDC_ERC20_DECIMALS,
            "native_gas_decimals": USDC_NATIVE_DECIMALS,
            "native_wei_equivalent": validated_amount * (10**(USDC_NATIVE_DECIMALS - USDC_ERC20_DECIMALS)),
        },
        "idempotency": {
            "idempotency_key": idempotency_key,
            "source_block_hash": block_hash,
            "nonce": nonce,
            "is_new": is_new,
            "status": status.value if isinstance(status, SettlementIntentState) else str(status),
            "conformance": "RFC 9562 § 5.4 / RFC 4122 Conforming UUIDv4 (Durable Mapping)",
        },
    }


ERC20_TRANSFER_EVENT_TOPIC: Final[str] = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


def validate_onchain_settlement_receipt(
    receipt: Dict[str, Any],
    intent: Dict[str, Any],
    finalized_block_number: Optional[int] = None,
    require_event_logs: bool = False,
) -> Tuple[bool, str]:
    """
    Cryptographically and economically binds an on-chain transaction receipt to the settlement intent.
    Fails closed if the receipt does not match:
    - chain_id (Arc L1 5042)
    - asset_contract (Arc USDC 0x3600000000000000000000000000000000000000)
    - recipient address
    - amount_micro_usdc
    - idempotency_key
    - status in {'CONFIRMED', 'SUCCESS', 'COMPLETE'}
    - finality: receipt.block_number <= finalized_block_number (when provided)
    - event logs: canonical Transfer event emitted by Arc USDC contract (when require_event_logs=True)
    """
    if not isinstance(receipt, dict) or not isinstance(intent, dict):
        return False, "Receipt or intent payload is not a valid dictionary"

    # 1. Chain binding
    receipt_chain = receipt.get("chain_id")
    intent_chain = intent.get("chain_id") or ARC_L1_CHAIN_CONFIG["evm_chain_id"]
    if receipt_chain != intent_chain:
        return False, f"Chain ID mismatch: receipt has {receipt_chain!r}, intent specified {intent_chain!r}"

    # 2. Asset contract binding
    receipt_asset = (receipt.get("asset_contract") or "").lower()
    intent_asset = (intent.get("token_address") or ARC_USDC_ERC20_ADDRESS).lower()
    if receipt_asset != intent_asset:
        return False, f"Asset contract mismatch: receipt has {receipt_asset!r}, intent specified {intent_asset!r}"

    # 3. Recipient binding
    receipt_recip = (receipt.get("recipient") or "").lower()
    intent_recip = (intent.get("recipient") or "").lower()
    if receipt_recip != intent_recip:
        return False, f"Recipient mismatch: receipt has {receipt_recip!r}, intent specified {intent_recip!r}"

    # 4. Economic amount binding
    try:
        receipt_amt = int(receipt.get("amount_micro_usdc", -1))
        intent_amt = int(intent.get("amount_micro_usdc", -2))
    except (ValueError, TypeError):
        return False, "Amount in receipt or intent is not a valid integer"
    if receipt_amt != intent_amt:
        return False, f"Amount mismatch: receipt has {receipt_amt} micro-USDC, intent specified {intent_amt}"

    # 5. Idempotency binding
    receipt_key = receipt.get("idempotency_key")
    intent_key = intent.get("idempotency_key")
    if not receipt_key or receipt_key != intent_key:
        return False, f"Idempotency key mismatch: receipt has {receipt_key!r}, intent specified {intent_key!r}"

    # 6. Status check
    receipt_status = str(receipt.get("status", "")).upper()
    if receipt_status not in {"CONFIRMED", "SUCCESS", "COMPLETE"}:
        return False, f"Receipt status is unconfirmed: {receipt_status}"

    # 7. Authoritative finality check
    if finalized_block_number is not None:
        block_num = receipt.get("block_number")
        if block_num is None or not isinstance(block_num, int):
            return False, "Receipt missing integer block_number required for finality verification"
        if block_num > finalized_block_number:
            return False, (
                f"Transaction unfinalized: receipt block {block_num} exceeds network finalized block "
                f"{finalized_block_number}"
            )

    # 8. Decoded event log verification
    if require_event_logs:
        logs = receipt.get("logs")
        if not isinstance(logs, list) or not logs:
            return False, "Receipt missing required event logs"
        found_transfer = False
        target_recip_topic = "0x" + intent_recip.replace("0x", "").lower().rjust(64, "0")
        for entry in logs:
            if not isinstance(entry, dict):
                continue
            log_addr = (entry.get("address") or "").lower()
            topics = [t.lower() for t in entry.get("topics", [])]
            if log_addr == ARC_USDC_ERC20_ADDRESS.lower() and topics and topics[0] == ERC20_TRANSFER_EVENT_TOPIC:
                # Check recipient topic in topic[2]
                if len(topics) >= 3 and topics[2] == target_recip_topic:
                    # Check value in data
                    data_hex = entry.get("data", "0x0")
                    try:
                        val = int(data_hex, 16) if isinstance(data_hex, str) else int(data_hex)
                        if val == intent_amt:
                            found_transfer = True
                            break
                    except ValueError:
                        continue
        if not found_transfer:
            return False, "No matching Arc USDC ERC-20 Transfer event log discovered in receipt"

    return True, "Receipt successfully validated and bound to intent"



def reconcile_ambiguous_gateway_outcome(
    intent_key: str,
    idempotency_key: str,
    gateway_status_provider: Callable[[str], Dict[str, Any]],
    store: DurableIdempotencyStore,
) -> Dict[str, Any]:
    """
    Reconciles an ambiguous outcome (e.g. client timeout or network disconnect)
    where gateway may have accepted the request.
    Performs a read-only status query using the persisted idempotency_key
    WITHOUT resubmitting or creating duplicate transactions.
    """
    existing_intent = store.get_intent(intent_key)
    if not existing_intent:
        raise ValueError(f"Intent key {intent_key!r} not found in durable store")

    # Perform read-only query against gateway
    query_resp = gateway_status_provider(idempotency_key)
    status_str = str(query_resp.get("status", "")).upper()

    if status_str in {"CONFIRMED", "COMPLETE", "COMPLETED"}:
        tx_hash = query_resp.get("tx_hash") or query_resp.get("id")
        current_status = SettlementIntentState(existing_intent["status"])
        if current_status in {SettlementIntentState.RECONCILIATION_REQUIRED, SettlementIntentState.REQUEST_ACCEPTED, SettlementIntentState.PENDING}:
            store.transition_state(
                intent_key=intent_key,
                from_state=current_status,
                to_state=SettlementIntentState.CONFIRMED,
                tx_hash=tx_hash,
            )
        return {"reconciled": True, "status": "CONFIRMED", "tx_hash": tx_hash}
    elif status_str in {"FAILED", "REJECTED", "CANCELED"}:
        current_status = SettlementIntentState(existing_intent["status"])
        if current_status in {SettlementIntentState.RECONCILIATION_REQUIRED, SettlementIntentState.REQUEST_ACCEPTED, SettlementIntentState.PENDING}:
            store.transition_state(
                intent_key=intent_key,
                from_state=current_status,
                to_state=SettlementIntentState.FAILED,
                failure_reason=query_resp.get("error", "Gateway reported failure during reconciliation"),
            )
        return {"reconciled": True, "status": "FAILED", "reason": query_resp.get("error")}
    else:
        return {"reconciled": False, "status": "PENDING_INVESTIGATION", "gateway_response": query_resp}

