#!/usr/bin/env python3
"""
Quantum Flex AI Teammates: Interactive Terminal Console (QF-Bot)
================================================================
Cyberpunk styled multi-agent teammate console:
- Chat with Amara, Athena, Sentinel, Immune, Claw, and Apex
- Multi-agent handoff visualizations
- Staged draft reviews with direct [y/n] approval gates
- Routine triggers and live telemetry inspections
"""

import sys
import os
import asyncio
from pathlib import Path

# Safe console rendering for Windows/Linux
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR / "mcp_layer"))

from qf_bot.orchestrator import QFBotOrchestrator
from qf_bot.routines import ROUTINE_CATALOG

# ── Cyberpunk ANSI Palette ───────────────────────────────────────────────────
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BLUE = "\033[94m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def print_banner():
    banner = f"""
{CYAN}{BOLD}╔═════════════════════════════════════════════════════════════════════╗
║   ██████╗ ███████╗    ██████╗  ██████╗ ████████╗                    ║
║  ██╔═══██╗██╔════╝    ██╔══██╗██╔═══██╗╚══██╔══╝                    ║
║  ██║   ██║█████╗      ██████╔╝██║   ██║   ██║                       ║
║  ██║▄▄ ██║██╔══╝      ██╔══██╗██║   ██║   ██║                       ║
║  ╚██████╔╝██║         ██████╔╝╚██████╔╝   ██║                       ║
║   ╚══▀▀═╝ ╚═╝         ╚═════╝  ╚═════╝    ╚═╝                       ║
║        {MAGENTA}QUANTUM FLEX AI TEAMMATES // AUTONOMOUS SWARM v1.0{CYAN}           ║
╚═════════════════════════════════════════════════════════════════════╝{RESET}
{DIM}AI teammates you can give real work to: sign in to tools, monitor telemetry,
run overnight routines, and stage draft actions for human sign-off.{RESET}
"""
    print(banner)


def print_roster_bar(roster):
    print(f"{BOLD}Active Teammates:{RESET}")
    pills = []
    for t in roster:
        pills.append(f"{t['avatar']} {BOLD}{t['name']}{RESET} ({CYAN}@{t['callsign']}{RESET})")
    print("  " + "  •  ".join(pills))
    print(f"{DIM}Type natural directives, mention @bot to target, or use /help{RESET}\n")


def print_draft_card(draft):
    risk_color = RED if draft.get("risk_level") == "CRITICAL" else YELLOW
    print(f"\n{risk_color}{BOLD}┌─────────────────────────────────────────────────────────────┐{RESET}")
    print(f"{risk_color}{BOLD}│ ⚠️  DRAFT ACTION STAGED — REQUIRES OPERATOR SIGN-OFF        │{RESET}")
    print(f"{risk_color}{BOLD}├─────────────────────────────────────────────────────────────┤{RESET}")
    print(f"│ {BOLD}Draft ID:{RESET}    {draft.get('draft_id')}  (Bot: {draft.get('bot')})")
    print(f"│ {BOLD}Title:{RESET}       {draft.get('title')}")
    print(f"│ {BOLD}Description:{RESET} {draft.get('description')}")
    print(f"│ {BOLD}Parameters:{RESET}  {draft.get('parameters')}")
    print(f"│ {BOLD}Status:{RESET}      {draft.get('status')}")
    print(f"{risk_color}{BOLD}└─────────────────────────────────────────────────────────────┘{RESET}\n")


async def main_loop():
    print_banner()
    orchestrator = QFBotOrchestrator()
    roster = orchestrator.get_roster()
    print_roster_bar(roster)

    while True:
        try:
            user_input = input(f"{GREEN}{BOLD}Operator ❯ {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{YELLOW}Terminating QF-Bot session. Homeostasis intact.{RESET}")
            break

        if not user_input:
            continue

        if user_input.lower() in ["exit", "quit", "/exit", "/quit"]:
            print(f"{YELLOW}Exiting QF-Bot console.{RESET}")
            break

        if user_input.startswith("/help"):
            print(f"\n{BOLD}Available Commands:{RESET}")
            print("  /drafts               List pending staged drafts")
            print("  /approve <draft_id>   Approve and execute a staged draft")
            print("  /discard <draft_id>   Discard a staged draft")
            print("  /routines             List available autonomous routines")
            print("  /routine <name>       Run a routine immediately (e.g. /routine overnight_audit)")
            print("  /roster               View details of all 6 AI teammates")
            print("  @bot <directive>      Target a specific bot directly (e.g. @sentinel or @immune)")
            print("  exit / quit           Exit the console\n")
            continue

        if user_input.startswith("/drafts"):
            drafts = orchestrator.draft_queue.list_drafts()
            print(f"\n{BOLD}Pending & Recent Staged Drafts ({len(drafts)}):{RESET}")
            for d in drafts:
                status_color = YELLOW if d['status'] == 'PENDING_APPROVAL' else GREEN if d['status'] == 'EXECUTED' else RED
                print(f"  • [{status_color}{d['draft_id']}{RESET}] ({d['bot']}) {d['title']} -> {status_color}{d['status']}{RESET}")
            print()
            continue

        if user_input.startswith("/approve"):
            parts = user_input.split()
            if len(parts) < 2:
                print(f"{RED}Usage: /approve <draft_id>{RESET}")
                continue
            draft_id = parts[1].strip()
            print(f"{CYAN}Executing staged draft {draft_id}...{RESET}")
            res = await orchestrator.draft_queue.approve_draft(draft_id)
            if res.get("status") == "EXECUTED":
                print(f"{GREEN}✓ Draft [{draft_id}] Approved & Executed!{RESET}")
                print(f"  Result: {res.get('result')}\n")
            else:
                print(f"{RED}✗ Failed to execute draft: {res.get('error')}{RESET}\n")
            continue

        if user_input.startswith("/discard"):
            parts = user_input.split()
            if len(parts) < 2:
                print(f"{RED}Usage: /discard <draft_id>{RESET}")
                continue
            draft_id = parts[1].strip()
            res = orchestrator.draft_queue.discard_draft(draft_id)
            print(f"{YELLOW}Draft [{draft_id}] discarded.{RESET}\n")
            continue

        if user_input.startswith("/routines"):
            print(f"\n{BOLD}Registered Autonomous Routines:{RESET}")
            for r_id, r_info in ROUTINE_CATALOG.items():
                print(f"  • {CYAN}{r_id}{RESET}: {BOLD}{r_info['title']}{RESET}")
                print(f"    {r_info['description']}")
                print(f"    {DIM}Teammates: {', '.join(r_info['bots'])} | Schedule: {r_info['schedule']}{RESET}\n")
            continue

        if user_input.startswith("/routine"):
            parts = user_input.split()
            r_name = parts[1].strip() if len(parts) > 1 else "overnight_audit"
            if r_name == "overnight_audit":
                print(f"{CYAN}Dispatching overnight audit swarm across Sentinel, Immune, Claw, and Athena...{RESET}")
                res = await orchestrator.routine_runner.run_overnight_audit()
                print(f"{GREEN}✓ Overnight Audit Complete ({res['duration_sec']:.1f}s){RESET}\n")
                print(f"{BOLD}Executive Debrief:{RESET}\n{res.get('debrief')}\n")
            elif r_name == "tripwire_heartbeat":
                print(f"{CYAN}Running Sentinel tripwire heartbeat...{RESET}")
                res = await orchestrator.routine_runner.run_tripwire_heartbeat()
                print(f"{GREEN}✓ Heartbeat recorded:{RESET} {res.get('data')}\n")
            else:
                print(f"{RED}Unknown routine '{r_name}'. Available: {list(ROUTINE_CATALOG.keys())}{RESET}")
            continue

        if user_input.startswith("/roster"):
            print(f"\n{BOLD}Quantum Flex AI Teammate Roster:{RESET}")
            for t in roster:
                print(f"  {t['avatar']} {BOLD}{t['name']}{RESET} ({CYAN}@{t['callsign']}{RESET})")
                print(f"    Role:  {t['role']}")
                print(f"    Model: {t['model']}")
            print()
            continue

        # Process Natural Query
        print(f"{DIM}Connecting to Quantum Flex Swarm...{RESET}")
        res = await orchestrator.handle_message(user_input)

        # Print handoffs if any
        if res.get("handoffs"):
            for h in res["handoffs"]:
                print(f"  {CYAN}⚡ Handoff [{h['from'].upper()} ➔ {h['to'].upper()}]:{RESET} {h['action']}")

        bot_info = res.get("bot", {})
        print(f"\n{MAGENTA}{BOLD}{bot_info.get('avatar', '🤖')} {bot_info.get('name', 'BOT')}:{RESET}")
        print(res.get("response", ""))

        # If a draft was staged, show card and prompt for immediate approval
        if res.get("staged_draft"):
            draft = res["staged_draft"]
            print_draft_card(draft)
            prompt = input(f"{YELLOW}Would you like to approve and execute [{draft['draft_id']}] now? (y/N): {RESET}").strip().lower()
            if prompt in ["y", "yes"]:
                print(f"{CYAN}Executing {draft['draft_id']}...{RESET}")
                app_res = await orchestrator.draft_queue.approve_draft(draft["draft_id"])
                if app_res.get("status") == "EXECUTED":
                    print(f"{GREEN}✓ Approved & Executed!{RESET} {app_res.get('result')}\n")
                else:
                    print(f"{RED}✗ Execution failed: {app_res.get('error')}{RESET}\n")

        print()


if __name__ == "__main__":
    asyncio.run(main_loop())
