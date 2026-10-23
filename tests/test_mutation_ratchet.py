"""
Tests for scripts/mutation_ratchet.py: the CI gate that fails when any Rego policy's
surviving-mutant count rises above its committed baseline.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys

import pytest

SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts", "mutation_ratchet.py"))
REPO = os.path.dirname(os.path.dirname(SCRIPT))


def _load():
    spec = importlib.util.spec_from_file_location("mutation_ratchet_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ratchet = _load()


def _report(status, survived, killed=10):
    return {"status": status, "fault_reason": "boom" if status == "FAULT" else None,
            "stats": {"survived": survived, "killed": killed}}


def test_equal_to_baseline_passes():
    ok, message = ratchet.evaluate("p.rego", 20, _report("SURVIVED", 20))
    assert ok and "20" in message


def test_regression_fails():
    ok, message = ratchet.evaluate("p.rego", 20, _report("SURVIVED", 21))
    assert not ok and "21" in message and "20" in message


def test_improvement_passes_and_asks_to_lower_baseline():
    ok, message = ratchet.evaluate("p.rego", 20, _report("SURVIVED", 15))
    assert ok and "lower" in message


def test_zero_baseline_fully_killed_passes():
    ok, _ = ratchet.evaluate("p.rego", 0, _report("PASSED", 0))
    assert ok


def test_engine_fault_fails_regardless_of_counts():
    ok, message = ratchet.evaluate("p.rego", 99, _report("FAULT", 0))
    assert not ok and "boom" in message


@pytest.mark.skipif(shutil.which("opa") is None, reason="opa binary not installed")
def test_committed_baseline_holds_for_repository():
    res = subprocess.run([sys.executable, SCRIPT], cwd=REPO, capture_output=True, text=True)
    assert res.returncode == 0, res.stdout + res.stderr


def test_baseline_covers_every_production_policy():
    with open(os.path.join(REPO, "sentinel", "policies", "mutation_baseline.json")) as f:
        baseline = json.load(f)
    policies = {
        name for name in os.listdir(os.path.join(REPO, "sentinel", "policies"))
        if name.endswith(".rego") and not name.endswith("_test.rego")
        and os.path.exists(os.path.join(REPO, "sentinel", "policies", name[:-5] + "_test.rego"))
    }
    assert policies <= set(baseline), f"policies with tests but no baseline: {sorted(policies - set(baseline))}"
