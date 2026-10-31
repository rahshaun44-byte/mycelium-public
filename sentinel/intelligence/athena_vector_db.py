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
from typing import List, Dict, Any, Tuple

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
