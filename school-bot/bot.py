#!/usr/bin/env python3
import os
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

app = FastAPI(title="School Bot Interface", description="Educational assistant decoupled from core infrastructure")

# Ensure completely isolated REST client to query QuantumFlex (read-only)
QF_API_BASE = "http://127.0.0.1:9050/api"
OLLAMA_API_BASE = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "qwen2.5-coder:1.5b"

SYSTEM_PROMPT = """You are an AI School Assistant. You are totally isolated from the QuantumFlex tactical network.
Your sole purpose is to help the user with their coursework, homework, math, writing, and studies.
Be friendly, educational, and clear. Do NOT act like a security node."""

class ChatRequest(BaseModel):
    message: str

@app.get("/api/mesh_status")
async def get_mesh_status():
    """Queries the secure QuantumFlex mesh for read-only system state."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{QF_API_BASE}/status")
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        return {"error": "Mesh unreachable", "details": str(e)}
    raise HTTPException(status_code=502, detail="Bad gateway to QF mesh")

async def ask_ollama(prompt: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(OLLAMA_API_BASE, json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "system": SYSTEM_PROMPT,
                "stream": False
            })
            if resp.status_code == 200:
                return resp.json().get("response", "No response from LLM.")
            return "Error: LLM returned non-200 status."
    except Exception as e:
        return f"Error contacting local AI engine: {e}"

@app.post("/api/chat")
async def chat(req: ChatRequest):
    """Isolated chat logic for school assistant."""
    msg = req.message.lower()
    
    if "check mesh status" in msg or "status of the mesh" in msg:
        status_data = await get_mesh_status()
        if "error" in status_data:
            return {"response": "I cannot reach the QuantumFlex Mesh right now. Is the Core Node online?"}
        return {"response": f"The QuantumFlex mesh is ONLINE. Connected teammates: {status_data.get(teammates_online, 0)}"}
    
    # Query Ollama for actual educational assistance
    ai_response = await ask_ollama(req.message)
    return {"response": ai_response}

# Mount isolated UI
app.mount("/ui", StaticFiles(directory="ui", html=True), name="ui")

@app.get("/")
async def root():
    return RedirectResponse(url="/ui/")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("SCHOOL_BOT_PORT", 9060))
    print(f"Starting Independent School Bot on port {port}...")
    uvicorn.run("bot:app", host="0.0.0.0", port=port, reload=False)
