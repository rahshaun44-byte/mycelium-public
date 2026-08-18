#!/usr/bin/env python3
"""
Quantum Flex Process Supervisor (Windows & Cross-Platform)
===========================================================
Manages all Quantum Flex node services as detached background daemons:
- Athena-Node (Port 8001)
- Amara-Dashboard (Port 8000)
- Api-Node (Port 8080)
- Quantum-Flex-MCP (Port 9000)
- Sentinel-Tripwire
- Immune-Daemon
"""

import os
import sys
import json
import socket
import subprocess
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Load .env into process environment
env_file = BASE_DIR / ".env"
if env_file.exists():
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()

SERVICES = [
    {
        "name": "Athena-Node",
        "script": "mcp_layer/athena_api.py",
        "pattern": "athena_api.py",
        "port": 8005,
    },
    {
        "name": "Amara-Dashboard",
        "script": "amara/dashboard.py",
        "pattern": "dashboard.py",
        "port": 8000,
    },
    {
        "name": "Api-Node",
        "script": "api_node/main.py",
        "pattern": "api_node/main.py",
        "port": 8080,
    },
    {
        "name": "Quantum-Flex-MCP",
        "script": "mcp_layer/quantum_flex_mcp.py",
        "pattern": "quantum_flex_mcp.py",
        "port": 9000,
    },
    {
        "name": "Sentinel-Tripwire",
        "script": "sentinel/tripwire_daemon.py",
        "pattern": "tripwire_daemon.py",
        "port": None,
    },
    {
        "name": "Immune-Daemon",
        "script": "mcp_layer/immune_daemon.py",
        "pattern": "immune_daemon.py",
        "port": None,
    },
]


def get_running_procs():
    procs = []
    if sys.platform == "win32":
        try:
            cmd = "Get-CimInstance Win32_Process -Filter \"Name LIKE 'python%.exe'\" | Select-Object ProcessId, CommandLine | ConvertTo-Json"
            res = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=6)
            if res.stdout.strip():
                data = json.loads(res.stdout)
                if isinstance(data, dict):
                    procs = [data]
                elif isinstance(data, list):
                    procs = data
        except Exception:
            pass
    return procs


def stop_all():
    print("[*] Stopping any existing Quantum Flex background processes...")
    procs = get_running_procs()
    stopped = 0
    current_pid = os.getpid()

    for svc in SERVICES:
        pattern = svc["pattern"]
        for p in procs:
            pid = p.get("ProcessId")
            cmdline = p.get("CommandLine") or ""
            if pid and pid != current_pid and pattern in cmdline:
                try:
                    if sys.platform == "win32":
                        subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
                    else:
                        subprocess.run(["kill", "-9", str(pid)], capture_output=True)
                    print(f"  [-] Stopped {svc['name']} (PID: {pid})")
                    stopped += 1
                except Exception:
                    pass
    if stopped == 0:
        print("  [+] No existing Quantum Flex processes were running.")
    return stopped


def start_all():
    stop_all()
    print("\n=========================================")
    print("  QUANTUM FLEX: Launching Node Daemons   ")
    print("=========================================")

    python_exe = sys.executable

    for svc in SERVICES:
        name = svc["name"]
        script_path = str(BASE_DIR / svc["script"])
        log_out = open(LOGS_DIR / f"{name}.log", "a", encoding="utf-8")
        log_err = open(LOGS_DIR / f"{name}.err.log", "a", encoding="utf-8")

        print(f"[*] Launching {name}...")

        if sys.platform == "win32":
            # DETACHED_PROCESS = 0x00000008, CREATE_NEW_PROCESS_GROUP = 0x00000200
            creation_flags = 0x00000008 | 0x00000200
            p = subprocess.Popen(
                [python_exe, "-u", script_path],
                cwd=str(BASE_DIR),
                stdout=log_out,
                stderr=log_err,
                creationflags=creation_flags,
                close_fds=True,
            )
        else:
            p = subprocess.Popen(
                [python_exe, "-u", script_path],
                cwd=str(BASE_DIR),
                stdout=log_out,
                stderr=log_err,
                start_new_session=True,
            )

        print(f"    -> Spawned PID {p.pid} (Logs: logs/{name}.log)")

    print("\n[+] All 6 Quantum Flex services launched successfully in the background.")


def check_port(port: int) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        res = s.connect_ex(("127.0.0.1", port))
        return (res == 0)
    except Exception:
        return False
    finally:
        s.close()


def print_status():
    print("=========================================")
    print("     QUANTUM FLEX: System Status         ")
    print("=========================================")

    procs = get_running_procs()
    current_pid = os.getpid()

    for svc in SERVICES:
        name = svc["name"]
        pattern = svc["pattern"]
        matched_pids = []

        for p in procs:
            pid = p.get("ProcessId")
            cmdline = p.get("CommandLine") or ""
            if pid and pid != current_pid and pattern in cmdline:
                matched_pids.append(str(pid))

        if matched_pids:
            pids_str = ", ".join(matched_pids)
            print(f"  [RUNNING] {name:<20} PID(s): {pids_str}")
        else:
            print(f"  [STOPPED] {name:<20}")

        if svc["port"]:
            is_open = check_port(svc["port"])
            state = "LISTENING" if is_open else "Inactive"
            print(f"              Port {svc['port']}: {state}")

    print("-----------------------------------------")
    print("  TAILSCALE MESH STATUS:                 ")
    print("-----------------------------------------")
    try:
        ts_res = subprocess.run(["tailscale", "status"], capture_output=True, text=True, timeout=5)
        print(ts_res.stdout.strip())
    except Exception:
        print("  Tailscale status query failed")
    print("=========================================\n")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] == "status":
        print_status()
    elif sys.argv[1] == "start":
        start_all()
        import time
        time.sleep(2)
        print_status()
    elif sys.argv[1] == "stop":
        stop_all()
        print("[+] All Quantum Flex services stopped.")
    elif sys.argv[1] == "restart":
        start_all()
        import time
        time.sleep(2)
        print_status()
    else:
        print("Usage: python qf_daemon.py [start|stop|restart|status]")
