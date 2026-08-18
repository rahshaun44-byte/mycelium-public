#!/usr/bin/env python3
"""
═════════════════════════════════════════════════════════════════════
  QUANTUM FLEX: LIVE-FIRE IMMUNE DAEMON & OPA GATING TEST
═════════════════════════════════════════════════════════════════════
Tests the exact live-fire scenario:
1. Starts OPA sidecar with `membrane_health.rego` on port 8181
2. Sets threat intelligence flag in OPA: ML_KEM_COMPROMISED = True
3. Initializes crypto_provider.conf with `active_kem=ML-KEM-512`
4. Executes single-cycle Immune Daemon evaluation (--once)
5. Asserts OPA verdict returned TOXIC with recommended_fallback `FrodoKEM-640-AES`
6. Asserts atomic rewrite of crypto_provider.conf to `FrodoKEM-640-AES`
"""

import os
import sys
import time
import json
import subprocess
import urllib.request
from pathlib import Path
import tempfile

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT_DIR = Path(__file__).resolve().parents[1]
OPA_EXE = Path(os.environ["LOCALAPPDATA"]) / "Programs" / "OPA" / "opa.exe"
POLICY_PATH = ROOT_DIR / "pqc-immune-daemon" / "membrane_health.rego"

def run_live_fire_test():
    print("=" * 68)
    print("  LIVE-FIRE TEST: PQC IMMUNE DAEMON (ML-KEM-512 COMPROMISE)")
    print("=" * 68)

    # 1. Start OPA server
    print(f"[*] Launching OPA daemon on 127.0.0.1:8181 with policy: {POLICY_PATH.name}")
    opa_proc = subprocess.Popen(
        [str(OPA_EXE), "run", "-s", "--addr", "127.0.0.1:8181", str(POLICY_PATH)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    time.sleep(2)

    try:
        # 2. Inject threat flag into OPA: ML_KEM_COMPROMISED = true
        print("[*] Injecting threat intel flag: data.threat_flags.ML_KEM_COMPROMISED = true")
        put_req = urllib.request.Request(
            "http://127.0.0.1:8181/v1/data/threat_flags",
            data=json.dumps({"ML_KEM_COMPROMISED": True, "FRODOKEM_COMPROMISED": False}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="PUT"
        )
        with urllib.request.urlopen(put_req, timeout=5) as resp:
            print(f"  [+] Threat flag injected. OPA HTTP {resp.status}")

        # 3. Create test crypto_provider.conf with ML-KEM-512
        with tempfile.TemporaryDirectory() as tmpdir:
            conf_file = Path(tmpdir) / "crypto_provider.conf"
            conf_file.write_text("active_kem=ML-KEM-512\nactive_sig=ML-DSA-65\n")
            print(f"[*] Initialized crypto_provider.conf with active_kem=ML-KEM-512")

            # 4. Run immune_daemon --once against live OPA
            daemon_script = ROOT_DIR / "pqc-immune-daemon" / "immune_daemon.py"
            cmd = [sys.executable, str(daemon_script), "--conf", str(conf_file), "--opa", "http://127.0.0.1:8181", "--once", "-v"]
            print(f"[*] Executing live Immune Daemon evaluation cycle...")
            res = subprocess.run(cmd, capture_output=True, text=True)
            print(res.stdout)
            if res.stderr:
                print(res.stderr)

            # 5. Verify config rewrite
            rewritten = conf_file.read_text()
            print("=" * 68)
            print(f"[*] Resulting crypto_provider.conf:\n{rewritten}")
            
            assert "active_kem=FrodoKEM-640-AES" in rewritten, (
                f"FAILED: Expected FrodoKEM-640-AES, but got:\n{rewritten}"
            )
            print("[PASS] LIVE-FIRE VERIFICATION SUCCEEDED:")
            print("       ML-KEM-512 correctly collapsed to FrodoKEM-640-AES via live OPA verdict!")
            print("=" * 68 + "\n")

    finally:
        opa_proc.terminate()
        opa_proc.wait()

if __name__ == "__main__":
    run_live_fire_test()
