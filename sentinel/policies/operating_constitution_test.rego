package quantumflex.constitution_test

import rego.v1
import data.quantumflex.constitution

# Baseline compliant sovereign payload
valid_context := {
    "capital": {
        "reserves": 9.0,
        "monthly_obligations": 1.0,
        "allocation_amount": 1.5,
        "funding_bucket": "CASH_FLOW_ENGINE",
        "financial_shock": false,
        "discretionary_expansion": true,
    },
    "privacy": {
        "inference_endpoint": "127.0.0.1:11434",
        "cloud_spend_usd": 0,
        "external_egress": false,
        "data_classification": "proprietary_research",
        "provenance_verified": true,
        "raw_household_dollars_exposed": false,
        "ambient_identifiers_present": false,
    },
    "auth": {
        "consequential_financial_action": true,
        "human_authorized": true,
        "actor_type": "human_operator",
        "authorizer_id": "rahshaun_chambers",
        "auth_credential": "CredTwoManAttestation",
        "idempotency_key_valid": true,
        "usdc_decimals": 6,
    },
    "ops": {
        "continuous_block_minutes": 75,
        "daily_deep_work_hours": 6,
        "named_objects_in_block": 1,
        "rest_hours_last_24h": 8,
        "operator_fatigue_flag": false,
        "helper_fairness_verified": true,
    },
}

test_all_four_constitutional_controls_admit if {
    res := constitution.evaluation with input as valid_context
    res.allow == true
    res.verdict == "ADMIT"
    res.controls["QF-CAPITAL-01"].allow == true
    res.controls["QF-CAPITAL-01"].decision == "EVALUATE_FUNDED_OPPORTUNITY"
    res.controls["QF-PRIVACY-01"].allow == true
    res.controls["QF-AUTH-01"].allow == true
    res.controls["QF-OPS-01"].allow == true
}

test_empty_input_fails_closed if {
    res := constitution.evaluation with input as {}
    res.allow == false
    res.verdict == "DENY"
    res.controls["QF-CAPITAL-01"].allow == false
    res.controls["QF-CAPITAL-01"].decision == "INVALID_CAPITAL_INPUTS"
    res.controls["QF-PRIVACY-01"].allow == false
    res.controls["QF-PRIVACY-01"].decision == "INVALID_PRIVACY_CONTEXT"
    res.controls["QF-AUTH-01"].allow == false
    res.controls["QF-AUTH-01"].decision == "INVALID_AUTH_CONTEXT"
    res.controls["QF-OPS-01"].allow == false
    res.controls["QF-OPS-01"].decision == "INVALID_OPS_INPUTS"
}

# ── QF-CAPITAL-01 Tests ──────────────────────────────────────────────────────
test_capital_below_six_months_denies if {
    inp := json.patch(valid_context, [{"op": "replace", "path": "/capital/reserves", "value": 5.5}])
    res := constitution.evaluation with input as inp
    res.allow == false
    res.controls["QF-CAPITAL-01"].allow == false
    res.controls["QF-CAPITAL-01"].decision == "PROTECT_AND_REBUILD_RESERVES"
}

test_capital_at_six_months_denies_discretionary_expansion if {
    inp := json.patch(valid_context, [
        {"op": "replace", "path": "/capital/reserves", "value": 6.0},
        {"op": "replace", "path": "/capital/allocation_amount", "value": 0},
        {"op": "replace", "path": "/capital/discretionary_expansion", "value": true},
    ])
    res := constitution.evaluation with input as inp
    res.allow == false
    res.controls["QF-CAPITAL-01"].decision == "MAINTAIN_RESERVE_RESTRICT_EXPANSION"
}

test_capital_at_six_months_allows_steady_non_expansion if {
    inp := json.patch(valid_context, [
        {"op": "replace", "path": "/capital/reserves", "value": 6.0},
        {"op": "replace", "path": "/capital/allocation_amount", "value": 0},
        {"op": "replace", "path": "/capital/discretionary_expansion", "value": false},
        {"op": "replace", "path": "/auth/consequential_financial_action", "value": false},
    ])
    res := constitution.evaluation with input as inp
    res.allow == true
    res.controls["QF-CAPITAL-01"].decision == "MAINTAIN_RESERVE_RESTRICT_EXPANSION"
}

test_capital_post_allocation_breach_denies if {
    # R = 7.0 (> 6.0), delta = 1.5 -> post = 5.5 (< 6.0)
    inp := json.patch(valid_context, [
        {"op": "replace", "path": "/capital/reserves", "value": 7.0},
        {"op": "replace", "path": "/capital/allocation_amount", "value": 1.5},
    ])
    res := constitution.evaluation with input as inp
    res.allow == false
    res.controls["QF-CAPITAL-01"].decision == "POST_ALLOCATION_RESERVE_BREACH"
}

test_capital_iron_reserve_sacred_lock_on_allocation if {
    inp := json.patch(valid_context, [
        {"op": "replace", "path": "/capital/funding_bucket", "value": "IRON_RESERVE"},
        {"op": "replace", "path": "/capital/allocation_amount", "value": 1.0},
        {"op": "replace", "path": "/capital/discretionary_expansion", "value": false},
    ])
    res := constitution.evaluation with input as inp
    res.allow == false
    res.controls["QF-CAPITAL-01"].decision == "IRON_RESERVE_SACRED_LOCK"
}

test_capital_iron_reserve_sacred_lock_on_discretionary_expansion if {
    inp := json.patch(valid_context, [
        {"op": "replace", "path": "/capital/funding_bucket", "value": "IRON_RESERVE"},
        {"op": "replace", "path": "/capital/allocation_amount", "value": 0},
        {"op": "replace", "path": "/capital/discretionary_expansion", "value": true},
    ])
    res := constitution.evaluation with input as inp
    res.allow == false
    res.controls["QF-CAPITAL-01"].decision == "IRON_RESERVE_SACRED_LOCK"
}

test_capital_iron_reserve_zero_allocation_non_expansion_admits if {
    inp := json.patch(valid_context, [
        {"op": "replace", "path": "/capital/funding_bucket", "value": "IRON_RESERVE"},
        {"op": "replace", "path": "/capital/allocation_amount", "value": 0},
        {"op": "replace", "path": "/capital/discretionary_expansion", "value": false},
    ])
    res := constitution.evaluation with input as inp
    res.allow == true
    res.controls["QF-CAPITAL-01"].decision == "EVALUATE_FUNDED_OPPORTUNITY"
}

test_capital_financial_shock_freezes_spending if {
    inp := json.patch(valid_context, [
        {"op": "replace", "path": "/capital/financial_shock", "value": true},
    ])
    res := constitution.evaluation with input as inp
    res.allow == false
    res.controls["QF-CAPITAL-01"].decision == "FREEZE_DISCRETIONARY_SPENDING"
}

# ── QF-PRIVACY-01 Tests ──────────────────────────────────────────────────────
test_privacy_paid_cloud_spend_denies if {
    inp := json.patch(valid_context, [
        {"op": "replace", "path": "/privacy/cloud_spend_usd", "value": 0.01},
    ])
    res := constitution.evaluation with input as inp
    res.allow == false
    res.controls["QF-PRIVACY-01"].decision == "ZERO_CLOUD_SPEND_VIOLATION"
}

test_privacy_external_cloud_endpoint_denies if {
    inp := json.patch(valid_context, [
        {"op": "replace", "path": "/privacy/inference_endpoint", "value": "https://api.openai.com/v1"},
    ])
    res := constitution.evaluation with input as inp
    res.allow == false
    res.controls["QF-PRIVACY-01"].decision == "NON_LOOPBACK_ENDPOINT_DENIED"
}

test_privacy_household_dollar_exposure_denies if {
    inp := json.patch(valid_context, [
        {"op": "replace", "path": "/privacy/raw_household_dollars_exposed", "value": true},
    ])
    res := constitution.evaluation with input as inp
    res.allow == false
    res.controls["QF-PRIVACY-01"].decision == "HOUSEHOLD_FINANCIAL_EXPOSURE_DENIED"
}

test_privacy_confidential_egress_denies if {
    inp := json.patch(valid_context, [
        {"op": "replace", "path": "/privacy/external_egress", "value": true},
    ])
    res := constitution.evaluation with input as inp
    res.allow == false
    res.controls["QF-PRIVACY-01"].decision == "CONFIDENTIAL_EGRESS_DENIED"
}

test_privacy_public_egress_admits if {
    inp := json.patch(valid_context, [
        {"op": "replace", "path": "/privacy/data_classification", "value": "public"},
        {"op": "replace", "path": "/privacy/external_egress", "value": true},
    ])
    res := constitution.evaluation with input as inp
    res.allow == true
    res.controls["QF-PRIVACY-01"].decision == "ADMIT_SOVEREIGN_LOCAL"
}

test_privacy_unverified_provenance_denies if {
    inp := json.patch(valid_context, [
        {"op": "replace", "path": "/privacy/provenance_verified", "value": false},
    ])
    res := constitution.evaluation with input as inp
    res.allow == false
    res.controls["QF-PRIVACY-01"].decision == "UNVERIFIED_DOCUMENT_PROVENANCE"
}

# ── QF-AUTH-01 Tests ─────────────────────────────────────────────────────────
test_auth_autonomous_agent_financial_action_denies if {
    inp := json.patch(valid_context, [
        {"op": "replace", "path": "/auth/actor_type", "value": "autonomous_agent"},
    ])
    res := constitution.evaluation with input as inp
    res.allow == false
    res.controls["QF-AUTH-01"].decision == "AUTONOMOUS_FINANCIAL_EXECUTION_FORBIDDEN"
}

test_auth_eighteen_decimal_usdc_denies if {
    inp := json.patch(valid_context, [
        {"op": "replace", "path": "/auth/usdc_decimals", "value": 18},
    ])
    res := constitution.evaluation with input as inp
    res.allow == false
    res.controls["QF-AUTH-01"].decision == "USDC_SIX_DECIMAL_INVARIANT_VIOLATION"
}

test_auth_non_financial_valid_actor_admits if {
    inp := json.patch(valid_context, [
        {"op": "replace", "path": "/auth/consequential_financial_action", "value": false},
        {"op": "replace", "path": "/auth/actor_type", "value": "autonomous_agent"},
        {"op": "replace", "path": "/auth/human_authorized", "value": false},
    ])
    res := constitution.evaluation with input as inp
    res.allow == true
    res.controls["QF-AUTH-01"].decision == "NON_FINANCIAL_ACTION_PERMITTED"
}

test_auth_non_financial_invalid_actor_denies if {
    inp := json.patch(valid_context, [
        {"op": "replace", "path": "/auth/consequential_financial_action", "value": false},
        {"op": "replace", "path": "/auth/actor_type", "value": "unregistered_bot"},
    ])
    res := constitution.evaluation with input as inp
    res.allow == false
    res.controls["QF-AUTH-01"].decision == "INVALID_AUTH_CONTEXT"
}

# ── QF-OPS-01 Tests ──────────────────────────────────────────────────────────
test_ops_fatigue_flag_triggers_recovery if {
    inp := json.patch(valid_context, [
        {"op": "replace", "path": "/ops/operator_fatigue_flag", "value": true},
    ])
    res := constitution.evaluation with input as inp
    res.allow == false
    res.controls["QF-OPS-01"].decision == "OPERATOR_FATIGUE_RECOVERY_REQUIRED"
}

test_ops_helper_unfairness_denies if {
    inp := json.patch(valid_context, [
        {"op": "replace", "path": "/ops/helper_fairness_verified", "value": false},
    ])
    res := constitution.evaluation with input as inp
    res.allow == false
    res.controls["QF-OPS-01"].decision == "HELPER_PROTECTION_VIOLATION"
}

test_ops_excessive_block_or_multi_object_denies if {
    inp := json.patch(valid_context, [
        {"op": "replace", "path": "/ops/named_objects_in_block", "value": 3},
    ])
    res := constitution.evaluation with input as inp
    res.allow == false
    res.controls["QF-OPS-01"].decision == "SINGLE_OBJECT_FOCUS_VIOLATION"
}
