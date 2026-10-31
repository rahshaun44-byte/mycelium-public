#!/usr/bin/env python3
"""
QuantumFlex Milestone QF-M5.1: Track 0 Household Financial Reserve Reconciler.

Governing Equation (Golden Financial Invariant / QF-CAPITAL-01):
    R_verified_liquid >= 6 * O
    where O = O_household_living + O_debt_service + O_operating

Strict Privacy & Security Invariants:
  1. Private input files MUST reside on local storage with 0600 permissions.
  2. Pending bug bounty awards, anticipated grants, and speculative/illiquid assets
     NEVER count toward R_verified_liquid (Safeguard C).
  3. External paid cloud LLM inference spend MUST equal $0.00.
  4. Zero raw household dollar amounts are ever printed to stdout or written to
     reconciliation receipts — only dimensionless ratios, shares, and gate booleans.
  5. Passing Track 0 closes ONLY the financial reserve gate; it NEVER auto-executes
     QF-A5 cryptographic signing (`qf_a5_signing_ceremony_completed` remains False).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.generate_research_dossier import (
    HardStopGateStatus,
    SecurityBoundaryError,
    evaluate_golden_financial_invariant,
)
from src.operating_constitution import evaluate_operating_constitution

DEFAULT_PRIVATE_WORKSHEET_PATH = (
    Path.home() / ".config" / "quantumflex" / "private" / "track0_worksheet.json"
)
DEFAULT_RECEIPT_OUTPUT_PATH = REPO_ROOT / "build_check" / "track0_reconciliation_receipt.json"
MAX_RECONCILIATION_AGE_DAYS = 30.0
ALLOWED_OPERATOR_IDS = frozenset({"rahshaun_chambers", "rocky", "qf-operator-key"})


class Track0ValidationError(ValueError):
    """Raised when a Track 0 worksheet violates structural, attestation, or cost invariants."""


def _require_non_negative_number(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise Track0ValidationError(f"Field '{field_name}' must be a numeric amount.")
    val = float(value)
    if not math.isfinite(val) or val < 0.0:
        raise Track0ValidationError(f"Field '{field_name}' must be finite and >= 0.0.")
    return val


def _sum_numeric_map(mapping: Any, section_name: str) -> float:
    if not isinstance(mapping, Mapping) or len(mapping) == 0:
        raise Track0ValidationError(f"Section '{section_name}' must be a non-empty JSON object.")
    total = 0.0
    for key, raw_val in mapping.items():
        total += _require_non_negative_number(raw_val, f"{section_name}.{key}")
    return total


def _parse_utc_timestamp(ts_str: Any) -> dt.datetime:
    if not isinstance(ts_str, str) or not ts_str.strip():
        raise Track0ValidationError("Field 'reconciled_at_utc' must be a non-empty ISO-8601 UTC string.")
    normalized = ts_str.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise Track0ValidationError(f"Invalid ISO-8601 timestamp '{ts_str}': {exc}") from exc
    if parsed.tzinfo is None:
        raise Track0ValidationError("Field 'reconciled_at_utc' must include an explicit UTC timezone offset.")
    return parsed.astimezone(dt.timezone.utc)


def load_private_worksheet(worksheet_path: Path) -> Dict[str, Any]:
    """Loads a private Track 0 worksheet JSON after enforcing strict 0600 permissions."""
    if not worksheet_path.is_file():
        raise FileNotFoundError(f"Private Track 0 worksheet not found at {worksheet_path}")
    mode = worksheet_path.stat().st_mode & 0o777
    if mode & 0o077:
        raise PermissionError(
            f"Private Track 0 worksheet {worksheet_path} has insecure permissions {oct(mode)}; "
            "expected 0o600 so household figures remain strictly owner-private."
        )
    data = json.loads(worksheet_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise Track0ValidationError("Worksheet root must be a JSON object.")
    return data


def reconcile_track0_worksheet(
    worksheet: Mapping[str, Any],
    reference_now_utc: Optional[dt.datetime] = None,
) -> Dict[str, Any]:
    """
    Independently validates all 6 Track 0 requirements, cross-checks against
    evaluate_golden_financial_invariant() and operating_constitution.wasm,
    and returns a strictly dimensionless, zero-dollar-leakage reconciliation receipt.
    """
    if not isinstance(worksheet, Mapping):
        raise Track0ValidationError("Worksheet must be a mapping.")
    if worksheet.get("schema") != "qf.track0_worksheet.v1":
        raise Track0ValidationError("Worksheet 'schema' must equal 'qf.track0_worksheet.v1'.")

    now_utc = reference_now_utc or dt.datetime.now(dt.timezone.utc)
    reconciled_dt = _parse_utc_timestamp(worksheet.get("reconciled_at_utc"))
    age_seconds = (now_utc - reconciled_dt).total_seconds()
    if age_seconds < -300.0:
        raise Track0ValidationError("Worksheet 'reconciled_at_utc' cannot be dated in the future.")
    freshness_days = max(age_seconds / 86400.0, 0.0)
    if freshness_days > MAX_RECONCILIATION_AGE_DAYS:
        raise Track0ValidationError(
            f"Track 0 reconciliation is stale ({freshness_days:.2f} days > {MAX_RECONCILIATION_AGE_DAYS:.0f} days max)."
        )

    # Requirement 6: Explicit Operator attestation
    attestation = worksheet.get("operator_attestation")
    if not isinstance(attestation, Mapping):
        raise Track0ValidationError("Missing 'operator_attestation' object.")
    operator_id = str(attestation.get("operator_id", "")).strip().lower()
    if operator_id not in ALLOWED_OPERATOR_IDS:
        raise Track0ValidationError("Attestation 'operator_id' must identify an authorized Operator.")
    for req_flag in (
        "operator_attested",
        "statements_verified_against_primary_institutions",
        "pending_awards_and_speculative_assets_excluded",
    ):
        if attestation.get(req_flag) is not True:
            raise Track0ValidationError(f"Operator attestation flag '{req_flag}' must be explicitly true.")

    # Requirement 1: Verified liquid account balances (excluding pending/speculative)
    liquid_reserves_usd = _sum_numeric_map(
        worksheet.get("verified_liquid_accounts_usd"),
        "verified_liquid_accounts_usd",
    )
    excluded_map = worksheet.get("excluded_non_reserve_items_usd")
    if not isinstance(excluded_map, Mapping):
        raise Track0ValidationError("Missing 'excluded_non_reserve_items_usd' section.")
    pending_bounties_usd = _require_non_negative_number(
        excluded_map.get("pending_bounties", 0.0),
        "excluded_non_reserve_items_usd.pending_bounties",
    )
    anticipated_grants_usd = _require_non_negative_number(
        excluded_map.get("anticipated_grants", 0.0),
        "excluded_non_reserve_items_usd.anticipated_grants",
    )
    speculative_assets_usd = _require_non_negative_number(
        excluded_map.get("speculative_or_illiquid_assets", 0.0),
        "excluded_non_reserve_items_usd.speculative_or_illiquid_assets",
    )

    # Requirement 2: Outstanding debts & monthly debt-service obligations
    debts_list = worksheet.get("outstanding_debts")
    if not isinstance(debts_list, list):
        raise Track0ValidationError("Field 'outstanding_debts' must be a list of debt entries.")
    monthly_debt_service_usd = 0.0
    total_debt_principal_usd = 0.0
    for idx, entry in enumerate(debts_list):
        if not isinstance(entry, Mapping):
            raise Track0ValidationError(f"Debt entry [{idx}] must be an object.")
        if not str(entry.get("name", "")).strip():
            raise Track0ValidationError(f"Debt entry [{idx}] must declare a non-empty 'name'.")
        total_debt_principal_usd += _require_non_negative_number(
            entry.get("principal_balance_usd", 0.0),
            f"outstanding_debts[{idx}].principal_balance_usd",
        )
        monthly_debt_service_usd += _require_non_negative_number(
            entry.get("monthly_payment_usd", 0.0),
            f"outstanding_debts[{idx}].monthly_payment_usd",
        )

    # Requirement 3: Monthly household living expenses
    household_living_usd = _sum_numeric_map(
        worksheet.get("monthly_household_living_expenses_usd"),
        "monthly_household_living_expenses_usd",
    )

    # Requirement 4: Committed QuantumFlex operating-cost baseline
    op_map = worksheet.get("committed_quantumflex_operating_expenses_usd")
    operating_total_usd = _sum_numeric_map(
        op_map,
        "committed_quantumflex_operating_expenses_usd",
    )
    assert isinstance(op_map, Mapping)
    cloud_llm_spend = _require_non_negative_number(
        op_map.get("external_cloud_llm_spend", 0.0),
        "committed_quantumflex_operating_expenses_usd.external_cloud_llm_spend",
    )
    if cloud_llm_spend != 0.0:
        raise SecurityBoundaryError(
            "Zero-Cloud-Spend Invariant Violation: committed external_cloud_llm_spend must equal $0.00."
        )
    llc_overhead = _require_non_negative_number(
        op_map.get("corporate_llc_overhead", 0.0),
        "committed_quantumflex_operating_expenses_usd.corporate_llc_overhead",
    )
    if llc_overhead != 0.0:
        raise Track0ValidationError(
            "PA-LLC is retired under QF-SOVEREIGN non-corporate mode; corporate_llc_overhead must equal 0.0."
        )

    # Requirement 5: Independent 6-month reserve calculation
    combined_monthly_obligations_usd = (
        household_living_usd + monthly_debt_service_usd + operating_total_usd
    )
    if combined_monthly_obligations_usd <= 0.0:
        raise Track0ValidationError(
            "Combined monthly obligations O must be strictly > 0.0 for a valid household reconciliation."
        )
    if household_living_usd + monthly_debt_service_usd <= 0.0:
        raise Track0ValidationError(
            "Household living + debt-service obligations must be > 0.0 (unpopulated template rejected)."
        )

    independent_coverage_months = liquid_reserves_usd / combined_monthly_obligations_usd
    independent_pass = liquid_reserves_usd >= (combined_monthly_obligations_usd * 6.0)

    # Cross-check against Golden Financial Invariant + Operating Constitution Wasm
    invariant_eval = evaluate_golden_financial_invariant(
        reserves_usd=liquid_reserves_usd,
        monthly_obligations_usd=combined_monthly_obligations_usd,
        pending_bounties_usd=pending_bounties_usd + speculative_assets_usd,
        pending_grants_usd=anticipated_grants_usd,
    )
    if invariant_eval.invariant_satisfied != independent_pass:
        raise RuntimeError("Internal parity mismatch between Track 0 reconciler and GoldenFinancialEvaluation.")

    # Verify Wasm privacy & capital evaluation using dimensionless ratio inputs (zero dollar exposure)
    wasm_eval = evaluate_operating_constitution(
        {
            "capital": {
                "reserves": round(independent_coverage_months, 6),
                "monthly_obligations": 1.0,
                "allocation_amount": 0.0,
                "funding_bucket": "CORE_RESERVE" if not independent_pass else "SURPLUS_GROWTH",
                "financial_shock": False,
                "discretionary_expansion": False,
            },
            "privacy": {
                "inference_endpoint": "http://127.0.0.1:11434",
                "cloud_spend_usd": 0.0,
                "external_egress": False,
                "data_classification": "household_financial",
                "provenance_verified": True,
                "raw_household_dollars_exposed": False,
                "ambient_identifiers_present": False,
            },
            "auth": {
                "consequential_financial_action": False,
                "actor_type": "rahshaun_chambers",
            },
            "ops": {
                "continuous_block_minutes": 30,
                "daily_deep_work_hours": 1.5,
                "named_objects_in_block": 1,
                "rest_hours_last_24h": 8.0,
                "operator_fatigue_flag": False,
                "helper_fairness_verified": True,
            },
        },
        require_wasm=True,
    )
    if not wasm_eval.get("wasm_verified") or not wasm_eval.get("parity_verified"):
        raise SecurityBoundaryError("Operating Constitution Wasm verification failed during Track 0 check.")

    gate_status = HardStopGateStatus(
        hs_px_pixel_cve_2026_58704_patched=True,
        as_01_03_account_security_verified=True,
        pa_llc_finallyfungus_subsistence_verified=False,
        track_0_reserve_ratio_gte_6m=independent_pass,
        sovereign_non_corporate_mode=True,
        individual_tax_and_program_compliance_verified=True,
        qf_a5_signing_ceremony_completed=False,
    )

    household_share_pct = round((household_living_usd / combined_monthly_obligations_usd) * 100.0, 2)
    debt_share_pct = round((monthly_debt_service_usd / combined_monthly_obligations_usd) * 100.0, 2)
    operating_share_pct = round((operating_total_usd / combined_monthly_obligations_usd) * 100.0, 2)
    debt_to_annual_obligations_ratio = round(
        total_debt_principal_usd / (combined_monthly_obligations_usd * 12.0),
        4,
    )

    return {
        "schema": "qf.track0_reconciliation_receipt.v1",
        "milestone": "QF-M5.1",
        "reconciled_at_utc": reconciled_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "evaluated_at_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "freshness_days": round(freshness_days, 4),
        "raw_dollar_figures_omitted": True,
        "operator_attested": True,
        "pending_bounties_excluded": True,
        "anticipated_grants_excluded": True,
        "speculative_assets_excluded": True,
        "operating_cost_baseline_verified": {
            "zero_cloud_llm_spend_verified": True,
            "pa_llc_retired_zero_corporate_overhead": True,
            "operating_share_of_monthly_obligations_pct": operating_share_pct,
        },
        "dimensionless_ratios": {
            "verified_liquid_coverage_months": round(independent_coverage_months, 2),
            "required_minimum_coverage_months": 6.0,
            "household_living_share_pct": household_share_pct,
            "debt_service_share_pct": debt_share_pct,
            "quantumflex_operating_share_pct": operating_share_pct,
            "debt_principal_to_annual_obligations_ratio": debt_to_annual_obligations_ratio,
        },
        "track_0_gate": {
            "status": "CLOSED" if independent_pass else "OPEN",
            "invariant_satisfied": independent_pass,
            "capital_posture": wasm_eval["controls"]["QF-CAPITAL-01"]["decision"],
            "discretionary_capex_decision": invariant_eval.discretionary_capex_decision,
            "wasm_parity_verified": True,
        },
        "cryptographic_boundary": {
            "HS-PX": "CLOSED",
            "AS-01..03": "CLOSED",
            "PA-LLC": "RETIRED",
            "TRACK_0": "CLOSED" if independent_pass else "OPEN",
            "PERSONAL_HARD_STOPS_CLEARED": gate_status.personal_hard_stops_cleared,
            "ALL_HARD_STOPS": gate_status.all_cleared,
            "QF_A5_SIGNING": "READY_FOR_HUMAN_CEREMONY" if independent_pass else "GATED",
            "ADMISSION_SIGNED": False,
        },
    }


def build_unreconciled_status_snapshot() -> Dict[str, Any]:
    """Returns the honest default open Track 0 ledger state when no private worksheet has been reconciled."""
    gate_status = HardStopGateStatus()
    return {
        "schema": "qf.track0_reconciliation_receipt.v1",
        "milestone": "QF-M5.1",
        "raw_dollar_figures_omitted": True,
        "operator_attested": False,
        "track_0_gate": {
            "status": "OPEN",
            "invariant_satisfied": False,
            "reason": "Awaiting offline Operator household reconciliation worksheet (~/.config/quantumflex/private/track0_worksheet.json).",
        },
        "cryptographic_boundary": {
            "HS-PX": "CLOSED",
            "AS-01..03": "CLOSED",
            "PA-LLC": "RETIRED",
            "TRACK_0": "OPEN",
            "PERSONAL_HARD_STOPS_CLEARED": gate_status.personal_hard_stops_cleared,
            "ALL_HARD_STOPS": gate_status.all_cleared,
            "QF_A5_SIGNING": "GATED",
            "ADMISSION_SIGNED": False,
        },
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Independently validate Track 0 reserves (R_verified_liquid >= 6O) with zero raw dollar output."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_PRIVATE_WORKSHEET_PATH,
        help="Path to 0600-permissioned private Track 0 worksheet JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_RECEIPT_OUTPUT_PATH,
        help="Output path for dimensionless Track 0 reconciliation receipt JSON",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Report current Track 0 & cryptographic boundary status without requiring private input",
    )
    args = parser.parse_args(argv)

    if args.status and not args.input.is_file():
        snapshot = build_unreconciled_status_snapshot()
        print(json.dumps(snapshot, indent=2))
        return 0

    worksheet = load_private_worksheet(args.input)
    receipt = reconcile_track0_worksheet(worksheet)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
