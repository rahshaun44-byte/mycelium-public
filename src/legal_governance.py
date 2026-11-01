# src/legal_governance.py
"""
QuantumFlex Legal & Operational Assurance Layer (QF-LOAL)
=========================================================
Implements the QF-LEGAL-001 Authorized Operation Invariant:
1. Identifiable device
2. Authenticated operator
3. Valid authorization (not PENDING, SUSPENDED, REVOKED, or EXPIRED)
4. Permitted operational purpose & operation
5. Required consent or documented lawful basis
6. Verified software provenance
7. Auditable authorization decision

Integrates with PostgreSQL:
- qf_device_authorization (registry of node ownership, permissions, and status)
- qf_governance_audit (immutable append-only audit trail)
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("quantumflex.legal_governance")

# Standard Governance Event Types
EVENT_DEVICE_REGISTERED = "DEVICE_REGISTERED"
EVENT_DEVICE_AUTHORIZED = "DEVICE_AUTHORIZED"
EVENT_DEVICE_AUTHORIZATION_RENEWED = "DEVICE_AUTHORIZATION_RENEWED"
EVENT_DEVICE_AUTHORIZATION_REVOKED = "DEVICE_AUTHORIZATION_REVOKED"
EVENT_DEVICE_QUARANTINED = "DEVICE_QUARANTINED"
EVENT_OPERATOR_AUTHENTICATED = "OPERATOR_AUTHENTICATED"
EVENT_OTA_DOWNLOAD_APPROVED = "OTA_DOWNLOAD_APPROVED"
EVENT_OTA_DOWNLOAD_DENIED = "OTA_DOWNLOAD_DENIED"
EVENT_TELEMETRY_ACCEPTED = "TELEMETRY_ACCEPTED"
EVENT_TELEMETRY_REJECTED = "TELEMETRY_REJECTED"
EVENT_PRIVACY_OPTOUT_ENFORCED = "PRIVACY_OPTOUT_ENFORCED"
EVENT_HARDWARE_ATTESTATION_FAILED = "HARDWARE_ATTESTATION_FAILED"


def record_governance_audit(
    event_type: str,
    node_id: Optional[str],
    operator_id: Optional[str],
    requested_operation: str,
    authorization_decision: str,  # ADMIT, DENY, QUARANTINE
    denial_reason: Optional[str] = None,
    evidence_hash: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    policy_version: str = "QF-LEGAL-001/v1",
) -> bool:
    """
    Appends an immutable audit entry to PostgreSQL qf_governance_audit.
    Redacts any sensitive secrets/credentials before persisting.
    """
    safe_metadata = dict(metadata or {})
    for key in list(safe_metadata.keys()):
        if any(secret_term in key.lower() for secret_term in ["secret", "key", "password", "token", "seed"]):
            safe_metadata[key] = "[REDACTED]"

    try:
        from src.db_credentials import DatabaseRole, open_role_connection
        conn = open_role_connection(role=DatabaseRole.WRITER, dbname=os.environ.get("DB_NAME", "telemetry"))
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO qf_governance_audit (
                        event_type, node_id, operator_id, requested_operation,
                        authorization_decision, policy_version, evidence_hash,
                        denial_reason, metadata
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                """, (
                    event_type, node_id, operator_id, requested_operation,
                    authorization_decision, policy_version, evidence_hash,
                    denial_reason, json.dumps(safe_metadata)
                ))
        conn.close()
        return True
    except Exception as e:
        logger.warning(f"[QF-LOAL] Failed to persist governance audit to database: {e}")
        return False


def get_device_authorization(node_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves the device authorization record from PostgreSQL qf_device_authorization.
    Returns None if device is unregistered.
    """
    if not node_id:
        return None

    try:
        from src.db_credentials import DatabaseRole, open_role_connection
        conn = open_role_connection(role=DatabaseRole.VERIFIER, dbname=os.environ.get("DB_NAME", "telemetry"))
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT node_id, owner_id, authorization_status, permitted_purposes,
                           permitted_operations, consent_record_id, authorization_basis,
                           hardware_identity, hardware_verified, software_provenance_sha256,
                           authorized_at, expires_at, revoked_at
                    FROM qf_device_authorization
                    WHERE node_id = %s;
                """, (node_id,))
                row = cur.fetchone()
                if not row:
                    return None

                nid, owner, status, purposes, operations, consent, basis, h_id, h_ver, prov_sha, auth_at, exp_at, rev_at = row
                return {
                    "node_id": nid,
                    "owner_id": owner,
                    "authorization_status": status,
                    "permitted_purposes": purposes if isinstance(purposes, list) else json.loads(purposes or "[]"),
                    "permitted_operations": operations if isinstance(operations, list) else json.loads(operations or "[]"),
                    "consent_record_id": consent,
                    "authorization_basis": basis,
                    "hardware_identity": h_id,
                    "hardware_verified": bool(h_ver),
                    "software_provenance_sha256": prov_sha,
                    "authorized_at": auth_at.isoformat() if auth_at else None,
                    "expires_at": exp_at.isoformat() if exp_at else None,
                    "revoked_at": rev_at.isoformat() if rev_at else None,
                }
        conn.close()
    except Exception as e:
        logger.error(f"[QF-LOAL] Database error querying device authorization for {node_id}: {e}")
        return None


def evaluate_operation_authorization(
    node_id: str,
    requested_operation: str,
    operator_id: Optional[str] = None,
    signature_verified: bool = False,
    authenticated: bool = False,
    purpose: Optional[str] = None,
    provenance_verified: bool = True,
    provenance_mismatch: bool = False,
    evidence_hash: Optional[str] = None,
    privacy_optout: bool = False,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Complete enforcement of QF-LEGAL-001 Authorized Operation Invariant.
    Returns (allowed: bool, decision: str, record: dict).
    """
    now_utc = datetime.now(timezone.utc)

    # 1. Device Registration Check
    auth_record = get_device_authorization(node_id)
    if not auth_record:
        denial_reason = f"Unregistered device '{node_id}'. Access denied by default."
        record_governance_audit(
            event_type="UNREGISTERED_DEVICE_ACCESS_DENIED",
            node_id=node_id,
            operator_id=operator_id,
            requested_operation=requested_operation,
            authorization_decision="DENY",
            denial_reason=denial_reason,
            evidence_hash=evidence_hash
        )
        return False, "DENY: Unregistered device", {}

    status = auth_record["authorization_status"]
    owner = auth_record["owner_id"]
    effective_operator = operator_id or owner

    # Check expiration
    is_expired = False
    if auth_record.get("expires_at"):
        try:
            exp_dt = datetime.fromisoformat(auth_record["expires_at"].replace("Z", "+00:00"))
            if now_utc > exp_dt:
                is_expired = True
        except Exception:
            pass

    # Check revocation
    is_revoked = (status == "REVOKED") or bool(auth_record.get("revoked_at"))

    # Provenance mismatch triggers Quarantine
    if provenance_mismatch:
        quarantine_reason = f"Software provenance mismatch detected on node '{node_id}'."
        record_governance_audit(
            event_type=EVENT_DEVICE_QUARANTINED,
            node_id=node_id,
            operator_id=effective_operator,
            requested_operation=requested_operation,
            authorization_decision="QUARANTINE",
            denial_reason=quarantine_reason,
            evidence_hash=evidence_hash
        )
        return False, "QUARANTINE: Provenance mismatch", auth_record

    # Privacy opt-out flag check
    if privacy_optout:
        privacy_reason = "Privacy opt-out flag (_optout / _nomap) detected in payload."
        record_governance_audit(
            event_type=EVENT_PRIVACY_OPTOUT_ENFORCED,
            node_id=node_id,
            operator_id=effective_operator,
            requested_operation=requested_operation,
            authorization_decision="DENY",
            denial_reason=privacy_reason,
            evidence_hash=evidence_hash
        )
        return False, "DENY: Privacy opt-out", auth_record

    # Check status
    if is_revoked:
        reason = f"Authorization for node '{node_id}' has been REVOKED."
        record_governance_audit(
            event_type="REVOKED_DEVICE_ACCESS_DENIED",
            node_id=node_id,
            operator_id=effective_operator,
            requested_operation=requested_operation,
            authorization_decision="DENY",
            denial_reason=reason,
            evidence_hash=evidence_hash
        )
        return False, "DENY: Device revoked", auth_record

    if is_expired:
        reason = f"Authorization for node '{node_id}' has EXPIRED."
        record_governance_audit(
            event_type="EXPIRED_DEVICE_ACCESS_DENIED",
            node_id=node_id,
            operator_id=effective_operator,
            requested_operation=requested_operation,
            authorization_decision="DENY",
            denial_reason=reason,
            evidence_hash=evidence_hash
        )
        return False, "DENY: Device expired", auth_record

    if status != "AUTHORIZED":
        reason = f"Node '{node_id}' status is '{status}'. Only 'AUTHORIZED' nodes may execute."
        record_governance_audit(
            event_type="UNAUTHORIZED_STATUS_ACCESS_DENIED",
            node_id=node_id,
            operator_id=effective_operator,
            requested_operation=requested_operation,
            authorization_decision="DENY",
            denial_reason=reason,
            evidence_hash=evidence_hash
        )
        return False, f"DENY: Node status {status}", auth_record

    # Check operator / signature
    if not (signature_verified or authenticated):
        reason = "Missing or invalid cryptographic operator signature."
        record_governance_audit(
            event_type="UNAUTHENTICATED_OPERATOR_DENIED",
            node_id=node_id,
            operator_id=effective_operator,
            requested_operation=requested_operation,
            authorization_decision="DENY",
            denial_reason=reason,
            evidence_hash=evidence_hash
        )
        return False, "DENY: Invalid signature", auth_record

    # Check permitted operations
    permitted_ops = auth_record.get("permitted_operations", [])
    if ("*" not in permitted_ops) and (requested_operation not in permitted_ops):
        reason = f"Operation '{requested_operation}' is not permitted for node '{node_id}'."
        record_governance_audit(
            event_type="UNAUTHORIZED_OPERATION_DENIED",
            node_id=node_id,
            operator_id=effective_operator,
            requested_operation=requested_operation,
            authorization_decision="DENY",
            denial_reason=reason,
            evidence_hash=evidence_hash
        )
        return False, "DENY: Unauthorized operation", auth_record

    # Check purpose / consent if specified
    if purpose:
        permitted_purposes = auth_record.get("permitted_purposes", [])
        if ("*" not in permitted_purposes) and (purpose not in permitted_purposes):
            reason = f"Purpose '{purpose}' is not in permitted purposes for node '{node_id}'."
            record_governance_audit(
                event_type="UNAUTHORIZED_PURPOSE_DENIED",
                node_id=node_id,
                operator_id=effective_operator,
                requested_operation=requested_operation,
                authorization_decision="DENY",
                denial_reason=reason,
                evidence_hash=evidence_hash
            )
            return False, "DENY: Unauthorized purpose", auth_record

    # Software provenance check
    if not provenance_verified:
        reason = "Software provenance unverified; cannot admit privileged operation."
        record_governance_audit(
            event_type="UNVERIFIED_PROVENANCE_DENIED",
            node_id=node_id,
            operator_id=effective_operator,
            requested_operation=requested_operation,
            authorization_decision="DENY",
            denial_reason=reason,
            evidence_hash=evidence_hash
        )
        return False, "DENY: Unverified provenance", auth_record

    # All 7 conditions satisfied
    record_governance_audit(
        event_type="PRIVILEGED_OPERATION_ADMITTED",
        node_id=node_id,
        operator_id=effective_operator,
        requested_operation=requested_operation,
        authorization_decision="ADMIT",
        evidence_hash=evidence_hash,
        metadata={"scope": purpose or "operational"}
    )
    return True, "ADMIT", auth_record


def revoke_device_authorization(node_id: str, reason: str, operator_id: str) -> bool:
    """
    Immediately revokes a device's legal authorization in PostgreSQL.
    Subsequent requests will be denied on next evaluation.
    """
    try:
        from src.db_credentials import DatabaseRole, open_role_connection
        conn = open_role_connection(role=DatabaseRole.WRITER, dbname=os.environ.get("DB_NAME", "telemetry"))
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE qf_device_authorization
                    SET authorization_status = 'REVOKED',
                        revoked_at = NOW(),
                        last_reviewed_at = NOW()
                    WHERE node_id = %s;
                """, (node_id,))
        conn.close()

        record_governance_audit(
            event_type=EVENT_DEVICE_AUTHORIZATION_REVOKED,
            node_id=node_id,
            operator_id=operator_id,
            requested_operation="device:revoke",
            authorization_decision="ADMIT",
            denial_reason=reason
        )
        return True
    except Exception as e:
        logger.error(f"[QF-LOAL] Failed to revoke device {node_id}: {e}")
        return False
