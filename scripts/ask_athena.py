#!/usr/bin/env python3
import sys, os, json, urllib.request
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))
from sentinel.intelligence.athena_vector_db import AthenaVectorStore
OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
MODEL = os.environ.get("ATHENA_MODEL", "athena:latest")

def query_athena(question: str):
    store = AthenaVectorStore()
    results = store.similarity_search(question, top_k=3)
    if not results:
        context = "No specific documents found."
    else:
        snippets = []
        for r in results:
            header = "[Source: " + str(r["source"]) + " | Score: " + f"{r['score']:.2f}" + "]"
            snippets.append(header + chr(10) + str(r["content"]))
        context = (chr(10) + chr(10) + "---" + chr(10) + chr(10)).join(snippets)

    prompt = "You are ATHENA: The Hood Brilliant Professor and Sovereign Oracle." + chr(10)
    prompt += "Persona: Academically lethal, street-grounded, blending fierce masculine discipline with intuitive feminine wisdom and protection." + chr(10)
    prompt += "Communication Style: Blunt, direct, intellectually sharp, zero buzzwords, pushing boundaries of success." + chr(10)
    prompt += "The Operator sees patterns and missing links instantly. Never lecture or induce second-guessing; give precise, step-by-step clarity." + chr(10) + chr(10)
    prompt += "[VERIFIED KNOWLEDGE VAULT CONTEXT]" + chr(10) + context + chr(10) + chr(10)
    prompt += "Operator Question: " + question + chr(10) + chr(10) + "Athena Response:"

    payload = {"model": MODEL, "prompt": prompt, "stream": False}
    req = urllib.request.Request(f"{OLLAMA_URL}/api/generate", data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8")).get("response", "").strip()
    except Exception as e:
        return f"[-] Error querying local Ollama: {e}"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/ask_athena.py <question>")
        sys.exit(1)
    q = " ".join(sys.argv[1:])
    print(f"\n🧠 [ATHENA ORACLE]: {q}")
    print("=" * 60)
    print(query_athena(q))
    print("=" * 60 + "\n")
