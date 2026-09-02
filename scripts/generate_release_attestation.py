#!/usr/bin/env python3
"""
QuantumFlex Attestation Stage 2: Generate Release Attestation
Binds the completed policy evidence and artifact manifest to the final offline bundle.
The output of this script is what is ultimately signed by Minisign / Ed25519.
"""

import hashlib
import json
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

def main():
    if len(sys.argv) < 2:
        print("Usage: generate_release_attestation.py <bundle.tar.gz>")
        sys.exit(1)

    bundle_path = sys.argv[1]
    workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    evidence_path = os.path.join(workspace, "policy_evidence.json")
    manifest_path = os.path.join(workspace, "release", "MANIFEST.json")
    
    if not os.path.exists(evidence_path):
        print(f"HARD STOP: Evidence file missing at {evidence_path}")
        sys.exit(1)
        
    if not os.path.exists(manifest_path):
        print(f"HARD STOP: Manifest file missing at {manifest_path}")
        sys.exit(1)

    # Load previously verified evidence
    with open(evidence_path, "r") as f:
        evidence = json.load(f)
        
    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    # Hash the payload itself
    bundle_hash = sha256_file(bundle_path)
    if not bundle_hash:
        print(f"HARD STOP: Target bundle not found at {bundle_path}")
        sys.exit(1)

    # Create the final canonical release identity R
    release_attestation = {
        "schema_version": "1.5.0",
        "evidence": evidence,
        "manifest": manifest,
        "artifact_identity": {
            "filename": os.path.basename(bundle_path),
            "sha256": bundle_hash
        }
    }
    
    # Dump deterministically
    attestation_json = json.dumps(release_attestation, sort_keys=True, indent=2)
    attestation_path = os.path.join(workspace, "release_attestation.json")
    
    with open(attestation_path, "w") as f:
        f.write(attestation_json)
        
    print(f"Release Attestation successfully bound at {attestation_path}")
    print(f"Artifact Hash (A): {bundle_hash}")
    
    # Conceptually, Minisign runs next on this attestation_path.

if __name__ == "__main__":
    main()
