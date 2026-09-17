package membrane.health

import rego.v1

# ═══════════════════════════════════════════════════════════════════
# QUANTUM FLEX — Membrane Health Policy
# The Biological Imperative: Autonomous Cryptographic Compliance
#
# Input: CycloneDX CBOM JSON (from CBOMkit-theia scan)
# Output: Structured verdict with per-component compliance status
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

# ── Threat Flags ─────────────────────────────────────────────────
# These are set via OPA data API by Sentinel or external threat feed.
# Default: no algorithms are compromised.
default ml_kem_compromised := false
ml_kem_compromised if data.threat_flags.ML_KEM_COMPROMISED == true

default frodokem_compromised := false
frodokem_compromised if data.threat_flags.FRODOKEM_COMPROMISED == true

# Dynamic compromised set — built from active threat flags
compromised_algorithms contains "ML-KEM-512" if ml_kem_compromised
compromised_algorithms contains "ML-KEM-768" if ml_kem_compromised
compromised_algorithms contains "ML-KEM-1024" if ml_kem_compromised
compromised_algorithms contains "FrodoKEM-640-AES" if frodokem_compromised
compromised_algorithms contains "FrodoKEM-976-AES" if frodokem_compromised
compromised_algorithms contains "FrodoKEM-1344-AES" if frodokem_compromised

# ── Per-Component Evaluation ─────────────────────────────────────
# Evaluates each cryptographic component in the CBOM

# Profile checks and compromise checks are mutually exclusive to avoid eval conflicts.
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

# ── Aggregate Verdict ────────────────────────────────────────────
# The node is TOXIC if ANY component is TOXIC

findings contains finding if {
    some comp in input.components
    comp.type == "crypto-asset"
    finding := component_verdict(comp)
}

toxic_findings contains f if {
    some f in findings
    f.status == "TOXIC"
}

default node_status := "COMPLIANT"
node_status := "TOXIC" if count(toxic_findings) > 0
node_status := "TOXIC" if count(deny) > 0

# ── Primary Decision Endpoint ────────────────────────────────────
# Query: POST /v1/data/membrane/health/verdict
verdict := {
    "node_status": node_status,
    "total_components": count(findings),
    "toxic_count": count(toxic_findings),
    "findings": findings,
    "recommended_fallback": recommended_fallback,
    "evaluated_at": input.metadata.timestamp,
}

# ── Fallback Recommendation ─────────────────────────────────────
# Verified ISO/IEC 18033-2:2006/Amd 2:2026 Profile
iso_fallback_map := {
    "ML-KEM-1024": "FrodoKEM-1344-AES",
    "ML-KEM-768": "FrodoKEM-976-AES",
    "FrodoKEM-1344-AES": "X25519",
    "FrodoKEM-976-AES": "X25519",
    "X25519": "NONE",
}

# Explicitly Isolated Draft/Experimental Profile
experimental_fallback_map := {
    "ML-KEM-512": "FrodoKEM-640-AES",
    "FrodoKEM-640-AES": "X25519",
}

# Enforce rejection if an ISO profile attempts to negotiate 640
deny contains "ISO compliance violation: FrodoKEM-640 is not an ISO standard" if {
    input.requested_profile == "iso_strict"
    input.cipher == "FrodoKEM-640-AES"
}

deny contains "ISO compliance violation: FrodoKEM-640 is not an ISO standard" if {
    input.requested_profile == "iso_strict"
    some comp in input.components
    comp.type == "crypto-asset"
    comp.cryptoProperties.algorithmProperties.algorithm == "FrodoKEM-640-AES"
}

# Dynamically match ML-KEM size variants to equivalent security-tier FrodoKEM variants
fallback_map := {
    "ML-KEM-512": "FrodoKEM-640-AES",
    "ML-KEM-768": "FrodoKEM-976-AES",
    "ML-KEM-1024": "FrodoKEM-1344-AES",
    "FrodoKEM-640-AES": "X25519",
    "FrodoKEM-976-AES": "X25519",
    "FrodoKEM-1344-AES": "X25519",
    "X25519": "NONE",
}

# ── Recovery Map (Self-Healing / Quarantine Parameters) ──────────
# Authoritative recovery parameters for the circuit breaker / quarantine state.
# The Python daemon reads these values — they are NEVER hardcoded in the binary.
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

# Strict Federal Compliance Fallback Map (FIPS 203 strict)
# Constrains fallbacks exclusively within FIPS-approved parameters; fails closed rather than switching to non-FIPS
fips_fallback_map := {
    "ML-KEM-1024": "NONE",
    "ML-KEM-768": "NONE",
    "ML-KEM-512": "NONE",
}

deny contains "FIPS compliance violation: Non-FIPS algorithm in fips_strict profile" if {
    input.requested_profile == "fips_strict"
    some comp in input.components
    comp.type == "crypto-asset"
    algo := comp.cryptoProperties.algorithmProperties.algorithm
    not algo in (quantum_safe_kem | quantum_safe_sig)
}

# Active fallback map selection based on profile
active_fallback_map := fips_fallback_map if {
    input.requested_profile == "fips_strict"
} else := iso_fallback_map if {
    input.requested_profile == "iso_strict"
} else := fallback_map

# If an active ML-KEM is toxic and FrodoKEM is healthy, pick the equivalent tier
recommended_fallback := active_fallback_map[kem] if {
    object.get(input, "requested_profile", "agility") != "fips_strict"
    count(deny) == 0
    some kem in active_kems
    kem in compromised_algorithms
    not frodokem_compromised
    active_fallback_map[kem]
}

# If FrodoKEM is also compromised, step down to approved classical (X25519)
recommended_fallback := "X25519" if {
    object.get(input, "requested_profile", "agility") != "fips_strict"
    count(deny) == 0
    some kem in active_kems
    kem in compromised_algorithms
    frodokem_compromised
}

default recommended_fallback := "NONE"

# A misspelled profile must never silently enable agility.
deny contains "Unknown compliance profile" if {
    not object.get(input, "requested_profile", "agility") in {"fips_strict", "iso_strict", "agility"}
}

# ── Inventory Completeness Checks ─────────────────────────────────
deny contains "Empty inventory: CBOM contains no cryptographic components" if {
    not input.components
}

deny contains "Empty inventory: CBOM contains no cryptographic components" if {
    count(input.components) == 0
}

deny contains "Missing crypto-assets: CBOM contains zero assessed crypto-asset components" if {
    count(input.components) > 0
    count(findings) == 0
}
