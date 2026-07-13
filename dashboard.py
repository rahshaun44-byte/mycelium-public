from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import json
import requests
import asyncio

app = FastAPI(title="A.M.A.R.A. Dashboard")

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"

@app.get("/")
async def home():
    return HTMLResponse("""
    <html>
    <head><title>A.M.A.R.A. Dashboard</title>
    <style>body{font-family:Arial; max-width:800px; margin:auto; padding:20px;}</style>
    </head>
    <body>
        <h1>Quantum Flex • A.M.A.R.A. Live Chat</h1>
        <p>Gemma3:12b • Ghost Node Synced</p>
        <div id="chat" style="height:400px; overflow-y:scroll; border:1px solid #ccc; padding:10px; margin-bottom:10px;"></div>
        <input id="input" style="width:80%" placeholder="Ask anything...">
        <button onclick="sendMessage()">Send</button>

        <script>
        let ws = new WebSocket("ws://localhost:8000/ws");
        ws.onmessage = function(event) {
            document.getElementById("chat").innerHTML += "<p><b>Ollama:</b> " + event.data + "</p>";
        };
        function sendMessage() {
            let msg = document.getElementById("input").value;
            if (msg) {
                document.getElementById("chat").innerHTML += "<p><b>You:</b> " + msg + "</p>";
                ws.send(msg);
                document.getElementById("input").value = "";
            }
        }
        </script>
    </body>
    </html>
    """)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            # Call Ollama
            payload = {
                "model": "gemma3:12b",
                "messages": [{"role": "user", "content": data}],
                "stream": False
            }
            r = requests.post(OLLAMA_URL, json=payload, timeout=60)
            response = r.json()["message"]["content"]
            await websocket.send_text(response)
    except WebSocketDisconnect:
        pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
