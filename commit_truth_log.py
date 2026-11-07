#!/usr/bin/env python3
import os
import sqlite3
import hashlib
from datetime import datetime, timezone

DOC_DIR = os.path.expanduser("~/mycelium/docs")
DOC_PATH = os.path.join(DOC_DIR, "TRUTH-LOG-2026-11-07-MERMIN-BELL-MOBILE-MESH.md")
DB_PATH = os.path.expanduser("~/quantum-flex/data/ledger.db")

SPEC_CONTENT = """# QUANTUMFLEX TRUTH LOG & ARCHITECTURAL SPECIFICATION
**Document ID:** QF-TL-2026-11-05-001  
**Component:** `pqc-immune-daemon` / Mycelium Service Plane / Stratum 0 Witness  
**External Grant Reference:** NLnet Foundation Application `2026-11-4af`  
**Hardware Baseline:** `qfx-yoga` (Ubuntu 26.04.1 LTS, Pluton TPM 2.0, Loopback Air-Gap)  
**Governing Invariant:** $Y = f(x - h) + k$  

## 1. Executive Abstract
QuantumFlex resolves Byzantine fault tolerance (BFT) and TOCTOU race conditions on bare-metal edge nodes without O(n^2) consensus voting storms by implementing the physical mechanics of a biological nervous system's intracellular microtubule lattice and axonal refractory window: Y = f(x - h) + k.

## 2. Variable Mapping
- x (Event-vs-Hold Cycle): Raw ingress payload arriving at the loopback/Tailscale boundary (100.64.0.0/10 -> 127.0.0.1).
- h (Entropy Shunting): Malformed packets, forged Ed25519/ML-DSA-65 tokens, or D-2 policy failures shunted to the Ghost Node quarantine sink (Landauer-compliant shock absorber).
- k (Refractory Memory Window Hold): Synchronous policy lock across OPA Gate (127.0.0.1:8181) and Stratum 0 Monotonic Witness (127.0.0.1:8444) preventing TOCTOU state mutation during PQC cipher transitions (FrodoKEM-976-AES <-> ML-KEM-768).
- Y (Deterministic Commit): Append-only state transition committed to quantum_flex_engine (127.0.0.1:9444) and hash-chained SQLite ledger.db, anchored by QF-A5 provenance and IBM Quantum GHZ coherence certification (ibm_kingston Job dbl33e56p51s73cnltvg, F = 0.9355, W = -0.4355).
"""

def commit_truth_log():
    os.makedirs(DOC_DIR, exist_ok=True)
    if not os.path.exists(DOC_PATH):
        with open(DOC_PATH, "w", encoding="utf-8") as f:
            f.write(SPEC_CONTENT)
    
    with open(DOC_PATH, "rb") as f:
        doc_sha256 = hashlib.sha256(f.read()).hexdigest()
    print(f"[+] Specification referenced: {DOC_PATH}")
    print(f"[+] Document SHA-256 Digest:   {doc_sha256}")

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Ensure table exists with exact schema expected by master audit script
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_runs (
            id INTEGER PRIMARY KEY,
            timestamp TEXT NOT NULL,
            event_data TEXT NOT NULL,
            prev_hash TEXT NOT NULL,
            current_hash TEXT NOT NULL
        );
    """)

    cursor.execute("SELECT id, current_hash FROM audit_runs ORDER BY id DESC LIMIT 1;")
    last_row = cursor.fetchone()
    next_id = (last_row[0] + 1) if last_row else 1
    prev_hash = last_row[1] if last_row else ("0" * 64)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    event_data = f"TRUTH_LOG_COMMIT:QF-TL-2026-11-07-002:SHA256={doc_sha256}"

    record_payload = f"{next_id}|{timestamp}|{event_data}|{prev_hash}"
    current_hash = hashlib.sha256(record_payload.encode("utf-8")).hexdigest()

    cursor.execute(
        "INSERT INTO audit_runs (id, timestamp, event_data, prev_hash, current_hash) VALUES (?, ?, ?, ?, ?);",
        (next_id, timestamp, event_data, prev_hash, current_hash)
    )
    conn.commit()
    conn.close()
    print(f"[+] SUCCESS: Appended Truth Log entry #{next_id} to hash-chained SQLite ledger.")
    print(f"    prev_hash:    {prev_hash[:16]}...")
    print(f"    current_hash: {current_hash[:16]}...")

if __name__ == "__main__":
    commit_truth_log()
