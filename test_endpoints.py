#!/usr/bin/env python3
import os
import urllib.request
import subprocess
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

TAILNET_HOST = json.loads(subprocess.check_output(["tailscale", "status", "--json"], timeout=10))["Self"]["DNSName"].rstrip(".")

def test_http_get(host, port, path, desc):
    try:
        scheme = "https" if port == 443 else "http"
        with urllib.request.urlopen(f"{scheme}://{host}:{port}{path}", timeout=10) as response:
            if not 200 <= response.status < 300:
                raise ValueError(f"HTTP {response.status}")
            print(f"[PASS] {desc:<35} -> HTTP {response.status}")
        return True
    except Exception as e:
        print(f"[FAIL] {desc:<35} -> Error: {e}")
        return False

print("==================================================================")
print("  QUANTUM FLEX: COMPREHENSIVE ENDPOINT VERIFICATION               ")
print("==================================================================")

endpoints = [
    ("127.0.0.1", 9001, "/api/status", "Cockpit status (Local)"),
    (TAILNET_HOST, 443, "/api/status", "Cockpit status (Tailscale HTTPS)"),
    ("127.0.0.1", 8000, "/", "AMARA Dashboard (Local)"),
    (TAILNET_HOST, 443, "/ui/", "Cockpit UI (Tailscale HTTPS)"),
    ("127.0.0.1", 8000, "/api/telemetry", "AMARA Telemetry API (Local)"),
    ("127.0.0.1", 8080, "/status", "API Gateway (Local)"),
    ("127.0.0.1", 8001, "/health", "Athena RAG Node (Local)"),
]

results = [test_http_get(*endpoint) for endpoint in endpoints]

print("==================================================================")
print("HTTP reachability only; admission restrictions are reported in /api/status.")
if __name__ == "__main__":
    raise SystemExit(0 if all(results) else 1)
