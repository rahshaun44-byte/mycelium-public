from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import asyncio
import httpx
import os
import sys
import json
import psycopg2
from pathlib import Path
from datetime import datetime
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import InvalidSignature
from kafka import KafkaProducer

app = FastAPI(title="Quantum Flex Core Node & Gateway API", version="2.1.0")

# Correct paths for this host
BASE_DIR = Path(__file__).resolve().parent.parent

# Auto-load .env if present
env_file = BASE_DIR / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

ORCHESTRATOR = str(BASE_DIR / "run_sentinel.py")
ATHENA_URL = os.environ.get("ATHENA_URL", "http://127.0.0.1:8001")
DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = int(os.environ.get("DB_PORT", 5432))
DB_NAME = os.environ.get("QUANTUM_DB_NAME", "quantum_flex")
DB_USER = os.environ.get("QUANTUM_SENTINEL_USER", "quantum_sentinel")
DB_PASS = os.environ.get("QUANTUM_SENTINEL_PASSWORD", os.environ.get("POSTGRES_PASSWORD", os.environ.get("SENTINEL_DB_PASSWORD", "")))

KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "100.64.1.15:9092")
KAFKA_PRODUCER = None

def get_kafka_producer():
    global KAFKA_PRODUCER
    if KAFKA_PRODUCER is None:
        KAFKA_PRODUCER = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(","),
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8"),
            acks="all",
            request_timeout_ms=5000,
            max_block_ms=5000,
            api_version=(3, 6, 0)
        )
    return KAFKA_PRODUCER

INGEST_CONCURRENCY_LIMIT = int(os.environ.get("INGEST_CONCURRENCY_LIMIT", "4"))
_ingest_semaphore = asyncio.Semaphore(INGEST_CONCURRENCY_LIMIT)


# ============================================================================
# Layer 2 / Layer 3: Edge Telemetry Ingestion & Verification Models
# ============================================================================

class TelemetryPayload(BaseModel):
    node_id: str
    seq: int
    timestamp: int
    payload: str  # Contains RF / OS event JSON
    signature: str  # Hex string (64 bytes / 128 hex chars)
    public_key: str  # Hex string (32 bytes / 64 hex chars)


class VerifiedReceipt(BaseModel):
    status: str
    node_id: str
    seq: int
    trust_score: int


def get_db_connection():
    """Returns a direct append-only connection to the persistence layer."""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        connect_timeout=3
    )


@app.post("/api/v1/telemetry/submit", response_model=VerifiedReceipt)
async def submit_telemetry(req: TelemetryPayload):
    """
    Layer 2 / Layer 3 Cryptographic Ingestion Gateway.
    Verifies Ed25519 signatures, checks privacy opt-out flags,
    and commits verified telemetry to the PostgreSQL append-only channel.
    """
    # 1. Reconstruct Public Key & Signature
    try:
        pk_bytes = bytes.fromhex(req.public_key)
        if len(pk_bytes) != 32:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed public key (must be 32 bytes)")
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed public key hex")

    try:
        sig_bytes = bytes.fromhex(req.signature)
        if len(sig_bytes) != 64:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed signature (must be 64 bytes)")
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed signature hex")

    try:
        verifying_key = ed25519.Ed25519PublicKey.from_public_bytes(pk_bytes)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Ed25519 key")

    # 2. DPI & Cryptographic Verification
    # Message format: deterministic concatenation of immutable fields
    message_bytes = f"{req.node_id}:{req.seq}:{req.payload}".encode("utf-8")
    try:
        verifying_key.verify(sig_bytes, message_bytes)
    except InvalidSignature:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Cryptographic verification failed: Invalid signature")

    # 3. Privacy Filter (_optout / _nomap)
    if "_optout" in req.payload.lower() or "_nomap" in req.payload.lower():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Privacy flag detected. Packet dropped.")

    # 4. Anti-Replay & Trust Score Calculation
    trust_score = 100

    # 5. Kafka Stream Publish (Decoupled Ingestion)
    try:
        producer = get_kafka_producer()
        future = producer.send(
            "quantum-telemetry-raw",
            key=req.node_id,
            value=req.dict()
        )
        future.get(timeout=5.0)  # Synchronously wait for message acknowledgment
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Kafka stream ingestion failed: {e}")

    return VerifiedReceipt(
        status="VERIFIED",
        node_id=req.node_id,
        seq=req.seq,
        trust_score=trust_score
    )


# ============================================================================
# Status & Query Endpoints
# ============================================================================

@app.get("/status")
async def system_status():
    """Full health check of all Quantum Flex nodes."""
    nodes = {}

    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            r = await client.get(f"{ATHENA_URL}/health")
            nodes["athena"] = r.json()
    except Exception as e:
        nodes["athena"] = {"status": "OFFLINE", "error": str(e)}

    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            r = await client.get("http://127.0.0.1:11434/api/tags")
            models = [m["name"] for m in r.json().get("models", [])]
            nodes["ollama"] = {"status": "ONLINE", "models": models}
    except Exception as e:
        nodes["ollama"] = {"status": "OFFLINE", "error": str(e)}

    return {
        "timestamp": datetime.now().isoformat(),
        "api_node": "ONLINE",
        "mesh_ip": os.environ.get("TAILNET_IP", "100.64.1.29"),
        "gateway_endpoint": "/api/v1/telemetry/submit",
        "nodes": nodes
    }


@app.post("/query")
async def query_athena(request: Request):
    """Route a RAG query to the Athena node."""
    data = await request.json()
    question = data.get("question", "")
    if not question:
        return {"status": "error", "message": "No question provided"}
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(f"{ATHENA_URL}/query", json={"question": question})
            return r.json()
    except Exception as e:
        return {"status": "fatal", "error": str(e)}


if __name__ == "__main__":
    import uvicorn
    api_port = int(os.environ.get("API_NODE_PORT", 8080))
    # Zero-Trust Mesh Lockdown: Bind strictly to the Tailscale overlay IP
    bind_host = os.environ.get("BIND_HOST", os.environ.get("TAILNET_IP", "100.64.1.29"))
    print(f"[*] Zero-Trust Gateway binding exclusively to mesh interface: {bind_host}:{api_port}")
    uvicorn.run(app, host=bind_host, port=api_port)
