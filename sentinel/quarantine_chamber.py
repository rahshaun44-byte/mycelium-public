import os
import hashlib
import shutil
import stat
import sys

def neutralize_payload(file_path, dest_dir=None):
    if dest_dir is None:
        dest_dir = os.environ.get("CONTAINER_QUARANTINE")
        if not dest_dir:
            dest_dir = "/opt/sentinel/quarantine" if os.path.exists("/opt/sentinel/quarantine") else "/quarantine"
    """
    Physical intervention: Strips execution rights, extracts the cryptographic hash, 
    and writes the isolated copy strictly into the writable quarantine tmpfs.
    """
    try:
        os.makedirs(dest_dir, exist_ok=True)
        # 1. Extract Cryptographic Identity (SHA-256)
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        file_hash = sha256_hash.hexdigest()

        base_name = os.path.basename(file_path)
        isolated_path = os.path.join(dest_dir, f"{base_name}.isolated")
        
        # 2. Copy into writable quarantine tmpfs sink
        shutil.copy2(file_path, isolated_path)

        # 3. Modify Permissions to Absolute Zero (chmod 000)
        os.chmod(isolated_path, 0o000)
        
        return {
            "status": "NEUTRALIZED",
            "original_name": base_name,
            "isolated_name": f"{base_name}.isolated",
            "sha256_hash": file_hash,
            "vault_path": isolated_path
        }
    except Exception as e:
        return {"status": "FAILED", "error": str(e)}

if __name__ == "__main__":
    print("\n[+] QUANTUM FLEX: Sentinel Pipeline Armed")
    
    # Enforce argument check
    if len(sys.argv) < 2:
        print("[-] ERROR: No target payload specified to the engine.")
        print("Usage: podman run <image> <target_file_inside_container>")
        sys.exit(1)
        
    target_payload = sys.argv[1]
    
    if os.path.exists(target_payload):
        result = neutralize_payload(target_payload)
        print(f"[+] NEUTRALIZATION REPORT:\n{result}\n")
        if result.get("status") != "NEUTRALIZED":
            sys.exit(1)
    else:
        print(f"[-] ERROR: Target file '{target_payload}' not found in chamber.\n")
        sys.exit(1)
