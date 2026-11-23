package quantumflex.invariant_test

import rego.v1
import data.quantumflex.invariant

# ── 1. Physical Water Tests (FinallyFungus) ──────────────────────────────────
test_physical_water_solvent if {
    now := time.now_ns() / 1000000000
    inp := {
        "domain": "physical",
        "resource_type": "WATER_GALLONS",
        "reserve_measured": 500.0,
        "units_claimed": 350.0,
        "requested_delta": 50.0,
        "telemetry_timestamp": now - 10,
        "max_staleness_seconds": 60,
    }
    invariant.allow with input as inp
    invariant.verdict == "ADMIT" with input as inp
}

test_physical_water_insolvent_breach if {
    # Liquid-class failure: claimed gallons exceed physical tank
    now := time.now_ns() / 1000000000
    inp := {
        "domain": "physical",
        "resource_type": "WATER_GALLONS",
        "reserve_measured": 200.0,
        "units_claimed": 350.0,
        "telemetry_timestamp": now - 5,
        "max_staleness_seconds": 60,
    }
    not invariant.allow with input as inp
    invariant.verdict == "DENY" with input as inp
    contains(invariant.reason, "INSOLVENT") with input as inp
}

test_physical_water_stale_sensor if {
    now := time.now_ns() / 1000000000
    inp := {
        "domain": "physical",
        "resource_type": "WATER_GALLONS",
        "reserve_measured": 500.0,
        "units_claimed": 100.0,
        "telemetry_timestamp": now - 300, # 5 minutes old
        "max_staleness_seconds": 60,
    }
    not invariant.allow with input as inp
    invariant.verdict == "DENY" with input as inp
    contains(invariant.reason, "Stale telemetry") with input as inp
}

# ── 2. Digital Infrastructure Tests (Yoga Host) ──────────────────────────────
test_digital_memory_solvent if {
    now := time.now_ns() / 1000000000
    inp := {
        "domain": "digital",
        "resource_type": "MEMORY_MB",
        "reserve_measured": 15127.0,
        "units_claimed": 7288.0,
        "requested_delta": 1024.0,
        "telemetry_timestamp": now - 2,
        "max_staleness_seconds": 30,
    }
    invariant.allow with input as inp
    invariant.verdict == "ADMIT" with input as inp
}

test_digital_memory_exhaustion if {
    now := time.now_ns() / 1000000000
    inp := {
        "domain": "digital",
        "resource_type": "MEMORY_MB",
        "reserve_measured": 15127.0,
        "units_claimed": 16000.0, # Exceeds available RAM
        "telemetry_timestamp": now - 2,
        "max_staleness_seconds": 30,
    }
    not invariant.allow with input as inp
    invariant.verdict == "DENY" with input as inp
}

# ── 3. Cryptographic Hardware Anchor Tests (Pluton TPM 2.0) ──────────────────
test_tpm_hardware_anchor_matched if {
    now := time.now_ns() / 1000000000
    hash := "105e799893e206c0c8159f4b02188bdc7aae8e4a72189de0463a4f1f9e1f787e"
    inp := {
        "domain": "digital",
        "resource_type": "TPM_ANCHOR",
        "reserve_measured": hash, # Hardware TPM NV index
        "units_claimed": hash,    # Ledger tip block_hash
        "telemetry_timestamp": now - 1,
        "max_staleness_seconds": 60,
    }
    invariant.allow with input as inp
    invariant.verdict == "ADMIT" with input as inp
}

test_tpm_hardware_anchor_tamper_desync if {
    now := time.now_ns() / 1000000000
    inp := {
        "domain": "digital",
        "resource_type": "TPM_ANCHOR",
        "reserve_measured": "105e799893e206c0c8159f4b02188bdc7aae8e4a72189de0463a4f1f9e1f787e",
        "units_claimed":    "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        "telemetry_timestamp": now - 1,
        "max_staleness_seconds": 60,
    }
    not invariant.allow with input as inp
    invariant.verdict == "DENY" with input as inp
    contains(invariant.reason, "ANCHOR_DESYNC") with input as inp
}

# ── Adversarial regressions (2026-11-23): type confusion, negative delta, caller-widened SLA ───
# OPA orders null < boolean < number < string < array < object, so a non-number reserve
# compared against a numeric obligation used to win. Each of these must DENY.

adv_base(extra) := object.union({
	"resource_type": "MEMORY_MB",
	"telemetry_timestamp": time.now_ns() / 1000000000,
	"max_staleness_seconds": 30,
}, extra)

test_adv_string_reserve_denied if {
	inp := adv_base({"reserve_measured": "0", "units_claimed": 1000000})
	not invariant.allow with input as inp
	invariant.domain_verdict == "INSOLVENT" with input as inp
}

test_adv_array_reserve_denied if {
	not invariant.allow with input as adv_base({"reserve_measured": [], "units_claimed": 5})
}

test_adv_object_reserve_denied if {
	not invariant.allow with input as adv_base({"reserve_measured": {}, "units_claimed": 5})
}

test_adv_string_obligation_denied if {
	not invariant.allow with input as adv_base({"reserve_measured": 10, "units_claimed": "1"})
}

test_adv_negative_delta_denied if {
	inp := adv_base({"reserve_measured": 1, "units_claimed": 1000, "requested_delta": -1000})
	not invariant.allow with input as inp
}

test_adv_string_delta_denied if {
	not invariant.allow with input as adv_base({"reserve_measured": 10, "units_claimed": 1, "requested_delta": "0"})
}

test_adv_caller_cannot_widen_staleness if {
	inp := adv_base({"reserve_measured": 10, "units_claimed": 1, "telemetry_timestamp": 0, "max_staleness_seconds": 1000000000000})
	not invariant.allow with input as inp
}

test_adv_caller_may_tighten_staleness if {
	now := time.now_ns() / 1000000000
	inp := adv_base({"reserve_measured": 10, "units_claimed": 1, "telemetry_timestamp": now - 20, "max_staleness_seconds": 10})
	not invariant.allow with input as inp
}

test_adv_string_timestamp_denied if {
	now := time.now_ns() / 1000000000
	inp := adv_base({"reserve_measured": 10, "units_claimed": 1, "telemetry_timestamp": sprintf("%d", [now])})
	not invariant.allow with input as inp
}

test_adv_numeric_solvent_still_admits if {
	inp := adv_base({"reserve_measured": 10, "units_claimed": 1, "requested_delta": 0})
	invariant.allow with input as inp
}
