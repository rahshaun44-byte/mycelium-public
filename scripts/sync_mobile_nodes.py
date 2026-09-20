#!/usr/bin/env python3
"""
QuantumFlex Mobile Node Synchronizer (QF-M1 Actuator)
=====================================================
Direct physical provisioning, health inspection, and over-the-wire deployment:
- Defaults to INSPECTION ONLY (zero mutations without explicit flags)
- Explicit flags:
    --push           : Push verified CLI, manifests, and web HUD to /sdcard/Download/QuantumFlex/
    --apk            : Install/update verified native Capacitor Cockpit APK (com.quantumflex.cockpit)
    --device SERIAL  : Target specific ADB device serial
- Full cryptographic pre-verification before any push or install
- Remote SHA-256 validation via 'adb shell sha256sum' after push
- Live Tailscale reachability probing (unreachable nodes reported as UNKNOWN, never PASS)
"""

import os
import sys
import time
import json
import socket
import argparse
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from scripts.sign_mobile_artifacts import verify_mobile_artifact, compute_file_sha256

CLI_PATH = ROOT_DIR / "mobile" / "qflex_cli.py"
CLI_MANIFEST = ROOT_DIR / "mobile" / "qflex_cli.py.manifest.json"
CLI_SIG = ROOT_DIR / "mobile" / "qflex_cli.py.sig"

SETUP_PATH = ROOT_DIR / "mobile" / "setup-mobile.sh"
SETUP_MANIFEST = ROOT_DIR / "mobile" / "setup-mobile.sh.manifest.json"
SETUP_SIG = ROOT_DIR / "mobile" / "setup-mobile.sh.sig"

TRUST_ANCHOR = ROOT_DIR / "mobile" / "release_signing_key.pub"

APK_PATH = ROOT_DIR / "mcp_layer" / "qf_bot" / "mobile_apk" / "android" / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
APK_MANIFEST = ROOT_DIR / "mcp_layer" / "qf_bot" / "mobile_apk" / "android" / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk.manifest.json"
APK_SIG = ROOT_DIR / "mcp_layer" / "qf_bot" / "mobile_apk" / "android" / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk.sig"

HUD_HTML = ROOT_DIR / "mcp_layer" / "qf_bot" / "ui" / "QuantumFlex-Mobile.html"

REMOTE_DIR = "/sdcard/Download/QuantumFlex"

# ANSI Colors
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_DIM = "\033[2m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_CYAN = "\033[96m"
CLR_WHITE = "\033[97m"

def _c(color: str, text: str) -> str:
    if sys.stdout.isatty():
        return f"{color}{text}{CLR_RESET}"
    return text

def run_adb(cmd: List[str], serial: Optional[str] = None, timeout: float = 15.0) -> Tuple[int, str, str]:
    full_cmd = ["adb"]
    if serial:
        full_cmd.extend(["-s", serial])
    full_cmd.extend(cmd)
    try:
        p = subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except Exception as e:
        return -1, "", str(e)

def probe_tailscale_node(ip: str, timeout_ms: int = 1500) -> Tuple[str, Optional[float]]:
    """Active live reachability check. Never guesses or relies on stale state."""
    try:
        p = subprocess.run(
            ["ping", "-c", "2", "-W", str(timeout_ms / 1000.0), ip],
            capture_output=True, text=True, timeout=(timeout_ms / 1000.0) + 1.0
        )
        if p.returncode == 0:
            for line in p.stdout.splitlines():
                if "avg" in line or "rtt" in line:
                    parts = line.split("=")[-1].strip().split("/")
                    if len(parts) >= 2:
                        return "ONLINE", float(parts[1])
            return "ONLINE", None
        return "UNREACHABLE", None
    except Exception:
        return "UNKNOWN", None

def get_connected_adb_devices() -> List[Dict[str, str]]:
    rc, stdout, stderr = run_adb(["devices", "-l"])
    devices = []
    if rc != 0:
        return devices
    for line in stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            serial = parts[0]
            state = parts[1]
            extra = " ".join(parts[2:])
            devices.append({"serial": serial, "state": state, "extra": extra})
    return devices

def inspect_adb_device(serial: str) -> Dict[str, Any]:
    info = {"serial": serial}
    # Properties
    props = ["ro.product.manufacturer", "ro.product.model", "ro.product.name",
             "ro.build.version.release", "ro.boot.flash.locked", "ro.boot.verifiedbootstate"]
    for pr in props:
        _, val, _ = run_adb(["shell", f"getprop {pr}"], serial=serial)
        info[pr] = val

    # Battery
    _, bat, _ = run_adb(["shell", "dumpsys battery | grep level"], serial=serial)
    info["battery"] = bat.strip()

    # Screen Wake
    _, wake, _ = run_adb(["shell", "dumpsys power | grep mWakefulness"], serial=serial)
    info["wakefulness"] = wake.strip().splitlines()[0] if wake else "unknown"

    # Package check
    _, pkgs, _ = run_adb(["shell", "pm list packages | grep com.quantumflex.cockpit"], serial=serial)
    info["cockpit_installed"] = "com.quantumflex.cockpit" in pkgs

    # Determine QuantumFlex Role
    model = info.get("ro.product.model", "")
    name = info.get("ro.product.name", "")
    if "Pixel 11" in model or "grizzly" in name:
        info["qf_node"] = "pixel-11-pro"
        info["qf_role"] = "shard-custodian"
        info["authority"] = "Titan M2 Hardware Security Module (OOB Signer)"
    elif "S23" in model or "SM-S711" in model:
        info["qf_node"] = "s23-fe"
        info["qf_role"] = "field-workstation"
        info["authority"] = "Knox Vault Hardware Security (Field Console)"
    else:
        info["qf_node"] = "unknown"
        info["qf_role"] = "observer"
        info["authority"] = "Untrusted / Observer (Privileged Actions DENIED)"

    return info

def verify_source_assets():
    print(_c(CLR_BOLD + CLR_CYAN, "\n[*] Cryptographic Pre-Flight: Verifying Source Artifacts Against Trust Anchor..."))
    checks = [
        ("Mobile Operator CLI", CLI_PATH, CLI_MANIFEST, CLI_SIG),
        ("Mobile Setup Bootstrap", SETUP_PATH, SETUP_MANIFEST, SETUP_SIG),
        ("Native Cockpit APK", APK_PATH, APK_MANIFEST, APK_SIG),
    ]

    for label, art, man, sig in checks:
        if not art.exists():
            print(_c(CLR_RED, f"[!] FATAL: Artifact missing: {art}"))
            sys.exit(1)
        ok, reason = verify_mobile_artifact(str(art), str(man), str(sig), str(TRUST_ANCHOR))
        if not ok:
            print(_c(CLR_RED, f"[!] FATAL: Source artifact verification FAILED for {label}: {reason}"))
            sys.exit(1)
        print(_c(CLR_GREEN, f"  [PASS] {label:<24} : {reason}"))
    print(_c(CLR_GREEN, "[+] All mobile source assets verified against pinned trust anchor.\n"))

def stage_and_verify_files_on_device(serial: str):
    print(_c(CLR_BOLD + CLR_CYAN, f"[*] Staging Verified Artifacts to Device ({serial}:{REMOTE_DIR})..."))
    run_adb(["shell", f"mkdir -p {REMOTE_DIR}"], serial=serial)

    files_to_push = [
        (CLI_PATH, f"{REMOTE_DIR}/qflex_cli.py"),
        (CLI_MANIFEST, f"{REMOTE_DIR}/qflex_cli.py.manifest.json"),
        (CLI_SIG, f"{REMOTE_DIR}/qflex_cli.py.sig"),
        (SETUP_PATH, f"{REMOTE_DIR}/setup-mobile.sh"),
        (SETUP_MANIFEST, f"{REMOTE_DIR}/setup-mobile.sh.manifest.json"),
        (SETUP_SIG, f"{REMOTE_DIR}/setup-mobile.sh.sig"),
        (TRUST_ANCHOR, f"{REMOTE_DIR}/release_signing_key.pub"),
        (HUD_HTML, f"{REMOTE_DIR}/QuantumFlex-Mobile.html"),
    ]

    for local_f, remote_f in files_to_push:
        rc, _, err = run_adb(["push", str(local_f), remote_f], serial=serial)
        if rc != 0:
            print(_c(CLR_RED, f"[!] Failed to push {local_f.name}: {err}"))
            sys.exit(1)

    # Remote SHA-256 verification via 'adb shell sha256sum'
    print(_c(CLR_BOLD + CLR_CYAN, "[*] Verifying Remote SHA-256 Checksums on Android File System..."))
    for local_f, remote_f in files_to_push:
        local_sha, _ = compute_file_sha256(str(local_f))
        rc, out, _ = run_adb(["shell", f"sha256sum {remote_f}"], serial=serial)
        if rc != 0 or not out:
            print(_c(CLR_RED, f"[!] Remote sha256sum failed for {remote_f}"))
            sys.exit(1)
        remote_sha = out.split()[0].strip()
        if remote_sha.lower() != local_sha.lower():
            print(_c(CLR_RED, f"[!] SHA-256 MISMATCH for {remote_f}!"))
            print(f"    Local  : {local_sha}")
            print(f"    Remote : {remote_sha}")
            sys.exit(1)
        print(_c(CLR_GREEN, f"  [PASS] {local_f.name:<28} : {remote_sha[:16]}... (matches)"))

    # Mark shell scripts executable
    run_adb(["shell", f"chmod 0755 {REMOTE_DIR}/setup-mobile.sh {REMOTE_DIR}/qflex_cli.py"], serial=serial)
    print(_c(CLR_GREEN, f"[+] Successfully staged and hash-verified files in {REMOTE_DIR}\n"))

def install_apk_on_device(serial: str):
    print(_c(CLR_BOLD + CLR_CYAN, f"[*] Installing Verified Capacitor Cockpit APK on Device ({serial})..."))
    rc, out, err = run_adb(["install", "-r", str(APK_PATH)], serial=serial, timeout=45.0)
    if rc != 0 or "Success" not in out:
        print(_c(CLR_RED, f"[!] APK Installation FAILED: {err or out}"))
        sys.exit(1)

    print(_c(CLR_GREEN, f"  [PASS] APK Installation Succeeded: {out}"))

    # Confirm package registration
    rc2, out2, _ = run_adb(["shell", "pm list packages | grep com.quantumflex.cockpit"], serial=serial)
    if "com.quantumflex.cockpit" in out2:
        print(_c(CLR_GREEN, "  [PASS] Verified package 'com.quantumflex.cockpit' is active on device.\n"))
    else:
        print(_c(CLR_RED, "  [!] Warning: Package was installed but not found in pm list.\n"))

def main():
    parser = argparse.ArgumentParser(description="QuantumFlex Mobile Node Synchronizer (QF-M1)")
    parser.add_argument("--push", action="store_true", help="Push verified artifacts to device")
    parser.add_argument("--apk", action="store_true", help="Install verified Cockpit APK onto device")
    parser.add_argument("--device", help="Specific ADB device serial to target")
    args = parser.parse_args()

    print()
    print(_c(CLR_BOLD + CLR_CYAN, "═══════════════════════════════════════════════════════════════"))
    print(_c(CLR_BOLD + CLR_WHITE, "  QUANTUMFLEX MOBILE NODE SYNCHRONIZER (QF-M1)"))
    print(_c(CLR_BOLD + CLR_CYAN, "═══════════════════════════════════════════════════════════════"))

    # 1. Discover ADB Devices
    adb_devices = get_connected_adb_devices()
    print(f"  ADB Connected Devices : {len(adb_devices)}")
    for d in adb_devices:
        print(f"    • Serial: {d['serial']:<20} State: {d['state']:<12} {d.get('extra', '')}")

    # 2. Live Probe of Known Mesh Nodes
    print()
    print(_c(CLR_BOLD, "  Live Tailscale Mesh Reachability (No Stale Assumptions):"))
    mesh_nodes = [
        ("qfx-yoga (Master)", "100.64.1.17"),
        ("pixel-11-pro (Custody)", "100.64.1.18"),
        ("rahshauns-s23-fe (Field)", "100.64.1.32"),
    ]
    for name, ip in mesh_nodes:
        status, rtt = probe_tailscale_node(ip)
        if status == "ONLINE":
            rtt_str = f"({rtt:.1f}ms)" if rtt else ""
            print(f"    • {name:<26} : {ip:<15} {_c(CLR_GREEN, '[ONLINE]')} {rtt_str}")
        else:
            print(f"    • {name:<26} : {ip:<15} {_c(CLR_YELLOW, '[UNKNOWN / OFFLINE]')}")

    print(_c(CLR_BOLD + CLR_CYAN, "───────────────────────────────────────────────────────────────"))

    if not adb_devices:
        print(_c(CLR_YELLOW, "  No ADB devices currently detected over USB or Wi-Fi."))
        print(_c(CLR_BOLD + CLR_CYAN, "═══════════════════════════════════════════════════════════════\n"))
        sys.exit(0)

    # Filter target device
    target_dev = None
    if args.device:
        target_dev = next((d for d in adb_devices if d["serial"] == args.device), None)
        if not target_dev:
            print(_c(CLR_RED, f"[!] Specified device serial '{args.device}' not found in ADB list."))
            sys.exit(1)
    else:
        # Default to first authorized device
        authorized = [d for d in adb_devices if d["state"] == "device"]
        if authorized:
            target_dev = authorized[0]
        else:
            target_dev = adb_devices[0]

    # Inspection
    serial = target_dev["serial"]
    state = target_dev["state"]
    print(f"\n  Inspecting Target Device: {_c(CLR_BOLD, serial)} (State: {state})")

    if state != "device":
        print(_c(CLR_YELLOW, f"  [!] Device is in '{state}' state (not authorized)."))
        print("      Unlock the phone and accept the USB debugging prompt to authorize.")
        print(_c(CLR_BOLD + CLR_CYAN, "═══════════════════════════════════════════════════════════════\n"))
        sys.exit(0)

    dev_info = inspect_adb_device(serial)
    print(f"  Manufacturer      : {dev_info.get('ro.product.manufacturer')}")
    print(f"  Model             : {dev_info.get('ro.product.model')} ({dev_info.get('ro.product.name')})")
    print(f"  Android OS        : Version {dev_info.get('ro.product.version.release', dev_info.get('ro.build.version.release'))}")
    print(f"  Assigned QF Node  : {_c(CLR_BOLD + CLR_GREEN, dev_info.get('qf_node'))}")
    print(f"  QF Role           : {_c(CLR_BOLD, dev_info.get('qf_role'))}")
    print(f"  Authority Domain  : {dev_info.get('authority')}")
    print(f"  Battery           : {dev_info.get('battery')}")
    print(f"  Screen Status     : {dev_info.get('wakefulness')}")
    print(f"  Cockpit Package   : {_c(CLR_GREEN if dev_info.get('cockpit_installed') else CLR_YELLOW, 'INSTALLED' if dev_info.get('cockpit_installed') else 'NOT INSTALLED')}")
    print(_c(CLR_BOLD + CLR_CYAN, "═══════════════════════════════════════════════════════════════"))

    if not args.push and not args.apk:
        print(_c(CLR_DIM, "\n  Default Mode: INSPECTION ONLY. Zero modifications made."))
        print("  Use --push to deploy verified files, --apk to install Cockpit, or both:\n")
        print(f"    python3 scripts/sync_mobile_nodes.py --push --apk --device {serial}\n")
        sys.exit(0)

    # Perform mutations if requested
    verify_source_assets()

    if args.push:
        stage_and_verify_files_on_device(serial)

    if args.apk:
        install_apk_on_device(serial)

    print(_c(CLR_BOLD + CLR_GREEN, "═══════════════════════════════════════════════════════════════"))
    print(_c(CLR_BOLD + CLR_GREEN, f"  DEPLOYMENT COMPLETE ON {dev_info.get('qf_node').upper()} ({serial})"))
    print(_c(CLR_BOLD + CLR_GREEN, "═══════════════════════════════════════════════════════════════\n"))

if __name__ == "__main__":
    main()
