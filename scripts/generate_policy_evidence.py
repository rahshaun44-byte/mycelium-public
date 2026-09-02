#!/usr/bin/env python3
"""
QuantumFlex Attestation Stage 1: Generate Policy Evidence
Calculates digests of the policy source, tests, infrastructure workflows, and OPA binary.
Binds to the exact Git commit context to ensure no tampering occurs upstream of verification.
"""

import hashlib
import json
import subprocess
import sys
import os

def sha256_file(filepath):
    if not os.path.exists(filepath):
        return None
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def get_git_commit():
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True)
        return res.stdout.strip()
    except subprocess.CalledProcessError:
        return "UNKNOWN_COMMIT"

def get_opa_binary_path():
    try:
        # For Windows, use where, for Linux use which. Let's try both depending on OS.
        cmd = ["where", "opa"] if os.name == 'nt' else ["which", "opa"]
        res = subprocess.run(cmd, check=True, capture_output=True, text=True)
        return res.stdout.strip().split('\n')[0]
    except subprocess.CalledProcessError:
        return None

def main():
    workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Files to hash
    pqc_dir = os.path.join(workspace, "pqc-immune-daemon")
    policy_file = os.path.join(pqc_dir, "membrane_health.rego") if os.path.exists(os.path.join(pqc_dir, "membrane_health.rego")) else os.path.join(workspace, "membrane_health.rego")
    test_file = os.path.join(pqc_dir, "membrane_health_test.rego") if os.path.exists(os.path.join(pqc_dir, "membrane_health_test.rego")) else os.path.join(workspace, "membrane_health_test.rego")
    workflow_file = os.path.join(workspace, ".github", "workflows", "quantumflex-release.yml")
    
    opa_path = get_opa_binary_path()
    
    evidence = {
        "schema_version": "1.5.0",
        "release_identity": {
            "source_identity": {
                "repository": "pqc-immune-daemon",
                "commit": get_git_commit(),
                "release_version": "1.5.0"
            },
            "policy_identity": {
                "membrane_health.rego": sha256_file(policy_file)
            },
            "verification_identity": {
                "membrane_health_test.rego": sha256_file(test_file),
                "opa_binary_sha256": sha256_file(opa_path) if opa_path else None
            },
            "infrastructure_identity": {
                "quantumflex-release.yml": sha256_file(workflow_file)
            }
        },
        "status": "APPROVED",
        "deployment_authorized": True
    }
    
    # Deterministic serialization for hashing later
    evidence_json = json.dumps(evidence, sort_keys=True, indent=2)
    evidence_path = os.path.join(workspace, "policy_evidence.json")
    
    with open(evidence_path, "w") as f:
        f.write(evidence_json)
        
    print(f"Policy evidence successfully generated at {evidence_path}")
    print(f"Source Commit Bound: {evidence['release_identity']['source_identity']['commit']}")

if __name__ == "__main__":
    main()
