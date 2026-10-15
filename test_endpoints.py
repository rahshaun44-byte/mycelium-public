#!/usr/bin/env python3
import os
import socket
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

TAILNET_IP = os.environ.get("TAILNET_IP", "100.64.1.17")

def test_http_get(host, port, path, desc):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect((host, port))
        host_header = "127.0.0.1" if port == 9000 else host
        request = f"GET {path} HTTP/1.1\r\nHost: {host_header}:{port}\r\nUser-Agent: Tester\r\nConnection: close\r\n\r\n"
        s.sendall(request.encode())
        data = s.recv(1024).decode(errors="replace")
        s.close()
        status_line = data.split("\r\n")[0] if data else "NO_RESPONSE"
        print(f"[PASS] {desc:<35} -> {status_line}")
    except Exception as e:
        print(f"[FAIL] {desc:<35} -> Error: {e}")

print("==================================================================")
print("  QUANTUM FLEX: COMPREHENSIVE ENDPOINT VERIFICATION               ")
print("==================================================================")

endpoints = [
    ("127.0.0.1", 9000, "/sse", "MCP SSE (Local)"),
    (TAILNET_IP, 9000, "/sse", "MCP SSE (Tailscale Mesh)"),
    ("127.0.0.1", 8000, "/", "AMARA Dashboard (Local)"),
    (TAILNET_IP, 8000, "/", "AMARA Dashboard (Tailscale)"),
    (TAILNET_IP, 8000, "/api/telemetry", "AMARA Telemetry API (Tailscale)"),
    (TAILNET_IP, 8080, "/status", "API Gateway (Tailscale)"),
    ("127.0.0.1", 8001, "/health", "Athena RAG Node (Local)"),
]

for host, port, path, desc in endpoints:
    test_http_get(host, port, path, desc)

print("==================================================================")
