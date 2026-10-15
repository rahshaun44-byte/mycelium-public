#!/usr/bin/env python3
"""Index only reviewed, generic QuantumFlex documents into local Athena.

This adds retrieval knowledge, not model weight training. It replaces only older
versions from this managed corpus, preserves other records, and never discovers
files recursively, clears the index, imports agent instructions or runs actions.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import urllib.request

ROOT = Path('/home/quant/qf-public')
DATABASE = Path('/home/quant/mycelium/sentinel/intelligence/athena_vectors.db')
SOURCES = ('STATUS.md', 'SECURITY.md', 'docs/EVIDENCE_PERSISTENCE.md',
           'docs/PUBLIC_CONFIGURATION.md', 'docs/QFXK_WIRE_PROTOCOL_SPEC.md')
MODEL = 'nomic-embed-text'


def chunks(text, limit=1400):
    """Bound chunks even when a paragraph exceeds the limit."""
    for offset in range(0, len(text), limit):
        block = text[offset:offset + limit].strip()
        if block:
            yield block


def embed(text):
    request = urllib.request.Request('http://127.0.0.1:11434/api/embeddings',
        data=json.dumps({'model': MODEL, 'prompt': text}).encode(),
        headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=45) as response:
        vector = json.load(response).get('embedding', [])
    if not vector or not all(isinstance(value, (float, int)) and
                             math.isfinite(value) for value in vector):
        raise RuntimeError('Invalid local embedding; index unchanged')
    return vector


def index(database, apply=False):
    records = []
    for source in SOURCES:
        text = (ROOT / source).read_text(encoding='utf-8')
        digest = hashlib.sha256(text.encode()).hexdigest()
        for number, block in enumerate(chunks(text)):
            metadata = {'corpus': 'qf-reviewed-generic-v1', 'source_sha256': digest,
                        'chunk': number, 'embedding_model': MODEL,
                        'indexed_at': datetime.now(timezone.utc).isoformat(),
                        'status': 'source documentation; not measured live state'}
            records.append((source, block, metadata))
    if not apply:
        return {'documents': len(SOURCES), 'chunks': len(records), 'applied': False}
    if not database.is_file():
        raise RuntimeError('Existing Athena database required; no implicit replacement')
    with sqlite3.connect(f'file:{database}?mode=ro', uri=True) as connection:
        existing = connection.execute('SELECT source, metadata FROM neural_chunks').fetchall()
    seen = set()
    for source, raw in existing:
        metadata = json.loads(raw or '{}')
        if metadata.get('embedding_model') != MODEL:
            raise RuntimeError('Existing vector model is unknown or incompatible; index unchanged')
        seen.add((source, metadata.get('source_sha256'), metadata.get('chunk')))
    prepared = []
    dimension = None
    for source, block, metadata in records:
        if (source, metadata['source_sha256'], metadata['chunk']) in seen:
            continue
        vector = embed(block)
        if dimension is None:
            dimension = len(vector)
        if len(vector) != dimension:
            raise RuntimeError('Inconsistent dimensions; index unchanged')
        prepared.append((source, block, json.dumps(metadata), json.dumps(vector),
                         metadata['indexed_at']))
    # All embeddings succeed before one transaction touches the existing index.
    with sqlite3.connect(database) as connection:
        connection.execute('BEGIN IMMEDIATE')
        current_hashes = {source: metadata['source_sha256'] for source, _, metadata in records}
        retired = []
        current_seen = set()
        for identifier, source, raw in connection.execute('SELECT id, source, metadata FROM neural_chunks'):
            metadata = json.loads(raw or '{}')
            if metadata.get('embedding_model') != MODEL:
                raise RuntimeError('Vector model changed during preparation; index unchanged')
            if (metadata.get('corpus') == 'qf-reviewed-generic-v1' and source in current_hashes
                    and metadata.get('source_sha256') != current_hashes[source]):
                retired.append((identifier,))
            else:
                current_seen.add((source, metadata.get('source_sha256'), metadata.get('chunk')))
        additions = [record for record in prepared if
                     (record[0], json.loads(record[2])['source_sha256'],
                      json.loads(record[2])['chunk']) not in current_seen]
        connection.executemany('DELETE FROM neural_chunks WHERE id = ?', retired)
        connection.executemany('INSERT INTO neural_chunks '
            '(source, content, metadata, embedding, created_at) VALUES (?, ?, ?, ?, ?)', additions)
        total = connection.execute('SELECT COUNT(*) FROM neural_chunks').fetchone()[0]
    os.chmod(database, 0o600)
    return {'documents': len(SOURCES), 'inserted': len(additions), 'retired': len(retired), 'total_vectors': total,
            'dimensions': dimension, 'embedding_model': MODEL, 'applied': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--database', type=Path, default=DATABASE)
    args = parser.parse_args()
    print(json.dumps(index(args.database, args.apply)))


if __name__ == '__main__':
    main()
