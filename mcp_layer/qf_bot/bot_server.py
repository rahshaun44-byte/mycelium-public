#!/usr/bin/env python3
"""
Quantum Flex AI Teammates: REST & Web API Server (QF-Bot)
=========================================================
Exposes the multi-agent teammate swarm over loopback and Tailscale mesh:
- REST API for conversational dispatch, teammate handoffs, and drafts
- Dynamic Draft Approval and Discard handling
- Routine execution engine (Overnight Audit, Heartbeats)
- Static Web HUD dashboard
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR / "mcp_layer"))

from qf_bot.orchestrator import QFBotOrchestrator
from qf_bot.routines import ROUTINE_CATALOG

# ── App Configuration ─────────────────────────────────────────────────────────
app = FastAPI(
    title="Quantum Flex AI Teammates (QF-Bot)",
    description="Autonomous Multi-Agent AI Teammates for Quantum Flex",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = QFBotOrchestrator()
UI_DIR = Path(__file__).resolve().parent / "ui"

# ── Pydantic Request Models ───────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    target_bot: Optional[str] = None

class ActionRequest(BaseModel):
    note: Optional[str] = ""

# ── API Endpoints ─────────────────────────────────────────────────────────────
@app.get("/api/status")
async def get_system_status():
    """Returns overall substrate health and connected bots."""
    try:
        conn = orchestrator._get_db()
        sentinel_info = orchestrator.sentinel.inspect_tpm_and_ledger(conn)
        conn.close()
    except Exception as e:
        sentinel_info = {"error": str(e)}

    immune_info = orchestrator.immune.inspect_crypto_state()
    claw_services = orchestrator.claw.list_services_status()

    return {
        "node": "quantumflex",
        "timestamp": datetime.now().isoformat(),
        "sentinel": sentinel_info,
        "immune": immune_info,
        "services": claw_services,
        "teammates_online": len(orchestrator.teammates),
        "pending_drafts": len([d for d in orchestrator.draft_queue.list_drafts() if d["status"] == "PENDING_APPROVAL"]),
    }

@app.get("/api/teammates")
async def get_teammates():
    """Returns the list of active AI teammates with avatars and roles."""
    return {"roster": orchestrator.get_roster()}

@app.get("/api/history")
async def get_history():
    """Returns the conversation history."""
    return {"messages": orchestrator.conversation_history}

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    """Dispatches a prompt to a specific teammate or triggers multi-bot collaboration."""
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    result = await orchestrator.handle_message(req.message, target_bot=req.target_bot)
    return result

@app.get("/api/drafts")
async def list_drafts():
    """Returns all staged draft actions requiring approval."""
    return {"drafts": orchestrator.draft_queue.list_drafts()}

@app.post("/api/drafts/{draft_id}/approve")
async def approve_draft(draft_id: str):
    """Executes a staged draft action upon operator sign-off."""
    res = await orchestrator.draft_queue.approve_draft(draft_id)
    if "error" in res and res.get("status") == "NOT_FOUND":
        raise HTTPException(status_code=404, detail=res["error"])
    return res

@app.post("/api/drafts/{draft_id}/discard")
async def discard_draft(draft_id: str):
    """Discards a staged draft action."""
    res = orchestrator.draft_queue.discard_draft(draft_id)
    if "error" in res and res.get("status") == "NOT_FOUND":
        raise HTTPException(status_code=404, detail=res["error"])
    return res

@app.get("/api/routines")
async def list_routines():
    """Returns available autonomous routines and past run status."""
    return {"routines": ROUTINE_CATALOG}

@app.post("/api/routines/{routine_id}/run")
async def run_routine(routine_id: str):
    """Manually triggers an autonomous routine."""
    if routine_id == "overnight_audit":
        res = await orchestrator.routine_runner.run_overnight_audit()
        return res
    elif routine_id == "tripwire_heartbeat":
        res = await orchestrator.routine_runner.run_tripwire_heartbeat()
        return res
    else:
        raise HTTPException(status_code=404, detail=f"Routine '{routine_id}' not found")

# ── Static UI Mounting ────────────────────────────────────────────────────────
if UI_DIR.exists():
    app.mount("/ui", StaticFiles(directory=str(UI_DIR), html=True), name="ui")

@app.get("/")
async def root():
    return RedirectResponse(url="/ui/")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("QF_BOT_PORT", 9050))
    print(f"Starting Quantum Flex AI Teammate Server on port {port}...")
    uvicorn.run("bot_server:app", host="0.0.0.0", port=port, reload=False)
