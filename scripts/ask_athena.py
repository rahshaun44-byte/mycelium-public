#!/usr/bin/env python3
import sys, os, json, urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from sentinel.intelligence.athena_vector_db import AthenaVectorStore

OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
MODEL = os.environ.get("ATHENA_MODEL", "athena:latest")


def query_athena(question: str, allowed_roles=None) -> str:
    store = AthenaVectorStore()
    results = store.similarity_search(question, top_k=3, allowed_roles=allowed_roles)
    if not results:
        context = "No specific documents found."
    else:
        snippets = []
        for r in results:
            meta = r.get("metadata") or {}
            sha_short = str(meta.get("chunk_sha256", meta.get("doc_sha256", "")))[:12]
            provenance_suffix = f" | SHA256: {sha_short}" if sha_short else ""
            header = f"[Source: {r['source']}{provenance_suffix} | Score: {r['score']:.2f}]"
            snippets.append(f"{header}\n{r['content']}")
        context = "\n\n---\n\n".join(snippets)

    prompt = (
        "You are ATHENA: Sovereign Intelligence and Strategic Oracle.\n"
        "Persona: Lethal, street-grounded, blending fierce masculine discipline with intuitive feminine wisdom and protection.\n"
        "Communication Style: Blunt, direct, intellectually sharp, zero buzzwords, pushing boundaries of success.\n"
        "The Operator sees patterns and missing links instantly. Never lecture or induce second-guessing; give precise, step-by-step clarity.\n\n"
        f"[VERIFIED KNOWLEDGE VAULT CONTEXT]\n{context}\n\n"
        f"Operator Question: {question}\n\n"
        "Athena Response:"
    )

    payload = {"model": MODEL, "prompt": prompt, "stream": False}
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8")).get("response", "").strip()
    except Exception as e:
        return f"[-] Error querying local Ollama: {e}"


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Query ATHENA: Sovereign Intelligence and Strategic Oracle")
    parser.add_argument("question", nargs="+", help="Question to ask Athena")
    parser.add_argument(
        "--role",
        action="append",
        dest="roles",
        help="Optional access role filter (public, client_confidential, sovereign_internal)",
    )
    args = parser.parse_args()
    q = " ".join(args.question)
    print(f"\n🧠 [ATHENA ORACLE]: {q}")
    print("=" * 60)
    print(query_athena(q, allowed_roles=args.roles))
    print("=" * 60 + "\n")
