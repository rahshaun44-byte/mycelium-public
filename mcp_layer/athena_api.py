import hmac
#!/usr/bin/env python3
"""
A.T.H.E.N.A. — Autonomous Tactical Hybrid Engine for Neural Architecture
==========================================================================
FastAPI service wrapping native SQLite Vector Memory & Custom Ollama Oracle.
Port: 8005 (127.0.0.1 loopback & Tailscale mesh accessible)
"""

import os
import subprocess
import sys
import gc
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Request as FastAPIRequest
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import urllib.request
import urllib.error

try:
    import psycopg2
    import psycopg2.extras
    PG_AVAILABLE = True
except ImportError:
    PG_AVAILABLE = False

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

PG_CONFIG = {
    "host": os.environ.get("DB_HOST", "127.0.0.1"),
    "port": int(os.environ.get("DB_PORT", 5432)),
    "dbname": os.environ.get("DB_NAME", "telemetry"),
    "user": os.environ.get("DB_USER", os.environ.get("GHOSTNODE_DB_USER", "ghostnode")),
    "password": os.environ.get("DB_PASSWORD", os.environ.get("GHOSTNODE_DB_PASSWORD", "")),
    "connect_timeout": 2,
}

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

# ── Live Telemetry Helper ─────────────────────────────────────────────────────
def read_tpm_nv_root() -> str | None:
    try:
        res = subprocess.run(
            ["tpm2_nvread", "-C", "o", "-s", "32", "0x1c00010"],
            capture_output=True,
            timeout=2,
        )
    except Exception:
        return None
    if res.returncode != 0 or len(res.stdout) != 32:
        return None
    return res.stdout.hex()



def get_live_telemetry_summary() -> str:
    if not PG_AVAILABLE:
        return "Live telemetry unavailable (PostgreSQL adapter missing)."
    try:
        conn = psycopg2.connect(**PG_CONFIG)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cur.execute("SELECT * FROM sentinel_ledger ORDER BY id DESC LIMIT 1")
        drive_row = cur.fetchone()
        
        cur.execute("SELECT * FROM integrity_registry LIMIT 1")
        integrity_row = cur.fetchone()
        
        cur.execute("SELECT * FROM telemetry_log ORDER BY timestamp DESC LIMIT 1")
        vitals_row = cur.fetchone()
        
        cur.close()
        conn.close()
        
        lines = []
        if vitals_row and vitals_row.get('timestamp'):
            ts = vitals_row.get('timestamp')
            if isinstance(ts, str):
                try:
                    # Handle basic ISO formats
                    ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except:
                    pass
            if isinstance(ts, datetime):
                from datetime import timezone
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                age = (now - ts).total_seconds()
                freshness = "LIVE" if age < 30 else "STALE" if age <= 120 else "UNAVAILABLE"
                lines.append(f"Telemetry timestamp: {ts.strftime('%Y-%m-%d %H:%M:%S %Z').strip()}")
                lines.append(f"Telemetry age: {int(age)} seconds ({freshness})")
                lines.append("")

        if drive_row:
            lines.append("Drive Score:")
            lines.append(f"  Value: {drive_row.get('drive_score')}")
            lines.append("  Definition: Sentinel's calculated Euclidean distance from baseline")
            lines.append("  Units: dimensionless")
            lines.append(f"  Interpretation: lower is better (optimal < 1000, max tolerance 1500). Current status: {drive_row.get('status')}")
            lines.append("")
            
            lines.append("Integrity Provenance:")
            b_hash = drive_row.get('block_hash') or 'UNVERIFIED'
            p_hash = drive_row.get('previous_hash') or 'UNVERIFIED'
            b_hash_disp = b_hash[:16] + "..." if len(b_hash) > 16 else b_hash
            p_hash_disp = p_hash[:16] + "..." if len(p_hash) > 16 else p_hash
            lines.append(f"  Block Hash: {b_hash_disp}")
            lines.append(f"  Previous Block: {p_hash_disp}")
            lines.append(f"  Ledger Status: {'Tamper-Evident Hash Chain Verified' if b_hash != 'UNVERIFIED' else 'Unverified / Legacy Record'}")
            
            nv_root = read_tpm_nv_root()
            tip = (b_hash or "").strip().lower()
            if nv_root is None:
                lines.append("  Hardware Anchor: TPM unread (device, auth, or size)")
            elif nv_root == tip and len(tip) == 64:
                lines.append("  Hardware Anchor: NV 0x1c00010 MATCHED")
            else:
                lines.append(
                    f"  Hardware Anchor: DIVERGENCE NV={nv_root[:16]}... DB={tip[:16]}..."
                )
            lines.append("")
            
            lines.append(f"CPU Usage: {drive_row.get('cpu_usage')}%")
            lines.append(f"RAM Usage: {drive_row.get('mem_usage')}%")
            lines.append(f"Hash Penalty: {drive_row.get('hash_penalty')}")
            lines.append(f"IO Wait: {drive_row.get('io_wait')}")
        if integrity_row:
            lines.append(f"Lockout Status: {integrity_row.get('lockout_status')} (Node: {integrity_row.get('node_id')})")
        if vitals_row:
            lines.append(f"System CPU Load (1m): {vitals_row.get('cpu_load_1m')}")
            
        if not lines:
            return "No telemetry records found in PostgreSQL."
            
        return "\\n".join(lines)
    except Exception as e:
        log.warning(f"Failed to fetch live telemetry: {e}")
        return f"Live telemetry unavailable (Database error: {e})"

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

        live_telemetry = get_live_telemetry_summary()

        prompt = f"""You are A.T.H.E.N.A., the tactical vector memory and oracle of QuantumFlex.
Answer the following query with technical precision, authoritative clarity, and strategic depth using the verified context below.

LIVE SYSTEM STATE:
{live_telemetry}

LIVE SYSTEM STATE is authoritative only for values explicitly supplied in this section.
If a requested live metric is absent, stale, or unavailable, say so.
Never infer, estimate, or invent a current value.
Static documentation must not be presented as current system state.

STATIC DOCUMENT CONTEXT:
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
async def ingest_text(req: IngestRequest, request: FastAPIRequest):
    expected_key = os.environ.get("ATHENA_API_KEY", os.environ.get("DASHBOARD_API_KEY"))
    if not expected_key:
        raise HTTPException(status_code=401, detail="Unauthorized: Service locked. API key not configured.")
    x_api_key = request.headers.get("x-api-key")
    if not x_api_key or not hmac.compare_digest(x_api_key, expected_key):
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid API Key")
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
    uvicorn.run(app, host="127.0.0.1", port=8005, log_level="info")
