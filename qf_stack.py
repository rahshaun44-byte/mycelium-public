#!/usr/bin/env python3
"""
Quantum Flex Unified Node Stack (The Core Hive)
================================================
Single unified orchestrator running the entire Quantum Flex architecture:
  - AMARA Sync Dashboard   : http://0.0.0.0:8000
  - ATHENA RAG Node        : http://127.0.0.1:8001
  - API Gateway Node       : http://0.0.0.0:8080
  - Quantum Flex MCP Server: http://0.0.0.0:9000 (SSE: /sse)
  - Sentinel Tripwire & Immune Daemon background workers
"""

import os
import sys
import asyncio
import logging
import threading
import time
from pathlib import Path
from datetime import datetime

# Load environment variables
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

env_file = BASE_DIR / ".env"
if env_file.exists():
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()

import uvicorn
from amara.dashboard import app as dashboard_app
from mcp_layer.athena_api import app as athena_app
from api_node.main import app as api_app
from mcp_layer.quantum_flex_mcp import server as mcp_server

# ── Logging Setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] QF-HIVE | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("qf_stack")


def run_dashboard():
    """Worker thread for AMARA Sync Dashboard on port 8000."""
    try:
        log.info("[+] Starting AMARA Dashboard on http://0.0.0.0:8000")
        uvicorn.run(dashboard_app, host="0.0.0.0", port=8000, log_level="warning", access_log=False)
    except Exception as e:
        log.error(f"[-] AMARA Dashboard error: {e}")


def run_athena():
    """Worker thread for ATHENA RAG API on port 8001."""
    try:
        log.info("[+] Starting ATHENA RAG on http://127.0.0.1:8001")
        uvicorn.run(athena_app, host="127.0.0.1", port=8001, log_level="warning", access_log=False)
    except Exception as e:
        log.error(f"[-] ATHENA RAG error: {e}")


def run_api():
    """Worker thread for API Gateway on port 8080."""
    try:
        log.info("[+] Starting API Gateway on http://0.0.0.0:8080")
        uvicorn.run(api_app, host="0.0.0.0", port=8080, log_level="warning", access_log=False)
    except Exception as e:
        log.error(f"[-] API Gateway error: {e}")


def run_tripwire():
    """Background worker for Sentinel Tripwire."""
    try:
        from sentinel.tripwire_daemon import main as tripwire_main
        log.info("[+] Sentinel Tripwire daemon thread active")
        tripwire_main()
    except Exception as e:
        log.warning(f"[-] Sentinel Tripwire thread exited: {e}")


def run_immune_daemon():
    """Background worker for Immune Daemon."""
    try:
        from mcp_layer.immune_daemon import main as immune_main
        log.info("[+] PQC Immune Daemon thread active")
        immune_main()
    except Exception as e:
        log.warning(f"[-] Immune Daemon thread exited: {e}")


async def main():
    print("""
=============================================================
  QUANTUM FLEX: UNIFIED NODE STACK & MCP SERVER v2.0
=============================================================
  * AMARA Dashboard      : http://0.0.0.0:8000
  * ATHENA RAG API       : http://127.0.0.1:8001
  * API Gateway          : http://0.0.0.0:8080
  * Quantum Flex MCP     : http://0.0.0.0:9000 (SSE: /sse)
  * Tailscale Host IP    : 100.64.1.29
  * Samsung S23 FE Peer  : 100.64.1.33
=============================================================
""")

    # 1. Start background services in dedicated worker threads
    t_dash = threading.Thread(target=run_dashboard, daemon=True, name="DashboardWorker")
    t_dash.start()

    t_athena = threading.Thread(target=run_athena, daemon=True, name="AthenaWorker")
    t_athena.start()

    t_api = threading.Thread(target=run_api, daemon=True, name="ApiWorker")
    t_api.start()

    t_tripwire = threading.Thread(target=run_tripwire, daemon=True, name="TripwireWorker")
    t_tripwire.start()

    t_immune = threading.Thread(target=run_immune_daemon, daemon=True, name="ImmuneWorker")
    t_immune.start()

    # Small delay for threads to bind sockets
    time.sleep(1.0)

    # 2. Main async loop runs the Quantum Flex MCP Server (SSE transport)
    log.info("[+] Starting Quantum Flex MCP Server on http://0.0.0.0:9000 (SSE: /sse)...")
    await mcp_server.run_sse_async(host="0.0.0.0", port=9000)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Quantum Flex Unified Stack stopped by operator.")
