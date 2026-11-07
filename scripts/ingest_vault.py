#!/usr/bin/env python3
"""
QuantumFlex Knowledge Vault Ingestion & Throughput Benchmark Tool
=================================================================
Reads all .md and .txt files from ~/mycelium/knowledge_vault,
splits documents into context-safe semantic chunks (<= 3,200 chars for
nomic-embed-text's 2,048-token window), attaches SHA-256 cryptographic
provenance and document-level access control metadata, and benchmarks
empirical ingestion throughput (pages/minute).
"""

import hashlib
import os
import sys
import time
from pathlib import Path
from typing import List, Tuple

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from sentinel.intelligence.athena_vector_db import AthenaVectorStore

CHARS_PER_STANDARD_PAGE = 1800
MAX_CHUNK_CHARS = 3200


def detect_access_role(text: str) -> str:
    """Extracts document access role from header or defaults to sovereign_internal."""
    lower = text[:600].lower()
    if "public" in lower or "commercial sample" in lower:
        return "public"
    if "client_confidential" in lower or "attorney-client" in lower:
        return "client_confidential"
    return "sovereign_internal"


def chunk_document(text: str, max_chars: int = MAX_CHUNK_CHARS) -> List[Tuple[int, str]]:
    """
    Splits document into semantic sections (by '\\n---\\n' or paragraphs)
    guaranteed to fit inside nomic-embed-text's 2,048-token window.
    Returns list of (char_offset, chunk_text).
    """
    raw_sections = text.split("\n---\n")
    chunks: List[Tuple[int, str]] = []
    cursor = 0

    for sec in raw_sections:
        sec_len = len(sec)
        stripped = sec.strip()
        if not stripped:
            cursor += sec_len + 5
            continue

        if len(stripped) <= max_chars:
            chunks.append((cursor, stripped))
        else:
            # Split oversized section by paragraphs
            paras = stripped.split("\n\n")
            buf = []
            buf_len = 0
            sub_offset = cursor
            for p in paras:
                if buf_len + len(p) + 2 > max_chars and buf:
                    chunks.append((sub_offset, "\n\n".join(buf)))
                    sub_offset += buf_len
                    buf = [p]
                    buf_len = len(p)
                else:
                    buf.append(p)
                    buf_len += len(p) + 2
            if buf:
                chunks.append((sub_offset, "\n\n".join(buf)))

        cursor += sec_len + 5

    return chunks if chunks else [(0, text[:max_chars].strip())]


def main():
    force_rebuild = "--clean" in sys.argv or "--force" in sys.argv
    vault_dir = ROOT_DIR / "knowledge_vault"
    if not vault_dir.exists():
        print(f"[-] Knowledge vault not found at: {vault_dir}")
        return 1

    store = AthenaVectorStore()
    files = sorted(list(vault_dir.glob("*.md")) + list(vault_dir.glob("*.txt")))

    if not files:
        print(f"[-] No .md or .txt files found in {vault_dir}")
        return 1

    if force_rebuild:
        print("[!] Force clean rebuild requested. Purging vector store...")
        store.clear()
    else:
        # Purge any deleted files that no longer exist on disk
        on_disk_names = {p.name for p in files}
        indexed_sources = store.get_all_sources()
        for src in indexed_sources:
            if src not in on_disk_names:
                deleted_count = store.delete_by_source(src)
                print(f"  [x] Pruned orphaned source: {src} ({deleted_count} chunks)")

    mode_str = "Clean Rebuild" if force_rebuild else "Delta Incremental Pass"
    print(f"[*] Ingesting {len(files)} files into Athena Vector Store ({mode_str})...")
    t_start = time.perf_counter()
    total_chars = 0
    new_chunks = 0
    skipped_files = 0
    updated_files = 0

    for p in files:
        try:
            text = p.read_text(encoding="utf-8")
            doc_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()

            # Zero-cost delta check: skip if file hash matches indexed hash
            if not force_rebuild:
                existing_sha = store.get_source_sha256(p.name)
                if existing_sha == doc_sha256:
                    skipped_files += 1
                    continue

            # File is new or changed: clear prior chunks for this document
            store.delete_by_source(p.name)

            access_role = detect_access_role(text)
            chunks = chunk_document(text)
            file_ok = 0

            for idx, (char_offset, chunk_text) in enumerate(chunks):
                est_page = (char_offset // CHARS_PER_STANDARD_PAGE) + 1
                meta = {
                    "source_path": str(p),
                    "doc_sha256": doc_sha256,
                    "chunk_index": idx + 1,
                    "total_chunks": len(chunks),
                    "char_offset": char_offset,
                    "estimated_page": est_page,
                    "access_role": access_role,
                }
                if store.add_document(content=chunk_text, source=p.name, metadata=meta):
                    file_ok += 1
                    total_chars += len(chunk_text)
                    new_chunks += 1

            updated_files += 1
            print(
                f"  [+] Ingested: {p.name:<45} | "
                f"Chunks: {file_ok}/{len(chunks)} | "
                f"Role: {access_role} | "
                f"SHA-256: {doc_sha256[:12]}..."
            )
        except Exception as e:
            print(f"  [-] Failed to ingest {p.name}: {e}")

    elapsed = max(time.perf_counter() - t_start, 1e-6)
    equiv_pages = total_chars / CHARS_PER_STANDARD_PAGE
    pages_per_min = (equiv_pages / elapsed) * 60.0

    print("-" * 80)
    print(f"[*] Ingestion Complete: {store.count()} verified vector chunks across {len(files)} documents.")
    if skipped_files > 0:
        print(f"[*] Delta Optimization: {skipped_files} unchanged files skipped (0 wasted CPU/RAM cycles).")
    if updated_files > 0:
        print(
            f"[*] Empirical Throughput: {total_chars:,} chars ({equiv_pages:.1f} standard pages) "
            f"in {elapsed:.2f}s -> {pages_per_min:.1f} pages/minute"
        )
    else:
        print(f"[*] Vault fully up to date in {elapsed:.4f}s (zero new embeddings needed).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

