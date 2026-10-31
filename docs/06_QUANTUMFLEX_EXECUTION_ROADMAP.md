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

## 2. Pillar 1: Competitive Security Audits & Bug Bounties (Pay-Per-Proof)

**Operating Mode:** Pseudonymous, Zero-Client Vulnerability Discovery & Formal Proof Submission  
**Target Platforms:** Immunefi, Code4rena, Sherlock, Cantina, HackerOne, Linux/OpenSSF Bug Bounties.  
**Payout Architecture:** \$5,000 to \$100,000+ per verified High/Critical proof (1099 platform payout; zero sales calls, zero retainers, zero client SLAs).

### 2.1 Technical Specifications of the Sovereign Audit Engine
* **Host Unit:** `qfx-yoga` (Airgapped / Loopback `127.0.0.1:11434`, zero external cloud API spend).
* **Verification Toolchain:**
  * **Formal & ABI Verification:** F\* 2026.09 + KaRaMeL C11 differential equivalence (`QF-A3` / `QF-A4`).
  * **EVM & Settlement Verification:** Foundry (`forge test -vvv`, `evm_version = "paris"`, 6-decimal USDC invariant, single-signer escrow drain & idempotency checks).
  * **Runtime Kernel & Descriptor Verification:** `fexecve` `EXECUTED_FD == VERIFIED_FD` TOCTOU race elimination (`QF-A6`).
  * **Automated Proof Compilation:** `scripts/generate_research_dossier.py` emits deterministic Markdown + PDF-1.4 vulnerability reports with `100%` SHA-256 citation provenance (`AT-RDOS-02`).

### 2.2 Acceptance Tests & Acceptance Criteria
* `AT-COMM-01`: Verify zero outbound packets leave `qfx-yoga` to third-party AI APIs during target codebase ingestion, embedding generation, and proof synthesis.
* `AT-COMM-02`: Codebase/specification ingestion throughput $\ge 50$ pages/minute (`396.7 pages/min` verified on SQLite + Ollama `nomic-embed-text`).
* `AT-COMM-03`: Every submitted vulnerability claim includes a reproducible PoC test and verified SHA-256 source citation.

---

## 3. Pillar 2: Non-Dilutive Open-Source Public-Good Grants & Personal Family-Office Oracle

**Operating Mode:** Individual Researcher Fellowships + Self-Only Household Capital Research  
**Grant Targets:** NLnet Foundation (NGI Zero Core / Entrust), OpenSSF, Sovereign Tech fellowships, Ethereum Foundation ESP (`€5,000 – €50,000+` non-dilutive individual grants for `pqc-immune-daemon`).  
**Personal Oracle Scope:** Private analysis of public SEC 10-K/10-Q filings, municipal tax/zoning codes, distressed assets, and scientific literature strictly for the Operator's own household capital preservation ($R_{\text{verified liquid}} \ge 6O$).

### 3.1 Technical Workflow
```
Target Corpus (Open-Source Repo / Grant Spec / Public SEC & Municipal Filings)
               │
               ▼
   Local Athena Ingestion Pipeline
   ├── Chunking & Page-Offset Extraction
   ├── PrivacyFilter Zero-Ambient-Data Sanitization
   └── Role-Isolated Vector & Provenance Store (blocks 'sovereign_internal' leakage)
               │
               ▼
   Deterministic Verification & Synthesis
   ├── Vulnerability / Compliance / Risk Extraction
   ├── 100% Citation & SHA-256 Verification (AT-RDOS-02)
   └── Corpus SHA-256 Merkle Root Computation
               │
               ▼
   Sovereign Output Generation
   ├── Markdown + Native Printable PDF-1.4 Dossier
   └── Machine-Readable Cryptographic Admission Receipt (AT-RDOS-03)
```

### 3.2 Acceptance Tests & Acceptance Criteria
* `AT-RDOS-01`: Ingestion of 500-page regulatory or technical audit corpus completed in $\le 600$ seconds on local compute (`0.0216s` synthetic pipeline / `109.63s` full SQLite + Ollama embedding).
* `AT-RDOS-02`: Zero factual hallucinations in citations: 100% of claims cite verified chunk IDs and page offsets.
* `AT-RDOS-03`: Cryptographic verification receipt generated and independently reproducible via `scripts/verify_dossier_independent.py`.

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
   * Execute `scripts/qf_signing_ceremony.py` utilizing the offline release key once personal security Hard Stops clear.
3. **QF-A6 Hardware Root of Trust Attestation:**
   * Execute `scripts/create_quantumflex_runtime_binding.py` binding node runtime state to Microsoft Pluton TPM 2.0 PCR quotes on `qfx-yoga` and Titan M2 StrongBox on `qfx-pixel`.

---

## 6. Pillar 5: Capital Preservation & Reserve Invariant ($R_{\text{verified liquid}} \ge 6O$)

### 6.1 The Mathematical Governing Rule
$$R_{\text{verified liquid}} \ge 6 \times \left(O_{\text{household}} + O_{\text{operating}}\right)$$

* **Hard Rule:** Discretionary capital outlays are strictly gated behind having at least 6 months of independently reconciled liquid reserves in place ($\le 30\text{ days}$ reconciliation freshness).
* **Zero Corporate Overhead (`PA-LLC` Retired as Operational Blocker):** Operating as a sovereign individual researcher/auditor requires `$0.00` in annual corporate franchise fees, commercial insurance, or client acquisition overhead.
* **Cash Flow Funnel:**
  1. Complete Bug Bounty Proofs & Public-Good Grant Milestones $\rightarrow$ route 100% of net proceeds to Bucket 1 (Iron Reserve) until $R_{\text{verified liquid}} \ge 6O$.
  2. Compound surplus peacefully through the Personal Family-Office Intelligence Oracle with zero client obligations.

---

## 7. Immediate Sovereign Execution Timeline (`QF-SOVEREIGN`)

| Milestone | Deliverable / Task | Acceptance Gate | Status |
|---|---|---|---|
| **M1: Personal Security Hard Stops** | Apply Pixel September 2026 bulletin (`CVE-2026-58704`); resolve CircleCI/TP-Link/Uber account alerts; reconcile Track 0 $R \ge 6O$ worksheet. | Operator sign-off (`PA-LLC` retired as non-corporate) | Pending Operator |
| **M2: Sovereign Node & Recovery** | Automated node audit, SQLite backup & restoration drill (`scripts/provision_appliance.sh`). | `40/40` vector parity & integrity check | **COMPLETE** |
| **M3/M4: Dossier & Independent Verifier** | Automated Markdown/PDF-1.4 dossier pipeline (`scripts/generate_research_dossier.py`) + independent verifier (`scripts/verify_dossier_independent.py`). | `61/61` pytest suite & 500p gate | **COMPLETE** |
| **M5: Sovereign Bounty & Grant Missions** | Deploy Bug Bounty Proof Template, NLnet Grant Proposal for `pqc-immune-daemon`, and Personal Family-Office Protocol in `sovereign_missions/`. | Zero-client, zero-PII verification | **ACTIVE** |
