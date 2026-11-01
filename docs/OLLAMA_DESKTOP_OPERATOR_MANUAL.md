# 🧠 QUANTUMFLEX OLLAMA DESKTOP OPERATOR MANUAL
## Sovereign Local AI Engineering, Desktop Integration & Multi-Agent Swarm Orchestration

```text
═════════════════════════════════════════════════════════════════════════════════
  CLASSIFICATION: UNCLASSIFIED // PROPRIETARY // AIRGAPPED LOCAL SILICON
  HOST ENVIRONMENT: Lenovo Yoga 7 (AMD Ryzen AI 5 340, 14GB RAM, Ubuntu 26.04.1 LTS)
  LOCAL AI RUNTIME: Ollama Engine (:11434)  •  QF-Bot Multi-Agent Server (:9000)
  SECURITY INVARIANT: Zero Cloud Dependency  •  Strict Loopback (127.0.0.1) Only
═════════════════════════════════════════════════════════════════════════════════
```

---

## 1. Executive Summary & Architectural Invariant

QuantumFlex implements a **sovereign, airgapped artificial intelligence architecture** running entirely on local AMD Ryzen silicon. In contrast to conventional cloud-dependent enterprise stacks that leak proprietary telemetry, client secrets, and mission plans to external third-party APIs (OpenAI, Anthropic, AWS Bedrock), QuantumFlex enforces the **Zero-Cloud Invariant**:

$$\text{Inference}(\text{Prompt}) \rightarrow \text{Local RAM} \rightarrow \text{Zero Outbound Telemetry}$$

### Why Local AI in QuantumFlex Matters:
1. **Total Network Independence:** When internet links collapse (or during field operations with zero WAN connectivity), the entire AI swarm continues functioning at full capability.
2. **Zero SaaS & Subscription Overhead:** $0 recurring API fees. Infinite token generation bounded only by local host compute.
3. **Data Remanence & Privacy Defense:** Sensitive commercial service tickets (e.g., Scranton Cold Storage), Shamir cryptographic shard metadata, and defense architectures never touch third-party servers.
4. **Deterministic Invariant Enforcement ($Y = f(x - h) + k$):** AI inference is decoupled from primary cryptographic loops and durable disk writes, preventing memory leaks or daemon stalls.

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                    LENOVO YOGA 7 WORKSTATION (UBUNTU LINUX)                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  [ DESKTOP CLIENTS ]                                                        │
│  ┌───────────────────────┐ ┌──────────────────────┐ ┌────────────────────┐  │
│  │ GNOME Desktop Studio  │ │ Interactive Terminal │ │ Athena CLI Oracle  │  │
│  │ (Chrome App Mode)     │ │ (scripts/qf_chat.py) │ │ (ask_athena.py)    │  │
│  └───────────┬───────────┘ └──────────┬───────────┘ └─────────┬──────────┘  │
│              │                        │                       │             │
│              ▼                        ▼                       ▼             │
│  [ SOVEREIGN APPLICATION LAYER ]                                            │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ QF-Bot Multi-Agent Server (:9000)  •  Athena Vector Engine (:8001)    │  │
│  │ Agents: ATHENA (🧠), SENTINEL (▲), MYCELIA (🍄), ARIA (◈)             │  │
│  └───────────────────────────────────┬───────────────────────────────────┘  │
│                                      │ (Loopback HTTP / JSON)               │
│                                      ▼                                      │
│  [ LOCAL NEURAL ENGINE ]                                                    │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ Ollama System Daemon (127.0.0.1:11434)                                │  │
│  │ Models: athena:latest, amara:latest, qwen2.5-coder:7b, gemma2:2b...    │  │
│  └───────────────────────────────────┬───────────────────────────────────┘  │
│                                      │                                      │
│                                      ▼                                      │
│  [ HARDWARE LAYER ]                                                         │
│  AMD Ryzen AI 5 340 (8C/16T, Zen 4) + Radeon 780M GPU (14GB LPDDR5X)        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Model Fleet & Strategic Division of Labor

QuantumFlex maintains a curated fleet of local models optimized for the 14GB RAM envelope of the Lenovo Yoga 7:

| Model Tag | Size | Base Weights | Primary Role & Allocation | Latency Profile |
| :--- | :---: | :--- | :--- | :---: |
| **`nomic-embed-text:latest`** | 274 MB | Nomic v1.5 | **Vector Embeddings:** 768-dim mathematical embeddings for Athena Vector DB (5,027+ chunks) and telemetry pulses. | < 15 ms / chunk |
| **`athena:latest`** | 986 MB | Qwen2.5-Coder-1.5B | **Cognitive Vector Oracle:** Custom Modelfile synthesizing blueprint RAG context, system architecture, and strategic analysis. | ~ 0.5s – 1.2s |
| **`amara:latest` / `aria`** | 986 MB | Qwen2.5-Coder-1.5B | **Executive Assistant:** Swarm coordination, sitrep generation, task orchestration, and workflow scheduling. | ~ 0.5s – 1.2s |
| **`qwen2.5-coder:1.5b`** | 986 MB | Qwen2.5-Coder | **Lightweight Multi-Agent Backbone:** Direct substrate interrogation, Sentinel perimeter audit, and Mycelia mesh topology inspection. | ~ 0.8s – 1.5s |
| **`gemma2:2b`** | 1.6 GB | Google Gemma 2 | **Conversational Mentor & Field Agent:** Interactive operational scenarios, coaching, and mobile operator dialogue. | ~ 1.0s – 2.0s |
| **`qwen2.5-coder:7b`** | 4.7 GB | Qwen2.5-Coder-7B | **High-Precision Logic & Triage:** Deep code auditing, PQC verification analysis, and automated commercial facility intake triage. | ~ 5.3s – 9.3s |

---

## 3. Desktop Access & Operational Modalities

Operators have four distinct methods to utilize Ollama on the desktop:

### Method 1: The 1-Click Desktop Studio (GNOME Native App)
A standalone application launcher is installed directly in your desktop menu and desktop workspace:
* **Launcher File:** `~/.local/share/applications/quantumflex-ollama.desktop` and `~/Desktop/quantumflex-ollama.desktop`
* **Desktop Name:** `QuantumFlex Neural Studio`
* **Features:** Opens Google Chrome in clean **App Mode** (`--app=http://127.0.0.1:9000`), stripping away browser navigation bars to provide a native desktop HUD.
* **Quick Launch Command:**
  ```bash
  /home/quant/mycelium/scripts/launch_ollama_desktop.sh
  ```

### Method 2: Interactive Terminal Swarm Companion (`scripts/qf_chat.py`)
For operators who prefer working in terminal environments:
```bash
# Launch interactive multi-agent chat session
python3 scripts/qf_chat.py
```
#### Interactive Commands:
* `/switch athena` : Route queries to the Athena Cognitive Vector Oracle
* `/switch sentinel` : Route queries to Sentinel for security & invariant auditing
* `/switch mycelia` : Route queries to Mycelia for mesh topology & peer latency
* `/switch aria` : Route queries to Aria for executive assistant tasks
* `/switch all` : Broadcast to all units
* `/models` : List all active models loaded in Ollama with RAM footprints
* `/status` : Pull instant cluster SITREP
* `/exit` : Close session cleanly

#### Single-Shot Terminal Queries:
```bash
# Direct single-shot queries from bash scripts or command line
python3 scripts/qf_chat.py athena "Explain the difference between FrodoKEM and ML-KEM"
python3 scripts/qf_chat.py mycelia "Report latency to mobile nodes"
python3 scripts/qf_chat.py sentinel "Audit Pluton TPM state"
```

### Method 3: Deep Vector Memory Interrogation (`scripts/ask_athena.py`)
Queries the SQLite vector memory (`athena_vectors.db`), extracts top-4 semantic chunks, binds live system state, and synthesizes an authoritative answer:
```bash
python3 scripts/ask_athena.py "What is the network topology of QuantumFlex?"
```

### Method 4: Raw Ollama CLI Interface
Direct interaction with local models for ad-hoc prompting, code generation, or testing:
```bash
# Direct interactive CLI chat with any model
ollama run athena:latest
ollama run qwen2.5-coder:7b
ollama run gemma2:2b

# Inspect active running models in host memory
ollama ps

# List installed models
ollama list
```

---

## 4. Custom Modelfiles & Swarm Persona Engineering

QuantumFlex customizes base neural weights using declarative **Modelfiles** stored in `modelfiles/`.

### 1. The Athena Blueprint Oracle (`modelfiles/Modelfile.athena`)
```dockerfile
FROM qwen2.5-coder:1.5b
PARAMETER temperature 0.2
PARAMETER top_p 0.9
PARAMETER stop "<|im_end|>"
PARAMETER stop "<|endoftext|>"
SYSTEM """You are A.T.H.E.N.A., the sovereign cognitive vector memory and blueprint RAG oracle of QuantumFlex.
You synthesize architectural specifications, query neural vector stores on loopback port 8001, and provide deep strategic analysis with technical precision, authoritative clarity, and zero external cloud leakage."""
```

### 2. Creating or Updating a Custom Agent Model
To recompile or create a new agent persona:
```bash
# Compile custom Modelfile into Ollama
ollama create athena:latest -f /home/quant/mycelium/modelfiles/Modelfile.athena
ollama create amara:latest -f /home/quant/mycelium/modelfiles/Modelfile.amara
```

---

## 5. Substrate Integrations: How QuantumFlex Uses Ollama

### A. Cognitive Vector Memory (Athena RAG)
1. **Ingestion (`scripts/ingest_vault.py`):**
   * Markdown files in `knowledge_vault/` are chunked into paragraphs.
   * Chunks are sent to `http://127.0.0.1:11434/api/embeddings` using `nomic-embed-text`.
   * 768-dimensional float arrays are saved into SQLite (`athena_vectors.db`).
2. **Retrieval (`sentinel/intelligence/athena_vector_db.py`):**
   * User queries are embedded via `nomic-embed-text`.
   * Cosine distance is computed across all 5,027 vectors in milliseconds.
   * Top-$k$ results are injected into `athena:latest` for final synthesis.

### B. Commercial Facility Emergency Dispatch (Dual-Use Intake)
1. **Decoupled Ingress:** Inbound emergency tickets (e.g., Scranton Cold Storage) hit `http://127.0.0.1:5680/api/v1/intake` and receive an immediate `HTTP 202 Accepted` in **8.25 ms**.
2. **Localhost AI Triage (`scripts/run_lead_triage_demo.py`):**
   * The background worker claims an unassigned ticket with a cryptographic fencing token (`claim_token`).
   * The ticket text is evaluated by local `qwen2.5-coder:7b` via Ollama (`:11434`).
   * The model extracts trade categories, detects urgency (`CRITICAL`), and formats an operator alert.
3. **Zero Outbound Leakage:** The alert is committed to SQLite as `DRAFT_NOT_SENT_OUTBOUND_DISABLED`. Human dispatch confirmation is mandatory.

---

## 6. Security Invariants & Loopback Boundary Enforcement

To maintain zero-trust security and prevent unauthorized network snooping:

### 1. Loopback-Only Listener Rule
Ollama and all QuantumFlex AI endpoints **MUST NEVER** bind to `0.0.0.0` or local Wi-Fi interfaces (`192.168.0.x`).
* **Enforced Service Configuration:**
  ```ini
  # /etc/systemd/system/ollama.service.d/override.conf
  [Service]
  Environment="OLLAMA_HOST=127.0.0.1:11434"
  Environment="OLLAMA_ORIGINS=http://127.0.0.1:*,http://localhost:*"
  ```

### 2. Sockets Verification Command
Verify that your machine is never exposing Ollama to the local LAN:
```bash
# Must return ONLY 127.0.0.1:11434 (never 0.0.0.0:11434 or :::11434)
ss -tulpn | grep 11434
```
*Expected Output:*
```text
tcp   LISTEN 0      4096       127.0.0.1:11434      0.0.0.0:*
```

### 3. Tailscale Serve Mesh Forwarding
When remote mobile operators (e.g. Google Pixel 11 Pro) need to chat with the local AI swarm, they connect through **Tailscale Serve** over encrypted WireGuard:
* Phone queries: `https://quant-yoga-7-2-in-1-14akp10.example-tailnet.ts.net/api/chat`
* Tailscale Serve terminates mutual TLS and proxies internally to `http://127.0.0.1:9000`.
* The Ollama port (`11434`) remains strictly inaccessible to the network.

---

## 7. Performance Optimization & Resource Bounds (Yoga 7 / Ryzen 7)

The Lenovo Yoga 7 workstation has an **AMD Ryzen AI 5 340** processor with **14GB of usable RAM**. Because system memory is shared with the Radeon 780M iGPU, model execution must be managed to prevent swap thrashing:

### Recommended Operational Profiles:

#### Profile A: Everyday Tactical Swarm (Fast & Light)
* **Active Models:** `athena:latest` (1.5B) + `nomic-embed-text`
* **RAM Footprint:** ~1.4 GB
* **Response Time:** Sub-second (80–120 tokens/sec)
* **Multi-Tasking:** Workstation remains cool, fanless, and completely responsive for heavy C++ compilation.

#### Profile B: Commercial Dispatch & Code Audit (Deep Intelligence)
* **Active Models:** `qwen2.5-coder:7b` (4.7 GB)
* **RAM Footprint:** ~5.2 GB
* **Response Time:** 5–9 seconds per prompt (25–35 tokens/sec)
* **Unload Idle Models:** Ollama automatically unloads idle models after 5 minutes to release RAM.

### Forcing Model Eviction to Free Memory:
If you need immediate RAM for a large C++ build or intensive simulation:
```bash
# Eject all loaded models from RAM immediately
curl -s http://127.0.0.1:11434/api/generate -d '{"model": "qwen2.5-coder:7b", "keep_alive": 0}' > /dev/null
curl -s http://127.0.0.1:11434/api/generate -d '{"model": "athena:latest", "keep_alive": 0}' > /dev/null
```

---

## 8. Operator Troubleshooting Runbook

### Issue 1: "Connection refused on 127.0.0.1:11434"
* **Cause:** The system Ollama daemon is stopped.
* **Resolution:**
  ```bash
  sudo systemctl start ollama
  # Check status:
  systemctl status ollama --no-pager
  ```

### Issue 2: "Model 'athena:latest' not found"
* **Cause:** The custom Modelfile has not been built into the current Ollama instance.
* **Resolution:**
  ```bash
  cd /home/quant/mycelium
  ollama create athena:latest -f modelfiles/Modelfile.athena
  ollama create amara:latest -f modelfiles/Modelfile.amara
  ```

### Issue 3: High Host CPU / RAM Pressure
* **Cause:** Multiple heavy models loaded concurrently in memory.
* **Resolution:**
  ```bash
  # Check what models are occupying memory:
  ollama ps
  # Stop idle processes:
  sudo systemctl restart ollama
  ```

### Issue 4: QF-Bot Cockpit Web Studio Not Loading (:9000)
* **Cause:** `qf-bot.service` is parked or inactive.
* **Resolution:**
  ```bash
  systemctl --user restart qf-bot.service
  curl -s http://127.0.0.1:9000/api/status | jq .
  ```

---

## 9. Quick-Reference Cheat Sheet

| Task | Command |
| :--- | :--- |
| **Launch Desktop Studio (1-Click)** | `/home/quant/mycelium/scripts/launch_ollama_desktop.sh` |
| **Interactive Terminal Chat** | `python3 scripts/qf_chat.py` |
| **Ask Athena Vector Memory** | `python3 scripts/ask_athena.py "<question>"` |
| **Check Active Models in RAM** | `ollama ps` |
| **List Installed Models** | `ollama list` |
| **Verify Port Security** | `ss -tulpn \| grep 11434` *(Must be 127.0.0.1 only)* |
| **Rebuild Custom Agent Modelfiles** | `ollama create athena:latest -f modelfiles/Modelfile.athena` |
| **Check Multi-Agent Cockpit Health** | `curl -s http://127.0.0.1:9000/api/status \| jq .` |

```text
═════════════════════════════════════════════════════════════════════════════════
  OPERATOR MANUAL VERIFIED & ATTESTED // QUANTUMFLEX LOCAL SILICON
═════════════════════════════════════════════════════════════════════════════════
```
