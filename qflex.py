#!/usr/bin/env python3
"""
═════════════════════════════════════════════════════════════════════
  QUANTUM FLEX: MASTER BIOLOGICAL CONTROL HUD & COMMAND CONSOLE
═════════════════════════════════════════════════════════════════════
Intelligent, secure, and effortless unified interface for QuantumFlex.
Provides live telemetry, neural vector RAG, autonomous swarm orchestration,
PQC crypto-agility monitoring, n8n workflow automation, and master host vault backup.
"""

import os
import sys
import json
import time
import urllib.request
import urllib.parse
import urllib.error
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Safe console rendering for Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")

# ANSI Color Palettes (Cyberpunk Theme)
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

# Service Ports & Endpoints
ATHENA_URL = "http://127.0.0.1:8005"
AMARA_URL = "http://127.0.0.1:8000"
OPA_URL = os.environ.get("OPA_ENDPOINT", "http://127.0.0.1:8181")
OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
N8N_URL = "http://127.0.0.1:5678"

def print_banner():
    banner = f"""
{CYAN}{BOLD}╔═══════════════════════════════════════════════════════════════════╗
║   ██████╗ ██╗   ██╗ █████╗ ███╗   ██╗████████╗██╗   ██╗███╗   ███╗   ║
║  ██╔═══██╗██║   ██║██╔══██╗████╗  ██║╚══██╔══╝██║   ██║████╗ ████║   ║
║  ██║   ██║██║   ██║███████║██╔██╗ ██║   ██║   ██║   ██║██╔████╔██║   ║
║  ██║▄▄ ██║██║   ██║██╔══██║██║╚██╗██║   ██║   ██║   ██║██║╚██╔╝██║   ║
║  ╚██████╔╝╚██████╔╝██║  ██║██║ ╚████║   ██║   ╚██████╔╝██║ ╚═╝ ██║   ║
║   ╚══▀▀═╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝ ╚═╝     ╚═╝   ║
║             {MAGENTA}BARE-METAL BIOLOGICAL SYSTEMS HUD — v2.5{CYAN}              ║
╚═══════════════════════════════════════════════════════════════════╝{RESET}"""
    print(banner)

def http_get(url: str, timeout: float = 3.0):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "QuantumFlex-HUD/2.5"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            try:
                return json.loads(resp.read().decode())
            except Exception:
                return {"status": "ONLINE"}
    except Exception:
        return None

def http_post(url: str, data: dict, timeout: float = 45.0):
    try:
        payload = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "QuantumFlex-HUD/2.5"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}

def check_service_health():
    """Probes all biological stratum services on loopback."""
    services = [
        {"name": "Ollama LLM Runner", "url": f"{OLLAMA_URL}/api/tags", "port": 11434, "stratum": "Neural Inference"},
        {"name": "Open Policy Agent", "url": f"{OPA_URL}/v1/data", "port": 8181, "stratum": "PQC Gating"},
        {"name": "Athena Neural RAG", "url": f"{ATHENA_URL}/health", "port": 8005, "stratum": "Vector Memory"},
        {"name": "Amara Dashboard", "url": f"{AMARA_URL}/", "port": 8000, "stratum": "Matrix HUD"},
        {"name": "n8n Workflow Engine", "url": f"{N8N_URL}/healthz", "port": 5678, "stratum": "Automation Core"},
    ]

    print(f"\n{BOLD}{CYAN}─── [BIOLOGICAL STRATA HEALTH VITALS] ───────────────────────────{RESET}")
    for s in services:
        res = http_get(s["url"])
        if res is not None:
            status_tag = f"{GREEN}[ONLINE]{RESET}"
            details = f"Port :{s['port']} | {s['stratum']}"
        else:
            status_tag = f"{RED}[OFFLINE]{RESET}"
            details = f"Port :{s['port']} | Not responding"
        print(f"  {status_tag} {BOLD}{s['name']:<22}{RESET} -> {details}")
    print(f"{CYAN}─────────────────────────────────────────────────────────────────{RESET}\n")

def cmd_ask_athena(query: str):
    """Directly queries Athena Vector RAG knowledge base."""
    print(f"\n{BOLD}[*] Interrogating A.T.H.E.N.A. Knowledge Graph...{RESET}")
    print(f"    {DIM}Query: \"{query}\"{RESET}")
    
    resp = http_post(f"{ATHENA_URL}/query", {"question": query})
    if "error" in resp:
        print(f"{RED}[!] Athena Offline or Error: {resp['error']}{RESET}")
        print(f"    {YELLOW}Tip: Start Athena via `qflex start` or python mcp_layer/athena_api.py{RESET}\n")
        return

    answer = resp.get("answer", "(No response generated)")
    sources = resp.get("sources", [])
    model = resp.get("model", "athena:latest")

    print(f"\n{CYAN}{BOLD}┌─── [A.T.H.E.N.A. SYNTHESIS] ────────────────────────────────────{RESET}")
    print(f"{GREEN}{answer.strip()}{RESET}")
    print(f"{CYAN}└─────────────────────────────────────────────────────────────────{RESET}")
    if sources:
        print(f"{DIM}Sources: {', '.join(sources)} | Model: {model}{RESET}\n")

def cmd_dispatch_directive(directive: str):
    """Dispatches a directive through the controller into the task queue."""
    print(f"\n{BOLD}[*] Dispatching Swarm Directive to Controller...{RESET}")
    print(f"    {DIM}Directive: \"{directive}\"{RESET}")
    
    controller_script = ROOT_DIR / "mcp_layer" / "controller.py"
    res = subprocess.run([sys.executable, str(controller_script), directive], capture_output=True, text=True)
    if res.returncode == 0:
        print(f"{GREEN}[+] Directive successfully processed and queued:{RESET}")
        for line in res.stdout.splitlines():
            if "Queued Task" in line or "Generated" in line:
                print(f"    {line}")
    else:
        print(f"{RED}[!] Controller dispatch error:{RESET}\n{res.stderr}")
    print()

def cmd_pqc_status():
    """Inspects post-quantum crypto-agility configuration."""
    conf_path = ROOT_DIR / "mcp_layer" / "crypto_provider.conf"
    if not conf_path.exists():
        conf_path = ROOT_DIR / "pqc-immune-daemon" / "crypto_provider.conf"

    print(f"\n{BOLD}{CYAN}─── [POST-QUANTUM CRYPTO-AGILITY (FIPS 203/204)] ────────────────{RESET}")
    if conf_path.exists():
        print(f"Config Source: {conf_path}")
        with open(conf_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    k, v = line.split("=", 1) if "=" in line else (line, "")
                    if "active" in k:
                        print(f"  {GREEN}{BOLD}* {k.upper():<16} : {v}{RESET}")
                    elif "fallback" in k:
                        print(f"  {YELLOW}  {k:<16} : {v}{RESET}")
    else:
        print(f"{RED}[!] crypto_provider.conf not found.{RESET}")
    print(f"{CYAN}─────────────────────────────────────────────────────────────────{RESET}\n")

def cmd_wealth_status():
    """Runs DePIN wealth elevation telemetry."""
    wealth_script = ROOT_DIR / "tools" / "depin_wealth_engine.py"
    if wealth_script.exists():
        subprocess.run([sys.executable, str(wealth_script)])
    else:
        print(f"{RED}[!] depin_wealth_engine.py missing.{RESET}\n")

def cmd_rotate_credentials():
    """Executes CSPRNG credential rotation and entropy audit."""
    rot_script = ROOT_DIR / "tools" / "rotate_credentials.py"
    if rot_script.exists():
        subprocess.run([sys.executable, str(rot_script), "--rotate"])
    else:
        print(f"{RED}[!] rotate_credentials.py missing.{RESET}\n")

def cmd_start_stack():
    """Launches full biological stack."""
    launcher_ps = ROOT_DIR / "Start-QuantumFlexStack.ps1"
    print(f"{BOLD}[*] Launching QuantumFlex biological stack via PowerShell...{RESET}")
    subprocess.Popen(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(launcher_ps)], shell=True)
    time.sleep(3)
    check_service_health()

def cmd_start_n8n():
    """Launches n8n workflow engine."""
    n8n_ps = ROOT_DIR / "Start-N8nNode.ps1"
    print(f"{BOLD}[*] Launching n8n Autonomous Workflow Engine...{RESET}")
    subprocess.Popen(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(n8n_ps)], shell=True)
    time.sleep(3)
    check_service_health()

def cmd_backup_vault():
    """Creates a permanent master host vault archive."""
    vault_script = ROOT_DIR / "tools" / "secure_host_vault.py"
    if vault_script.exists():
        subprocess.run([sys.executable, str(vault_script)])
    else:
        print(f"{RED}[!] secure_host_vault.py missing.{RESET}\n")

def interactive_hud():
    """Interactive TUI Menu for instant ease of use."""
    while True:
        print_banner()
        check_service_health()
        print(f"{BOLD}SELECT AN ACTION:{RESET}")
        print(f"  {CYAN}[1]{RESET} Ask A.T.H.E.N.A. (Neural Vector Memory / RAG)")
        print(f"  {CYAN}[2]{RESET} Dispatch Swarm Directive (\"The Claw\" Controller)")
        print(f"  {CYAN}[3]{RESET} Sovereign Wealth Dashboard (3-Stream Engine)")
        print(f"  {CYAN}[4]{RESET} PQC Immune Daemon & Crypto-Agility Status")
        print(f"  {CYAN}[5]{RESET} Rotate & Secure All Credentials (CSPRNG Vault)")
        print(f"  {CYAN}[6]{RESET} Start Full Biological Stack (All Node Services)")
        print(f"  {CYAN}[7]{RESET} Launch n8n Workflow Engine (Port 5678)")
        print(f"  {CYAN}[8]{RESET} Backup Master Host Vault (C:\\Users\\quant\\QuantumFlex_Master_Vault)")
        print(f"  {CYAN}[0]{RESET} Exit HUD Console\n")

        choice = input(f"{BOLD}{MAGENTA}quantum-flex > {RESET}").strip()
        if choice == "1":
            q = input(f"\n{BOLD}Enter query for Athena:{RESET} ").strip()
            if q:
                cmd_ask_athena(q)
            input(f"{DIM}Press Enter to continue...{RESET}")
        elif choice == "2":
            d = input(f"\n{BOLD}Enter directive to orchestrate:{RESET} ").strip()
            if d:
                cmd_dispatch_directive(d)
            input(f"{DIM}Press Enter to continue...{RESET}")
        elif choice == "3":
            cmd_wealth_status()
            input(f"{DIM}Press Enter to continue...{RESET}")
        elif choice == "4":
            cmd_pqc_status()
            input(f"{DIM}Press Enter to continue...{RESET}")
        elif choice == "5":
            confirm = input(f"{YELLOW}Confirm rotation of all secrets to new 140-bit tokens? (y/N): {RESET}").strip().lower()
            if confirm == "y":
                cmd_rotate_credentials()
            input(f"{DIM}Press Enter to continue...{RESET}")
        elif choice == "6":
            cmd_start_stack()
            input(f"{DIM}Press Enter to continue...{RESET}")
        elif choice == "7":
            cmd_start_n8n()
            input(f"{DIM}Press Enter to continue...{RESET}")
        elif choice == "8":
            cmd_backup_vault()
            input(f"{DIM}Press Enter to continue...{RESET}")
        elif choice in ("0", "exit", "quit", "q"):
            print(f"\n{GREEN}QuantumFlex HUD session closed. State invariant.{RESET}\n")
            break
        else:
            print(f"{RED}Invalid selection.{RESET}")
            time.sleep(1)

def main():
    if len(sys.argv) < 2:
        interactive_hud()
        return

    cmd = sys.argv[1].lower()
    if cmd in ("status", "health", "vitals"):
        print_banner()
        check_service_health()
    elif cmd in ("ask", "athena", "query"):
        if len(sys.argv) < 3:
            print("Usage: python qflex.py ask \"<your question>\"")
        else:
            cmd_ask_athena(" ".join(sys.argv[2:]))
    elif cmd in ("claw", "directive", "task", "orchestrate"):
        if len(sys.argv) < 3:
            print("Usage: python qflex.py claw \"<your directive>\"")
        else:
            cmd_dispatch_directive(" ".join(sys.argv[2:]))
    elif cmd in ("pqc", "crypto", "kem"):
        cmd_pqc_status()
    elif cmd in ("wealth", "depin", "yield"):
        cmd_wealth_status()
    elif cmd in ("rotate", "vault"):
        cmd_rotate_credentials()
    elif cmd in ("start", "up"):
        cmd_start_stack()
    elif cmd in ("n8n", "automation"):
        cmd_start_n8n()
    elif cmd in ("backup", "save", "archive"):
        cmd_backup_vault()
    else:
        print("""
QuantumFlex Unified Command Console
Usage:
  python qflex.py                - Open interactive Cyberpunk HUD
  python qflex.py status         - Check health of all biological strata
  python qflex.py ask "<query>"  - Interrogate Athena Vector Memory (athena:latest)
  python qflex.py claw "<task>"  - Decompose and queue swarm directive
  python qflex.py wealth         - View Sovereign Wealth Elevation Engine
  python qflex.py pqc            - Inspect post-quantum KEM/DSA agility status
  python qflex.py n8n            - Launch n8n Autonomous Workflow Engine
  python qflex.py backup         - Save & archive entire stack to Master Host Vault
  python qflex.py rotate         - Rotate all database and API credentials
  python qflex.py start          - Launch all node background services
""")

if __name__ == "__main__":
    main()
