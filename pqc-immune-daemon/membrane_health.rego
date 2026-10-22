package membrane.health

import rego.v1

# ═══════════════════════════════════════════════════════════════════
# QUANTUM FLEX — Membrane Health Policy
# The Biological Imperative: Autonomous Cryptographic Compliance
#
# Authoritative States Enforced:
#   MISSING, INVALID, ERROR, UNVERIFIED, STALE, OBSERVED,
#   VERIFIED, ADMITTED, DENIED, SIMULATED, DEVELOPMENT_ONLY
#
# Core Governance Rule: ABSENCE OF EVIDENCE MUST NEVER BECOME VERIFIED.
# ═══════════════════════════════════════════════════════════════════

# ── Approved Algorithm Registry ──────────────────────────────────
# NIST FIPS 203/204/205 approved algorithms (2026 baseline)
quantum_safe_kem := {
    "ML-KEM-512",
    "ML-KEM-768",
    "ML-KEM-1024",
}

quantum_safe_sig := {
    "ML-DSA-44",
    "ML-DSA-65",
    "ML-DSA-87",
    "SLH-DSA-SHA2-128f",
    "SLH-DSA-SHA2-128s",
    "SLH-DSA-SHA2-192f",
    "SLH-DSA-SHAKE-128f",
}

# Classical algorithms permitted for hybrid mode only
classical_approved := {
    "X25519",
    "Ed25519",
    "AES-256-GCM",
    "SHA-256",
    "SHA-384",
    "SHA-512",
}

# Conservative lattice fallbacks (non-NIST but mathematically distinct)
fallback_approved := {
    "FrodoKEM-640-AES",
    "FrodoKEM-976-AES",
    "FrodoKEM-1344-AES",
}

# Union of all approved algorithms
all_approved := quantum_safe_kem | quantum_safe_sig | classical_approved | fallback_approved

# Valid compliance profiles (Task 5)
valid_profiles := {"fips_strict", "iso_strict", "agility"}

# ── Compliance Profile Validation (Task 5) ────────────────────────
deny contains "Missing compliance profile" if {
    not input.requested_profile
}

deny contains "Unknown compliance profile" if {
    input.requested_profile
    not input.requested_profile in valid_profiles
}

# ── Inventory & CBOM Completeness Checks (Task 6) ──────────────────
deny contains "Missing inventory: CBOM components array missing" if {
    not input.components
}

deny contains "Empty inventory: CBOM contains no cryptographic components" if {
    input.components
    count(input.components) == 0
}

deny contains "Missing crypto-assets: CBOM contains zero assessed crypto-asset components" if {
    input.components
    count(input.components) > 0
    count(findings) == 0
}

# ── Threat Flags Intelligence (Task 7) ─────────────────────────────
# Distinguish:
# - data.threat_flags missing/incomplete -> UNVERIFIED / deny
# - threat flag true -> COMPROMISED
# - threat flag explicitly false -> VERIFIED safe
ml_kem_compromised if {
    data.threat_flags.ML_KEM_COMPROMISED == true
}

frodokem_compromised if {
    data.threat_flags.FRODOKEM_COMPROMISED == true
}

ml_kem_verified_safe if {
    data.threat_flags.ML_KEM_COMPROMISED == false
}

frodokem_verified_safe if {
    data.threat_flags.FRODOKEM_COMPROMISED == false
}

# Active algorithm threat feed check
deny contains "Threat feed unverified: active algorithm has no threat attestation" if {
    some kem in active_kems
    kem in {"ML-KEM-512", "ML-KEM-768", "ML-KEM-1024"}
    not ml_kem_compromised
    not ml_kem_verified_safe
}

deny contains "Threat feed unverified: active algorithm has no threat attestation" if {
    some kem in active_kems
    kem in {"FrodoKEM-640-AES", "FrodoKEM-976-AES", "FrodoKEM-1344-AES"}
    not frodokem_compromised
    not frodokem_verified_safe
}

compromised_algorithms contains "ML-KEM-512" if ml_kem_compromised
compromised_algorithms contains "ML-KEM-768" if ml_kem_compromised
compromised_algorithms contains "ML-KEM-1024" if ml_kem_compromised
compromised_algorithms contains "FrodoKEM-640-AES" if frodokem_compromised
compromised_algorithms contains "FrodoKEM-976-AES" if frodokem_compromised
compromised_algorithms contains "FrodoKEM-1344-AES" if frodokem_compromised

# Profile-specific algorithm restrictions
deny contains "ISO compliance violation: FrodoKEM-640 is not an ISO standard" if {
    input.requested_profile == "iso_strict"
    some comp in input.components
    comp.type == "crypto-asset"
    comp.cryptoProperties.algorithmProperties.algorithm == "FrodoKEM-640-AES"
}

deny contains "FIPS compliance violation: Non-FIPS algorithm in fips_strict profile" if {
    input.requested_profile == "fips_strict"
    some comp in input.components
    comp.type == "crypto-asset"
    algo := comp.cryptoProperties.algorithmProperties.algorithm
    not algo in (quantum_safe_kem | quantum_safe_sig)
}

# ── Per-Component Evaluation ───────────────────────────────────────
component_verdict(comp) := {"algorithm": algo, "status": "TOXIC", "reason": "Algorithm outside fips_strict registry (FIPS 203/204/205)"} if {
    algo := comp.cryptoProperties.algorithmProperties.algorithm
    input.requested_profile == "fips_strict"
    not algo in (quantum_safe_kem | quantum_safe_sig)
} else := {"algorithm": algo, "status": "TOXIC", "reason": "Algorithm compromised"} if {
    algo := comp.cryptoProperties.algorithmProperties.algorithm
    algo in compromised_algorithms
} else := {"algorithm": algo, "status": "TOXIC", "reason": "Unknown/deprecated algorithm"} if {
    algo := comp.cryptoProperties.algorithmProperties.algorithm
    not algo in all_approved
} else := {"algorithm": algo, "status": "COMPLIANT", "reason": "Approved by algorithm policy; module validation not assessed"} if {
    algo := comp.cryptoProperties.algorithmProperties.algorithm
    algo in all_approved
}

findings contains finding if {
    some comp in input.components
    comp.type == "crypto-asset"
    finding := component_verdict(comp)
}

toxic_findings contains f if {
    some f in findings
    f.status == "TOXIC"
}

# ── Fallback Maps ──────────────────────────────────────────────────
iso_fallback_map := {
    "ML-KEM-1024": "FrodoKEM-1344-AES",
    "ML-KEM-768": "FrodoKEM-976-AES",
    "FrodoKEM-1344-AES": "X25519",
    "FrodoKEM-976-AES": "X25519",
    "X25519": "NONE",
}

fallback_map := {
    "ML-KEM-512": "FrodoKEM-640-AES",
    "ML-KEM-768": "FrodoKEM-976-AES",
    "ML-KEM-1024": "FrodoKEM-1344-AES",
    "FrodoKEM-640-AES": "X25519",
    "FrodoKEM-976-AES": "X25519",
    "FrodoKEM-1344-AES": "X25519",
    "X25519": "NONE",
}

fips_fallback_map := {
    "ML-KEM-1024": "NONE",
    "ML-KEM-768": "NONE",
    "ML-KEM-512": "NONE",
}

experimental_fallback_map := {
    "ML-KEM-512": "FrodoKEM-640-AES",
    "FrodoKEM-640-AES": "X25519",
}

recovery_map := {
    "max_retries": 3,
    "timeout_window_sec": 60,
    "quarantine_delay_ms": 5000,
    "safe_mode_cipher": "FrodoKEM-976-AES",
    "quarantine_action": "isolate_and_hold",
}

active_kems contains algo if {
    some comp in input.components
    comp.type == "crypto-asset"
    algo := comp.cryptoProperties.algorithmProperties.algorithm
    algo in (quantum_safe_kem | fallback_approved)
}

active_fallback_map := fips_fallback_map if {
    input.requested_profile == "fips_strict"
} else := iso_fallback_map if {
    input.requested_profile == "iso_strict"
} else := fallback_map if {
    input.requested_profile == "agility"
} else := {}

recommended_fallback := active_fallback_map[kem] if {
    input.requested_profile in {"iso_strict", "agility"}
    count(deny) == 0
    some kem in active_kems
    kem in compromised_algorithms
    not frodokem_compromised
    active_fallback_map[kem]
}

recommended_fallback := "X25519" if {
    input.requested_profile in {"iso_strict", "agility"}
    count(deny) == 0
    some kem in active_kems
    kem in compromised_algorithms
    frodokem_compromised
}

default recommended_fallback := "NONE"

# ── Authoritative Verification State (Task 2 & Core Governance Rule) ────
default verification_state := "UNVERIFIED"

verification_state := "MISSING" if {
    not input.components
} else := "INVALID" if {
    not input.requested_profile
} else := "INVALID" if {
    not input.requested_profile in valid_profiles
} else := "UNVERIFIED" if {
    "Threat feed unverified: active algorithm has no threat attestation" in deny
} else := "VERIFIED" if {
    count(toxic_findings) > 0
} else := "DENIED" if {
    count(deny) > 0
} else := "VERIFIED" if {
    count(findings) > 0
    count(toxic_findings) == 0
    count(deny) == 0
}

# ── Node Status (Task 6 & Task 7) ─────────────────────────────────
default node_status := "UNVERIFIED"

node_status := "TOXIC" if {
    count(toxic_findings) > 0
} else := "TOXIC" if {
    count(deny) > 0
} else := "COMPLIANT" if {
    count(findings) > 0
    count(toxic_findings) == 0
    count(deny) == 0
}

# Timestamp safe extraction (guarantees verdict is never undefined)
meta_timestamp := object.get(object.get(input, "metadata", {}), "timestamp", null)

# ── Primary Decision Endpoint ────────────────────────────────────
verdict := {
    "node_status": node_status,
    "verification_state": verification_state,
    "total_components": count(findings),
    "toxic_count": count(toxic_findings),
    "deny_reasons": deny,
    "findings": findings,
    "recommended_fallback": recommended_fallback,
    "evaluated_at": meta_timestamp,
}
