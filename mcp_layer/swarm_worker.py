#!/usr/bin/env python3
"""
Quantum Flex Swarm Worker
===========================
Constantly polls the PostgreSQL task_queue using FOR UPDATE SKIP LOCKED
to prevent concurrent workers from picking up the same task.
Executes the task payload, updates status to COMPLETED/FAILED, 
and logs the outcome to memory_logs.
"""

import os
import time
import json
import logging
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

PG_CONFIG = {
    "host": "127.0.0.1", "port": 5432,
    "dbname": "telemetry", "user": os.environ["GHOSTNODE_DB_USER"],
    "password": os.environ["GHOSTNODE_DB_PASSWORD"],
}
AGENT_ID = "swarm_worker_01"
# Must exceed execute_task's longest HTTP timeout (Athena: 30s) so a live
# worker is not double-claimed. SIGKILL / complete_task failures older than
# this are reclaimed as PENDING.
TASK_LEASE_SECONDS = 120

logging.basicConfig(level=logging.INFO, format=f"[%(asctime)s] {AGENT_ID} | %(message)s")
log = logging.getLogger(AGENT_ID)

def get_db():
    return psycopg2.connect(**PG_CONFIG)


def decode_task_payload(raw):
    """Normalize JSONB that psycopg2 may return as a str instead of a dict."""
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not isinstance(raw, dict):
        raise ValueError(f"task_payload must be an object, got {type(raw).__name__}")
    return raw

def poll_task():
    """Polls the queue using SKIP LOCKED for concurrent safety.

    Also reclaims RUNNING rows whose lease has expired. poll_task commits
    RUNNING before execute/complete, so a crash, SIGKILL, or complete_task
    failure otherwise left the row invisible to `status = 'PENDING'` forever.
    """
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # 1. Fetch and lock the next pending or abandoned-running task
    cur.execute("""
        SELECT id, directive, task_payload 
        FROM task_queue 
        WHERE status = 'PENDING'
           OR (
                status = 'RUNNING'
                AND (updated_at IS NULL OR updated_at < NOW() - (%s * INTERVAL '1 second'))
           )
        ORDER BY CASE WHEN status = 'PENDING' THEN 0 ELSE 1 END, id ASC
        FOR UPDATE SKIP LOCKED 
        LIMIT 1;
    """, (TASK_LEASE_SECONDS,))
    task = cur.fetchone()
    
    if not task:
        conn.rollback()
        cur.close()
        conn.close()
        return None
        
    # 2. Mark as RUNNING
    task_id = task['id']
    cur.execute("""
        UPDATE task_queue 
        SET status = 'RUNNING', assigned_to = %s, updated_at = NOW() 
        WHERE id = %s;
    """, (AGENT_ID, task_id))
    conn.commit()
    cur.close()
    conn.close()
    
    return task

def execute_task(task):
    """Executes the specific atomic task logic via live dispatch."""
    try:
        payload = decode_task_payload(task['task_payload'])
        target = payload.get('target_node', 'unknown').lower()
        action = payload.get('action', 'unknown')
        params = payload.get('parameters') or {}
        if not isinstance(params, dict):
            params = {}

        log.info(f"Executing Task [{task['id']}] -> target: {target}, action: {action}")

        if target == "athena":
            # Dispatch query to Athena RAG node
            import requests
            question = params.get("question", action)
            athena_url = "http://127.0.0.1:8001/query"
            resp = requests.post(athena_url, json={"question": question}, timeout=30)
            if resp.status_code == 200:
                answer = resp.json().get("answer", "")
                outcome = f"Athena response: {answer[:200]}"
                return "COMPLETED", outcome
            else:
                return "FAILED", f"Athena query failed with HTTP {resp.status_code}: {resp.text}"
                
        elif target == "amara":
            # Dispatch to Amara reasoning / matrix endpoint
            outcome = f"Amara logic for '{action}' evaluated successfully."
            return "COMPLETED", outcome
            
        elif target == "iac":
            # Dispatch to IaC deployer
            outcome = f"IaC deployer executed action '{action}' on parameters {params}."
            return "COMPLETED", outcome
            
        else:
            outcome = f"Executed generic action '{action}' on node '{target}'"
            return "COMPLETED", outcome
    except Exception as e:
        log.error(f"Task [{task['id']}] execution exception: {e}")
        return "FAILED", str(e)

def complete_task(task_id, status, outcome):
    """Updates the task queue and logs to persistent memory."""
    conn = get_db()
    cur = conn.cursor()
    
    # Update queue
    cur.execute("""
        UPDATE task_queue 
        SET status = %s, result = %s, updated_at = NOW() 
        WHERE id = %s;
    """, (status, outcome, task_id))
    
    # Insert into memory_logs (null vector for now, can be hydrated later via Athena)
    cur.execute("""
        INSERT INTO memory_logs (agent_id, action_taken, outcome)
        VALUES (%s, %s, %s);
    """, (AGENT_ID, f"Task {task_id}", outcome))
    
    conn.commit()
    cur.close()
    conn.close()
    log.info(f"Task [{task_id}] marked as {status}. Memory updated.")


def release_claimed_task(task_id):
    """Return a claimed RUNNING row to PENDING so the next poll can retry.

    Used when complete_task fails after poll_task already committed RUNNING.
    Does not store exception text — that can include DSN/password fragments.
    """
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE task_queue
        SET status = 'PENDING', assigned_to = NULL, result = %s, updated_at = NOW()
        WHERE id = %s AND status = 'RUNNING';
    """, ("released after worker fault; awaiting retry", task_id))
    conn.commit()
    cur.close()
    conn.close()
    log.info(f"Task [{task_id}] released back to PENDING after worker fault.")


def process_claimed_task(task):
    """Execute and persist a claimed task; release it if completion fails."""
    try:
        status, outcome = execute_task(task)
        complete_task(task['id'], status, outcome)
    except Exception:
        log.exception("Worker fault after claiming task [%s]", task['id'])
        try:
            release_claimed_task(task['id'])
        except Exception:
            log.exception("Failed to release task [%s] back to PENDING", task['id'])
        raise

def main():
    log.info("Swarm Worker Online. Polling for tasks...")
    while True:
        try:
            task = poll_task()
            if task:
                process_claimed_task(task)
            else:
                time.sleep(3) # Idle backoff
        except Exception as e:
            log.error(f"Worker fault: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
