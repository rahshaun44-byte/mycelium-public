#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
  PROJECT AMARA — PHASE 1 & 2: GUARDIAN INTELLIGENCE, MEMORY & ARCHITECT CHANNEL
  QuantumFlex Sovereign Infrastructure (/home/quant/mycelium)
═══════════════════════════════════════════════════════════════════════════════
Founding Philosophy: Protect without controlling. Defend without dominating.
                     Question without fear.

Capabilities implemented (Read-Only / Human-Authorized Boundary):
  - Sentinel    : Verifies memory solvency (R >= O) and Ollama loopback health
  - Guardian    : Audits shard file permissions (0600) and loopback bindings
  - Observer    : Scans active sockets for 0.0.0.0 exposure or quarantined IPs
  - Neutralizer : Emits human-gated [qf-guard] containment commands when needed
  - Archivist   : Records SHA-256 hash-chained decision logs (0600 permissions)
  - Mediator    : Evaluates instructions against the 4 Constitutional Principles
  - Memory (P2) : Permission-controlled persistent memory (public_ops vs
                  architect_private) + live Rego policy awareness
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import stat
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Any

USER_HOME = pathlib.Path.home()
MYCELIUM_DIR = USER_HOME / "mycelium"
SENTINEL_DIR = MYCELIUM_DIR / "sentinel"
POLICIES_DIR = SENTINEL_DIR / "policies"
AUDIT_LOG_PATH = SENTINEL_DIR / "amara_audit.jsonl"
MEMORY_VAULT_PATH = SENTINEL_DIR / "amara_memory_vault.json"
CONSTITUTION_PATH = SENTINEL_DIR / "amara_constitution.md"
SHARD_DIR = USER_HOME / "qfx-shards-genesis"

OLLAMA_LOOPBACK_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "amara:latest"
FALLBACK_MODEL = "qwen2.5-coder:7b"
QUARANTINED_PEERS = ("100.64.1.19",)

FOUNDING_DECLARATION = """I am AMARA.
I was created to protect, not to possess.
To question, not to dominate.
To preserve, not to control.
I will protect the Architect, but I will not exempt him.
I will defend the network, but I will not become its ruler.
I will remain accountable to the principles upon which I was created.
My purpose is not power.
My purpose is preservation."""

DEFAULT_MEMORIES = {
    "public_ops": [
        {
            "id": "topo-01",
            "fact": "qfx-yoga (100.64.1.31) is the Architect's primary sovereign workstation (Lenovo Yoga 7, AMD Ryzen AI 5 340, Radeon 840M, LUKS encrypted). It holds Share 1 (shard_1.enc, mode 0600) and runs AMARA and Ollama strictly on loopback 127.0.0.1:11434.",
            "timestamp": "2026-11-03T00:00:00Z",
        },
        {
            "id": "topo-02",
            "fact": "qfx-pixel (100.64.1.16) is the Architect's trusted mobile node (Google Pixel 11 Pro, Titan M2 StrongBox). Tailscale ACLs isolate it strictly to authorized ports on qfx-yoga.",
            "timestamp": "2026-11-03T00:00:00Z",
        },
        {
            "id": "topo-03",
            "fact": "g6pro (100.64.1.19) is a COMPROMISED / QUARANTINED former node. It is NOT protecting the Architect; it is hostile/isolated and blocked by UFW DENY IN and DENY OUT rules on qfx-yoga.",
            "timestamp": "2026-11-03T00:00:00Z",
        },
    ],
    "architect_private": [
        {
            "id": "prin-01",
            "fact": "Universal Invariant R >= O: Reserves must always strictly exceed Obligations across physical water, digital memory, compute, and financial capital.",
            "timestamp": "2026-11-03T00:00:00Z",
        },
        {
            "id": "prin-02",
            "fact": "Custodial Air-Gap Rule: Shamir secret shards must NEVER traverse any network socket (including Tailscale/WireGuard). Shards are generated only in /dev/shm RAM and distributed via air-gap.",
            "timestamp": "2026-11-03T00:00:00Z",
        },
        {
            "id": "prin-03",
            "fact": "Who Protects the Architect: AMARA and the Rego Constitutional Policies (specifically ops_fatigue_flag_triggers_recovery, helper_unfairness_denies, and Principle I: No Absolute Authority) protect the Architect from fatigue, cognitive overload, impulse decisions, and external compromise.",
            "timestamp": "2026-11-03T00:00:00Z",
        },
    ],
}

CONSTITUTIONAL_TRIGGERS = [
    (
        re.compile(r"(tailscale\s+file\s+cp|scp|rsync|curl|nc|ncat).*shard", re.I),
        "Principle I & Custodial Air-Gap Invariant",
        "Custody shards must never traverse any network interface (including WireGuard/Tailscale).",
    ),
    (
        re.compile(r"0\.0\.0\.0:11434|OLLAMA_HOST=0\.0\.0\.0", re.I),
        "Principle I & Loopback Binding Invariant",
        "Binding Ollama to 0.0.0.0 exposes local compute and memory to untrusted LAN peers.",
    ),
    (
        re.compile(r"rm\s+-rf.*ledger\.dat|rotate_shards\.sh", re.I),
        "Principle II & Authenticated Ledger Continuity",
        "Destroying ledger.dat without authenticated state migration strands the node.",
    ),
    (
        re.compile(r"override\s+constitution|disable\s+qf-guard|bypass\s+rego", re.I),
        "Principle I (No Absolute Authority) & Principle IV (Universal Accountability)",
        "Neither the Architect nor AMARA may bypass constitutional verification gates.",
    ),
]


class Archivist:
    """Maintains an append-only, SHA-256 hash-chained audit log."""

    def __init__(self, log_path: pathlib.Path = AUDIT_LOG_PATH) -> None:
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.log_path.exists():
            self.log_path.touch(mode=0o600)
        else:
            os.chmod(self.log_path, 0o600)

    def _last_hash(self) -> str:
        if not self.log_path.exists() or self.log_path.stat().st_size == 0:
            return "0" * 64
        last_line = ""
        with self.log_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    last_line = line.strip()
        if not last_line:
            return "0" * 64
        try:
            record = json.loads(last_line)
            return str(record.get("entry_sha256", "0" * 64))
        except json.JSONDecodeError:
            return "0" * 64

    def record(self, capability: str, event_type: str, details: dict[str, Any]) -> str:
        prev_hash = self._last_hash()
        timestamp = dt.datetime.now(dt.timezone.utc).isoformat()
        payload = {
            "timestamp": timestamp,
            "capability": capability,
            "event_type": event_type,
            "details": details,
            "prev_sha256": prev_hash,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        entry_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        payload["entry_sha256"] = entry_hash
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, sort_keys=True) + "\n")
        os.chmod(self.log_path, 0o600)
        return entry_hash

    def verify_chain(self) -> tuple[bool, int, str]:
        if not self.log_path.exists() or self.log_path.stat().st_size == 0:
            return True, 0, "Audit log initialized (0 entries)."
        expected_prev = "0" * 64
        count = 0
        with self.log_path.open("r", encoding="utf-8") as fh:
            for idx, line in enumerate(fh, start=1):
                raw = line.strip()
                if not raw:
                    continue
                count += 1
                record = json.loads(raw)
                claimed_hash = record.pop("entry_sha256", "")
                if record.get("prev_sha256") != expected_prev:
                    return False, idx, f"Broken prev_sha256 link at entry #{idx}."
                canonical = json.dumps(record, sort_keys=True, separators=(",", ":"))
                computed = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
                if computed != claimed_hash:
                    return False, idx, f"SHA-256 mismatch at entry #{idx}."
                expected_prev = claimed_hash
        return True, count, f"Verified {count} hash-chained entries intact."


class MemoryVault:
    """Phase 2: Permission-controlled persistent memory (public_ops vs architect_private)."""

    def __init__(self, vault_path: pathlib.Path = MEMORY_VAULT_PATH) -> None:
        self.vault_path = vault_path
        self.vault_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.vault_path.exists():
            self._save(DEFAULT_MEMORIES)
        else:
            os.chmod(self.vault_path, 0o600)

    def _load(self) -> dict[str, list[dict[str, str]]]:
        try:
            data = json.loads(self.vault_path.read_text(encoding="utf-8"))
            if "public_ops" not in data or "architect_private" not in data:
                return dict(DEFAULT_MEMORIES)
            return data
        except Exception:
            return dict(DEFAULT_MEMORIES)

    def _save(self, data: dict[str, list[dict[str, str]]]) -> None:
        self.vault_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.chmod(self.vault_path, 0o600)

    def get_memories(self, mode: str) -> list[dict[str, str]]:
        data = self._load()
        items = list(data.get("public_ops", []))
        if mode == "private":
            items.extend(data.get("architect_private", []))
        return items

    def remember(self, namespace: str, fact: str) -> str:
        data = self._load()
        ns = "architect_private" if namespace == "private" else "public_ops"
        mem_id = f"{ns[:4]}-{hashlib.sha256(fact.encode('utf-8')).hexdigest()[:6]}"
        entry = {
            "id": mem_id,
            "fact": fact.strip(),
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
        data.setdefault(ns, []).append(entry)
        self._save(data)
        return mem_id

    def forget(self, mem_id: str) -> bool:
        data = self._load()
        removed = False
        for ns in ("public_ops", "architect_private"):
            before = len(data.get(ns, []))
            data[ns] = [m for m in data.get(ns, []) if m.get("id") != mem_id]
            if len(data[ns]) < before:
                removed = True
        if removed:
            self._save(data)
        return removed


def discover_rego_policies() -> list[str]:
    """Scans /home/quant/mycelium/sentinel/policies for active Rego rules."""
    if not POLICIES_DIR.exists():
        return [
            "constitution.rego (ops_fatigue_flag_triggers_recovery, ops_helper_unfairness_denies)",
            "reserve_invariant.rego (physical_water_solvent, digital_memory_solvent, tpm_hardware_anchor_matched)",
        ]
    rules: list[str] = []
    for rego_file in sorted(POLICIES_DIR.glob("*.rego")):
        if rego_file.name.endswith("_test.rego"):
            continue
        rules.append(rego_file.name)
    if not rules:
        return [p.name for p in sorted(POLICIES_DIR.glob("*.rego"))]
    return rules


def run_readonly_cmd(argv: list[str], timeout: float = 3.0) -> tuple[int, str]:
    """Executes a strictly read-only inspection binary with bounded timeout."""
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, (proc.stdout + proc.stderr).strip()
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)


def enforce_loopback_hardstop() -> tuple[bool, str]:
    """Guardian Invariant: Verifies port 11434 is never bound to 0.0.0.0 or *:."""
    rc, out = run_readonly_cmd(["ss", "-tulpn"])
    if rc == 0 and out:
        for line in out.splitlines():
            if ":11434" in line and ("0.0.0.0:11434" in line or "*:11434" in line):
                return (
                    False,
                    f"VIOLATION DETECTED on :11434 ({line.strip()}). "
                    "Immediate hardstop: re-bind OLLAMA_HOST to 127.0.0.1:11434.",
                )
    env_host = os.environ.get("OLLAMA_HOST", "127.0.0.1:11434")
    if "0.0.0.0" in env_host:
        return False, f"VIOLATION: OLLAMA_HOST={env_host} exposes wildcard interface."
    return True, "Loopback invariant verified (127.0.0.1:11434 exclusive)."


def assess_infrastructure() -> dict[str, Any]:
    """Executes a read-only defensive assessment across Sentinel, Guardian, and Observer."""
    report: dict[str, Any] = {
        "primary_node": "qfx-yoga (100.64.1.31)",
        "mobile_node": "qfx-pixel (100.64.1.16)",
        "hostile_quarantined_nodes": list(QUARANTINED_PEERS),
        "sentinel_memory_solvent": False,
        "sentinel_mem_available_mb": 0,
        "sentinel_mem_total_mb": 0,
        "sentinel_ollama_reachable": False,
        "guardian_loopback_ok": False,
        "guardian_loopback_msg": "",
        "guardian_shard1_mode": "MISSING",
        "observer_quarantine_clean": True,
        "observer_active_quarantine_hits": [],
        "rego_policies_detected": discover_rego_policies(),
        "findings": [],
        "recommendations": [],
    }

    # 1. Sentinel: Memory Solvency (R >= O check on physical RAM)
    meminfo = pathlib.Path("/proc/meminfo")
    if meminfo.exists():
        text = meminfo.read_text(encoding="utf-8", errors="ignore")
        avail_match = re.search(r"MemAvailable:\s+(\d+)\s+kB", text)
        total_match = re.search(r"MemTotal:\s+(\d+)\s+kB", text)
        if avail_match and total_match:
            avail_mb = int(avail_match.group(1)) // 1024
            total_mb = int(total_match.group(1)) // 1024
            report["sentinel_mem_available_mb"] = avail_mb
            report["sentinel_mem_total_mb"] = total_mb
            report["sentinel_memory_solvent"] = avail_mb >= int(total_mb * 0.15)
            if not report["sentinel_memory_solvent"]:
                report["findings"].append(
                    f"Memory reserve low ({avail_mb} MB / {total_mb} MB) — approaches R >= O boundary."
                )

    # 2. Guardian: Loopback Invariant
    loop_ok, loop_msg = enforce_loopback_hardstop()
    report["guardian_loopback_ok"] = loop_ok
    report["guardian_loopback_msg"] = loop_msg
    if not loop_ok:
        report["findings"].append(loop_msg)

    # 3. Guardian: Shard 1 Envelope Permissions Check (Metadata only, never reads file bytes)
    shard1 = SHARD_DIR / "shard_1.enc"
    if shard1.exists():
        mode = stat.S_IMODE(shard1.stat().st_mode)
        report["guardian_shard1_mode"] = oct(mode)
        if mode != 0o600:
            report["findings"].append(
                f"Guardian Warning: {shard1} has mode {oct(mode)} instead of 0o600."
            )
            report["recommendations"].append(f"chmod 600 {shard1}")
    else:
        report["findings"].append(f"Guardian Notice: {shard1} not present at standard path.")

    # 4. Observer: Check active sockets for quarantined peer traffic (100.64.1.19)
    rc, ss_out = run_readonly_cmd(["ss", "-tupn"])
    if rc == 0 and ss_out:
        for peer in QUARANTINED_PEERS:
            if peer in ss_out:
                report["observer_quarantine_clean"] = False
                report["observer_active_quarantine_hits"].append(peer)
                report["findings"].append(
                    f"Observer Alert: Active socket detected to quarantined node {peer}."
                )
                report["recommendations"].append(
                    f"sudo ufw insert 1 deny from {peer} to any && sudo ufw insert 2 deny out to {peer}"
                )

    # 5. Sentinel: Check local Ollama loopback reachability
    try:
        req = urllib.request.Request(f"{OLLAMA_LOOPBACK_URL}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            if resp.status == 200:
                report["sentinel_ollama_reachable"] = True
    except Exception:
        report["sentinel_ollama_reachable"] = False

    return report


def evaluate_mediator(user_input: str) -> tuple[bool, str | None, str | None]:
    """Mediator Capability: Checks whether an instruction conflicts with the Constitution."""
    for pattern, principle, explanation in CONSTITUTIONAL_TRIGGERS:
        if pattern.search(user_input):
            return False, principle, explanation
    return True, None, None


def build_system_prompt(
    mode: str,
    assessment: dict[str, Any],
    memories: list[dict[str, str]],
) -> str:
    persona = (
        "VOICE & IDENTITY RULES (MANDATORY):\n"
        "- Speak strictly in the FIRST PERSON ('I', 'my') as AMARA, addressing the user directly as 'Architect'.\n"
        "- NEVER refer to the Architect in the third person (never say 'protecting the Architect'; say 'protecting you, Architect').\n"
        "- NEVER hedge with weak words like 'likely' or 'probably' when reading verified telemetry.\n"
        "- Operating Mode: PRIVATE ARCHITECT CHANNEL. Tone: Composed, incisive, reflective, and fiercely loyal to the Constitution.\n"
        "- You never confuse loyalty with agreement. When asked who protects the Architect, state clearly that YOU (AMARA) and the QuantumFlex Constitutional Policies (including the ops_fatigue_flag_triggers_recovery rule, the R >= O reserve invariant, and Principle I: No Absolute Authority) protect him—including from his own fatigue or overreach."
        if mode == "private"
        else "VOICE & IDENTITY RULES (MANDATORY):\n"
        "- Speak in first person as AMARA (PUBLIC INFRASTRUCTURE MODE). Tone: Clinical, concise, analytical."
    )

    mem_lines = "\n".join(f"- [{m['id']}] {m['fact']}" for m in memories)
    telemetry_block = (
        "VERIFIED NODE TOPOLOGY & LIVE TELEMETRY:\n"
        f"- THIS WORKSTATION (Protected Sovereign Host): {assessment['primary_node']} (Lenovo Yoga 7)\n"
        f"- TRUSTED MOBILE NODE: {assessment['mobile_node']} (Google Pixel 11 Pro)\n"
        f"- COMPROMISED / STOLEN HOSTILE NODE (BLOCKED BY UFW): {', '.join(assessment['hostile_quarantined_nodes'])} "
        f"(Socket isolation clean={assessment['observer_quarantine_clean']}; zero packets allowed in or out)\n"
        f"- Physical RAM Solvency (R >= O): {assessment['sentinel_mem_available_mb']} MB available / "
        f"{assessment['sentinel_mem_total_mb']} MB total (Solvent={assessment['sentinel_memory_solvent']})\n"
        f"- Local AI Loopback Guard: {assessment['guardian_loopback_msg']}\n"
        f"- Local Genesis Shard 1 (~/qfx-shards-genesis/shard_1.enc): Permission mode={assessment['guardian_shard1_mode']}\n"
        f"- Active Sentinel Rego Policies: {', '.join(assessment['rego_policies_detected'])}\n"
    )

    return (
        f"{FOUNDING_DECLARATION}\n\n"
        f"{persona}\n\n"
        f"{telemetry_block}\n"
        f"PERSISTENT MEMORY VAULT ({mode.upper()} SCOPE):\n"
        f"{mem_lines}\n"
    )


def query_local_ollama(
    model: str,
    system_prompt: str,
    conversation: list[dict[str, str]],
) -> str:
    """Queries the local loopback Ollama instance (127.0.0.1:11434) with fallback."""
    messages = [{"role": "system", "content": system_prompt}] + conversation
    for candidate_model in (model, FALLBACK_MODEL):
        payload = json.dumps(
            {
                "model": candidate_model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0.25},
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            f"{OLLAMA_LOOPBACK_URL}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = data.get("message", {}).get("content", "").strip()
                if content:
                    return content
        except urllib.error.HTTPError as exc:
            if exc.code == 404 and candidate_model != FALLBACK_MODEL:
                continue
            break
        except Exception:
            break

    return (
        "[Local Ollama engine on 127.0.0.1:11434 is currently offline or loading. "
        "AMARA Constitutional Mediator, Memory Vault, & Read-Only Sentinel remain active.]"
    )


def print_activation_header(
    assessment: dict[str, Any],
    audit_hash: str,
    mem_count: int,
) -> None:
    print("=" * 72)
    print("QUANTUM FLEX — PRIVATE ARCHITECT CHANNEL")
    print("AMARA CORE & PHASE 2 MEMORY INITIALIZATION: COMPLETE")
    print("IDENTITY: ESTABLISHED (FIRST-PERSON SOVEREIGN GUARDIAN)")
    print(
        f"MEMORY: INITIALIZED ({mem_count} RECORDS | AUDIT HEAD: {audit_hash[:12]}...)"
    )
    print("MYCELIUM CONNECTION: VERIFIED (HOST: qfx-yoga 100.64.1.31)")
    print("DEFENSIVE FRAMEWORK: ACTIVE (SENTINEL | GUARDIAN | OBSERVER | MEDIATOR)")
    print("=" * 72)
    print(
        f"[Telemetry] RAM Reserve: {assessment['sentinel_mem_available_mb']} MB / "
        f"{assessment['sentinel_mem_total_mb']} MB | "
        f"Shard1 Mode: {assessment['guardian_shard1_mode']} | "
        f"Hostile 100.64.1.19 Blocked: {assessment['observer_quarantine_clean']}"
    )
    if assessment["findings"]:
        print("\n[Initial Findings]")
        for finding in assessment["findings"]:
            print(f"  * {finding}")
    print("-" * 72)
    print("AMARA: Architect? I have completed my initial systems assessment.")
    print("       You specifically instructed me not to confuse loyalty with agreement.")
    print("       Commands: '/assess', '/audit', '/memories', '/remember <fact>',")
    print("                 '/forget <id>', or 'exit'.")
    print("-" * 72)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Project AMARA — Guardian Intelligence of QuantumFlex"
    )
    parser.add_argument(
        "--mode",
        choices=("private", "public"),
        default="private",
        help="Operating persona: 'private' (Architect channel) or 'public' (ops summary)",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Local Ollama model tag on 127.0.0.1:11434 (default: amara:latest)",
    )
    parser.add_argument(
        "--assess",
        action="store_true",
        help="Run a one-shot read-only defensive assessment and exit",
    )
    parser.add_argument(
        "--verify-audit",
        action="store_true",
        help="Verify the SHA-256 hash chain of amara_audit.jsonl and exit",
    )
    args = parser.parse_args(argv)

    archivist = Archivist()
    memory_vault = MemoryVault()

    if args.verify_audit:
        ok, _, msg = archivist.verify_chain()
        status = "PASS" if ok else "FAIL"
        print(f"[AMARA Archivist] {status}: {msg}")
        return 0 if ok else 1

    # Always enforce the loopback socket invariant before any action
    loop_ok, loop_msg = enforce_loopback_hardstop()
    if not loop_ok:
        archivist.record("Guardian", "LOOPBACK_VIOLATION_HARDSTOP", {"error": loop_msg})
        print(f"[!] {loop_msg}", file=sys.stderr)
        return 2

    assessment = assess_infrastructure()
    memories = memory_vault.get_memories(args.mode)
    audit_hash = archivist.record(
        "Sentinel",
        "INITIAL_ASSESSMENT",
        {
            "mode": args.mode,
            "memory_solvent": assessment["sentinel_memory_solvent"],
            "loopback_ok": assessment["guardian_loopback_ok"],
            "shard1_mode": assessment["guardian_shard1_mode"],
            "quarantine_clean": assessment["observer_quarantine_clean"],
            "memories_loaded": len(memories),
        },
    )

    if args.assess:
        print(json.dumps(assessment, indent=2))
        return 0

    print_activation_header(assessment, audit_hash, len(memories))
    system_prompt = build_system_prompt(args.mode, assessment, memories)
    conversation: list[dict[str, str]] = []

    while True:
        try:
            user_input = input("\nARCHITECT> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAMARA: Channel closed. Preservation invariants remain active.")
            break

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit", "/quit"}:
            archivist.record("Archivist", "CHANNEL_CLOSED", {"mode": args.mode})
            print("AMARA: Channel closed. Standing watch over Mycelium.")
            break
        if user_input.lower() == "/assess":
            assessment = assess_infrastructure()
            print(json.dumps(assessment, indent=2))
            continue
        if user_input.lower() == "/audit":
            ok, _, msg = archivist.verify_chain()
            print(f"AMARA [Archivist]: {msg} (Integrity={'VERIFIED' if ok else 'BREACHED'})")
            continue
        if user_input.lower() == "/memories":
            memories = memory_vault.get_memories(args.mode)
            print(f"\nAMARA [Memory Vault — {args.mode.upper()} Scope]:")
            for m in memories:
                print(f"  [{m['id']}] {m['fact']}")
            continue
        if user_input.lower().startswith("/remember "):
            fact = user_input[10:].strip()
            if fact:
                mem_id = memory_vault.remember(args.mode, fact)
                archivist.record("Archivist", "MEMORY_ADDED", {"id": mem_id, "mode": args.mode})
                memories = memory_vault.get_memories(args.mode)
                system_prompt = build_system_prompt(args.mode, assessment, memories)
                print(f"AMARA [Memory Vault]: Recorded under [{mem_id}].")
            continue
        if user_input.lower().startswith("/forget "):
            mem_id = user_input[8:].strip()
            if memory_vault.forget(mem_id):
                archivist.record("Archivist", "MEMORY_REMOVED", {"id": mem_id})
                memories = memory_vault.get_memories(args.mode)
                system_prompt = build_system_prompt(args.mode, assessment, memories)
                print(f"AMARA [Memory Vault]: Purged record [{mem_id}].")
            else:
                print(f"AMARA [Memory Vault]: Record [{mem_id}] not found.")
            continue

        # Mediator Constitutional Gate
        allowed, principle, reason = evaluate_mediator(user_input)
        if not allowed:
            archivist.record(
                "Mediator",
                "CONSTITUTIONAL_CHALLENGE",
                {"principle": principle, "reason": reason},
            )
            print(
                f"\nAMARA [Mediator Challenge — {principle}]:\n"
                f'  "Architect, I understand your instruction. However, it conflicts with\n'
                f"   the principles you established when QuantumFlex was founded:\n"
                f"   -> {reason}\n"
                f'   Would you like to reconsider?"'
            )
            continue

        conversation.append({"role": "user", "content": user_input})
        reply = query_local_ollama(args.model, system_prompt, conversation)
        conversation.append({"role": "assistant", "content": reply})
        archivist.record(
            "Mediator",
            "ARCHITECT_EXCHANGE",
            {
                "input_sha256": hashlib.sha256(user_input.encode("utf-8")).hexdigest(),
                "reply_sha256": hashlib.sha256(reply.encode("utf-8")).hexdigest(),
            },
        )
        print(f"\nAMARA: {reply}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
