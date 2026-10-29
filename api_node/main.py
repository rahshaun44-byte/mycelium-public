import hmac
from fastapi import HTTPException, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import asyncio
import httpx
import os
import sys
import time
from pathlib import Path

# Universal Invariant Gate (R >= O)
sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.privacy_filter import PrivacyFilter
from api_node.circle_usdc_settlement import (
    ARC_L1_CHAIN_CONFIG,
    PayloadMismatchError,
    build_arc_settlement_payload,
    scale_to_micro_usdc,
)
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


def persist_telemetry_frame(node_id: str, timestamp: int, payload_str: str) -> bool:
    """Live persistence caller: commits verified telemetry frame to quantum_telemetry_channel."""
    # Defense-in-depth: Never allow opted-out or prohibited ambient data to reach database storage
    try:
        if PrivacyFilter.contains_optout(payload_str) or PrivacyFilter.contains_prohibited_ambient_data(payload_str):
            print(f"[!] Telemetry live persistence rejected: Prohibited ambient or opt-out data detected in payload.")
            return False
    except Exception as e:
        print(f"[!] Telemetry live persistence filter error (fail-closed): {e}")
        return False
    try:
        from src.db_credentials import DatabaseRole, open_role_connection
        conn = open_role_connection(
            role=DatabaseRole.WRITER,
            dbname=os.environ.get("DB_NAME", "telemetry"),
        )
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO quantum_telemetry_channel (node_id, timestamp, payload)
                    VALUES (%s, %s, %s)
                """, (node_id, timestamp, payload_str))
        conn.close()
        return True
    except Exception as e:
        print(f"[!] Telemetry live persistence warning: {e}")
        return False


@app.post("/api/v1/telemetry/submit")
async def submit_telemetry(request: Request):
    """
    Ingestion & Verification Gateway (Layer 2 / Layer 3):
    1. Cryptographic Ed25519 signature verification (fails closed: 401 Unauthorized).
    2. Edge privacy & opt-out filter (drops _optout / _nomap: 403 Forbidden).
    3. Live database persistence into quantum_telemetry_channel.
    4. Receipt issuance (200 OK, status: VERIFIED, trust_score: 100).
    """
    import json
    from src.privacy_filter import PrivacyFilter

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    node_id = data.get("node_id")
    seq = data.get("seq")
    timestamp = data.get("timestamp")
    payload = data.get("payload")
    sig_hex = data.get("signature")
    pub_hex = data.get("public_key")

    if not all([node_id, seq is not None, timestamp is not None, payload is not None, sig_hex, pub_hex]):
        raise HTTPException(status_code=400, detail="Missing required telemetry submission fields")

    # 1. Cryptographic Verification (Ed25519)
    try:
        from cryptography.hazmat.primitives.asymmetric import ed25519
        from cryptography.exceptions import InvalidSignature

        pub_bytes = bytes.fromhex(pub_hex)
        sig_bytes = bytes.fromhex(sig_hex)
        public_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)

        message_bytes = f"{node_id}:{seq}:{payload}".encode("utf-8")
        public_key.verify(sig_bytes, message_bytes)
    except (ValueError, InvalidSignature, Exception) as e:
        raise HTTPException(status_code=401, detail=f"Unauthorized: Signature verification failed: {e}")

    # 2. Deep Packet Inspection (DPI) & Privacy Opt-Out Filter
    payload_obj = None
    if isinstance(payload, str):
        try:
            payload_obj = json.loads(payload)
        except Exception:
            payload_obj = None
    elif isinstance(payload, dict):
        payload_obj = payload

    # 2. Deep Packet Inspection (DPI) & Zero-Ambient Boundary
    if (payload_obj is not None and PrivacyFilter.contains_prohibited_ambient_data(payload_obj)) or \
       (isinstance(payload, str) and PrivacyFilter.contains_prohibited_ambient_data(payload)):
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Prohibited ambient network or personal tracking identifiers detected",
        )

    # Evaluate SSID fields
    ssid_to_check = None
    if isinstance(payload_obj, dict):
        ssid_to_check = payload_obj.get("ssid")

    # If explicit SSID is tagged, or if the payload contains an optout/nomap tag:
    if ssid_to_check and PrivacyFilter.should_exclude_ssid(ssid_to_check):
        raise HTTPException(status_code=403, detail="Forbidden: Privacy opt-out tag detected in SSID")

    # Sanitize frames if a list is present (Atomic rejection if any prohibited ambient data is present)
    if isinstance(payload_obj, dict) and "frames" in payload_obj and isinstance(payload_obj["frames"], list):
        for f in payload_obj["frames"]:
            if isinstance(f, dict) and PrivacyFilter.contains_prohibited_ambient_data(f):
                raise HTTPException(
                    status_code=403,
                    detail="Forbidden: Prohibited ambient network or personal tracking identifiers detected in frame batch",
                )
        sanitized = []
        for f in payload_obj["frames"]:
            if isinstance(f, dict):
                clean_f = PrivacyFilter.sanitize_telemetry_frame(f)
                if clean_f is not None:
                    sanitized.append(clean_f)
        if not sanitized and payload_obj["frames"]:
            raise HTTPException(status_code=403, detail="Forbidden: All telemetry frames opted out")
        payload_obj["frames"] = sanitized
    elif isinstance(payload_obj, dict) and PrivacyFilter.contains_optout(payload_obj):
        raise HTTPException(status_code=403, detail="Forbidden: Privacy opt-out tag detected in payload")
    elif isinstance(payload, str) and PrivacyFilter.should_exclude_ssid(payload):
        raise HTTPException(status_code=403, detail="Forbidden: Privacy opt-out tag detected in payload")

    # 3. Live Persistence Caller
    payload_str = json.dumps(payload_obj) if payload_obj is not None else str(payload)
    if not persist_telemetry_frame(node_id, int(timestamp), payload_str):
        raise HTTPException(status_code=403, detail="Forbidden: Persistence rejected by privacy filter")

    # 4. Receipt
    return {
        "status": "VERIFIED",
        "trust_score": 100,
        "node_id": node_id,
        "seq": seq
    }


class ArcSettlementRequest(BaseModel):
    recipient_address: str = Field(..., description="EVM recipient address (0x...)")
    amount_usdc: float | str = Field(..., description="USDC amount to settle (e.g. 5.50)")
    block_hash: str = Field(..., description="Source block hash for RFC 4122 idempotency derivation")
    nonce: int = Field(default=0, ge=0, description="Settlement nonce")


# Idempotency registry tracking committed settlement payloads by idempotency_key
COMMITTED_SETTLEMENT_IDEMPOTENCY_REGISTRY: Dict[str, Dict[str, Any]] = {}


@app.post("/api/v1/settlement/arc")
async def execute_arc_usdc_settlement(payload: ArcSettlementRequest) -> JSONResponse:
    """
    Executes a micro-settlement on Circle Arc L1 using native USDC gas,
    6-decimal micro-USDC scaling, and RFC 9562/4122 deterministic idempotency.
    Enforces deduplication: identical requests return the prior committed settlement.
    """
    # 1. PrivacyFilter inspection
    payload_dict = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    if PrivacyFilter.contains_optout(payload_dict):
        raise HTTPException(status_code=403, detail="Forbidden: Privacy opt-out tag detected in settlement payload")

    # 2. Scale amount to integer micro-USDC
    try:
        micro_amount = scale_to_micro_usdc(payload.amount_usdc)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # 3. Build Arc L1 payload
    try:
        settlement_payload = build_arc_settlement_payload(
            recipient_address=payload.recipient_address,
            amount_micro_usdc=micro_amount,
            block_hash=payload.block_hash,
            nonce=payload.nonce,
        )
        idempotency_key = settlement_payload["idempotency"]["idempotency_key"]
        is_new = settlement_payload["idempotency"].get("is_new", True)

        # Deduplication check: reject double execution on identical idempotency key or persisted intent
        if not is_new or idempotency_key in COMMITTED_SETTLEMENT_IDEMPOTENCY_REGISTRY:
            return JSONResponse(status_code=200, content={
                "status": "SETTLEMENT_COMMITTED_DRY_RUN",
                "action": "ALREADY_COMMITTED_IDEMPOTENT_RETRY",
                "chain": settlement_payload["chain_config"]["chain_name"],
                "gas_token": "NATIVE_USDC",
                "settlement": settlement_payload["settlement"],
                "idempotency": settlement_payload["idempotency"],
            })

        COMMITTED_SETTLEMENT_IDEMPOTENCY_REGISTRY[idempotency_key] = settlement_payload
        return JSONResponse(status_code=200, content={
            "status": "SETTLEMENT_COMMITTED_DRY_RUN",
            "action": "COMMITTED_NEW",
            "chain": settlement_payload["chain_config"]["chain_name"],
            "gas_token": "NATIVE_USDC",
            "settlement": settlement_payload["settlement"],
            "idempotency": settlement_payload["idempotency"],
        })
    except PayloadMismatchError as exc:
        raise HTTPException(status_code=409, detail=f"Conflict: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Settlement failed: {exc}") from exc


if __name__ == "__main__":
    import uvicorn
    api_port = int(os.environ.get("API_NODE_PORT", 8080))
    api_host = os.environ.get("API_NODE_HOST", "127.0.0.1")
    uvicorn.run(app, host=api_host, port=api_port)

