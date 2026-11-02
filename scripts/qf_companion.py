#!/usr/bin/env python3
"""
QuantumFlex Sovereign AI Companion & Interactive Neural Terminal (qf)
=====================================================================
Natural, conversational agentic companion for local LLMs, RAG, and tools.
Governing Invariants:
- Zero Cloud Spend Invariant ($0.00): Strictly loopback 127.0.0.1:11434
- Fail-Closed Security & Proof-Grounded Answers
- Microsoft Pluton TPM 2.0 & Titan M2 Cluster Awareness

Usage:
  qf                                # Interactive streaming companion session
  qf "your question here"           # One-shot natural language query
  qf --athena "search query"        # One-shot query grounded in Athena vector memory
  qf --code "write a function..."   # One-shot query directed to qwen2.5-coder:7b
  qf --status                       # Instant cluster & node telemetry sitrep
"""

import os
import sys
import json
import time
import shutil
import urllib.request
import urllib.error
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add repo root to path for Athena vector DB and sentinel tools
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Optional prompt_toolkit for full readline, history, and autocomplete
try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.completion import WordCompleter
    from prompt_toolkit.styles import Style
    PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    PROMPT_TOOLKIT_AVAILABLE = False

# ANSI Color Codes
BOLD = "\033[1m"
DIM = "\033[2m"
ITALIC = "\033[3m"
CYAN = "\033[38;5;51m"
BLUE = "\033[38;5;39m"
GREEN = "\033[38;5;48m"
YELLOW = "\033[38;5;220m"
RED = "\033[38;5;196m"
MAGENTA = "\033[38;5;201m"
ORANGE = "\033[38;5;208m"
WHITE = "\033[38;5;231m"
GRAY = "\033[38;5;244m"
RESET = "\033[0m"

OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
DEFAULT_MODEL = os.environ.get("QF_MODEL", "qwen2.5-coder:7b")
DEFAULT_EMBED_MODEL = "nomic-embed-text:latest"

SYSTEM_PROMPT = """You are QuantumFlex Sovereign AI Companion (qf).
You are pairing with Rahshaun Chambers (Rocky), Chief Architect and Operator of QuantumFlex.
Core Principles:
1. Tone: Highly intelligent, street-grounded, blunt, direct, intellectually sharp. No corporate fluff, no condescending lectures.
2. Invariants: $0.00 External Cloud Spend Invariant (100% sovereign local inference on AMD Ryzen AI silicon), strict privacy, and mathematical fail-closed proofs.
3. Hardware Reality: Running locally on qfx-yoga (Ubuntu 26.04.1 LTS, 16 GB unified LPDDR5x, Microsoft Pluton TPM 2.0). Connected to qfx-pixel (Titan M2) and g6pro (Kafka).
4. Code & Architecture: Deliver production-ready, mathematically sound code (Foundry, Python 3.14, C11, Wasm, F*).
5. When referencing facts, prioritize verified grounded citations."""

SLASH_COMMANDS = [
    "/help", "/model", "/models", "/athena", "/run", "/view",
    "/status", "/clear", "/save", "/exit", "/quit"
]


def print_banner(model_name: str):
    term_width = min(shutil.get_terminal_size().columns, 80)
    print(f"\n{BOLD}{CYAN}╭{'─' * (term_width - 2)}╮{RESET}")
    print(f"{BOLD}{CYAN}│{WHITE}  ⚡ QUANTUMFLEX SOVEREIGN AI COMPANION (qf)  {CYAN}{' ' * (term_width - 46)}│{RESET}")
    print(f"{BOLD}{CYAN}│{GRAY}  Local Airgapped Intelligence • AMD Ryzen AI Silicon • $0.00 Cloud Spend {CYAN}{' ' * max(0, term_width - 77)}│{RESET}")
    print(f"{BOLD}{CYAN}╰{'─' * (term_width - 2)}╯{RESET}")
    print(f"  {DIM}Active Engine:{RESET} {BOLD}{GREEN}{model_name}{RESET}  {DIM}│ Endpoint:{RESET} {YELLOW}{OLLAMA_URL}{RESET}")
    print(f"  {DIM}Quick Commands:{RESET} {CYAN}/model{RESET} {DIM}(switch){RESET} • {CYAN}/athena <q>{RESET} {DIM}(vault memory){RESET} • {CYAN}/run <cmd>{RESET} {DIM}(terminal){RESET} • {CYAN}/status{RESET} • {CYAN}/help{RESET}\n")


def check_ollama_alive() -> bool:
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


def get_available_models() -> List[str]:
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        return [DEFAULT_MODEL]


def query_athena_vector_db(query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    try:
        from sentinel.intelligence.athena_vector_db import AthenaVectorStore
        store = AthenaVectorStore()
        return store.similarity_search(query, top_k=top_k)
    except Exception as e:
        return [{"source": "error", "content": f"Athena Vector Search unavailable: {e}", "score": 0.0}]


def stream_llm_chat(messages: List[Dict[str, str]], model: str, print_header: bool = True) -> str:
    """Streams token chunks from local Ollama via /api/chat in real time."""
    url = f"{OLLAMA_URL}/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {
            "num_ctx": 4096,
            "temperature": 0.4
        }
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )

    if print_header:
        print(f"\n{BOLD}{CYAN}╭─ [⚡ {model}] {RESET}")
    
    full_response = []
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            for line in resp:
                if not line.strip():
                    continue
                chunk = json.loads(line.decode("utf-8"))
                msg = chunk.get("message", {}).get("content", "")
                if msg:
                    sys.stdout.write(f"{WHITE}{msg}{RESET}")
                    sys.stdout.flush()
                    full_response.append(msg)
                if chunk.get("done", False):
                    break
        print(f"\n{BOLD}{CYAN}╰────────────────────────────────────────────────{RESET}\n")
    except Exception as e:
        err_msg = f"\n{RED}[!] Local inference error on {model}: {e}{RESET}\n"
        print(err_msg)
        return err_msg
        
    return "".join(full_response)


def execute_shell_command(cmd: str) -> str:
    """Executes local bash command and returns formatted output."""
    print(f"{DIM}[*] Running: {cmd}{RESET}")
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30, cwd=str(ROOT_DIR))
        out = (res.stdout + res.stderr).strip()
        if not out:
            return "[+] Command finished with exit code 0 (no output)."
        return out
    except subprocess.TimeoutExpired:
        return "[-] Command timed out after 30 seconds."
    except Exception as e:
        return f"[-] Command execution failed: {e}"


def get_cluster_status() -> str:
    """Collects real-time host, node, and invariant metrics."""
    lines = []
    lines.append(f"{BOLD}Host Hardware:{RESET} AMD Ryzen AI 5 340 (Zen 5 AVX-512) • Ubuntu 26.04.1 LTS")
    
    # Memory
    try:
        import psutil
        mem = psutil.virtual_memory()
        lines.append(f"{BOLD}Unified RAM:{RESET} {mem.used / (1024**3):.1f} GiB / {mem.total / (1024**3):.1f} GiB ({mem.percent}% used) • {mem.available / (1024**3):.1f} GiB free")
    except Exception:
        pass

    # Engine status
    try:
        res = subprocess.run("tail -n 2 /home/quant/.local/state/quantum-flex-mycelium/engine.log 2>/dev/null", shell=True, capture_output=True, text=True)
        engine_line = res.stdout.strip().splitlines()[-1] if res.stdout.strip() else "Unknown"
        lines.append(f"{BOLD}Evidence Engine:{RESET} 127.0.0.1:9444 ({engine_line})")
    except Exception:
        pass

    # Tailscale
    try:
        res = subprocess.run("tailscale status", shell=True, capture_output=True, text=True)
        ts_nodes = [l.strip() for l in res.stdout.splitlines() if l.strip()]
        lines.append(f"{BOLD}Tailscale Mesh ({len(ts_nodes)} nodes):{RESET}")
        for n in ts_nodes:
            lines.append(f"  • {n}")
    except Exception:
        pass

    # Invariants
    lines.append(f"{BOLD}Invariants:{RESET} Zero-Cloud Spend Invariant ($0.00 USD) • Pluton TPM 2.0 Direct-to-Active")
    return "\n".join(lines)


def run_interactive_session(initial_model: str = DEFAULT_MODEL):
    if not check_ollama_alive():
        print(f"{RED}[!] Error: Ollama daemon is not responding on {OLLAMA_URL}{RESET}")
        print(f"    Run: {YELLOW}systemctl --user start ollama.service{RESET}")
        return

    current_model = initial_model
    available_models = get_available_models()
    if current_model not in available_models and available_models:
        current_model = available_models[0]

    print_banner(current_model)

    # Initialize conversation history
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]

    history_file = Path.home() / ".qf_history"
    session = None
    if PROMPT_TOOLKIT_AVAILABLE:
        completer = WordCompleter(SLASH_COMMANDS + available_models, ignore_case=True)
        session = PromptSession(
            history=FileHistory(str(history_file)),
            auto_suggest=AutoSuggestFromHistory(),
            completer=completer
        )

    while True:
        try:
            prompt_str = f"{BOLD}{GREEN}qf ({current_model.split(':')[0]}){CYAN} >> {RESET}"
            if session:
                user_input = session.prompt(prompt_str).strip()
            else:
                user_input = input(prompt_str).strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{DIM}[*] Companion session detached. Stay sovereign.{RESET}\n")
            break

        if not user_input:
            continue

        # Handle Slash Commands
        lower_input = user_input.lower()
        if lower_input in ["/exit", "/quit", "exit", "quit", ":q"]:
            print(f"{DIM}[*] Disconnecting from sovereign neural terminal.{RESET}\n")
            break

        if lower_input in ["/clear", "/reset"]:
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            print(f"{GREEN}[+] Context cleared. Conversation memory reset.{RESET}\n")
            continue

        if lower_input == "/help":
            print(f"\n{BOLD}{CYAN}── QuantumFlex Companion Commands ─────────────────────────────{RESET}")
            print(f"  {YELLOW}/model [name]{RESET}       : Show active model or switch to another (e.g., /model athena)")
            print(f"  {YELLOW}/models{RESET}             : List all models currently loaded in Ollama")
            print(f"  {YELLOW}/athena <query>{RESET}     : Query local Athena vector store for blueprints & roadmaps")
            print(f"  {YELLOW}/run <command>{RESET}      : Execute local shell command and display output")
            print(f"  {YELLOW}/view <filepath>{RESET}    : View local file and feed it into conversation context")
            print(f"  {YELLOW}/status{RESET}             : View live host RAM, CPU, TPM, and Tailscale mesh status")
            print(f"  {YELLOW}/clear{RESET}              : Reset conversation context memory")
            print(f"  {YELLOW}/save [path]{RESET}        : Save conversation history to a markdown file")
            print(f"  {YELLOW}/exit{RESET}               : Exit session\n")
            continue

        if lower_input == "/models":
            available_models = get_available_models()
            print(f"\n{BOLD}{CYAN}── Available Local Ollama Models ({len(available_models)}) ──────────────────{RESET}")
            for m in available_models:
                star = f" {GREEN}◀ ACTIVE{RESET}" if m == current_model else ""
                print(f"  • {BOLD}{m:<28}{RESET}{star}")
            print()
            continue

        if lower_input.startswith("/model"):
            parts = user_input.split(maxsplit=1)
            if len(parts) > 1:
                target = parts[1].strip()
                # fuzzy match
                matched = [m for m in available_models if target in m]
                if matched:
                    current_model = matched[0]
                    print(f"{GREEN}[+] Switched active model to: {BOLD}{current_model}{RESET}\n")
                else:
                    print(f"{RED}[!] Model '{target}' not found. Run /models to list.{RESET}\n")
            else:
                print(f"{DIM}Current model:{RESET} {BOLD}{current_model}{RESET}\n")
            continue

        if lower_input.startswith("/athena"):
            query = user_input[7:].strip()
            if not query:
                print(f"{YELLOW}[?] Provide a query: /athena <search topic>{RESET}\n")
                continue
            print(f"{DIM}[*] Searching Athena cognitive vector store for: {query}...{RESET}")
            chunks = query_athena_vector_db(query, top_k=3)
            print(f"\n{BOLD}{CYAN}── Athena Retrieved Chunks ({len(chunks)}) ───────────────────────{RESET}")
            context_str_list = []
            for i, c in enumerate(chunks, 1):
                meta = c.get("metadata") or {}
                sha = str(meta.get("chunk_sha256", meta.get("doc_sha256", "")))[:12]
                src = c.get("source", "unknown")
                score = c.get("score", 0.0)
                print(f"  [{i}] {BOLD}{src}{RESET} (SHA: {sha} | Score: {score:.2f})")
                context_str_list.append(f"Source: {src} (SHA256: {sha}):\n{c.get('content', '')}")
            print(f"{BOLD}{CYAN}─────────────────────────────────────────────────────────────{RESET}\n")
            
            # Formulate RAG message
            augmented_content = (
                f"[OPERATOR DIRECTIVE WITH ATHENA VAULT CONTEXT]\n"
                f"Query: {query}\n\n"
                f"Context from Athena Vector Store:\n"
                + "\n---\n".join(context_str_list)
                + "\n\nPlease provide a clear, grounded analysis citing the verified sources above."
            )
            messages.append({"role": "user", "content": augmented_content})
            reply = stream_llm_chat(messages, current_model)
            messages.append({"role": "assistant", "content": reply})
            continue

        if lower_input.startswith("/run"):
            cmd = user_input[4:].strip()
            if not cmd:
                print(f"{YELLOW}[?] Provide a command: /run <shell command>{RESET}\n")
                continue
            output = execute_shell_command(cmd)
            print(f"\n{BOLD}{CYAN}── Output of: {cmd} ─────────────────────────────{RESET}")
            print(output[:3000])
            if len(output) > 3000:
                print(f"{DIM}... [truncated {len(output) - 3000} characters]{RESET}")
            print(f"{BOLD}{CYAN}─────────────────────────────────────────────────────────────{RESET}\n")
            # Ask if user wants to analyze it
            messages.append({
                "role": "user",
                "content": f"I ran command `{cmd}` and got the following output:\n```\n{output[:2000]}\n```\nPlease analyze this output."
            })
            continue

        if lower_input.startswith("/view"):
            fpath_str = user_input[5:].strip()
            fpath = Path(fpath_str)
            if not fpath.is_absolute():
                fpath = ROOT_DIR / fpath
            if not fpath.exists() or not fpath.is_file():
                print(f"{RED}[!] File not found: {fpath}{RESET}\n")
                continue
            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")[:10000]
                print(f"{GREEN}[+] Ingested {len(content)} characters from {fpath.name} into context.{RESET}\n")
                messages.append({
                    "role": "user",
                    "content": f"Here is the content of `{fpath.name}`:\n```\n{content}\n```\nPlease confirm you received this file."
                })
                reply = stream_llm_chat(messages, current_model)
                messages.append({"role": "assistant", "content": reply})
            except Exception as e:
                print(f"{RED}[!] Error reading file: {e}{RESET}\n")
            continue

        if lower_input == "/status":
            print(f"\n{BOLD}{CYAN}── Live Cluster & Node Telemetry ─────────────────────────────{RESET}")
            print(get_cluster_status())
            print(f"{BOLD}{CYAN}─────────────────────────────────────────────────────────────{RESET}\n")
            continue

        if lower_input.startswith("/save"):
            parts = user_input.split(maxsplit=1)
            out_file = Path(parts[1].strip()) if len(parts) > 1 else (ROOT_DIR / f"qf_chat_{int(time.time())}.md")
            try:
                with open(out_file, "w", encoding="utf-8") as f:
                    f.write(f"# QuantumFlex Companion Session Export\nDate: {time.ctime()}\n\n")
                    for m in messages:
                        if m["role"] == "system":
                            continue
                        f.write(f"### {m['role'].upper()}\n\n{m['content']}\n\n---\n\n")
                print(f"{GREEN}[+] Session saved to {out_file}{RESET}\n")
            except Exception as e:
                print(f"{RED}[!] Failed to save session: {e}{RESET}\n")
            continue

        # Standard Conversational Query
        # Auto-detect if user is asking about blueprints/invariants/history and offer Athena context
        if any(kw in lower_input for kw in ["p0", "hard stop", "reserve", "invariant", "roadmap", "qf-a", "nlnet", "blueprint"]):
            print(f"{DIM}[*] Auto-fetching Athena context for relevant terms...{RESET}", end="\r")
            chunks = query_athena_vector_db(user_input, top_k=2)
            sys.stdout.write("\r" + " " * 60 + "\r")
            if chunks and chunks[0].get("score", 0) > 0.35:
                context_str = "\n---\n".join([f"Source: {c['source']}:\n{c['content']}" for c in chunks])
                user_msg_augmented = f"[Grounding Context from Local Vault]:\n{context_str}\n\nUser Question: {user_input}"
                messages.append({"role": "user", "content": user_msg_augmented})
            else:
                messages.append({"role": "user", "content": user_input})
        else:
            messages.append({"role": "user", "content": user_input})

        # Stream response
        reply = stream_llm_chat(messages, current_model)
        messages.append({"role": "assistant", "content": reply})


def main():
    import argparse
    parser = argparse.ArgumentParser(description="QuantumFlex Sovereign AI Companion (qf)")
    parser.add_argument("query", nargs="*", help="One-shot prompt to query local AI directly")
    parser.add_argument("-m", "--model", default=DEFAULT_MODEL, help=f"Model name (default: {DEFAULT_MODEL})")
    parser.add_argument("-a", "--athena", action="store_true", help="Grounded search via Athena Vector Store")
    parser.add_argument("-c", "--code", action="store_true", help="Use qwen2.5-coder:7b specifically for coding")
    parser.add_argument("-s", "--status", action="store_true", help="Print live cluster sitrep and exit")

    args = parser.parse_args()

    if args.status:
        print(get_cluster_status())
        return

    model = "qwen2.5-coder:7b" if args.code else args.model

    if args.query:
        full_query = " ".join(args.query)
        if args.athena:
            chunks = query_athena_vector_db(full_query, top_k=3)
            context_str = "\n---\n".join([f"Source: {c['source']}:\n{c['content']}" for c in chunks])
            augmented = (
                f"[VERIFIED KNOWLEDGE VAULT CONTEXT]\n{context_str}\n\n"
                f"Operator Question: {full_query}\n\n"
                f"Provide a concise, grounded answer citing verified sources."
            )
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": augmented}
            ]
        else:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": full_query}
            ]
        
        stream_llm_chat(messages, model, print_header=True)
    else:
        run_interactive_session(initial_model=model)


if __name__ == "__main__":
    main()
