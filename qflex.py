#!/home/quant/mycelium/venv/bin/python3
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
try:
    from dotenv import load_dotenv
except ImportError:
    venv_py = Path.home() / '.venv/qflex/bin/python3'
    if venv_py.exists() and sys.executable != str(venv_py):
        os.execv(str(venv_py), [str(venv_py)] + sys.argv)
    raise

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
ATHENA_URL = os.environ.get("ATHENA_URL", "http://127.0.0.1:8001")
AMARA_URL = os.environ.get("AMARA_URL", "http://127.0.0.1:8000")
OPA_URL = os.environ.get("OPA_ENDPOINT", "http://127.0.0.1:8181")
OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
MCP_URL = os.environ.get("MCP_URL", "http://127.0.0.1:9000/sse")
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
        {"name": "Open Policy Agent", "url": f"{OPA_URL}/health", "port": 8181, "stratum": "Stratum 0: PQC Gating"},
        {"name": "Amara Matrix PG", "url": None, "port": 5432, "stratum": "Stratum 1: Data Matrix"},
        {"name": "Amara Dashboard", "url": f"{AMARA_URL}/", "port": 8000, "stratum": "Stratum 3: Matrix HUD"},
        {"name": "Athena Neural RAG", "url": f"{ATHENA_URL}/health", "port": 8001, "stratum": "Stratum 3: Vector Memory"},
        {"name": "API Gateway Node", "url": "http://127.0.0.1:8080/status", "port": 8080, "stratum": "Stratum 3: Core API"},
        {"name": "Quantum Flex MCP", "url": "http://127.0.0.1:9000/sse", "port": 9000, "stratum": "Stratum 3: Model Context Protocol"},
        {"name": "Ollama LLM Runner", "url": f"{OLLAMA_URL}/api/tags", "port": 11434, "stratum": "Neural Inference (Optional)"},
    ]

    print(f"\n{BOLD}{CYAN}─── [BIOLOGICAL STRATA HEALTH VITALS] ───────────────────────────{RESET}")
    for s in services:
        if s.get("url"):
            res = http_get(s["url"])
            online = res is not None
        else:
            import socket
            try:
                with socket.create_connection(("127.0.0.1", s["port"]), timeout=1.0):
                    online = True
            except Exception:
                online = False

        if online:
            status_tag = f"{GREEN}[ONLINE]{RESET}"
            details = f"Port :{s['port']} | {s['stratum']}"
        else:
            status_tag = f"{RED}[OFFLINE]{RESET}"
            details = f"Port :{s['port']} | Not responding"
        print(f"  {status_tag} {BOLD}{s['name']:<22}{RESET} -> {details}")

    # Stratum 0 Universal Invariant Gate (R >= O)
    try:
        from sentinel.invariant_gate import evaluate_all_invariants
        inv = evaluate_all_invariants(evaluator="qflex_status")
        inv_tag = f"{GREEN}[ADMIT]{RESET}" if inv["all_allowed"] else f"{RED}[DENY]{RESET}"
        print(f"  {inv_tag} {BOLD}{'Universal Invariant':<22}{RESET} -> Stratum 0: R >= O (Digital RAM, TPM 2.0, Water)")
    except Exception as e:
        print(f"  {YELLOW}[CHECK]{RESET} {BOLD}{'Universal Invariant':<22}{RESET} -> OPA sidecar (:8181) pending evaluation ({e})")

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
    """Read-only capability/configuration report; never a compliance attestation."""
    def probe(*args):
        try:
            result = subprocess.run(["openssl", *args], capture_output=True, text=True, timeout=5)
            return result.stdout if result.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired):
            return None

    print("\nQuantumFlex cryptographic posture")
    print("\n[1] Host provider capabilities (this probe process only)")
    version = probe("version")
    print("OpenSSL:", version.strip() if version else "UNKNOWN")
    algorithms = probe("list", "-kem-algorithms", "-provider", "default", "-propquery", "provider=default")
    capability = "UNKNOWN" if algorithms is None else ("AVAILABLE" if "ML-KEM-768" in algorithms else "UNAVAILABLE")
    print("Default-provider ML-KEM-768:", capability)
    providers = probe("list", "-providers")
    fips_loaded = providers is not None and any(line.strip() == "fips" for line in providers.splitlines())
    print("FIPS provider in probe:", "UNKNOWN" if providers is None else ("LOADED" if fips_loaded else "NOT LISTED"))
    print("FIPS 140-3 validation: NOT ESTABLISHED; module certificate and approved operating conditions require verification.")

    print("\n[2] Configured policy (running daemon not inspected)")
    profile = os.environ.get("PQC_COMPLIANCE_PROFILE", "fips_strict")
    print("Profile from this environment/default:", profile)
    print("Daemon --profile can override this value.")
    if profile == "fips_strict":
        print("Strict fallback: NONE on compromise, denial, or unavailable policy; no ML-KEM parameter downgrade.")
    elif profile in ("agility", "iso_strict"):
        print("Research/agility fallback enabled; this is not a FIPS validation claim.")
    else:
        print("INVALID profile; daemon startup rejects this value.")
    conf_path = Path(os.environ.get("PQC_PROVIDER_CONF", str(ROOT_DIR / "mcp_layer" / "crypto_provider.conf")))
    print("Configuration file:", conf_path)
    if conf_path.is_file():
        for line in conf_path.read_text().splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip() in ("active_kem", "active_sig"):
                print(f"Configured {key.strip()}: {value.strip()} (not a negotiated-session measurement)")
    else:
        print("Configuration unavailable")

    print("\n[3] C++ source implementation (running binary not inspected)")
    print("IPC KEM: native OpenSSL ML-KEM-768; message types 0x12/0x13/0x14.")
    print("Legacy Frodo + X25519: research code only; legacy KEM requests are rejected by migrated IPC.")
    print("KEM exchange returns a confirmation tag, never the shared secret. Existing transport remains mTLS.")
    print("Provider selection follows OpenSSL configuration and QF_KEM_PROPERTIES; validation is not inferred.")
    print("Deployment, traffic enforcement, and test results: NOT VERIFIED by this command.\n")

def cmd_invariant_status():
    """Evaluates the Universal Reserve Invariant (R >= O) across Digital and Physical Strata."""
    try:
        from sentinel.invariant_gate import evaluate_all_invariants
        res = evaluate_all_invariants(evaluator="qflex_hud")
        all_ok = res["all_allowed"]
        color = GREEN if all_ok else RED
        print(f"\n{BOLD}{CYAN}╔═══════════════════════════════════════════════════════════════════════╗{RESET}")
        print(f"{BOLD}{CYAN}║     QUANTUM FLEX: UNIVERSAL INVARIANT GATE (R >= O) HUD               ║{RESET}")
        print(f"{BOLD}{CYAN}╚═══════════════════════════════════════════════════════════════════════╝{RESET}")
        print(f"  Overall Verdict: {color}{BOLD}[{res['overall_verdict']}]{RESET}")
        print(f"  Policy Engine  : Open Policy Agent (:8181/v1/data/quantumflex/invariant)")
        print(f"  Audit Ledger   : PostgreSQL telemetry.invariant_audit_ledger\n")

        for name, ev in res["evaluations"].items():
            ev_col = GREEN if ev["allowed"] else RED
            p = ev["payload"]
            print(f"  {BOLD}▶ {name.upper()}{RESET} [{ev_col}{ev['verdict']}{RESET}]")
            print(f"    Detail   : {ev['reason']}")
            print(f"    Measured : {p.get('reserve_measured')} (R)")
            print(f"    Claimed  : {p.get('units_claimed')} (O)")
            if p.get('requested_delta'):
                print(f"    Delta    : {p.get('requested_delta')}")
        print(f"\n{BOLD}{CYAN}───────────────────────────────────────────────────────────────────────{RESET}\n")
    except Exception as e:
        print(f"{RED}[!] Failed to evaluate invariant gate: {e}{RESET}\n")

def cmd_rotate_credentials():
    """Executes CSPRNG credential rotation and entropy audit."""
    rot_script = ROOT_DIR / "tools" / "rotate_credentials.py"
    if rot_script.exists():
        subprocess.run([sys.executable, str(rot_script), "--rotate"])
    else:
        print(f"{RED}[!] rotate_credentials.py missing.{RESET}\n")

QF_SERVICES = [
    "amara-matrix.service",
    "opa-immune.service",
    "ollama.service",
    "immune-daemon.service",
    "amara-dashboard.service",
    "athena-node.service",
    "api-node.service",
    "qflex-mcp.service",
    "qf-monitor.service",
    "swarm-worker.service",
    "active-defense.service",
    "sentinel-drive.timer",
    "amara-predict.timer",
    "neurogenesis.timer",
]

def cmd_start_stack():
    """Launches full biological stack via systemd user units."""
    print(f"{BOLD}[*] Launching QuantumFlex biological stack via systemd user units...{RESET}")
    subprocess.run(["systemctl", "--user", "start"] + QF_SERVICES)
    time.sleep(2)
    check_service_health()

def cmd_stop_stack():
    """Stops all QuantumFlex services."""
    print(f"{BOLD}[*] Stopping QuantumFlex biological stack...{RESET}")
    subprocess.run(["systemctl", "--user", "stop"] + QF_SERVICES)
    time.sleep(1)
    check_service_health()

def cmd_restart_stack():
    """Restarts full biological stack."""
    print(f"{BOLD}[*] Restarting QuantumFlex biological stack...{RESET}")
    subprocess.run(["systemctl", "--user", "restart"] + QF_SERVICES)
    time.sleep(2)
    check_service_health()

def cmd_start_n8n():
    """Launches n8n workflow engine via Podman."""
    print(f"{BOLD}[*] Launching n8n Autonomous Workflow Engine via Podman...{RESET}")
    subprocess.run([
        "podman", "run", "-d",
        "--name", "qflex-n8n",
        "-p", "127.0.0.1:5678:5678",
        "-v", "qflex_n8n_data:/home/node/.n8n",
        "--restart", "unless-stopped",
        "docker.n8n.io/n8nio/n8n"
    ])
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
        print(f"  {CYAN}[6]{RESET} Start / Restart Full Biological Stack (Systemd)")
        print(f"  {CYAN}[7]{RESET} Stop Full Biological Stack")
        print(f"  {CYAN}[8]{RESET} Backup Master Host Vault (~/QuantumFlex_Master_Vault)")
        print(f"  {CYAN}[9]{RESET} Universal Invariant Gate (R >= O HUD)")
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
            cmd_restart_stack()
            input(f"{DIM}Press Enter to continue...{RESET}")
        elif choice == "7":
            cmd_stop_stack()
            input(f"{DIM}Press Enter to continue...{RESET}")
        elif choice == "8":
            cmd_backup_vault()
            input(f"{DIM}Press Enter to continue...{RESET}")
        elif choice == "9":
            cmd_invariant_status()
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
    elif cmd in ("invariant", "gate", "solvency", "reserve"):
        cmd_invariant_status()
    elif cmd in ("pqc", "crypto", "kem"):
        cmd_pqc_status()
    elif cmd in ("rotate", "vault"):
        cmd_rotate_credentials()
    elif cmd in ("start", "up"):
        cmd_start_stack()
    elif cmd in ("stop", "down"):
        cmd_stop_stack()
    elif cmd in ("restart", "reload"):
        cmd_restart_stack()
    elif cmd in ("n8n", "automation"):
        cmd_start_n8n()
    elif cmd in ("backup", "save", "archive"):
        cmd_backup_vault()
    else:
        print("""
QuantumFlex Unified Command Console
Usage:
  python qflex.py                - Open interactive HUD
  python qflex.py status         - Check health of strata
  python qflex.py ask "<query>"  - Interrogate Athena Vector Memory (athena:latest)
  python qflex.py claw "<task>"  - Decompose and queue swarm directive
  python qflex.py invariant      - Evaluate Universal Invariant Gate (R >= O)
  python qflex.py pqc            - Inspect post-quantum KEM/DSA agility status
  python qflex.py n8n            - Launch n8n Autonomous Workflow Engine
  python qflex.py backup         - Save & archive entire stack to Master Host Vault
  python qflex.py rotate         - Rotate all database and API credentials
  python qflex.py start          - Launch all node background services
""")

if __name__ == "__main__":
    main()
