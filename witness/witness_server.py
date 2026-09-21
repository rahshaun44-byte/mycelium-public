#!/usr/bin/env python3
"""
QuantumFlex Monotonic Witness Server
====================================
Independent external anti-rollback witness arbiter (Gate 5 / QF_EXTERNAL_CHECKPOINT_V1).
Enforces the monotonic invariant: sequence > highest_witnessed_sequence.
Operates with atomic SQLite WAL persistence and zero external dependencies.
"""

import http.server
import json
import os
import sqlite3
import sys
import threading
import time
from typing import Tuple, Dict, Any

BIND_ADDR = os.environ.get("WITNESS_BIND_ADDR", "127.0.0.1:8444")
DATA_DIR = os.environ.get("WITNESS_DATA_DIR", "/data")
DB_PATH = os.path.join(DATA_DIR, "witness_checkpoints.db")

os.makedirs(DATA_DIR, exist_ok=True)

# ── Database Initialization ──────────────────────────────────────────────────

def init_db(db_path: str):
    conn = sqlite3.connect(db_path, timeout=10.0)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = FULL;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS authoritative_checkpoints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id TEXT NOT NULL,
            sequence INTEGER NOT NULL,
            state_digest TEXT NOT NULL,
            policy_digest TEXT,
            checkpoint_epoch INTEGER,
            previous_checkpoint_digest TEXT,
            signer_key_id TEXT,
            signature TEXT,
            received_at_ns INTEGER NOT NULL
        );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_node_seq ON authoritative_checkpoints (node_id, sequence);")
    conn.commit()
    conn.close()

init_db(DB_PATH)
db_lock = threading.Lock()

# ── Checkpoint Verification & Ingestion ──────────────────────────────────────

def ingest_checkpoint(cp: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    # 1. Schema check
    node_id = cp.get("node_id", "default_node")
    sequence = cp.get("sequence")
    state_digest = cp.get("state_digest")

    if sequence is None or not isinstance(sequence, int) or sequence < 1:
        return 400, {"status": "REJECTED", "error": "Invalid or missing sequence"}
    if not state_digest or not isinstance(state_digest, str):
        return 400, {"status": "REJECTED", "error": "Invalid or missing state_digest"}

    # Disallow IEEE-754 precision breach
    if sequence > 9007199254740991:
        return 400, {"status": "REJECTED", "error": "Sequence exceeds IEEE-754 ceiling (2^53 - 1)"}

    with db_lock:
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        try:
            cur = conn.cursor()
            cur.execute("SELECT COALESCE(MAX(sequence), 0) FROM authoritative_checkpoints WHERE node_id = ?", (node_id,))
            highest_seq = cur.fetchone()[0]

            # 2. Monotonic Anti-Rollback Gate
            if sequence <= highest_seq and highest_seq != 0:
                err_msg = f"MONOTONIC ROLLBACK DETECTED: sequence {sequence} <= highest witnessed {highest_seq}"
                sys.stderr.write(f"[WITNESS ALERT] {err_msg}\n")
                return 409, {
                    "status": "REJECTED",
                    "error": err_msg,
                    "attempted_sequence": sequence,
                    "highest_witnessed": highest_seq
                }

            # 3. Commit checkpoint
            now_ns = time.time_ns()
            cur.execute("""
                INSERT INTO authoritative_checkpoints 
                (node_id, sequence, state_digest, policy_digest, checkpoint_epoch, 
                 previous_checkpoint_digest, signer_key_id, signature, received_at_ns)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                node_id,
                sequence,
                state_digest,
                cp.get("policy_digest", ""),
                cp.get("checkpoint_epoch", int(time.time())),
                cp.get("previous_checkpoint_digest", ""),
                cp.get("signer_key_id", ""),
                cp.get("signature", ""),
                now_ns
            ))
            conn.commit()
            sys.stdout.write(f"[WITNESS COMMITTED] Node '{node_id}' sequence {sequence} committed.\n")
            sys.stdout.flush()
            return 201, {
                "status": "COMMITTED",
                "node_id": node_id,
                "sequence": sequence,
                "state_digest": state_digest,
                "committed_at_ns": now_ns
            }
        finally:
            conn.close()

def get_highest_sequence(node_id: str = "default_node") -> int:
    with db_lock:
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        try:
            cur = conn.cursor()
            cur.execute("SELECT COALESCE(MAX(sequence), 0) FROM authoritative_checkpoints WHERE node_id = ?", (node_id,))
            return cur.fetchone()[0]
        finally:
            conn.close()

# ── HTTP Request Handler ─────────────────────────────────────────────────────

class WitnessHTTPHandler(http.server.BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        if self.path in ("/health", "/healthz", "/status"):
            highest = get_highest_sequence()
            self._send_json(200, {
                "status": "HEALTHY",
                "service": "quantumflex-monotonic-witness",
                "highest_witnessed_sequence": highest
            })
        elif self.path.startswith("/v1/checkpoint"):
            highest = get_highest_sequence()
            self._send_json(200, {
                "highest_sequence": highest
            })
        else:
            self._send_json(404, {"error": "Not Found"})

    def do_POST(self):
        if self.path in ("/v1/checkpoint", "/checkpoint"):
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length <= 0 or content_length > 65536:
                self._send_json(400, {"error": "Invalid Content-Length (max 64 KiB)"})
                return

            body = self.rfile.read(content_length)
            try:
                data = json.loads(body.decode("utf-8"))
            except Exception as e:
                self._send_json(400, {"error": f"JSON decode failed: {str(e)}"})
                return

            status_code, resp_data = ingest_checkpoint(data)
            self._send_json(status_code, resp_data)
        else:
            self._send_json(404, {"error": "Not Found"})

    def _send_json(self, status: int, data: Dict[str, Any]):
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        # Override to keep logs clean
        sys.stdout.write(f"[WITNESS HTTP] {self.address_string()} - {format % args}\n")
        sys.stdout.flush()

def main():
    if ":" in BIND_ADDR:
        host, port_str = BIND_ADDR.rsplit(":", 1)
        port = int(port_str)
    else:
        host = "127.0.0.1"
        port = int(BIND_ADDR)

    server = http.server.ThreadingHTTPServer((host, port), WitnessHTTPHandler)
    print(f"[+] QuantumFlex Monotonic Witness listening on {host}:{port}")
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[*] Witness shutting down cleanly.")
    finally:
        server.server_close()

if __name__ == "__main__":
    main()
