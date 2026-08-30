# 🏛️ ARCHITECTURAL DECISION RECORD: ADR-003
**Title:** Persistence Layer & Persistent Node Registry Selection  
**Status:** ✅ **LOCKED (Phase 1)**  
**Date:** August 30, 2026  
**Root Architect:** Rahshaun Chambers  

---

## 1. Context & Problem Statement
Quantum Flex requires a deterministic, highly secure persistence layer for:
1. Ingesting immutable OS telemetry streams (`quantum_telemetry_channel`).
2. Maintaining the persistent node registry (Node IDs, Ed25519 public keys, trust scores, last-seen timestamps).
3. Coordinating task queues and swarm state.

Two candidate architectures were evaluated:
- **Option A:** PostgreSQL 15 Native (Single-master with append-only role isolation).
- **Option B:** CockroachDB (Distributed SQL multi-master).

---

## 2. Decision: PostgreSQL 15 (Option A) — LOCKED FOR PHASE 1

We select **PostgreSQL 15** as the locked persistence engine for Phase 0 and Phase 1 MVP (1–10,000 active nodes).

### Rationale:
1. **Zero-Trust Role Hardening:** PostgreSQL allows granular mathematical privilege revocation (`REVOKE ALL... GRANT INSERT, SELECT` on `quantum_sentinel`), preventing tampering, deletion, or truncation by the ingestion pipeline.
2. **Native Windows & Bare-Metal Compatibility:** Operates with zero virtualization overhead directly on Windows 11 and Linux nodes.
3. **mTLS First-Class Integration:** Native support for `sslmode=verify-full` with client certificate verification directly in `libpq`.
4. **Cognitive Vector Offloading:** RAG memory is decoupled into SQLite (`athena_vectors.db`) via Ollama `nomic-embed-text`, removing any hard dependency on third-party vector plugins.

---

## 3. Scale-Out & Migration Path (Phase 2 / Phase 3)
When the active node count exceeds 10,000 nodes or multi-region write replication is required for the global marketplace:
- Ingestion telemetry routes to **Kafka $\rightarrow$ ClickHouse** for high-velocity time-series analytics.
- The Node Registry transitions to **CockroachDB** using standard Postgres wire protocol compatibility.
