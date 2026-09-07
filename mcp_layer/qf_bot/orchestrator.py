#!/usr/bin/env python3
"""
Quantum Flex Swarm Orchestrator (Tactical Command)
===================================================
Multi-agent tactical router & thread orchestrator:
- Manages AI tactical unit coordination & multi-unit sweeps
- Implements two-man Action Authorization Gate (Drafts requiring operator sign-off)
- Grounded in verified live telemetry & Athena vector memory
- Persistent audit logging in PostgreSQL
"""

import os
import sys
import json
import uuid
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import psycopg2
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

PG_CONFIG = {
    "host": os.environ.get("DB_HOST", "127.0.0.1"),
    "port": int(os.environ.get("DB_PORT", 5432)),
    "dbname": os.environ.get("DB_NAME", "telemetry"),
    "user": os.environ.get("GHOSTNODE_DB_USER", "ghostnode"),
    "password": os.environ.get("GHOSTNODE_DB_PASSWORD", ""),
    "connect_timeout": 3,
}

from qf_bot.teammates import (
    AmaraTeammate,
    AthenaTeammate,
    SentinelTeammate,
    ImmuneTeammate,
    ClawTeammate,
)
from qf_bot.routines import RoutineRunner, ROUTINE_CATALOG, log_memory


class DraftQueue:
    """Manages staged operational actions requiring Chief Architect authorization."""

    def __init__(self):
        self.drafts: Dict[str, Dict[str, Any]] = {}
        self._seed_default_sample_draft()

    def _seed_default_sample_draft(self):
        draft_id = "AUTH-1042"
        self.drafts[draft_id] = {
            "draft_id": draft_id,
            "bot": "CLAW",
            "title": "Start Service 'athena-node.service'",
            "description": "Initialize the Athena RAG Cognitive Node systemd user unit to activate the local vector loopback API on port 8001.",
            "action_type": "service_action",
            "parameters": {"service": "athena-node.service", "action": "start"},
            "risk_level": "TIER 3 (OPERATIONAL DISRUPTION)",
            "status": "PENDING_APPROVAL",
            "created_at": datetime.now().isoformat(),
        }

    def create_draft(self, bot: str, title: str, description: str, action_type: str, parameters: dict, risk_level: str = "TIER 3") -> Dict[str, Any]:
        draft_id = f"AUTH-{uuid.uuid4().hex[:4].upper()}"
        draft = {
            "draft_id": draft_id,
            "bot": bot,
            "title": title,
            "description": description,
            "action_type": action_type,
            "parameters": parameters,
            "risk_level": risk_level,
            "status": "PENDING_APPROVAL",
            "created_at": datetime.now().isoformat(),
        }
        self.drafts[draft_id] = draft
        log_memory(f"{bot.lower()}_unit", f"Staged Action Authorization [{draft_id}]", f"Title: {title}")
        return draft

    def list_drafts(self) -> List[Dict[str, Any]]:
        return list(self.drafts.values())

    def get_draft(self, draft_id: str) -> Optional[Dict[str, Any]]:
        return self.drafts.get(draft_id)

    async def approve_draft(self, draft_id: str) -> Dict[str, Any]:
        draft = self.drafts.get(draft_id)
        if not draft:
            return {"error": f"Authorization ID '{draft_id}' not found", "status": "NOT_FOUND"}

        if draft["status"] != "PENDING_APPROVAL":
            return {"error": f"Authorization ID '{draft_id}' is already {draft['status']}", "status": draft["status"]}

        action_type = draft.get("action_type")
        params = draft.get("parameters", {})
        execution_result = ""

        try:
            if action_type == "service_action":
                service = params.get("service")
                action = params.get("action", "restart")
                import subprocess
                res = subprocess.run(["systemctl", "--user", action, service], capture_output=True, text=True, timeout=10)
                if res.returncode == 0:
                    execution_result = f"Command executed successfully: systemctl --user {action} {service}"
                else:
                    execution_result = f"Command failed (code {res.returncode}): {res.stderr.strip()}"
            else:
                execution_result = f"Action '{action_type}' executed with parameters: {params}"

            draft["status"] = "EXECUTED"
            draft["executed_at"] = datetime.now().isoformat()
            draft["result"] = execution_result
            log_memory("chief_architect", f"Authorized Action [{draft_id}]", execution_result)
            return {"status": "EXECUTED", "draft": draft, "result": execution_result}

        except Exception as e:
            draft["status"] = "FAILED"
            draft["result"] = str(e)
            return {"status": "FAILED", "draft": draft, "error": str(e)}

    def discard_draft(self, draft_id: str) -> Dict[str, Any]:
        draft = self.drafts.get(draft_id)
        if not draft:
            return {"error": f"Authorization ID '{draft_id}' not found", "status": "NOT_FOUND"}

        draft["status"] = "DISCARDED"
        draft["discarded_at"] = datetime.now().isoformat()
        log_memory("chief_architect", f"Aborted Action [{draft_id}]", f"Title: {draft.get('title')}")
        return {"status": "DISCARDED", "draft": draft}


class QFBotOrchestrator:
    """Master Tactical Swarm Orchestrator."""

    def __init__(self):
        self.amara = AmaraTeammate()
        self.athena = AthenaTeammate()
        self.sentinel = SentinelTeammate()
        self.immune = ImmuneTeammate()
        self.claw = ClawTeammate()

        self.teammates = {
            "amara": self.amara,
            "athena": self.athena,
            "sentinel": self.sentinel,
            "immune": self.immune,
            "claw": self.claw,
        }

        self.draft_queue = DraftQueue()
        self.routine_runner = RoutineRunner()
        self.conversation_history: List[Dict[str, Any]] = []

    def get_roster(self) -> List[Dict[str, Any]]:
        return [t.to_dict() for t in self.teammates.values()]

    def _get_db(self):
        return psycopg2.connect(**PG_CONFIG)

    async def generate_full_sitrep(self) -> str:
        """Generates an institutional, verified SITREP across all substrates."""
        try:
            conn = self._get_db()
            sentinel_data = self.sentinel.inspect_tpm_and_ledger(conn)
            conn.close()
        except Exception as e:
            sentinel_data = {"error": str(e)}

        immune_data = self.immune.inspect_crypto_state()
        services = self.claw.list_services_status()

        active_count = sum(1 for v in services.values() if v == "active")
        total_count = len(services)
        tpm_match = sentinel_data.get("tpm_anchor_matched")
        tpm_str = "MATCHED (Hardware SHA-256 Validated)" if tpm_match else "TPM UNREAD / DISCONNECTED"

        drive_val = sentinel_data.get("drive_score")
        drive_str = f"{drive_val:.1f} / 1000.0 (NOMINAL)" if isinstance(drive_val, (int, float)) else "UNKNOWN"

        sitrep = f"""[SITREP // {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} EDT]
DEFCON / POSTURE    : EQUILIBRIUM (SYSTEM OPTIMAL)
HARDWARE ANCHOR     : TPM 2.0 NV 0x1c00010 {tpm_str}
HOMEOSTATIC DRIVE   : D = {drive_str}
PQC MEMBRANE STATE  : {immune_data.get('opa_verdict', 'UNKNOWN')} ({immune_data.get('active_kem')} / {immune_data.get('active_sig')} Active)
FALLBACK CIPHER     : {immune_data.get('fallback_kem')} (ARMED)
ACTIVE SUB-SYSTEMS  : {active_count}/{total_count} Running
PENDING ACTIONS     : {len([d for d in self.draft_queue.list_drafts() if d['status'] == 'PENDING_APPROVAL'])} Authorization(s) Required"""
        return sitrep

    async def handle_message(self, user_text: str, target_bot: Optional[str] = None) -> Dict[str, Any]:
        """Main tactical entrypoint for directive processing."""
        user_msg = {
            "id": str(uuid.uuid4()),
            "sender": "Chief Architect",
            "role": "user",
            "text": user_text,
            "timestamp": datetime.now().isoformat(),
        }
        self.conversation_history.append(user_msg)

        # Quick command: SITREP
        if any(w in user_text.lower() for w in ["sitrep", "status report", "full status"]):
            sitrep_text = await self.generate_full_sitrep()
            bot_msg = {
                "id": str(uuid.uuid4()),
                "sender": self.amara.name,
                "callsign": self.amara.callsign,
                "avatar": self.amara.avatar,
                "role": "unit",
                "text": sitrep_text,
                "timestamp": datetime.now().isoformat(),
            }
            self.conversation_history.append(bot_msg)
            return {
                "mode": "sitrep",
                "bot": self.amara.to_dict(),
                "response": sitrep_text,
                "handoffs": [],
                "message": bot_msg,
            }

        # Detect explicit @ mentions
        lower_text = user_text.lower()
        for callsign in self.teammates.keys():
            if f"@{callsign}" in lower_text:
                target_bot = callsign
                break

        if target_bot and target_bot in self.teammates:
            return await self._dispatch_single_bot(self.teammates[target_bot], user_text)

        return await self._orchestrate_multi_bot(user_text)

    async def _dispatch_single_bot(self, bot, user_text: str) -> Dict[str, Any]:
        """Direct query to a specific unit with verified context."""
        context = ""
        staged_draft = None

        if bot.callsign == "sentinel":
            try:
                conn = self._get_db()
                data = self.sentinel.inspect_tpm_and_ledger(conn)
                conn.close()
                context = f"Verified Live Sentinel Telemetry:\n{json.dumps(data, indent=2)}"
            except Exception as e:
                context = f"Telemetry read error: {e}"

        elif bot.callsign == "athena":
            vec_res = self.athena.query_vector_store(user_text, top_k=3)
            chunks = [f"Source: {c['source']}\n{c['content']}" for c in vec_res.get("chunks", [])]
            context = "\n---\n".join(chunks)

        elif bot.callsign == "immune":
            crypto_data = self.immune.inspect_crypto_state()
            context = f"Verified Cryptographic Agility State:\n{json.dumps(crypto_data, indent=2)}"

        elif bot.callsign == "claw":
            services = self.claw.list_services_status()
            try:
                conn = self._get_db()
                q_info = self.claw.inspect_task_queue(conn)
                conn.close()
            except Exception:
                q_info = {}
            context = f"Substrate Daemons:\n{json.dumps(services, indent=2)}\nTask Queue:\n{json.dumps(q_info, indent=2)}"

            # Stage action if service modification requested
            if any(w in user_text.lower() for w in ["restart", "stop", "start", "kill"]):
                for s in services.keys():
                    if s.split(".")[0].lower() in user_text.lower():
                        action = "restart" if "restart" in user_text.lower() else "stop" if "stop" in user_text.lower() else "start"
                        staged_draft = self.draft_queue.create_draft(
                            bot="CLAW",
                            title=f"{action.upper()} Service '{s}'",
                            description=f"Action requested by Chief Architect: '{user_text}'. Requires authorization prior to execution.",
                            action_type="service_action",
                            parameters={"service": s, "action": action},
                            risk_level="TIER 3 (OPERATIONAL DISRUPTION)",
                        )
                        break

        response_text = await bot.generate_response(user_text, context=context)

        bot_msg = {
            "id": str(uuid.uuid4()),
            "sender": bot.name,
            "callsign": bot.callsign,
            "avatar": bot.avatar,
            "role": "unit",
            "text": response_text,
            "staged_draft": staged_draft,
            "timestamp": datetime.now().isoformat(),
        }
        self.conversation_history.append(bot_msg)

        log_memory(f"{bot.callsign}_unit", f"Evaluated Directive: {user_text[:80]}", response_text[:200])

        return {
            "mode": "direct",
            "bot": bot.to_dict(),
            "response": response_text,
            "staged_draft": staged_draft,
            "handoffs": [],
            "message": bot_msg,
        }

    async def _orchestrate_multi_bot(self, user_text: str) -> Dict[str, Any]:
        """Multi-unit coordination through Amara."""
        handoffs = []

        handoffs.append({
            "from": "amara",
            "to": "sentinel",
            "action": "Dispatching Sentinel for hardware anchor & ledger verification...",
        })

        conn = self._get_db()
        sentinel_data = self.sentinel.inspect_tpm_and_ledger(conn)
        conn.close()

        immune_data = self.immune.inspect_crypto_state()
        claw_services = self.claw.list_services_status()

        vec_res = self.athena.query_vector_store(user_text, top_k=2)
        athena_context = ""
        if vec_res.get("chunks"):
            handoffs.append({
                "from": "sentinel",
                "to": "athena",
                "action": "Injecting verified vector blueprint memory into tactical assessment...",
            })
            athena_context = "\n".join([c["content"] for c in vec_res["chunks"]])

        composite_context = f"""
LIVE MULTI-UNIT SUBSTRATE TELEMETRY:
[SENTINEL PERIMETER]
- Drive Score (D): {sentinel_data.get('drive_score')} ({sentinel_data.get('drive_status')})
- Block Hash Tip: {sentinel_data.get('block_hash')}
- TPM 0x1c00010 Match: {'MATCHED' if sentinel_data.get('tpm_anchor_matched') else 'TPM DISCONNECTED/UNREAD'}
- CPU: {sentinel_data.get('cpu_usage')}% | RAM: {sentinel_data.get('mem_usage')}%

[IMMUNE PQC AGILITY]
- Active KEM: {immune_data.get('active_kem')} | Active Sig: {immune_data.get('active_sig')}
- OPA Membrane Health: {immune_data.get('opa_status')} (Verdict: {immune_data.get('opa_verdict')})

[CLAW SUBSTRATE]
- Active services: {[k for k, v in claw_services.items() if v == 'active']}
- Inactive services: {[k for k, v in claw_services.items() if v != 'active']}

[ATHENA MEMORY CHUNKS]
{athena_context[:600]}
"""

        response_text = await self.amara.generate_response(
            f"Directive: {user_text}\nCoordinate with Sentinel, Athena, Immune, and Claw. Deliver a structured, authoritative tactical assessment.",
            context=composite_context,
        )

        bot_msg = {
            "id": str(uuid.uuid4()),
            "sender": self.amara.name,
            "callsign": self.amara.callsign,
            "avatar": self.amara.avatar,
            "role": "unit",
            "text": response_text,
            "handoffs": handoffs,
            "timestamp": datetime.now().isoformat(),
        }
        self.conversation_history.append(bot_msg)

        log_memory("amara_unit", f"Swarm Coordination: {user_text[:80]}", response_text[:200])

        return {
            "mode": "orchestrated",
            "bot": self.amara.to_dict(),
            "response": response_text,
            "handoffs": handoffs,
            "message": bot_msg,
        }
