from fastapi import FastAPI, Request
import asyncio
import httpx
import os
from datetime import datetime

app = FastAPI(title="Quantum Flex Core Node API", version="2.0.0")

# Correct absolute paths for this host
ORCHESTRATOR = "/home/USERNAME/mycelium/run_sentinel.py"
ATHENA_URL = "http://127.0.0.1:8001"


@app.get("/status")
async def system_status():
    """Full health check of all Quantum Flex nodes."""
    nodes = {}

    # Check Athena RAG node
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{ATHENA_URL}/health")
            nodes["athena"] = r.json()
    except Exception as e:
        nodes["athena"] = {"status": "OFFLINE", "error": str(e)}

    # Check Ollama
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get("http://127.0.0.1:11434/api/tags")
            models = [m["name"] for m in r.json().get("models", [])]
            nodes["ollama"] = {"status": "ONLINE", "models": models}
    except Exception as e:
        nodes["ollama"] = {"status": "OFFLINE", "error": str(e)}

    return {
        "timestamp": datetime.now().isoformat(),
        "api_node": "ONLINE",
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


@app.post("/ingest")
async def ingest_payload(request: Request):
    """Stage a file into the Sentinel quarantine pipeline."""
    data = await request.json()
    file_path = data.get("file_path")

    if not file_path:
        return {"status": "error", "message": "No file_path provided"}

    print(f"[>>] API Received Ingestion Request for: {file_path}")

    try:
        # Anti-Gravity Execution: Non-blocking asynchronous subprocess
        process = await asyncio.create_subprocess_exec(
            "python3", ORCHESTRATOR, file_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            return {"status": "success", "telemetry": stdout.decode().strip()}
        else:
            return {"status": "fatal", "error": stderr.decode().strip()}
    except Exception as e:
        return {"status": "fatal", "error": str(e)}
