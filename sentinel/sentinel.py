#!/usr/bin/env python3
"""
Quantum Flex Sentinel: Unified Truth Ledger (Euclidean Drive)
==============================================================
Single-cycle execution designed for systemd .timer invocation.
NO flat-file silos. ALL telemetry flows directly to the amara-matrix
PostgreSQL state-bus via psycopg2.

Mathematical Bound:
    D = sqrt( sum( (Sc_i - Sb_i)^2 ) )
    
State Vector: [V1_RAM_MB, V2_CPU_PCT, V3_IO_WAIT_PCT, V4_HASH_PENALTY]
Tolerance: 1500
Hash Penalty: 5000 (guarantees instant breach regardless of other vectors)
"""

import subprocess
import psycopg2
import math
import json
import requests
from datetime import datetime

# ── Configuration & Baselines ─────────────────────────────────────────────────
# Superuser connection (Truth Log: memory_logs, integrity_registry)
DB_CONFIG = {
    "dbname": "telemetry",
    "user": "ghostnode",
    "password": "quantum_flex_auth",
    "host": "127.0.0.1",
    "port": "5432",
}

# Restricted service role (sentinel_ledger ONLY — blast radius containment)
DB_SENTINEL = {
    "dbname": "telemetry",
    "user": "sentinel_service",
    "password": "***REDACTED-ROTATED-CREDENTIAL***",
    "host": "127.0.0.1",
    "port": "5432",
}

TARGET_NODE = "amara-matrix"
TOLERANCE = 1500.0
HASH_PENALTY_VALUE = 5000.0  # Mathematically guarantees breach of 1500 threshold

# Setpoints: [RAM_MB, CPU_Percent, IO_Wait_Percent, Hash_Mismatch_Penalty]
SETPOINT = [512.0, 5.0, 1.0, 0.0]


def execute_command(cmd):
    """Executes a local shell command and returns stdout."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip()


def get_current_telemetry():
    """Extracts V1 (RAM), V2 (CPU), V3 (IO Wait), V4 (Hash) from the physical node."""
    # ── V1 & V2: Podman Stats ─────────────────────────────────────────────
    stats_raw = execute_command(f"podman stats --no-stream --format json {TARGET_NODE}")
    stats = json.loads(stats_raw)[0]

    # Parse RAM: e.g. "107MB / 2.147GB" -> 107.0
    mem_usage_str = stats.get("mem_usage", "0MB / 0GB").split("/")[0].strip()
    mem_val = float("".join(c for c in mem_usage_str if c.isdigit() or c == "."))
    if "GB" in mem_usage_str or "GiB" in mem_usage_str:
        mem_val *= 1024.0
    ram_mb = mem_val

    # Parse CPU: e.g. "0.61%" -> 0.61
    cpu_percent = float(stats.get("cpu_percent", "0.00%").replace("%", ""))

    # ── V3: I/O Wait (from /proc/stat) ────────────────────────────────────
    try:
        with open("/proc/stat", "r") as f:
            cpu_line = f.readline().split()
            # Fields: user nice system idle iowait irq softirq steal
            cpu_times = [float(x) for x in cpu_line[1:8]]
            iowait = cpu_times[4]
            total = sum(cpu_times)
            io_wait_pct = (iowait / total) * 100.0 if total > 0 else 0.0
    except Exception:
        io_wait_pct = 0.0

    # ── V4: Cryptographic Integrity ───────────────────────────────────────
    current_digest = execute_command(
        f"podman inspect --format='{{{{.ImageDigest}}}}' {TARGET_NODE}"
    )

    return ram_mb, cpu_percent, io_wait_pct, current_digest


def query_integrity_registry(current_digest):
    """Queries amara-matrix for the baseline hash. Returns (conn, hash_penalty)."""
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        cur.execute(
            "SELECT expected_digest FROM integrity_registry WHERE node_id = %s",
            (TARGET_NODE,),
        )
        row = cur.fetchone()
        expected_digest = row[0] if row else None
        cur.close()

        if expected_digest is None:
            # No baseline registered — fail secure
            return conn, HASH_PENALTY_VALUE

        hash_penalty = 0.0 if current_digest == expected_digest else HASH_PENALTY_VALUE
        return conn, hash_penalty

    except Exception as e:
        print(f"[SENTINEL] TRUTH LOG FAILURE: {e}")
        # Fail secure: apply penalty if DB unreachable
        return conn, HASH_PENALTY_VALUE


def log_to_truth_bus(conn, drive, ram, cpu, io, hash_penalty):
    """Commits the telemetry vector and drive calculation to the unified state-bus."""
    # 1. Write to memory_logs via ghostnode (superuser)
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO memory_logs (agent_id, action_taken, outcome)
               VALUES (%s, %s, %s)""",
            (
                "Sentinel",
                f"Euclidean Drive: {drive:.2f}",
                f"V1_RAM={ram:.1f}MB V2_CPU={cpu:.2f}% V3_IOW={io:.2f}% V4_HASH={hash_penalty:.0f}",
            ),
        )
        conn.commit()
        cur.close()
    except Exception as e:
        print(f"[SENTINEL] Failed to commit to Truth Log: {e}")

    # 2. Write structured telemetry to sentinel_ledger via restricted role
    status = "HARDSTOP" if drive > TOLERANCE else "EQUILIBRIUM"
    try:
        sconn = psycopg2.connect(**DB_SENTINEL)
        scur = sconn.cursor()
        scur.execute(
            """INSERT INTO sentinel_ledger (cpu_usage, mem_usage, io_wait, hash_penalty, drive_score, status)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (cpu, ram, io, hash_penalty, drive, status),
        )
        sconn.commit()
        scur.close()
        sconn.close()
    except Exception as e:
        print(f"[SENTINEL] Failed to commit to sentinel_ledger: {e}")


def trigger_n8n_webhook(drive):
    """Fires a localized webhook to the n8n orchestrator."""
    url = "http://127.0.0.1:5678/webhook/sentinel-alert"
    payload = {
        "timestamp": datetime.now().isoformat(),
        "deviant_node": TARGET_NODE,
        "euclidean_drive": f"{drive:.2f}",
        "lockout_status": True,
        "action_taken": "HARDSTOP_SIGSTOP_EXECUTED"
    }
    try:
        response = requests.post(url, json=payload, timeout=2.0)
        print(f"[SENTINEL] n8n Webhook Fired. Response: {response.status_code}")
    except Exception as e:
        print(f"[SENTINEL] Failed to trigger n8n webhook: {e}")

def execute_hardstop(conn, drive):
    """Freezes the deviant container and locks the integrity registry."""
    print(f"[SENTINEL] CRITICAL: Drive {drive:.2f} > {TOLERANCE}. EXECUTING HARDSTOP (SIGSTOP).")
    execute_command(f"podman pause {TARGET_NODE}")

    # Trigger Orchestrator
    trigger_n8n_webhook(drive)

    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE integrity_registry SET lockout_status = TRUE WHERE node_id = %s",
            (TARGET_NODE,),
        )
        cur.execute(
            """INSERT INTO memory_logs (agent_id, action_taken, outcome)
               VALUES ('Sentinel', %s, 'Container frozen. Lockout engaged.')""",
            (f"HARDSTOP: Drive {drive:.2f} breached tolerance {TOLERANCE}",),
        )
        conn.commit()
        cur.close()
    except Exception as e:
        print(f"[SENTINEL] Lockout log failed: {e}")


def enforce_homeostasis():
    """Single-cycle homeostatic enforcement. Designed for .timer invocation."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] Sentinel Cycle Initiated...")

    # 1. Extract physical telemetry
    ram, cpu, io, current_hash = get_current_telemetry()

    # 2. Query the Truth Log for integrity baseline
    conn, hash_penalty = query_integrity_registry(current_hash)

    # 3. Construct current state vector
    current_state = [ram, cpu, io, hash_penalty]

    # 4. Calculate Euclidean Drive
    drive = math.sqrt(sum((c - b) ** 2 for c, b in zip(current_state, SETPOINT)))

    print(f"[{ts}] Telemetry Vector: {current_state} | Drive: {drive:.2f} | Tolerance: {TOLERANCE}")

    # 5. Commit to unified state-bus (NO flat files)
    if conn:
        log_to_truth_bus(conn, drive, ram, cpu, io, hash_penalty)

    # 6. The Logic Gate
    if drive > TOLERANCE:
        if conn:
            execute_hardstop(conn, drive)
    else:
        print(f"[{ts}] System within equilibrium. No action required.")

    # 7. Cleanup
    if conn:
        conn.close()


if __name__ == "__main__":
    enforce_homeostasis()
