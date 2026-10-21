import hmac
from fastapi import HTTPException
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
import asyncio
import httpx
import os
import sys
import time
from pathlib import Path

# Universal Invariant Gate (R >= O)
sys.path.append(str(Path(__file__).resolve().parent.parent))
try:
    from sentinel.invariant_gate import evaluate_invariant, evaluate_all_invariants
except Exception as e:
    evaluate_invariant = None
    evaluate_all_invariants = None
from pathlib import Path
from datetime import datetime


def verify_api_node_auth(request: Request):
    expected_key = os.environ.get("API_NODE_KEY", os.environ.get("DASHBOARD_API_KEY"))
    if not expected_key:
        raise HTTPException(status_code=401, detail="Unauthorized: Service locked. API key not configured.")
    x_api_key = request.headers.get("x-api-key")
    if not x_api_key or not hmac.compare_digest(x_api_key, expected_key):
        raise HTTPException(status_code=401, detail="Unauthorized: Missing or invalid x-api-key.")

app = FastAPI(title="Quantum Flex Core Node API", version="2.0.0")

# Mount mobile setup directories for over-the-network Termux provisioning
_mobile_dir = Path(__file__).resolve().parent.parent / "mobile"
if _mobile_dir.exists():
    app.mount("/mobile", StaticFiles(directory=str(_mobile_dir)), name="mobile")


# Correct paths for this host
BASE_DIR = Path(__file__).resolve().parent.parent
ORCHESTRATOR = str(BASE_DIR / "run_sentinel.py")
ATHENA_URL = os.environ.get("ATHENA_URL", "http://127.0.0.1:8001")

# Each ingest request spawns a full python3 subprocess (run_sentinel.py).
# Without a cap, a burst of requests spawns unbounded concurrent subprocesses
# and can exhaust host RAM/CPU. This bounds concurrent subprocess execution;
# excess requests wait for a slot instead of each spawning immediately.

ALLOWED_DIRECTORIES = [
    (BASE_DIR / "knowledge_vault").resolve(),
    (BASE_DIR / "docs").resolve(),
    (BASE_DIR / "sentinel" / "knowledge_base").resolve(),
]

def assert_path_contained(target_path: Path):
    resolved = target_path.resolve()
    for allowed in ALLOWED_DIRECTORIES:
        if resolved == allowed or allowed in resolved.parents:
            return True
    return False

INGEST_CONCURRENCY_LIMIT = int(os.environ.get("INGEST_CONCURRENCY_LIMIT", "4"))
_ingest_semaphore = asyncio.Semaphore(INGEST_CONCURRENCY_LIMIT)


async def run_orchestrator(*args: str) -> tuple[int, bytes, bytes]:
    """Run run_sentinel.py as a subprocess, bounded by _ingest_semaphore."""
    async with _ingest_semaphore:
        process = await asyncio.create_subprocess_exec(
            sys.executable, ORCHESTRATOR, *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        return process.returncode, stdout, stderr


@app.get("/status")
async def system_status():
    """Full health check of all Quantum Flex nodes."""
    nodes = {}

    # Check Athena RAG node
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            r = await client.get(f"{ATHENA_URL}/health")
            nodes["athena"] = r.json()
    except Exception as e:
        nodes["athena"] = {"status": "OFFLINE", "error": str(e)}

    # Check Ollama
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            r = await client.get("http://127.0.0.1:11434/api/tags")
            models = [m["name"] for m in r.json().get("models", [])]
            nodes["ollama"] = {"status": "ONLINE", "models": models}
    except Exception as e:
        nodes["ollama"] = {"status": "OFFLINE", "error": str(e)}

    if evaluate_all_invariants:
        try:
            inv = evaluate_all_invariants(evaluator="api_node_status")
            nodes["invariant_gate"] = {
                "status": "ONLINE" if inv["all_allowed"] else "RESTRICTED",
                "overall_verdict": inv["overall_verdict"],
                "all_allowed": inv["all_allowed"]
            }
        except Exception as e:
            nodes["invariant_gate"] = {"status": "OFFLINE", "error": str(e)}

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
    verify_api_node_auth(request)
    data = await request.json()
    file_path = data.get("file_path")

    if not file_path:
        return {"status": "error", "message": "No file_path provided"}

    p = Path(file_path)
    if not assert_path_contained(p):
        raise HTTPException(
            status_code=403, 
            detail="Forbidden: Ingestion target must reside within authorized knowledge directories."
        )

    print(f"[>>] API Received Ingestion Request for: {file_path}")

    try:
        returncode, stdout, stderr = await run_orchestrator(file_path)

        if returncode == 0:
            return {"status": "success", "telemetry": stdout.decode().strip()}
        else:
            return {"status": "fatal", "error": stderr.decode().strip()}
    except Exception as e:
        return {"status": "fatal", "error": str(e)}


@app.post("/webhook/ingest")
async def webhook_ingest(request: Request):
    verify_api_node_auth(request)
    """Stage raw HTTP POST JSON payload directly into the Sentinel sandbox."""
    try:
        data = await request.json()
    except Exception as e:
        return {"status": "error", "message": f"Invalid JSON payload: {e}"}

    import random
    airlock_base = "/dev/shm/qflex_airlock" if os.path.exists("/dev/shm") else "/tmp/qflex_airlock"
    temp_dir = os.path.join(airlock_base, "webhooks")
    os.makedirs(temp_dir, exist_ok=True)
    
    filename = f"webhook_{int(datetime.now().timestamp())}_{random.randint(100, 999)}.json"
    temp_file_path = os.path.join(temp_dir, filename)

    try:
        with open(temp_file_path, "w") as f:
            import json
            json.dump(data, f)
            
        returncode, stdout, stderr = await run_orchestrator(temp_file_path)

        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

        if returncode == 0:
            return {"status": "success", "telemetry": stdout.decode().strip()}
        else:
            return {"status": "fatal", "error": stderr.decode().strip()}
            
    except Exception as e:
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception:
                pass
        return {"status": "fatal", "error": str(e)}


@app.get("/api/invariant")
async def get_invariant_status():
    """Returns real-time Universal Invariant Gate status (R >= O) for Digital and Physical Strata."""
    if not evaluate_all_invariants:
        return {"status": "error", "message": "Invariant gate module unavailable"}
    try:
        res = evaluate_all_invariants(evaluator="api_node_rest")
        return {
            "status": "success",
            "invariant": res
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/invariant/evaluate")
async def evaluate_custom_invariant(request: Request):
    """
    Submits a custom or physical telemetry vector to the OPA Invariant Gate.
    Supports mobile operator checks (Termux / PWA) and automated IoT sensors (FinallyFungus tanks).
    """
    if not evaluate_invariant:
        return {"status": "error", "message": "Invariant gate module unavailable"}
    try:
        data = await request.json()
        if "telemetry_timestamp" not in data or not data["telemetry_timestamp"]:
            data["telemetry_timestamp"] = int(time.time())
        if "max_staleness_seconds" not in data or not data["max_staleness_seconds"]:
            data["max_staleness_seconds"] = 60

        evaluator = request.headers.get("X-Operator-ID", "api_node_mobile")
        result = evaluate_invariant(data, evaluator=evaluator)
        return {
            "status": "success",
            "result": result
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    import uvicorn
    api_port = int(os.environ.get("API_NODE_PORT", 8080))
    api_host = os.environ.get("API_NODE_HOST", "127.0.0.1")
    uvicorn.run(app, host=api_host, port=api_port)
