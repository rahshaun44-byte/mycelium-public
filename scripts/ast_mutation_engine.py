#!/usr/bin/env python3
"""
QuantumFlex AST-Aware Source Span Mutation Engine.
Parses Rego policies via `opa parse --format=json --json-include locations`,
locates real expressions while skipping default rules and synthetic bodies,
verifies source spans, isolates mutations in temporary sandboxes,
and classifies results (KILLED, SURVIVED, INVALID, EXECUTION_ERROR).
"""

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional, Tuple


def find_opa_binary() -> Optional[str]:
    """Finds opa binary in PATH or standard locations."""
    path = shutil.which("opa")
    if path and os.path.isfile(path) and os.access(path, os.X_OK):
        return path
    for fallback in ["/usr/local/bin/opa", "/usr/bin/opa", os.path.expanduser("~/.local/bin/opa")]:
        if os.path.isfile(fallback) and os.access(fallback, os.X_OK):
            return fallback
    return None


def extract_expressions_from_ast(ast: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Recursively extracts mutable expressions from OPA AST.
    Skips:
      - default rules
      - synthetic true bodies attached to constant rules, defaults, or else values
    """
    expressions = []

    def walk(node: Any, in_default: bool = False) -> None:
        if isinstance(node, dict):
            is_def = in_default or (node.get("default") is True)
            if "index" in node and "terms" in node and "location" in node:
                terms = node.get("terms")
                is_synthetic_true = (
                    isinstance(terms, dict)
                    and terms.get("type") == "boolean"
                    and terms.get("value") is True
                )
                if not is_def and not is_synthetic_true:
                    expressions.append(node)

            for k, v in node.items():
                if k == "rules":
                    for r in v:
                        walk(r, in_default=(r.get("default") is True))
                elif k != "rules":
                    walk(v, in_default=is_def)
        elif isinstance(node, list):
            for item in node:
                walk(item, in_default=in_default)

    walk(ast)
    return expressions


def write_json_report(path: Optional[str], report: Dict[str, Any]) -> None:
    """Safely writes report to json_out path if specified."""
    if not path:
        return
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    except Exception as e:
        print(f"Warning: Failed to write JSON report to {path}: {e}", file=sys.stderr)


def run_mutation_engine(policy_path: str, test_target: Optional[str] = None, json_out: Optional[str] = None) -> int:
    report: Dict[str, Any] = {
        "policy": policy_path,
        "status": "FAULT",
        "exit_code": 2,
        "fault_reason": None,
        "stats": {
            "total_expressions": 0,
            "killed": 0,
            "survived": 0,
            "invalid": 0,
            "execution_errors": 0,
            "score": None,
        },
        "mutants": [],
    }

    try:
        opa_bin = find_opa_binary()
        if not opa_bin:
            report["fault_reason"] = "opa binary not found in PATH"
            print("EXECUTION_FAULT: opa binary not found in PATH.", file=sys.stderr)
            write_json_report(json_out, report)
            return 2

        if not os.path.isfile(policy_path):
            report["fault_reason"] = f"Policy file not found: {policy_path}"
            print(f"EXECUTION_FAULT: Policy file not found: {policy_path}", file=sys.stderr)
            write_json_report(json_out, report)
            return 2

        abs_policy = os.path.abspath(policy_path)
        policy_dir = os.path.dirname(abs_policy)
        policy_name = os.path.basename(abs_policy)

        # 1. Parse AST with locations
        parse_proc = subprocess.run(
            [opa_bin, "parse", "--format=json", "--json-include", "locations", abs_policy],
            capture_output=True,
            text=True,
        )
        if parse_proc.returncode != 0:
            report["fault_reason"] = f"OPA parse failed: {parse_proc.stderr.strip()}"
            print(f"EXECUTION_FAULT: OPA parse failed for {policy_path}: {parse_proc.stderr.strip()}", file=sys.stderr)
            write_json_report(json_out, report)
            return 2

        try:
            ast = json.loads(parse_proc.stdout)
        except Exception as e:
            report["fault_reason"] = f"Failed to decode OPA AST JSON: {e}"
            print(f"EXECUTION_FAULT: Failed to decode OPA AST JSON: {e}", file=sys.stderr)
            write_json_report(json_out, report)
            return 2

        # 2. Extract mutable expressions
        expressions = extract_expressions_from_ast(ast)
        report["stats"]["total_expressions"] = len(expressions)

        if not expressions:
            report["fault_reason"] = "No mutable expressions found in policy"
            print(f"EXECUTION_FAULT: No mutable expressions found in {policy_path}.", file=sys.stderr)
            write_json_report(json_out, report)
            return 2

        # 3. Read source bytes for exact span matching
        with open(abs_policy, "rb") as f:
            source_bytes = f.read()
        lines = source_bytes.splitlines(keepends=True)

        # 4. Check unmutated baseline test
        # The policy directory is always loaded; an external test target is
        # loaded alongside it, for the baseline and for every mutant alike.
        extra_test_paths: List[str] = []
        if test_target:
            abs_target = os.path.abspath(test_target)
            if not os.path.exists(abs_target):
                report["fault_reason"] = f"Test path not found: {test_target}"
                print(f"EXECUTION_FAULT: Test path not found: {test_target}", file=sys.stderr)
                write_json_report(json_out, report)
                return 2
            if os.path.commonpath([abs_target, policy_dir]) != policy_dir:
                extra_test_paths.append(abs_target)

        baseline_proc = subprocess.run(
            [opa_bin, "test", "--format=json", policy_dir, *extra_test_paths],
            capture_output=True,
            text=True,
        )
        try:
            baseline_results = json.loads(baseline_proc.stdout) if baseline_proc.stdout.strip() else []
        except Exception:
            baseline_results = []

        baseline_failed = (
            baseline_proc.returncode != 0
            or any(t.get("fail") is True for t in baseline_results)
            or any("error" in t for t in baseline_results)
            or len(baseline_results) == 0
        )
        if baseline_failed:
            detail = (baseline_proc.stderr or baseline_proc.stdout).strip()
            report["fault_reason"] = f"Baseline tests failed or errored on {policy_dir}: {detail}"
            print(f"EXECUTION_FAULT: Baseline tests failed on {policy_dir}: {detail}", file=sys.stderr)
            write_json_report(json_out, report)
            return 2

        # 5. Evaluate each mutant in an isolated temporary sandbox
        killed = 0
        survived = 0
        invalid = 0
        execution_errors = 0

        for idx, expr in enumerate(expressions):
            loc = expr.get("location", {})
            row = loc.get("row")
            col = loc.get("col")
            encoded_text = loc.get("text")

            if not row or not col or not encoded_text:
                report["fault_reason"] = f"Missing location metadata for expression at index {idx}"
                print(f"EXECUTION_FAULT: Expression {idx} missing location.", file=sys.stderr)
                write_json_report(json_out, report)
                return 2

            expected_bytes = base64.b64decode(encoded_text)
            if row > len(lines):
                report["fault_reason"] = f"Span row {row} out of bounds (file has {len(lines)} lines)"
                print(f"EXECUTION_FAULT: Span desync at row {row}.", file=sys.stderr)
                write_json_report(json_out, report)
                return 2

            line_start_offset = sum(len(lines[i]) for i in range(row - 1))
            offset = line_start_offset + (col - 1)
            got_bytes = source_bytes[offset : offset + len(expected_bytes)]

            if got_bytes != expected_bytes:
                report["fault_reason"] = (
                    f"Span desync at row {row}, col {col}: "
                    f"expected {expected_bytes!r}, got {got_bytes!r}"
                )
                print(f"EXECUTION_FAULT: Span desync at row {row}, col {col}.", file=sys.stderr)
                write_json_report(json_out, report)
                return 2

            original_text = expected_bytes.decode("utf-8", errors="replace")

            # Mutation: plain expression is negated; expression starting with 'not' has it removed
            if original_text.startswith("not "):
                mutated_text = original_text[4:]
            elif original_text.startswith("not\t"):
                mutated_text = original_text[4:]
            else:
                mutated_text = f"not {original_text}"

            mutated_bytes = (
                source_bytes[:offset]
                + mutated_text.encode("utf-8")
                + source_bytes[offset + len(expected_bytes) :]
            )

            mutant_entry: Dict[str, Any] = {
                "index": idx,
                "location": {"row": row, "col": col, "file": loc.get("file", policy_name)},
                "original": original_text,
                "mutated": mutated_text,
                "outcome": "UNKNOWN",
            }

            with tempfile.TemporaryDirectory() as sandbox_dir:
                # Copy entire policy directory into sandbox to prevent modifying source tree
                # and avoid OPA loading output files as data
                for item in os.listdir(policy_dir):
                    src_item = os.path.join(policy_dir, item)
                    dst_item = os.path.join(sandbox_dir, item)
                    if os.path.isfile(src_item):
                        shutil.copy2(src_item, dst_item)
                    elif os.path.isdir(src_item):
                        shutil.copytree(src_item, dst_item)

                # Overwrite policy with mutant
                sandboxed_policy = os.path.join(sandbox_dir, policy_name)
                with open(sandboxed_policy, "wb") as f_mut:
                    f_mut.write(mutated_bytes)

                # Step A: Validate syntax with opa check
                check_proc = subprocess.run(
                    [opa_bin, "check", sandboxed_policy],
                    capture_output=True,
                    text=True,
                )
                if check_proc.returncode != 0:
                    mutant_entry["outcome"] = "INVALID"
                    mutant_entry["details"] = check_proc.stderr.strip()
                    invalid += 1
                    report["mutants"].append(mutant_entry)
                    continue

                # Step B: Run test suite with opa test --format=json
                test_proc = subprocess.run(
                    [opa_bin, "test", "--format=json", sandbox_dir, *extra_test_paths],
                    capture_output=True,
                    text=True,
                )

                try:
                    test_results = json.loads(test_proc.stdout) if test_proc.stdout.strip() else []
                except Exception:
                    test_results = []

                has_failed_assertion = any(t.get("fail") is True for t in test_results)
                has_error = any("error" in t for t in test_results) or (test_proc.returncode != 0 and not test_results)

                if has_failed_assertion:
                    mutant_entry["outcome"] = "KILLED"
                    killed += 1
                elif has_error:
                    mutant_entry["outcome"] = "EXECUTION_ERROR"
                    execution_errors += 1
                else:
                    mutant_entry["outcome"] = "SURVIVED"
                    survived += 1

                report["mutants"].append(mutant_entry)

        report["stats"]["killed"] = killed
        report["stats"]["survived"] = survived
        report["stats"]["invalid"] = invalid
        report["stats"]["execution_errors"] = execution_errors

        executed_count = killed + survived + execution_errors
        if executed_count > 0:
            report["stats"]["score"] = round((killed / executed_count) * 100.0, 2)

        # Determine overall verdict and exit code
        if execution_errors > 0:
            report["status"] = "FAULT"
            report["exit_code"] = 2
            report["fault_reason"] = f"{execution_errors} mutant(s) produced execution errors."
            print(f"EXECUTION_FAULT: {execution_errors} mutant(s) caused execution errors.", file=sys.stderr)
            write_json_report(json_out, report)
            return 2

        if executed_count == 0:
            report["status"] = "FAULT"
            report["exit_code"] = 2
            report["fault_reason"] = "Zero valid mutants could be executed."
            print("EXECUTION_FAULT: Zero valid mutants executed.", file=sys.stderr)
            write_json_report(json_out, report)
            return 2

        if survived > 0:
            report["status"] = "SURVIVED"
            report["exit_code"] = 1
            print(f"MUTATION_FAIL: {survived} mutant(s) survived ({killed}/{executed_count} killed).")
            write_json_report(json_out, report)
            return 1

        report["status"] = "PASSED"
        report["exit_code"] = 0
        print(f"MUTATION_PASS: 100% mutants killed ({killed}/{executed_count} killed, {invalid} invalid).")
        write_json_report(json_out, report)
        return 0

    except Exception as exc:
        report["status"] = "FAULT"
        report["exit_code"] = 2
        report["fault_reason"] = f"Unexpected exception: {exc}"
        print(f"EXECUTION_FAULT: Unexpected exception in mutation engine: {exc}", file=sys.stderr)
        write_json_report(json_out, report)
        return 2


def main() -> None:
    parser = argparse.ArgumentParser(description="QuantumFlex AST-Aware Source Span Mutation Engine.")
    parser.add_argument("policy_path", help="Path to policy.rego under test")
    parser.add_argument("test_path", nargs="?", default=None, help="Optional path to test file or directory")
    parser.add_argument("--json-out", dest="json_out", default=None, help="Path to write JSON execution report")

    args = parser.parse_args()
    code = run_mutation_engine(args.policy_path, args.test_path, args.json_out)
    sys.exit(code)


if __name__ == "__main__":
    main()
