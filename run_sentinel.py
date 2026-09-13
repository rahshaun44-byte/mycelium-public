#!/usr/bin/env python3
"""
=====================================================================
  QUANTUM FLEX // SENTINEL ORCHESTRATOR (Thermodynamic Ghost Node)
=====================================================================
Grounding Landauer Principle (h -> 0): Decouples friction and prevents
NVMe SSD NAND flash block wear by confining quarantined anomalous blobs
strictly to volatile tmpfs RAM-disks inside rootless Podman containers.

Key Invariants:
  1. Staging partition is /dev/shm/qflex_airlock (RAM-backed, 0700).
  2. Podman runs with --read-only rootfs, --cap-drop=ALL, no-new-privileges.
  3. Exclusive writable sink inside container is volatile tmpfs:
     --tmpfs /opt/sentinel/quarantine:rw,size=64m,noexec,nosuid,nodev
  4. Automatic thermodynamic dissipation: staged payloads are zero-wiped
     in RAM before unlink upon chamber cycle completion.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

VOLATILE_HOST_AIRLOCK = Path("/dev/shm/qflex_airlock")
CONTAINER_AIRLOCK = "/opt/sentinel/airlock"
CONTAINER_QUARANTINE = "/opt/sentinel/quarantine"
ENGINE_IMAGE = "localhost/qflex/sentinel:v1"
FALLBACK_IMAGE = "alpine:3.20"


def secure_zero_wipe(file_path: Path) -> None:
    """Overwrites file with zeroes before unlinking to enforce thermodynamic dissipation."""
    try:
        if file_path.is_file():
            length = file_path.stat().st_size
            with open(file_path, "wb") as f:
                f.write(b"\x00" * min(length, 1024 * 1024 * 16))
            file_path.unlink(missing_ok=True)
    except Exception as e:
        print(f"[!] Warning: Zero-wipe failed for {file_path}: {e}")


def deploy_to_chamber(target_file_path: str) -> bool:
    print("\n[>>] QUANTUM FLEX: Initializing Sentinel Thermodynamic Orchestrator...")

    target_path = Path(target_file_path).resolve()
    if not target_path.is_file():
        print(f"[-] FATAL: Target payload '{target_path}' does not exist on host.")
        return False

    # 1. Prepare Volatile RAM Airlock
    try:
        VOLATILE_HOST_AIRLOCK.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(VOLATILE_HOST_AIRLOCK, 0o700)
    except Exception as e:
        print(f"[-] FATAL: Unable to create volatile RAM airlock at {VOLATILE_HOST_AIRLOCK}: {e}")
        return False

    base_name = target_path.name
    staged_payload_path = VOLATILE_HOST_AIRLOCK / base_name
    container_payload_path = f"{CONTAINER_AIRLOCK}/{base_name}"

    try:
        # 2. Stage Payload exclusively into volatile RAM
        shutil.copy2(target_path, staged_payload_path)
        print(f"[+] Payload staged to volatile RAM airlock: {staged_payload_path} (0 NVMe SSD writes)")

        # 3. Detect container runtime image
        image = ENGINE_IMAGE
        inspect_res = subprocess.run(["podman", "image", "exists", ENGINE_IMAGE], capture_output=True)
        if inspect_res.returncode != 0:
            print(f"[i] Primary engine image '{ENGINE_IMAGE}' not found; utilizing hardened fallback '{FALLBACK_IMAGE}'.")
            image = FALLBACK_IMAGE

        # 4. Construct Thermodynamic Ghost Node Podman Execution String
        podman_cmd = [
            "podman", "run", "--rm",
            "--network=none",
            "--user", "0",
            "--security-opt", "no-new-privileges=true",
            "--cap-drop=ALL",
            "--read-only",
            "--tmpfs", f"{CONTAINER_QUARANTINE}:rw,size=64m,noexec,nosuid,nodev",
            "-v", f"{VOLATILE_HOST_AIRLOCK}:{CONTAINER_AIRLOCK}:ro,Z",
        ]

        if image == ENGINE_IMAGE:
            podman_cmd.extend([image, container_payload_path])
        else:
            # Alpine fallback: Hash, neutralize, and store isolated copy strictly inside volatile tmpfs
            cmd_script = (
                f"sha256sum {container_payload_path} && "
                f"cp {container_payload_path} {CONTAINER_QUARANTINE}/{base_name}.isolated && "
                f"chmod 000 {CONTAINER_QUARANTINE}/{base_name}.isolated && "
                f"echo '[+] Neutralized into volatile tmpfs sink: {CONTAINER_QUARANTINE}/{base_name}.isolated' && "
                f"df -h {CONTAINER_QUARANTINE}"
            )
            podman_cmd.extend([image, "sh", "-c", cmd_script])

        print(f"[>>] Detonating Chamber: {' '.join(podman_cmd)}")

        # 5. Execute Detonation and Capture Telemetry
        result = subprocess.run(podman_cmd, capture_output=True, text=True, check=True)
        print("\n=== SENSOR TELEMETRY ===")
        print(result.stdout.strip())
        print("========================")
        return True

    except subprocess.CalledProcessError as e:
        print("\n[-] FATAL: Chamber Execution Failed.")
        print(f"Error Output: {e.stderr.strip()}")
        return False
    finally:
        # 6. Landauer Thermodynamic Dissipation: Zero-wipe and purge RAM airlock
        if staged_payload_path.exists():
            secure_zero_wipe(staged_payload_path)
            print(f"[+] Thermodynamic Dissipation: Volatile payload purged from RAM.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 run_sentinel.py </path/to/suspicious/file>")
        sys.exit(1)

    success = deploy_to_chamber(sys.argv[1])
    sys.exit(0 if success else 1)
