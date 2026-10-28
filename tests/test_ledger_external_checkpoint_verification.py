"""
QuantumFlex Gate 3: Ledger Immutability & External Witness Verification Suite
=============================================================================
Demonstrates detection of database ledger tampering by an independent external verifier:
1. Record alteration (payload mutation)
2. Record deletion (row removal)
3. Record reordering (sequence swap)
4. Full administrative rewrite / hash-chain recomputation (detected via independent external witness checkpoint)
"""

import hashlib
import json
import time
from typing import List, Dict, Any, Tuple
import pytest


def canonical_json(data: Dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def compute_entry_hash(prev_hash: str, payload: Dict[str, Any]) -> str:
    serialized = canonical_json(payload)
    return hashlib.sha256(f"{prev_hash}::{serialized}".encode("utf-8")).hexdigest()


class LedgerDatabase:
    """Simulates the PostgreSQL telemetry_log table with trigger and internal hash chain."""
    def __init__(self):
        self.rows: List[Dict[str, Any]] = []

    def append(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        seq = len(self.rows) + 1
        prev_hash = self.rows[-1]["entry_hash"] if self.rows else "0" * 64
        entry_hash = compute_entry_hash(prev_hash, payload)
        row = {
            "sequence": seq,
            "prev_hash": prev_hash,
            "entry_hash": entry_hash,
            "payload": payload,
            "created_at": time.time(),
        }
        self.rows.append(row)
        return row

    def internal_chain_valid(self) -> bool:
        """Evaluates whether the database's internal hash chain is self-consistent."""
        for i, row in enumerate(self.rows):
            expected_prev = self.rows[i - 1]["entry_hash"] if i > 0 else "0" * 64
            if row["prev_hash"] != expected_prev:
                return False
            if row["entry_hash"] != compute_entry_hash(expected_prev, row["payload"]):
                return False
        return True

    def privileged_admin_rewrite(self, target_seq: int, forged_payload: Dict[str, Any]) -> None:
        """
        Simulates a compromised DB superuser disabling triggers, altering row data,
        and recomputing all subsequent in-database hashes to make the DB appear internally valid.
        """
        idx = target_seq - 1
        self.rows[idx]["payload"] = forged_payload
        for i in range(idx, len(self.rows)):
            prev_hash = self.rows[i - 1]["entry_hash"] if i > 0 else "0" * 64
            self.rows[i]["prev_hash"] = prev_hash
            self.rows[i]["entry_hash"] = compute_entry_hash(prev_hash, self.rows[i]["payload"])


class ExternalWitnessCheckpointStore:
    """
    Independent out-of-band witness store (e.g. QF Witness on port 8444 / TPM NV ram).
    Stores authoritative signed checkpoints independent of the database engine.
    Retains persistent cryptographic evidence of equivocation attempts.
    """
    def __init__(self):
        self.authoritative_checkpoints: Dict[int, Dict[str, Any]] = {}
        self.equivocation_evidence: List[Dict[str, Any]] = []
        self.highest_sequence = 0

    def commit_checkpoint(self, checkpoint: Dict[str, Any]) -> Tuple[bool, str]:
        seq = checkpoint["sequence"]
        digest = checkpoint["state_digest"]
        prev_digest = checkpoint.get("previous_checkpoint_digest", "")

        # Equivocation check: sequence already witnessed with different state digest
        if seq in self.authoritative_checkpoints:
            existing = self.authoritative_checkpoints[seq]
            if existing["state_digest"] != digest:
                evidence = {
                    "sequence": seq,
                    "first_checkpoint": existing,
                    "conflicting_checkpoint": checkpoint,
                    "detected_at": time.time(),
                    "reason": "EQUIVOCATION: witness signed conflicting state digests for the same sequence",
                }
                self.equivocation_evidence.append(evidence)
                return False, f"EQUIVOCATION_DETECTED: conflicting state digest at sequence {seq} persisted to audit log"

        if seq <= self.highest_sequence:
            return False, f"MONOTONIC_ROLLBACK_DETECTED: attempted {seq} <= highest {self.highest_sequence}"


        if self.highest_sequence > 0:
            last_cp = self.authoritative_checkpoints[self.highest_sequence]
            if prev_digest != last_cp["state_digest"]:
                return False, "FORK_DETECTED: previous_checkpoint_digest does not match authoritative witness head"

        self.authoritative_checkpoints[seq] = checkpoint
        self.highest_sequence = seq
        return True, f"CHECKPOINT_COMMITTED: #{seq} acknowledged"

    def verify_ledger(self, ledger: LedgerDatabase) -> Tuple[bool, str]:
        """Verifies a ledger against both internal consistency and independent external checkpoints."""
        if not ledger.internal_chain_valid():
            return False, "INTERNAL_HASH_CHAIN_BROKEN: corrupted or mismatched row hashes"

        # Check against every external checkpoint anchor
        for seq, cp in self.authoritative_checkpoints.items():
            if seq > len(ledger.rows):
                return False, f"LEDGER_TRUNCATION_DETECTED: external checkpoint exists for #{seq}, but ledger has only {len(ledger.rows)} rows"
            ledger_entry = ledger.rows[seq - 1]
            if ledger_entry["entry_hash"] != cp["state_digest"]:
                return False, (
                    f"TAMPER_DETECTED: ledger row #{seq} hash {ledger_entry['entry_hash'][:16]}... "
                    f"does not match independent external witness checkpoint {cp['state_digest'][:16]}..."
                )

        return True, "LEDGER_VERIFIED: all records match authoritative external witness anchors"


def test_independent_witness_catches_record_alteration():
    """Modifying a payload breaks the internal hash chain."""
    ledger = LedgerDatabase()
    witness = ExternalWitnessCheckpointStore()

    for i in range(1, 5):
        row = ledger.append({"event": f"telemetry_{i}", "val": i * 10})
        witness.commit_checkpoint({
            "sequence": i,
            "state_digest": row["entry_hash"],
            "previous_checkpoint_digest": ledger.rows[i - 2]["entry_hash"] if i > 1 else "",
        })

    # Tamper with row 2 without recomputing chain
    ledger.rows[1]["payload"]["val"] = 999
    valid, reason = witness.verify_ledger(ledger)
    assert valid is False
    assert "INTERNAL_HASH_CHAIN_BROKEN" in reason


def test_independent_witness_catches_record_deletion():
    """Deleting a row causes an immediate sequence and hash mismatch."""
    ledger = LedgerDatabase()
    witness = ExternalWitnessCheckpointStore()

    for i in range(1, 4):
        row = ledger.append({"event": f"telemetry_{i}"})
        witness.commit_checkpoint({
            "sequence": i,
            "state_digest": row["entry_hash"],
            "previous_checkpoint_digest": ledger.rows[i - 2]["entry_hash"] if i > 1 else "",
        })

    del ledger.rows[1]  # Delete row 2
    valid, reason = witness.verify_ledger(ledger)
    assert valid is False


def test_independent_witness_catches_record_reordering():
    """Swapping two rows breaks hash chain sequence."""
    ledger = LedgerDatabase()
    witness = ExternalWitnessCheckpointStore()

    for i in range(1, 4):
        row = ledger.append({"event": f"telemetry_{i}"})
        witness.commit_checkpoint({
            "sequence": i,
            "state_digest": row["entry_hash"],
            "previous_checkpoint_digest": ledger.rows[i - 2]["entry_hash"] if i > 1 else "",
        })

    # Swap row 1 and row 2
    ledger.rows[1], ledger.rows[2] = ledger.rows[2], ledger.rows[1]
    valid, reason = witness.verify_ledger(ledger)
    assert valid is False


def test_independent_witness_defeats_privileged_admin_recomputation():
    """
    CRITICAL SECURITY CHECK:
    A privileged database superuser alters row 2, and uses administrator privileges
    to recompute all subsequent hashes in the database.
    The database's internal chain is valid, but the independent external witness checkpoint
    flags the tamper attempt.
    """
    ledger = LedgerDatabase()
    witness = ExternalWitnessCheckpointStore()

    # Build genuine chain of 5 records, committing checkpoints #2 and #4 to witness
    for i in range(1, 6):
        row = ledger.append({"sensor": "qf_node_1", "reading": i * 100})
        if i in (2, 4):
            witness.commit_checkpoint({
                "sequence": i,
                "state_digest": row["entry_hash"],
                "previous_checkpoint_digest": ledger.rows[i - 2]["entry_hash"] if i > 1 else "",
            })

    # Pre-attack verification passes
    ok, msg = witness.verify_ledger(ledger)
    assert ok is True

    # Privileged administrator alters row 2 and recomputes the internal hash chain
    ledger.privileged_admin_rewrite(target_seq=2, forged_payload={"sensor": "qf_node_1", "reading": 999999})

    # The database internally looks 100% self-consistent!
    assert ledger.internal_chain_valid() is True

    # But verification against the independent out-of-band witness FAILS:
    tamper_ok, tamper_reason = witness.verify_ledger(ledger)
    assert tamper_ok is False
    assert "TAMPER_DETECTED" in tamper_reason
    assert "does not match independent external witness checkpoint" in tamper_reason

    # The attacker also cannot rewrite the external witness:
    # 1. Submitting a new checkpoint with sequence 2 fails with equivocation detection:
    ok_eq, msg_eq = witness.commit_checkpoint({
        "sequence": 2,
        "state_digest": ledger.rows[1]["entry_hash"],
    })
    assert ok_eq is False
    assert "EQUIVOCATION_DETECTED" in msg_eq

    # Submitting a lower sequence not previously indexed (e.g. sequence 1) fails rollback detection:
    ok_rb, msg_rb = witness.commit_checkpoint({
        "sequence": 1,
        "state_digest": ledger.rows[0]["entry_hash"],
    })
    assert ok_rb is False
    assert "MONOTONIC_ROLLBACK_DETECTED" in msg_rb

    # 2. Submitting a fork from an altered sequence fails previous digest check
    ok_fk, msg_fk = witness.commit_checkpoint({
        "sequence": 5,
        "state_digest": ledger.rows[4]["entry_hash"],
        "previous_checkpoint_digest": "0xforgedprevioushash",
    })
    assert ok_fk is False
    assert "FORK_DETECTED" in msg_fk


def test_independent_witness_persists_equivocation_evidence():
    """
    CORRECTION B VERIFICATION:
    If a witness or attacker attempts equivocation by submitting two conflicting
    checkpoints for the same sequence number, the verifier must NOT silently drop it.
    It MUST retain persistent evidence of the conflicting statements in an audit log.
    """
    witness = ExternalWitnessCheckpointStore()

    # Legitimate checkpoint sequence 1
    cp1_orig = {
        "sequence": 1,
        "state_digest": "0xstate_digest_alpha_genuine",
        "signer_key_id": "key_operator_1",
        "signature": "sig_alpha_genuine",
    }
    ok1, msg1 = witness.commit_checkpoint(cp1_orig)
    assert ok1 is True
    assert len(witness.equivocation_evidence) == 0

    # Malicious/compromised second checkpoint presented for sequence 1 with conflicting digest
    cp1_conflicting = {
        "sequence": 1,
        "state_digest": "0xstate_digest_alpha_equivocated_fork",
        "signer_key_id": "key_operator_1",
        "signature": "sig_alpha_fork",
    }
    ok2, msg2 = witness.commit_checkpoint(cp1_conflicting)
    assert ok2 is False
    assert "EQUIVOCATION_DETECTED" in msg2

    # Persistent evidence was recorded and retained:
    assert len(witness.equivocation_evidence) == 1
    evidence = witness.equivocation_evidence[0]
    assert evidence["sequence"] == 1
    assert evidence["first_checkpoint"]["state_digest"] == "0xstate_digest_alpha_genuine"
    assert evidence["conflicting_checkpoint"]["state_digest"] == "0xstate_digest_alpha_equivocated_fork"
    assert "EQUIVOCATION" in evidence["reason"]

