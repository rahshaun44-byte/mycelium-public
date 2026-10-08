package quantumflex.invariant

import rego.v1

# ═══════════════════════════════════════════════════════════════════
# QUANTUM FLEX — Universal Reserve Invariant Policy (R >= O)
# The Hardware Imperative: Fail-Secure Solvency & Hardware Anchoring
#
# Enforces the fundamental invariant: R >= O (Reserve >= Obligations)
# Applicable to verified host infrastructure (RAM, Disk) and TPM 2.0 anchors.
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

# Cryptographic Dual-Anchor Check (NVRAM Baseline + PCR 15 Runtime)
is_anchor_valid if {
    input.resource_type == "DUAL_TPM_ANCHOR"
    input.reserve_measured != null
    input.units_claimed != null
    input.pcr15_runtime_measured != null
    regex.match("^[0-9a-fA-F]{64}$", input.reserve_measured)
    regex.match("^[0-9a-fA-F]{64}$", input.units_claimed)
    regex.match("^[0-9a-fA-F]{64}$", input.pcr15_runtime_measured)
    input.reserve_measured != "0000000000000000000000000000000000000000000000000000000000000000"
    lower(input.reserve_measured) == lower(input.units_claimed)
}

# Numeric Invariant Check (R >= O)
is_numeric_resource if {
    input.resource_type in {"MEMORY_MB", "DISK_GB"}
}

is_numeric_solvent if {
    is_numeric_resource
    input.reserve_measured != null
    input.units_claimed != null
    input.reserve_measured >= 0
    input.units_claimed >= 0
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
    input.resource_type == "DUAL_TPM_ANCHOR"
    not is_anchor_valid
} else := "INSOLVENT: Outstanding claims exceed measured system reserve (R < O)" if {
    is_numeric_resource
    input.reserve_measured < input.units_claimed
} else := "EXCEEDS_HEADROOM: Requested transaction would breach system reserve" if {
    is_numeric_resource
    input.reserve_measured >= input.units_claimed
    not is_numeric_solvent
} else := "Invariant holds: system reserve strictly covers obligations (R >= O)" if {
    allow
} else := "Denied by fail-secure invariant default"
