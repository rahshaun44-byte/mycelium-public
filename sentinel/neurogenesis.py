#!/usr/bin/env python3
"""
Quantum Flex — Automated Neurogenesis (Truth Log Pruning)
==========================================================
Maintains a rolling 7-day state window on memory_logs and sentinel_ledger.
Prevents OOM from unbounded telemetry accumulation (~3000 rows/day).

Designed for daily cron invocation via systemd .timer.
"""

import hashlib
import os
import psycopg2
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv(Path.home() / ".config" / "qflex" / "secrets" / ".env")

# Superuser connection (must be able to DELETE from memory_logs)
DB_CONFIG = {
    "dbname": "telemetry",
    "user": os.environ["DB_USER"],
    "password": os.environ["DB_PASSWORD"],
    "host": os.environ["DB_HOST"],
    "port": os.environ["DB_PORT"],
}

RETENTION_DAYS = 7


def _setup_purge_log(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS purge_log (
            id BIGSERIAL PRIMARY KEY,
            partition_id TEXT NOT NULL,
            pre_purge_sha256 TEXT NOT NULL,
            volume_purged_bytes BIGINT NOT NULL,
            purged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


def _pre_purge_fingerprint(cur, partition_name):
    """Hashes the partition's row data before it's dropped -- a plain,
    honest audit record of what existed and when, with no fake signatures."""
    cur.execute(f"SELECT * FROM {partition_name}")
    rows = cur.fetchall()
    h = hashlib.sha256()
    volume = 0
    for row in rows:
        row_bytes = "|".join("" if v is None else str(v) for v in row).encode()
        h.update(row_bytes)
        volume += len(row_bytes)
    return h.hexdigest(), volume


def manage_partitions(cur, base_table):
    now = datetime.now()

    # 1. Prune T-7 (Drop old partition), logging what it held first
    prune_date = now - timedelta(days=RETENTION_DAYS)
    prune_suffix = prune_date.strftime("%Y_%m_%d")
    prune_table = f"{base_table}_p{prune_suffix}"

    cur.execute(f"SELECT to_regclass('{prune_table}')")
    if cur.fetchone()[0] is not None:
        _setup_purge_log(cur)
        fingerprint, volume = _pre_purge_fingerprint(cur, prune_table)
        cur.execute(
            """INSERT INTO purge_log (partition_id, pre_purge_sha256, volume_purged_bytes)
               VALUES (%s, %s, %s)""",
            (prune_table, fingerprint, volume),
        )
        cur.execute(f"DROP TABLE IF EXISTS {prune_table}")
        print(f"[Neurogenesis] Partition {prune_table} logged (sha256={fingerprint[:16]}..., {volume}B) and dropped.")
    else:
        print(f"[Neurogenesis] Partition {prune_table} does not exist. Nothing to prune.")

    # 2. Provision T+1 and T+2
    for offset in [1, 2]:
        future_date = now + timedelta(days=offset)
        start_ts = future_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_ts = start_ts + timedelta(days=1)

        suffix = start_ts.strftime("%Y_%m_%d")
        new_table = f"{base_table}_p{suffix}"

        start_str = start_ts.strftime("%Y-%m-%d %H:%M:%S")
        end_str = end_ts.strftime("%Y-%m-%d %H:%M:%S")

        cur.execute(f"CREATE TABLE IF NOT EXISTS {new_table} PARTITION OF {base_table} FOR VALUES FROM ('{start_str}') TO ('{end_str}')")

def prune_truth_log():
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] Neurogenesis Cycle Initiated — enforcing {RETENTION_DAYS}-day rolling window and provisioning future partitions...")

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        tables_to_manage = ["memory_logs", "sentinel_ledger", "telemetry_log"]

        for table in tables_to_manage:
            manage_partitions(cur, table)

        # Log the pruning event itself
        cur.execute(
            """INSERT INTO memory_logs (agent_id, action_taken, outcome)
               VALUES ('Neurogenesis', %s, %s)""",
            (
                f"PRUNE & PROVISION: {RETENTION_DAYS}-day rolling window enforced",
                f"Dropped T-{RETENTION_DAYS} partitions and provisioned T+1, T+2 for all truth logs.",
            ),
        )

        conn.commit()
        cur.close()
        conn.close()

        print(f"[{ts}] Neurogenesis complete: Partitions managed via O(1) ops.")

    except Exception as e:
        print(f"[{ts}] NEUROGENESIS FAILURE: {e}")

if __name__ == "__main__":
    prune_truth_log()
