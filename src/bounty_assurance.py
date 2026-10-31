"""
QuantumFlex Sovereign Bounty Assurance & Cryptographic Settlement Controls
(`QF-BOUNTY-01`, `QF-BOUNTY-02`, `QF-BOUNTY-03`, and Technical Corrections A–D).

Implements fail-closed verification for:
  - Technical Correction A: Six-invariant Two-Person Authorization (beyond hardware signatures alone).
  - Technical Correction B: Per-contract/per-chain ERC-20 & canonical 6-decimal USDC precision verification.
  - Technical Correction C: Full-operation-context deterministic RFC 4122 UUIDv4 idempotency keys.
  - Technical Correction D: Six-factor context-dependent vulnerability severity classification.
  - Acceptance Gates:
      * QF-BOUNTY-01 (Authorization Integrity)
      * QF-BOUNTY-02 (Evidence Integrity)
      * QF-BOUNTY-03 (Disclosure Integrity)
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import math
import re
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Mapping, MutableSet, Optional, Sequence, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from scripts.generate_research_dossier import PrivacyFilter, SecurityBoundaryError

# Canonical USDC Contract Registry (6 decimals = 1_000_000 base units per 1 USDC)
CANONICAL_USDC_CONTRACTS: Dict[Tuple[int, str], int] = {
    (8453, "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"): 6,   # Base Mainnet USDC
    (84532, "0x036cbd53842c5426634e7929541ec2318f3dcf7e"): 6,  # Base Sepolia USDC
}

_EVM_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
_HEX_DIGEST_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_BLOCK_HASH_RE = re.compile(r"^0x[0-9a-fA-F]{64}$")

ALLOWED_LOCAL_TEST_ENVIRONMENTS = frozenset(
    {
        "local_foundry_fork",
        "offline_source_snapshot",
        "authorized_local_sandbox",
    }
)

ALLOWED_HUMAN_APPROVERS = frozenset({"rahshaun_chambers", "rocky", "qf-operator-key"})

# Patterns that indicate operational live-drain instructions rather than local snapshot proof
_LIVE_EXPLOIT_COMMAND_PATTERNS: Tuple[Tuple[str, re.Pattern[str]], ...] = (
    (
        "FORGE_LIVE_BROADCAST",
        re.compile(r"\bforge\s+script\b[^\n]*--broadcast\b", re.IGNORECASE),
    ),
    (
        "CAST_SEND_EXTERNAL_RPC",
        re.compile(
            r"\bcast\s+send\b[^\n]*--rpc-url\s+https?://(?!127\.0\.0\.1|localhost)",
            re.IGNORECASE,
        ),
    ),
    (
        "RAW_PRIVATE_KEY_CLI_FLAG",
        re.compile(r"--private-key\s+0x[0-9a-fA-F]{64}\b"),
    ),
)

SEVERITY_RANK: Dict[str, int] = {
    "Informational": 0,
    "Low": 1,
    "Medium": 2,
    "High": 3,
    "Critical": 4,
}
RANK_TO_SEVERITY: Dict[int, str] = {v: k for k, v in SEVERITY_RANK.items()}


class BountyGateError(SecurityBoundaryError):
    """Raised when QF-BOUNTY-01..03 or Technical Corrections A–D fail closed."""


def _canonical_json_bytes(obj: Mapping[str, Any]) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _normalize_evm_address(addr: str, field_name: str) -> str:
    if not isinstance(addr, str) or not _EVM_ADDRESS_RE.match(addr.strip()):
        raise BountyGateError(f"Invalid 20-byte EVM hex address for '{field_name}': {addr!r}")
    return addr.strip().lower()


def _parse_utc_iso(ts_str: Any, field_name: str) -> dt.datetime:
    if not isinstance(ts_str, str) or not ts_str.strip():
        raise BountyGateError(f"Field '{field_name}' must be a non-empty ISO-8601 UTC timestamp.")
    clean = ts_str.strip()
    if clean.endswith("Z"):
        clean = clean[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(clean)
    except ValueError as exc:
        raise BountyGateError(f"Malformed ISO-8601 timestamp in '{field_name}': {exc}") from exc
    if parsed.tzinfo is None:
        raise BountyGateError(f"Field '{field_name}' must include an explicit timezone offset.")
    return parsed.astimezone(dt.timezone.utc)


# ==============================================================================
# Technical Correction A: Six-Invariant Two-Person Authorization
# ==============================================================================
@dataclass(frozen=True)
class SignerAttestation:
    signer_id: str
    credential_id: str
    public_key_raw_b64: str
    signature_b64: str


def build_two_person_signing_payload(
    *,
    chain_id: int,
    contract_address: str,
    operation_type: str,
    destination: str,
    amount_base_units: int,
    nonce: str,
    issued_at_unix: int,
    expires_at_unix: int,
) -> bytes:
    """Builds the canonical transaction-bound payload that both signers must independently sign."""
    if isinstance(chain_id, bool) or not isinstance(chain_id, int) or chain_id <= 0:
        raise BountyGateError("chain_id must be a positive integer.")
    if isinstance(amount_base_units, bool) or not isinstance(amount_base_units, int) or amount_base_units < 0:
        raise BountyGateError("amount_base_units must be a non-negative integer.")
    clean_op = (operation_type or "").strip()
    clean_nonce = (nonce or "").strip()
    if not clean_op or not clean_nonce:
        raise BountyGateError("operation_type and nonce must be non-empty.")

    envelope = {
        "domain": "qf.two_person_auth.v1",
        "chain_id": chain_id,
        "contract_address": _normalize_evm_address(contract_address, "contract_address"),
        "operation_type": clean_op,
        "destination": _normalize_evm_address(destination, "destination"),
        "amount_base_units": amount_base_units,
        "nonce": clean_nonce,
        "issued_at_unix": int(issued_at_unix),
        "expires_at_unix": int(expires_at_unix),
    }
    return _canonical_json_bytes(envelope)


def verify_two_person_authorization(
    *,
    chain_id: int,
    contract_address: str,
    operation_type: str,
    destination: str,
    amount_base_units: int,
    nonce: str,
    issued_at_unix: int,
    expires_at_unix: int,
    current_unix: int,
    attestation_a: SignerAttestation,
    attestation_b: SignerAttestation,
    authorized_identities: Mapping[str, Sequence[str]],
    trusted_credential_pubkeys_b64: Mapping[str, str],
    consumed_replay_keys: MutableSet[str],
    revoked_identities: Sequence[str] = (),
    revoked_credentials: Sequence[str] = (),
    max_ttl_seconds: int = 900,
) -> Dict[str, Any]:
    """
    Enforces all 6 mandatory two-person authorization guarantees:
      1. Two distinct authorized identities (`signer_a != signer_b`).
      2. Independent signing credentials (`credential_a != credential_b`, distinct Ed25519 keys).
      3. Explicit transaction payload binding (cryptographic Ed25519 verification over canonical tx tuple).
      4. Nonce and expiry validation (`issued_at_unix <= current_unix <= expires_at_unix`, bounded TTL).
      5. Replay protection (rejects previously consumed `(chain_id, contract, nonce)` or tx digest).
      6. Revocation handling (rejects revoked signer identities or revoked credentials).
    """
    # 1. Distinct authorized identities
    id_a = (attestation_a.signer_id or "").strip()
    id_b = (attestation_b.signer_id or "").strip()
    if not id_a or not id_b:
        raise BountyGateError("Two-Person Auth Violation: signer identities must be non-empty.")
    if id_a == id_b:
        raise BountyGateError(
            f"Two-Person Auth Violation: distinct identities required, got single identity '{id_a}'."
        )
    if id_a not in authorized_identities or id_b not in authorized_identities:
        raise BountyGateError("Two-Person Auth Violation: one or more signers are not authorized.")

    # 6. Revocation handling (checked before cryptographic work and before nonce mutation)
    revoked_id_set = {s.strip() for s in revoked_identities}
    revoked_cred_set = {c.strip() for c in revoked_credentials}
    if id_a in revoked_id_set or id_b in revoked_id_set:
        raise BountyGateError("Two-Person Auth Violation: signer identity has been revoked.")

    # 2. Independent signing credentials
    cred_a = (attestation_a.credential_id or "").strip()
    cred_b = (attestation_b.credential_id or "").strip()
    if not cred_a or not cred_b:
        raise BountyGateError("Two-Person Auth Violation: credential IDs must be non-empty.")
    if cred_a == cred_b:
        raise BountyGateError("Two-Person Auth Violation: independent signing credentials required.")
    if cred_a in revoked_cred_set or cred_b in revoked_cred_set:
        raise BountyGateError("Two-Person Auth Violation: signing credential has been revoked.")
    if cred_a not in authorized_identities[id_a] or cred_b not in authorized_identities[id_b]:
        raise BountyGateError("Two-Person Auth Violation: credential is not bound to declared signer identity.")

    expected_pub_a = trusted_credential_pubkeys_b64.get(cred_a)
    expected_pub_b = trusted_credential_pubkeys_b64.get(cred_b)
    if not expected_pub_a or not expected_pub_b:
        raise BountyGateError("Two-Person Auth Violation: credential public key missing from trust registry.")
    if expected_pub_a == expected_pub_b or attestation_a.public_key_raw_b64 == attestation_b.public_key_raw_b64:
        raise BountyGateError("Two-Person Auth Violation: two credentials must not share the same key material.")
    if attestation_a.public_key_raw_b64 != expected_pub_a or attestation_b.public_key_raw_b64 != expected_pub_b:
        raise BountyGateError("Two-Person Auth Violation: presented public key does not match pinned credential.")

    # 4. Nonce & expiry validation
    if expires_at_unix < issued_at_unix:
        raise BountyGateError("Two-Person Auth Violation: expires_at_unix precedes issued_at_unix.")
    if (expires_at_unix - issued_at_unix) > max_ttl_seconds:
        raise BountyGateError(
            f"Two-Person Auth Violation: authorization window exceeds max_ttl_seconds ({max_ttl_seconds}s)."
        )
    if current_unix < issued_at_unix or current_unix > expires_at_unix:
        raise BountyGateError("Two-Person Auth Violation: authorization payload is expired or not yet valid.")

    # 3. Explicit transaction payload binding + Ed25519 signature verification
    tx_bytes = build_two_person_signing_payload(
        chain_id=chain_id,
        contract_address=contract_address,
        operation_type=operation_type,
        destination=destination,
        amount_base_units=amount_base_units,
        nonce=nonce,
        issued_at_unix=issued_at_unix,
        expires_at_unix=expires_at_unix,
    )
    tx_binding_sha256 = hashlib.sha256(tx_bytes).hexdigest()

    # 5. Replay protection check
    norm_contract = _normalize_evm_address(contract_address, "contract_address")
    replay_nonce_key = f"nonce:{chain_id}:{norm_contract}:{nonce.strip()}"
    replay_digest_key = f"tx:{tx_binding_sha256}"
    if replay_nonce_key in consumed_replay_keys or replay_digest_key in consumed_replay_keys:
        raise BountyGateError("Two-Person Auth Violation: replay detected on previously consumed nonce/payload.")

    for label, att in (("signer_a", attestation_a), ("signer_b", attestation_b)):
        try:
            pub_raw = base64.b64decode(att.public_key_raw_b64, validate=True)
            sig_raw = base64.b64decode(att.signature_b64, validate=True)
            pub_key = Ed25519PublicKey.from_public_bytes(pub_raw)
            pub_key.verify(sig_raw, tx_bytes)
        except (ValueError, InvalidSignature) as exc:
            raise BountyGateError(
                f"Two-Person Auth Violation: invalid Ed25519 signature for {label} ('{att.signer_id}')."
            ) from exc

    consumed_replay_keys.add(replay_nonce_key)
    consumed_replay_keys.add(replay_digest_key)

    return {
        "authorized": True,
        "signer_a_id": id_a,
        "signer_b_id": id_b,
        "credential_a_id": cred_a,
        "credential_b_id": cred_b,
        "tx_binding_sha256": tx_binding_sha256,
        "nonce": nonce.strip(),
    }


# ==============================================================================
# Technical Correction B: Verified Token Contract Precision (USDC vs Arbitrary ERC-20)
# ==============================================================================
def verify_token_decimal_precision(
    *,
    chain_id: int,
    token_address: str,
    human_amount: str | Decimal,
    onchain_queried_decimals: Optional[int],
    assumed_decimals: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Verifies token decimal precision against the actual contract deployment per chain:
      - Canonical Base Mainnet / Base Sepolia USDC MUST equal 6 decimals (1 USDC = 10^6 base units).
      - Arbitrary ERC-20 contracts MUST provide `onchain_queried_decimals` from `decimals()`;
        assuming 6 or 18 decimals without contract verification fails closed.
    """
    if isinstance(chain_id, bool) or not isinstance(chain_id, int) or chain_id <= 0:
        raise BountyGateError("Invalid chain_id for token precision verification.")
    norm_token = _normalize_evm_address(token_address, "token_address")

    if isinstance(onchain_queried_decimals, bool) or not isinstance(onchain_queried_decimals, int):
        raise BountyGateError(
            "Token Precision Violation: onchain_queried_decimals must be queried from the deployed token contract; "
            "never assume ERC-20 decimals without verification."
        )
    if onchain_queried_decimals < 0 or onchain_queried_decimals > 36:
        raise BountyGateError(f"Out-of-range ERC-20 decimals value: {onchain_queried_decimals}.")

    canonical_key = (chain_id, norm_token)
    is_canonical_usdc = canonical_key in CANONICAL_USDC_CONTRACTS
    if is_canonical_usdc and onchain_queried_decimals != 6:
        raise BountyGateError(
            f"Canonical USDC Precision Violation on chain {chain_id} ({norm_token}): "
            f"expected 6 decimals (10^6), got {onchain_queried_decimals}."
        )

    if assumed_decimals is not None and assumed_decimals != onchain_queried_decimals:
        raise BountyGateError(
            f"Token Precision Mismatch: caller assumed {assumed_decimals} decimals, "
            f"but deployed contract {norm_token} on chain {chain_id} uses {onchain_queried_decimals} decimals."
        )

    try:
        dec_amount = human_amount if isinstance(human_amount, Decimal) else Decimal(str(human_amount))
    except InvalidOperation as exc:
        raise BountyGateError(f"Invalid token amount '{human_amount}': {exc}") from exc

    if not dec_amount.is_finite() or dec_amount < Decimal("0"):
        raise BountyGateError("Token amount must be finite and non-negative.")

    scale = Decimal(10) ** onchain_queried_decimals
    scaled = dec_amount * scale
    if scaled != scaled.to_integral_value():
        raise BountyGateError(
            f"Token amount '{dec_amount}' exceeds {onchain_queried_decimals}-decimal precision of contract {norm_token}."
        )

    return {
        "chain_id": chain_id,
        "token_address": norm_token,
        "is_canonical_usdc": is_canonical_usdc,
        "verified_decimals": onchain_queried_decimals,
        "human_amount": str(dec_amount),
        "base_units": int(scaled),
    }


# ==============================================================================
# Technical Correction C: Full-Operation-Context Deterministic Idempotency
# ==============================================================================
def derive_contextual_idempotency_key(
    *,
    chain_id: int,
    contract_address: str,
    operation_type: str,
    nonce: str | int,
    destination: str,
    amount_base_units: int,
    proof_block_hash: Optional[str] = None,
) -> str:
    """
    Derives a deterministic RFC 4122 UUID v4 idempotency key bound to the complete
    operation context rather than `sha256(blockHash)` alone:
      (chain_id, contract_address, operation_type, nonce, destination, amount_base_units[, proof_block_hash])
    """
    if isinstance(chain_id, bool) or not isinstance(chain_id, int) or chain_id <= 0:
        raise BountyGateError("chain_id must be a positive integer for idempotency derivation.")
    norm_contract = _normalize_evm_address(contract_address, "contract_address")
    norm_dest = _normalize_evm_address(destination, "destination")

    clean_op = (operation_type or "").strip()
    if not clean_op:
        raise BountyGateError("operation_type must be non-empty for idempotency derivation.")

    if isinstance(nonce, bool) or nonce is None or str(nonce).strip() == "":
        raise BountyGateError("nonce must be explicitly provided for idempotency derivation.")
    norm_nonce = str(nonce).strip()

    if isinstance(amount_base_units, bool) or not isinstance(amount_base_units, int) or amount_base_units < 0:
        raise BountyGateError("amount_base_units must be a non-negative integer.")

    context_obj: Dict[str, Any] = {
        "domain": "qf.contextual_idempotency.v1",
        "chain_id": chain_id,
        "contract_address": norm_contract,
        "operation_type": clean_op,
        "nonce": norm_nonce,
        "destination": norm_dest,
        "amount_base_units": amount_base_units,
    }
    if proof_block_hash is not None:
        clean_bh = proof_block_hash.strip().lower()
        if not _BLOCK_HASH_RE.match(clean_bh):
            raise BountyGateError(f"Invalid 32-byte 0x-prefixed proof_block_hash: {proof_block_hash!r}")
        context_obj["proof_block_hash"] = clean_bh

    digest = bytearray(hashlib.sha256(_canonical_json_bytes(context_obj)).digest()[:16])
    # Set RFC 4122 version 4 (0100xxxx) and variant 1 (10xxxxxx) bits deterministically
    digest[6] = (digest[6] & 0x0F) | 0x40
    digest[8] = (digest[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(digest)))


# ==============================================================================
# Technical Correction D: Context-Dependent Severity Classification
# ==============================================================================
def assess_contextual_severity(
    *,
    reachable_functionality: str,
    required_attacker_privilege: str,
    compensating_controls: Sequence[str],
    theoretical_max_exposure_usd: float,
    realistic_reachable_exposure_usd: float,
    exploitability: str,
    program_max_severity_for_class: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Evaluates severity from all 6 contextual factors — never auto-classifying
    missing dual authorization as Critical without unmitigated reachable loss.
    """
    if (
        not math.isfinite(theoretical_max_exposure_usd)
        or not math.isfinite(realistic_reachable_exposure_usd)
        or theoretical_max_exposure_usd < 0.0
        or realistic_reachable_exposure_usd < 0.0
    ):
        raise BountyGateError("Economic exposure figures must be finite and >= 0.0.")
    if realistic_reachable_exposure_usd > theoretical_max_exposure_usd:
        raise BountyGateError(
            "realistic_reachable_exposure_usd cannot exceed theoretical_max_exposure_usd."
        )

    valid_reachability = {
        "unrestricted_external",
        "privileged_mutable",
        "timelocked_or_guarded",
        "paused_or_unreachable",
        "view_only",
    }
    if reachable_functionality not in valid_reachability:
        raise BountyGateError(f"Unsupported reachable_functionality: {reachable_functionality!r}")

    valid_privileges = {
        "unauthenticated",
        "ordinary_user",
        "compromised_single_operator",
        "multi_party_collusion",
    }
    if required_attacker_privilege not in valid_privileges:
        raise BountyGateError(f"Unsupported required_attacker_privilege: {required_attacker_privilege!r}")

    valid_exploitability = {
        "deterministic_single_tx",
        "conditional_multi_step",
        "unlikely_precondition",
    }
    if exploitability not in valid_exploitability:
        raise BountyGateError(f"Unsupported exploitability: {exploitability!r}")

    # Baseline rank from reachable functionality & realistic economic loss
    if reachable_functionality in {"paused_or_unreachable", "view_only"} or realistic_reachable_exposure_usd == 0.0:
        rank = SEVERITY_RANK["Informational"] if reachable_functionality == "view_only" else SEVERITY_RANK["Low"]
    elif realistic_reachable_exposure_usd >= 100_000.0 and reachable_functionality == "unrestricted_external":
        rank = SEVERITY_RANK["Critical"]
    elif realistic_reachable_exposure_usd >= 25_000.0:
        rank = SEVERITY_RANK["High"]
    elif realistic_reachable_exposure_usd >= 1_000.0:
        rank = SEVERITY_RANK["Medium"]
    else:
        rank = SEVERITY_RANK["Low"]

    # Adjust for required attacker privileges (single compromised operator != unauthenticated Critical by default)
    if required_attacker_privilege == "compromised_single_operator" and rank == SEVERITY_RANK["Critical"]:
        rank -= 1
    elif required_attacker_privilege == "multi_party_collusion":
        rank = min(rank, SEVERITY_RANK["Medium"])

    # Adjust for compensating controls (timelock, velocity caps, destination allowlist, pause)
    unique_controls = {c.strip() for c in compensating_controls if c and c.strip()}
    if len(unique_controls) >= 2:
        rank = max(SEVERITY_RANK["Low"], rank - 1)
    elif len(unique_controls) == 1 and rank == SEVERITY_RANK["Critical"]:
        rank -= 1

    # Adjust for exploitability
    if exploitability == "unlikely_precondition":
        rank = max(SEVERITY_RANK["Low"], rank - 1)

    # Apply program-specific rubric cap if specified
    if program_max_severity_for_class is not None:
        if program_max_severity_for_class not in SEVERITY_RANK:
            raise BountyGateError(
                f"Invalid program_max_severity_for_class: {program_max_severity_for_class!r}"
            )
        rank = min(rank, SEVERITY_RANK[program_max_severity_for_class])

    severity = RANK_TO_SEVERITY[rank]
    return {
        "severity": severity,
        "theoretical_max_exposure_usd": round(theoretical_max_exposure_usd, 2),
        "realistic_reachable_exposure_usd": round(realistic_reachable_exposure_usd, 2),
        "compensating_controls_count": len(unique_controls),
        "required_attacker_privilege": required_attacker_privilege,
        "reachable_functionality": reachable_functionality,
        "exploitability": exploitability,
        "program_rubric_cap_applied": program_max_severity_for_class,
    }


# ==============================================================================
# Acceptance Gates: QF-BOUNTY-01, QF-BOUNTY-02, QF-BOUNTY-03
# ==============================================================================
def evaluate_qf_bounty_01_authorization(
    *,
    program_name: str,
    program_scope_url: str,
    scope_verified_at_utc: str,
    target_identifier: str,
    authorized_targets: Sequence[str],
    testing_environment: str,
    permitted_methods_verified: bool,
    autonomous_exploitation_enabled: bool = False,
) -> Dict[str, Any]:
    """
    QF-BOUNTY-01 — Authorization Integrity:
    No analysis or reproduction workflow proceeds unless the target, dated scope proof,
    and local-only permitted testing environment are explicitly authorized.
    """
    clean_program = (program_name or "").strip()
    clean_url = (program_scope_url or "").strip()
    clean_target = (target_identifier or "").strip()
    if not clean_program or not clean_url or not clean_target:
        raise BountyGateError(
            "QF-BOUNTY-01 FAIL: program_name, program_scope_url, and target_identifier are required."
        )
    scope_dt = _parse_utc_iso(scope_verified_at_utc, "scope_verified_at_utc")

    normalized_scope = {t.strip() for t in authorized_targets if t and t.strip()}
    if clean_target not in normalized_scope:
        raise BountyGateError(
            f"QF-BOUNTY-01 FAIL: target '{clean_target}' is not listed in authorized program scope."
        )
    if testing_environment not in ALLOWED_LOCAL_TEST_ENVIRONMENTS:
        raise BountyGateError(
            f"QF-BOUNTY-01 FAIL: testing_environment '{testing_environment}' is prohibited; "
            f"must be one of {sorted(ALLOWED_LOCAL_TEST_ENVIRONMENTS)}."
        )
    if permitted_methods_verified is not True:
        raise BountyGateError("QF-BOUNTY-01 FAIL: permitted_methods_verified must be explicitly True.")
    if autonomous_exploitation_enabled:
        raise BountyGateError("QF-BOUNTY-01 FAIL: autonomous exploitation is strictly prohibited.")

    return {
        "gate_id": "QF-BOUNTY-01",
        "status": "PASS",
        "program_name": clean_program,
        "target_identifier": clean_target,
        "scope_verified_at_utc": scope_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "testing_environment": testing_environment,
    }


def evaluate_qf_bounty_02_evidence(
    *,
    source_files_bytes: Mapping[str, bytes],
    claimed_source_sha256: Mapping[str, str],
    vulnerable_function: str,
    missing_security_invariant: str,
    reproducer_run_digests: Sequence[str],
    baseline_behavior_established: bool,
    remediation_regression_restores_invariant: bool,
    theoretical_max_exposure_usd: float,
    realistic_reachable_exposure_usd: float,
    provenance_receipt_bytes: bytes,
    claimed_provenance_receipt_sha256: str,
) -> Dict[str, Any]:
    """
    QF-BOUNTY-02 — Evidence Integrity:
    Independently recomputes source SHA-256 digests, verifies named vulnerable function
    and missing invariant, requires deterministic local reproduction across >= 2 runs,
    requires baseline + remediation regression proof, validates realistic <= theoretical
    exposure, and verifies the preserved provenance receipt digest.
    """
    if not source_files_bytes or not claimed_source_sha256:
        raise BountyGateError("QF-BOUNTY-02 FAIL: source_files_bytes and claimed_source_sha256 must be non-empty.")
    if set(source_files_bytes.keys()) != set(claimed_source_sha256.keys()):
        raise BountyGateError("QF-BOUNTY-02 FAIL: mismatch between provided source files and claimed hash keys.")

    recomputed_hashes: Dict[str, str] = {}
    for rel_path, raw_bytes in source_files_bytes.items():
        if not isinstance(raw_bytes, (bytes, bytearray)):
            raise BountyGateError(f"QF-BOUNTY-02 FAIL: source '{rel_path}' must be raw bytes.")
        actual_sha = hashlib.sha256(raw_bytes).hexdigest()
        expected_sha = claimed_source_sha256[rel_path].strip().lower()
        if actual_sha != expected_sha:
            raise BountyGateError(
                f"QF-BOUNTY-02 FAIL: recomputed SHA-256 mismatch for '{rel_path}' "
                f"(expected {expected_sha}, got {actual_sha})."
            )
        recomputed_hashes[rel_path] = actual_sha

    clean_fn = (vulnerable_function or "").strip()
    clean_inv = (missing_security_invariant or "").strip()
    if not clean_fn or not clean_inv:
        raise BountyGateError(
            "QF-BOUNTY-02 FAIL: vulnerable_function and missing_security_invariant must be explicitly identified."
        )

    if len(reproducer_run_digests) < 2:
        raise BountyGateError(
            "QF-BOUNTY-02 FAIL: reproducer determinism requires at least 2 repeated local run digests."
        )
    normalized_runs = [d.strip().lower() for d in reproducer_run_digests]
    if any(not _HEX_DIGEST_RE.match(d) for d in normalized_runs):
        raise BountyGateError("QF-BOUNTY-02 FAIL: reproducer_run_digests must be valid 64-char SHA-256 hex digests.")
    if len(set(normalized_runs)) != 1:
        raise BountyGateError(
            "QF-BOUNTY-02 FAIL: non-deterministic reproducer output across repeated local runs."
        )

    if baseline_behavior_established is not True:
        raise BountyGateError("QF-BOUNTY-02 FAIL: baseline behavior before remediation must be established.")
    if remediation_regression_restores_invariant is not True:
        raise BountyGateError(
            "QF-BOUNTY-02 FAIL: remediation regression test must demonstrate restored security invariant."
        )

    if (
        not math.isfinite(theoretical_max_exposure_usd)
        or not math.isfinite(realistic_reachable_exposure_usd)
        or theoretical_max_exposure_usd < 0.0
        or realistic_reachable_exposure_usd < 0.0
        or realistic_reachable_exposure_usd > theoretical_max_exposure_usd
    ):
        raise BountyGateError(
            "QF-BOUNTY-02 FAIL: invalid economic impact bounds (require 0 <= realistic <= theoretical)."
        )

    if not provenance_receipt_bytes:
        raise BountyGateError("QF-BOUNTY-02 FAIL: preserved provenance_receipt_bytes cannot be empty.")
    actual_receipt_sha = hashlib.sha256(provenance_receipt_bytes).hexdigest()
    if actual_receipt_sha != (claimed_provenance_receipt_sha256 or "").strip().lower():
        raise BountyGateError("QF-BOUNTY-02 FAIL: preserved provenance receipt SHA-256 mismatch.")

    return {
        "gate_id": "QF-BOUNTY-02",
        "status": "PASS",
        "verified_sources_count": len(recomputed_hashes),
        "vulnerable_function": clean_fn,
        "missing_security_invariant": clean_inv,
        "deterministic_reproducer_sha256": normalized_runs[0],
        "provenance_receipt_sha256": actual_receipt_sha,
    }


def evaluate_qf_bounty_03_disclosure(
    *,
    dossier_markdown: str,
    third_party_pii_cleared: bool,
    program_disclosure_rules_confirmed: bool,
    human_submission_approved: bool,
    human_approver_id: str,
    approved_at_utc: str,
) -> Dict[str, Any]:
    """
    QF-BOUNTY-03 — Disclosure Integrity:
    No submission occurs without mandatory human approval, PrivacyFilter verification
    (zero leaked secrets/PII/internal paths), absence of live treasury-drain commands,
    and explicit confirmation of program disclosure rules.
    """
    if not isinstance(dossier_markdown, str) or not dossier_markdown.strip():
        raise BountyGateError("QF-BOUNTY-03 FAIL: dossier_markdown cannot be empty.")

    _, redactions_needed = PrivacyFilter.sanitize(dossier_markdown)
    if redactions_needed > 0:
        raise BountyGateError(
            f"QF-BOUNTY-03 FAIL: dossier contains {redactions_needed} unsanitized secret/PII/internal-host pattern(s)."
        )

    for rule_name, pattern in _LIVE_EXPLOIT_COMMAND_PATTERNS:
        if pattern.search(dossier_markdown):
            raise BountyGateError(
                f"QF-BOUNTY-03 FAIL: dossier includes prohibited operational live-exploitation instruction ({rule_name})."
            )

    if third_party_pii_cleared is not True:
        raise BountyGateError("QF-BOUNTY-03 FAIL: third_party_pii_cleared must be explicitly True.")
    if program_disclosure_rules_confirmed is not True:
        raise BountyGateError("QF-BOUNTY-03 FAIL: program_disclosure_rules_confirmed must be explicitly True.")
    if human_submission_approved is not True:
        raise BountyGateError(
            "QF-BOUNTY-03 FAIL: mandatory human submission approval has not been granted."
        )

    clean_approver = (human_approver_id or "").strip().lower()
    if clean_approver not in ALLOWED_HUMAN_APPROVERS:
        raise BountyGateError("QF-BOUNTY-03 FAIL: human_approver_id must be an authorized human Operator.")
    approved_dt = _parse_utc_iso(approved_at_utc, "approved_at_utc")

    return {
        "gate_id": "QF-BOUNTY-03",
        "status": "PASS",
        "human_approver_id": clean_approver,
        "approved_at_utc": approved_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "privacy_clean": True,
        "live_drain_instructions_absent": True,
    }


def evaluate_sovereign_bounty_gates(
    *,
    authorization_kwargs: Mapping[str, Any],
    evidence_kwargs: Mapping[str, Any],
    disclosure_kwargs: Mapping[str, Any],
) -> Dict[str, Any]:
    """Evaluates QF-BOUNTY-01, QF-BOUNTY-02, and QF-BOUNTY-03 sequentially fail-closed."""
    g1 = evaluate_qf_bounty_01_authorization(**authorization_kwargs)
    g2 = evaluate_qf_bounty_02_evidence(**evidence_kwargs)
    g3 = evaluate_qf_bounty_03_disclosure(**disclosure_kwargs)
    return {
        "submission_admitted": True,
        "gates": {
            "QF-BOUNTY-01": g1,
            "QF-BOUNTY-02": g2,
            "QF-BOUNTY-03": g3,
        },
    }
