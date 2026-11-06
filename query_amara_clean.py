#!/usr/bin/env python3
import urllib.request
import json
import os

DB_PATH = os.path.expanduser("~/case_summary_for_legal_handover.txt")
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"

if not os.path.exists(DB_PATH):
    print(f"[-] Error: Summary file not found at {DB_PATH}")
    exit(1)

with open(DB_PATH, "r", encoding="utf-8") as f:
    summary_content = f.read()

payload = {
    "model": "athena:latest",
    "system": "You are a strict legal telemetry parser. You must ONLY output facts directly present in the provided text. Never invent cyber attacks, malicious payloads, or software exploits when discussing case audit logs.",
    "prompt": f"Read this official case ledger and answer the question below strictly using its contents:\n\n{summary_content}\n\nQUESTION: What exact event occurred immediately prior to the retaliatory eviction? List the chronological events in order.",
    "stream": False
}

data = json.dumps(payload).encode("utf-8")
req = urllib.request.Request(
    OLLAMA_URL, 
    data=data, 
    headers={"Content-Type": "application/json"}
)

print("[*] Sending clean payload to local Amara instance...")
try:
    with urllib.request.urlopen(req, timeout=60) as response:
        result = json.loads(response.read().decode("utf-8"))
        print("\n" + "=" * 80)
        print("AMARA CLEAN RECALL RESPONSE:")
        print("=" * 80)
        print(result.get("response", "No response field found in output."))
        print("=" * 80 + "\n")
except Exception as e:
    print(f"[-] API Error: {e}")
