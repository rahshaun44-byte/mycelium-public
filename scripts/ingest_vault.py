#!/usr/bin/env python3
"""
QuantumFlex Knowledge Vault Ingestion Tool
===========================================
Reads all .md and .txt files from ~/mycelium/knowledge_vault
and embeds them directly into Athena local vector memory.
"""

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from sentinel.intelligence.athena_vector_db import AthenaVectorStore

def main():
    vault_dir = ROOT_DIR / 'knowledge_vault'
    if not vault_dir.exists():
        print(f'[-] Knowledge vault not found at: {vault_dir}')
        return

    store = AthenaVectorStore()
    files = list(vault_dir.glob('*.md')) + list(vault_dir.glob('*.txt'))
    
    if not files:
        print(f'[-] No .md or .txt files found in {vault_dir}')
        return

    print(f'[*] Ingesting {len(files)} files into Athena Vector Store...')
    for p in sorted(files):
        try:
            text = p.read_text(encoding='utf-8')
            store.add_document(content=text, source=p.name, metadata={'source_path': str(p)})
            print(f'  [+] Successfully ingested: {p.name}')
        except Exception as e:
            print(f'  [-] Failed to ingest {p.name}: {e}')

    print(f'[*] Done. Athena now holds {store.count()} total vectors.')

if __name__ == '__main__':
    main()
