#!/usr/bin/env python3
"""
A.T.H.E.N.A. — Autonomous Tactical Hybrid Engine for Neural Architecture
==========================================================================
FastAPI service wrapping native SQLite Vector Memory & Custom Ollama Oracle.
Port: 8001 (127.0.0.1 loopback & Tailscale mesh accessible)
"""

import os
import sys
import gc
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import urllib.request
import urllib.error

# Add parent directory for imports
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from sentinel.intelligence.athena_vector_db import AthenaVectorStore

# ── Configuration ─────────────────────────────────────────────────────────────
OLLAMA_BASE_URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
EMBED_MODEL     = os.environ.get("EMBED_MODEL", "nomic-embed-text")
CHAT_MODEL      = os.environ.get("ATHENA_MODEL", "athena:latest")
MAX_VECTORS     = 50_000
TOP_K_RESULTS   = 4

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] ATHENA | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("athena")

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="A.T.H.E.N.A. RAG Node",
    description="Autonomous Tactical Hybrid Engine for Neural Architecture — Quantum Flex",
    version="2.5.0",
)

_store: Optional[AthenaVectorStore] = None
_startup_time = datetime.now().isoformat()

def get_store() -> AthenaVectorStore:
    global _store
    if _store is None:
        _store = AthenaVectorStore()
    return _store

# ── Pydantic models ───────────────────────────────────────────────────────────
class QueryRequest(BaseModel):
    question: str
    top_k: int = TOP_K_RESULTS
    mode: Optional[str] = "tactical"

class IngestRequest(BaseModel):
    text: str
    source: str = "manual"
    metadata: dict = {}

# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    """Node health check — called by AMARA, Mobile CLI, and Gateway."""
    try:
        store = get_store()
        count = store.count()
        return {
            "status":       "ONLINE",
            "node":         "athena",
            "vector_count": count,
            "max_vectors":  MAX_VECTORS,
            "embed_model":  EMBED_MODEL,
            "chat_model":   CHAT_MODEL,
            "uptime_since": _startup_time,
            "timestamp":    datetime.now().isoformat(),
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "DEGRADED", "error": str(e)}
        )

@app.post("/query")
async def query_rag(req: QueryRequest):
    """
    RAG query pipeline:
    1. Retrieve top-k semantic chunks from AthenaVectorStore
    2. Build context-grounded prompt with Truth Directive
    3. Generate synthesized tactical response via Ollama athena / qwen2.5-coder
    """
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        store = get_store()
        count = store.count()

        if count == 0:
            return {
                "answer":   "Knowledge base is currently unindexed. Run `python tools/train_athena_memory.py` to index blueprints.",
                "sources":  [],
                "context":  "",
                "model":    CHAT_MODEL,
                "vectors":  0,
            }

        # Retrieve top relevant chunks
        results = store.similarity_search(req.question, top_k=req.top_k)
        context_blocks = [r["content"] for r in results]
        context = "\n\n---\n\n".join(context_blocks)
        sources = list(set(r["source"] for r in results))

        prompt = f"""You are A.T.H.E.N.A., the tactical vector memory and oracle of QuantumFlex.
Answer the following query with technical precision, authoritative clarity, and strategic depth using the verified context below.

CONTEXT:
{context}

QUERY:
{req.question}

ANSWER:"""

        # Query local Ollama instance
        payload = json.dumps({
            "model": CHAT_MODEL,
            "prompt": prompt,
            "stream": False
        }).encode("utf-8")

        ollama_req = urllib.request.Request(
            f"{OLLAMA_BASE_URL}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"}
        )

        with urllib.request.urlopen(ollama_req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            answer = data.get("response", "").strip()

        gc.collect()

        return {
            "answer":  answer,
            "sources": sources,
            "context": context[:400] + "..." if len(context) > 400 else context,
            "model":   CHAT_MODEL,
            "vectors": count,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        log.error(f"RAG query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ingest")
async def ingest_text(req: IngestRequest):
    """Directly ingests a new document/truth entry into vector memory."""
    try:
        store = get_store()
        count = store.count()
        if count >= MAX_VECTORS:
            raise HTTPException(status_code=429, detail="Vector memory limit reached.")

        success = store.add_document(
            content=req.text,
            source=req.source,
            metadata=req.metadata
        )
        if not success:
            raise HTTPException(status_code=500, detail="Failed to generate vector embedding.")

        new_count = store.count()
        return {
            "status": "ingested",
            "source": req.source,
            "total_vectors": new_count
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Ingest failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="info")
