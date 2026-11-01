package quantumflex.legal

import rego.v1

# ==============================================================================
# QUANTUMFLEX LEGAL & OPERATIONAL ASSURANCE LAYER (QF-LOAL)
# Standard: QF-LEGAL-001 — Authorized Operation Invariant
#
# NO PRIVILEGED OPERATION WITHOUT:
#   1. Identifiable device.
#   2. Authenticated operator.
#   3. Valid authorization (not PENDING, SUSPENDED, REVOKED, or EXPIRED).
#   4. Permitted operational purpose & operation.
#   5. Required consent or documented lawful basis.
#   6. Verified software provenance.
#   7. Auditable authorization decision.
#
# IF ANY REQUIRED CONDITION FAILS:
#   DENY, LOG, PRESERVE EVIDENCE, PREVENT PRIVILEGED EXECUTION.
# ==============================================================================

default allow := false
default verdict := "DENY"
default quarantine := false
default reason := "Default deny (fail-closed)"

# Helper checks
device_id := object.get(input, "device_id", "")
operator_id := object.get(input, "operator_id", "")
auth_status := object.get(input, "authorization_status", "PENDING")
is_expired := object.get(input, "is_expired", false)
is_revoked := object.get(input, "is_revoked", false)
signature_verified := object.get(input, "signature_verified", false)
authenticated := object.get(input, "authenticated", false)
purpose := object.get(input, "purpose", "")
permitted_purposes := object.get(input, "permitted_purposes", [])
operation := object.get(input, "operation", "")
permitted_operations := object.get(input, "permitted_operations", [])
consent_valid := object.get(input, "consent_valid", false)
lawful_basis := object.get(input, "lawful_basis", "")
provenance_verified := object.get(input, "provenance_verified", false)
provenance_mismatch := object.get(input, "provenance_mismatch", false)
audit_logged := object.get(input, "audit_logged", false)
privacy_optout := object.get(input, "privacy_optout", false)

# 1. Device identification
device_identified if {
    device_id != ""
    device_id != "unregistered"
    device_id != "unknown"
}

# 2. Operator authentication
operator_authenticated if {
    operator_id != ""
    signature_verified == true
}

operator_authenticated if {
    operator_id != ""
    authenticated == true
}

# 3. Valid authorization status
authorization_valid if {
    auth_status == "AUTHORIZED"
    is_expired == false
    is_revoked == false
}

# 4. Permitted operational purpose and operation
purpose_permitted if {
    permitted_purposes[_] == "*"
}

purpose_permitted if {
    permitted_purposes[_] == purpose
}

operation_permitted if {
    permitted_operations[_] == "*"
}

operation_permitted if {
    permitted_operations[_] == operation
}

# 5. Lawful basis or consent
basis_valid if {
    consent_valid == true
}

basis_valid if {
    lawful_basis != ""
}

# 6. Software provenance
provenance_valid if {
    provenance_verified == true
    provenance_mismatch == false
}

# 7. Auditable decision
audit_valid if {
    audit_logged == true
}

# Quarantine condition: Software tampering or provenance mismatch detected
quarantine if {
    provenance_mismatch == true
}

# Admit condition: ALL seven requirements strictly met, zero privacy opt-out breach
allow if {
    device_identified
    operator_authenticated
    authorization_valid
    purpose_permitted
    operation_permitted
    basis_valid
    provenance_valid
    audit_valid
    privacy_optout == false
}

# Verdict resolution
verdict := "QUARANTINE" if {
    quarantine == true
} else := "ADMIT" if {
    allow == true
} else := "DENY"

# Detailed failure reason resolution
reason := "ADMIT: All QF-LEGAL-001 conditions satisfied" if {
    allow == true
} else := "QUARANTINE: Software provenance mismatch or tampering detected" if {
    quarantine == true
} else := "DENY: Privacy opt-out flag detected in payload" if {
    privacy_optout == true
} else := "DENY: Unregistered or missing device identity" if {
    not device_identified
} else := "DENY: Unauthenticated operator or invalid signature" if {
    not operator_authenticated
} else := "DENY: Device authorization revoked" if {
    is_revoked == true
} else := "DENY: Device authorization expired" if {
    is_expired == true
} else := "DENY: Device authorization suspended or pending" if {
    auth_status != "AUTHORIZED"
} else := "DENY: Requested purpose not permitted" if {
    not purpose_permitted
} else := "DENY: Requested operation not permitted" if {
    not operation_permitted
} else := "DENY: Missing consent or lawful operational basis" if {
    not basis_valid
} else := "DENY: Unverified software provenance" if {
    not provenance_valid
} else := "DENY: Audit record not committed" if {
    not audit_valid
} else := "DENY: General authorization boundary failure"

# Consolidated evaluation document
evaluation := {
    "allow": allow,
    "verdict": verdict,
    "quarantine": quarantine,
    "reason": reason,
    "policy_version": "QF-LEGAL-001/v1"
}
