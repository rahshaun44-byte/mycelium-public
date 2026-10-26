"""
QuantumFlex Track 4: Crash-Proof Settlement Relayer & State Reconciliation Engine
================================================================================
Enforces the three-part idempotency model:
  1. On-Chain Smart Contract: executedProofs(blockHash) mapping (Paris EVM).
  2. Transaction Reconciliation: Relayer Write-Ahead Journal (WAL) + Receipt Verification.
  3. API / Settlement Deduplication: RFC 4122 UUID v5 derived deterministically from proof hash.

Zero Double-Spending Invariant:
  Under network drop, process kill, or RPC timeout after broadcast,
  the relayer reconciles on-chain state upon cold boot and never submits
  a duplicate transaction.
"""

import json
import os
import tempfile
import time
import uuid
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, List

from api_node.circle_usdc_settlement import QuantumFlexUSDCSettler, SettlementStatus

# Canonical namespace UUID for QuantumFlex USDC Settlements (RFC 4122)
QUANTUMFLEX_NAMESPACE_UUID = uuid.UUID("7b67b14d-91d4-4bb6-b631-f9d924df9287")


class RelayerIntentState(str, Enum):
    STAGED = "STAGED"
    BROADCAST_IN_FLIGHT = "BROADCAST_IN_FLIGHT"
    PENDING_RECONCILIATION = "PENDING_RECONCILIATION"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    DROPPED = "DROPPED"


def derive_deterministic_uuid_v5(proof_hash: str) -> str:
    """
    Derive an RFC 4122 Version 5 UUID (name-based SHA-1 digest) deterministically
    from the canonical proof block hash.
    Conforms to UUID specifications required by external payment APIs without
    falsely claiming random UUID v4 entropy.
    """
    return str(uuid.uuid5(QUANTUMFLEX_NAMESPACE_UUID, str(proof_hash)))


@dataclass
class SettlementIntent:
    intent_id: str             # RFC 4122 UUID v5
    proof_hash: str            # SHA256 hex digest of canonical quantum proof
    recipient: str             # EVM destination address (0x...)
    amount_atomic: int         # 6-decimal atomic USDC (1 USDC = 1_000_000n)
    state: RelayerIntentState
    tx_hash: Optional[str] = None
    nonce: Optional[int] = None
    broadcast_count: int = 0
    created_at: float = 0.0
    updated_at: float = 0.0
    failure_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["state"] = self.state.value if isinstance(self.state, RelayerIntentState) else str(self.state)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SettlementIntent":
        data_copy = dict(data)
        data_copy["state"] = RelayerIntentState(data_copy["state"])
        return cls(**data_copy)


from contextlib import contextmanager
import fcntl


class SettlementIntentJournal:
    """
    Durable, crash-resilient Write-Ahead Log (WAL) for settlement intents.
    Uses atomic tempfile + rename + sync to guarantee zero corrupt or partial states on SIGKILL.
    Guarantees cross-process concurrency safety via POSIX advisory file locking (fcntl.flock).
    """
    def __init__(self, journal_dir: Path):
        self.journal_dir = Path(journal_dir)
        self.journal_dir.mkdir(parents=True, exist_ok=True)
        self.journal_file = self.journal_dir / "settlement_intents.json"
        self.lock_file = self.journal_dir / "settlement_intents.lock"

    @contextmanager
    def locked(self, exclusive: bool = True):
        lock_fd = os.open(str(self.lock_file), os.O_CREAT | os.O_RDWR, 0o600)
        mode = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        try:
            fcntl.flock(lock_fd, mode)
            yield
        finally:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            finally:
                os.close(lock_fd)

    def _load_raw(self) -> Dict[str, Dict[str, Any]]:
        if not self.journal_file.exists():
            return {}
        try:
            with open(self.journal_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def load(self, intent_id: str) -> Optional[SettlementIntent]:
        with self.locked(exclusive=False):
            data = self._load_raw()
            if intent_id in data:
                return SettlementIntent.from_dict(data[intent_id])
            return None

    def list_all(self) -> List[SettlementIntent]:
        with self.locked(exclusive=False):
            data = self._load_raw()
            return [SettlementIntent.from_dict(v) for v in data.values()]

    def list_unconfirmed(self) -> List[SettlementIntent]:
        return [intent for intent in self.list_all() if intent.state != RelayerIntentState.CONFIRMED]

    def save(self, intent: SettlementIntent) -> None:
        intent.updated_at = time.time()
        with self.locked(exclusive=True):
            data = self._load_raw()
            data[intent.intent_id] = intent.to_dict()

            temp_path = None
            try:
                temp_fd, temp_path = tempfile.mkstemp(dir=str(self.journal_dir), prefix="intent_", suffix=".tmp")
                with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(temp_path, str(self.journal_file))

                # POSIX directory sync: guarantees directory entry update persists across sudden power loss
                try:
                    dir_fd = os.open(str(self.journal_dir), os.O_RDONLY | os.O_DIRECTORY)
                    try:
                        os.fsync(dir_fd)
                    finally:
                        os.close(dir_fd)
                except (OSError, AttributeError):
                    pass
            except Exception:
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                    except OSError:
                        pass
                raise


class NetworkDropBeforeReceiptException(Exception):
    """Simulates connection failure or crash after broadcast before receipt is returned."""
    pass


class CrashProofSettlementRelayer:
    """
    Settlement Relayer orchestrating on-chain submissions with crash recovery.
    """
    def __init__(self, journal: SettlementIntentJournal, chain_client: Any):
        self.journal = journal
        self.chain_client = chain_client

    def stage_settlement(self, recipient: str, amount_atomic: int, proof: Dict[str, Any]) -> SettlementIntent:
        """
        Stage a settlement intent with proof verification and deterministic UUID v5.
        Enforces 6-decimal precision rule (atomic integer).
        """
        if not isinstance(amount_atomic, int) or amount_atomic <= 0:
            raise ValueError(f"USDC amount must be a positive 6-decimal atomic integer, got: {amount_atomic}")

        if not QuantumFlexUSDCSettler.verify_quantum_proof(proof):
            raise ValueError("Cryptographic or empirical validation failed for quantum proof.")

        proof_hash = proof["block_hash"]
        intent_id = derive_deterministic_uuid_v5(proof_hash)

        existing = self.journal.load(intent_id)
        if existing:
            return existing

        now = time.time()
        intent = SettlementIntent(
            intent_id=intent_id,
            proof_hash=proof_hash,
            recipient=recipient,
            amount_atomic=amount_atomic,
            state=RelayerIntentState.STAGED,
            created_at=now,
            updated_at=now
        )
        self.journal.save(intent)
        return intent

    def execute_settlement(self, intent_id: str, simulate_network_drop: bool = False) -> Dict[str, Any]:
        """
        Broadcast settlement with pre-flight idempotency checks and crash-safe logging.
        """
        intent = self.journal.load(intent_id)
        if not intent:
            raise ValueError(f"Intent {intent_id} not found in journal.")

        if intent.state == RelayerIntentState.CONFIRMED:
            return {
                "status": SettlementStatus.CONFIRMED.value,
                "tx_hash": intent.tx_hash,
                "action": "ALREADY_CONFIRMED_IDEMPOTENT"
            }

        # 1. Pre-flight on-chain invariant: check if proof is already executed
        if self.chain_client.is_proof_executed(intent.proof_hash):
            intent.state = RelayerIntentState.CONFIRMED
            self.journal.save(intent)
            return {
                "status": SettlementStatus.CONFIRMED.value,
                "tx_hash": intent.tx_hash,
                "action": "CONFIRMED_ON_CHAIN_PREFLIGHT",
                "gas_burned": 0
            }

        # 2. Allocate nonce and pre-register tx_hash before transmission
        tx_hash, nonce = self.chain_client.prepare_transaction(
            proof_hash=intent.proof_hash,
            recipient=intent.recipient,
            amount_atomic=intent.amount_atomic
        )

        intent.tx_hash = tx_hash
        intent.nonce = nonce
        intent.broadcast_count += 1
        intent.state = RelayerIntentState.BROADCAST_IN_FLIGHT

        # Commit BROADCAST_IN_FLIGHT to durable storage BEFORE sending to mempool
        self.journal.save(intent)

        # 3. Broadcast to blockchain mempool
        self.chain_client.broadcast_raw_transaction(tx_hash)

        # 4. Simulate network drop or crash immediately after broadcast
        if simulate_network_drop:
            raise NetworkDropBeforeReceiptException(
                f"Simulated network drop after broadcasting tx: {tx_hash}"
            )

        # 5. Await receipt
        receipt = self.chain_client.wait_for_receipt(tx_hash)
        if receipt.get("status") == 1:
            intent.state = RelayerIntentState.CONFIRMED
            self.journal.save(intent)
            return {
                "status": SettlementStatus.CONFIRMED.value,
                "tx_hash": tx_hash,
                "receipt": receipt
            }
        else:
            intent.state = RelayerIntentState.FAILED
            intent.failure_reason = receipt.get("error", "Transaction reverted on-chain")
            self.journal.save(intent)
            return {
                "status": SettlementStatus.FAILED.value,
                "tx_hash": tx_hash,
                "reason": intent.failure_reason
            }

    def cold_restart_reconcile(self) -> List[Dict[str, Any]]:
        """
        Cold restart recovery routine:
        Inspects all unconfirmed intents in journal and reconciles with on-chain truth.
        Guarantees zero duplicate payments are broadcast.
        """
        results = []
        unconfirmed = self.journal.list_unconfirmed()

        for intent in unconfirmed:
            proof_hash = intent.proof_hash
            tx_hash = intent.tx_hash

            # Tier 1 On-Chain Source of Truth: Check if contract executed this proof
            if self.chain_client.is_proof_executed(proof_hash):
                # The transaction was mined on-chain! Reconcile intent without rebroadcasting
                receipt = None
                if tx_hash:
                    receipt = self.chain_client.get_receipt(tx_hash)
                elif hasattr(self.chain_client, "find_receipt_by_proof"):
                    receipt = self.chain_client.find_receipt_by_proof(proof_hash)
                    if receipt:
                        tx_hash = receipt.get("tx_hash")
                        intent.tx_hash = tx_hash

                intent.state = RelayerIntentState.CONFIRMED
                self.journal.save(intent)
                results.append({
                    "intent_id": intent.intent_id,
                    "status": RelayerIntentState.CONFIRMED.value,
                    "reconciliation": "DISCOVERED_ON_CHAIN_MINED",
                    "broadcast_count": intent.broadcast_count,
                    "tx_hash": tx_hash,
                    "receipt": receipt
                })
                continue

            # Tier 2 Transaction Reconciliation: If not marked executed on-chain
            if tx_hash:
                tx_status = self.chain_client.get_transaction_status(tx_hash)
                if tx_status == "MINED_SUCCESS":
                    # Mined but executedProofs query had race or delay; verify & confirm
                    intent.state = RelayerIntentState.CONFIRMED
                    self.journal.save(intent)
                    results.append({
                        "intent_id": intent.intent_id,
                        "status": RelayerIntentState.CONFIRMED.value,
                        "reconciliation": "TX_MINED_CONFIRMED",
                        "broadcast_count": intent.broadcast_count,
                        "tx_hash": tx_hash
                    })
                elif tx_status == "PENDING":
                    # Transaction is still pending in mempool; do NOT mark failed, do NOT re-broadcast
                    intent.state = RelayerIntentState.PENDING_RECONCILIATION
                    self.journal.save(intent)
                    results.append({
                        "intent_id": intent.intent_id,
                        "status": RelayerIntentState.PENDING_RECONCILIATION.value,
                        "reconciliation": "IN_FLIGHT_MEMPOOL_AWAITING_MINING",
                        "broadcast_count": intent.broadcast_count,
                        "tx_hash": tx_hash
                    })
                elif tx_status in {"REVERTED", "FAILED"}:
                    intent.state = RelayerIntentState.FAILED
                    intent.failure_reason = "Transaction reverted on chain without executing proof"
                    self.journal.save(intent)
                    results.append({
                        "intent_id": intent.intent_id,
                        "status": RelayerIntentState.FAILED.value,
                        "reconciliation": "TX_REVERTED",
                        "broadcast_count": intent.broadcast_count,
                        "tx_hash": tx_hash
                    })
                elif tx_status in {"DROPPED", "NOT_FOUND"}:
                    # Critical Safety Invariant: Absence from a single RPC node's mempool does NOT prove
                    # network-wide abandonment. It may be propagating or pending on another mining peer.
                    # Maintain PENDING_RECONCILIATION to prevent duplicate payment submissions.
                    intent.state = RelayerIntentState.PENDING_RECONCILIATION
                    self.journal.save(intent)
                    results.append({
                        "intent_id": intent.intent_id,
                        "status": RelayerIntentState.PENDING_RECONCILIATION.value,
                        "reconciliation": "AWAITING_PROPAGATION_OR_CONFIRMATION",
                        "broadcast_count": intent.broadcast_count,
                        "tx_hash": tx_hash
                    })
            else:
                # Local tx_hash was not journaled prior to crash.
                # Query mempool to check if a transaction was broadcast right before power loss!
                in_flight = None
                if hasattr(self.chain_client, "find_in_flight_by_proof"):
                    in_flight = self.chain_client.find_in_flight_by_proof(proof_hash)

                if in_flight:
                    discovered_tx = in_flight.get("tx_hash")
                    intent.tx_hash = discovered_tx
                    intent.state = RelayerIntentState.PENDING_RECONCILIATION
                    self.journal.save(intent)
                    results.append({
                        "intent_id": intent.intent_id,
                        "status": RelayerIntentState.PENDING_RECONCILIATION.value,
                        "reconciliation": "DISCOVERED_IN_FLIGHT_MEMPOOL_WITHOUT_LOCAL_TX_HASH",
                        "broadcast_count": intent.broadcast_count,
                        "tx_hash": discovered_tx
                    })
                else:
                    # Verified truly unbroadcast
                    results.append({
                        "intent_id": intent.intent_id,
                        "status": RelayerIntentState.STAGED.value,
                        "reconciliation": "NEVER_BROADCAST"
                    })

        return results
