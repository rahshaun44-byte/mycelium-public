#!/usr/bin/env python3
"""
QuantumFlex Operating Constitution — Enforceable Mycelium Control Plane
=======================================================================
Governing Principle:
  The mission exists to serve life, not consume it.
  Mission Success = Security + Peace + Financial Independence
                  + Scientific Freedom + Positive Impact

Enforces four permanent, fail-closed Mycelium controls:
  - QF-CAPITAL-01 : Six-month reserve gate (R >= 6 * O) & sacred Bucket 1 lock
  - QF-PRIVACY-01 : Local-only inference ($0.00 cloud), provenance, zero leak
  - QF-AUTH-01    : Mandatory human authorization for consequential finance
  - QF-OPS-01     : Operator & helper workload sustainability protection
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

from sentinel.policies.wasm_gatekeeper import get_constitution_wasm_gatekeeper
from src.privacy_filter import PrivacyFilter

UUID_V4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

ALLOWED_LOOPBACK_ENDPOINTS = frozenset({
    "127.0.0.1:11434",
    "http://127.0.0.1:11434",
    "localhost:11434",
    "http://localhost:11434",
    "none",
})

CONFIDENTIAL_CLASSIFICATIONS = frozenset({
    "household_financial",
    "proprietary_research",
    "client_confidential",
    "sovereign_internal",
})

VALID_CLASSIFICATIONS = CONFIDENTIAL_CLASSIFICATIONS | {"public"}

VALID_FUNDING_BUCKETS = frozenset({
    "IRON_RESERVE",
    "CASH_FLOW_ENGINE",
    "ASYMMETRIC_RESEARCH",
    "CLIENT_DEPOSIT",
    "NONE",
})

APPROVED_AUTHORIZERS = frozenset({
    "rahshaun_chambers",
    "qf-operator-key",
})

APPROVED_CREDENTIALS = frozenset({
    "CredMtlsCertVerified",
    "CredShamirThresholdMet",
    "CredTwoManAttestation",
    "TitanM2StrongBox",
    "TitanM2_StrongBox",
    "TitanM3StrongBox",
    "TitanM3_StrongBox",
    "PlutonTPM2",
})

VALID_ACTOR_TYPES = frozenset({
    "human_operator",
    "operator_cosigned_agent",
    "autonomous_agent",
})


def _is_real_number(val: Any) -> bool:
    return isinstance(val, (int, float)) and not isinstance(val, bool) and math.isfinite(float(val))


@dataclass(frozen=True)
class ControlVerdict:
    control_id: str
    allow: bool
    decision: str
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "control_id": self.control_id,
            "allow": self.allow,
            "decision": self.decision,
            "details": dict(self.details),
        }


def evaluate_qf_capital_01(capital_ctx: Optional[Dict[str, Any]]) -> ControlVerdict:
    """
    QF-CAPITAL-01: Six-month reserve calculation and capital-allocation gate.
    Invariant: R >= 6 * O, post-allocation (R - delta) >= 6 * O, Bucket 1 sacred.
    Privacy rule: Raw dollar figures are NEVER echoed into the returned details;
    only dimensionless month-coverage ratios are emitted.
    """
    if not isinstance(capital_ctx, dict):
        return ControlVerdict("QF-CAPITAL-01", False, "INVALID_CAPITAL_INPUTS", {})

    reserves = capital_ctx.get("reserves")
    obligations = capital_ctx.get("monthly_obligations")
    allocation = capital_ctx.get("allocation_amount", 0)
    bucket = capital_ctx.get("funding_bucket", "CASH_FLOW_ENGINE")
    shock = capital_ctx.get("financial_shock", False)
    discretionary = capital_ctx.get("discretionary_expansion", False)

    if (
        not _is_real_number(reserves)
        or not _is_real_number(obligations)
        or not _is_real_number(allocation)
        or not isinstance(shock, bool)
        or not isinstance(discretionary, bool)
        or reserves < 0
        or obligations <= 0
        or allocation < 0
        or bucket not in VALID_FUNDING_BUCKETS
    ):
        return ControlVerdict("QF-CAPITAL-01", False, "INVALID_CAPITAL_INPUTS", {})

    r_val = float(reserves)
    o_val = float(obligations)
    a_val = float(allocation)
    six_month_floor = 6.0 * o_val
    post_r = r_val - a_val

    # Dimensionless ratios only (dollars stay off the page)
    ratio_details = {
        "coverage_months": round(r_val / o_val, 2),
        "post_allocation_months": round(post_r / o_val, 2),
        "required_minimum_months": 6.0,
        "funding_bucket": bucket,
    }

    if shock:
        return ControlVerdict("QF-CAPITAL-01", False, "FREEZE_DISCRETIONARY_SPENDING", ratio_details)

    if bucket == "IRON_RESERVE" and (a_val > 0.0 or discretionary):
        return ControlVerdict("QF-CAPITAL-01", False, "IRON_RESERVE_SACRED_LOCK", ratio_details)

    if r_val < six_month_floor:
        return ControlVerdict("QF-CAPITAL-01", False, "PROTECT_AND_REBUILD_RESERVES", ratio_details)

    if r_val == six_month_floor:
        allow_steady = (a_val == 0.0) and (not discretionary)
        return ControlVerdict(
            "QF-CAPITAL-01",
            allow_steady,
            "MAINTAIN_RESERVE_RESTRICT_EXPANSION",
            ratio_details,
        )

    if post_r < six_month_floor:
        return ControlVerdict("QF-CAPITAL-01", False, "POST_ALLOCATION_RESERVE_BREACH", ratio_details)

    return ControlVerdict("QF-CAPITAL-01", True, "EVALUATE_FUNDED_OPPORTUNITY", ratio_details)


def evaluate_qf_privacy_01(privacy_ctx: Optional[Dict[str, Any]]) -> ControlVerdict:
    """
    QF-PRIVACY-01: Local-only processing for confidential research and financial data.
    Enforces $0.00 cloud spend, loopback inference, SHA-256 provenance,
    zero household financial dollar leakage, and Zero Ambient Data filtering.
    """
    if not isinstance(privacy_ctx, dict):
        return ControlVerdict("QF-PRIVACY-01", False, "INVALID_PRIVACY_CONTEXT", {})

    endpoint = privacy_ctx.get("inference_endpoint", "")
    cloud_spend = privacy_ctx.get("cloud_spend_usd", -1)
    external_egress = privacy_ctx.get("external_egress", True)
    classification = privacy_ctx.get("data_classification", "")
    provenance_ok = privacy_ctx.get("provenance_verified", False)
    dollars_exposed = privacy_ctx.get("raw_household_dollars_exposed", False)
    ambient_present = privacy_ctx.get("ambient_identifiers_present", False)

    # Optional telemetry frame inspection via PrivacyFilter
    telemetry_frame = privacy_ctx.get("telemetry_frame")
    if telemetry_frame is not None:
        if not isinstance(telemetry_frame, dict) or PrivacyFilter.sanitize_telemetry_frame(telemetry_frame) is None:
            ambient_present = True

    if not _is_real_number(cloud_spend) or float(cloud_spend) != 0.0:
        return ControlVerdict("QF-PRIVACY-01", False, "ZERO_CLOUD_SPEND_VIOLATION", {"cloud_spend_usd": 0.0})

    if not isinstance(endpoint, str) or endpoint not in ALLOWED_LOOPBACK_ENDPOINTS:
        return ControlVerdict("QF-PRIVACY-01", False, "NON_LOOPBACK_ENDPOINT_DENIED", {"endpoint": str(endpoint)})

    if not isinstance(dollars_exposed, bool) or dollars_exposed:
        return ControlVerdict("QF-PRIVACY-01", False, "HOUSEHOLD_FINANCIAL_EXPOSURE_DENIED", {})

    if not isinstance(ambient_present, bool) or ambient_present:
        return ControlVerdict("QF-PRIVACY-01", False, "AMBIENT_DATA_COLLECTION_DENIED", {})

    if not isinstance(external_egress, bool) or classification not in VALID_CLASSIFICATIONS:
        return ControlVerdict("QF-PRIVACY-01", False, "INVALID_PRIVACY_CONTEXT", {})

    egress_ok = (external_egress is False) or (classification == "public" and external_egress is True)
    if not egress_ok:
        return ControlVerdict("QF-PRIVACY-01", False, "CONFIDENTIAL_EGRESS_DENIED", {"classification": classification})

    if provenance_ok is not True:
        return ControlVerdict("QF-PRIVACY-01", False, "UNVERIFIED_DOCUMENT_PROVENANCE", {})

    return ControlVerdict(
        "QF-PRIVACY-01",
        True,
        "ADMIT_SOVEREIGN_LOCAL",
        {"endpoint": endpoint, "classification": classification, "cloud_spend_usd": 0.0},
    )


def evaluate_qf_auth_01(auth_ctx: Optional[Dict[str, Any]]) -> ControlVerdict:
    """
    QF-AUTH-01: Mandatory human authorization for consequential financial actions.
    Blocks autonomous agent self-authorization, enforces cryptographic credentials,
    RFC 4122 UUIDv4 idempotency, and the 6-decimal USDC invariant.
    """
    if not isinstance(auth_ctx, dict):
        return ControlVerdict("QF-AUTH-01", False, "INVALID_AUTH_CONTEXT", {})

    consequential = auth_ctx.get("consequential_financial_action", True)
    human_auth = auth_ctx.get("human_authorized", False)
    actor_type = auth_ctx.get("actor_type", "unknown")
    authorizer_id = auth_ctx.get("authorizer_id", "")
    credential = auth_ctx.get("auth_credential", "CredNone")
    idem_valid = auth_ctx.get("idempotency_key_valid", False)
    idem_key = auth_ctx.get("idempotency_key")
    usdc_decimals = auth_ctx.get("usdc_decimals", 6)

    if idem_key is not None:
        idem_valid = isinstance(idem_key, str) and bool(UUID_V4_RE.match(idem_key)) and bool(idem_valid or True)
        if "idempotency_key_valid" in auth_ctx and auth_ctx["idempotency_key_valid"] is False:
            idem_valid = False

    if not isinstance(consequential, bool):
        return ControlVerdict("QF-AUTH-01", False, "INVALID_AUTH_CONTEXT", {})

    if consequential is False:
        if actor_type in VALID_ACTOR_TYPES:
            return ControlVerdict("QF-AUTH-01", True, "NON_FINANCIAL_ACTION_PERMITTED", {"actor_type": actor_type})
        return ControlVerdict("QF-AUTH-01", False, "INVALID_AUTH_CONTEXT", {})

    if actor_type == "autonomous_agent":
        return ControlVerdict("QF-AUTH-01", False, "AUTONOMOUS_FINANCIAL_EXECUTION_FORBIDDEN", {})

    if human_auth is not True:
        return ControlVerdict("QF-AUTH-01", False, "MISSING_HUMAN_OPERATOR_APPROVAL", {})

    if actor_type not in {"human_operator", "operator_cosigned_agent"}:
        return ControlVerdict("QF-AUTH-01", False, "INVALID_AUTH_CONTEXT", {})

    if authorizer_id not in APPROVED_AUTHORIZERS:
        return ControlVerdict("QF-AUTH-01", False, "UNVERIFIED_AUTHORIZER_IDENTITY", {})

    if credential not in APPROVED_CREDENTIALS:
        return ControlVerdict("QF-AUTH-01", False, "INSUFFICIENT_CRYPTOGRAPHIC_CREDENTIAL", {})

    if idem_valid is not True:
        return ControlVerdict("QF-AUTH-01", False, "MISSING_DETERMINISTIC_IDEMPOTENCY_KEY", {})

    if not _is_real_number(usdc_decimals) or float(usdc_decimals) != 6.0:
        return ControlVerdict("QF-AUTH-01", False, "USDC_SIX_DECIMAL_INVARIANT_VIOLATION", {})

    return ControlVerdict(
        "QF-AUTH-01",
        True,
        "HUMAN_AUTHORIZATION_VERIFIED",
        {"authorizer_id": authorizer_id, "credential": credential, "usdc_decimals": 6},
    )


def evaluate_qf_ops_01(ops_ctx: Optional[Dict[str, Any]]) -> ControlVerdict:
    """
    QF-OPS-01: Operator workload and operational sustainability monitoring.
    Protects Rahshaun Chambers and all helpers against burnout, sleep deprivation,
    unbounded deep-work sprints, scope sprawl (>1 object/block), and unfair risk transfer.
    """
    if not isinstance(ops_ctx, dict):
        return ControlVerdict("QF-OPS-01", False, "INVALID_OPS_INPUTS", {})

    block_min = ops_ctx.get("continuous_block_minutes")
    daily_hrs = ops_ctx.get("daily_deep_work_hours")
    objects = ops_ctx.get("named_objects_in_block")
    rest_hrs = ops_ctx.get("rest_hours_last_24h")
    fatigue = ops_ctx.get("operator_fatigue_flag", True)
    helper_ok = ops_ctx.get("helper_fairness_verified", False)

    if (
        not _is_real_number(block_min)
        or not _is_real_number(daily_hrs)
        or not _is_real_number(objects)
        or not _is_real_number(rest_hrs)
        or not isinstance(fatigue, bool)
        or not isinstance(helper_ok, bool)
        or block_min < 0
        or daily_hrs < 0
        or objects < 0
        or rest_hrs < 0
    ):
        return ControlVerdict("QF-OPS-01", False, "INVALID_OPS_INPUTS", {})

    metrics = {
        "continuous_block_minutes": float(block_min),
        "daily_deep_work_hours": float(daily_hrs),
        "named_objects_in_block": int(objects),
        "rest_hours_last_24h": float(rest_hrs),
    }

    if fatigue:
        return ControlVerdict("QF-OPS-01", False, "OPERATOR_FATIGUE_RECOVERY_REQUIRED", metrics)

    if not helper_ok:
        return ControlVerdict("QF-OPS-01", False, "HELPER_PROTECTION_VIOLATION", metrics)

    if rest_hrs < 7.0:
        return ControlVerdict("QF-OPS-01", False, "REST_DEFICIT_RECOVERY_REQUIRED", metrics)

    if daily_hrs > 8.0:
        return ControlVerdict("QF-OPS-01", False, "DAILY_WORKLOAD_CEILING_EXCEEDED", metrics)

    if block_min > 90.0:
        return ControlVerdict("QF-OPS-01", False, "DEEP_WORK_BLOCK_LIMIT_EXCEEDED", metrics)

    if objects > 1:
        return ControlVerdict("QF-OPS-01", False, "SINGLE_OBJECT_FOCUS_VIOLATION", metrics)

    return ControlVerdict("QF-OPS-01", True, "SUSTAINABLE_CADENCE_VERIFIED", metrics)


def _scrub_json_safe(obj: Any) -> Any:
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    if isinstance(obj, dict):
        return {str(k): _scrub_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_scrub_json_safe(v) for v in obj]
    return obj


def _normalize_wasm_input(context: Dict[str, Any], py_privacy: ControlVerdict, py_auth: ControlVerdict) -> Dict[str, Any]:
    """Propagates derived Python checks (telemetry_frame, UUIDv4 regex) into Wasm evaluation input."""
    raw_cap = context.get("capital")
    raw_priv = context.get("privacy")
    raw_auth = context.get("auth")
    raw_ops = context.get("ops")

    wasm_in: Dict[str, Any] = {
        "capital": dict(raw_cap) if isinstance(raw_cap, dict) else raw_cap,
        "privacy": dict(raw_priv) if isinstance(raw_priv, dict) else raw_priv,
        "auth": dict(raw_auth) if isinstance(raw_auth, dict) else raw_auth,
        "ops": dict(raw_ops) if isinstance(raw_ops, dict) else raw_ops,
    }
    if isinstance(wasm_in["privacy"], dict):
        wasm_in["privacy"].pop("telemetry_frame", None)
        if py_privacy.decision == "AMBIENT_DATA_COLLECTION_DENIED":
            wasm_in["privacy"]["ambient_identifiers_present"] = True
    if isinstance(wasm_in["auth"], dict) and "idempotency_key" in wasm_in["auth"]:
        raw_key = wasm_in["auth"].pop("idempotency_key")
        key_ok = isinstance(raw_key, str) and bool(UUID_V4_RE.match(raw_key))
        prev_flag = wasm_in["auth"].get("idempotency_key_valid", True)
        wasm_in["auth"]["idempotency_key_valid"] = bool(key_ok and prev_flag is True)
    return _scrub_json_safe(wasm_in)


def evaluate_operating_constitution(
    context: Optional[Dict[str, Any]],
    require_wasm: bool = True,
) -> Dict[str, Any]:
    """
    Evaluates all four permanent Mycelium constitutional controls fail-closed.
    Cross-verifies deterministic Python invariants against the in-process
    OPA Wasm module (`operating_constitution.wasm`). If either layer denies,
    or if Wasm disagrees with Python, execution fails closed (`DENY`).
    """
    if not isinstance(context, dict):
        context = {}

    c_cap = evaluate_qf_capital_01(context.get("capital"))
    c_priv = evaluate_qf_privacy_01(context.get("privacy"))
    c_auth = evaluate_qf_auth_01(context.get("auth"))
    c_ops = evaluate_qf_ops_01(context.get("ops"))

    py_allow = c_cap.allow and c_priv.allow and c_auth.allow and c_ops.allow

    wasm_gatekeeper = get_constitution_wasm_gatekeeper()
    wasm_verified = False
    wasm_allow = False
    wasm_controls: Dict[str, Any] = {}

    if wasm_gatekeeper is not None:
        wasm_input = _normalize_wasm_input(context, c_priv, c_auth)
        wasm_res = wasm_gatekeeper.evaluate_constitution(wasm_input)
        wasm_verified = True
        wasm_allow = bool(wasm_res.get("allow", False))
        wasm_controls = wasm_res.get("controls", {})
    elif require_wasm:
        return {
            "allow": False,
            "verdict": "DENY",
            "reason": "FAIL_CLOSED_WASM_ENGINE_UNAVAILABLE",
            "wasm_verified": False,
            "controls": {
                "QF-CAPITAL-01": c_cap.to_dict(),
                "QF-PRIVACY-01": c_priv.to_dict(),
                "QF-AUTH-01": c_auth.to_dict(),
                "QF-OPS-01": c_ops.to_dict(),
            },
        }
    else:
        wasm_allow = py_allow

    parity_ok = True
    if wasm_verified:
        for cid, py_ctrl in (
            ("QF-CAPITAL-01", c_cap),
            ("QF-PRIVACY-01", c_priv),
            ("QF-AUTH-01", c_auth),
            ("QF-OPS-01", c_ops),
        ):
            w_ctrl = wasm_controls.get(cid, {})
            if bool(w_ctrl.get("allow", False)) != py_ctrl.allow or w_ctrl.get("decision") != py_ctrl.decision:
                parity_ok = False

    final_allow = bool(py_allow and wasm_allow and parity_ok)
    return {
        "allow": final_allow,
        "verdict": "ADMIT" if final_allow else "DENY",
        "wasm_verified": wasm_verified,
        "parity_verified": parity_ok,
        "controls": {
            "QF-CAPITAL-01": c_cap.to_dict(),
            "QF-PRIVACY-01": c_priv.to_dict(),
            "QF-AUTH-01": c_auth.to_dict(),
            "QF-OPS-01": c_ops.to_dict(),
        },
    }
