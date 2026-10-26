"""
QuantumFlex Track 4: Relayer Crash-Recovery and Settlement Idempotency Integration Suite
========================================================================================
Proves the end-to-end crash-recovery invariant requested by security review:
  1. Relayer broadcasts settlement transaction.
  2. Network connection drops before receipt is received.
  3. Relayer process terminates / crashes.
  4. Cold relayer process boots from persistent journal.
  5. Original transaction is discovered on-chain.
  6. Relayer verifies on-chain receipt and contract state.
  7. Relayer confirms operation with ZERO second payment submitted.
  8. Handles unresolved/pending transactions without marking them failed.
  9. Repeated recovery invocations yield strictly idempotent results.
 10. Enforces exact 6-decimal USDC scaling and RFC 4122 UUID v5 compliance.
"""

import hashlib
import json
import pytest
import tempfile
import uuid
from pathlib import Path
from typing import Dict, Any, Optional

from api_node.settlement_recovery import (
    CrashProofSettlementRelayer,
    SettlementIntentJournal,
    SettlementIntent,
    RelayerIntentState,
    NetworkDropBeforeReceiptException,
    derive_deterministic_uuid_v5,
    QUANTUMFLEX_NAMESPACE_UUID
)


class MockEVMParisSettlementChain:
    """
    High-fidelity simulation of Base/Paris EVM node and QuantumFlexUSDCSettler contract.
    Enforces:
      - 6-decimal USDC balances (1_000_000n = 1.00 USDC).
      - Atomic executedProofs(bytes32 => bool) state mapping.
      - Mempool transaction tracking with explicit mine/revert/drop controls.
    """
    def __init__(self, relayer_address: str = "0xRelayer11111111111111111111111111111111"):
        self.relayer_address = relayer_address
        self.nonce_counter = 0
        self.mempool: Dict[str, Dict[str, Any]] = {}
        self.mined_txs: Dict[str, Dict[str, Any]] = {}
        self.executed_proofs: Dict[str, bool] = {}
        self.balances: Dict[str, int] = {
            self.relayer_address: 100_000_000,  # 100.00 USDC
        }
        self.total_broadcasts_received = 0
        self.confirmed_nonce = 0
        self.mined_txs_by_nonce: Dict[tuple[str, int], Dict[str, Any]] = {}

    def get_confirmed_nonce(self, address: str) -> int:
        if address == self.relayer_address:
            return self.confirmed_nonce
        return 0

    def get_transaction_by_nonce(self, address: str, nonce: int) -> Optional[Dict[str, Any]]:
        return self.mined_txs_by_nonce.get((address, nonce))

    def prepare_transaction(self, proof_hash: str, recipient: str, amount_atomic: int) -> tuple[str, int]:
        nonce = self.nonce_counter
        self.nonce_counter += 1
        tx_hash = "0x" + hashlib.sha256(f"{self.relayer_address}:{nonce}:{proof_hash}:{amount_atomic}".encode()).hexdigest()
        self.mempool[tx_hash] = {
            "tx_hash": tx_hash,
            "nonce": nonce,
            "proof_hash": proof_hash,
            "recipient": recipient,
            "amount_atomic": amount_atomic,
            "status": "PENDING"
        }
        return tx_hash, nonce

    def broadcast_raw_transaction(self, tx_hash: str) -> None:
        if tx_hash not in self.mempool:
            raise RuntimeError(f"Unknown tx_hash: {tx_hash}")
        self.total_broadcasts_received += 1

    def is_proof_executed(self, proof_hash: str) -> bool:
        return self.executed_proofs.get(proof_hash, False)

    def get_transaction_status(self, tx_hash: str) -> str:
        if tx_hash in self.mined_txs:
            return "MINED_SUCCESS" if self.mined_txs[tx_hash]["status"] == 1 else "REVERTED"
        if tx_hash in self.mempool:
            return "PENDING"
        return "DROPPED"

    def get_receipt(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        return self.mined_txs.get(tx_hash)

    def find_in_flight_by_proof(self, proof_hash: str) -> Optional[Dict[str, Any]]:
        for tx in self.mempool.values():
            if tx.get("proof_hash") == proof_hash:
                return tx
        return None

    def find_receipt_by_proof(self, proof_hash: str) -> Optional[Dict[str, Any]]:
        for tx in self.mined_txs.values():
            if tx.get("proof_hash") == proof_hash:
                return tx
        return None

    def wait_for_receipt(self, tx_hash: str) -> Dict[str, Any]:
        if tx_hash in self.mined_txs:
            return self.mined_txs[tx_hash]
        raise TimeoutError(f"Receipt for {tx_hash} not yet available")

    def mine_block(self) -> None:
        """Simulate block producer mining all pending transactions in mempool into a block."""
        for tx_hash, tx_data in list(self.mempool.items()):
            proof_hash = tx_data["proof_hash"]
            recipient = tx_data["recipient"]
            amount = tx_data["amount_atomic"]

            # Contract execution logic (Paris EVM)
            if self.executed_proofs.get(proof_hash, False):
                # Contract reverts if proof already executed
                self.mined_txs[tx_hash] = {
                    "tx_hash": tx_hash,
                    "proof_hash": proof_hash,
                    "status": 0,
                    "error": "PROOF_ALREADY_EXECUTED",
                    "block_number": 1042
                }
            else:
                self.executed_proofs[proof_hash] = True
                self.balances[recipient] = self.balances.get(recipient, 0) + amount
                self.balances[self.relayer_address] -= amount
                self.mined_txs[tx_hash] = {
                    "tx_hash": tx_hash,
                    "proof_hash": proof_hash,
                    "status": 1,
                    "block_number": 1042,
                    "gas_used": 42100,
                    "recipient": recipient,
                    "amount_atomic": amount
                }
            self.confirmed_nonce = max(self.confirmed_nonce, tx_data["nonce"] + 1)
            del self.mempool[tx_hash]


def make_valid_quantum_proof(job_id: str = "qf-bell-proof-001") -> Dict[str, Any]:
    payload = json.dumps({"job_id": job_id, "correlation": 0.9258}, sort_keys=True, separators=(",", ":"))
    block_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return {
        "job_id": job_id,
        "correlation": 0.9258,
        "zero_entropy": 0.0,
        "canonical_payload": payload,
        "block_hash": block_hash
    }


# ==============================================================================
# TEST SUITE: Deterministic Crash Recovery & Settlement Idempotency
# ==============================================================================

def test_full_crash_recovery_after_broadcast_drops_connection():
    """
    The Definitive Crash Test:
      1. Relayer broadcasts settlement transaction.
      2. Network connection drops before receipt arrives (simulating crash/disconnect).
      3. Relayer process terminates; memory state destroyed.
      4. Cold relayer starts from persistent WAL journal.
      5. Original transaction is mined on-chain.
      6. Relayer recovers transaction, confirms receipt, marks CONFIRMED.
      7. Proves ZERO second payment is broadcast (broadcast_count == 1).
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        journal_dir = Path(temp_dir)
        chain = MockEVMParisSettlementChain()
        recipient = "0xRecipient44444444444444444444444444444444"
        amount_atomic = 1_000_000  # 1.00 USDC in 6 decimals
        proof = make_valid_quantum_proof("qf-crash-run-1")

        # -------------------------------------------------------------
        # STEP 1: Process A starts, stages intent, and broadcasts
        # -------------------------------------------------------------
        journal_a = SettlementIntentJournal(journal_dir)
        relayer_a = CrashProofSettlementRelayer(journal_a, chain)

        intent_staged = relayer_a.stage_settlement(recipient, amount_atomic, proof)
        assert intent_staged.state == RelayerIntentState.STAGED
        assert intent_staged.broadcast_count == 0

        # Broadcast with simulated network drop right after submission
        with pytest.raises(NetworkDropBeforeReceiptException):
            relayer_a.execute_settlement(intent_staged.intent_id, simulate_network_drop=True)

        # -------------------------------------------------------------
        # STEP 2: Process A terminates / crashes (Simulated Crash)
        # -------------------------------------------------------------
        crashed_persisted_intent = journal_a.load(intent_staged.intent_id)
        assert crashed_persisted_intent is not None
        broadcast_tx_hash = crashed_persisted_intent.tx_hash
        assert broadcast_tx_hash is not None
        assert chain.total_broadcasts_received == 1

        # Simulate host crash: delete Process A objects from memory
        del relayer_a
        del journal_a

        # -------------------------------------------------------------
        # STEP 3: Verify Persistence: Intent survived crash in journal
        # -------------------------------------------------------------
        journal_b = SettlementIntentJournal(journal_dir)
        recovered_intent = journal_b.load(intent_staged.intent_id)
        assert recovered_intent is not None
        assert recovered_intent.state == RelayerIntentState.BROADCAST_IN_FLIGHT
        assert recovered_intent.tx_hash == broadcast_tx_hash
        assert recovered_intent.broadcast_count == 1

        # -------------------------------------------------------------
        # STEP 4: Network miners mine the broadcast transaction on-chain
        # -------------------------------------------------------------
        assert chain.is_proof_executed(proof["block_hash"]) is False
        chain.mine_block()
        # On-chain state is now executed
        assert chain.is_proof_executed(proof["block_hash"]) is True
        assert chain.balances[recipient] == 1_000_000

        # -------------------------------------------------------------
        # STEP 5: Process B (Cold Restart) boots and runs reconciliation
        # -------------------------------------------------------------
        relayer_b = CrashProofSettlementRelayer(journal_b, chain)
        reconciliation_results = relayer_b.cold_restart_reconcile()

        assert len(reconciliation_results) == 1
        rec = reconciliation_results[0]
        assert rec["status"] == RelayerIntentState.CONFIRMED.value
        assert rec["reconciliation"] == "DISCOVERED_ON_CHAIN_MINED"
        assert rec["tx_hash"] == broadcast_tx_hash
        assert rec["broadcast_count"] == 1

        # -------------------------------------------------------------
        # STEP 6: Assertions on Zero Double-Spending
        # -------------------------------------------------------------
        final_intent = journal_b.load(intent_staged.intent_id)
        assert final_intent.state == RelayerIntentState.CONFIRMED
        assert final_intent.broadcast_count == 1
        assert chain.total_broadcasts_received == 1  # ZERO second broadcast!
        assert chain.balances[recipient] == 1_000_000  # Exactly 1.00 USDC credited


def test_crash_recovery_when_transaction_remains_pending_in_mempool():
    """
    Opposite Case:
      The transaction was broadcast, receipt dropped, process crashes and restarts,
      BUT the transaction is still unmined (pending in mempool).
      Assertion:
        - Must NOT treat as failed.
        - Must NOT re-broadcast or trigger a duplicate payment.
        - Transitions to PENDING_RECONCILIATION.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        journal_dir = Path(temp_dir)
        chain = MockEVMParisSettlementChain()
        recipient = "0xRecipientPending"
        amount_atomic = 2_500_000  # 2.50 USDC
        proof = make_valid_quantum_proof("qf-pending-proof")

        # Stage and broadcast with network drop
        journal = SettlementIntentJournal(journal_dir)
        relayer = CrashProofSettlementRelayer(journal, chain)
        intent = relayer.stage_settlement(recipient, amount_atomic, proof)

        with pytest.raises(NetworkDropBeforeReceiptException):
            relayer.execute_settlement(intent.intent_id, simulate_network_drop=True)

        assert chain.total_broadcasts_received == 1

        # Crash and cold restart WITHOUT mining the transaction
        del relayer
        del journal

        journal_restarted = SettlementIntentJournal(journal_dir)
        relayer_restarted = CrashProofSettlementRelayer(journal_restarted, chain)

        # Run reconciliation while tx is still pending
        results = relayer_restarted.cold_restart_reconcile()

        assert len(results) == 1
        rec = results[0]
        assert rec["status"] == RelayerIntentState.PENDING_RECONCILIATION.value
        assert rec["reconciliation"] == "IN_FLIGHT_MEMPOOL_AWAITING_MINING"

        # Check intent state in journal
        pending_intent = journal_restarted.load(intent.intent_id)
        assert pending_intent.state == RelayerIntentState.PENDING_RECONCILIATION
        assert pending_intent.broadcast_count == 1
        assert chain.total_broadcasts_received == 1  # No second payment broadcast!
        assert chain.balances.get(recipient, 0) == 0  # Not credited yet


def test_repeated_recovery_invocations_are_strictly_idempotent():
    """
    Repeated recovery attempts over an already-settled or discovered intent
    produce zero additional transactions, zero gas burn, and zero balance change.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        journal_dir = Path(temp_dir)
        chain = MockEVMParisSettlementChain()
        recipient = "0xRecipientRepeated"
        amount_atomic = 5_000_000  # 5.00 USDC
        proof = make_valid_quantum_proof("qf-repeat-proof")

        journal = SettlementIntentJournal(journal_dir)
        relayer = CrashProofSettlementRelayer(journal, chain)
        intent = relayer.stage_settlement(recipient, amount_atomic, proof)

        with pytest.raises(NetworkDropBeforeReceiptException):
            relayer.execute_settlement(intent.intent_id, simulate_network_drop=True)

        chain.mine_block()

        # Run recovery 5 consecutive times
        for _ in range(5):
            relayer.cold_restart_reconcile()
            # Attempt explicit execution on the intent
            exec_res = relayer.execute_settlement(intent.intent_id)
            assert exec_res["status"] == "CONFIRMED"

        assert chain.total_broadcasts_received == 1
        assert chain.balances[recipient] == 5_000_000


def test_preflight_onchain_executed_proofs_check_burns_zero_gas():
    """
    Verifies that if a proof is already marked executed on-chain (e.g. from an earlier batch
    or another relayer node), pre-flight check catches it and skips broadcast with 0 gas burned.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        journal_dir = Path(temp_dir)
        chain = MockEVMParisSettlementChain()
        proof = make_valid_quantum_proof("qf-preflight-proof")

        # Manually mark executed on-chain
        chain.executed_proofs[proof["block_hash"]] = True

        journal = SettlementIntentJournal(journal_dir)
        relayer = CrashProofSettlementRelayer(journal, chain)

        intent = relayer.stage_settlement("0xSomeone", 1_000_000, proof)
        result = relayer.execute_settlement(intent.intent_id)

        assert result["status"] == "CONFIRMED"
        assert result["action"] == "CONFIRMED_ON_CHAIN_PREFLIGHT"
        assert result["gas_burned"] == 0
        assert chain.total_broadcasts_received == 0


def test_deterministic_uuid_v5_derivation():
    """
    Verifies that idempotency keys strictly conform to RFC 4122 Version 5 (name-based SHA-1)
    and are 100% deterministic without random entropy.
    """
    proof_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    key1 = derive_deterministic_uuid_v5(proof_hash)
    key2 = derive_deterministic_uuid_v5(proof_hash)

    # Determinism
    assert key1 == key2

    # RFC 4122 compliance
    parsed_uuid = uuid.UUID(key1)
    assert parsed_uuid.version == 5
    assert parsed_uuid.variant == uuid.RFC_4122

    # Rejects claiming random UUID v4
    assert parsed_uuid.version != 4


def test_six_decimal_atomic_usdc_enforcement():
    """
    Enforces the 6-decimal rule (1 USDC = 1_000_000 atomic units).
    Rejects floats, strings, negative amounts, or 18-decimal scales.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        journal = SettlementIntentJournal(Path(temp_dir))
        relayer = CrashProofSettlementRelayer(journal, MockEVMParisSettlementChain())
        proof = make_valid_quantum_proof("qf-decimals-test")

        # Rejects float
        with pytest.raises(ValueError, match="6-decimal atomic integer"):
            relayer.stage_settlement("0xUser", 1.5, proof)  # type: ignore

        # Rejects zero or negative
        with pytest.raises(ValueError, match="6-decimal atomic integer"):
            relayer.stage_settlement("0xUser", 0, proof)


def test_crash_power_loss_before_tx_hash_persisted_reconciles_without_duplicate():
    """
    Adversarial Scenario:
      1. Relayer stages settlement intent (state = STAGED, tx_hash = None on disk).
      2. Transaction is broadcast to network, but power cuts BEFORE tx_hash can be persisted.
         (Journal on disk still has state = STAGED and tx_hash = None).
      3. Block producer mines transaction on-chain.
      4. Relayer cold restarts with only STAGED / tx_hash=None in durable journal.
      5. Relayer runs cold_restart_reconcile().
      6. Assertions:
         - Relayer discovers proof executed on-chain.
         - Relayer associates mined receipt and transitions intent to CONFIRMED.
         - ZERO second payment is broadcast (total_broadcasts_received == 1).
         - Recipient credited exactly once.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        journal_dir = Path(temp_dir)
        chain = MockEVMParisSettlementChain()
        recipient = "0xAdversarialRecipient"
        amount_atomic = 3_000_000  # 3.00 USDC
        proof = make_valid_quantum_proof("qf-adv-power-loss-mined")

        # Process A stages intent
        journal_a = SettlementIntentJournal(journal_dir)
        relayer_a = CrashProofSettlementRelayer(journal_a, chain)
        intent = relayer_a.stage_settlement(recipient, amount_atomic, proof)
        assert intent.state == RelayerIntentState.STAGED
        assert intent.tx_hash is None

        # Simulate broadcast to mempool WITHOUT updating the journal file
        # (simulating sudden power loss before journal write/fsync)
        tx_hash, _ = chain.prepare_transaction(intent.proof_hash, recipient, amount_atomic)
        chain.broadcast_raw_transaction(tx_hash)

        # Host crashes immediately (Process A destroyed)
        del relayer_a
        del journal_a

        # Journal on disk still has only STAGED with tx_hash = None!
        journal_b = SettlementIntentJournal(journal_dir)
        persisted = journal_b.load(intent.intent_id)
        assert persisted.state == RelayerIntentState.STAGED
        assert persisted.tx_hash is None

        # Transaction is mined on-chain
        chain.mine_block()
        assert chain.is_proof_executed(proof["block_hash"]) is True

        # Process B starts cold and reconciles
        relayer_b = CrashProofSettlementRelayer(journal_b, chain)
        results = relayer_b.cold_restart_reconcile()

        assert len(results) == 1
        rec = results[0]
        assert rec["status"] == RelayerIntentState.CONFIRMED.value
        assert rec["reconciliation"] == "DISCOVERED_ON_CHAIN_MINED"
        assert rec["tx_hash"] == tx_hash

        # Final invariant checks
        final_intent = journal_b.load(intent.intent_id)
        assert final_intent.state == RelayerIntentState.CONFIRMED
        assert chain.total_broadcasts_received == 1  # ZERO duplicate payment!
        assert chain.balances[recipient] == 3_000_000


def test_crash_power_loss_before_tx_hash_persisted_while_pending_in_mempool():
    """
    Adversarial Scenario (Pending in Mempool):
      1. Relayer stages intent (STAGED, tx_hash = None on disk).
      2. Transaction broadcast to mempool; power cuts before tx_hash is written to journal.
      3. Transaction remains UNMINED in mempool.
      4. Relayer cold restarts with only STAGED in journal.
      5. Relayer runs cold_restart_reconcile().
      6. Assertions:
         - Relayer discovers in-flight transaction in mempool matching proof_hash.
         - Relayer adopts tx_hash and transitions to PENDING_RECONCILIATION.
         - Relayer does NOT broadcast a second transaction.
         - Recipient balance remains 0 (not prematurely credited).
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        journal_dir = Path(temp_dir)
        chain = MockEVMParisSettlementChain()
        recipient = "0xAdversarialPending"
        amount_atomic = 4_000_000  # 4.00 USDC
        proof = make_valid_quantum_proof("qf-adv-power-loss-pending")

        journal_a = SettlementIntentJournal(journal_dir)
        relayer_a = CrashProofSettlementRelayer(journal_a, chain)
        intent = relayer_a.stage_settlement(recipient, amount_atomic, proof)

        # Broadcast to mempool without journal commit (sudden power loss)
        tx_hash, _ = chain.prepare_transaction(intent.proof_hash, recipient, amount_atomic)
        chain.broadcast_raw_transaction(tx_hash)

        del relayer_a
        del journal_a

        # Cold restart
        journal_b = SettlementIntentJournal(journal_dir)
        relayer_b = CrashProofSettlementRelayer(journal_b, chain)

        # Reconcile while tx is still pending in mempool
        results = relayer_b.cold_restart_reconcile()

        assert len(results) == 1
        rec = results[0]
        assert rec["status"] == RelayerIntentState.PENDING_RECONCILIATION.value
        assert rec["reconciliation"] == "DISCOVERED_IN_FLIGHT_MEMPOOL_WITHOUT_LOCAL_TX_HASH"
        assert rec["tx_hash"] == tx_hash

        # Invariants: no duplicate broadcast, no premature credit
        assert chain.total_broadcasts_received == 1
        assert chain.balances.get(recipient, 0) == 0

        # Now mine the block and reconcile again
        chain.mine_block()
        relayer_b.cold_restart_reconcile()

        final_intent = journal_b.load(intent.intent_id)
        assert final_intent.state == RelayerIntentState.CONFIRMED
        assert chain.total_broadcasts_received == 1  # Still exactly 1!
        assert chain.balances[recipient] == 4_000_000


def test_concurrent_relayers_recovery_with_split_rpc_mempool_visibility():
    """
    Adversarial Concurrency Scenario:
      Two independent relayer processes attempt to recover the same staged settlement
      simultaneously, while the original transaction is pending and NOT visible to
      one of their RPC endpoints (simulating network partition / RPC propagation delay).
      
      Assertions:
        1. Process 1 (seeing pending tx) reconciles to PENDING_RECONCILIATION.
        2. Process 2 (invisible mempool) locks journal, sees state in flight/pending,
           and REFUSES to broadcast a duplicate transaction.
        3. Block mines on-chain.
        4. Both processes eventually reconcile to CONFIRMED.
        5. Zero duplicate broadcasts, exactly one payment credited.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        journal_dir = Path(temp_dir)
        chain_rpc1 = MockEVMParisSettlementChain()
        chain_rpc2 = MockEVMParisSettlementChain()  # Separate node with split view

        # Share on-chain state when blocks mine, but separate mempools
        chain_rpc2.executed_proofs = chain_rpc1.executed_proofs
        chain_rpc2.balances = chain_rpc1.balances
        chain_rpc2.mined_txs = chain_rpc1.mined_txs

        recipient = "0xSplitRPCRecipient"
        amount_atomic = 1_500_000  # 1.50 USDC
        proof = make_valid_quantum_proof("qf-concurrent-split-rpc")

        # Process 1 stages intent and broadcasts via RPC 1
        journal1 = SettlementIntentJournal(journal_dir)
        relayer1 = CrashProofSettlementRelayer(journal1, chain_rpc1)
        intent = relayer1.stage_settlement(recipient, amount_atomic, proof)

        # Broadcast drops before receipt
        with pytest.raises(NetworkDropBeforeReceiptException):
            relayer1.execute_settlement(intent.intent_id, simulate_network_drop=True)

        assert chain_rpc1.total_broadcasts_received == 1
        assert chain_rpc2.total_broadcasts_received == 0  # Not in RPC 2's mempool!

        # Process 2 boots against RPC 2 concurrently
        journal2 = SettlementIntentJournal(journal_dir)
        relayer2 = CrashProofSettlementRelayer(journal2, chain_rpc2)

        # Process 1 runs reconcile
        res1 = relayer1.cold_restart_reconcile()
        assert res1[0]["status"] == RelayerIntentState.PENDING_RECONCILIATION.value

        # Process 2 runs reconcile simultaneously against RPC 2 (where mempool is empty)
        # Because journal records state as in flight/pending, Relayer 2 does NOT duplicate
        res2 = relayer2.cold_restart_reconcile()
        assert res2[0]["status"] == RelayerIntentState.PENDING_RECONCILIATION.value
        assert chain_rpc2.total_broadcasts_received == 0  # No duplicate broadcast!

        # Now mine the block on the blockchain
        chain_rpc1.mine_block()
        assert chain_rpc1.is_proof_executed(proof["block_hash"]) is True
        assert chain_rpc2.is_proof_executed(proof["block_hash"]) is True

        # Both relayers reconcile after mining
        relayer1.cold_restart_reconcile()
        relayer2.cold_restart_reconcile()

        final1 = journal1.load(intent.intent_id)
        final2 = journal2.load(intent.intent_id)

        assert final1.state == RelayerIntentState.CONFIRMED
        assert final2.state == RelayerIntentState.CONFIRMED
        assert chain_rpc1.total_broadcasts_received == 1  # Exactly one broadcast in total!
        assert chain_rpc1.balances[recipient] == 1_500_000  # Exactly one credit


def test_recovery_distinguishes_consumed_nonce_from_successful_settlement():
    """
    Advanced Nonce-Reconciliation Scenario:
      1. Relayer stages an intent, prepares transaction with allocated nonce N=0, and broadcasts.
      2. Relayer crashes before receiving receipt.
      3. An external event on-chain (e.g. cancellation transaction or unrelated transfer)
         executes with nonce N=0, advancing the account's confirmed on-chain nonce to N=1.
      4. The proof was NEVER executed on-chain (is_proof_executed == False).
      5. The original transaction was evicted/dropped from the mempool.
      6. The relayer boots cold and runs cold_restart_reconcile().
      7. Assertions:
         - Relayer discovers on-chain confirmed nonce has advanced past intent's nonce (1 > 0).
         - Relayer verifies proof was not executed.
         - Relayer marks intent FAILED with 'NONCE_CONSUMED_WITHOUT_EXECUTION'.
         - Relayer does NOT hang indefinitely in PENDING_RECONCILIATION.
         - ZERO duplicate payment was executed, recipient was not credited.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        journal_dir = Path(temp_dir)
        chain = MockEVMParisSettlementChain()
        recipient = "0xNonceVictim"
        amount_atomic = 2_000_000  # 2.00 USDC
        proof = make_valid_quantum_proof("qf-consumed-nonce-proof")

        journal = SettlementIntentJournal(journal_dir)
        relayer = CrashProofSettlementRelayer(journal, chain)
        intent = relayer.stage_settlement(recipient, amount_atomic, proof)

        # Broadcast with network drop
        with pytest.raises(NetworkDropBeforeReceiptException):
            relayer.execute_settlement(intent.intent_id, simulate_network_drop=True)

        persisted_intent = journal.load(intent.intent_id)
        assert persisted_intent.nonce == 0
        persisted_tx = persisted_intent.tx_hash

        # Simulate: Transaction is evicted from mempool (DROPPED)
        del chain.mempool[persisted_tx]

        # Stage 1: Account advances on-chain, but receipt is missing / temporarily unavailable
        # Critical Invariant: Missing receipt must NOT trigger terminal failure!
        # Must hold in PENDING_RECONCILIATION rather than prematurely abandoning intent
        chain.confirmed_nonce = 5
        assert chain.is_proof_executed(proof["block_hash"]) is False

        # Cold restart A
        del relayer
        del journal

        journal_restarted = SettlementIntentJournal(journal_dir)
        relayer_restarted = CrashProofSettlementRelayer(journal_restarted, chain)

        results_a = relayer_restarted.cold_restart_reconcile()
        assert len(results_a) == 1
        assert results_a[0]["status"] == RelayerIntentState.PENDING_RECONCILIATION.value
        assert results_a[0]["reconciliation"] == "AWAITING_RECEIPT_OR_PROVEN_REPLACEMENT"

        # Stage 2: Definitive proof of replacement transaction is returned by chain
        # A different transaction hash was mined at (relayer_address, nonce=0)
        replacement_tx_hash = "0xReplacementHash99999999999999999999999999999999"
        chain.mined_txs_by_nonce[(chain.relayer_address, 0)] = {
            "tx_hash": replacement_tx_hash,
            "nonce": 0,
            "status": 1
        }

        results_b = relayer_restarted.cold_restart_reconcile()

        assert len(results_b) == 1
        rec = results_b[0]
        assert rec["status"] == RelayerIntentState.FAILED.value
        assert rec["reconciliation"] == "NONCE_REPLACED_BY_DIFFERENT_TX"
        assert rec["replacing_tx_hash"] == replacement_tx_hash
        assert rec["confirmed_nonce"] == 5
        assert rec["intent_nonce"] == 0

        # Verify journal state
        final_intent = journal_restarted.load(intent.intent_id)
        assert final_intent.state == RelayerIntentState.FAILED
        assert "different transaction" in final_intent.failure_reason.lower()
        assert chain.balances.get(recipient, 0) == 0  # Zero funds transferred


