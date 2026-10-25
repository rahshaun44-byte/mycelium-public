#!/usr/bin/env python3
"""
QuantumFlex Sovereign Multi-Agent Interactive Terminal & Ollama Companion
========================================================================
Interactive terminal companion to interrogate the local Ollama neural swarm:
- ATHENA  : Cognitive vector memory & blueprint RAG
- SENTINEL: Perimeter defense, TPM 2.0 anchor & invariant gate
- MYCELIA : WireGuard P2P mesh & node reachability
- ARIA    : Sovereign executive assistant & orchestration

Usage:
  python3 scripts/qf_chat.py                       # Launch interactive console
  python3 scripts/qf_chat.py athena "<prompt>"    # Single-shot query to Athena
  python3 scripts/qf_chat.py sentinel "<prompt>"  # Single-shot query to Sentinel
  python3 scripts/qf_chat.py mycelia "<prompt>"   # Single-shot query to Mycelia
  python3 scripts/qf_chat.py aria "<prompt>"      # Single-shot query to Aria
"""

import os
import sys
import json
import urllib.request
import urllib.error
from typing import Optional, Dict, Any

# ANSI Colors
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[0;36m"
GREEN = "\033[0;32m"
YELLOW = "\033[0;33m"
RED = "\033[0;31m"
MAGENTA = "\033[0;35m"
WHITE = "\033[1;37m"
RESET = "\033[0m"

QF_BOT_URL = os.environ.get("QF_BOT_URL", "http://127.0.0.1:9001")
OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")

AGENTS = {
    "athena": {"name": "ATHENA", "avatar": "🧠", "color": CYAN, "desc": "Cognitive Vector Memory & Blueprint RAG Oracle"},
    "amara": {"name": "AMARA", "avatar": "⚡", "color": MAGENTA, "desc": "Biological System Monitor & Autonomous Engine"},
    "sentinel": {"name": "SENTINEL", "avatar": "▲", "color": RED, "desc": "Perimeter Defense & Invariant Gate"},
    "cs320": {"name": "CS320", "avatar": "🎓", "color": GREEN, "desc": "SNHU Coursework, Java QA & Test Automation Coach"},
    "all": {"name": "ALL UNITS", "avatar": "⬡", "color": YELLOW, "desc": "Swarm Broadcaster & Auto-Router"},
}


def query_qf_bot(message: str, target_bot: Optional[str] = None) -> Dict[str, Any]:
    """Dispatches query to local QF-Bot server on loopback port 9001."""
    url = f"{QF_BOT_URL}/api/chat"
    payload = json.dumps({"message": message, "target_bot": target_bot or ""}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        # Fallback to direct Ollama if QF-Bot server is not running
        return query_ollama_fallback(message, target_bot)


def query_ollama_fallback(message: str, target_bot: Optional[str] = None) -> Dict[str, Any]:
    """Direct query to local Ollama if QF-Bot service is offline."""
    if target_bot == "athena":
        model = "athena:latest"
    elif target_bot in ["amara", "aria"]:
        model = "amara:latest"
    elif target_bot in ["cs320", "tutor"]:
        model = "cs320-tutor:latest"
    else:
        model = "qwen2.5-coder:7b"
    url = f"{OLLAMA_URL}/api/generate"
    payload = json.dumps({"model": model, "prompt": message, "stream": False}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {
                "bot": {"name": (target_bot or "Ollama").upper(), "avatar": "🤖", "callsign": target_bot or "ollama"},
                "response": data.get("response", "").strip(),
                "mode": "ollama_direct"
            }
    except Exception as e:
        return {
            "bot": {"name": "ERROR", "avatar": "⚠️", "callsign": "error"},
            "response": f"[!] Error reaching Ollama on {OLLAMA_URL}: {e}",
            "mode": "error"
        }


def print_banner():
    print(f"{BOLD}{CYAN}═══════════════════════════════════════════════════════════════{RESET}")
    print(f"{BOLD}{WHITE}  QUANTUMFLEX SOVEREIGN NEURAL TERMINAL  •  LOCAL OLLAMA{RESET}")
    print(f"{DIM}  Airgapped Inference on Local AMD Ryzen Silicon (127.0.0.1:11434){RESET}")
    print(f"{BOLD}{CYAN}═══════════════════════════════════════════════════════════════{RESET}")
    print(f"  {BOLD}Available Agents:{RESET}")
    for k, v in AGENTS.items():
        print(f"    {v['color']}{v['avatar']} {v['name']:<10}{RESET} : {v['desc']}")
    print(f"  {BOLD}Control Commands:{RESET}")
    print(f"    {YELLOW}/switch <agent>{RESET} : Switch target agent (athena, sentinel, mycelia, aria, all)")
    print(f"    {YELLOW}/models{RESET}        : List active models in Ollama")
    print(f"    {YELLOW}/status{RESET}        : View cluster telemetry & mesh status")
    print(f"    {YELLOW}/exit{RESET}          : Exit session")
    print(f"{BOLD}{CYAN}═══════════════════════════════════════════════════════════════{RESET}\n")


def cmd_list_models():
    url = f"{OLLAMA_URL}/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = data.get("models", [])
            print(f"\n{BOLD}{CYAN}── Active Ollama Models ({len(models)}) ──────────────────────────────{RESET}")
            for m in models:
                size_gb = m.get("size", 0) / (1024 ** 3)
                print(f"  • {BOLD}{m.get('name'):<26}{RESET} {size_gb:.2f} GB  (modified: {m.get('modified_at', '')[:10]})")
            print()
    except Exception as e:
        print(f"{RED}[!] Failed to query Ollama models: {e}{RESET}\n")


def interactive_loop():
    print_banner()
    current_agent = "athena"

    while True:
        info = AGENTS[current_agent]
        prompt_label = f"{info['color']}[{info['avatar']} {info['name']}]{RESET} {BOLD}>>{RESET} "

        try:
            user_input = input(prompt_label).strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{DIM}[*] Session closed.{RESET}")
            break

        if not user_input:
            continue

        if user_input in ["/exit", "exit", "quit", ":q"]:
            print(f"{DIM}[*] Disconnecting from sovereign neural terminal.{RESET}")
            break

        if user_input.startswith("/switch"):
            parts = user_input.split()
            if len(parts) > 1 and parts[1].lower() in AGENTS:
                current_agent = parts[1].lower()
                print(f"{GREEN}[+] Switched to {AGENTS[current_agent]['avatar']} {AGENTS[current_agent]['name']}{RESET}\n")
            else:
                print(f"{YELLOW}[?] Specify one of: {', '.join(AGENTS.keys())}{RESET}\n")
            continue

        if user_input == "/models":
            cmd_list_models()
            continue

        if user_input in ["/status", "status"]:
            user_input = "sitrep"

        # Dispatch query
        target = "" if current_agent == "all" else current_agent
        print(f"{DIM}Thinking on local silicon...{RESET}", end="\r", flush=True)

        res = query_qf_bot(user_input, target_bot=target)
        bot = res.get("bot", {})
        resp_text = res.get("response", "")
        avatar = bot.get("avatar", "🤖")
        callsign = bot.get("callsign", current_agent).upper()

        # Clear the "Thinking..." line
        print(" " * 40, end="\r", flush=True)
        print(f"\n{BOLD}{CYAN}┌─── [{avatar} {callsign}] ────────────────────────────────────{RESET}")
        print(f"{WHITE}{resp_text}{RESET}")
        print(f"{BOLD}{CYAN}└─────────────────────────────────────────────────────────────{RESET}\n")


def main():
    if len(sys.argv) > 2:
        target = sys.argv[1].lower()
        if target not in AGENTS and target != "all":
            prompt = " ".join(sys.argv[1:])
            target = "athena"
        else:
            prompt = " ".join(sys.argv[2:])

        print(f"{DIM}[*] Dispatching to [{target.upper()}] on local silicon...{RESET}", end="\r", flush=True)
        res = query_qf_bot(prompt, target_bot=target)
        bot = res.get("bot", {})
        print(" " * 60, end="\r", flush=True)
        print(f"\n{BOLD}{CYAN}[{bot.get('avatar', '🤖')} {bot.get('name', target.upper())}]:{RESET}\n{res.get('response', '')}\n")
    elif len(sys.argv) == 2 and sys.argv[1] not in ["-h", "--help"]:
        prompt = sys.argv[1]
        print(f"{DIM}[*] Dispatching to [ATHENA] on local silicon...{RESET}", end="\r", flush=True)
        res = query_qf_bot(prompt, target_bot="athena")
        print(" " * 60, end="\r", flush=True)
        print(f"\n{BOLD}{CYAN}[🧠 ATHENA]:{RESET}\n{res.get('response', '')}\n")
    else:
        interactive_loop()


if __name__ == "__main__":
    main()
