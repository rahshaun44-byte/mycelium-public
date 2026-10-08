package quantumflex.invariant

import rego.v1

# ═══════════════════════════════════════════════════════════════════
# QUANTUM FLEX — System Integrity & Hardware Attestation Policy
# 
# Explicitly distinguishes:
#   1. System Solvency:      Available >= Obligated (RAM / Disk)
#   2. Anchor Integrity:     Hardware NVRAM == Software Ledger Tip
#   3. PCR Observation:      Runtime register read from silicon
#   4. Hardware Attestation: Cryptographic TPM Quote with verified signature
# ═══════════════════════════════════════════════════════════════════

default allow := false
default verdict := "DENY"

# Determine effective staleness window (default 60s)
effective_max_staleness := input.max_staleness_seconds if {
    input.max_staleness_seconds != null
    input.max_staleness_seconds > 0
} else := 60

# Freshness assertion
is_fresh if {
    input.telemetry_timestamp != null
    now_sec := time.now_ns() / 1000000000
    age := now_sec - input.telemetry_timestamp
    age >= 0
    age <= effective_max_staleness
}

# 1. System Solvency Check (Available >= Obligated)
is_solvency_resource if {
    input.resource_type in {"SYSTEM_SOLVENCY", "MEMORY_MB", "DISK_GB", "WATER_GALLONS"}
}

solvency_valid if {
    is_solvency_resource
    avail := object.get(input, "available", object.get(input, "reserve_measured", null))
    oblig := object.get(input, "obligated", object.get(input, "units_claimed", null))
    delta := object.get(input, "requested_delta", 0)
    avail != null
    oblig != null
    avail >= 0
    oblig >= 0
    avail >= (oblig + delta)
}

# 2. Anchor Integrity Check (Hardware NVRAM == Software Ledger Tip)
is_anchor_resource if {
    input.resource_type in {"TPM_ANCHOR", "DUAL_TPM_ANCHOR"}
}

anchor_integrity_valid if {
    is_anchor_resource
    hw := object.get(input, "hardware_anchor", object.get(input, "reserve_measured", null))
    ledger := object.get(input, "ledger_tip", object.get(input, "units_claimed", null))
    hw != null
    ledger != null
    regex.match("^[0-9a-fA-F]{64}$", hw)
    regex.match("^[0-9a-fA-F]{64}$", ledger)
    hw != "0000000000000000000000000000000000000000000000000000000000000000"
    lower(hw) == lower(ledger)
}

# 3. PCR Register Observation Check (Register successfully measured from silicon)
is_pcr_resource if {
    input.resource_type in {"TPM_PCR", "TPM_PCR15"}
}

pcr_observation_valid if {
    is_pcr_resource
    pcr := object.get(input, "pcr_value", object.get(input, "pcr15_runtime_measured", null))
    pcr != null
    regex.match("^[0-9a-fA-F]{64}$", pcr)
    pcr != "0000000000000000000000000000000000000000000000000000000000000000"
}

# 4. Hardware Attestation Check (TPM Quote + Nonce + Signature)
is_attestation_resource if {
    input.resource_type in {"TPM_ATTESTATION"}
}

hardware_attestation_valid if {
    is_attestation_resource
    input.quote_verified == true
}

# Master Admission Evaluation
allow if {
    is_fresh
    solvency_valid
}

allow if {
    is_fresh
    anchor_integrity_valid
}

allow if {
    is_fresh
    pcr_observation_valid
}

allow if {
    is_fresh
    hardware_attestation_valid
}

# Authoritative Admission Verdict
verdict := "ADMIT" if {
    allow
} else := "DENY"

# Domain-specific Verdict for Granular Hardware/Audit State
domain_verdict := "SOLVENT" if {
    is_solvency_resource
    solvency_valid
} else := "INSOLVENT" if {
    is_solvency_resource
    not solvency_valid
} else := "ANCHORED" if {
    is_anchor_resource
    anchor_integrity_valid
} else := "ANCHOR_DESYNC" if {
    is_anchor_resource
    not anchor_integrity_valid
} else := "OBSERVED" if {
    is_pcr_resource
    pcr_observation_valid
} else := "PCR_UNOBSERVED" if {
    is_pcr_resource
    not pcr_observation_valid
} else := "ATTESTED" if {
    is_attestation_resource
    hardware_attestation_valid
} else := "NOT_ATTESTED" if {
    is_attestation_resource
    not hardware_attestation_valid
} else := verdict

# Accurate Reason Telemetry
reason := "Stale telemetry: measurement age exceeds maximum SLA" if {
    not is_fresh
} else := "System headroom holds: available capacity strictly covers obligations (AVAILABLE >= OBLIGATED)" if {
    is_solvency_resource
    solvency_valid
} else := "INSOLVENT: Claimed obligations exceed available system capacity" if {
    is_solvency_resource
    not solvency_valid
} else := "Anchor integrity verified: hardware NVRAM matches software ledger tip (HARDWARE == LEDGER)" if {
    is_anchor_resource
    anchor_integrity_valid
} else := "ANCHOR_DESYNC: Hardware NVRAM tip does not match software ledger root hash" if {
    is_anchor_resource
    not anchor_integrity_valid
} else := "Runtime PCR register successfully observed from TPM silicon (PCR READ SUCCESSFULLY)" if {
    is_pcr_resource
    pcr_observation_valid
} else := "PCR_UNOBSERVED: Failed to read valid 256-bit register from TPM silicon" if {
    is_pcr_resource
    not pcr_observation_valid
} else := "Cryptographic TPM quote and signature verified against expected measurement (ATTESTED)" if {
    is_attestation_resource
    hardware_attestation_valid
} else := "TPM quote generation and signature verification not yet executed (NOT_ATTESTED)" if {
    is_attestation_resource
    not hardware_attestation_valid
} else := "Admission granted by verified integrity invariant" if {
    allow
} else := "Denied by fail-secure invariant default"
