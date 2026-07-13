#!/usr/bin/env python3
"""
Quantum Flex Swarm Pre-Flight Checklist
=========================================
Executes a strict verification of the active daemon status and PostgreSQL Truth Log
connection before allowing the swarm to initiate.
"""

import sys
import subprocess
import psycopg2

PG_CONFIG = {
    "host": "127.0.0.1", "port": 5432,
    "dbname": "telemetry", "user": "ghostnode",
    "password": "quantum_flex_auth",
}

def check_postgres():
    print("[*] Verifying PostgreSQL Truth Log (amara-matrix)... ", end="")
    try:
        conn = psycopg2.connect(**PG_CONFIG, connect_timeout=3)
        conn.close()
        print("OK")
        return True
    except Exception as e:
        print("FAILED")
        print(f"    Error: {e}")
        return False

def check_daemon(service_name):
    print(f"[*] Verifying Systemd Daemon ({service_name})... ", end="")
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-active", service_name],
            capture_output=True, text=True, timeout=3
        )
        if result.stdout.strip() == "active":
            print("ACTIVE")
            return True
        else:
            print("INACTIVE")
            return False
    except Exception as e:
        print("FAILED")
        print(f"    Error: {e}")
        return False

def check_ollama():
    print("[*] Verifying Ollama Inference Engine... ", end="")
    try:
        result = subprocess.run(
            ["curl", "-s", "http://127.0.0.1:11434/api/tags"],
            capture_output=True, text=True, timeout=3
        )
        if '"models":' in result.stdout:
            print("ONLINE")
            return True
        else:
            print("OFFLINE (Unexpected Response)")
            return False
    except Exception as e:
        print("FAILED")
        return False

def main():
    print("=== QUANTUM FLEX SWARM PRE-FLIGHT ===")
    checks = [
        check_postgres(),
        check_daemon("ghost-node-agent.service"),
        check_daemon("athena-node.service"),
        check_daemon("qf-monitor.service"),
        check_ollama()
    ]
    
    if all(checks):
        print("\n[SUCCESS] Pre-Flight Checklist Passed. System is hardened and ready for Swarm execution.")
        sys.exit(0)
    else:
        print("\n[CRITICAL] Pre-Flight Checklist Failed. Swarm initiation aborted to protect infrastructure.")
        sys.exit(1)

if __name__ == "__main__":
    main()
