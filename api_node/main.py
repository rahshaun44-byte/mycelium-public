from fastapi import FastAPI, Request
import subprocess

app = FastAPI(title="Quantum Flex Core Node")

@app.post("/ingest")
async def ingest_payload(request: Request):
    data = await request.json()
    file_path = data.get("file_path")
    
    if not file_path:
        return {"status": "error", "message": "No file_path provided"}
        
    print(f"[>>] API Received Ingestion Request for: {file_path}")
    
    # Trigger the Sentinel Orchestrator locally
    orchestrator = "/home/chambers/quantum_flex/run_sentinel.py"
    try:
        result = subprocess.run(["python3", orchestrator, file_path], capture_output=True, text=True)
        return {"status": "success", "telemetry": result.stdout}
    except Exception as e:
        return {"status": "fatal", "error": str(e)}
