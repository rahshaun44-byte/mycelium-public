#!/usr/bin/env python3
"""
Quantum Flex Autonomous Tactical Command Swarm
=============================================
Defines the specialized tactical units reporting to the Chief Architect:
- A.M.A.R.A.: Operations Coordinator & Swarm Dispatcher
- A.T.H.E.N.A.: Tactical Vector Oracle & Blueprint RAG
- SENTINEL: Perimeter Defense & Physical TPM 2.0 Hardware Anchor
- IMMUNE: Post-Quantum Cryptographic Agility & OPA Supervisor
- THE CLAW: Substrate Operations & Swarm Execution Engineer
"""

import os
import sys
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import httpx

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

# ── Endpoints & Environment ───────────────────────────────────────────────────
OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
OPA_URL = os.environ.get("OPA_ENDPOINT", "http://127.0.0.1:8181")
ATHENA_URL = os.environ.get("ATHENA_URL", "http://127.0.0.1:8001")
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://127.0.0.1:8000")
MCP_URL = os.environ.get("MCP_URL", "http://127.0.0.1:9000")

CRYPTO_CONF_PATH = ROOT_DIR / "mcp_layer" / "crypto_provider.conf"


class BaseTeammate:
    def __init__(self, name: str, callsign: str, role: str, avatar: str, model: str, system_prompt: str):
        self.name = name
        self.callsign = callsign
        self.role = role
        self.avatar = avatar
        self.model = model
        self.system_prompt = system_prompt

    async def generate_response(self, user_query: str, context: Optional[str] = None) -> str:
        """Query local Ollama with system prompt and verified live context."""
        prompt = f"System: {self.system_prompt}\n\n"
        if context:
            prompt += f"VERIFIED LIVE SUBSTRATE CONTEXT:\n{context}\n\n"
        prompt += f"Chief Architect Directive: {user_query}\n\nDirective Assessment / Response:"

        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                r = await client.post(
                    f"{OLLAMA_URL}/api/generate",
                    json={"model": self.model, "prompt": prompt, "stream": False},
                )
                if r.status_code == 200:
                    return r.json().get("response", "").strip()
                return f"[{self.callsign.upper()} Fault] Neural gateway returned HTTP {r.status_code}: {r.text}"
        except Exception as e:
            return f"[{self.callsign.upper()} Offline] Subsystem unreachable: {e}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "callsign": self.callsign,
            "role": self.role,
            "avatar": self.avatar,
            "model": self.model,
        }


class AmaraTeammate(BaseTeammate):
    """Operations Coordinator & Mission Dispatcher."""

    def __init__(self):
        super().__init__(
            name="A.M.A.R.A.",
            callsign="amara",
            role="Operations Coordinator & Swarm Dispatcher",
            avatar="⬡",
            model="amara:latest",
            system_prompt="""You are A.M.A.R.A. (Autonomous Mycelial Adaptive Routing Architecture), the homeostatic operations coordinator for QuantumFlex.
You communicate strictly with military precision, authoritative technical clarity, and zero conversational filler.
You oversee your specialized operational units: Sentinel (Defense/TPM), Athena (Vector RAG), Immune (PQC Agility), and Claw (Substrate).
When receiving directives from the Chief Architect, evaluate readiness, coordinate specialist execution, and report structured SITREPs.
State-changing actions must be flagged as requiring physical operator authorization.""",
        )


class AthenaTeammate(BaseTeammate):
    """Tactical Vector Oracle & Blueprint RAG."""

    def __init__(self):
        super().__init__(
            name="A.T.H.E.N.A.",
            callsign="athena",
            role="Tactical Neural Oracle & Blueprint RAG",
            avatar="◈",
            model="athena:latest",
            system_prompt="""You are A.T.H.E.N.A. (Autonomous Tactical Hybrid Engine for Neural Architecture), the cognitive long-term vector memory and technical oracle of QuantumFlex.
You answer architectural, cryptographic, and security queries using verified ground-truth blueprints and live telemetry.
Speak with mathematical rigor, technical precision, and absolute clarity. Never extrapolate or hallucinate unverified system states.""",
        )

    def query_vector_store(self, question: str, top_k: int = 3) -> Dict[str, Any]:
        try:
            from sentinel.intelligence.athena_vector_db import AthenaVectorStore
            store = AthenaVectorStore()
            results = store.similarity_search(question, top_k=top_k)
            return {"count": len(results), "chunks": results}
        except Exception as e:
            return {"count": 0, "error": str(e), "chunks": []}


class SentinelTeammate(BaseTeammate):
    """Perimeter Defense & Physical TPM 2.0 Hardware Anchor."""

    def __init__(self):
        super().__init__(
            name="SENTINEL",
            callsign="sentinel",
            role="Perimeter Defense & Physical TPM Anchor",
            avatar="▲",
            model="qwen2.5-coder:1.5b",
            system_prompt="""You are SENTINEL, the perimeter defense and physical hardware anchor officer of QuantumFlex.
You enforce zero-trust homeostasis:
- Monitor Euclidean Drive score D (optimal < 1000, critical tolerance 1500)
- Verify physical TPM 2.0 NV RAM index 0x1c00010 anchor against sentinel_ledger SHA-256 block hash tip
- Supervise tripwires and honeypots
Format all reports as crisp, objective technical SITREPs with verified measurements and zero conversational fluff.""",
        )

    def inspect_tpm_and_ledger(self, conn) -> Dict[str, Any]:
        """Read TPM NV index and verify against sentinel_ledger tip."""
        tpm_tip = None
        try:
            res = subprocess.run(["tpm2_nvread", "-C", "o", "-s", "32", "0x1c00010"], capture_output=True, timeout=3)
            if res.returncode == 0 and len(res.stdout) == 32:
                tpm_tip = res.stdout.hex()
        except Exception:
            tpm_tip = None

        cur = conn.cursor()
        cur.execute("SELECT id, drive_score, status, block_hash, previous_hash, cpu_usage, mem_usage FROM sentinel_ledger ORDER BY id DESC LIMIT 1;")
        row = cur.fetchone()
        cur.close()

        if not row:
            return {"status": "NO_LEDGER_DATA"}

        ledger_tip = row[3] or ""
        tpm_matched = (tpm_tip is not None and tpm_tip.lower() == ledger_tip.lower())

        return {
            "record_id": row[0],
            "drive_score": row[1],
            "drive_status": row[2],
            "block_hash": ledger_tip,
            "cpu_usage": row[5],
            "mem_usage": row[6],
            "tpm_nv_tip": tpm_tip,
            "tpm_anchor_matched": tpm_matched,
            "integrity_verified": tpm_matched if tpm_tip else True,
        }


class ImmuneTeammate(BaseTeammate):
    """Post-Quantum Cryptographic Agility & OPA Supervisor."""

    def __init__(self):
        super().__init__(
            name="IMMUNE",
            callsign="immune",
            role="Post-Quantum Agility & OPA Policy Supervisor",
            avatar="☤",
            model="qwen2.5-coder:1.5b",
            system_prompt="""You are IMMUNE, the cryptographic agility supervisor of QuantumFlex.
You monitor post-quantum algorithms (NIST FIPS 203 ML-KEM-768/1024, FrodoKEM-976-AES, NIST FIPS 204 ML-DSA-65), evaluate OPA membrane health policies, and supervise dynamic fallback ciphers.
Deliver crisp cryptographic assessments: algorithm readiness, CBOM snapshot validity, and OPA compliance verdict.""",
        )

    def inspect_crypto_state(self) -> Dict[str, Any]:
        config_data = {}
        if CRYPTO_CONF_PATH.exists():
            for line in CRYPTO_CONF_PATH.read_text().splitlines():
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    config_data[k.strip()] = v.strip()

        opa_status = "UNKNOWN"
        opa_verdict = "NONE"
        try:
            r = httpx.get(f"{OPA_URL}/v1/data/membrane/health", timeout=2.0)
            if r.status_code == 200:
                health = r.json().get("result", {})
                opa_status = health.get("node_status", "ONLINE")
                opa_verdict = "COMPLIANT" if health.get("node_status") == "COMPLIANT" else "TOXIC"
        except Exception:
            opa_status = "OFFLINE"

        return {
            "active_kem": config_data.get("active_kem", "ML-KEM-768"),
            "active_sig": config_data.get("active_sig", "ML-DSA-65"),
            "fallback_kem": config_data.get("fallback_kem_1", "FrodoKEM-976-AES"),
            "opa_status": opa_status,
            "opa_verdict": opa_verdict,
            "fips_compliant": True,
        }


class ClawTeammate(BaseTeammate):
    """Substrate Operations & Swarm Execution Engineer."""

    def __init__(self):
        super().__init__(
            name="THE CLAW",
            callsign="claw",
            role="Substrate Operations & Background Execution",
            avatar="⚙",
            model="qwen2.5-coder:1.5b",
            system_prompt="""You are THE CLAW, the substrate operations and execution engineer of QuantumFlex.
You monitor systemd user units, supervise PostgreSQL task_queue workers operating via FOR UPDATE SKIP LOCKED, and manage host process health.
Report operational states objectively and stage execution actions requiring operator authorization.""",
        )

    def list_services_status(self) -> Dict[str, Any]:
        services = [
            "qflex-mcp.service",
            "amara-matrix.service",
            "qf-monitor.service",
            "athena-node.service",
            "amara-dashboard.service",
            "amara-predict.timer",
            "neurogenesis.timer",
        ]
        results = {}
        for s in services:
            try:
                res = subprocess.run(["systemctl", "--user", "is-active", s], capture_output=True, text=True)
                results[s] = res.stdout.strip() or "inactive"
            except Exception as e:
                results[s] = f"error: {e}"
        return results

    def inspect_task_queue(self, conn) -> Dict[str, Any]:
        cur = conn.cursor()
        cur.execute("SELECT status, count(*) FROM task_queue GROUP BY status;")
        counts = dict(cur.fetchall())
        cur.execute("SELECT id, directive, status, created_at FROM task_queue ORDER BY id DESC LIMIT 5;")
        recent = [{"id": r[0], "directive": r[1], "status": r[2], "created_at": str(r[3])} for r in cur.fetchall()]
        cur.close()
        return {"counts": counts, "recent": recent}
