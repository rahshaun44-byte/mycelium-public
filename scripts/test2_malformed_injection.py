#!/usr/bin/env python3
"""
Test 2 Runner: Malformed / Empty OPA Response Injection
Validates D-2 fail-secure invariant under malformed OPA verdicts.
"""
import json
import os
import subprocess
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

CONF_PATH = "/home/quant/mycelium/mcp_layer/crypto_provider.conf"
LOG_PATH = "/home/quant/.local/state/quantum-flex-mycelium/immune-daemon.log"

request_count = 0

class MalformedProxyHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        global request_count
        request_count += 1
        
        # Read request body
        content_len = int(self.headers.get('Content-Length', 0))
        post_body = self.rfile.read(content_len)
        
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        
        # Alternate between empty result and malformed fields
        if request_count % 2 == 1:
            # Test D-2: Empty dict in result
            payload = {"result": {}}
        else:
            # Malformed status injection without node_status
            payload = {"result": {"status": "MALFORMED_INJECTION", "compliant": False}}
            
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def log_message(self, format, *args):
        return  # Suppress default server logs

def get_active_kem():
    if not os.path.exists(CONF_PATH):
        return None
    with open(CONF_PATH) as f:
        for line in f:
            if line.startswith("active_kem="):
                return line.strip().split("=")[1]
    return None

def main():
    print("[TEST 2] Starting Malformed / Empty OPA Response Injection Test")
    initial_kem = get_active_kem()
    print(f"[*] Initial active_kem: {initial_kem}")
    assert initial_kem == "ML-KEM-768", f"Precondition failed: expected ML-KEM-768, got {initial_kem}"

    print("[*] Stopping opa-immune.service...")
    subprocess.run(["systemctl", "--user", "stop", "opa-immune.service"], check=True)

    server = None
    server_thread = None
    try:
        server = HTTPServer(("127.0.0.1", 8181), MalformedProxyHandler)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        print("[*] Malformed HTTP injector bound to 127.0.0.1:8181")

        print("[*] Waiting for immune_daemon to query malformed endpoint (polling every 500ms)...")
        time.sleep(3.0)

        quarantine_kem = get_active_kem()
        print(f"[*] Post-injection active_kem: {quarantine_kem}")
        print(f"[*] Total intercepted requests: {request_count}")

        if quarantine_kem != "FrodoKEM-976-AES":
            print(f"[FAIL] Expected quarantine fallback FrodoKEM-976-AES, got {quarantine_kem}")
            sys.exit(1)
        print("[PASS] Invariant Verified: Daemon failed-secure to FrodoKEM-976-AES upon malformed OPA payload.")

    finally:
        if server:
            print("[*] Shutting down malformed HTTP injector...")
            server.shutdown()
            server.server_close()
        
        print("[*] Restarting opa-immune.service...")
        subprocess.run(["systemctl", "--user", "start", "opa-immune.service"], check=True)

    print("[*] Waiting for daemon recovery cycle (5s quarantine window + restore)...")
    time.sleep(7.0)

    recovered_kem = get_active_kem()
    print(f"[*] Post-recovery active_kem: {recovered_kem}")
    if recovered_kem != "ML-KEM-768":
        print(f"[FAIL] Expected recovery to ML-KEM-768, got {recovered_kem}")
        sys.exit(1)
        
    print("[PASS] Test 2 Complete: Clean recovery to ML-KEM-768 confirmed.")

if __name__ == "__main__":
    main()
