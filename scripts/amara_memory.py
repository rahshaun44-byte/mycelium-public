#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
  PROJECT AMARA — PHASE 2: PERMISSION-CONTROLLED PERSISTENT MEMORY VAULT
  QuantumFlex Sovereign Infrastructure (/home/quant/mycelium)
═══════════════════════════════════════════════════════════════════════════════
Architecture:
  1. public_ops tier: Verified infrastructure topology, physical hardware proof
     manifests, and OPA policy facts (Mode 0644).
  2. architect_private tier: Founding directives, /remember notes, and personal
     operational principles (Strict Mode 0600).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import pathlib
import uuid
from typing import Any

USER_HOME = pathlib.Path.home()
MYCELIUM_DIR = USER_HOME / "mycelium"
SENTINEL_DIR = MYCELIUM_DIR / "sentinel"
PUBLIC_OPS_PATH = SENTINEL_DIR / "memory_public_ops.json"
PRIVATE_MEMORY_PATH = SENTINEL_DIR / "memory_architect_private.json"

DEFAULT_TOPOLOGY_FACTS = {
    "node_mandate": "ALL NODES WILL ALWAYS PROTECT. Every admitted node in the QuantumFlex sovereign mesh is bound by the universal constitutional invariant to defend and protect the Architect and the network.",
    "nodes": {
        "qfx-yoga": {
            "tailscale_ip": "100.64.1.31",
            "hardware": "Lenovo Yoga 7 2-in-1 14AKP10 (AMD Ryzen AI 5 340, Radeon 840M, Microsoft Pluton TPM 2.0)",
            "role": "Primary Sovereign Engine & Workstation (Architect's Master Node)",
            "trust_state": "TRUSTED_PRIMARY",
            "protects_architect": True,
            "protection_domain": "Orchestrates sovereign defense, local compute, memory solvency (R >= O), and PostgreSQL containment walls.",
        },
        "qfx-pixel": {
            "tailscale_ip": "100.64.1.16",
            "hardware": "Google Pixel 11 Pro (Titan M2 StrongBox key 'qf-operator-key', Android 17)",
            "role": "Chief Architect Mobile HUD & Out-of-Band Hardware Key Anchor",
            "trust_state": "TRUSTED_HUD",
            "protects_architect": True,
            "protection_domain": "Protects mobile command interface and provides out-of-band Titan M2 cryptographic authorization.",
        },
        "g6pro": {
            "tailscale_ip": "100.64.1.19",
            "hardware": "HP ProBook 450 G6",
            "role": "Dedicated Apache Kafka Broker & Event Streaming Node (ports 9092, 8090)",
            "trust_state": "QUARANTINED_PROTECTED_STANDBY",
            "protects_architect": True,
            "protection_domain": "Protects telemetry streaming, event decoupling, and high-throughput buffer ingestion. Currently held under defensive socket quarantine until sanitized.",
        },
    },
    "verified_milestones": {
        "physical_quantum_execution": {
            "qpu": "ibm_kingston (156-qubit Heron r2 silicon)",
            "job_id": "dbl33e56p51s73cnltvg",
            "fidelity": 0.9355,
            "witness_expectation": -0.4355,
            "witness_95_ucb": -0.4174,
            "qaoa_optimal_portfolio": "|101> (Tech + Treasury)",
            "classical_equivalence": "< 1e-14 across all 8 states",
            "ledger_entry": 42,
            "status": "CERTIFIED_ON_PHYSICAL_SILICON",
        },
        "smart_contract_settlement": {
            "contract": "QuantumFlexUSDCSettler.sol",
            "evm_target": "paris (solc 0.8.24)",
            "token": "USDC (strictly 6 decimals)",
            "tests_passed": "29/29 (including 128k formal invariant fuzz calls)",
            "fail_closed_gate": "revokeAttester() halts in O(1)",
            "invariant_3": "Passed both branches (correlation >= 8500 bps AND witness UCB < 0)",
        },
    },
    "governing_rego_policies": {
        "operating_constitution.rego": [
            "QF-CAPITAL-01: Six-month reserve gate (R >= 6 * O) & sacred Bucket 1 IRON_RESERVE lock",
            "QF-PRIVACY-01: Local-only inference ($0.00 cloud), provenance, zero leak",
            "QF-AUTH-01: Mandatory human authorization for consequential finance (zero autonomous agent transfers)",
            "QF-OPS-01: Operator workload protection & ops_fatigue_flag_triggers_recovery",
        ],
        "reserve_invariant.rego": [
            "Universal Invariant R >= O across compute, memory, and capital",
            "Physical water and digital memory solvency monitors",
            "TPM 2.0 hardware anchor validation",
        ],
        "membrane_health.rego": [
            "ML-KEM-768 FIPS 203 strict compliance",
            "Automated 3-state circuit breaker (ACTIVE, QUARANTINE, RECOVERY)",
        ],
    },
}


class AmaraMemoryVault:
    """Manages the two-tier permission-controlled memory for Project AMARA."""

    def __init__(self) -> None:
        SENTINEL_DIR.mkdir(parents=True, exist_ok=True)
        self._init_public_ops()
        self._init_private_memory()

    def _init_public_ops(self) -> None:
        if not PUBLIC_OPS_PATH.exists():
            with PUBLIC_OPS_PATH.open("w", encoding="utf-8") as fh:
                json.dump(DEFAULT_TOPOLOGY_FACTS, fh, indent=2)
            os.chmod(PUBLIC_OPS_PATH, 0o644)
        else:
            # Refresh topology if missing
            try:
                data = json.loads(PUBLIC_OPS_PATH.read_text(encoding="utf-8"))
                if "nodes" not in data or "g6pro" not in data.get("nodes", {}):
                    data.update(DEFAULT_TOPOLOGY_FACTS)
                    PUBLIC_OPS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
            except Exception:
                PUBLIC_OPS_PATH.write_text(json.dumps(DEFAULT_TOPOLOGY_FACTS, indent=2), encoding="utf-8")
            os.chmod(PUBLIC_OPS_PATH, 0o644)

    def _init_private_memory(self) -> None:
        if not PRIVATE_MEMORY_PATH.exists():
            initial_data = {
                "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                "memories": [],
            }
            with PRIVATE_MEMORY_PATH.open("w", encoding="utf-8") as fh:
                json.dump(initial_data, fh, indent=2)
        os.chmod(PRIVATE_MEMORY_PATH, 0o600)

    def get_public_ops(self) -> dict[str, Any]:
        try:
            return json.loads(PUBLIC_OPS_PATH.read_text(encoding="utf-8"))
        except Exception:
            return DEFAULT_TOPOLOGY_FACTS

    def get_private_memories(self) -> list[dict[str, Any]]:
        try:
            data = json.loads(PRIVATE_MEMORY_PATH.read_text(encoding="utf-8"))
            return data.get("memories", [])
        except Exception:
            return []

    def remember(self, text: str, category: str = "architect_directive") -> dict[str, Any]:
        """Saves a permanent memory in the architect_private tier."""
        memories = self.get_private_memories()
        memory_entry = {
            "id": f"mem_{uuid.uuid4().hex[:8]}",
            "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "category": category,
            "text": text.strip(),
            "sha256": hashlib.sha256(text.strip().encode("utf-8")).hexdigest(),
        }
        memories.append(memory_entry)
        data = {
            "updated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "memories": memories,
        }
        PRIVATE_MEMORY_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.chmod(PRIVATE_MEMORY_PATH, 0o600)
        return memory_entry

    def forget(self, memory_id: str) -> bool:
        """Removes a private memory by ID."""
        memories = self.get_private_memories()
        filtered = [m for m in memories if m.get("id") != memory_id]
        if len(filtered) == len(memories):
            return False
        data = {
            "updated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "memories": filtered,
        }
        PRIVATE_MEMORY_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.chmod(PRIVATE_MEMORY_PATH, 0o600)
        return True

    def compile_memory_context(self, mode: str = "private") -> str:
        """Compiles ground-truth topology, Rego policies, and private directives into a prompt block."""
        pub = self.get_public_ops()
        nodes = pub.get("nodes", {})
        rego = pub.get("governing_rego_policies", {})

        topology_lines = [
            "SOVEREIGN MESH TOPOLOGY & TRUTH TABLE (NEVER CONTRADICT THIS):",
            "MANDATE: ALL NODES WILL ALWAYS PROTECT. Every admitted node in the QuantumFlex mesh is bound to protect the Architect and the network.",
            f"1. qfx-yoga ({nodes.get('qfx-yoga', {}).get('tailscale_ip')}): Primary Sovereign Workstation & Engine. TRUSTED. Protects Architect (compute, memory solvency, DB walls).",
            f"2. qfx-pixel ({nodes.get('qfx-pixel', {}).get('tailscale_ip')}): Architect's Mobile HUD (Titan M2). TRUSTED. Protects Architect (mobile command & hardware key auth).",
            f"3. g6pro ({nodes.get('g6pro', {}).get('tailscale_ip')}): Dedicated Kafka Broker & Event Streaming Node. PROTECTS ARCHITECT (telemetry streaming & event decoupling; held in defensive socket quarantine until sanitized).",
        ]

        rego_lines = [
            "GOVERNING OPA REGO CONSTITUTIONAL RULES (ACTIVE ON DISK):",
            f"- {rego.get('operating_constitution.rego', [''])[3]}",
            f"- {rego.get('operating_constitution.rego', [''])[0]}",
            f"- {rego.get('operating_constitution.rego', [''])[2]}",
            "- Universal Invariant R >= O: Reserves strictly exceed Obligations at all times.",
        ]

        lines = ["\n".join(topology_lines), "\n".join(rego_lines)]

        if mode == "private":
            priv = self.get_private_memories()
            if priv:
                priv_lines = ["ARCHITECT PRIVATE DIRECTIVES (/remember entries):"]
                for m in priv[-8:]:  # Include last 8 memories
                    priv_lines.append(f"[{m.get('id')}] {m.get('text')}")
                lines.append("\n".join(priv_lines))

        return "\n\n".join(lines)


if __name__ == "__main__":
    vault = AmaraMemoryVault()
    print("[+] Amara Memory Vault Initialized.")
    print(vault.compile_memory_context())
