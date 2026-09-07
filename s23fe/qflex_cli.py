#!/usr/bin/env python3
"""
Quantum Flex Mobile CLI (Termux / Samsung Galaxy S23 FE)
=========================================================
Lightweight, zero-overhead mobile interface to communicate with Athena RAG,
Amara Orchestrator, and inspect biological telemetry securely over Tailscale mesh.

Target Host: 100.64.1.17 (quantumflex)
"""

import sys
import json
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime

HOST_IP = "100.64.1.17"
MCP_PORT = 9000
DASHBOARD_PORT = 8000
API_PORT = 8080
ATHENA_PORT = 8001

def _http_get(url: str, timeout: float = 5.0) -> dict:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "QuantumFlex-S23FE/2.5"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode())
    except urllib.error.URLError as e:
        return {"error": f"Connection failed to {url}: {e}"}
    except Exception as e:
        return {"error": str(e)}

def _http_post(url: str, data: dict, timeout: float = 60.0) -> dict:
    try:
        payload = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "QuantumFlex-S23FE/2.5"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode())
    except urllib.error.URLError as e:
        return {"error": f"Connection failed to {url}: {e}"}
    except Exception as e:
        return {"error": str(e)}

def cmd_status():
    print("\n==========================================")
    print("  QUANTUM FLEX: Mobile Node Health Check  ")
    print(f"  Target: http://{HOST_IP}")
    print("==========================================")
    
    # 1. Athena Node Check
    athena_data = _http_get(f"http://{HOST_IP}:{ATHENA_PORT}/health", timeout=4.0)
    if "error" in athena_data:
        print(f"[!] Athena RAG: OFFLINE ({athena_data['error']})")
    else:
        print(f"[+] Athena RAG: {athena_data.get('status', 'ONLINE')}")
        print(f"    Active Vectors : {athena_data.get('vector_count', 0)}")
        print(f"    Neural Model   : {athena_data.get('chat_model', 'athena:latest')}")

    # 2. Amara Dashboard Check
    dash_data = _http_get(f"http://{HOST_IP}:{DASHBOARD_PORT}/api/telemetry", timeout=4.0)
    if "error" in dash_data:
        print(f"[!] Amara Node: OFFLINE ({dash_data['error']})")
    else:
        drive = dash_data.get("drive", {})
        score = float(drive.get("drive_score", 0) or 0)
        status = drive.get("status", "OPTIMAL")
        print(f"[+] Amara Drive: {score:.1f} / 1500.0 (Status: {status})")
        print(f"    RAM Usage  : {drive.get('mem_usage', 0)} MB")
        print(f"    CPU Usage  : {drive.get('cpu_usage', 0)} %")

    print("==========================================\n")

def cmd_athena(question: str):
    print(f"\n[*] Interrogating Athena Neural RAG from Mobile...")
    print(f"    Query: \"{question}\"")
    data = _http_post(f"http://{HOST_IP}:{ATHENA_PORT}/query", {"question": question}, timeout=60.0)
    if "error" in data:
        # Fallback to API Gateway port if direct Athena fails
        data = _http_post(f"http://{HOST_IP}:{API_PORT}/query", {"question": question}, timeout=60.0)

    if "error" in data:
        print(f"[!] Error: {data['error']}")
    else:
        print("\n--- [ATHENA SYNTHESIS] -------------------")
        print(data.get("answer", "(No answer returned)"))
        print("------------------------------------------")
        sources = data.get("sources", [])
        if sources:
            print(f"Sources : {', '.join(sources)}")
        print(f"Model   : {data.get('model', 'athena:latest')}\n")

def cmd_interactive_chat():
    """Live interactive conversation loop with Athena from mobile terminal."""
    print("\n==========================================")
    print("  ATHENA NEURAL ORACLE — MOBILE CHAT LOOP ")
    print("  Type 'exit' or 'quit' to return to shell")
    print("==========================================\n")
    while True:
        try:
            prompt = input("athena-mobile > ").strip()
            if not prompt:
                continue
            if prompt.lower() in ("exit", "quit", "q"):
                break
            cmd_athena(prompt)
        except (KeyboardInterrupt, EOFError):
            print("\nSession ended.")
            break

def print_help():
    print("""
QuantumFlex Mobile Controller (Samsung S23 FE / Termux)
Usage:
  python qflex_cli.py status             - Health check of all host services
  python qflex_cli.py athena "<query>"   - Query Athena RAG knowledge base
  python qflex_cli.py chat               - Open interactive mobile chat with Athena
  python qflex_cli.py dash               - Output mobile web dashboard URL
""")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_help()
        sys.exit(0)

    cmd = sys.argv[1].lower()
    if cmd == "status":
        cmd_status()
    elif cmd in ("athena", "ask", "rag", "query"):
        if len(sys.argv) < 3:
            print("Usage: python qflex_cli.py athena \"<your question>\"")
        else:
            cmd_athena(" ".join(sys.argv[2:]))
    elif cmd in ("chat", "talk", "loop"):
        cmd_interactive_chat()
    elif cmd in ("dash", "dashboard"):
        print(f"\nAMARA Sync Dashboard URL: http://{HOST_IP}:{DASHBOARD_PORT}")
        print("Open this in Samsung Internet or Chrome over Tailscale.\n")
    else:
        print_help()
