#!/usr/bin/env python3
"""
QuantumFlex AST-Aware Source Span Mutation Engine.
Locates target nodes via `opa parse --format=json`, verifies exact spans via base64 `location.text`,
injects semantic negations (`not (...)`), and measures KILLED vs SURVIVED accurately.
"""

import sys
import subprocess
import json
import base64
import os

def check_opa_installed():
    try:
        subprocess.run(["opa", "version"], check=True, capture_output=True)
    except FileNotFoundError:
        print("EXECUTION_ERROR: opa binary not found in PATH.", file=sys.stderr)
        sys.exit(1)

def get_ast(policy_path):
    result = subprocess.run(["opa", "parse", "--format=json", policy_path], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"EXECUTION_ERROR: OPA failed to parse {policy_path}.", file=sys.stderr)
        sys.exit(1)
    return json.loads(result.stdout)

def extract_expressions(ast_node, matches):
    if isinstance(ast_node, dict):
        if ast_node.get("type") == "expr" and "location" in ast_node:
            matches.append(ast_node)
        for val in ast_node.values():
            extract_expressions(val, matches)
    elif isinstance(ast_node, list):
        for item in ast_node:
            extract_expressions(item, matches)

def mutate_and_test(policy_path, original_content, target_node):
    location = target_node.get("location", {})
    if "text" not in location or "col" not in location:
        return "INVALID"

    # Verify exact base64 span matches source code
    expected_text = base64.b64decode(location["text"]).decode("utf-8")
    
    col = location["col"]
    row = location["row"]
    
    lines = original_content.splitlines()
    if row > len(lines):
        return "INVALID"
        
    line = lines[row - 1]
    # Check if the text matches starting at the column (1-indexed)
    got = line[col - 1 : col - 1 + len(expected_text)]
    if got != expected_text:
        print(f"EXECUTION_ERROR: Span desync at row {row}, col {col}. Expected '{expected_text}', got '{got}'.", file=sys.stderr)
        return "EXECUTION_ERROR"

    # Semantic mutation: negate the entire expression span safely
    mutated_line = line[:col - 1] + f"not ({expected_text})" + line[col - 1 + len(expected_text):]
    mutated_content = "\n".join(lines[:row - 1] + [mutated_line] + lines[row:])

    mutant_path = policy_path + ".mutant"
    with open(mutant_path, "w") as f:
        f.write(mutated_content)

    # Check if the mutant is actually valid rego syntax first
    check_res = subprocess.run(["opa", "check", mutant_path], capture_output=True)
    if check_res.returncode != 0:
        os.remove(mutant_path)
        return "INVALID"

    # Run tests to see if the mutation is detected
    test_res = subprocess.run(["opa", "test", mutant_path, policy_path.replace(".rego", "_test.rego")], capture_output=True)
    os.remove(mutant_path)
    
    # If tests fail, the mutation was caught (KILLED). If they pass, the mutation survived (SURVIVED).
    if test_res.returncode != 0:
        return "KILLED"
    return "SURVIVED"

def main():
    if len(sys.argv) < 2:
        print("Usage: ast_mutation_engine.py <policy.rego>")
        sys.exit(1)

    policy_path = sys.argv[1]
    check_opa_installed()

    with open(policy_path, "r", encoding="utf-8") as f:
        original_content = f.read()

    ast = get_ast(policy_path)
    expressions = []
    extract_expressions(ast, expressions)

    if not expressions:
        print("No expressions found to mutate.")
        sys.exit(0)

    stats = {"KILLED": 0, "SURVIVED": 0, "INVALID": 0, "EXECUTION_ERROR": 0}
    
    for expr in expressions:
        result = mutate_and_test(policy_path, original_content, expr)
        stats[result] += 1
        
    print(f"Mutation testing complete: {stats}")
    if stats["SURVIVED"] > 0 or stats["EXECUTION_ERROR"] > 0:
        print("HARD STOP: Mutations survived or execution failed. Tests do not provide sufficient coverage.")
        sys.exit(1)
    
    print("SUCCESS: 100% Mutation Coverage.")

if __name__ == "__main__":
    main()
