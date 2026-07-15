#!/usr/bin/env python3
"""
Quantum Flex — Automated Neurogenesis (Truth Log Pruning)
==========================================================
Maintains a rolling 7-day state window on memory_logs and sentinel_ledger.
Prevents OOM from unbounded telemetry accumulation (~3000 rows/day).

Designed for daily cron invocation via systemd .timer.
"""

import psycopg2
from datetime import datetime

# Superuser connection (must be able to DELETE from memory_logs)
DB_CONFIG = {
    "dbname": "telemetry",
    "user": "ghostnode",
    "password": "quantum_flex_auth",
    "host": "127.0.0.1",
    "port": "5432",
}

RETENTION_DAYS = 7


def prune_truth_log():
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] Neurogenesis Cycle Initiated — pruning telemetry older than {RETENTION_DAYS} days...")

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        # 1. Prune memory_logs (primary truth log)
        cur.execute(
            "DELETE FROM memory_logs WHERE timestamp < NOW() - INTERVAL '%s days'",
            (RETENTION_DAYS,),
        )
        memory_pruned = cur.rowcount

        # 2. Prune sentinel_ledger (structured telemetry)
        cur.execute(
            "DELETE FROM sentinel_ledger WHERE timestamp < NOW() - INTERVAL '%s days'",
            (RETENTION_DAYS,),
        )
        sentinel_pruned = cur.rowcount

        # 3. Prune telemetry_log (qf_monitor data) if it exists
        try:
            cur.execute(
                "DELETE FROM telemetry_log WHERE timestamp < NOW() - INTERVAL '%s days'",
                (RETENTION_DAYS,),
            )
            telemetry_pruned = cur.rowcount
        except Exception:
            conn.rollback()
            telemetry_pruned = 0

        # 4. Log the pruning event itself
        cur.execute(
            """INSERT INTO memory_logs (agent_id, action_taken, outcome)
               VALUES ('Neurogenesis', %s, %s)""",
            (
                f"PRUNE: {RETENTION_DAYS}-day rolling window enforced",
                f"Deleted {memory_pruned} memory_logs, {sentinel_pruned} sentinel_ledger, "
                f"{telemetry_pruned} telemetry_log rows.",
            ),
        )

        conn.commit()
        cur.close()
        conn.close()

        print(f"[{ts}] Pruning complete:")
        print(f"  memory_logs:    {memory_pruned} rows deleted")
        print(f"  sentinel_ledger: {sentinel_pruned} rows deleted")
        print(f"  telemetry_log:  {telemetry_pruned} rows deleted")

    except Exception as e:
        print(f"[{ts}] NEUROGENESIS FAILURE: {e}")


if __name__ == "__main__":
    prune_truth_log()
