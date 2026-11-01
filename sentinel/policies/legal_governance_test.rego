package quantumflex.legal_test

import rego.v1
import data.quantumflex.legal

# Helper nominal input that satisfies all QF-LEGAL-001 conditions
nominal_input := {
    "device_id": "qfx-pixel",
    "operator_id": "rocky@qfx-pixel",
    "authorization_status": "AUTHORIZED",
    "is_expired": false,
    "is_revoked": false,
    "signature_verified": true,
    "authenticated": true,
    "purpose": "tactical-hud",
    "permitted_purposes": ["tactical-hud", "mobile-sentinel"],
    "operation": "telemetry:heartbeat",
    "permitted_operations": ["telemetry:heartbeat", "draft:approve"],
    "consent_valid": true,
    "lawful_basis": "Owner-operator direct physical consent",
    "provenance_verified": true,
    "provenance_mismatch": false,
    "audit_logged": true,
    "privacy_optout": false,
}

test_nominal_authorization_admits if {
    res := legal.evaluation with input as nominal_input
    res.allow == true
    res.verdict == "ADMIT"
    res.reason == "ADMIT: All QF-LEGAL-001 conditions satisfied"
}

test_nominal_session_only_admits if {
    input_session := object.union(nominal_input, {"signature_verified": false, "authenticated": true})
    res := legal.evaluation with input as input_session
    res.allow == true
    res.verdict == "ADMIT"
}

test_nominal_signature_only_admits if {
    input_sig := object.union(nominal_input, {"signature_verified": true, "authenticated": false})
    res := legal.evaluation with input as input_sig
    res.allow == true
    res.verdict == "ADMIT"
}

test_unregistered_device_denied if {
    bad_input := object.union(nominal_input, {"device_id": ""})
    res := legal.evaluation with input as bad_input
    res.allow == false
    res.verdict == "DENY"
    res.reason == "DENY: Unregistered or missing device identity"
}

test_revoked_device_denied if {
    bad_input := object.union(nominal_input, {"authorization_status": "REVOKED", "is_revoked": true})
    res := legal.evaluation with input as bad_input
    res.allow == false
    res.verdict == "DENY"
    res.reason == "DENY: Device authorization revoked"
}

test_expired_authorization_denied if {
    bad_input := object.union(nominal_input, {"authorization_status": "EXPIRED", "is_expired": true})
    res := legal.evaluation with input as bad_input
    res.allow == false
    res.verdict == "DENY"
    res.reason == "DENY: Device authorization expired"
}

test_suspended_device_denied if {
    bad_input := object.union(nominal_input, {"authorization_status": "SUSPENDED"})
    res := legal.evaluation with input as bad_input
    res.allow == false
    res.verdict == "DENY"
    res.reason == "DENY: Device authorization suspended or pending"
}

test_invalid_device_signature_denied if {
    bad_input := object.union(nominal_input, {"signature_verified": false, "authenticated": false})
    res := legal.evaluation with input as bad_input
    res.allow == false
    res.verdict == "DENY"
    res.reason == "DENY: Unauthenticated operator or invalid signature"
}

test_empty_operator_id_with_signature_denied if {
    bad_input := object.union(nominal_input, {"operator_id": "", "signature_verified": true, "authenticated": false})
    res := legal.evaluation with input as bad_input
    res.allow == false
    res.verdict == "DENY"
    res.reason == "DENY: Unauthenticated operator or invalid signature"
}

test_empty_operator_id_with_session_denied if {
    bad_input := object.union(nominal_input, {"operator_id": "", "signature_verified": false, "authenticated": true})
    res := legal.evaluation with input as bad_input
    res.allow == false
    res.verdict == "DENY"
    res.reason == "DENY: Unauthenticated operator or invalid signature"
}

test_unauthorized_operation_denied if {
    bad_input := object.union(nominal_input, {"operation": "privileged:destructive_wipe"})
    res := legal.evaluation with input as bad_input
    res.allow == false
    res.verdict == "DENY"
    res.reason == "DENY: Requested operation not permitted"
}

test_unauthorized_purpose_denied if {
    bad_input := object.union(nominal_input, {"purpose": "unauthorized-commercial-surveillance"})
    res := legal.evaluation with input as bad_input
    res.allow == false
    res.verdict == "DENY"
    res.reason == "DENY: Requested purpose not permitted"
}

test_missing_consent_and_lawful_basis_denied if {
    bad_input := object.union(nominal_input, {"consent_valid": false, "lawful_basis": ""})
    res := legal.evaluation with input as bad_input
    res.allow == false
    res.verdict == "DENY"
    res.reason == "DENY: Missing consent or lawful operational basis"
}

test_unverified_provenance_denied if {
    bad_input := object.union(nominal_input, {"provenance_verified": false})
    res := legal.evaluation with input as bad_input
    res.allow == false
    res.verdict == "DENY"
    res.reason == "DENY: Unverified software provenance"
}

test_provenance_mismatch_quarantines if {
    bad_input := object.union(nominal_input, {"provenance_mismatch": true})
    res := legal.evaluation with input as bad_input
    res.allow == false
    res.quarantine == true
    res.verdict == "QUARANTINE"
    res.reason == "QUARANTINE: Software provenance mismatch or tampering detected"
}

test_privacy_optout_telemetry_denied if {
    bad_input := object.union(nominal_input, {"privacy_optout": true})
    res := legal.evaluation with input as bad_input
    res.allow == false
    res.verdict == "DENY"
    res.reason == "DENY: Privacy opt-out flag detected in payload"
}

test_missing_audit_record_denied if {
    bad_input := object.union(nominal_input, {"audit_logged": false})
    res := legal.evaluation with input as bad_input
    res.allow == false
    res.verdict == "DENY"
    res.reason == "DENY: Audit record not committed"
}
