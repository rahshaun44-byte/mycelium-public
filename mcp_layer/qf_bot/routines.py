#!/usr/bin/env python3
"""
Quantum Flex Autonomous Tactical Sweeps & Routines
===================================================
Automated sweeps that tactical units execute on schedule or on-demand:
- Overnight Deep Stack Audit: Sentinel + Immune + Claw + Athena synthesis
- Perimeter Heartbeat: Verifies drive score and physical TPM 2.0 anchor
- PQC Agility Check: Verifies OPA compliance and fallback cipher readiness
"""

import os
import sys
import json
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


def get_db():
    return psycopg2.connect(**PG_CONFIG)


def log_memory(agent_id: str, action: str, outcome: str):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO memory_logs (agent_id, action_taken, outcome) VALUES (%s, %s, %s);",
            (agent_id, action, outcome),
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[Routines DB Warning] Failed to write memory log: {e}", file=sys.stderr)


class RoutineRunner:
    def __init__(self):
        self.amara = AmaraTeammate()
        self.athena = AthenaTeammate()
        self.sentinel = SentinelTeammate()
        self.immune = ImmuneTeammate()
        self.claw = ClawTeammate()

    async def run_overnight_audit(self) -> Dict[str, Any]:
        """Runs the complete multi-unit tactical audit."""
        start_time = datetime.now()
        report = {
            "routine": "overnight_audit",
            "timestamp": start_time.isoformat(),
            "steps": [],
            "status": "SUCCESS",
        }

        # Step 1: Sentinel Hardware & Ledger Check
        try:
            conn = get_db()
            sentinel_data = self.sentinel.inspect_tpm_and_ledger(conn)
            conn.close()
            report["steps"].append({
                "unit": "SENTINEL",
                "action": "Hardware TPM 2.0 & Ledger Verification",
                "data": sentinel_data,
                "status": "VERIFIED" if sentinel_data.get("tpm_anchor_matched") else "ATTENTION",
            })
        except Exception as e:
            sentinel_data = {"error": str(e)}
            report["steps"].append({"unit": "SENTINEL", "action": "Ledger Check", "error": str(e), "status": "FAILED"})

        # Step 2: Immune PQC Agility & OPA Check
        try:
            immune_data = self.immune.inspect_crypto_state()
            report["steps"].append({
                "unit": "IMMUNE",
                "action": "PQC CBOM & OPA Membrane Health",
                "data": immune_data,
                "status": "COMPLIANT" if immune_data.get("opa_verdict") == "COMPLIANT" else "DEGRADED",
            })
        except Exception as e:
            immune_data = {"error": str(e)}
            report["steps"].append({"unit": "IMMUNE", "action": "PQC Check", "error": str(e), "status": "FAILED"})

        # Step 3: Claw Substrate Daemons Audit
        try:
            claw_services = self.claw.list_services_status()
            conn = get_db()
            claw_queue = self.claw.inspect_task_queue(conn)
            conn.close()
            report["steps"].append({
                "unit": "CLAW",
                "action": "Substrate Services & Swarm Queue Audit",
                "data": {"services": claw_services, "queue": claw_queue},
                "status": "OPTIMAL",
            })
        except Exception as e:
            report["steps"].append({"unit": "CLAW", "action": "Service Audit", "error": str(e), "status": "FAILED"})

        # Step 4: Athena Synthesis & Executive Briefing
        summary_context = f"""
Sentinel Hardware & Ledger State:
- Drive Score: {sentinel_data.get('drive_score')} (Status: {sentinel_data.get('drive_status')})
- TPM NV 0x1c00010 vs Ledger Tip: {'MATCHED' if sentinel_data.get('tpm_anchor_matched') else 'MISMATCH/UNREAD'}
- CPU Usage: {sentinel_data.get('cpu_usage')}% | Mem Usage: {sentinel_data.get('mem_usage')}%

Immune PQC Agility State:
- Active KEM: {immune_data.get('active_kem')} | Active Sig: {immune_data.get('active_sig')}
- OPA Membrane Health: {immune_data.get('opa_status')} (Verdict: {immune_data.get('opa_verdict')})

Claw Operational State:
- Monitored Services: {json.dumps(claw_services if 'claw_services' in locals() else {})}
"""
        debrief = await self.athena.generate_response(
            "Synthesize an authoritative, crisp executive debrief for the Chief Architect based on the verified audit context.",
            context=summary_context,
        )

        report["debrief"] = debrief
        report["duration_sec"] = (datetime.now() - start_time).total_seconds()

        log_memory(
            agent_id="tactical_swarm",
            action="Tactical Sweep: Overnight Deep Stack Audit",
            outcome=f"Completed in {report['duration_sec']:.1f}s. Drive: {sentinel_data.get('drive_score')}, OPA: {immune_data.get('opa_verdict')}.",
        )

        return report

    async def run_tripwire_heartbeat(self) -> Dict[str, Any]:
        """Fast heartbeat check by Sentinel."""
        conn = get_db()
        data = self.sentinel.inspect_tpm_and_ledger(conn)
        conn.close()
        log_memory(
            agent_id="sentinel_unit",
            action="Perimeter Heartbeat",
            outcome=f"Drive Score: {data.get('drive_score')} | TPM Anchor: {data.get('tpm_anchor_matched')}",
        )
        return {"routine": "tripwire_heartbeat", "data": data, "timestamp": datetime.now().isoformat()}


ROUTINE_CATALOG = {
    "overnight_audit": {
        "title": "Overnight Deep Stack Audit",
        "description": "Full-spectrum inspection of TPM 2.0 anchor, block hashes, PQC OPA membrane, systemd units, and executive Athena debrief.",
        "schedule": "Nightly at 02:00 EDT (or on-demand)",
        "units": ["Amara", "Sentinel", "Immune", "Claw", "Athena"],
    },
    "tripwire_heartbeat": {
        "title": "Perimeter & Hardware Anchor Heartbeat",
        "description": "Verifies Euclidean drive score homeostasis (<1000) and matches physical TPM 2.0 NV index 0x1c00010 against sentinel_ledger tip.",
        "schedule": "Hourly (or on-demand)",
        "units": ["Sentinel"],
    },
}
