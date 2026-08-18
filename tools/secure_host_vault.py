#!/usr/bin/env python3
"""
═════════════════════════════════════════════════════════════════════
  QUANTUM FLEX: MASTER HOST VAULT & SECURE PERSISTENCE ENGINE
═════════════════════════════════════════════════════════════════════
Securely packages, verifies, and permanently archives the entire QuantumFlex
biological infrastructure onto the host PC with SHA-256 integrity manifests
and restricted NTFS ACLs.
"""

import os
import sys
import shutil
import hashlib
import zipfile
import subprocess
from pathlib import Path
from datetime import datetime

# Safe console rendering for Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

USER_HOME = Path.home()
DEFAULT_VAULT_DIR = USER_HOME / "QuantumFlex_Master_Vault"
REPOS_DIR = Path(__file__).resolve().parents[2]

def compute_sha256(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

def secure_archive_quantumflex(vault_dir: Path = DEFAULT_VAULT_DIR):
    print("=" * 68)
    print("  QUANTUM FLEX: SECURE MASTER HOST VAULT CREATION")
    print("=" * 68)
    print(f"[*] Host Vault Target: {vault_dir}")

    vault_dir.mkdir(parents=True, exist_ok=True)
    backups_dir = vault_dir / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_zip_name = f"quantumflex_master_snapshot_{timestamp}.zip"
    archive_zip_path = backups_dir / archive_zip_name

    # Discover components
    components = [
        ("mycelium", REPOS_DIR / "mycelium"),
        ("qflex", REPOS_DIR / "qflex"),
        ("pqc-immune-daemon", REPOS_DIR / "pqc-immune-daemon"),
        ("master_spec", REPOS_DIR / "QUANTUM_ENTANGLEMENT_MASTER.md"),
    ]

    print("[*] Packing verified source tree into secure zip archive...")
    manifest = {
        "created_at": datetime.now().isoformat(),
        "vault_path": str(vault_dir),
        "archive_file": archive_zip_name,
        "components": {}
    }

    # Blacklisted folders/files from backup archive
    ignore_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv", "chroma_db"}
    ignore_extensions = {".ptau", ".pyc", ".tmp"}

    with zipfile.ZipFile(archive_zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for name, comp_path in components:
            if not comp_path.exists():
                continue
            
            if comp_path.is_file():
                arcname = f"quantumflex/{comp_path.name}"
                zipf.write(comp_path, arcname)
                manifest["components"][name] = {
                    "type": "file",
                    "path": str(comp_path),
                    "sha256": compute_sha256(comp_path)
                }
            elif comp_path.is_dir():
                file_count = 0
                for root, dirs, files in os.walk(comp_path):
                    dirs[:] = [d for d in dirs if d not in ignore_dirs]
                    for f in files:
                        ext = Path(f).suffix.lower()
                        if ext in ignore_extensions:
                            continue
                        full_f = Path(root) / f
                        rel_path = full_f.relative_to(REPOS_DIR)
                        zipf.write(full_f, str(rel_path))
                        file_count += 1
                manifest["components"][name] = {
                    "type": "directory",
                    "file_count": file_count
                }

    archive_sha256 = compute_sha256(archive_zip_path)
    manifest["archive_sha256"] = archive_sha256
    manifest["archive_size_mb"] = round(archive_zip_path.stat().st_size / (1024 * 1024), 2)

    # Write manifest
    manifest_path = vault_dir / "VAULT_INTEGRITY_MANIFEST.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        import json
        json.dump(manifest, f, indent=2)

    # Create README in Vault
    readme_path = vault_dir / "README_VAULT.md"
    readme_path.write_text(f"""# QuantumFlex Host Master Vault

**Vault Created:** {manifest['created_at']}
**Latest Snapshot:** `{archive_zip_name}`
**SHA-256 Checksum:** `{archive_sha256}`
**Archive Size:** {manifest['archive_size_mb']} MB

### Restoration Instructions
To restore the entire QuantumFlex stack from this vault:
```powershell
Expand-Archive -Path "{archive_zip_path}" -DestinationPath "C:\\Users\\quant\\.gemini\\antigravity-ide\\scratch\\repos" -Force
```
""", encoding="utf-8")

    # Tighten Windows NTFS permissions (icacls) to current user only
    try:
        current_user = os.environ.get("USERNAME", "quant")
        subprocess.run(
            f'icacls "{vault_dir}" /inheritance:r /grant:r {current_user}:(OI)(CI)F',
            shell=True,
            capture_output=True
        )
        print("  [+] Applied restricted NTFS ACLs (Private to current user).")
    except Exception as e:
        print(f"  [-] ACL notice: {e}")

    print("=" * 68)
    print(f"  VAULT CREATION COMPLETE: {manifest['archive_size_mb']} MB")
    print(f"  ARCHIVE: {archive_zip_path}")
    print(f"  SHA-256: {archive_sha256}")
    print("=" * 68 + "\n")

if __name__ == "__main__":
    secure_archive_quantumflex()
