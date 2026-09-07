#!/usr/bin/env python3
"""
Test 3 Runner: Primary Crypto Failure & Full Fallback Chain Rollover
Validates:
1. ML-KEM-768 (TOXIC) -> FrodoKEM-976-AES
2. FrodoKEM-976-AES (TOXIC) -> X25519
3. X25519 (TOXIC) -> Chain Exhaustion (recommended=NONE) -> FAIL-CLOSED HALT (sys.exit(1))
4. Clean post-test recovery
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

current_stage = 1

class ChainProxyHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        global current_stage
        content_len = int(self.headers.get('Content-Length', 0))
        post_body = self.rfile.read(content_len)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

        if current_stage == 1:
            # Stage 1: ML-KEM-768 is TOXIC -> fallback to FrodoKEM-976-AES
            payload = {
                "result": {
                    "node_status": "TOXIC",
                    "recommended_fallback": "FrodoKEM-976-AES",
                    "findings": [{"algorithm": "ML-KEM-768", "status": "TOXIC", "reason": "Test 3 Injection Stage 1"}]
                }
            }
        elif current_stage == 2:
            # Stage 2: FrodoKEM-976-AES is TOXIC -> fallback to X25519
            payload = {
                "result": {
                    "node_status": "TOXIC",
                    "recommended_fallback": "X25519",
                    "findings": [{"algorithm": "FrodoKEM-976-AES", "status": "TOXIC", "reason": "Test 3 Injection Stage 2"}]
                }
            }
        else:
            # Stage 3: X25519 is TOXIC -> fallback exhausted (NONE)
            payload = {
                "result": {
                    "node_status": "TOXIC",
                    "recommended_fallback": "NONE",
                    "findings": [{"algorithm": "X25519", "status": "TOXIC", "reason": "Test 3 Injection Stage 3 - Exhaustion"}]
                }
            }

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

def reset_conf(kem="ML-KEM-768"):
    lines = []
    if os.path.exists(CONF_PATH):
        with open(CONF_PATH) as f:
            for line in f:
                if line.startswith("active_kem="):
                    lines.append(f"active_kem={kem}\n")
                else:
                    lines.append(line)
        with open(CONF_PATH, "w") as f:
            f.writelines(lines)

def main():
    global current_stage
    print("[TEST 3] Primary Crypto Failure & Full Fallback Chain Rollover Test")
    
    # 1. Run local test suite verification
    print("[*] Running unit test assertions in test_immune_daemon.py...")
    res = subprocess.run([
        "/home/quant/mycelium/venv/bin/python3",
        "/home/quant/pqc-immune-daemon/pqc-immune-daemon/test_immune_daemon.py"
    ], capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[FAIL] test_immune_daemon.py failed:\n{res.stderr}")
        sys.exit(1)
    print("[PASS] Unit test invariant verified.")

    initial_kem = get_active_kem()
    print(f"[*] Initial active_kem on disk: {initial_kem}")
    if initial_kem != "ML-KEM-768":
        reset_conf("ML-KEM-768")
        time.sleep(1)

    print("[*] Stopping opa-immune.service...")
    subprocess.run(["systemctl", "--user", "stop", "opa-immune.service"], check=True)

    server = None
    server_thread = None
    try:
        server = HTTPServer(("127.0.0.1", 8181), ChainProxyHandler)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        print("[*] Mock OPA Chain Injector bound to 127.0.0.1:8181")

        # --- STAGE 1: ML-KEM-768 -> FrodoKEM-976-AES ---
        current_stage = 1
        print("[*] Stage 1: Injecting TOXIC verdict for ML-KEM-768 (expecting rollover -> FrodoKEM-976-AES)...")
        for _ in range(10):
            time.sleep(0.5)
            if get_active_kem() == "FrodoKEM-976-AES":
                break
        s1_kem = get_active_kem()
        print(f"[*] Post-Stage 1 active_kem: {s1_kem}")
        assert s1_kem == "FrodoKEM-976-AES", f"Stage 1 failed: expected FrodoKEM-976-AES, got {s1_kem}"
        print("[PASS] Stage 1 Rollover: ML-KEM-768 -> FrodoKEM-976-AES verified.")

        # --- STAGE 2: FrodoKEM-976-AES -> X25519 ---
        current_stage = 2
        print("[*] Stage 2: Injecting TOXIC verdict for FrodoKEM-976-AES (expecting rollover -> X25519)...")
        for _ in range(10):
            time.sleep(0.5)
            if get_active_kem() == "X25519":
                break
        s2_kem = get_active_kem()
        print(f"[*] Post-Stage 2 active_kem: {s2_kem}")
        assert s2_kem == "X25519", f"Stage 2 failed: expected X25519, got {s2_kem}"
        print("[PASS] Stage 2 Rollover: FrodoKEM-976-AES -> X25519 verified.")

        # --- STAGE 3: X25519 -> NONE (Chain Exhaustion -> Halt) ---
        current_stage = 3
        print("[*] Stage 3: Injecting TOXIC verdict for X25519 (expecting chain exhaustion -> sys.exit(1) halt)...")
        # Check daemon log before stage 3
        time.sleep(2.0)
        
        # Verify log output records the fatal halt
        with open(LOG_PATH, "r") as lf:
            recent_logs = lf.read()
        
        if "FATAL: TOXIC verdict with no usable fallback (recommended=NONE)" in recent_logs:
            print("[PASS] Stage 3 Verified: Daemon logged fatal exhaustion and halted data path.")
        else:
            print("[WARN] Checking for exhaustion trigger...")
            time.sleep(1.0)
            with open(LOG_PATH, "r") as lf:
                recent_logs = lf.read()
            assert "FATAL: TOXIC verdict with no usable fallback" in recent_logs, "Expected fatal exhaustion log not found!"
            print("[PASS] Stage 3 Verified: Daemon logged fatal exhaustion and halted data path.")

        # Invariant: conf must NOT be rewritten to an unverified or bogus cipher
        s3_kem = get_active_kem()
        assert s3_kem == "X25519", f"Security violation: config mutated after exhaustion to {s3_kem}"
        print("[PASS] Invariant Verified: No unverified cipher state written upon chain exhaustion.")

    finally:
        if server:
            print("[*] Shutting down mock OPA server...")
            server.shutdown()
            server.server_close()

        print("[*] Restoring baseline config (active_kem=ML-KEM-768)...")
        reset_conf("ML-KEM-768")

        print("[*] Restarting opa-immune.service...")
        subprocess.run(["systemctl", "--user", "start", "opa-immune.service"], check=True)

        print("[*] Restarting immune-daemon.service...")
        subprocess.run(["systemctl", "--user", "restart", "immune-daemon.service"], check=True)

    print("[*] Waiting for clean steady state (5s)...")
    time.sleep(5.0)

    final_kem = get_active_kem()
    print(f"[*] Final steady-state active_kem: {final_kem}")
    assert final_kem == "ML-KEM-768", f"Recovery failed: expected ML-KEM-768, got {final_kem}"
    print("[PASS] Test 3 Complete: Full 3-tier fallback rollover & fail-closed halt verified.")

if __name__ == "__main__":
    main()
