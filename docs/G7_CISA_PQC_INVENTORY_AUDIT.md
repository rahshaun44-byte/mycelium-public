# G7 / CISA PQC Joint Guidance: Alpha Node Line-Audit & CBOM Mapping

**Reference Artifact**: G7 International Action Group (IAG) / CISA / ANSSI Joint Guidance: *Post-Quantum Cryptography: A Guidance Document for Public and Private Sector Organizations* (Published: 3 September 2026).  
**Operational Scope**: QuantumFlex Alpha Node (Control Plane & Edge Workstation).  
**Generated CBOM Template**: [`docs/cbom_alpha_node_template.json`](file:///home/quant/mycelium/docs/cbom_alpha_node_template.json)

---

## 1. Executive Summary & Epistemic Guardrails

1. **Principle 6 Compliance**: *"Do not watch 'quantum supremacy' headlines as a migrate-now trigger. Watch inventory completeness and algorithm agility."*
   - QuantumFlex does not track speculative quantum timeline headlines or compute vendor roadmaps to justify architecture.
   - Migration readiness is measured strictly by **inventory completeness** (all cryptographic assets indexed down to wire sizes and OIDs) and **algorithm agility** (automated, zero-downtime configuration rollover).
2. **Absence of Hard Deadlines**:
   - The G7/CISA 3 Sep 2026 paper establishes **five qualitative priorities**. It does not impose new statutory calendar deadlines on private infrastructure.
   - **Federal Separation**: Federal executive orders (e.g., EO 14412 with 2030/2031 milestones and OMB M-26-15) govern federal High-Value Assets (HVAs) and covered agency contractors. QuantumFlex does not falsely claim federal agency compliance status.

---

## 2. Line-Audit: The Five G7/CISA Priorities Mapped to QuantumFlex

| G7/CISA Priority | International Stance | QuantumFlex Alpha Node Implementation | Operational Status |
| :--- | :--- | :--- | :--- |
| **Priority 1: Establish Inventory & Visibility** | Discover and catalog all cryptographic assets, algorithms, key sizes, libraries, and handshake surfaces. | CycloneDX v1.5 CBOM schema in [`cbom_alpha_node_template.json`](file:///home/quant/mycelium/docs/cbom_alpha_node_template.json) generated dynamically by `immune_daemon.py`. | **VERIFIED** |
| **Priority 2: Develop Agility Strategy & Governance** | Implement provider architectures that allow algorithm substitution without rewriting underlying services. | Open Policy Agent (`membrane_health.rego`) authoritative fallback chain (`ML-KEM-768 -> FrodoKEM-976-AES -> X25519`) with atomic file swap. | **VERIFIED** |
| **Priority 3: Identify & Protect High-Value Assets (HVAs)** | Guard sensitive data with multi-decade shelf-life against Harvest Now, Decrypt Later (HNDL). | Master genesis / unlock entropy fractured into Shamir's Secret Sharing ($GF(256)$) shards; Shard #1 isolated on Pixel GrapheneOS Titan M2 enclave. | **VERIFIED** |
| **Priority 4: Track Standards & Dependency Posture** | Align with published standards (FIPS 203/204/205) and audit third-party library trust boundaries. | OpenSSL 3.5.8 default provider for standardized primitives; continuous monitoring of withdrawn algorithms (e.g. HAWK, SIKE). | **VERIFIED** |
| **Priority 5: Secure Interoperability & Hybrid Testing** | Deploy hybrid key exchange and dual signatures during transition to hedge against mathematical breaks. | CFRG `draft-irtf-cfrg-hybrid-kems` dual-PRF combiner (FrodoKEM-976 + X25519) with 16-byte `QFXK` MTU wire framing and constant-time decapsulation. | **VERIFIED** |

---

## 3. Alpha Node Wire & Cryptographic Surface Catalog

### A. Active & Fallback Cryptographic Components

```
Active Primary (FIPS Modern)        Fallback 1 (Conservative LWE)       Fallback 2 (Classical)
┌───────────────────────────┐      ┌───────────────────────────┐      ┌───────────────────────────┐
│ KEM: ML-KEM-768 (1184B)   │ ───► │ KEM: FrodoKEM-976 (15.6KB)│ ───► │ KEM: X25519 (32B)         │
│ SIG: ML-DSA-65 (1952B)    │      │ SIG: SLH-DSA-128s (7.8KB) │      │ SIG: Ed25519 (32B)        │
└───────────────────────────┘      └───────────────────────────┘      └───────────────────────────┘
```

* **Active Primary Wire Combination**:
  * CFRG Dual-PRF Hybrid Combiner: $K = \text{HKDF-Extract-and-Expand}(K_{\text{X25519}} \parallel K_{\text{Frodo}}, \text{Context})$.
  * Public Key: 15,664 bytes (spans 12 MTU frames).
  * Ciphertext: 15,776 bytes (spans 12 MTU frames).
  * Decapsulation Timing Oracle: **Zero** (unconditional dual execution, bitwise error masking, RFC 7748 low-order point rejection).

### B. Network Surface & Boundary Confinement

| Endpoint / Surface | Port | Protocol Framing | Access Boundary | Threat Mitigation |
| :--- | :--- | :--- | :--- | :--- |
| **mTLS IPC Wire** | `9443` | TLS 1.3 + `QFXK` Binary Chunk Framing | Tailscale Mesh (`100.64.1.29`) & Loopback | Client cert required; 1200ms reassembly deadline; 64-session memory cap. |
| **OPA Policy Sidecar** | `8181` | HTTP/REST (`/v1/data/membrane/health/verdict`) | **Strict Loopback (`127.0.0.1`) Only** | Zero external exposure; unreachable triggers fail-secure quarantine. |
| **API Gateway** | `8080` | HTTP/REST | Tailscale WireGuard Mesh Only | Rate-limited telemetry ingress. |

---

## 4. Residual Uncertainty & Unresolved Fields (`NULL` Register)

Per the QuantumFlex Equation of Truth ($Y = f(x - h) + k$), unverified or unmeasured fields are strictly recorded as `NULL`:

1. **FIPS 140-3 Module & CAVP Algorithm Validation Certificates**:
   * *Status*: `NULL`
   * *Rationale*: OpenSSL 3.5.8 default provider contains native implementations of FIPS 203/204/205 algorithms, but neither the host application nor the integration has completed formal third-party NVLAP laboratory testing or NIST CMVP validation. Formal certificate numbers are strictly `NULL` (Pre-validation internal evidence is not equivalent to CMVP certification).
2. **CEDRUS+C-128s-5684 Local Validation**:
   * *Status*: `local_validation: NULL` / `gatekeeper_state: NO_INPUT`
   * *Rationale*: External academic paper claim (IACR 2025/2236) with published hash counts (4,207,118 sign / 5,745 verify). Unresolved table collisions (`Table 23 [0x06]` is 192-bit fast). No compiled reference binary on disk. Hard Stop gate enforced by `scripts/cedrus_artifact_gate.py`.
3. **Bare-Metal Yoga 7 DVFS / Hertzbleed Profile**:
   * *Status*: `NULL` (dry-run on KVM VM exited with code 2 / `PARTIAL`).
   * *Rationale*: Sysfs cpufreq paths must be executed directly on bare-metal Ryzen hardware with `powersave` disabled and turbo pinned before benchmark timing is valid.
4. **Cryptanalytically Relevant Quantum Computer (CRQC) Arrival**:
   * *Status*: `DATA NOT FOUND`
   * *Rationale*: Theoretical worst-case estimates (e.g. Gao et al. $2^{0.5596n}$) require $2^{n/2}$ memory floor. Speculative headlines are discarded.
