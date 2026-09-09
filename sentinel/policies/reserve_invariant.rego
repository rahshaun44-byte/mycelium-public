package quantumflex.invariant

import rego.v1

# ═══════════════════════════════════════════════════════════════════
# QUANTUM FLEX — Universal Reserve Invariant Policy (R >= O)
# The Physical Imperative: Fail-Secure Solvency & Hardware Anchoring
#
# Enforces the fundamental invariant: R >= O (Reserve >= Obligations)
# Applicable to both Digital Infrastructure and Physical Operations.
# ═══════════════════════════════════════════════════════════════════

# Default posture is strictly FAIL-CLOSED
default allow := false
default verdict := "DENY"

# Determine effective staleness window (default 60s)
effective_max_staleness := input.max_staleness_seconds if {
    input.max_staleness_seconds != null
    input.max_staleness_seconds > 0
} else := 60

# Freshness assertion: measurement must be within acceptable SLA
is_fresh if {
    input.telemetry_timestamp != null
    now_sec := time.now_ns() / 1000000000
    age := now_sec - input.telemetry_timestamp
    age >= 0
    age <= effective_max_staleness
}

# Cryptographic Anchor Check (Physical TPM 2.0 vs Ledger Tip)
is_anchor_valid if {
    input.resource_type == "TPM_ANCHOR"
    input.reserve_measured != null
    input.units_claimed != null
    count(input.reserve_measured) == 64
    count(input.units_claimed) == 64
    lower(input.reserve_measured) == lower(input.units_claimed)
}

# Numeric Invariant Check (R >= O)
is_numeric_resource if {
    input.resource_type in {"MEMORY_MB", "DISK_GB", "WATER_GALLONS", "POWER_AMPS", "CRYPTO_RESERVE"}
}

is_numeric_solvent if {
    is_numeric_resource
    input.reserve_measured != null
    input.units_claimed != null
    input.reserve_measured >= input.units_claimed
    
    # Check post-transaction headroom if requested_delta is specified
    post_reserve := input.reserve_measured - delta_amount
    post_claims := input.units_claimed - delta_amount
    post_reserve >= 0
    post_reserve >= post_claims
}

delta_amount := input.requested_delta if {
    input.requested_delta != null
} else := 0

# Master admission evaluation
allow if {
    is_fresh
    is_anchor_valid
}

allow if {
    is_fresh
    is_numeric_solvent
}

verdict := "ADMIT" if {
    allow
}

reason := "Stale telemetry: measurement age exceeds maximum SLA" if {
    not is_fresh
} else := "ANCHOR_DESYNC: Hardware TPM NVRAM tip does not match ledger root hash" if {
    input.resource_type == "TPM_ANCHOR"
    not is_anchor_valid
} else := "INSOLVENT: Outstanding claims exceed measured physical reserve (R < O)" if {
    is_numeric_resource
    input.reserve_measured < input.units_claimed
} else := "EXCEEDS_HEADROOM: Requested transaction would breach physical reserve" if {
    is_numeric_resource
    input.reserve_measured >= input.units_claimed
    not is_numeric_solvent
} else := "Invariant holds: physical reserve strictly covers obligations (R >= O)" if {
    allow
} else := "Denied by fail-secure invariant default"
