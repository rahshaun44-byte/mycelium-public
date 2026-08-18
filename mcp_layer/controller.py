#!/usr/bin/env python3
"""
Quantum Flex Swarm Controller (The Claw)
==========================================
Agent Orchestrator. Accepts a single complex directive and breaks it down
into atomic tasks. It feeds these tasks into the local Ollama instance
for structuring, strictly validates against TaskSchema (Pydantic gate),
and inserts them into the PostgreSQL task_queue via SKIP LOCKED pattern.
"""

import os
import sys
import json
import logging
import asyncio
from datetime import datetime
from pathlib import Path
import psycopg2
from pydantic import BaseModel, Field, ValidationError
import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ── Configuration ─────────────────────────────────────────────────────────────
OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:1.5b")
PG_CONFIG = {
    "host": os.environ.get("DB_HOST", "127.0.0.1"),
    "port": int(os.environ.get("DB_PORT", 5432)),
    "dbname": os.environ.get("DB_NAME", "telemetry"),
    "user": os.environ.get("GHOSTNODE_DB_USER", "ghostnode"),
    "password": os.environ.get("GHOSTNODE_DB_PASSWORD", ""),
}

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] CONTROLLER | %(message)s")
log = logging.getLogger("claw")

from typing import Literal

# ── Pydantic Schema Validation Gate ───────────────────────────────────────────
class TaskSchema(BaseModel):
    target_node: Literal["amara", "athena", "iac"] = Field(..., description="Target node: amara, athena, or iac")
    action: str = Field(..., min_length=2, description="Action or operation name")
    parameters: dict = Field(default_factory=dict, description="Parameters dictionary")

# ── Orchestrator Logic ────────────────────────────────────────────────────────
def init_db():
    conn = psycopg2.connect(**PG_CONFIG)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS task_queue (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            status VARCHAR(20) DEFAULT 'PENDING',
            directive TEXT NOT NULL,
            task_payload JSONB NOT NULL,
            assigned_to VARCHAR(50),
            result TEXT,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)
    conn.commit()
    return conn

async def generate_tasks(directive: str) -> list[dict]:
    """Uses the local LLM to break down the directive, gating strictly with TaskSchema."""
    prompt = f"""You are the QuantumFlex Agent Orchestrator. Break down this directive into a JSON array of atomic sub-tasks.
Each task object MUST strictly follow this JSON structure:
{{
  "target_node": "amara" | "athena" | "iac",
  "action": "string describing the action",
  "parameters": {{}}
}}

Directive: {directive}

Return ONLY a valid JSON array of objects."""

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(f"{OLLAMA_URL}/api/generate", json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json"
        })
        r.raise_for_status()
        response_text = r.json().get("response", "[]")
        
    try:
        raw = json.loads(response_text)
        if isinstance(raw, dict):
            if "tasks" in raw and isinstance(raw["tasks"], list):
                raw_list = raw["tasks"]
            else:
                raw_list = [raw]
        elif isinstance(raw, list):
            raw_list = raw
        else:
            raise ValueError(f"Unexpected JSON root type: {type(raw)}")

        validated_tasks = []
        for item in raw_list:
            # Enforce Pydantic validation gate
            task_obj = TaskSchema.model_validate(item)
            node = task_obj.target_node.strip().lower()
            if node not in ("amara", "athena", "iac"):
                raise ValueError(f"Invalid target_node '{node}'. Must be 'amara', 'athena', or 'iac'.")
            task_dict = task_obj.model_dump()
            task_dict["target_node"] = node
            validated_tasks.append(task_dict)

        return validated_tasks

    except (json.JSONDecodeError, ValidationError, ValueError) as e:
        log.error(f"Pydantic Validation Gate REJECTED LLM output: {e}")
        return []

def queue_task(conn, directive: str, payload: dict):
    """Inserts a validated task into the PostgreSQL task_queue."""
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO task_queue (directive, task_payload, status)
        VALUES (%s, %s, 'PENDING')
        RETURNING id;
    """, (directive, json.dumps(payload)))
    task_id = cur.fetchone()[0]
    conn.commit()
    log.info(f"Queued Task [{task_id}] -> Node: {payload.get('target_node')} | Action: {payload.get('action')}")
    return task_id

async def main(directive: str):
    log.info(f"Received Directive: {directive}")
    conn = init_db()
    
    log.info(f"Querying {MODEL} for task breakdown...")
    tasks = await generate_tasks(directive)
    
    if not tasks:
        log.warning("No valid tasks generated or validation gate failed. Swarm initiation aborted.")
        sys.exit(1)
        
    log.info(f"Pydantic Gate Passed: {len(tasks)} validated sub-tasks. Queuing...")
    for t in tasks:
        queue_task(conn, directive, t)
        
    log.info("Swarm Orchestration Complete.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 controller.py '<directive>'")
        sys.exit(1)
    
    asyncio.run(main(sys.argv[1]))
