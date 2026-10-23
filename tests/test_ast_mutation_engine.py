"""
Tests for QuantumFlex AST-Aware Source Span Mutation Engine.
Validates the 7 core mutation behaviors:
1. Strong suite: 5/5 killed, 1 INVALID (an assignment); covers multi-line & negated; synthetic bodies skipped.
2. Weak suite: survivors reported, exit 1.
3. Conflicting function: 1 EXECUTION_ERROR and 1 KILLED, exit 2 (error not counted as kill).
4. No mutable expressions: exit 2.
5. Failing baseline: exit 2.
6. Missing policy file: exit 2.
7. Copy of real sentinel/policies: bootgate mutants executed (24/24), directory hashes unchanged.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
import pytest

ENGINE_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "scripts", "ast_mutation_engine.py")
)


def hash_directory(dir_path: str) -> dict:
    """Computes SHA-256 hashes for all files in a directory."""
    hashes = {}
    for root, _, files in os.walk(dir_path):
        for f in sorted(files):
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, dir_path)
            with open(full_path, "rb") as fp:
                hashes[rel_path] = hashlib.sha256(fp.read()).hexdigest()
    return hashes


def test_strong_suite():
    """
    Strong suite:
    - 5/5 killed
    - 1 INVALID (an assignment)
    - covers multi-line expression
    - covers negated expression
    - synthetic bodies are not mutated
    - exits 0
    """
    policy_code = """package strong
import rego.v1

default allow := false
const_val := 42

allow if {
    x := 10
    input.val == 100
    input.multi ==
        200
    not input.flag
    input.score > 50
    input.limit < 1000
}
"""
    test_code = """package strong
import rego.v1

test_allow_pass if {
    allow with input as {
        "val": 100,
        "multi": 200,
        "flag": false,
        "score": 51,
        "limit": 999,
    }
}

test_allow_fail_val if {
    not allow with input as {
        "val": 99,
        "multi": 200,
        "flag": false,
        "score": 51,
        "limit": 999,
    }
}

test_allow_fail_multi if {
    not allow with input as {
        "val": 100,
        "multi": 999,
        "flag": false,
        "score": 51,
        "limit": 999,
    }
}

test_allow_fail_flag if {
    not allow with input as {
        "val": 100,
        "multi": 200,
        "flag": true,
        "score": 51,
        "limit": 999,
    }
}

test_allow_fail_score if {
    not allow with input as {
        "val": 100,
        "multi": 200,
        "flag": false,
        "score": 50,
        "limit": 999,
    }
}

test_allow_fail_limit if {
    not allow with input as {
        "val": 100,
        "multi": 200,
        "flag": false,
        "score": 51,
        "limit": 1000,
    }
}
"""
    with tempfile.TemporaryDirectory() as td:
        policy_file = os.path.join(td, "policy.rego")
        test_file = os.path.join(td, "policy_test.rego")
        json_out = os.path.join(td, "report.json")

        with open(policy_file, "w") as f:
            f.write(policy_code)
        with open(test_file, "w") as f:
            f.write(test_code)

        res = subprocess.run(
            [sys.executable, ENGINE_PATH, policy_file, "--json-out", json_out],
            capture_output=True,
            text=True,
        )

        assert res.returncode == 0, f"Expected exit 0, got {res.returncode}. Output:\n{res.stdout}\n{res.stderr}"

        with open(json_out, "r") as f:
            report = json.load(f)

        stats = report["stats"]
        assert stats["killed"] == 5, f"Expected 5 killed, got {stats['killed']}"
        assert stats["survived"] == 0, f"Expected 0 survived, got {stats['survived']}"
        assert stats["invalid"] == 1, f"Expected 1 invalid, got {stats['invalid']}"
        assert stats["execution_errors"] == 0, f"Expected 0 errors, got {stats['execution_errors']}"
        assert stats["total_expressions"] == 6, f"Expected 6 expressions, got {stats['total_expressions']}"


def test_weak_suite():
    """
    Weak suite:
    - Tests only subset of conditions
    - Survivors reported
    - Exits 1
    """
    policy_code = """package weak
import rego.v1

default allow := false

allow if {
    input.role == "admin"
}

allow if {
    input.role == "auditor"
}
"""
    test_code = """package weak
import rego.v1

test_allow if {
    allow with input as {"role": "admin"}
}
"""
    with tempfile.TemporaryDirectory() as td:
        policy_file = os.path.join(td, "policy.rego")
        test_file = os.path.join(td, "policy_test.rego")
        json_out = os.path.join(td, "report.json")

        with open(policy_file, "w") as f:
            f.write(policy_code)
        with open(test_file, "w") as f:
            f.write(test_code)

        res = subprocess.run(
            [sys.executable, ENGINE_PATH, policy_file, "--json-out", json_out],
            capture_output=True,
            text=True,
        )

        assert res.returncode == 1, f"Expected exit 1, got {res.returncode}"

        with open(json_out, "r") as f:
            report = json.load(f)

        stats = report["stats"]
        assert stats["survived"] >= 1, f"Expected at least 1 survivor, got {stats['survived']}"
        assert stats["killed"] >= 1, f"Expected at least 1 killed, got {stats['killed']}"


def test_conflicting_function():
    """
    Conflicting function:
    - 1 EXECUTION_ERROR (eval_conflict_error) and 1 KILLED
    - Error is NOT counted as a kill
    - Exits 2
    """
    policy_code = """package conflict
import rego.v1

f(x) := "a" if x == 1
f(x) := "b" if x == 2
"""
    test_code = """package conflict
import rego.v1

test_f if {
    f(1) == "a"
}
"""
    with tempfile.TemporaryDirectory() as td:
        policy_file = os.path.join(td, "policy.rego")
        test_file = os.path.join(td, "policy_test.rego")
        json_out = os.path.join(td, "report.json")

        with open(policy_file, "w") as f:
            f.write(policy_code)
        with open(test_file, "w") as f:
            f.write(test_code)

        res = subprocess.run(
            [sys.executable, ENGINE_PATH, policy_file, "--json-out", json_out],
            capture_output=True,
            text=True,
        )

        assert res.returncode == 2, f"Expected exit 2 for execution errors, got {res.returncode}"

        with open(json_out, "r") as f:
            report = json.load(f)

        stats = report["stats"]
        assert stats["execution_errors"] == 1, f"Expected 1 execution error, got {stats['execution_errors']}"
        assert stats["killed"] == 1, f"Expected 1 killed, got {stats['killed']}"
        assert report["status"] == "FAULT"


def test_no_mutable_expressions():
    """
    No mutable expressions found:
    - Policy has only constants and default rules
    - Exits 2
    """
    policy_code = """package empty
import rego.v1

default allow := false
const_val := 42
"""
    with tempfile.TemporaryDirectory() as td:
        policy_file = os.path.join(td, "policy.rego")
        json_out = os.path.join(td, "report.json")

        with open(policy_file, "w") as f:
            f.write(policy_code)

        res = subprocess.run(
            [sys.executable, ENGINE_PATH, policy_file, "--json-out", json_out],
            capture_output=True,
            text=True,
        )

        assert res.returncode == 2, f"Expected exit 2 for zero expressions, got {res.returncode}"
        with open(json_out, "r") as f:
            report = json.load(f)
        assert report["status"] == "FAULT"


def test_failing_baseline():
    """
    Failing baseline:
    - Existing test suite fails before mutation
    - Exits 2
    """
    policy_code = """package failing
import rego.v1

allow if 1 == 2
"""
    test_code = """package failing
import rego.v1

test_allow if allow
"""
    with tempfile.TemporaryDirectory() as td:
        policy_file = os.path.join(td, "policy.rego")
        test_file = os.path.join(td, "policy_test.rego")
        json_out = os.path.join(td, "report.json")

        with open(policy_file, "w") as f:
            f.write(policy_code)
        with open(test_file, "w") as f:
            f.write(test_code)

        res = subprocess.run(
            [sys.executable, ENGINE_PATH, policy_file, "--json-out", json_out],
            capture_output=True,
            text=True,
        )

        assert res.returncode == 2, f"Expected exit 2 for failing baseline, got {res.returncode}"
        with open(json_out, "r") as f:
            report = json.load(f)
        assert report["status"] == "FAULT"


def test_missing_policy_file():
    """
    Missing policy file:
    - File does not exist
    - Exits 2
    """
    with tempfile.TemporaryDirectory() as td:
        missing_file = os.path.join(td, "missing_policy.rego")
        json_out = os.path.join(td, "report.json")

        res = subprocess.run(
            [sys.executable, ENGINE_PATH, missing_file, "--json-out", json_out],
            capture_output=True,
            text=True,
        )

        assert res.returncode == 2, f"Expected exit 2 for missing policy file, got {res.returncode}"
        with open(json_out, "r") as f:
            report = json.load(f)
        assert report["status"] == "FAULT"


def test_external_test_dir_used_for_baseline_and_mutants():
    """
    Tests in a separate directory passed as test_path:
    - Baseline and every mutant load the policy together with that test directory
    - Both mutants are killed, exits 0
    """
    policy_code = """package ext
import rego.v1

default allow := false

allow if {
    input.role == "admin"
    input.active == true
}
"""
    test_code = """package ext
import rego.v1

test_admin_active if {
    allow with input as {"role": "admin", "active": true}
}

test_admin_inactive if {
    not allow with input as {"role": "admin", "active": false}
}

test_guest_active if {
    not allow with input as {"role": "guest", "active": true}
}
"""
    with tempfile.TemporaryDirectory() as td:
        policy_dir = os.path.join(td, "policies")
        test_dir = os.path.join(td, "tests")
        os.makedirs(policy_dir)
        os.makedirs(test_dir)
        policy_file = os.path.join(policy_dir, "policy.rego")
        json_out = os.path.join(td, "report.json")

        with open(policy_file, "w") as f:
            f.write(policy_code)
        with open(os.path.join(test_dir, "policy_test.rego"), "w") as f:
            f.write(test_code)

        res = subprocess.run(
            [sys.executable, ENGINE_PATH, policy_file, test_dir, "--json-out", json_out],
            capture_output=True,
            text=True,
        )

        assert res.returncode == 0, f"Expected exit 0, got {res.returncode}. Output:\n{res.stdout}\n{res.stderr}"
        with open(json_out, "r") as f:
            report = json.load(f)
        assert report["stats"]["killed"] == 2
        assert report["stats"]["survived"] == 0


def test_missing_test_path():
    """
    test_path that does not exist:
    - Not silently ignored
    - Exits 2
    """
    with tempfile.TemporaryDirectory() as td:
        policy_file = os.path.join(td, "policy.rego")
        json_out = os.path.join(td, "report.json")
        with open(policy_file, "w") as f:
            f.write("package p\nimport rego.v1\n\nallow if input.x == 1\n")

        res = subprocess.run(
            [sys.executable, ENGINE_PATH, policy_file, os.path.join(td, "nope"), "--json-out", json_out],
            capture_output=True,
            text=True,
        )

        assert res.returncode == 2, f"Expected exit 2 for missing test path, got {res.returncode}"
        with open(json_out, "r") as f:
            report = json.load(f)
        assert report["status"] == "FAULT"


def test_copy_of_real_sentinel_bootgate():
    """
    Copy of real sentinel/policies:
    - bootgate gets mutants actually executed (24/24 killed)
    - Source directory hashes are completely unchanged
    - Exits 0
    """
    src_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "sentinel", "policies")
    )
    assert os.path.isdir(src_dir), f"Source sentinel policies directory missing at {src_dir}"

    with tempfile.TemporaryDirectory() as td:
        copied_dir = os.path.join(td, "policies")
        shutil.copytree(src_dir, copied_dir)

        initial_hashes = hash_directory(copied_dir)
        bootgate_policy = os.path.join(copied_dir, "bootgate.rego")
        json_out = os.path.join(td, "report.json")

        res = subprocess.run(
            [sys.executable, ENGINE_PATH, bootgate_policy, "--json-out", json_out],
            capture_output=True,
            text=True,
        )

        assert res.returncode == 0, f"Expected exit 0 on bootgate.rego, got {res.returncode}. Output:\n{res.stdout}\n{res.stderr}"

        with open(json_out, "r") as f:
            report = json.load(f)

        stats = report["stats"]
        assert stats["killed"] == 24, f"Expected 24 killed on bootgate, got {stats['killed']}"
        assert stats["survived"] == 0, f"Expected 0 survived on bootgate, got {stats['survived']}"
        assert stats["invalid"] == 0, f"Expected 0 invalid on bootgate, got {stats['invalid']}"

        after_hashes = hash_directory(copied_dir)
        assert initial_hashes == after_hashes, "Directory contents were modified during mutation testing!"
