# NATIVE PQC-AGILITY SUPERVISOR: CNSA 2.0 & CMMC 2.0 ARCHITECTURE
**Autonomous Algorithmic Migration & Continuous Cryptographic Policy Enforcement**

*Author:* Rahshaun Chambers (FinallyFungus LLC / QuantumFlex Systems)  
*Date:* August 2026  
*Classification:* Technical Whitepaper & Architectural Reference

---

## 1. Executive Summary & Regulatory Catalyst

The defense and federal supply chain faces a compressed convergence of cryptographic mandates. The **January 1, 2027 CNSA 2.0 procurement gate** strictly requires ML-KEM-1024 and ML-DSA-87 for all new National Security Systems (NSS) acquisitions, with no waiver queue. In parallel, **CMMC 2.0 Phase 2 assessments begin November 10, 2026**, demanding verifiable, FIPS-validated cryptography. While **OMB Memorandum M-26-15** primarily targets federal agencies (setting an October 22, 2026 deadline for agency migration plans), it drives immediate downstream pressure into procurement specifications and RFP security questionnaires.

Traditional static cryptographic migrations require destructive code refactoring, manual certificate reissuance, and scheduled process downtime. This whitepaper introduces the **Native PQC-Agility Supervisor**, a cross-platform Python-based, zero-restart cryptographic control plane. By combining CycloneDX-shaped active algorithm self-inventories and an Open Policy Agent (OPA) policy engine, the system autonomously executes **atomic algorithmic fallback** (e.g., `ML-KEM-768` $\rightarrow$ `FrodoKEM-976-AES` $\rightarrow$ `X25519`) without interrupting live worker processes.

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                   PQC-AGILITY SUPERVISOR: SYSTEM TOPOGRAPHY                     │
└───────────────────────────────────────┬────────────────────────────────────────┘
                                        │
             ┌──────────────────────────┴──────────────────────────┐
             ▼                                                     ▼
┌─────────────────────────┐                               ┌─────────────────────────┐
│     ANOMALY KERNEL      │                               │    OPA POLICY SIDECAR   │
│  (EWMA-LIF Telemetry)   │                               │ (membrane_health.rego)  │
│ iowait / CPU / Memory   │                               │ NIST FIPS 203/204 Gating│
└────────────┬────────────┘                               └────────────┬────────────┘
             │                                                         │
             └──────────────────────────┬──────────────────────────────┘
                                        ▼
                         ┌─────────────────────────────┐
                         │   IMMUNE DAEMON SUPERVISOR  │
                         │    Atomic Config Swap       │
                         │   (crypto_provider.conf)    │
                         └──────────────┬──────────────┘
                                        ▼
                         ┌─────────────────────────────┐
                         │   WORKER DAEMON PROCESS     │
                         │   (Inotify / ConfigWatcher) │
                         │ Zero-Downtime Re-handshake  │
                         └─────────────────────────────┘
```

---

## 2. Structural Architecture & Core Mechanisms

### 2.1 CycloneDX-Shaped Active Algorithm Inventory
The supervisor evaluates its own active configuration to assemble a **CycloneDX-shaped Cryptographic Bill of Materials (CBOM)** self-inventory:
- Emits active Key Encapsulation Mechanisms (KEMs) and Digital Signature Algorithms (DSAs) to the policy sidecar.
- Designed to act as the enforcement layer integrating with full estate scanners (e.g., CBOMkit-theia) for comprehensive inventory ingestion.

### 2.2 Open Policy Agent (OPA) Sidecar Evaluation
The CBOM payload is evaluated over high-speed local loopback against declarative Rego rules (`membrane_health.rego`):
- **Threat Intel Ingestion:** Monitors real-time vulnerability feeds (`data.threat_flags`).
- **Toxicity Classification:** Flags deprecated algorithms (RSA-2048, ECDSA P-256) and compromised lattice parameters as `TOXIC`.
- **Deterministic Multi-Tier Fallback:** Rather than a naive global default, the policy evaluates equivalent security tiers:
  - `ML-KEM-512` (NIST Level 1) $\rightarrow$ `FrodoKEM-640-AES`
  - `ML-KEM-768` (NIST Level 3) $\rightarrow$ `FrodoKEM-976-AES`
  - `ML-KEM-1024` (NIST Level 5) $\rightarrow$ `FrodoKEM-1344-AES`
  - `FrodoKEM` Exhaustion $\rightarrow$ `X25519` (Hybrid Fail-Safe)

### 2.3 Atomic Vein Collapse (Zero-Downtime Migration)
Upon receiving a `TOXIC` verdict from OPA, the supervisor executes an **Atomic Vein Collapse**:
1. Generates an updated `crypto_provider.conf` within a secure staging buffer.
2. Performs an atomic file system swap (`os.replace` / POSIX `rename`) to prevent partial reads.
3. Worker processes, monitoring via native inode/mtime watchers (`ConfigWatcher`), detect the swap and autonomously renegotiate subsequent TLS/PQC handshakes using the fallback algorithm—**zero restarts, zero session drops**.

---

## 3. Empirical Verification & Live-Fire Benchmark

The architecture was validated via a live-fire integration suite simulating an upstream zero-day compromise against `ML-KEM-512`:

```
[LIVE-FIRE VERIFICATION RUN: 2026-08-18]
1. OPA Sidecar Initialized on port 8181 (membrane_health.rego).
2. Threat Flag Injected: data.threat_flags.ML_KEM_COMPROMISED = true
3. Active Configuration: active_kem=ML-KEM-512, active_sig=ML-DSA-65
4. Supervisor Evaluation: OPA HTTP 200 -> Verdict: TOXIC
5. Decision Output: recommended_fallback: FrodoKEM-640-AES
6. Atomic Action: Config rewritten in 0.4ms -> active_kem=FrodoKEM-640-AES
7. State: COMPLIANT | Invariant Maintained.
```

---

## 4. Scope and Limitations

- **No Cryptography Performed:** The supervisor is a control-plane component that performs no cryptography at all. It contains no cryptographic module, validated or otherwise, and performs no key establishment, encryption, or signing. It is designed to sit *around* a customer's FIPS-validated modules.
- **KEM-Scoped Rollover:** Automated fallback is currently scoped to key-establishment algorithms. Signature schemes are evaluated and reported, but not automatically rotated.

---

## 5. Enterprise Advisory & Integration Scope

For defense contractors subject to **CNSA 2.0** and **CMMC 2.0 (Level 2/3)**, FinallyFungus LLC delivers rapid architectural prototyping and compliance enablement:
- **Phase 1: Cryptographic Inventory & CBOM Automated Pipeline Setup**
- **Phase 2: OPA Policy Customization & Threat Feed Integration**
- **Phase 3: Daemon Hardening & Zero-Downtime Fallback Verification**
- **Phase 4: Technical Evidence Artifacts for 3PAO/C3PAO Assessment**

*Contact:* advisory@finallyfungus.com | Enterprise Architectural Services
