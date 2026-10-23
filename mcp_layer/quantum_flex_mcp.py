#!/usr/bin/env python3
"""
Quantum Flex MCP Server (Windows & Cross-Platform)
===================================================
Exposes the running Quantum Flex node stack (ATHENA RAG, AMARA Dashboard,
API Gateway, Sentinel/Tripwire, Immune Daemon) as standard Model Context Protocol
(MCP) tools over Tailscale.

Bound to 127.0.0.1:9000 for local MCP clients:
- SSE Endpoint:             http://127.0.0.1:9000/sse
- Streamable HTTP Endpoint: http://127.0.0.1:9000/mcp (or /)
"""

import asyncio
import ipaddress
import json
import logging
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import httpx
from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

# ── Logging Configuration ───────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] QF-MCP | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("quantum_flex_mcp")

# ── Paths & Network Endpoints ───────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent  # mycelium directory
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

ATHENA_URL = os.environ.get("ATHENA_URL", "http://127.0.0.1:8001")
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://127.0.0.1:8000")
API_NODE_URL = os.environ.get("API_NODE_URL", "http://127.0.0.1:8080")
MCP_PORT = int(os.environ.get("MCP_PORT", 9000))
MCP_HOST = os.environ.get("MCP_HOST", "127.0.0.1")

KNOWN_SERVICES = {
    "Athena-Node": {"pattern": "athena_api.py", "port": 8001, "script": "mcp_layer/athena_api.py"},
    "Amara-Dashboard": {"pattern": "dashboard.py", "port": 8000, "script": "amara/dashboard.py"},
    "Api-Node": {"pattern": "api_node/main.py", "port": 8080, "script": "api_node/main.py"},
    "Quantum-Flex-MCP": {"pattern": "quantum_flex_mcp.py", "port": 9000, "script": "mcp_layer/quantum_flex_mcp.py"},
    "Sentinel-Tripwire": {"pattern": "tripwire_daemon.py", "port": None, "script": "sentinel/tripwire_daemon.py"},
    "Immune-Daemon": {"pattern": "immune_daemon.py", "port": None, "script": "pqc-immune-daemon/immune_daemon.py"},
}

ALLOWED_ACTIONS = {"start", "stop", "restart"}

# ── Initialize MCP Server ───────────────────────────────────────────────────
server = MCPServer(
    name="quantum-flex",
    title="Quantum Flex Node Stack Controller",
    description="Query and control the Quantum Flex SOC-in-a-box node stack over Tailscale mesh.",
    version="2.0.0",
)


def _get_active_processes() -> List[Dict[str, Any]]:
    """Query running python processes on Windows or Linux."""
    procs = []
    if sys.platform == "win32":
        try:
            cmd = "Get-CimInstance Win32_Process -Filter \"Name LIKE 'python%.exe'\" | Select-Object ProcessId, CommandLine | ConvertTo-Json"
            res = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=5)
            if res.stdout.strip():
                data = json.loads(res.stdout)
                if isinstance(data, dict):
                    procs = [data]
                elif isinstance(data, list):
                    procs = data
        except Exception as e:
            log.warning(f"Process query error: {e}")
    else:
        try:
            res = subprocess.run(["pgrep", "-a", "python"], capture_output=True, text=True, timeout=5)
            for line in res.stdout.strip().splitlines():
                parts = line.split(" ", 1)
                if len(parts) == 2:
                    procs.append({"ProcessId": int(parts[0]), "CommandLine": parts[1]})
        except Exception as e:
            log.warning(f"Process query error: {e}")
    return procs


@server.tool()
def list_services() -> dict:
    """List status, process IDs, and port states for all Quantum Flex services."""
    procs = _get_active_processes()
    results = {}

    for name, cfg in KNOWN_SERVICES.items():
        pattern = cfg["pattern"]
        matched_pids = []
        for p in procs:
            cmdline = p.get("CommandLine") or ""
            if pattern in cmdline:
                matched_pids.append(p.get("ProcessId"))

        status = "RUNNING" if matched_pids else "STOPPED"
        port_listening = False

        if cfg["port"]:
            # Test socket connectivity
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            try:
                res = sock.connect_ex(("127.0.0.1", cfg["port"]))
                port_listening = (res == 0)
            except Exception:
                port_listening = False
            finally:
                sock.close()

        results[name] = {
            "status": status,
            "pids": matched_pids,
            "port": cfg["port"],
            "listening": port_listening,
        }

    return {
        "timestamp": datetime.now().isoformat(),
        "substrate": sys.platform,
        "services": results,
    }


@server.tool()
async def ask_athena(question: str) -> dict:
    """Query ATHENA (RAG cognitive node) with a security or telemetry question.
    Proxied securely over loopback — ATHENA itself is never exposed externally."""
    if not question.strip():
        return {"error": "Question cannot be empty"}
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(f"{ATHENA_URL}/query", json={"question": question})
            return r.json()
    except Exception as e:
        return {"status": "OFFLINE", "error": f"Failed to query Athena: {str(e)}"}


@server.tool()
async def dashboard_snapshot() -> dict:
    """Fetch live telemetry, Euclidean Drive score (D), RAM/CPU load, and integrity state from AMARA Dashboard."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{DASHBOARD_URL}/api/telemetry")
            return r.json()
    except Exception as e:
        return {"status": "OFFLINE", "error": f"Failed to reach dashboard: {str(e)}"}


@server.tool()
async def api_node_status() -> dict:
    """Fetch health check and status from the API Gateway node."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{API_NODE_URL}/status")
            return r.json()
    except Exception as e:
        return {"status": "OFFLINE", "error": f"Failed to query API node: {str(e)}"}


@server.tool()
def tailnet_mesh_status() -> dict:
    """Check Tailscale mesh status, local IP, and report peer connectivity."""
    try:
        res = subprocess.run(["tailscale", "status", "--json"], capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            data = json.loads(res.stdout)
            self_node = data.get("Self", {})
            peers = data.get("Peer", {})
            s23_status = "UNKNOWN"
            for k, p in peers.items():
                if "s23" in p.get("HostName", "").lower() or "s23" in p.get("DNSName", "").lower():
                    s23_status = {
                        "host_name": p.get("HostName"),
                        "tailscale_ip": p.get("TailscaleIPs", [""])[0],
                        "active": p.get("Active", False),
                        "direct": p.get("CurAddr", ""),
                        "last_seen": p.get("LastSeen", ""),
                    }
                    break

            return {
                "local_hostname": self_node.get("HostName"),
                "local_tailscale_ip": self_node.get("TailscaleIPs", [""])[0],
                "magic_dns_suffix": data.get("MagicDNSSuffix"),
                "s23_fe_peer": s23_status,
                "total_peers": len(peers),
            }
        else:
            # Fallback plain text status
            txt_res = subprocess.run(["tailscale", "status"], capture_output=True, text=True, timeout=5)
            return {"status_raw": txt_res.stdout}
    except Exception as e:
        return {"error": str(e)}


@server.tool()
def service_status(service_name: str) -> dict:
    """Inspect status and read the last 40 lines of logs for a specific Quantum Flex service."""
    if service_name not in KNOWN_SERVICES:
        return {"error": f"Unknown service '{service_name}'. Known services: {list(KNOWN_SERVICES.keys())}"}

    log_file = LOGS_DIR / f"{service_name}.log"
    err_file = LOGS_DIR / f"{service_name}.err.log"

    stdout_content = ""
    stderr_content = ""

    if log_file.exists():
        try:
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
                stdout_content = "".join(lines[-40:])
        except Exception as e:
            stdout_content = f"Error reading log: {e}"

    if err_file.exists():
        try:
            with open(err_file, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
                stderr_content = "".join(lines[-40:])
        except Exception as e:
            stderr_content = f"Error reading err log: {e}"

    return {
        "service": service_name,
        "stdout_recent": stdout_content or "(No output captured)",
        "stderr_recent": stderr_content or "(No errors logged)",
    }


@server.tool()
def service_action(service_name: str, action: str) -> dict:
    """Start, stop, or restart a specific Quantum Flex service.
    service_name must be one of: Athena-Node, Amara-Dashboard, Api-Node, Quantum-Flex-MCP, Sentinel-Tripwire, Immune-Daemon.
    action must be one of: start, stop, restart."""
    if service_name not in KNOWN_SERVICES:
        return {"error": f"Invalid service '{service_name}'"}
    if action not in ALLOWED_ACTIONS:
        return {"error": f"Invalid action '{action}'. Must be one of {ALLOWED_ACTIONS}"}

    cfg = KNOWN_SERVICES[service_name]
    pattern = cfg["pattern"]
    script_rel = cfg["script"]
    script_path = BASE_DIR / script_rel

    # 1. Stop if running
    procs = _get_active_processes()
    stopped_pids = []
    for p in procs:
        cmdline = p.get("CommandLine") or ""
        pid = p.get("ProcessId")
        if pattern in cmdline and pid:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
            else:
                subprocess.run(["kill", "-9", str(pid)], capture_output=True)
            stopped_pids.append(pid)

    if action == "stop":
        return {"service": service_name, "action": "stop", "stopped_pids": stopped_pids, "status": "SUCCESS"}

    # 2. Start service
    log_out = LOGS_DIR / f"{service_name}.log"
    log_err = LOGS_DIR / f"{service_name}.err.log"

    if sys.platform == "win32":
        cmd = f"Start-Process python -ArgumentList '\"{script_path}\"' -RedirectStandardOutput '{log_out}' -RedirectStandardError '{log_err}' -WindowStyle Hidden"
        subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True)
    else:
        subprocess.Popen(
            [sys.executable, str(script_path)],
            stdout=open(log_out, "a"),
            stderr=open(log_err, "a"),
            start_new_session=True,
        )

    return {
        "service": service_name,
        "action": action,
        "stopped_pids": stopped_pids,
        "status": "STARTED",
        "log_path": str(log_out),
    }


# ── Transport Security ──────────────────────────────────────────────────────
_TAILNET_NETS = (ipaddress.ip_network("100.64.0.0/10"), ipaddress.ip_network("fd7a:115c:a1e0::/48"))
_TS_DNS_RE = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+ts\.net$")


def _local_tailnet_identity() -> tuple[list[str], Optional[str]]:
    """Return this node's own tailnet IPs and MagicDNS name; ([], None) on any doubt."""
    try:
        res = subprocess.run(["tailscale", "status", "--json"], capture_output=True, text=True, timeout=5)
        self_node = json.loads(res.stdout).get("Self")
    except (OSError, subprocess.SubprocessError, ValueError, AttributeError):
        return [], None
    if not isinstance(self_node, dict):
        return [], None

    ips = []
    raw_ips = self_node.get("TailscaleIPs")
    for raw in raw_ips if isinstance(raw_ips, list) else []:
        try:
            ip = ipaddress.ip_address(raw)
        except (TypeError, ValueError):
            continue
        if any(ip in net for net in _TAILNET_NETS):
            ips.append(f"[{ip}]" if ip.version == 6 else str(ip))

    dns = self_node.get("DNSName")
    dns = dns.rstrip(".").lower() if isinstance(dns, str) else ""
    return ips, dns if _TS_DNS_RE.match(dns) else None


def _transport_security(port: int) -> TransportSecuritySettings:
    """Exact Host/Origin allowlist: loopback plus this node's own tailnet identity, never wildcards."""
    hosts = [f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"]
    ips, dns = _local_tailnet_identity()
    hosts += [f"{ip}:{port}" for ip in ips]
    origins = [f"http://{h}" for h in hosts]
    if dns:
        hosts += [dns, f"{dns}:443", f"{dns}:{port}"]
        origins += [f"https://{dns}", f"https://{dns}:443", f"http://{dns}:{port}"]
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True, allowed_hosts=hosts, allowed_origins=origins
    )


# ── Server Runner ───────────────────────────────────────────────────────────
async def main():
    log.info("=" * 60)
    log.info("Quantum Flex MCP Server v2.0 Starting")
    log.info(f"  Bind Host : {MCP_HOST}")
    log.info(f"  Port      : {MCP_PORT}")
    log.info(f"  SSE URL   : http://{MCP_HOST}:{MCP_PORT}/sse")
    log.info("=" * 60)

    # Loopback only. Remote access is Tailscale Serve, not 0.0.0.0.
    await server.run_sse_async(
        host=MCP_HOST, port=MCP_PORT, transport_security=_transport_security(MCP_PORT)
    )


if __name__ == "__main__":
    asyncio.run(main())
