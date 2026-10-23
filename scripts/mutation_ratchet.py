#!/usr/bin/env python3
"""
Rego mutation ratchet for CI.

Runs scripts/ast_mutation_engine.py on every policy listed in
sentinel/policies/mutation_baseline.json and fails if any policy's surviving-mutant
count rises above its committed baseline, or if the engine faults. A count below
baseline passes and asks for the baseline to be lowered, so gains can be locked in.

Exit codes: 0 = no policy regressed, 1 = regression or engine fault.
"""

import json
import os
import subprocess
import sys
import tempfile
from typing import Any, Dict, Tuple

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POLICY_DIR = os.path.join(REPO, "sentinel", "policies")
BASELINE_PATH = os.path.join(POLICY_DIR, "mutation_baseline.json")
ENGINE = os.path.join(REPO, "scripts", "ast_mutation_engine.py")


def evaluate(policy: str, max_survived: int, report: Dict[str, Any]) -> Tuple[bool, str]:
    """Judges one engine report against its baseline. Returns (passed, message)."""
    if report.get("status") == "FAULT":
        return False, f"FAIL {policy}: engine fault: {report.get('fault_reason')}"
    survived = report["stats"]["survived"]
    killed = report["stats"]["killed"]
    if survived > max_survived:
        return False, f"FAIL {policy}: {survived} survivors exceeds baseline {max_survived} ({killed} killed)"
    if survived < max_survived:
        return True, (
            f"PASS {policy}: {survived} survivors, below baseline {max_survived}; "
            f"lower max_survived to {survived} in mutation_baseline.json to lock this in"
        )
    return True, f"PASS {policy}: {survived} survivors (baseline {max_survived}, {killed} killed)"


def run_engine(policy: str) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "report.json")
        subprocess.run(
            [sys.executable, ENGINE, os.path.join(POLICY_DIR, policy), "--json-out", out],
            capture_output=True,
            text=True,
        )
        if not os.path.exists(out):
            return {"status": "FAULT", "fault_reason": "engine wrote no report"}
        with open(out, encoding="utf-8") as f:
            return json.load(f)


def main() -> int:
    with open(BASELINE_PATH, encoding="utf-8") as f:
        baseline = json.load(f)
    all_ok = True
    for policy, entry in sorted(baseline.items()):
        ok, message = evaluate(policy, entry["max_survived"], run_engine(policy))
        print(message)
        all_ok = all_ok and ok
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
