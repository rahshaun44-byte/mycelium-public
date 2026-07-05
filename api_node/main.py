from fastapi import FastAPI, Request
import asyncio

app = FastAPI(title="Quantum Flex Core Node")

@app.post("/ingest")
async def ingest_payload(request: Request):
    data = await request.json()
    file_path = data.get("file_path")
    
    if not file_path:
        return {"status": "error", "message": "No file_path provided"}
        
    print(f"[>>] API Received Ingestion Request for: {file_path}")
    
    orchestrator = "/home/chambers/quantum_flex/run_sentinel.py"
    
    try:
        # Anti-Gravity Execution: Non-blocking asynchronous subprocess
        process = await asyncio.create_subprocess_exec(
            "python3", orchestrator, file_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # The API yields control back to the event loop while waiting for Podman
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            return {"status": "success", "telemetry": stdout.decode().strip()}
        else:
            return {"status": "fatal", "error": stderr.decode().strip()}
    except Exception as e:
        return {"status": "fatal", "error": str(e)}
