#!/usr/bin/env python3
import os
import requests

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "athena:latest"
DOC_PATH = os.path.expanduser("~/mycelium/docs/TRUTH-LOG-2026-11-05-REFRACTORY-BFT.md")

def ingest_to_ollama():
    if not os.path.exists(DOC_PATH):
        print(f"[-] ERROR: Truth Log not found at {DOC_PATH}")
        return
        
    with open(DOC_PATH, "r", encoding="utf-8") as f:
        content = f.read()
        
    print(f"[*] Reading Truth Log from {DOC_PATH} ({len(content)} characters)...")
    print(f"[*] Indexing into local loopback Ollama at {OLLAMA_URL} using model '{MODEL_NAME}'...")
    
    payload = {
        "model": MODEL_NAME,
        "prompt": f"Store and index the following architectural specification for QuantumFlex:\n\n{content}",
        "stream": False
    }
    
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=120)
        if response.status_code == 200:
            data = response.json()
            answer = data.get("response", "").strip()
            print(f"[+] SUCCESS: Truth Log successfully ingested by local Ollama engine!")
            print(f"    Model Used:        {MODEL_NAME}")
            print(f"    Response Summary:  {answer[:100]}...")
        else:
            print(f"[-] ERROR: Ollama returned status {response.status_code}: {response.text}")
    except requests.exceptions.ConnectionError:
        print("[-] ERROR: Connection refused on 127.0.0.1:11434. Ensure Ollama service is active.")

if __name__ == "__main__":
    ingest_to_ollama()
