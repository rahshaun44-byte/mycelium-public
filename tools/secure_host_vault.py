#!/usr/bin/env python3
"""
═════════════════════════════════════════════════════════════════════
  QUANTUM FLEX: MASTER HOST VAULT & SECURE PERSISTENCE ENGINE
═════════════════════════════════════════════════════════════════════
Securely packages, verifies, and permanently archives the entire QuantumFlex
host infrastructure (code, secrets, Shamir shares, credentials, configs)
with SHA-256 integrity manifests and POSIX 0700/0600 permissions.
"""

import os
import sys
import shutil
import hashlib
import zipfile
import subprocess
from pathlib import Path
from datetime import datetime
import json

# Safe console rendering for Windows if applicable
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

USER_HOME = Path.home()
DEFAULT_VAULT_DIR = USER_HOME / "QuantumFlex_Master_Vault"

def compute_sha256(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

def secure_archive_quantumflex(vault_dir: Path = DEFAULT_VAULT_DIR):
    print("=" * 72)
    print("  QUANTUM FLEX: SECURE MASTER HOST VAULT CREATION (LINUX / POSIX)")
    print("=" * 72)
    print(f"[*] Host User Home:   {USER_HOME}")
    print(f"[*] Host Vault Target: {vault_dir}")

    vault_dir.mkdir(parents=True, exist_ok=True)
    backups_dir = vault_dir / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_zip_name = f"quantumflex_master_snapshot_{timestamp}.zip"
    archive_zip_path = backups_dir / archive_zip_name

    # Comprehensive components list covering code, authority, secrets, configs
    components = [
        # Repositories & Engine Source Trees
        ("mycelium", USER_HOME / "mycelium"),
        ("projects", USER_HOME / "projects"),
        ("quantumflex", USER_HOME / "quantumflex"),
        ("qf-public", USER_HOME / "qf-public"),
        ("qf-research", USER_HOME / "qf-research"),
        ("qf-security-private", USER_HOME / "qf-security-private"),
        
        # Authority Shares, Shards & Recovery
        ("qfx-authority-share1", USER_HOME / "qfx-authority-share1"),
        ("qfx-shards-genesis", USER_HOME / "qfx-shards-genesis"),
        ("qfx-recovery", USER_HOME / "qfx-recovery"),
        ("qfx-backup", USER_HOME / "qfx-backup"),
        ("qfx-tools", USER_HOME / "qfx-tools"),
        ("tools", USER_HOME / "tools"),
        
        # Secrets, Keys & Configurations
        ("ssh_credentials", USER_HOME / ".ssh"),
        ("gnupg_keys", USER_HOME / ".gnupg"),
        ("config_qf", USER_HOME / ".config" / "qf"),
        ("config_quantumflex", USER_HOME / ".config" / "quantumflex"),
        ("config_systemd_user", USER_HOME / ".config" / "systemd" / "user"),
        
        # Standalone Root Credentials & Environments
        ("recovery_file_dat", USER_HOME / "recovery_file.dat"),
        ("recovery_file_uuid_dat", USER_HOME / "recovery_file_22e403ac-29f5-437b-b90b-b0a3b10f2836.dat"),
        ("create_wallet_js", USER_HOME / "create-wallet.js"),
        ("home_env", USER_HOME / ".env"),
        ("bashrc", USER_HOME / ".bashrc"),
        ("gitconfig", USER_HOME / ".gitconfig"),
    ]

    print("[*] Packing verified infrastructure into secure zip archive...")
    manifest = {
        "created_at": datetime.now().isoformat(),
        "host": os.uname().nodename if hasattr(os, "uname") else "qfx-yoga",
        "vault_path": str(vault_dir),
        "archive_file": archive_zip_name,
        "components": {}
    }

    # Blacklisted folders/files from backup archive to avoid multi-GB build bloat
    ignore_dirs = {
        ".git", "__pycache__", "node_modules", ".venv", "venv", 
        "target", "chroma_db", "dist", ".cache", ".pytest_cache",
        "build", "build_check", "out", ".vscode", "playwright-locator-profile",
        "QuantumFlex_Master_Vault"
    }
    ignore_extensions = {
        ".ptau", ".pyc", ".tmp", ".deb", ".o", ".a", ".so", 
        ".rlib", ".rmeta", ".d"
    }

    total_files_archived = 0

    with zipfile.ZipFile(archive_zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for name, comp_path in components:
            if not comp_path.exists():
                continue
            
            if comp_path.is_file():
                rel_path = comp_path.relative_to(USER_HOME)
                zipf.write(comp_path, str(rel_path))
                total_files_archived += 1
                manifest["components"][name] = {
                    "type": "file",
                    "path": str(comp_path),
                    "archive_rel_path": str(rel_path),
                    "size_bytes": comp_path.stat().st_size,
                    "sha256": compute_sha256(comp_path)
                }
                print(f"  [+] Archived file: {rel_path}")
            elif comp_path.is_dir():
                file_count = 0
                for root, dirs, files in os.walk(comp_path):
                    dirs[:] = [d for d in dirs if d not in ignore_dirs]
                    for f in files:
                        ext = Path(f).suffix.lower()
                        if ext in ignore_extensions:
                            continue
                        full_f = Path(root) / f
                        if full_f.is_symlink() and not full_f.exists():
                            continue
                        try:
                            rel_path = full_f.relative_to(USER_HOME)
                            zipf.write(full_f, str(rel_path))
                            file_count += 1
                            total_files_archived += 1
                        except Exception as e:
                            print(f"  [-] Skip {full_f}: {e}")
                manifest["components"][name] = {
                    "type": "directory",
                    "path": str(comp_path),
                    "file_count": file_count
                }
                print(f"  [+] Archived dir:  {name} ({file_count} files)")

    archive_sha256 = compute_sha256(archive_zip_path)
    archive_size_bytes = archive_zip_path.stat().st_size
    manifest["archive_sha256"] = archive_sha256
    manifest["archive_size_mb"] = round(archive_size_bytes / (1024 * 1024), 2)
    manifest["total_files_archived"] = total_files_archived

    # Write manifest
    manifest_path = vault_dir / "VAULT_INTEGRITY_MANIFEST.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    # Create README in Vault
    readme_path = vault_dir / "README_VAULT.md"
    readme_path.write_text(f"""# QuantumFlex Host Master Vault

**Vault Created:** {manifest['created_at']}
**Host Node:** `{manifest['host']}`
**Latest Snapshot:** `{archive_zip_name}`
**SHA-256 Checksum:** `{archive_sha256}`
**Archive Size:** {manifest['archive_size_mb']} MB
**Total Files:** {manifest['total_files_archived']}

### Integrity Verification
```bash
sha256sum -c - <<< "{archive_sha256}  {archive_zip_path.name}"
```

### Restoration Instructions
To restore the entire QuantumFlex stack and credentials to this or a newly provisioned machine:
```bash
# 1. Unzip snapshot archive directly to home directory
unzip -o "{archive_zip_path}" -d "$HOME"

# 2. Re-establish fail-closed cryptographic permissions
chmod 0700 "$HOME/.ssh" "$HOME/projects/beta/secrets" "$HOME/qfx-authority-share1"
chmod 0600 "$HOME/.ssh/"* 2>/dev/null || true
chmod 0600 "$HOME/projects/beta/secrets/"* 2>/dev/null || true
chmod 0600 "$HOME/.config/qf/"* 2>/dev/null || true
chmod 0600 "$HOME/.config/quantumflex/"* 2>/dev/null || true
chmod 0600 "$HOME/qfx-authority-share1/"* 2>/dev/null || true
```
""", encoding="utf-8")

    # Enforce strict POSIX permissions (0700 dir, 0600 files)
    try:
        os.chmod(vault_dir, 0o700)
        os.chmod(backups_dir, 0o700)
        os.chmod(archive_zip_path, 0o600)
        os.chmod(manifest_path, 0o600)
        os.chmod(readme_path, 0o600)
        print("  [+] Enforced fail-closed POSIX permissions (0700 dir, 0600 files).")
    except Exception as e:
        print(f"  [-] POSIX permissions notice: {e}")

    # Fallback for Windows NTFS ACLs if running on Windows
    if sys.platform == "win32":
        try:
            current_user = os.environ.get("USERNAME", "quant")
            subprocess.run(
                f'icacls "{vault_dir}" /inheritance:r /grant:r {current_user}:(OI)(CI)F',
                shell=True,
                capture_output=True
            )
            print("  [+] Applied restricted NTFS ACLs.")
        except Exception as e:
            print(f"  [-] Windows ACL notice: {e}")

    print("=" * 72)
    print(f"  VAULT CREATION COMPLETE: {manifest['archive_size_mb']} MB ({manifest['total_files_archived']} files)")
    print(f"  ARCHIVE: {archive_zip_path}")
    print(f"  SHA-256: {archive_sha256}")
    print("=" * 72 + "\n")

    return archive_zip_path, archive_sha256

if __name__ == "__main__":
    secure_archive_quantumflex()

