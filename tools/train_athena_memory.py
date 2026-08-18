#!/usr/bin/env python3
"""
═════════════════════════════════════════════════════════════════════
  QUANTUM FLEX: ATHENA NEURAL MEMORY TRAINING & INGESTION PIPELINE
═════════════════════════════════════════════════════════════════════
Grounds Athena and Amara with absolute truth by indexing all architecture
blueprints, security guidelines, API schemas, and historical logs into
AthenaVectorStore via nomic-embed-text.
"""

import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime

# Safe console rendering for Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT_DIR = Path(__file__).resolve().parents[1]
REPOS_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from sentinel.intelligence.athena_vector_db import AthenaVectorStore

def recursive_chunk_text(text: str, chunk_size: int = 750, chunk_overlap: int = 100) -> list:
    """Lightweight native text chunker adhering to semantic markdown boundaries."""
    paragraphs = re.split(r'(\n#{1,4} |\n\n+)', text)
    chunks = []
    current_chunk = ""

    for piece in paragraphs:
        if len(current_chunk) + len(piece) <= chunk_size:
            current_chunk += piece
        else:
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
            overlap = current_chunk[-chunk_overlap:] if len(current_chunk) > chunk_overlap else ""
            current_chunk = overlap + piece

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks if chunks else [text]

def train_and_index_knowledge():
    print("=" * 68)
    print("  QUANTUM FLEX: COGNITIVE NEURAL INGESTION & TRAINING")
    print("=" * 68)

    store = AthenaVectorStore()
    print(f"[*] Native Vector Store Target: {store.db_path}")
    print(f"[*] Existing Neural Vectors  : {store.count()}")

    # 1. Discover all high-value knowledge sources
    target_docs = []
    
    priority_files = [
        REPOS_DIR / "QUANTUM_ENTANGLEMENT_MASTER.md",
        ROOT_DIR / "CLAUDE.md",
        ROOT_DIR / "quantum_flex_architecture.md",
        ROOT_DIR / "sentinel" / "knowledge_base" / "quantum_flex_architecture.txt",
        REPOS_DIR / "qflex" / "qflex-clean" / "MASTER_STATE_CLARIFICATION.md",
        REPOS_DIR / "qflex" / "qflex-clean" / "OPEN_FAULTS.md",
    ]

    for p in priority_files:
        if p.exists():
            target_docs.append(p)

    for folder in [ROOT_DIR / "docs", ROOT_DIR / "sentinel" / "knowledge_base"]:
        if folder.exists():
            for f in folder.glob("*.md"):
                if f not in target_docs:
                    target_docs.append(f)
            for f in folder.glob("*.txt"):
                if f not in target_docs:
                    target_docs.append(f)

    print(f"[*] Discovered {len(target_docs)} core knowledge artifacts.")

    # Clear old vectors for clean training pass
    store.clear()
    total_indexed = 0

    for doc_path in target_docs:
        try:
            content = doc_path.read_text(encoding="utf-8", errors="ignore")
            chunks = recursive_chunk_text(content, chunk_size=750, chunk_overlap=100)
            doc_added = 0
            for i, chunk in enumerate(chunks):
                success = store.add_document(
                    content=chunk,
                    source=f"sentinel/{doc_path.name}",
                    metadata={
                        "file_path": str(doc_path),
                        "chunk_id": i,
                        "ingested_at": datetime.now().isoformat(),
                        "domain": "quantum_flex_architecture"
                    }
                )
                if success:
                    doc_added += 1
                    total_indexed += 1
            print(f"  [+] Ingested {doc_added:>3}/{len(chunks)} neural chunks from {doc_path.name}")
        except Exception as e:
            print(f"  [-] Failed processing {doc_path.name}: {e}")

    final_count = store.count()
    print("\n" + "=" * 68)
    print(f"  TRAINING COMPLETE: {final_count} TOTAL NEURAL VECTORS ACTIVE")
    print("  ATHENA & AMARA ARE NOW COGNITIVELY GROUNDED IN MASTER STATE")
    print("=" * 68 + "\n")

if __name__ == "__main__":
    train_and_index_knowledge()
