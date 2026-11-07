package quantumflex.constitution

import rego.v1

# ==============================================================================
# QUANTUMFLEX OPERATING CONSTITUTION — ENFORCEABLE POLICY ENGINE
# Governing Equation:
#   Mission Success = Security + Peace + Financial Independence
#                   + Scientific Freedom + Positive Impact
#
# Four Permanent Mycelium Controls:
#   1. QF-CAPITAL-01 : Six-month reserve gate (R >= 6 * O) & sacred Bucket 1 lock
#   2. QF-PRIVACY-01 : Local-only inference ($0.00 cloud), provenance, zero leak
#   3. QF-AUTH-01    : Mandatory human authorization for consequential finance
#   4. QF-OPS-01     : Operator & helper workload sustainability protection
# ==============================================================================

default allow := false
default verdict := "DENY"
default qf_capital_01_allow := false
default qf_privacy_01_allow := false
default qf_auth_01_allow := false
default qf_ops_01_allow := false

# ------------------------------------------------------------------------------
# 1. QF-CAPITAL-01: Six-Month Reserve & Capital-Allocation Gate (R >= 6O)
# ------------------------------------------------------------------------------
default capital_is_object := false

raw_capital := object.get(input, "capital", null)

capital_is_object if {
    is_object(raw_capital)
}

capital_ctx := raw_capital if {
    capital_is_object
} else := {}

reserves := object.get(capital_ctx, "reserves", -1)
monthly_obligations := object.get(capital_ctx, "monthly_obligations", -1)
allocation_amount := object.get(capital_ctx, "allocation_amount", 0)
funding_bucket := object.get(capital_ctx, "funding_bucket", "CASH_FLOW_ENGINE")
financial_shock := object.get(capital_ctx, "financial_shock", false)
discretionary_expansion := object.get(capital_ctx, "discretionary_expansion", false)

valid_funding_buckets := {
    "IRON_RESERVE",
    "CASH_FLOW_ENGINE",
    "ASYMMETRIC_RESEARCH",
    "CLIENT_DEPOSIT",
    "NONE",
}

capital_inputs_valid if {
    capital_is_object
    is_number(reserves)
    is_number(monthly_obligations)
    is_number(allocation_amount)
    is_boolean(financial_shock)
    is_boolean(discretionary_expansion)
    reserves >= 0
    monthly_obligations > 0
    allocation_amount >= 0
    funding_bucket in valid_funding_buckets
}

six_month_floor := 6 * monthly_obligations if {
    capital_inputs_valid
} else := -1

post_allocation_reserves := reserves - allocation_amount if {
    capital_inputs_valid
} else := -1

iron_reserve_violated if {
    funding_bucket == "IRON_RESERVE"
    allocation_amount > 0
}

iron_reserve_violated if {
    funding_bucket == "IRON_RESERVE"
    discretionary_expansion == true
}

capital_decision := "INVALID_CAPITAL_INPUTS" if {
    not capital_inputs_valid
} else := "FREEZE_DISCRETIONARY_SPENDING" if {
    financial_shock == true
} else := "IRON_RESERVE_SACRED_LOCK" if {
    iron_reserve_violated
} else := "PROTECT_AND_REBUILD_RESERVES" if {
    reserves < six_month_floor
} else := "MAINTAIN_RESERVE_RESTRICT_EXPANSION" if {
    reserves == six_month_floor
} else := "POST_ALLOCATION_RESERVE_BREACH" if {
    reserves > six_month_floor
    post_allocation_reserves < six_month_floor
} else := "EVALUATE_FUNDED_OPPORTUNITY"

qf_capital_01_allow if {
    capital_inputs_valid
    financial_shock == false
    not iron_reserve_violated
    reserves > six_month_floor
    post_allocation_reserves >= six_month_floor
}

qf_capital_01_allow if {
    capital_inputs_valid
    financial_shock == false
    not iron_reserve_violated
    reserves == six_month_floor
    allocation_amount == 0
    discretionary_expansion == false
}

# ------------------------------------------------------------------------------
# 2. QF-PRIVACY-01: Sovereign Local-Only Intelligence & Zero Financial Exposure
# ------------------------------------------------------------------------------
default privacy_is_object := false

raw_privacy := object.get(input, "privacy", null)

privacy_is_object if {
    is_object(raw_privacy)
}

privacy_ctx := raw_privacy if {
    privacy_is_object
} else := {}

allowed_loopback_endpoints := {
    "127.0.0.1:11434",
    "http://127.0.0.1:11434",
    "localhost:11434",
    "http://localhost:11434",
    "none",
}

confidential_classifications := {
    "household_financial",
    "proprietary_research",
    "client_confidential",
    "sovereign_internal",
}

valid_classifications := confidential_classifications | {"public"}

inference_endpoint := object.get(privacy_ctx, "inference_endpoint", "")
cloud_spend_usd := object.get(privacy_ctx, "cloud_spend_usd", -1)
external_egress := object.get(privacy_ctx, "external_egress", true)
data_classification := object.get(privacy_ctx, "data_classification", "")
provenance_verified := object.get(privacy_ctx, "provenance_verified", false)
raw_household_dollars_exposed := object.get(privacy_ctx, "raw_household_dollars_exposed", false)
ambient_identifiers_present := object.get(privacy_ctx, "ambient_identifiers_present", false)

egress_permitted if {
    external_egress == false
}

egress_permitted if {
    data_classification == "public"
}

qf_privacy_01_allow if {
    privacy_is_object
    is_string(inference_endpoint)
    inference_endpoint in allowed_loopback_endpoints
    is_number(cloud_spend_usd)
    cloud_spend_usd == 0
    is_boolean(external_egress)
    is_string(data_classification)
    data_classification in valid_classifications
    egress_permitted
    provenance_verified == true
    raw_household_dollars_exposed == false
    ambient_identifiers_present == false
}

privacy_decision := "INVALID_PRIVACY_CONTEXT" if {
    not privacy_is_object
} else := "ADMIT_SOVEREIGN_LOCAL" if {
    qf_privacy_01_allow
} else := "ZERO_CLOUD_SPEND_VIOLATION" if {
    not is_number(cloud_spend_usd)
} else := "ZERO_CLOUD_SPEND_VIOLATION" if {
    cloud_spend_usd != 0
} else := "NON_LOOPBACK_ENDPOINT_DENIED" if {
    not is_string(inference_endpoint)
} else := "NON_LOOPBACK_ENDPOINT_DENIED" if {
    not inference_endpoint in allowed_loopback_endpoints
} else := "HOUSEHOLD_FINANCIAL_EXPOSURE_DENIED" if {
    not is_boolean(raw_household_dollars_exposed)
} else := "HOUSEHOLD_FINANCIAL_EXPOSURE_DENIED" if {
    raw_household_dollars_exposed != false
} else := "AMBIENT_DATA_COLLECTION_DENIED" if {
    not is_boolean(ambient_identifiers_present)
} else := "AMBIENT_DATA_COLLECTION_DENIED" if {
    ambient_identifiers_present != false
} else := "INVALID_PRIVACY_CONTEXT" if {
    not is_boolean(external_egress)
} else := "INVALID_PRIVACY_CONTEXT" if {
    not is_string(data_classification)
} else := "INVALID_PRIVACY_CONTEXT" if {
    not data_classification in valid_classifications
} else := "CONFIDENTIAL_EGRESS_DENIED" if {
    not egress_permitted
} else := "UNVERIFIED_DOCUMENT_PROVENANCE"

# ------------------------------------------------------------------------------
# 3. QF-AUTH-01: Human Authorization for Consequential Financial Actions
# ------------------------------------------------------------------------------
default auth_is_object := false

raw_auth := object.get(input, "auth", null)

auth_is_object if {
    is_object(raw_auth)
}

auth_ctx := raw_auth if {
    auth_is_object
} else := {}

consequential_financial_action := object.get(auth_ctx, "consequential_financial_action", true)
human_authorized := object.get(auth_ctx, "human_authorized", false)
actor_type := object.get(auth_ctx, "actor_type", "unknown")
authorizer_id := object.get(auth_ctx, "authorizer_id", "")
auth_credential := object.get(auth_ctx, "auth_credential", "CredNone")
idempotency_key_valid := object.get(auth_ctx, "idempotency_key_valid", false)
usdc_decimals := object.get(auth_ctx, "usdc_decimals", 6)

approved_authorizers := {
    "rahshaun_chambers",
    "qf-operator-key",
}

approved_credentials := {
    "CredMtlsCertVerified",
    "CredShamirThresholdMet",
    "CredTwoManAttestation",
    "TitanM2StrongBox",
    "TitanM2_StrongBox",
    "TitanM3StrongBox",
    "TitanM3_StrongBox",
    "PlutonTPM2",
}

valid_actor_types := {
    "human_operator",
    "operator_cosigned_agent",
    "autonomous_agent",
}

qf_auth_01_allow if {
    auth_is_object
    is_boolean(consequential_financial_action)
    consequential_financial_action == false
    actor_type in valid_actor_types
}

qf_auth_01_allow if {
    auth_is_object
    is_boolean(consequential_financial_action)
    consequential_financial_action == true
    human_authorized == true
    actor_type in {"human_operator", "operator_cosigned_agent"}
    authorizer_id in approved_authorizers
    auth_credential in approved_credentials
    idempotency_key_valid == true
    is_number(usdc_decimals)
    usdc_decimals == 6
}

auth_decision := "INVALID_AUTH_CONTEXT" if {
    not auth_is_object
} else := "INVALID_AUTH_CONTEXT" if {
    not is_boolean(consequential_financial_action)
} else := "NON_FINANCIAL_ACTION_PERMITTED" if {
    consequential_financial_action == false
    actor_type in valid_actor_types
} else := "INVALID_AUTH_CONTEXT" if {
    consequential_financial_action == false
} else := "AUTONOMOUS_FINANCIAL_EXECUTION_FORBIDDEN" if {
    actor_type == "autonomous_agent"
} else := "MISSING_HUMAN_OPERATOR_APPROVAL" if {
    human_authorized != true
} else := "INVALID_AUTH_CONTEXT" if {
    not actor_type in {"human_operator", "operator_cosigned_agent"}
} else := "UNVERIFIED_AUTHORIZER_IDENTITY" if {
    not authorizer_id in approved_authorizers
} else := "INSUFFICIENT_CRYPTOGRAPHIC_CREDENTIAL" if {
    not auth_credential in approved_credentials
} else := "MISSING_DETERMINISTIC_IDEMPOTENCY_KEY" if {
    idempotency_key_valid != true
} else := "USDC_SIX_DECIMAL_INVARIANT_VIOLATION" if {
    usdc_decimals != 6
} else := "HUMAN_AUTHORIZATION_VERIFIED"

# ------------------------------------------------------------------------------
# 4. QF-OPS-01: Operator & Helper Workload Sustainability Gate
# ------------------------------------------------------------------------------
default ops_is_object := false

raw_ops := object.get(input, "ops", null)

ops_is_object if {
    is_object(raw_ops)
}

ops_ctx := raw_ops if {
    ops_is_object
} else := {}

continuous_block_minutes := object.get(ops_ctx, "continuous_block_minutes", -1)
daily_deep_work_hours := object.get(ops_ctx, "daily_deep_work_hours", -1)
named_objects_in_block := object.get(ops_ctx, "named_objects_in_block", -1)
rest_hours_last_24h := object.get(ops_ctx, "rest_hours_last_24h", -1)
operator_fatigue_flag := object.get(ops_ctx, "operator_fatigue_flag", true)
helper_fairness_verified := object.get(ops_ctx, "helper_fairness_verified", false)

ops_inputs_valid if {
    ops_is_object
    is_number(continuous_block_minutes)
    is_number(daily_deep_work_hours)
    is_number(named_objects_in_block)
    is_number(rest_hours_last_24h)
    is_boolean(operator_fatigue_flag)
    is_boolean(helper_fairness_verified)
    continuous_block_minutes >= 0
    daily_deep_work_hours >= 0
    named_objects_in_block >= 0
    rest_hours_last_24h >= 0
}

qf_ops_01_allow if {
    ops_inputs_valid
    operator_fatigue_flag == false
    helper_fairness_verified == true
    continuous_block_minutes <= 90
    daily_deep_work_hours <= 8
    named_objects_in_block <= 1
    rest_hours_last_24h >= 7
}

ops_decision := "SUSTAINABLE_CADENCE_VERIFIED" if {
    qf_ops_01_allow
} else := "INVALID_OPS_INPUTS" if {
    not ops_inputs_valid
} else := "OPERATOR_FATIGUE_RECOVERY_REQUIRED" if {
    operator_fatigue_flag == true
} else := "HELPER_PROTECTION_VIOLATION" if {
    helper_fairness_verified != true
} else := "REST_DEFICIT_RECOVERY_REQUIRED" if {
    rest_hours_last_24h < 7
} else := "DAILY_WORKLOAD_CEILING_EXCEEDED" if {
    daily_deep_work_hours > 8
} else := "DEEP_WORK_BLOCK_LIMIT_EXCEEDED" if {
    continuous_block_minutes > 90
} else := "SINGLE_OBJECT_FOCUS_VIOLATION" if {
    named_objects_in_block > 1
} else := "OPS_SUSTAINABILITY_HOLD"

# ------------------------------------------------------------------------------
# Composite Constitutional Verdict (Fail-Closed Across All Four Controls)
# ------------------------------------------------------------------------------
allow if {
    qf_capital_01_allow
    qf_privacy_01_allow
    qf_auth_01_allow
    qf_ops_01_allow
}

verdict := "ADMIT" if {
    allow
} else := "DENY"

evaluation := {
    "allow": allow,
    "verdict": verdict,
    "controls": {
        "QF-CAPITAL-01": {
            "allow": qf_capital_01_allow,
            "decision": capital_decision,
        },
        "QF-PRIVACY-01": {
            "allow": qf_privacy_01_allow,
            "decision": privacy_decision,
        },
        "QF-AUTH-01": {
            "allow": qf_auth_01_allow,
            "decision": auth_decision,
        },
        "QF-OPS-01": {
            "allow": qf_ops_01_allow,
            "decision": ops_decision,
        },
    },
}
