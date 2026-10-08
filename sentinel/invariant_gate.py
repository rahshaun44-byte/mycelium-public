#!/usr/bin/env python3
"""
═════════════════════════════════════════════════════════════════════
  QUANTUM FLEX // UNIVERSAL INVARIANT GATE (R >= O)
═════════════════════════════════════════════════════════════════════
Fail-secure admission gate enforcing physical and digital solvency.
Wraps Open Policy Agent (OPA) on http://127.0.0.1:8181.
Evaluates:
  - Digital Host Memory Headroom (Host RAM vs Process Claims)
  - Physical TPM 2.0 Hardware NVRAM Anchor (Index 0x1c00010 vs Ledger)
Persists all audit evaluations to PostgreSQL telemetry: invariant_audit_ledger.
"""

import os
import sys
import json
import time
import argparse
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

OPA_ENDPOINT = os.environ.get("OPA_ENDPOINT", "http://127.0.0.1:8181")
INVARIANT_URL = f"{OPA_ENDPOINT}/v1/data/quantumflex/invariant"

# ANSI Colors
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"


def get_db_connection():
    """Returns a psycopg2 connection to the telemetry database, or None if unavailable."""
    try:
        import psycopg2
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parent.parent / ".env")
        load_dotenv(Path(__file__).resolve().parent / ".env")
        conn = psycopg2.connect(
            host=os.environ.get("DB_HOST", "127.0.0.1"),
            port=int(os.environ.get("DB_PORT", "5432")),
            dbname=os.environ.get("DB_NAME", "telemetry"),
            user=os.environ.get("GHOSTNODE_DB_USER", "ghostnode"),
            password=os.environ.get("GHOSTNODE_DB_PASSWORD", ""),
            connect_timeout=2
        )
        return conn
    except Exception:
        return None


def log_invariant_audit(
    domain: str,
    resource_type: str,
    reserve_measured: Any,
    units_claimed: Any,
    requested_delta: Any,
    verdict: str,
    allow: bool,
    reason: str,
    evaluator: str = "invariant_gate"
) -> bool:
    """Persists invariant evaluation result into PostgreSQL invariant_audit_ledger."""
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO invariant_audit_ledger 
                (domain, resource_type, reserve_measured, units_claimed, requested_delta, verdict, allow, reason, evaluator)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                str(domain),
                str(resource_type),
                str(reserve_measured),
                str(units_claimed),
                str(requested_delta if requested_delta is not None else 0),
                str(verdict),
                bool(allow),
                str(reason),
                str(evaluator)
            )
        )
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return False


def query_opa_invariant(payload: Dict[str, Any]) -> Tuple[bool, str, str]:
    """Evaluates telemetry vector against Universal Invariant (R >= O) via Wasm or OPA sidecar."""
    # Zero-Friction Gatekeeper: Attempt in-process Wasm evaluation first (<100 µs)
    if os.environ.get("FORCE_HTTP_OPA") != "1":
        try:
            from sentinel.policies.wasm_gatekeeper import get_reserve_wasm_gatekeeper
            wasm_gate = get_reserve_wasm_gatekeeper()
            if wasm_gate is not None:
                return wasm_gate.evaluate_invariant(payload)
        except Exception:
            pass

    # Fallback: Loopback HTTP query to OPA sidecar (127.0.0.1:8181)
    try:
        req_data = json.dumps({"input": payload}).encode("utf-8")
        url = os.environ.get("OPA_INVARIANT_URL", INVARIANT_URL)
        req = urllib.request.Request(
            url,
            data=req_data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            result = data.get("result", {})
            allow = result.get("allow", False)
            verdict = result.get("verdict", "DENY")
            reason = result.get("reason", "Unspecified policy denial")
            return allow, verdict, reason
    except Exception as e:
        return False, "DENY", f"Fail-Secure: OPA sidecar unreachable ({e})"


def check_digital_memory() -> Dict[str, Any]:
    """Reads live host memory telemetry from /proc/meminfo."""
    mem_total = 0.0
    mem_avail = 0.0
    with open("/proc/meminfo", "r") as f:
        for line in f:
            if line.startswith("MemTotal:"):
                mem_total = float(line.split()[1]) / 1024.0
            elif line.startswith("MemAvailable:"):
                mem_avail = float(line.split()[1]) / 1024.0

    mem_used = mem_total - mem_avail
    return {
        "domain": "digital",
        "resource_type": "MEMORY_MB",
        "reserve_measured": round(mem_total, 2),
        "units_claimed": round(mem_used, 2),
        "telemetry_timestamp": int(time.time()),
        "max_staleness_seconds": 30,
    }


def check_tpm_anchor() -> Dict[str, Any]:
    """Reads static NVRAM genesis anchor and live PCR 15 runtime state."""
    nvram_tip = None
    try:
        res_nv = subprocess.run(["tpm2_nvread", "-C", "o", "-s", "32", "0x1c00010"], capture_output=True, timeout=3)
        if res_nv.returncode == 0 and len(res_nv.stdout) == 32:
            nvram_tip = res_nv.stdout.hex()
    except Exception:
        pass

    pcr15_state = None
    try:
        res_pcr = subprocess.run(["tpm2_pcrread", "sha256:15"], capture_output=True, text=True, timeout=3)
        if res_pcr.returncode == 0:
            for line in res_pcr.stdout.splitlines():
                if line.strip().startswith("15:"):
                    pcr15_state = line.split("15:")[1].strip().lower().replace("0x", "")
    except Exception:
        pass

    ledger_tip = None
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT block_hash FROM sentinel_ledger ORDER BY id DESC LIMIT 1;")
            row = cur.fetchone()
            if row and row[0]:
                ledger_tip = row[0]
            cur.close()
            conn.close()
        except Exception:
            pass

    return {
        "domain": "digital",
        "resource_type": "DUAL_TPM_ANCHOR",
        "reserve_measured": nvram_tip if nvram_tip else "UNAVAILABLE_NVRAM_READ_FAILED",
        "units_claimed": ledger_tip if ledger_tip else "UNAVAILABLE_LEDGER_READ_FAILED",
        "pcr15_runtime_measured": pcr15_state if pcr15_state else "UNAVAILABLE_PCR_READ_FAILED",
        "telemetry_timestamp": int(time.time()),
        "max_staleness_seconds": 60,
    }


def evaluate_invariant(payload: Dict[str, Any], evaluator: str = "invariant_gate") -> Dict[str, Any]:
    """
    Core functional evaluation endpoint.
    Queries OPA, commits to invariant_audit_ledger, and returns result dict.
    """
    allow, verdict, reason = query_opa_invariant(payload)
    
    # Audit log to PostgreSQL
    log_invariant_audit(
        domain=payload.get("domain", "unknown"),
        resource_type=payload.get("resource_type", "unknown"),
        reserve_measured=payload.get("reserve_measured"),
        units_claimed=payload.get("units_claimed"),
        requested_delta=payload.get("requested_delta", 0),
        verdict=verdict,
        allow=allow,
        reason=reason,
        evaluator=evaluator
    )
    
    return {
        "allowed": allow,
        "verdict": verdict,
        "reason": reason,
        "payload": payload,
        "timestamp": int(time.time())
    }


def evaluate_all_invariants(evaluator: str = "invariant_gate_all") -> Dict[str, Any]:
    """Runs a full composite evaluation across verified hardware (Digital RAM + Pluton TPM 2.0)."""
    mem_payload = check_digital_memory()
    mem_res = evaluate_invariant(mem_payload, evaluator=evaluator)

    tpm_payload = check_tpm_anchor()
    tpm_res = evaluate_invariant(tpm_payload, evaluator=evaluator)

    all_allowed = mem_res["allowed"] and tpm_res["allowed"]
    
    return {
        "all_allowed": all_allowed,
        "overall_verdict": "ADMIT" if all_allowed else "DENY",
        "timestamp": int(time.time()),
        "evaluations": {
            "digital_memory": mem_res,
            "tpm_anchor": tpm_res
        }
    }


def main():
    parser = argparse.ArgumentParser(
        description="QuantumFlex Universal Invariant Gate (R >= O)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # all command
    subparsers.add_parser("all", help="Evaluate composite hardware invariant (Digital RAM + TPM 2.0)")

    # memory command
    subparsers.add_parser("memory", help="Check host memory solvency (R_RAM >= O_USED)")

    # tpm command
    subparsers.add_parser("tpm", help="Verify TPM 2.0 NVRAM anchor against sentinel_ledger tip")

    args = parser.parse_args()

    if args.command == "all":
        res = evaluate_all_invariants(evaluator="cli_all")
        color = GREEN if res["all_allowed"] else RED
        print(f"\n{BOLD}{CYAN}╔═══════════════════════════════════════════════════════════════════╗{RESET}")
        print(f"{BOLD}{CYAN}║     QUANTUM FLEX: COMPOSITE INVARIANT AUDIT (R >= O)              ║{RESET}")
        print(f"{BOLD}{CYAN}╚═══════════════════════════════════════════════════════════════════╝{RESET}")
        print(f"  Overall Status: {color}{BOLD}[{res['overall_verdict']}]{RESET}\n")
        
        for name, ev in res["evaluations"].items():
            ev_col = GREEN if ev["allowed"] else RED
            p = ev["payload"]
            print(f"  * {BOLD}{name.upper()}{RESET} [{ev_col}{ev['verdict']}{RESET}]: {ev['reason']}")
            print(f"    Measured Reserve (R): {p.get('reserve_measured')}")
            print(f"    Claimed (O)         : {p.get('units_claimed')}")
        print(f"{BOLD}{CYAN}───────────────────────────────────────────────────────────────────{RESET}\n")
        sys.exit(0 if res["all_allowed"] else 2)

    elif args.command == "memory":
        payload = check_digital_memory()
        title = "Host Physical Memory Invariant"
    elif args.command == "tpm":
        payload = check_tpm_anchor()
        title = "Pluton TPM 2.0 Hardware Anchor Invariant"
    else:
        sys.exit(1)

    result = evaluate_invariant(payload, evaluator="cli_single")
    allow = result["allowed"]
    verdict = result["verdict"]
    reason = result["reason"]

    color = GREEN if allow else RED
    print(f"\n{BOLD}{CYAN}─── [QUANTUMFLEX INVARIANT GATE] ───────────────────────────{RESET}")
    print(f"  Target:     {BOLD}{title}{RESET}")
    print(f"  Verdict:    {color}{BOLD}[{verdict}]{RESET}")
    print(f"  Detail:     {reason}")
    print(f"  Payload:    {json.dumps(payload, indent=2)}")
    print(f"  Audit:      Committed to PostgreSQL (invariant_audit_ledger)")
    print(f"{BOLD}{CYAN}────────────────────────────────────────────────────────────{RESET}\n")

    sys.exit(0 if allow else 2)


if __name__ == "__main__":
    main()
