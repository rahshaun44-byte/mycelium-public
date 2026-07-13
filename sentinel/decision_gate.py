#!/usr/bin/env python3
"""
Ghost Node — Decision Gate
==========================
Upgraded: reads REAL kernel telemetry from /proc and vmstat.
Writes rich ledger.json every 60s to feed the AMARA dashboard.
Confidence score is computed from live system health, not hardcoded.
"""

import time
import json
import subprocess
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] GHOST-NODE | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("decision-gate")

CONFIDENCE_THRESHOLD = 0.75
LEDGER = Path("sentinel/ledger/ledger.json")


def read_iowait() -> float:
    try:
        result = subprocess.run(
            ["vmstat", "1", "2"], capture_output=True, text=True, timeout=5
        )
        lines = [l for l in result.stdout.strip().splitlines() if l and l[0].isdigit()]
        if lines:
            return float(lines[-1].split()[15])
    except Exception:
        pass
    return 0.0


def read_memory() -> dict:
    mem = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    mem[parts[0].rstrip(":")] = int(parts[1])
    except Exception:
        return {"ram_used_pct": 0.0, "swap_used_mb": 0.0}

    total = mem.get("MemTotal", 1)
    free  = mem.get("MemAvailable", 0)
    swap_total = mem.get("SwapTotal", 0)
    swap_free  = mem.get("SwapFree", 0)

    return {
        "ram_used_pct":  round(((total - free) / total) * 100.0, 2),
        "swap_used_mb":  round((swap_total - swap_free) / 1024.0, 2),
    }


def read_cpu_load() -> float:
    try:
        with open("/proc/loadavg") as f:
            return float(f.read().split()[0])
    except Exception:
        return 0.0


def compute_confidence(iowait: float, ram_pct: float, swap_mb: float) -> float:
    """
    Biological fitness function.
    Y = f(x) where environmental health maps to system confidence.
    Full health (low metrics) = 0.95. Critical state = 0.20.
    """
    score = 1.0
    score -= min(iowait / 100.0, 0.40)      # iowait degrades up to -40 pts
    score -= min(ram_pct / 200.0, 0.30)     # RAM pressure degrades up to -30 pts
    score -= min(swap_mb / 4096.0, 0.20)    # Swap degrades up to -20 pts
    return round(max(score, 0.05), 3)


def gate_decision(confidence: float) -> str:
    return "EXECUTE" if confidence >= CONFIDENCE_THRESHOLD else "HARD_STOP"


def main():
    log.info("Decision Gate Initialized — Quantum Flex Ghost Node ONLINE")
    LEDGER.parent.mkdir(parents=True, exist_ok=True)

    while True:
        iowait   = read_iowait()
        mem      = read_memory()
        cpu_load = read_cpu_load()
        confidence = compute_confidence(iowait, mem["ram_used_pct"], mem["swap_used_mb"])
        decision   = gate_decision(confidence)

        data = {
            "timestamp":  datetime.now().isoformat(),
            "status":     "ENTANGLEMENT_DELTA",
            "decision":   decision,
            "confidence": confidence,
            "nodes":      ["core_node", "sentinel", "mcp_layer", "athena-node", "qf-monitor"],
            "telemetry": {
                "iowait_pct":   iowait,
                "ram_used_pct": mem["ram_used_pct"],
                "swap_used_mb": mem["swap_used_mb"],
                "cpu_load_1m":  cpu_load,
            },
            "source": "ghost-node-agent",
        }

        with open(LEDGER, "w") as f:
            json.dump(data, f, indent=2)

        log.info(
            f"Sync Complete | confidence={confidence} | decision={decision} | "
            f"iowait={iowait}% | RAM={mem['ram_used_pct']}% | "
            f"swap={mem['swap_used_mb']:.1f}MB"
        )
        time.sleep(60)


if __name__ == "__main__":
    main()
