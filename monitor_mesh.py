#!/usr/bin/env python3
import subprocess
import urllib.request
import json
import time
import datetime

OPA_HEALTH_URL = "http://127.0.0.1:8181/health"
CHECK_INTERVAL_SEC = 30

def check_opa():
    try:
        req = urllib.request.Request(OPA_HEALTH_URL, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                return True, "HEALTHY"
    except Exception as e:
        return False, str(e)
    return False, "Non-200 response"

def check_tailscale():
    try:
        result = subprocess.run(
            ["tailscale", "status", "--json"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True, 
            timeout=5
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            backend_state = data.get("BackendState", "Unknown")
            self_node = data.get("Self", {})
            self_online = self_node.get("Online", False)
            is_healthy = (backend_state == "Running" and self_online)
            
            # Auto-heal if stalled or offline
            if not is_healthy and backend_state in ("Running", "Starting", "Stopped", "NeedsLogin"):
                print("[!] Tailscale connection stalled or offline. Triggering autonomous bounce...")
                subprocess.run(["tailscale", "down"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
                subprocess.run(["tailscale", "up", "--accept-routes=false", "--ssh"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
                return True, "HEALED_ONLINE"
                
            return is_healthy, f"{backend_state} (Online={self_online})"
        else:
            return False, f"Command failed: {result.stderr.strip()}"
    except Exception as e:
        return False, str(e)

def main_loop():
    print(f"[*] Starting QuantumFlex Mesh & OPA Monitor on qfx-yoga (Interval: {CHECK_INTERVAL_SEC}s)...")
    print("-" * 75)
    
    try:
        while True:
            timestamp = datetime.datetime.utcnow().isoformat() + "Z"
            
            opa_ok, opa_msg = check_opa()
            ts_ok, ts_msg = check_tailscale()
            
            opa_status = "[OK]" if opa_ok else "[ALERT]"
            ts_status = "[OK]" if ts_ok else "[ALERT]"
            
            print(f"[{timestamp}] OPA Gateway: {opa_status} ({opa_msg}) | Tailscale Mesh: {ts_status} ({ts_msg})")
            
            if not opa_ok or not ts_ok:
                print(f"[-] WARNING: Perimeter anomaly detected at {timestamp}!")
                
            time.sleep(CHECK_INTERVAL_SEC)
    except KeyboardInterrupt:
        print("\n[*] Monitor stopped by operator.")

if __name__ == "__main__":
    main_loop()
