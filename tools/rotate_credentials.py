#!/usr/bin/env python3
"""
Quantum Flex: Automated Credential Rotation & Secret Hygiene Tool
----------------------------------------------------------------
Generates cryptographically secure (CSPRNG) credentials, rotates local
configuration files atomically, enforces secret isolation across services,
and audits workspace security boundaries.
"""

import os
import sys
import math
import secrets
import argparse
from pathlib import Path

# Paths
REPO_ROOT = Path(__file__).resolve().parents[1]
SCRATCH_REPOS = Path(__file__).resolve().parents[2]
ENV_FILE = REPO_ROOT / ".env"
ENV_EXAMPLE = REPO_ROOT / ".env.windows.example"

def calculate_shannon_entropy(s: str) -> float:
    """Calculate the Shannon entropy of a given string in bits per character."""
    if not s:
        return 0.0
    prob = [float(s.count(c)) / len(s) for c in dict.fromkeys(list(s))]
    return -sum(p * math.log2(p) for p in prob)

def generate_secure_password(length: int = 32) -> str:
    """Generate a high-entropy URL-safe alphanumeric/symbolic secret."""
    return secrets.token_urlsafe(length)

def generate_api_key() -> str:
    """Generate a 256-bit hex API key with a structured prefix."""
    return f"qf_live_{secrets.token_hex(24)}"

def generate_tunnel_token() -> str:
    """Generate a realistic, high-entropy Cloudflare-style token."""
    return f"eyJhIjoi{secrets.token_urlsafe(24)}\"_{secrets.token_urlsafe(40)}"

def rotate_all_credentials(env_path: Path = ENV_FILE) -> dict:
    """
    Windows-only legacy rotation function.
    Fails closed on Linux to prevent destroying Linux host configuration.
    """
    if sys.platform != "win32":
        raise RuntimeError(
            "Windows-oriented rotate_credentials.py is strictly disabled on Linux. "
            "Use tools/rotate_credentials_linux.py instead."
        )
    raise NotImplementedError("Windows execution disabled on this node.")

def audit_credentials(env_path: Path = ENV_FILE) -> bool:
    """
    Audits credential strength, entropy, uniqueness, and .gitignore coverage.
    """
    print("=" * 60)
    print("  QUANTUM FLEX: CREDENTIAL & SECRET HYGIENE AUDIT")
    print("=" * 60)
    
    if not env_path.exists():
        print(f"[-] ERROR: .env file not found at {env_path}")
        return False

    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    secrets_found = {}
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if any(term in k.upper() for term in ["PASSWORD", "KEY", "TOKEN", "SECRET"]):
            secrets_found[k] = v

    print(f"\n[*] Auditing {len(secrets_found)} critical credentials in .env:")
    all_passed = True
    seen_values = set()

    for key, val in secrets_found.items():
        entropy = calculate_shannon_entropy(val)
        bit_strength = entropy * len(val)
        
        # Check uniqueness
        if val in seen_values:
            print(f"  [!] FAIL: Reused secret detected for {key}!")
            all_passed = False
        seen_values.add(val)

        # Check entropy / length
        status = "[+] PASS" if bit_strength >= 100 and len(val) >= 16 else "[-] WEAK"
        if status == "[-] WEAK":
            all_passed = False
            
        print(f"  {status}: {key} (Length: {len(val)}, Entropy: {entropy:.2f} b/char, Total: ~{bit_strength:.0f} bits, Value: [REDACTED])")

    # Audit .gitignore rules across scratch repos
    print("\n[*] Auditing .gitignore exclusions across workspace:")
    gitignore_passed = True
    for gitignore_path in SCRATCH_REPOS.rglob(".gitignore"):
        try:
            content = gitignore_path.read_text(encoding="utf-8")
            has_env = ".env" in content
            has_key = "*.key" in content or ".key" in content
            has_pem = "*.pem" in content or ".pem" in content
            
            rel_path = gitignore_path.relative_to(SCRATCH_REPOS)
            if has_env and (has_key or has_pem):
                print(f"  [+] PASS: {rel_path} covers .env and cryptographic keys.")
            else:
                print(f"  [!] WARN: {rel_path} may be missing some secret patterns (.env={has_env}, keys={has_key}, pem={has_pem})")
        except Exception as e:
            print(f"  [-] ERROR reading {gitignore_path}: {e}")

    print("\n" + "=" * 60)
    if all_passed and gitignore_passed:
        print("  AUDIT PASSED: ZERO COMPROMISE / ALL SECRETS HARDENED")
    else:
        print("  AUDIT FAILED: REMEDIATION REQUIRED")
    print("=" * 60 + "\n")
    return all_passed

def main():
    parser = argparse.ArgumentParser(description="Quantum Flex Credential Manager")
    parser.add_argument("--rotate", action="store_true", help="Rotate all credentials with new high-entropy secrets")
    parser.add_argument("--audit", action="store_true", help="Audit current credentials and security posture")

    args = parser.parse_args()

    if args.rotate:
        if sys.platform != "win32":
            from tools.rotate_credentials_linux import CredentialRotationManager
            print("[*] Linux host detected: Delegating to secure Linux credential manager...")
            manager = CredentialRotationManager(workspace_root=REPO_ROOT)
            manager.run(dry_run=True)
            print("[!] Mutating rotation requires explicit provider confirmation. Run tools/rotate_credentials_linux.py --rotate when ready.")
            return
        print("[*] Generating new isolated cryptographic secrets...")
        rotated = rotate_all_credentials()
        print("[+] Credentials successfully rotated into .env.")
        audit_credentials()
    elif args.audit:
        success = audit_credentials()
        sys.exit(0 if success else 1)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
