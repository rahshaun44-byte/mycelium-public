#!/usr/bin/env python3
"""
═════════════════════════════════════════════════════════════════════
  QUANTUM FLEX: ATHENA NATIVE VECTOR STORE & COGNITIVE MEMORY
═════════════════════════════════════════════════════════════════════
Lightweight, zero-DLL dependency, pure-Python SQLite vector store.
Uses Ollama `nomic-embed-text` for 768-dim embeddings and fast
cosine-similarity search over knowledge artifacts.
"""

import os
import sys
import json
import math
import hashlib
import sqlite3
import urllib.request
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional

# Safe console rendering for Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT_DIR = Path(__file__).resolve().parents[2]
DB_PATH = ROOT_DIR / "sentinel" / "intelligence" / "athena_vectors.db"
OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text")

def get_embedding(text: str) -> List[float]:
    """Generates 768-dim embedding via local Ollama nomic-embed-text."""
    url = f"{OLLAMA_URL}/api/embeddings"
    data = json.dumps({"model": EMBED_MODEL, "prompt": text}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            return res.get("embedding", [])
    except Exception as e:
        print(f"[-] Embedding generation error: {e}")
        return []

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Computes cosine similarity between two float vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm_a = math.sqrt(sum(a * a for a, b in zip(v1, v2)))
    norm_b = math.sqrt(sum(b * b for a, b in zip(v1, v2)))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)

class AthenaVectorStore:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self.apply_migrations()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS neural_chunks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source TEXT,
                        content TEXT,
                        metadata JSON,
                        embedding JSON,
                        created_at TEXT
                    );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_source ON neural_chunks(source);")
        finally:
            conn.close()

    def apply_migrations(self):
        """Applies SQL schema migrations non-destructively."""
        migrations_dir = Path(__file__).resolve().parent / "migrations"
        if not migrations_dir.exists():
            return
        sql_files = sorted(migrations_dir.glob("*.sql"))
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                for sql_file in sql_files:
                    sql_text = sql_file.read_text(encoding="utf-8")
                    conn.executescript(sql_text)
        finally:
            conn.close()

    def get_or_create_document(self, source: str, content: str = "", metadata: dict = None) -> int:
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT id FROM documents WHERE source = ?", (source,))
                row = cur.fetchone()
                if row:
                    return row[0]
                meta_json = json.dumps(metadata or {}, sort_keys=True)
                cur.execute(
                    "INSERT INTO documents (source, content, metadata, created_at) VALUES (?, ?, ?, ?)",
                    (source, content, meta_json, datetime.now().isoformat())
                )
                return cur.lastrowid
        finally:
            conn.close()

    def add_claim(
        self,
        claim_id: str,
        document_id: int,
        claim_text: str,
        byte_offset_start: int,
        byte_offset_end: int,
        source_sha256: str,
        claim_sha256: str,
        epistemic_tier: str,
    ) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO claims (
                        claim_id, document_id, claim_text, byte_offset_start,
                        byte_offset_end, source_sha256, claim_sha256, epistemic_tier, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        claim_id, document_id, claim_text, byte_offset_start,
                        byte_offset_end, source_sha256, claim_sha256, epistemic_tier,
                        datetime.now().isoformat()
                    )
                )
            return True
        finally:
            conn.close()

    def get_claim(self, claim_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM claims WHERE claim_id = ?", (claim_id,))
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_claims_by_source(self, source_sha256: str) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM claims WHERE source_sha256 = ?", (source_sha256,))
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def add_evidence_span(
        self,
        span_id: str,
        claim_id: str,
        doc_uri: str,
        source_type: str,
        merkle_root: str,
        leaf_index: int,
        leaf_hash: str,
        inclusion_proof: List[Dict[str, Any]],
    ) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO evidence_spans (
                        span_id, claim_id, doc_uri, source_type,
                        merkle_root, leaf_index, leaf_hash, inclusion_proof_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        span_id, claim_id, doc_uri, source_type,
                        merkle_root, leaf_index, leaf_hash,
                        json.dumps(inclusion_proof)
                    )
                )
            return True
        finally:
            conn.close()

    def get_evidence_spans(self, claim_id: str) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM evidence_spans WHERE claim_id = ?", (claim_id,))
            rows = cur.fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d["inclusion_proof"] = json.loads(d.pop("inclusion_proof_json"))
                results.append(d)
            return results
        finally:
            conn.close()

    def add_verification_record(
        self,
        record_id: str,
        claim_id: str,
        verifier_kernel: str,
        kernel_version: str,
        status: str,
        assumptions: List[str],
        proof_script: str,
        execution_time_ms: float,
    ) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO verification_records (
                        record_id, claim_id, verifier_kernel, kernel_version,
                        status, assumptions_json, proof_script, execution_time_ms, verified_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record_id, claim_id, verifier_kernel, kernel_version,
                        status, json.dumps(assumptions), proof_script,
                        execution_time_ms, datetime.now().isoformat()
                    )
                )
            return True
        finally:
            conn.close()

    def get_verification_records(self, claim_id: str) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM verification_records WHERE claim_id = ?", (claim_id,))
            rows = cur.fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d["assumptions"] = json.loads(d.pop("assumptions_json"))
                results.append(d)
            return results
        finally:
            conn.close()

    def add_decontamination_record(
        self,
        paper_id: str,
        source_uri: str,
        content_sha256: str,
        minhash_signature: str,
        benchmark_leakage_score: float,
        quarantine_status: str,
    ) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO decontamination_records (
                        paper_id, source_uri, content_sha256, minhash_signature,
                        benchmark_leakage_score, quarantine_status, audited_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        paper_id, source_uri, content_sha256, minhash_signature,
                        benchmark_leakage_score, quarantine_status, datetime.now().isoformat()
                    )
                )
            return True
        finally:
            conn.close()

    def get_decontamination_record(self, paper_id_or_sha256: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM decontamination_records WHERE paper_id = ? OR content_sha256 = ?",
                (paper_id_or_sha256, paper_id_or_sha256)
            )
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def delete_by_source(self, source: str) -> int:
        """Removes existing chunks for a given source document to guarantee idempotent re-ingestion."""
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                cur = conn.execute("DELETE FROM neural_chunks WHERE source = ?", (source,))
                return cur.rowcount
        finally:
            conn.close()

    def add_document(self, content: str, source: str = "manual", metadata: dict = None):
        if not metadata:
            metadata = {}
        else:
            metadata = dict(metadata)
        metadata.setdefault("chunk_sha256", hashlib.sha256(content.encode("utf-8")).hexdigest())
        metadata.setdefault("access_role", "sovereign_internal")
        embedding = get_embedding(content)
        if not embedding:
            return False
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                conn.execute(
                    "INSERT INTO neural_chunks (source, content, metadata, embedding, created_at) VALUES (?, ?, ?, ?, ?)",
                    (source, content, json.dumps(metadata, sort_keys=True), json.dumps(embedding), datetime.now().isoformat())
                )
            return True
        finally:
            conn.close()

    def get_source_sha256(self, source: str) -> Optional[str]:
        """Retrieves the doc_sha256 for a given source document if present in metadata."""
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute("SELECT metadata FROM neural_chunks WHERE source = ? LIMIT 1", (source,))
            row = cur.fetchone()
            if row and row[0]:
                try:
                    meta = json.loads(row[0])
                    return meta.get("doc_sha256")
                except Exception:
                    return None
            return None
        finally:
            conn.close()

    def get_all_sources(self) -> List[str]:
        """Returns all distinct source document names currently indexed."""
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT source FROM neural_chunks")
            return [r[0] for r in cur.fetchall()]
        finally:
            conn.close()

    def similarity_search(
        self,
        query: str,
        top_k: int = 4,
        allowed_roles: List[str] = None,
    ) -> List[Dict[str, Any]]:
        query_emb = get_embedding(query)
        if not query_emb:
            return []

        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, source, content, metadata, embedding FROM neural_chunks")
            rows = cur.fetchall()
        finally:
            conn.close()

        if not rows:
            return []

        try:
            import numpy as np
            has_np = True
        except ImportError:
            has_np = False

        if has_np:
            filtered_rows = []
            emb_list = []
            for r_id, source, content, meta_raw, emb_raw in rows:
                try:
                    meta = json.loads(meta_raw) if meta_raw else {}
                    doc_role = meta.get("access_role", "sovereign_internal")
                    if allowed_roles is not None and doc_role not in allowed_roles:
                        continue
                    emb = json.loads(emb_raw)
                    filtered_rows.append((r_id, source, content, meta))
                    emb_list.append(emb)
                except Exception:
                    continue

            if not filtered_rows:
                return []

            matrix = np.array(emb_list, dtype=np.float32)
            q_vec = np.array(query_emb, dtype=np.float32)
            dot = np.dot(matrix, q_vec)
            norms = np.linalg.norm(matrix, axis=1) * np.linalg.norm(q_vec)
            norms[norms == 0.0] = 1e-9
            scores = dot / norms

            top_indices = np.argsort(scores)[::-1][:top_k]
            scored = []
            for idx in top_indices:
                r_id, source, content, meta = filtered_rows[idx]
                scored.append({
                    "id": r_id,
                    "source": source,
                    "content": content,
                    "metadata": meta,
                    "score": float(scores[idx]),
                })
            return scored

        scored = []
        for r_id, source, content, meta_raw, emb_raw in rows:
            try:
                emb = json.loads(emb_raw)
                meta = json.loads(meta_raw) if meta_raw else {}
                doc_role = meta.get("access_role", "sovereign_internal")
                if allowed_roles is not None and doc_role not in allowed_roles:
                    continue
                score = cosine_similarity(query_emb, emb)
                scored.append({
                    "id": r_id,
                    "source": source,
                    "content": content,
                    "metadata": meta,
                    "score": score
                })
            except Exception:
                continue

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def count(self) -> int:
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM neural_chunks")
            return cur.fetchone()[0]
        finally:
            conn.close()

    def clear(self):
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                conn.execute("DELETE FROM neural_chunks")
        finally:
            conn.close()

if __name__ == "__main__":
    store = AthenaVectorStore()
    print(f"Athena Native Vector Store initialized. Total vectors: {store.count()}")
