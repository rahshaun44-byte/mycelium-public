#!/usr/bin/env python3
"""
═════════════════════════════════════════════════════════════════════
  OPERATION KINETIC YIELD: ATHENA TACTICAL OBJECTION ENGINE
═════════════════════════════════════════════════════════════════════
Real-time objection handler. Ingests prospect pushback from C-level /
architect outreach, queries Athena Vector RAG, and synthesizes grounded,
authoritative engineering counter-responses in seconds.
"""

import os
import sys
import json
import urllib.request
from pathlib import Path

# Safe console rendering for Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ATHENA_URL = "http://127.0.0.1:8001/query"

# ANSI Colors
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

SYSTEM_PROMPT = """You are A.T.H.E.N.A., acting as the Senior Cryptographic Architect assisting Rahshaun Chambers (FinallyFungus LLC).
The user is a CISO, Lead Security Architect, or Director at a federal defense subcontractor who has raised an objection to our PQC-Agility Supervisor advisory outreach.

Formulate an authoritative, engineering-grounded, and concise email reply (under 150 words) that:
1. Validates their engineering perspective without sounding defensive.
2. Identifies the specific failure mode or regulatory blindspot in their objection (citing OMB M-26-15 or NIST FIPS 203/204/205).
3. Offers a low-friction next step (e.g., sending the 2-page Whitepaper or a 10-min technical architecture walkthrough).
4. Maintains an engineer-to-engineer tone. Never sound like a pushy salesman."""

def solve_objection(objection: str) -> str:
    print(f"\n{BOLD}[*] Interrogating Athena Neural Oracle on Objection...{RESET}")
    print(f"    {DIM}Objection: \"{objection}\"{RESET}\n")

    query = f"{SYSTEM_PROMPT}\n\nPROSPECT OBJECTION:\n{objection}"
    
    payload = json.dumps({"question": query, "top_k": 4}).encode("utf-8")
    req = urllib.request.Request(
        ATHENA_URL,
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            answer = data.get("answer", "")
            return answer
    except Exception as e:
        return f"Error contacting Athena RAG node: {e}"

def main():
    if len(sys.argv) > 1:
        objection_text = " ".join(sys.argv[1:])
        counter = solve_objection(objection_text)
        print(f"{CYAN}{BOLD}┌─── [TACTICAL COUNTER-RESPONSE] ────────────────────────────────{RESET}")
        print(f"{GREEN}{counter}{RESET}")
        print(f"{CYAN}└─────────────────────────────────────────────────────────────────{RESET}\n")
    else:
        print(f"{CYAN}{BOLD}=== ATHENA TACTICAL OBJECTION ENGINE (INTERACTIVE) ==={RESET}")
        print(f"Paste prospect reply below (or type 'exit' to quit):\n")
        while True:
            try:
                line = input(f"{BOLD}prospect > {RESET}").strip()
                if not line:
                    continue
                if line.lower() in ("exit", "quit", "q"):
                    break
                counter = solve_objection(line)
                print(f"\n{CYAN}{BOLD}┌─── [TACTICAL COUNTER-RESPONSE] ────────────────────────────────{RESET}")
                print(f"{GREEN}{counter}{RESET}")
                print(f"{CYAN}└─────────────────────────────────────────────────────────────────{RESET}\n")
            except (KeyboardInterrupt, EOFError):
                break

if __name__ == "__main__":
    main()
