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
from typing import Dict, Any, Optional

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
        self.wallet_id = wallet_id or DEFAULT_WALLET_ID
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
