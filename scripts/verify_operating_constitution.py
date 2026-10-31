#!/usr/bin/env python3
"""
QuantumFlex Operating Constitution Enforcement Engine
=====================================================
Programmatically enforces the four permanent constitutional controls defined
in `knowledge_vault/01_MISSION_AND_GOALS.md`:

  - QF-CAPITAL-01 : Six-month reserve calculation & capital-allocation gate (R >= 6*O)
  - QF-PRIVACY-01 : Local-only processing for confidential research & financial data
  - QF-AUTH-01    : Explicit human Operator authorization for consequential financial actions
  - QF-OPS-01     : Operator workload & operational sustainability protection
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from typing import Any, Dict
from urllib.parse import urlparse


@dataclass(frozen=True)
class ConstitutionalVerdict:
    control_id: str
    allowed: bool
    decision: str
    reason: str


def evaluate_qf_capital_01(
    liquid_reserves_usd: float,
    monthly_obligations_usd: float,
    proposed_discretionary_spend_usd: float = 0.0,
    customer_funded_hardware: bool = True,
    unexpected_shock_active: bool = False,
    verified_liquid_only: bool = True,
    committed_operating_obligations_usd: float = 0.0,
) -> ConstitutionalVerdict:
    """
    QF-CAPITAL-01: Enforces R >= 6 * O fail-closed capital allocation gate.
    Privacy rule: Raw dollar figures stay off the page; only dimensionless
    coverage-month ratios are emitted into verdict reasons.
    """
    total_obligations = monthly_obligations_usd + committed_operating_obligations_usd
    if (
        not verified_liquid_only
        or total_obligations <= 0
        or monthly_obligations_usd < 0
        or committed_operating_obligations_usd < 0
        or liquid_reserves_usd < 0
        or proposed_discretionary_spend_usd < 0
    ):
        return ConstitutionalVerdict(
            control_id="QF-CAPITAL-01",
            allowed=False,
            decision="DENY_INVALID_INPUT",
            reason="Verified liquid reserves and positive monthly obligations are required (fail-closed).",
        )

    required_six_month_reserve = 6.0 * total_obligations
    coverage_months = liquid_reserves_usd / total_obligations
    post_spend_reserves = liquid_reserves_usd - proposed_discretionary_spend_usd
    post_months = post_spend_reserves / total_obligations

    if unexpected_shock_active:
        if proposed_discretionary_spend_usd > 0:
            return ConstitutionalVerdict(
                control_id="QF-CAPITAL-01",
                allowed=False,
                decision="FREEZE_AND_RECALCULATE",
                reason="Unexpected financial shock active: all discretionary spending is frozen.",
            )
        return ConstitutionalVerdict(
            control_id="QF-CAPITAL-01",
            allowed=True,
            decision="FREEZE_AND_RECALCULATE",
            reason="Shock mode active with zero discretionary spend.",
        )

    if not customer_funded_hardware and proposed_discretionary_spend_usd > 0:
        return ConstitutionalVerdict(
            control_id="QF-CAPITAL-01",
            allowed=False,
            decision="DENY_SPECULATIVE_HARDWARE",
            reason="Speculative unfunded hardware purchases are prohibited by QF-CAPITAL-01.",
        )

    if liquid_reserves_usd < required_six_month_reserve:
        return ConstitutionalVerdict(
            control_id="QF-CAPITAL-01",
            allowed=proposed_discretionary_spend_usd == 0.0,
            decision="PROTECT_AND_REBUILD",
            reason=(
                f"Coverage ({coverage_months:.2f} months) is below the 6.00-month floor. "
                "Protect and rebuild Bucket 1."
            ),
        )

    if post_spend_reserves < required_six_month_reserve:
        return ConstitutionalVerdict(
            control_id="QF-CAPITAL-01",
            allowed=False,
            decision="MAINTAIN_RESERVE_RESTRICT_EXPANSION",
            reason=(
                f"Proposed allocation reduces coverage from {coverage_months:.2f} to {post_months:.2f} months, "
                "piercing the 6.00-month reserve floor."
            ),
        )

    if post_spend_reserves == required_six_month_reserve:
        return ConstitutionalVerdict(
            control_id="QF-CAPITAL-01",
            allowed=True,
            decision="MAINTAIN_RESERVE",
            reason="Post-allocation coverage sits at 6.00 months; zero-outlay operations only.",
        )

    return ConstitutionalVerdict(
        control_id="QF-CAPITAL-01",
        allowed=True,
        decision="ADMIT_FUNDED_OPPORTUNITY",
        reason=(
            f"Post-allocation coverage ({post_months:.2f} months) strictly exceeds "
            "the 6.00-month constitutional floor."
        ),
    )


def evaluate_qf_privacy_01(
    inference_url: str,
    cloud_spend_usd: float = 0.0,
    contains_household_or_proprietary_data: bool = True,
    ambient_data_sanitized: bool = True,
) -> ConstitutionalVerdict:
    """
    QF-PRIVACY-01: Enforces loopback-only local inference (127.0.0.1 / ::1 / localhost),
    $0.00 cloud spend, and zero ambient data leakage.
    """
    if cloud_spend_usd > 0.0:
        return ConstitutionalVerdict(
            control_id="QF-PRIVACY-01",
            allowed=False,
            decision="DENY_CLOUD_SPEND",
            reason=f"Non-zero cloud inference spend (${cloud_spend_usd:.2f}) violates the $0.00 invariant.",
        )

    if not ambient_data_sanitized:
        return ConstitutionalVerdict(
            control_id="QF-PRIVACY-01",
            allowed=False,
            decision="DENY_UNSANITIZED_TELEMETRY",
            reason="Telemetry or document payload has not passed PrivacyFilter sanitization.",
        )

    parsed = urlparse(inference_url)
    host = (parsed.hostname or "").lower()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        return ConstitutionalVerdict(
            control_id="QF-PRIVACY-01",
            allowed=False,
            decision="DENY_EXTERNAL_ENDPOINT",
            reason=(
                f"Endpoint host '{host}' is not loopback. Confidential research and household "
                "financial data must never leave local hardware."
            ),
        )

    return ConstitutionalVerdict(
        control_id="QF-PRIVACY-01",
        allowed=True,
        decision="ALLOW_SOVEREIGN_LOCAL",
        reason="Loopback inference verified (127.0.0.1), $0.00 cloud spend, PrivacyFilter active.",
    )


def evaluate_qf_auth_01(
    consequential_financial_action: bool,
    operator_human_authorized: bool,
    two_man_or_hardware_attested: bool,
    deterministic_idempotency_key: str = "",
) -> ConstitutionalVerdict:
    """
    QF-AUTH-01: Requires explicit human Operator authorization and hardware/two-man
    attestation for any consequential financial action.
    """
    if not consequential_financial_action:
        return ConstitutionalVerdict(
            control_id="QF-AUTH-01",
            allowed=True,
            decision="ALLOW_READ_ONLY",
            reason="Non-mutating / read-only operation requires no financial settlement signature.",
        )

    if not operator_human_authorized:
        return ConstitutionalVerdict(
            control_id="QF-AUTH-01",
            allowed=False,
            decision="DENY_MISSING_OPERATOR_APPROVAL",
            reason="Consequential financial action rejected: missing explicit human authorization from Rahshaun Chambers.",
        )

    if not two_man_or_hardware_attested:
        return ConstitutionalVerdict(
            control_id="QF-AUTH-01",
            allowed=False,
            decision="DENY_MISSING_HARDWARE_ATTESTATION",
            reason="Consequential financial action rejected: missing Pluton TPM 2.0 / Titan M2 hardware attestation.",
        )

    if len(deterministic_idempotency_key.strip()) < 16:
        return ConstitutionalVerdict(
            control_id="QF-AUTH-01",
            allowed=False,
            decision="DENY_MISSING_IDEMPOTENCY_KEY",
            reason="Consequential financial action rejected: missing deterministic idempotency key.",
        )

    return ConstitutionalVerdict(
        control_id="QF-AUTH-01",
        allowed=True,
        decision="ALLOW_AUTHORIZED_SETTLEMENT",
        reason="Human Operator authorization, hardware attestation, and deterministic idempotency verified.",
    )


def evaluate_qf_ops_01(
    daily_operator_hours: float,
    max_sustainable_daily_hours: float = 6.0,
    uninterrupted_rest_hours: float = 8.0,
    active_concurrent_heavy_models: int = 1,
) -> ConstitutionalVerdict:
    """
    QF-OPS-01: Protects Operator workload, rest, and system sustainability.
    A system that exhausts its Operator has failed its purpose.
    """
    if daily_operator_hours > max_sustainable_daily_hours:
        return ConstitutionalVerdict(
            control_id="QF-OPS-01",
            allowed=False,
            decision="THROTTLE_PROTECT_OPERATOR_PEACE",
            reason=(
                f"Operator workload ({daily_operator_hours:.1f}h) exceeds sustainable ceiling "
                f"({max_sustainable_daily_hours:.1f}h). Defer non-essential tasks; protect peace and recovery."
            ),
        )

    if uninterrupted_rest_hours < 7.0:
        return ConstitutionalVerdict(
            control_id="QF-OPS-01",
            allowed=False,
            decision="ENFORCE_RECOVERY_WINDOW",
            reason=(
                f"Rest window ({uninterrupted_rest_hours:.1f}h) is below minimum recovery floor (7.0h). "
                "Operator health and peace take precedence over expansion."
            ),
        )

    if active_concurrent_heavy_models > 1:
        return ConstitutionalVerdict(
            control_id="QF-OPS-01",
            allowed=False,
            decision="DENY_MEMORY_OVERCOMMIT",
            reason=(
                f"Concurrent heavy models ({active_concurrent_heavy_models}) exceed 14 GiB host ceiling "
                "(max 1 heavy model active)."
            ),
        )

    return ConstitutionalVerdict(
        control_id="QF-OPS-01",
        allowed=True,
        decision="SUSTAINABLE_OPERATING_PACE",
        reason="Operator workload, recovery window, and 14 GiB hardware concurrency are within peaceful sustainable bounds.",
    )


def evaluate_all_controls(state: Dict[str, Any]) -> Dict[str, Any]:
    v_cap = evaluate_qf_capital_01(**state.get("capital", {}))
    v_priv = evaluate_qf_privacy_01(**state.get("privacy", {}))
    v_auth = evaluate_qf_auth_01(**state.get("auth", {}))
    v_ops = evaluate_qf_ops_01(**state.get("ops", {}))

    verdicts = [v_cap, v_priv, v_auth, v_ops]
    all_passed = all(v.allowed for v in verdicts)
    return {
        "constitution_aligned": all_passed,
        "verdicts": {v.control_id: asdict(v) for v in verdicts},
    }


if __name__ == "__main__":
    baseline_state = {
        "capital": {
            "liquid_reserves_usd": 36000.0,
            "monthly_obligations_usd": 5000.0,
            "proposed_discretionary_spend_usd": 0.0,
            "customer_funded_hardware": True,
            "unexpected_shock_active": False,
        },
        "privacy": {
            "inference_url": "http://127.0.0.1:11434",
            "cloud_spend_usd": 0.0,
            "contains_household_or_proprietary_data": True,
            "ambient_data_sanitized": True,
        },
        "auth": {
            "consequential_financial_action": False,
            "operator_human_authorized": True,
            "two_man_or_hardware_attested": True,
            "deterministic_idempotency_key": "00000000-0000-4000-8000-000000000001",
        },
        "ops": {
            "daily_operator_hours": 4.5,
            "max_sustainable_daily_hours": 6.0,
            "uninterrupted_rest_hours": 8.5,
            "active_concurrent_heavy_models": 1,
        },
    }
    report = evaluate_all_controls(baseline_state)
    print(json.dumps(report, indent=2))
    sys.exit(0 if report["constitution_aligned"] else 1)
