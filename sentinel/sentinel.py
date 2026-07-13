#!/usr/bin/env python3
"""
Quantum Flex Sentinel: Euclidean Drive Monitor
==============================================
Calculates the Euclidean distance (Drive) between current telemetry and the optimal setpoint.
V1: Memory Usage (MB)
V2: CPU Load (%)
V3: I/O Wait (%)
V4: Cryptographic Integrity (Binary Penalty)

If Drive > Tolerance, executes a SIGSTOP (Hardstop) on the deviant node.
"""

import math
import time
import json
import logging
import subprocess
import psycopg2

# ── Configuration ─────────────────────────────────────────────────────────────
TOLERANCE = 1500.0
HASH_PENALTY = 5000.0  # Massive penalty to mathematically guarantee a hardstop
POLLING_INTERVAL = 10   # Seconds. Balances reactivity with runtime overhead.

# Setpoints (Sb)
SB_MEM = 512.0
SB_CPU = 5.0
SB_IOW = 1.0
SB_HASH = 0.0

BASELINE_SETPOINT = [SB_MEM, SB_CPU, SB_IOW, SB_HASH]

PG_CONFIG = {
    "host": "127.0.0.1", "port": 5432,
    "dbname": "telemetry", "user": "ghostnode",
    "password": "quantum_flex_auth",
}

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] SENTINEL | %(message)s")
log = logging.getLogger("sentinel")

def get_expected_digest(node_id):
    try:
        conn = psycopg2.connect(**PG_CONFIG, connect_timeout=3)
        cur = conn.cursor()
        cur.execute("SELECT expected_digest FROM integrity_registry WHERE node_id = %s", (node_id,))
        res = cur.fetchone()
        conn.close()
        return res[0] if res else None
    except Exception as e:
        log.error(f"DB Error: {e}")
        return None

def get_node_telemetry(node_id):
    # 1. Get stats
    try:
        stats_raw = subprocess.check_output(
            ["podman", "stats", node_id, "--no-stream", "--format", "json"], 
            text=True
        )
        stats = json.loads(stats_raw)[0]
        
        # Parse Mem (e.g. "75MB" -> 75.0)
        mem_str = stats.get("MemUsage", "0B").split("/")[0].strip().replace("MB", "").replace("GB", "").replace("B", "")
        # Very rough parse for PoC, assuming MB scale.
        try: mem_mb = float(mem_str) * 1024 if "G" in stats.get("MemUsage","") else float(mem_str)
        except: mem_mb = 0.0
        
        # Parse CPU
        cpu_str = stats.get("CPUPerc", "0.00%").replace("%", "")
        try: cpu_pct = float(cpu_str)
        except: cpu_pct = 0.0
        
    except Exception as e:
        log.error(f"Failed to fetch stats for {node_id}: {e}")
        return None

    # 2. Get IO Wait (System-wide proxy for now)
    try:
        with open("/proc/stat", "r") as f:
            cpu_times = f.readline().split()[1:8]
            cpu_times = [float(x) for x in cpu_times]
            io_wait = cpu_times[4]
            total_time = sum(cpu_times)
            # Rough instantaneous IO wait %
            io_pct = (io_wait / total_time) * 100.0 if total_time > 0 else 0.0
    except:
        io_pct = 0.0

    # 3. Get Integrity
    expected_digest = get_expected_digest(node_id)
    hash_penalty = 0.0
    if expected_digest:
        try:
            current_digest = subprocess.check_output(
                ["podman", "inspect", "--format='{{.ImageDigest}}'", node_id], 
                text=True
            ).strip().strip("'")
            if current_digest != expected_digest:
                hash_penalty = HASH_PENALTY
        except Exception:
            hash_penalty = HASH_PENALTY # Assume breach on failure
            
    return [mem_mb, cpu_pct, io_pct, hash_penalty]

def calculate_drive(current_state, baseline_setpoint):
    if len(current_state) != len(baseline_setpoint):
        raise ValueError("State vectors must align.")
    return math.sqrt(sum((c - b) ** 2 for c, b in zip(current_state, baseline_setpoint)))

def hardstop_node(node_id, drive_val):
    log.critical(f"TOLERANCE BREACHED! Drive: {drive_val:.2f} > {TOLERANCE}. Executing SIGSTOP.")
    subprocess.run(["podman", "pause", node_id])
    
    # Update Truth Log
    try:
        conn = psycopg2.connect(**PG_CONFIG)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO memory_logs (agent_id, action_taken, outcome)
            VALUES ('SENTINEL', %s, 'Drive threshold exceeded. Container frozen.')
        """, (f"SIGSTOP issued to {node_id} (D={drive_val:.2f})",))
        
        cur.execute("UPDATE integrity_registry SET lockout_status = TRUE WHERE node_id = %s", (node_id,))
        conn.commit()
        conn.close()
    except:
        pass

def main():
    log.info("Sentinel Euclidean Drive Monitor Online.")
    target_node = "amara-matrix"
    
    while True:
        telemetry = get_node_telemetry(target_node)
        if telemetry:
            try:
                drive = calculate_drive(telemetry, BASELINE_SETPOINT)
                log.info(f"Node: {target_node} | Sc: {telemetry} | Drive: {drive:.2f}")
                
                if drive > TOLERANCE:
                    hardstop_node(target_node, drive)
                    break # Halt monitoring after quarantine
            except Exception as e:
                log.error(f"Calculation fault: {e}")
        
        time.sleep(POLLING_INTERVAL)

if __name__ == "__main__":
    main()
