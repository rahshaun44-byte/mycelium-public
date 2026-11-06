#!/usr/bin/env python3
import requests
import sys

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "athena:latest"

PROMPT = (
    "Based on the recently ingested QuantumFlex Truth Log (TRUTH-LOG-2026-11-05-REFRACTORY-BFT.md), "
    "explain how the refractory window variable (k) and the Ghost Node entropy sink (h) "
    "work together to eliminate TOCTOU race conditions and Byzantine faults under our Y = f(x - h) + k invariant."
)

def query_athena():
    print(f"[*] Querying local loopback Athena ({MODEL_NAME}) at {OLLAMA_URL}...")
    payload = {
        "model": MODEL_NAME,
        "prompt": PROMPT,
        "stream": False
    }
    
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=120)
        if response.status_code == 200:
            data = response.json()
            answer = data.get("response", "").strip()
            print("\n[+] ATHENA RESPONSE:\n")
            print(answer)
            print("\n" + "="*50)
        else:
            print(f"[-] ERROR: Ollama returned status {response.status_code}: {response.text}")
    except requests.exceptions.ConnectionError:
        print("[-] ERROR: Connection refused on 127.0.0.1:11434. Ensure Ollama is running.")

if __name__ == "__main__":
    query_athena()
