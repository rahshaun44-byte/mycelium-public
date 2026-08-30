# 🌌 QUANTUM FLEX: 7-LAYER DePIN INFRASTRUCTURE AUDIT & MAPPING
**Document:** QF-MAP-7L-001  
**Architecture:** 7-Layer DePIN Telemetry & Micro-Data Network  
**Root Architect:** Rahshaun Chambers  
**Stack:** Rust · C++20 · Solana · Kafka · Axum · PostgreSQL  

---

## 1. Executive Summary
This audit maps all active and legacy codebase components across the repository tree into the unified **7-Layer Quantum Flex DePIN Architecture**.

```
[Layer 7: Governance]       ──> Wyoming DAO LLC / On-Chain Voting
       │
[Layer 6: Marketplace]      ──> quantum-flex-console (Web) & quantum-flex-terminal (PWA)
       │
[Layer 5: Incentive Engine]  ──> Solana Anchor ($QFX SPL Token)
       │
[Layer 4: Processing]        ──> recursive_rsi_engine (C++) / Kafka → Flink → PostgreSQL
       │
[Layer 3: Verification]     ──> Ed25519 Signature Checker & Auto-Warden / PKI
       │
[Layer 2: API Gateway]      ──> quantum-flex-infrastructure (ZMQ / Axum / MCP :8080/:9000)
       │
[Layer 1: Node SDK (Edge)]  ──> quantum-flex-sdk (Rust) & sentinel_push.exe (C++20)
```

---

## 2. Component Mapping Breakdown

### Layer 1: Node SDK (Edge Layer)
*   **`quantum-flex-sdk/` (Rust 1.94.0):**
    *   *Role:* Edge daemon running on field hardware (laptops, SBCs, mobile edge).
    *   *Functions:* `wifiscanner 0.5` RF probing, BSSID anonymization, `_optout` exclusion filter, Ed25519 keypair identity generation, payload signing.
*   **`sentinel_push.exe` (C++20 MSVC):**
    *   *Role:* OS-level security sentinel.
    *   *Functions:* Real-time Windows Event Log ingestion via `wevtapi.dll` (`EvtSubscribe`), direct immutable `libpq` persistence.

### Layer 2: API Gateway (Ingestion Layer)
*   **`quantum-flex-infrastructure/` (Python / Axum):**
    *   *Role:* High-throughput ingestion gateway.
    *   *Functions:* Axum router on `127.0.0.1:8080` accepting signed packets from edge nodes; ZMQ broadcaster for local subsystem pub/sub.
*   **`api_node/` & `mcp_layer/`:**
    *   *Role:* Ingest traffic controller.
    *   *Functions:* `asyncio.Semaphore` concurrency limiting (`INGEST_CONCURRENCY_LIMIT`) to prevent RAM/CPU resource exhaustion.

### Layer 3: Verification & DPI (Deep Packet Inspection)
*   **`qflex_auto_warden.py` & `pki/`:**
    *   *Role:* Cryptographic trust verification.
    *   *Functions:* Validates Solana-compatible Ed25519 packet signatures, inspects sequence counter monotonicity, checks for spoofing/replay anomalies, and computes trust scores.
*   **`pqc-immune-daemon/`:**
    *   *Role:* Post-quantum cryptographic security layer for long-term data integrity.

### Layer 4: Processing & Enrichment Pipeline
*   **`recursive_rsi_engine/` (C++):**
    *   *Role:* Mathematical enrichment engine.
    *   *Functions:* Computes Recursive Relative Strength Index ($RSI^2$), signal variance, spatial RF density calculations, and anomaly detection.
*   **Persistence & Queue (Phase 1 Target):**
    *   *Role:* Real-time streaming and storage.
    *   *Functions:* Kafka message bus $\rightarrow$ Apache Flink stream aggregation $\rightarrow$ PostgreSQL (`quantum_telemetry_channel`).

### Layer 5: Incentive & Token Engine
*   **Solana Anchor Program (`$QFX`):**
    *   *Role:* Utility-first decentralized reward engine.
    *   *Functions:* Translates verified node trust scores and packet counts into on-chain SPL token emissions. Zero presale / ICO; 100% work-based reward distribution.

### Layer 6: Marketplace & Consumer API
*   **`quantum-flex-console/` (Web Frontend):**
    *   *Role:* B2B buyer portal.
    *   *Functions:* Visualizes aggregated, anonymized spatial RF intelligence feeds, licensing pricing engine, and API key management.
*   **`quantum-flex-terminal/` (Docker / PWA):**
    *   *Role:* Node operator dashboard.
    *   *Functions:* Lightweight web app showing live node status, verified packet count, trust score, and earnings.
*   **`amara/dashboard.py`:**
    *   *Role:* Operator telemetry viewer.
    *   *Functions:* Real-time visualization of the Euclidean Drive metric and system homeostasis.

### Layer 7: Governance & Legal Wrapper
*   **Wyoming DAO LLC Framework:**
    *   *Role:* Legal liability shield and on-chain protocol governance.
    *   *Functions:* Binds protocol parameter adjustments, treasury allocations, and data buyer licensing agreements to DAO smart contracts.

---

## 3. Immediate Action Items
1. **Packaging:** Bundle `quantum-flex-sdk/` with `cargo build --release` and write a one-line deployment script for alpha nodes.
2. **Lock ADR-003:** Formally certify PostgreSQL for the Phase 1 persistent node registry.
3. **Queue Setup:** Scaffold local Kafka pipeline configuration for Phase 1 stream processing.
