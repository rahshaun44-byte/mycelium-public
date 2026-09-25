---
name: quantumflex-ai-oracle
description: >-
  Local neural model orchestration via Ollama, Athena cognitive memory RAG vault
  ingestion, Amara autonomous agent loop, LLM task swarm ("The Claw"), and offline inference.
---

# QuantumFlex AI, Oracle & Autonomous Swarm Playbook

This skill provides operational and development workflows for managing local AI models, dense vector RAG knowledge retrieval, and the autonomous task swarm.

---

## 1. Local Neural Models (Ollama Stack)

QuantumFlex runs strictly local, offline-capable inference using the Ollama runtime on `127.0.0.1:11434`.

### Available Models & Roles:
| Model | Size / Base | Role & Purpose |
|---|---|---|
| `athena:latest` | 1.5B (Qwen2.5-Coder) | High-speed cognitive Oracle & RAG context synthesizer |
| `amara:latest` | 1.5B (Qwen2.5-Coder) | Autonomous decision agent & system orchestration |
| `qwen2.5-coder:1.5b` | 1.5B | Ultra-low latency code & structured output generation |
| `qwen2.5-coder:7b` | 7.6B | Deep multi-step reasoning & complex architecture analysis |
| `gemma2:2b` | 2.6B | General comprehension & fallback semantic parsing |
| `nomic-embed-text` | 137M | Dense vector embeddings for Knowledge Vault similarity search |

### Verifying Ollama Health:
```bash
curl -s http://127.0.0.1:11434/api/tags | jq '.models[].name'
```

---

## 2. Athena Cognitive Memory & Knowledge Vault

Athena indexes Markdown documents in `knowledge_vault/` into dense vector embeddings using `nomic-embed-text` and stores them in SQLite (`data/athena_memory.db`).

### Ingesting & Re-indexing Knowledge Vault:
```bash
/home/quant/mycelium/venv/bin/python3 scripts/ingest_vault.py
```
*Action:* Parses documents in `knowledge_vault/`, computes embeddings, and builds the local vector index.

### Querying the Athena Oracle:
```bash
/home/quant/mycelium/venv/bin/python3 scripts/ask_athena.py "What are the fail-closed invariants of QuantumFlex?"
```

### Running the Athena API Service:
```bash
/home/quant/mycelium/venv/bin/python3 mcp_layer/athena_api.py
```

---

## 3. Autonomous LLM Task Swarm ("The Claw")

The task swarm breaks down high-level directives into atomic executable jobs via Ollama and executes them concurrently using a Postgres task queue.

### Architecture:
1. **Controller (`mcp_layer/controller.py`)**: Breaks directives into discrete task definitions and enqueues them into Postgres db `telemetry` table `task_queue`.
2. **Workers (`mcp_layer/swarm_worker.py`)**: Polls `task_queue` with `SELECT ... FOR UPDATE SKIP LOCKED`, executes tasks, and logs results to `memory_logs`.

### Starting the Swarm Controller:
```bash
/home/quant/mycelium/venv/bin/python3 mcp_layer/controller.py --directive "Perform full system health and security scan"
```

### Starting Swarm Worker Pool:
```bash
/home/quant/mycelium/venv/bin/python3 mcp_layer/swarm_worker.py --workers 2
```

---

## 4. Interactive Terminal Chat (`qf_chat.py`)

Direct interactive chat with QuantumFlex models with context awareness:
```bash
/home/quant/mycelium/venv/bin/python3 scripts/qf_chat.py --model athena:latest
```
