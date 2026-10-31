#!/usr/bin/env python3
"""
QuantumFlex Milestone QF-M5.1: Prepared QF-A5 Signing Ceremony Preflight & Guarded Runner.

Enforces the strict two-step cryptographic boundary:
  1. Closing security gates (HS-PX, AS-01..03) and retiring PA-LLC NEVER auto-authorizes
     cryptographic signing.
  2. Track 0 (R_verified_liquid >= 6O) must independently pass via a fresh, attested,
     ratio-only Track 0 receipt.
  3. Even after Track 0 passes, preflight mode (`--preflight`, the default) NEVER signs
     artifacts (`ADMISSION_SIGNED = FALSE`). Signing occurs ONLY when a human Operator
     explicitly invokes `--execute-ceremony` with `--operator-confirm-ceremony` and a
     0600-permissioned Ed25519 release key.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.generate_research_dossier import HardStopGateStatus
from src.admission_receipt import (
    DEFAULT_PRIVATE_KEY_PATH,
    DEFAULT_PUBLIC_KEY_PATH,
    DEFAULT_REQUIRED_ARTIFACTS,
    build_admission_payload,
    compute_file_sha256,
    ensure_or_load_release_keypair,
    resolve_git_state,
    sign_admission_receipt,
    verify_admission_receipt,
)

QF_M5_REQUIRED_ARTIFACTS: tuple[str, ...] = DEFAULT_REQUIRED_ARTIFACTS + (
    "src/operating_constitution.py",
    "src/bounty_assurance.py",
    "sentinel/policies/operating_constitution.wasm",
    "scripts/generate_research_dossier.py",
    "scripts/verify_dossier_independent.py",
    "scripts/reconcile_track0_reserves.py",
    "docs/audits/2026-10-30-notion-checklist-reconciliation.md",
)

DEFAULT_PREFLIGHT_PATH = REPO_ROOT / "build_check" / "qf_a5_ceremony_preflight.json"
DEFAULT_TRACK0_RECEIPT_PATH = REPO_ROOT / "build_check" / "track0_reconciliation_receipt.json"
REQUIRED_CONFIRMATION_PHRASE = "I_AUTHORIZE_QF_A5_SIGNING"


def _evaluate_track0_receipt(track0_receipt_path: Optional[Path]) -> bool:
    """Returns True only if a valid, operator-attested Track 0 ratio receipt proves >= 6.0 months."""
    if track0_receipt_path is None or not track0_receipt_path.is_file():
        return False
    data = json.loads(track0_receipt_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return False
    if data.get("schema") != "qf.track0_reconciliation_receipt.v1":
        return False
    if data.get("operator_attested") is not True:
        return False
    if data.get("raw_dollar_figures_omitted") is not True:
        return False
    gate = data.get("track_0_gate", {})
    ratios = data.get("dimensionless_ratios", {})
    if not isinstance(gate, dict) or not isinstance(ratios, dict):
        return False
    coverage = float(ratios.get("verified_liquid_coverage_months", 0.0))
    return (
        gate.get("status") == "CLOSED"
        and gate.get("invariant_satisfied") is True
        and gate.get("wasm_parity_verified") is True
        and coverage >= 6.0
    )


def build_qf_a5_preflight_manifest(
    repo_root: Path = REPO_ROOT,
    track0_receipt_path: Optional[Path] = DEFAULT_TRACK0_RECEIPT_PATH,
    required_artifacts: Iterable[str] = QF_M5_REQUIRED_ARTIFACTS,
    evaluated_at_utc: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Prepares and validates QF-A5 ceremony readiness WITHOUT touching private keys
    or generating any cryptographic signature.
    """
    artifact_digests: Dict[str, str] = {}
    for rel_path in required_artifacts:
        artifact_digests[rel_path] = compute_file_sha256(repo_root / rel_path)

    git_state = resolve_git_state(repo_root)
    track0_closed = _evaluate_track0_receipt(track0_receipt_path)

    gate_status = HardStopGateStatus(
        hs_px_pixel_cve_2026_58704_patched=True,
        as_01_03_account_security_verified=True,
        pa_llc_finallyfungus_subsistence_verified=False,
        track_0_reserve_ratio_gte_6m=track0_closed,
        sovereign_non_corporate_mode=True,
        individual_tax_and_program_compliance_verified=True,
        qf_a5_signing_ceremony_completed=False,
    )

    ts = evaluated_at_utc or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "schema": "qf.a5_ceremony_preflight.v1",
        "milestone": "QF-M5.1",
        "evaluated_at_utc": ts,
        "git_branch": git_state["git_branch"],
        "git_commit": git_state["git_commit"],
        "ledger_state": {
            "HS-PX": "CLOSED",
            "AS-01..03": "CLOSED",
            "PA-LLC": "RETIRED",
            "TRACK_0": "CLOSED" if track0_closed else "OPEN",
            "ALL_HARD_STOPS": gate_status.all_cleared,
            "PERSONAL_HARD_STOPS_CLEARED": gate_status.personal_hard_stops_cleared,
            "QF_A5_SIGNING": "READY_FOR_HUMAN_CEREMONY" if track0_closed else "GATED",
            "ADMISSION_SIGNED": False,
        },
        "artifact_sha256": artifact_digests,
        "authorized_ceremony_runbook": [
            "1. Reconcile offline ~/.config/quantumflex/private/track0_worksheet.json (0600) via scripts/reconcile_track0_reserves.py.",
            "2. Confirm TRACK_0 == CLOSED and PERSONAL_HARD_STOPS_CLEARED == True in preflight output.",
            "3. Verify Ed25519 release key permissions (0600) at ~/.config/quantumflex/keys/qf_release_ed25519.pem.",
            "4. Execute human-authorized signing ceremony with --execute-ceremony --operator-confirm-ceremony I_AUTHORIZE_QF_A5_SIGNING.",
            "5. Verify detached provenance via ~/.local/libexec/quantumflex/verify-provenance.",
        ],
    }


def execute_guarded_qf_a5_ceremony(
    *,
    repo_root: Path = REPO_ROOT,
    track0_receipt_path: Optional[Path] = DEFAULT_TRACK0_RECEIPT_PATH,
    private_key_path: Path = DEFAULT_PRIVATE_KEY_PATH,
    public_key_path: Path = DEFAULT_PUBLIC_KEY_PATH,
    output_receipt_path: Path,
    operator_confirmation: str = "",
    required_artifacts: Iterable[str] = QF_M5_REQUIRED_ARTIFACTS,
) -> Dict[str, Any]:
    """
    Executes the QF-A5 Ed25519 signing ceremony ONLY when:
      1. Track 0 financial gate independently passes (`TRACK_0 == CLOSED`), AND
      2. Explicit human confirmation phrase `I_AUTHORIZE_QF_A5_SIGNING` is supplied, AND
      3. Valid 0600-permissioned Ed25519 private key is present.
    Otherwise fails closed with PermissionError without writing any signed artifact.
    """
    preflight = build_qf_a5_preflight_manifest(
        repo_root=repo_root,
        track0_receipt_path=track0_receipt_path,
        required_artifacts=required_artifacts,
    )
    if preflight["ledger_state"]["TRACK_0"] != "CLOSED":
        raise PermissionError(
            "QF-A5 Ceremony Blocked (Fail-Closed): TRACK_0 financial reserve gate is OPEN. "
            "Closing security gates does not authorize cryptographic signing."
        )
    if operator_confirmation != REQUIRED_CONFIRMATION_PHRASE:
        raise PermissionError(
            "QF-A5 Ceremony Blocked (Fail-Closed): Explicit human authorization phrase "
            f"'{REQUIRED_CONFIRMATION_PHRASE}' is required."
        )

    priv_key, pub_key = ensure_or_load_release_keypair(
        private_key_path=private_key_path,
        public_key_path=public_key_path,
        auto_generate_if_missing=False,
    )
    completed_gate = HardStopGateStatus(
        hs_px_pixel_cve_2026_58704_patched=True,
        as_01_03_account_security_verified=True,
        pa_llc_finallyfungus_subsistence_verified=False,
        track_0_reserve_ratio_gte_6m=True,
        sovereign_non_corporate_mode=True,
        individual_tax_and_program_compliance_verified=True,
        qf_a5_signing_ceremony_completed=True,
    )
    payload = build_admission_payload(repo_root=repo_root, required_artifacts=required_artifacts)
    payload["qf_m5_ceremony_boundary"] = {
        "HS-PX": "CLOSED",
        "AS-01..03": "CLOSED",
        "PA-LLC": "RETIRED",
        "TRACK_0": "CLOSED",
        "PERSONAL_HARD_STOPS_CLEARED": completed_gate.personal_hard_stops_cleared,
        "ALL_HARD_STOPS": completed_gate.all_cleared,
        "QF_A5_SIGNING": "PASS",
        "ADMISSION_SIGNED": True,
    }
    signed_receipt = sign_admission_receipt(payload=payload, private_key=priv_key)
    verify_admission_receipt(signed_receipt, repo_root=repo_root, trusted_public_key=pub_key)

    output_receipt_path.parent.mkdir(parents=True, exist_ok=True)
    output_receipt_path.write_text(
        json.dumps(signed_receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return signed_receipt


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prepare (without premature signing) or guard the QuantumFlex QF-A5 signing ceremony."
    )
    parser.add_argument(
        "--preflight",
        action="store_true",
        default=True,
        help="Validate artifact hashes and hard-stop ledger without signing (default)",
    )
    parser.add_argument(
        "--track0-receipt",
        type=Path,
        default=DEFAULT_TRACK0_RECEIPT_PATH,
        help="Path to dimensionless Track 0 reconciliation receipt JSON",
    )
    parser.add_argument(
        "--preflight-output",
        type=Path,
        default=DEFAULT_PREFLIGHT_PATH,
        help="Path to write unsigned QF-A5 preflight readiness manifest",
    )
    parser.add_argument(
        "--execute-ceremony",
        action="store_true",
        help="Execute Ed25519 signing ONLY if Track 0 is CLOSED and human confirmation is provided",
    )
    parser.add_argument(
        "--operator-confirm-ceremony",
        default="",
        help="Exact human confirmation phrase required when --execute-ceremony is set",
    )
    parser.add_argument(
        "--signed-output",
        type=Path,
        default=REPO_ROOT / "build_check" / "qf_m5_signed_admission_receipt.json",
        help="Target path for signed receipt if ceremony is explicitly authorized",
    )
    parser.add_argument(
        "--private-key",
        type=Path,
        default=DEFAULT_PRIVATE_KEY_PATH,
        help="Path to 0600 Ed25519 release private key PEM",
    )
    parser.add_argument(
        "--public-key",
        type=Path,
        default=DEFAULT_PUBLIC_KEY_PATH,
        help="Path to Ed25519 release public key PEM",
    )
    args = parser.parse_args(argv)

    if args.execute_ceremony:
        signed = execute_guarded_qf_a5_ceremony(
            track0_receipt_path=args.track0_receipt,
            private_key_path=args.private_key,
            public_key_path=args.public_key,
            output_receipt_path=args.signed_output,
            operator_confirmation=args.operator_confirm_ceremony,
        )
        print(json.dumps({"ceremony_executed": True, "seal": signed["cryptographic_seal"]}, indent=2))
        return 0

    preflight = build_qf_a5_preflight_manifest(track0_receipt_path=args.track0_receipt)
    args.preflight_output.parent.mkdir(parents=True, exist_ok=True)
    args.preflight_output.write_text(json.dumps(preflight, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(preflight, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
