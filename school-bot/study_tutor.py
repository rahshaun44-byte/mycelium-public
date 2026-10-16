#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║  SOVEREIGN STUDY TUTOR  •  Local Ollama  •  Zero Cloud Leakage  ║
║  100% Private • Data Never Leaves 127.0.0.1:11434               ║
╚══════════════════════════════════════════════════════════════════╝
Academic Integrity:
  • This tool is a STUDY AID only — concept explanation, quizzing, drilling.
  • Never paste its output directly into graded submissions.
  • Never run this during proctored exams / test-outs.
  • Local-only: no internet, no cloud API calls, no logging to 3rd parties.

Usage:
  qf-study                                  # Interactive menu
  qf-study quiz "topic"                     # Start quiz on topic
  qf-study explain "concept"                # Explain a concept
  qf-study drill "topic"                    # Rapid-fire drill mode (gemma3:4b)
  qf-study review <file>                    # Socratic code review & JUnit test coach
"""

import os
import sys
import json
import time
import readline
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

# ─── ANSI Colors ───────────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BLUE   = "\033[94m"
MAGENTA= "\033[95m"
WHITE  = "\033[97m"

OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")

# Aligned with Yoga 7 installed Ollama models (qwen2.5-coder:7b for depth, gemma3:4b for speed)
STUDY_MODEL = os.environ.get("STUDY_MODEL", "qwen2.5-coder:7b")
FAST_MODEL  = os.environ.get("FAST_MODEL",  "gemma3:4b")

# ─── System personas ───────────────────────────────────────────────
TUTOR_SYSTEM = """You are a brilliant, direct academic tutor. Your style:
- Explain concepts clearly with real examples
- Never preachy or condescending
- Give analogies that actually land
- When asked to quiz, give ONE question at a time and wait for the answer
- When grading answers: be honest, specific about what's right/wrong, explain why
- Keep answers tight and useful — no padding or corporate fluff
- Adapt to the level: if something confuses, attack it from a different angle
CRITICAL: Never write essays or code that the user could paste directly into graded work.
Your job is to make the HUMAN understand, not to do the work FOR them."""

QUIZ_SYSTEM = """You are a Socratic quiz master. Rules:
1. Ask exactly ONE multiple-choice question (A/B/C/D) on the given topic
2. After the student answers, reveal if correct and explain WHY in 2-3 sentences
3. Then say "Ready for the next one? (yes/no)" and wait
4. Track score mentally. After 10 questions, give a score and weak-area summary
5. Never give the answer before the student responds
6. Make questions progressively harder as the student gets them right
CRITICAL: This is for STUDYING, not for answering actual exam questions live."""

DRILL_SYSTEM = """You are a rapid-fire concept drill instructor. Rules:
1. Fire short, punchy questions one at a time — no multiple choice, just open-ended
2. Student gives a quick answer. You rate it: ✅ SOLID / ⚠️ PARTIAL / ❌ WRONG
3. After rating, give the correct 1-sentence answer and move to the next question
4. Keep the energy high and pace fast
5. Focus on definitions, distinctions, and real-world applications"""

# ─── Core Ollama call ──────────────────────────────────────────────
def stream_ollama(model: str, messages: list, system: str = "") -> str:
    """Stream Ollama response to terminal, return full text."""
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {
            "temperature": 0.4,
            "top_p": 0.9,
            "num_predict": 1024,
        }
    }
    if system:
        payload["system"] = system

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=data,
        headers={"Content-Type": "application/json"}
    )

    full_response = ""
    print(f"\n{CYAN}{BOLD}", end="", flush=True)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            for line in resp:
                if not line.strip():
                    continue
                chunk = json.loads(line.decode("utf-8"))
                token = chunk.get("message", {}).get("content", "")
                if token:
                    print(token, end="", flush=True)
                    full_response += token
                if chunk.get("done"):
                    break
    except urllib.error.URLError as e:
        print(f"\n{RED}[!] Cannot reach Ollama at {OLLAMA_URL}: {e}{RESET}")
        print(f"{YELLOW}    Run: sudo systemctl start ollama{RESET}")
        sys.exit(1)

    print(f"{RESET}\n")
    return full_response


def check_ollama() -> bool:
    """Verify Ollama is running and return available models."""
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=3) as resp:
            data = json.loads(resp.read())
            models = [m["name"] for m in data.get("models", [])]
            return models
    except Exception:
        return []


def banner():
    print(f"""
{BOLD}{BLUE}╔══════════════════════════════════════════════════════════════════╗
║          🎓  SOVEREIGN STUDY TUTOR  •  100% LOCAL AI             ║
║     Zero Cloud • Zero Logging • Academic Integrity Safe          ║
╚══════════════════════════════════════════════════════════════════╝{RESET}
{DIM}  Powered by Ollama at {OLLAMA_URL}
  Model: {STUDY_MODEL}  •  Data never leaves your machine{RESET}
""")


def print_integrity_notice():
    print(f"""
{YELLOW}{BOLD}⚠  ACADEMIC INTEGRITY REMINDER{RESET}
{YELLOW}  • Use this to STUDY and UNDERSTAND — not to copy answers
  • Never run during proctored exams or test-outs
  • Never paste AI output directly into graded submissions
  • You're fine: everything stays on 127.0.0.1, zero cloud{RESET}
""")


# ─── Modes ─────────────────────────────────────────────────────────

def mode_explain(topic: str):
    """Explain a concept clearly with examples."""
    print(f"\n{GREEN}📖 Explaining: {BOLD}{topic}{RESET}\n")
    messages = [{"role": "user", "content": f"Explain this concept clearly with a practical example: {topic}"}]
    stream_ollama(STUDY_MODEL, messages, TUTOR_SYSTEM)


def mode_quiz(topic: str):
    """Socratic quiz mode — one question at a time."""
    print(f"\n{MAGENTA}🧪 Quiz Mode: {BOLD}{topic}{RESET}")
    print_integrity_notice()
    print(f"{DIM}  Answer each question. Type 'quit' to stop.{RESET}\n")

    history = [{"role": "user", "content": f"Start a quiz on this topic: {topic}. Give me the first multiple-choice question now."}]
    score = 0
    total = 0

    while True:
        response = stream_ollama(STUDY_MODEL, history, QUIZ_SYSTEM)
        history.append({"role": "assistant", "content": response})

        user_input = input(f"{BOLD}{WHITE}Your answer → {RESET}").strip()
        if user_input.lower() in ("quit", "exit", "q", "stop"):
            print(f"\n{GREEN}Session ended. Great work pushing through!{RESET}")
            break
        if not user_input:
            continue

        history.append({"role": "user", "content": user_input})
        total += 1


def mode_drill(topic: str):
    """Rapid-fire drill mode for fast memorization."""
    print(f"\n{RED}⚡ Drill Mode: {BOLD}{topic}{RESET}")
    print(f"{DIM}  Fast answers. No multiple choice. Type 'quit' to stop.{RESET}\n")

    history = [{"role": "user", "content": f"Start a rapid-fire drill on: {topic}. Fire the first question now. Keep it short."}]

    while True:
        response = stream_ollama(FAST_MODEL, history, DRILL_SYSTEM)
        history.append({"role": "assistant", "content": response})

        user_input = input(f"{BOLD}{WHITE}→ {RESET}").strip()
        if user_input.lower() in ("quit", "exit", "q", "stop"):
            print(f"\n{GREEN}Drill complete. Solid session.{RESET}")
            break
        if not user_input:
            continue

        history.append({"role": "user", "content": user_input})


def mode_chat(topic: Optional[str] = None):
    """General freeform study chat."""
    print(f"\n{CYAN}💬 Study Chat{RESET}")
    print(f"{DIM}  Ask anything. Type 'quiz <topic>', 'drill <topic>', 'explain <concept>', or 'quit'.{RESET}\n")

    history = []
    if topic:
        history.append({"role": "user", "content": f"I'm studying: {topic}. Be my tutor."})
        stream_ollama(STUDY_MODEL, history, TUTOR_SYSTEM)

    while True:
        try:
            user_input = input(f"{BOLD}{WHITE}You → {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{GREEN}Session ended. Good studying!{RESET}")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print(f"\n{GREEN}Good studying! Degree is getting closer.{RESET}")
            break

        # Inline mode switches
        parts = user_input.split(" ", 1)
        if parts[0].lower() == "quiz" and len(parts) > 1:
            mode_quiz(parts[1])
            continue
        elif parts[0].lower() == "drill" and len(parts) > 1:
            mode_drill(parts[1])
            continue
        elif parts[0].lower() == "explain" and len(parts) > 1:
            mode_explain(parts[1])
            continue

        history.append({"role": "user", "content": user_input})
        response = stream_ollama(STUDY_MODEL, history, TUTOR_SYSTEM)
        history.append({"role": "assistant", "content": response})


def mode_review(filepath: str):
    """Socratic coursework code review (Academic Integrity Safe — never rewrites the file for copy-paste)."""
    p = Path(filepath).expanduser().resolve()
    if not p.is_file():
        print(f"{RED}[!] File not found: {p}{RESET}")
        sys.exit(1)
    snippet = p.read_text(encoding="utf-8", errors="replace")[:16000]
    print(f"\n{GREEN}🔍 Socratic Code & Test Coach: {BOLD}{p.name}{RESET}")
    print_integrity_notice()
    prompt = (
        f"Review this student coursework file ({p.name}) as a Socratic CS tutor:\n"
        f"1. State what the code currently does well.\n"
        f"2. Point out any missing boundary checks, null/empty/length validations, or missing JUnit 5 test cases (without writing copy-paste code for the student).\n"
        f"3. Ask me ONE question to verify I can explain how this code works in my own words.\n\n"
        f"```java\n{snippet}\n```"
    )
    history = [{"role": "user", "content": prompt}]
    while True:
        response = stream_ollama(STUDY_MODEL, history, TUTOR_SYSTEM)
        history.append({"role": "assistant", "content": response})
        user_input = input(f"{BOLD}{WHITE}You (or 'quit') → {RESET}").strip()
        if user_input.lower() in ("quit", "exit", "q", "stop"):
            print(f"\n{GREEN}Review complete. You own this code.{RESET}")
            break
        if not user_input:
            continue
        history.append({"role": "user", "content": user_input})


def interactive_menu():
    """Interactive mode selection menu."""
    banner()

    models = check_ollama()
    if not models:
        print(f"{RED}[!] Ollama is not running. Start it with: sudo systemctl start ollama{RESET}")
        sys.exit(1)

    print(f"{GREEN}✓ Ollama online • {len(models)} models available{RESET}")
    avail = ", ".join(models[:4])
    print(f"{DIM}  Available: {avail}{RESET}\n")

    print_integrity_notice()

    print(f"""{BOLD}SELECT A MODE:{RESET}
  {CYAN}[1]{RESET} 💬  Study Chat      — Ask anything, get clear explanations
  {CYAN}[2]{RESET} 🧪  Quiz Me         — Socratic Q&A, one question at a time
  {CYAN}[3]{RESET} ⚡  Rapid Drill     — Fast-fire memorization mode ({FAST_MODEL})
  {CYAN}[4]{RESET} 📖  Explain Concept — Deep dive on a single topic
  {YELLOW}[5]{RESET} 🎓  Study CS 320    — Software Testing, JUnit 5 & QA (Appointment/Contact/Task)
  {YELLOW}[6]{RESET} 🎓  Study CS 210    — Programming Languages (C++, Java, Python)
  {MAGENTA}[7]{RESET} 🛡️  Study PQC & Sec — Post-Quantum Crypto (ML-KEM, GAUGE, Least-Privilege DB Walls)
  {GREEN}[8]{RESET} 🔍  Review My Code  — Socratic coach on a coursework file (no copy-paste)
  {CYAN}[q]{RESET} 🚪  Quit
""")

    choice = input(f"{BOLD}Choose → {RESET}").strip().lower()

    if choice in ("1", "chat"):
        topic = input(f"{DIM}Topic/subject (or press Enter to skip) → {RESET}").strip()
        mode_chat(topic or None)

    elif choice in ("2", "quiz"):
        topic = input(f"{BOLD}Topic to quiz on → {RESET}").strip()
        if topic:
            mode_quiz(topic)
        else:
            print(f"{RED}Need a topic.{RESET}")

    elif choice in ("3", "drill"):
        topic = input(f"{BOLD}Topic to drill → {RESET}").strip()
        if topic:
            mode_drill(topic)
        else:
            print(f"{RED}Need a topic.{RESET}")

    elif choice in ("4", "explain"):
        concept = input(f"{BOLD}Concept to explain → {RESET}").strip()
        if concept:
            mode_explain(concept)
        else:
            print(f"{RED}Need a concept.{RESET}")

    elif choice == "5":
        print(f"\n{GREEN}Loading CS 320: Software Testing, Automation, and Quality Assurance...{RESET}")
        topic = "CS 320 Software Testing, JUnit 5 assertions (assertThrows, assertEquals), boundary value analysis, equivalence partitioning, Contact/Task/Appointment service validation, and SDLC"
        mode_quiz(topic)

    elif choice == "6":
        print(f"\n{GREEN}Loading CS 210: Programming Languages...{RESET}")
        topic = "CS 210 Programming Languages, C++, Java, Python syntax comparison, memory safety, secure coding practices, and file operations"
        mode_quiz(topic)

    elif choice == "7":
        print(f"\n{MAGENTA}Loading Post-Quantum Cryptography & Zero-Trust Systems...{RESET}")
        topic = "NIST PQC standards (FIPS 203 ML-KEM, FIPS 204 ML-DSA), hybrid X25519 + ML-KEM-768 handshakes, adversary cost models (GAUGE), and PostgreSQL least-privilege role containment"
        mode_quiz(topic)

    elif choice == "8":
        fpath = input(f"{BOLD}Path to your coursework file (e.g. ~/Documents/CS320/...) → {RESET}").strip()
        if fpath:
            mode_review(fpath)
        else:
            print(f"{RED}Need a file path.{RESET}")

    elif choice in ("q", "quit", "exit"):
        print(f"\n{GREEN}Degree doesn't fail itself. Keep going.{RESET}\n")
        sys.exit(0)

    else:
        print(f"{RED}Invalid choice.{RESET}")


# ─── Entry point ───────────────────────────────────────────────────
if __name__ == "__main__":
    args = sys.argv[1:]

    if not args:
        interactive_menu()
    elif args[0] == "quiz" and len(args) > 1:
        banner()
        mode_quiz(" ".join(args[1:]))
    elif args[0] == "drill" and len(args) > 1:
        banner()
        mode_drill(" ".join(args[1:]))
    elif args[0] == "explain" and len(args) > 1:
        banner()
        mode_explain(" ".join(args[1:]))
    elif args[0] == "review" and len(args) > 1:
        banner()
        mode_review(args[1])
    elif args[0] == "preflight":
        from bot import inspect_cs320_workspace
        data = inspect_cs320_workspace()
        email_odt = Path("/home/quant/Documents/SNHU-emails/email-cs320-antoun.odt")
        email_str = "No email draft found"
        if email_odt.exists():
            try:
                import zipfile, xml.etree.ElementTree as ET
                with zipfile.ZipFile(email_odt) as z:
                    tree = ET.fromstring(z.read("content.xml"))
                    email_str = " ".join(tree.itertext()).strip()
            except Exception as e:
                email_str = f"Error reading email draft: {e}"
        print(f"\n{BOLD}{CYAN}=== 1. PROF. ANTOUN EMAIL / SUBMISSION RULES ==={RESET}\n{email_str}")
        print(f"\n{BOLD}{CYAN}=== 2. CS 320 WORKSPACE FILES ==={RESET}")
        for f in data["files_found"]:
            print(f"  • {f}")
        print(f"\n{BOLD}{CYAN}=== 3. ZIP ARCHIVE CONTENTS ==={RESET}")
        for zname, zfiles in data["zip_inventories"].items():
            print(f"  [{zname}] -> {len(zfiles)} entries: {', '.join(zfiles[:10])}")
        print(f"\n{BOLD}{CYAN}=== 4. CODE OWNERSHIP & SIMPLICITY AUDIT ==={RESET}")
        for sc in data["style_checks"]:
            print(f"  • {sc['file']} ({sc['lines']} lines): {'; '.join(sc['flags'])}")
        print(f"\n{BOLD}{CYAN}=== 5. MAVEN TEST STATUS ==={RESET}\n{data['maven_summary']}\n")
    elif args[0] == "chat":
        banner()
        mode_chat(" ".join(args[1:]) if len(args) > 1 else None)
    else:
        print(f"{RED}Usage: qf-study [preflight|quiz|drill|explain|review|chat] [topic_or_file]{RESET}")
        sys.exit(1)
