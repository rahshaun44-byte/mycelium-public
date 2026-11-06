#!/usr/bin/env python3
import urllib.request
import json
import os
import sys

SUMMARY_PATH = os.path.expanduser("~/case_summary_for_legal_handover.txt")
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "athena:latest"

def load_ledger():
    if not os.path.exists(SUMMARY_PATH):
        print(f"[-] Error: Case summary ledger not found at {SUMMARY_PATH}")
        sys.exit(1)
    with open(SUMMARY_PATH, "r", encoding="utf-8") as f:
        return f.read()

def query_amara(custom_prompt=None):
    ledger_content = load_ledger()
    default_prompt = (
        "Based on the ingested case audit ledger and the operator's strategic decision "
        "to reject local bad-faith drama, maintain absolute zero contact, and protect "
        "their livelihood and QuantumFlex technical baseline:\n\n"
        f"{ledger_content}\n\n"
        "QUESTION: What are your precise tactical recommendations for the operator's "
        "next steps to secure legal standing, protect livelihood, and maintain unbroken technical momentum?"
    )
    prompt = custom_prompt if custom_prompt else default_prompt
    payload = {
        "model": MODEL_NAME,
        "system": "You are AMARA, the AI guardian intelligence for Quantum Flex. Provide direct, tactical, and grounded operational recommendations to protect the operator's livelihood, technical work, and legal standing under strict zero-contact constraints. No filler, absolute clarity.",
        "prompt": prompt,
        "stream": False
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(OLLAMA_URL, data=data, headers={"Content-Type": "application/json"})
    print("[*] Querying local Amara instance (athena:latest)...")
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
            print("\n" + "=" * 80)
            print("AMARA TACTICAL ADVISORY:")
            print("=" * 80)
            print(result.get("response", "No response returned."))
            print("=" * 80 + "\n")
    except Exception as e:
        print(f"[-] API Connection Error: {e}")

if __name__ == "__main__":
    user_query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
    query_amara(user_query)
