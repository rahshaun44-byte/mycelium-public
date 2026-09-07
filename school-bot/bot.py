#!/usr/bin/env python3
import os
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

app = FastAPI(title="School Bot Interface", description="Educational assistant with isolated filesystem agency")

QF_API_BASE = "http://127.0.0.1:9050/api"
OLLAMA_API_BASE = "http://127.0.0.1:11434/api/chat"
MODEL_NAME = "qwen2.5-coder:1.5b"

ALLOWED_PATHS = ["/home/quant/SNHU_Vault", "/home/quant/SNHU_C5_Term"]

SYSTEM_PROMPT = """You are an autonomous AI School Assistant. You have access to the user's school directories via tools.
Use the `list_directory`, `read_file`, and `write_file` tools to assist the user with their coursework.
You are strictly sandboxed. Never mention PQC or QuantumFlex."""

class ChatRequest(BaseModel):
    message: str

def validate_path(requested_path: str) -> str:
    """Ensures path is within the allowed SNHU directories."""
    abs_path = os.path.abspath(requested_path)
    for allowed in ALLOWED_PATHS:
        if abs_path.startswith(os.path.abspath(allowed)):
            return abs_path
    raise ValueError(f"Path traversal blocked: {abs_path} is outside allowed school directories.")

# Tool implementations
def tool_list_directory(path: str) -> str:
    try:
        safe_path = validate_path(path)
        if os.path.isdir(safe_path):
            return "\n".join(os.listdir(safe_path))
        return "Error: Directory not found."
    except Exception as e:
        return str(e)

def tool_read_file(path: str) -> str:
    try:
        safe_path = validate_path(path)
        with open(safe_path, "r") as f:
            return f.read()
    except Exception as e:
        return str(e)

def tool_write_file(path: str, content: str) -> str:
    try:
        safe_path = validate_path(path)
        os.makedirs(os.path.dirname(safe_path), exist_ok=True)
        with open(safe_path, "w") as f:
            f.write(content)
        return "File successfully written."
    except Exception as e:
        return str(e)

# Tool Schema
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "Lists all files and folders in a specific school directory. Example: /home/quant/SNHU_Vault",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Absolute path to the directory"}},
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Reads the contents of a specific file in the school directory.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Absolute path to the file"}},
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Creates or overwrites a file with the given content in the school directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path to the file"},
                    "content": {"type": "string", "description": "Content to write"}
                },
                "required": ["path", "content"]
            }
        }
    }
]

async def agent_loop(user_message: str) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message}
    ]
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        for _ in range(3):
            resp = await client.post(OLLAMA_API_BASE, json={
                "model": MODEL_NAME,
                "messages": messages,
                "tools": TOOLS,
                "stream": False
            })
            if resp.status_code != 200:
                return f"Error contacting AI engine: {resp.text}"
            
            data = resp.json()
            message = data.get("message", {})
            messages.append(message)
            
            tool_calls = message.get("tool_calls")
            if not tool_calls:
                return message.get("content", "I am done thinking.")
            
            # Execute tools
            for call in tool_calls:
                func_name = call.get("function", {}).get("name")
                args = call.get("function", {}).get("arguments", {})
                
                result = ""
                if func_name == "list_directory":
                    result = tool_list_directory(args.get("path", ""))
                elif func_name == "read_file":
                    result = tool_read_file(args.get("path", ""))
                elif func_name == "write_file":
                    result = tool_write_file(args.get("path", ""), args.get("content", ""))
                else:
                    result = f"Error: Unknown tool {func_name}"
                    
                messages.append({
                    "role": "tool",
                    "content": result,
                    "name": func_name
                })
        return "I have reached the maximum number of actions for this request."

@app.get("/api/mesh_status")
async def get_mesh_status():
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{QF_API_BASE}/status")
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        pass
    return {"error": "Mesh unreachable"}

@app.post("/api/chat")
async def chat(req: ChatRequest):
    msg = req.message.lower()
    
    if "check mesh status" in msg or "status of the mesh" in msg:
        status_data = await get_mesh_status()
        if "error" in status_data:
            return {"response": "I cannot reach the QuantumFlex Mesh right now. Is the Core Node online?"}
        return {"response": f"The QuantumFlex mesh is ONLINE. Connected teammates: {status_data.get('teammates_online', 0)}"}
    
    ai_response = await agent_loop(req.message)
    return {"response": ai_response}

app.mount("/ui", StaticFiles(directory="ui", html=True), name="ui")

@app.get("/")
async def root():
    return RedirectResponse(url="/ui/")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("SCHOOL_BOT_PORT", 9060))
    print(f"Starting Agentic School Bot on port {port}...")
    uvicorn.run("bot:app", host="0.0.0.0", port=port, reload=False)
