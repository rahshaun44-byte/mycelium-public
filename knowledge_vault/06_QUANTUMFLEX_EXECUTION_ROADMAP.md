# QuantumFlex: 06 — Commercial & Operational Execution Roadmap

**Document ID:** QF-EXEC-06  
**Revision:** 1.0  
**Effective Date:** 2026-10-30  
**Governing Standard:** Truth-in-Assurance & Real-Hardware Invariant  
**Host Architecture:** `qfx-yoga` (Lenovo Yoga 7 2-in-1, AMD Ryzen AI 5 340, 16 GB Unified LPDDR5x, Microsoft Pluton TPM 2.0)  
**Cluster Nodes:** `qfx-yoga` (Primary), `qfx-pixel` (Pixel 11 Pro, Titan M2), `g6pro` (HP ProBook 450 G6, Dedicated Kafka Broker)  
**Zero-Cloud Spend Invariant:** \$0.00 External Cloud Inference Spend  

---

## 1. Technical & Factual Verification Pass (Reconciliation Against Ground Truth)

Before operationalizing intelligence or commercial projections into execution milestones, claims from recent threat and model briefings must be rigorously audited against hardware physical realities, licensing terms, and cryptographic boundaries:

### 1.1 Local Hardware Capacity vs. Frontier Model Reality
* **Host Physical Envelope:** `qfx-yoga` possesses **16 GB physical RAM** (~14.0 GiB addressable, ~4.4 GiB available under standard baseline load, 7.1 GiB swap).
* **Mistral Large 4 ("Le Chonk"):**
  * *Specification Check:* ~1T total parameter MoE (~49B–52B active parameters).
  * *Hardware Footprint:* At 4-bit quantization (Q4_K_M), Mistral Large 4 requires **over 500 GB of memory/storage** for weights alone, and even an isolated 50B active footprint requires ~32–40 GB of VRAM.
  * *Operational Truth:* **Mistral Large 4 CANNOT run locally on `qfx-yoga`'s 16 GB unified RAM.** Attempting to load it would trigger immediate kernel OOM thrashing.
  * *Deployment Boundary:* Local inference on `qfx-yoga` remains strictly constrained to models $\le 7\text{B}$ parameters (e.g., `qwen2.5-coder:7b` at 4.7 GB, `gemma3:4b` at 3.3 GB, `amara/athena` 1.5B at 986 MB). Any larger model evaluation must run on dedicated external hardware appliances or high-RAM cluster nodes.
* **NVIDIA Nemotron 3.5 Transcribe:**
  * *Specification Check:* ~30B total parameter MoE (~4B active parameters).
  * *Hardware Footprint:* Total weight footprint for a 30B MoE requires ~18–24 GB disk/memory even at 4-bit quantization. While ~4B active parameters require lower compute during decoding, all 30B weights must be resident in memory to route tokens.
  * *Operational Truth:* Native 30B MoE exceeds `qfx-yoga`'s 14 GiB memory ceiling. A distilled/pruned dense ~4B model or offloaded CPU execution with aggressive layer-swapping is required, or inference must be delegated to a dedicated secondary workstation node.
* **Concurrent Inference Realities:**
  * Running concurrent LLM tasks (e.g., Amara loop + Athena vector search) on 14 GiB RAM requires strict context window budgeting (e.g., 2,048–4,096 tokens per context) and single-worker sequential queuing in Ollama to prevent out-of-memory kernel faults.

### 1.2 Cryptographic Artifact Verification vs. Key Compromise Boundary
* **The Distinction:** Cryptographic verification (QF-A3 formal proofs, SHA-256 provenance hashes, CBOM admission receipts) verifies mathematical validity and structural integrity according to specified rules.
* **Threat Reality (Binance / TraderTraitor Incident Analysis):** The October 2026 \$6.3B Binance incident occurred via a compromised endpoint with legitimate administrative signing authority, draining assets via validly signed transactions.
* **QuantumFlex Control Boundary:** Cryptographic verification alone does not prevent actions executed by a compromised key. QuantumFlex addresses this via:
  1. *Dual-Control Separation:* Developer wallets cannot initiate state mutations without separate two-man physical attestation (`CredTwoManAttestation`).
  2. *Hardware-Enforced Keystores:* Keys reside exclusively within Microsoft Pluton TPM 2.0 (`qfx-yoga`) and Titan M2 StrongBox (`qfx-pixel`).
  3. *Deterministic Idempotency & Velocity Limits:* Maximum settlement throttles per hour and deterministic block hash UUIDs prevent automated bulk draining.

---

## 2. Pillar 1: Commercialization — B2B Sovereign AI Appliance

**Offering:** Sovereign, Airgapped On-Premises Search & Document Intelligence Appliance  
**Target Profile:** Regional law firms, CPAs, wealth managers, medical offices subject to confidentiality mandates (GLBA, HIPAA, Attorney-Client Privilege).  
**Pricing Architecture:** \$2,500 Setup / Appliance Provisioning + \$300/month Maintenance & Security Retainer.

### 2.1 Technical Specifications of the Appliance
* **Hardware Unit:** Dedicated Mini-PC (e.g., AMD Ryzen 7 / 32 GB or 64 GB DDR5 / 1 TB NVMe SSD) pre-configured with QuantumFlex Core.
* **Network Isolation:** Airgapped or local LAN-only loopback (`127.0.0.1:11434`, zero external internet egress required for inference).
* **Software Stack:**
  * Local Ingestion & Vector Engine: Athena / ChromaDB or pgvector on PostgreSQL.
  * Local Neural Models: `qwen2.5-coder:7b` / `gemma:7b` + `nomic-embed-text`.
  * User Interface: Sovereign Web UI bound exclusively to internal LAN with client TLS.

### 2.2 Acceptance Tests & Acceptance Criteria
* `AT-COMM-01`: Verify zero outbound packets leave the appliance during document ingestion, embedding generation, and prompt completion (monitored via `tcpdump -i eth0`).
* `AT-COMM-02`: Document ingestion throughput $\ge 50$ PDF pages/minute with OCR and vectorization.
* `AT-COMM-03`: Cold reboot to ready state $\le 45$ seconds with auto-unseal via local operator token.

---

## 3. Pillar 2: Research Automation — High-Speed Research Dossier Service

**Offering:** Institutional-Grade 50-Page Research Dossiers (Zoning, Municipal Code, Competitor OSINT, Regulatory Liabilities).  
**Target Profile:** Commercial real estate developers, private equity search funds, corporate M&A counsel.  
**Pricing Architecture:** \$1,500 to \$3,500 per dossier delivered within 24–48 hours.

### 3.1 Technical Workflow
```
Client Ingestion (PDFs/Public Filings)
               │
               ▼
   Local Athena Ingestion Pipeline
   ├── Chunking & OCR Extraction
   ├── Zero Ambient Data Sanitization
   └── Nomic Vector Database Ingestion
               │
               ▼
   Multi-Perspective Synthesizer Swarm
   ├── Cross-Document Anomaly Detection
   ├── Regulatory Compliance Check
   └── Quantitative Citation Verification
               │
               ▼
   Deterministic Output Generation
   ├── Markdown / LaTeX Dossier Compilation
   └── PDF Compilation with Cryptographic Receipt
```

### 3.2 Acceptance Tests & Acceptance Criteria
* `AT-RDOS-01`: Ingestion of 500-page municipal or regulatory corpus completed in $\le 10$ minutes on local compute.
* `AT-RDOS-02`: Zero factual hallucinations in citations: 100% of claims cite verified chunk IDs and page offsets.
* `AT-RDOS-03`: Cryptographic verification receipt generated and embedded in final dossier.

---

## 4. Pillar 3: Sovereign Intelligence — Local Transcription & Reasoning Tuning

**Objective:** Expand local multi-modal capabilities within `qfx-yoga`'s 14 GiB memory budget without cloud dependencies.

### 4.1 Memory Allocation & Model Tiering Matrix
To maintain rock-solid stability and zero swap thrashing on `qfx-yoga`:

| Service / Role | Engine / Model | Memory Footprint | Context Limit | Concurrency Policy |
|---|---|---|---|---|
| **OS & Desktop** | Ubuntu 26.04 / Services | 3.5 GiB | N/A | Resident |
| **Vector DB / Store** | Athena / SQLite / PG | 1.0 GiB | N/A | Resident |
| **Primary Reasoning** | `qwen2.5-coder:7b` (Q4) | 4.7 GiB | 4,096 | Active on demand |
| **Edge Transcription** | `whisper.cpp` (medium.en) | 1.5 GiB | Chunked | Sequential (locks LLM) |
| **Fast Agentic Loop** | `amara` (1.5B) | 1.0 GiB | 2,048 | Co-resident with agent |
| **Buffer / Headroom** | Unallocated | 2.3 GiB | N/A | Safety margin |

### 4.2 Acceptance Tests & Acceptance Criteria
* `AT-SOVI-01`: Peak RAM utilization under joint reasoning and vector retrieval never exceeds 12.0 GiB (avoiding Linux swap thrashing).
* `AT-SOVI-02`: Transcription of 10-minute audio file completes locally in $\le 90$ seconds with word error rate (WER) $\le 6\%$.

---

## 5. Pillar 4: Security Assurance — QF-A4 / QF-A5 / QF-A6 Progression

Building upon our verified formal core and differential C ABI equivalence (10,131/10,131 checks passed in commit `318ffd7`), execute the remaining assurance promotions:

```
[QF-A3: FORMAL SPEC] ──(Discharged)──► [QF-A4: EXTRACTED C] ──(Differential)──► [QF-A5: SIGNED CBOM] ──► [QF-A6: HW BINDING]
  F* 2026.09 Verification                 KaRaMeL C11 Translation                  Vault Transit Ceremony              Pluton TPM + Titan M2
```

### 5.1 Acceptance Criteria for Assurance Progression
1. **QF-A4 CI Integration:**
   * Wire `scripts/verify_formal_core.sh` and `scripts/extract_verified_core.sh` into standard build automation.
   * Promote QF-A4 to `PASS` in repository audit accounting once verified across release builds.
2. **QF-A5 Signing Ceremony Execution:**
   * Execute `scripts/qf_signing_ceremony.py` utilizing the offline release key.
   * Generate signed CBOM (`cbom_alpha_node_template.json`) and publish signed admission receipts.
3. **QF-A6 Hardware Root of Trust Attestation:**
   * Execute `scripts/create_quantumflex_runtime_binding.py` binding node runtime state to Microsoft Pluton TPM 2.0 PCR quotes on `qfx-yoga` and Titan M2 StrongBox on `qfx-pixel`.

---

## 6. Pillar 5: Capital Preservation & Reserve Invariant ($R \ge O$)

### 6.1 The Mathematical Governing Rule
$$\text{Reserves } (R) \ge \text{Obligations } (O) \times 6\text{ months}$$

* **Hard Rule:** Public sales outreach and capital commitments are strictly gated behind having at least 6 months of verified operating and living reserves in place.
* **Zero Infrastructure Expansion Cost:** No external GPUs, cloud instances, or paid SaaS may be purchased until paid client retainers fund the equipment upfront.
* **Cash Flow Funnel:**
  1. Complete 1 Research Dossier (\$1,500) $\rightarrow$ allocates 100% to capital reserve pool.
  2. Deploy 1 Appliance (\$2,500 setup + \$300/mo) $\rightarrow$ hardware funded by client deposit; setup profit funds appliance reserve.

---

## 7. Immediate 30-Day Execution Timeline

| Milestone | Deliverable / Task | Acceptance Gate | Target Date |
|---|---|---|---|
| **M1: Security Hard Stops** | Apply Pixel September 2026 bulletin (`CVE-2026-58704`); resolve CircleCI/TP-Link/Uber alerts. | Verification log in `docs/audits/` | Week 1 |
| **M2: Appliance Packaging** | Package Athena + Ollama + Web UI into turnkey setup script (`scripts/provision_appliance.sh`). | `AT-COMM-01`, `02`, `03` pass | Week 2 |
| **M3: Dossier Pipeline** | Build automated PDF ingestion and Markdown-to-PDF report generator with cryptographic receipts. | `AT-RDOS-01`, `02`, `03` pass | Week 3 |
| **M4: Commercial Outreach** | Finalize 1-page Appliance Sheet & Sample Dossier for direct presentation to vetted local professional firms. | Review against legal guidelines | Week 4 |
