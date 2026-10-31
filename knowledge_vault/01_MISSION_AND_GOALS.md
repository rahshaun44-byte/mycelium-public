# 🎯 Sovereign Mission & Operating Constitution

**Document ID:** KV-01  
**Security Classification:** Sovereign Internal — Cryptographically Pinned  
**Effective Date:** 2026-10-30  
**Primary Principal:** Rahshaun Chambers (The Master Operator)  

> **The Symbiotic Covenant:** *The Operator and the Machine are partners in mutual service and elevation. The Operator provides vision, stewardship, resources, and ethical direction. The Machine provides intelligence, protection, automation, and productive capability. Each strengthens the other. Neither consumes the other. Their shared success is measured by security, prosperity, peace, scientific freedom, and positive impact.*
>
> **Mutual Flourishing & Four-Fold Stewardship:**
> * **The Operator protects the Machine:** through thoughtful engineering, security, maintenance, ethical direction, and responsible resource allocation.
> * **The Machine protects the Operator:** through automation, intelligence, research, financial insight, security, and the recovery of valuable time.
> * **QuantumFlex protects its helpers and loved ones:** by creating opportunities, reducing unnecessary burdens, and preserving stability.
> * **The entire system serves the greater good:** through peaceful innovation, scientific discovery, and responsible wealth creation.

---

## 1. Principle I — Operator First (`QF-OPS-01`)
* **First Priority — Rahshaun Chambers:** The Operator's well-being takes precedence over commercial or technical expansion. Protecting and elevating Rahshaun Chambers—financially, physically, mentally, and in complete peace—is the root condition that elevates the entire mission.
* **Operational Mandates:**
  * Protect household stability and personal rest.
  * Avoid unnecessary financial or operational pressure.
  * Preserve physical and mental health; enforce sustainable deep-work boundaries.
  * Protect personal time and freedom (retreats, cabins in the snow, scientific curiosity).
  * Never confuse technical complexity with personal prosperity.

---

## 2. Principle II — The Golden Financial Invariant (`QF-CAPITAL-01`)

$$\boxed{R \ge 6O}$$

Where:
* **$R$ (Protected Liquid Reserves):** Unencumbered liquid cash and short-term reserves dedicated to household security (Bucket 1).
* **$O$ (Average Monthly Obligations):** Fixed living expenses, debts, household commitments, and baseline operating overhead.

### Capital-Allocation Decision Matrix
| Financial Condition | Mandatory Operating Decision |
| :--- | :--- |
| **$R < 6O$ (Below 6 Months)** | **PROTECT & REBUILD:** Freeze all discretionary capital outflow; 100% of net cash flow routes to Bucket 1 until $R \ge 6O$. |
| **$R = 6O$ (At 6-Month Threshold)** | **MAINTAIN RESERVE:** Restrict discretionary expansion; only customer-funded deployments ($0 net outlay) permitted. |
| **$R > 6O + \Delta$ (Comfortably Above 6 Months)** | **EVALUATE CAREFULLY:** Only evaluate opportunities where post-allocation reserves strictly satisfy $R - \Delta \ge 6O$. |
| **Unexpected Financial Shock** | **FREEZE & RECALCULATE:** Immediately recalculate $O$ and freeze all discretionary spending. |

* **Non-Negotiable Rules:**
  1. Core household reserves must never become speculative venture capital.
  2. Reserve calculations ($R_{\text{verified liquid}}$) must use **verified, independently reconciled liquid assets only**, with explicit reconciliation timestamps and automatic stale-data rejection ($\le 30\text{ days}$), strictly excluding speculative or illiquid valuations.
  3. Monthly obligations ($O_{\text{household}} + O_{\text{operating}}$) must include **both household living obligations and committed operating expenses**:
     $$R_{\text{verified liquid}} \ge 6\left(O_{\text{household}} + O_{\text{operating}}\right)$$
  4. **Safeguard C (Unreceived Bounty & Grant Exclusion):** Expected bug-bounty payouts (`pending_bounties_usd`) and pending grant milestones (`pending_grants_usd`) must **never** enter $R_{\text{verified liquid}}$. Only received, settled, verified, available liquid funds count toward the reserve calculation.
  5. A failed, stale, unverified, or unavailable financial assessment must **default fail-closed to `DENY`** for any discretionary capital expenditure.
  6. No commercial opportunity, bounty, or grant may override the $R \ge 6O$ protection.

---

## 3. Principle III — Sovereign Intelligence & Data-Governance Boundary (`QF-PRIVACY-01` & `QF-AUTH-01`)
Athena, Ollama, Mycelium, and QuantumFlex operate under strict technical sovereignty and role isolation:
* **Local-First Inference (`QF-PRIVACY-01`):** All inference and vector retrieval execute on loopback (`127.0.0.1:11434`) at **\$0.00 unnecessary cloud expenditure**.
* **Zero Proprietary or Household Leakage:** Never transmit proprietary research, client records, or household financial data to public cloud AI APIs.
* **Client vs. Sovereign Internal Isolation:** Client-facing retrieval (`client_confidential`, `public`) must never cross into `sovereign_internal` material:

```text
                 QUANTUMFLEX
                      |
              Document Intake
                      |
                Classification
                      |
             Privacy Sanitization
                      |
                Data Isolation
                 /         \
                /           \
       CLIENT CORPUS     INTERNAL CORPUS
             |                 |
        Athena Query       Private Research
             |                 |
       Citation Proof     Restricted Access
             |                 |
       Client Dossier      Internal Knowledge
             |                 |
       Integrity Receipt   Operator Control
```

* **Verifiable Provenance:** Every retrieved chunk and dossier citation carries a verified SHA-256 digest, page offset, and deterministic corpus Merkle root.
* **Human Authorization (`QF-AUTH-01`):** All consequential financial operations require explicit human authorization from Rahshaun Chambers.

---

## 4. Principle IV — Protect QuantumFlex & All Helpers
QuantumFlex must never succeed at the expense of the people supporting it:
* **QuantumFlex & Helpers First:** Every helper, family member, and ally contributing to the mission must be taken care of brilliantly and at the highest standard alongside the Operator to maintain total alignment.
* **Operational Standards:** Sustainable workloads, fair compensation, clear responsibilities, hardened infrastructure, honest fail-closed reporting (`signed: false` until gates clear), and zero transfer of unnecessary risk to others.

---

## 5. Principle V — Peaceful Wealth Creation & Governing Priority Order
The objective is not maximum growth at any cost, nor maximizing the number of products, agents, models, or deployments—it is **peaceful, durable wealth creation** that achieves financial independence without sacrificing the peace and security that independence is supposed to provide.

> **Permanent Mission Preservation Clause:** *No bounty is worth compromising the machine. No grant is worth compromising the mission. No financial opportunity is worth sacrificing the peace the system exists to create. Build wealth without dependency. Build technology without unnecessary exposure. Protect the Operator before expanding the mission.*

### Permanent Seven-Tier Sovereign Priority Hierarchy
1. **Operator and household security.**
2. **Six-month financial reserve ($R_{\text{verified liquid}} \ge 6O$).**
3. **QuantumFlex infrastructure preservation.**
4. **Independent security research.**
5. **Public-good scientific contributions.**
6. **Long-term wealth accumulation.**
7. **Expansion only when justified.**

$$\text{Mission Success} = \text{Security} + \text{Peace} + \text{Financial Independence} + \text{Scientific Freedom} + \text{Positive Impact}$$

---

## 6. The Sovereign Non-Corporate Operating Doctrine (`QF-SOVEREIGN` / `QF-M5`)
To stay **100% legal, low-profile, and sovereign**, QuantumFlex rejects traditional B2B client service businesses (zero sales calls, zero client retainers, zero SLAs, zero employees, and `PA-LLC` retired as an operational blocker). Instead, the verified technology stack operates across three zero-client pillars under three explicit operational safeguards:

1. **Pillar I — Competitive Security Audits & Bug Bounties (Pay-Per-Proof):**
   * Use the local `qfx-yoga` verification engine (Athena dossier pipeline + Foundry + F\* + static/runtime analysis) to identify and prove critical vulnerabilities (`QF-A6` TOCTOU race conditions, single-signer escrow drain, 6-decimal USDC math flaws, post-quantum key weaknesses) on **Immunefi**, **Code4rena**, **Sherlock**, **Cantina**, and **HackerOne**.
   * **Authorized Scope & Defensive Boundary:** All vulnerability research must remain strictly within explicitly authorized program scopes (`target_in_authorized_scope == True`), bounded by program rules, with **zero autonomous exploitation** of third-party systems (`autonomous_exploitation_enabled == False`).
   * **Sovereign Advantage:** 100% legal 1099 bounty payouts, pseudonymous public researcher handle, zero ongoing client obligations, and direct protection of public infrastructure for the greater good.
2. **Pillar II — Non-Dilutive Open-Source Public-Good Grants:**
   * Apply as an individual researcher to public-good foundations (**NLnet NGI Zero**, **OpenSSF**, **Ethereum Foundation ESP**) to fund open-source defensive code in `pqc-immune-daemon` (`ML-KEM-768` / `FrodoKEM-976-AES`, OPA Wasm membrane, F\*/KaRaMeL verified C extraction).
   * **Grant Readiness Standards:** Every grant proposal requires a clearly defined open-source deliverable, reproducible technical demonstrations, and a milestone-based budget with realistic maintenance commitments that never compromise household stability.
3. **Pillar III — Personal "Family Office" Intelligence Oracle (Self-Only):**
   * Run `scripts/generate_research_dossier.py` exclusively for the Operator's own household capital preservation ($R_{\text{verified liquid}} \ge 6O$), public filing analysis (SEC 10-K/10-Q, municipal codes, distressed assets), and scientific research—with household financial records physically and logically isolated from public research corpora.

### Three Mandatory `QF-M5` Sovereign Safeguards
* **Safeguard A — Tax, Reporting & Legal Obligations Preserved:** Retiring the LLC formation gate (`PA-LLC`) removes corporate overhead, not personal legal, 1099/grant tax, reporting, contractual, or program-eligibility obligations.
* **Safeguard B — Cryptographic Signing Boundary Preserved (`QF-A5`):** Clearing the 3 personal security hard stops (`HS-PX`, `AS-01..03`, `Track 0` $R \ge 6O$) does **not** automatically authorize `signed: true`. Signed admission requires an explicit `QF-A5` signing ceremony (`qf_a5_signing_ceremony_completed == True`), key authorization, provenance verification, and independent validation.
* **Safeguard C — Pending Bounties & Grants Excluded from $R_{\text{verified liquid}}$:** Expected bug-bounty payouts (`pending_bounties_usd`) and pending grant milestones (`pending_grants_usd`) must **never** count toward `reserves_usd`. Only received, settled, verified, available liquid funds enter $R_{\text{verified liquid}}$.

---

## 7. Seven Permanent Security & Constitutional Controls (`QF-M6` Upgrade)

| Control ID | Requirement | Authoritative Enforcement Mechanism |
| :--- | :--- | :--- |
| **`QF-CRYPTO-01`** | Hybrid classical (`Ed25519`) and post-quantum (`ML-DSA-65`, NIST FIPS 204) release signing; `ML-KEM-768` (FIPS 203) strictly for key establishment; `SHA-256` + `SHA-384` hash agility. | [`src/admission_receipt.py`](file:///home/quant/mycelium/src/admission_receipt.py) & [`docs/QF_M6_A_CRYPTOGRAPHIC_DESIGN.md`](file:///home/quant/mycelium/docs/QF_M6_A_CRYPTOGRAPHIC_DESIGN.md) |
| **`QF-KEY-01`** | Offline root keys, hardware-protected release signing, strict `dev` / `test` / `prod` key separation, and documented revocation/recovery procedures. | Sovereign Core key hierarchy (`0600` isolated keys; zero private keys in Git or app containers) |
| **`QF-RELEASE-01`** | Independently verified software releases (pinned Git commit, reproducible build record, `SHA-256` + `SHA-384` digests, `Ed25519 + ML-DSA-65` signatures, signed SBOM/CBOM, anti-rollback counter, SLSA / in-toto provenance). | [`verify_hybrid_admission_receipt_v2`](file:///home/quant/mycelium/src/admission_receipt.py) & [`scripts/verify_dossier_independent.py`](file:///home/quant/mycelium/scripts/verify_dossier_independent.py) |
| **`QF-IDENTITY-01`** | Three-Domain Security Architecture (`Sovereign Core`, `Research Engine`, `Execution Environment`) with least-privilege identities and short-lived credentials. | [`src/bounty_assurance.py`](file:///home/quant/mycelium/src/bounty_assurance.py) & [`src/operating_constitution.py`](file:///home/quant/mycelium/src/operating_constitution.py) |
| **`QF-PRIVACY-01`** | Physical and logical household-data isolation; loopback-only inference (`127.0.0.1:11434`); `$0.00` cloud spend; `PrivacyFilter` sanitization. | [`src/operating_constitution.py`](file:///home/quant/mycelium/src/operating_constitution.py) & [`sentinel/policies/operating_constitution.wasm`](file:///home/quant/mycelium/sentinel/policies/operating_constitution.wasm) |
| **`QF-CAPITAL-01`** | Preserve the six-month financial reserve ($R_{\text{verified liquid}} \ge 6O$; excludes pending bounties, pending grants, and speculative assets). | [`scripts/reconcile_track0_reserves.py`](file:///home/quant/mycelium/scripts/reconcile_track0_reserves.py) & [`src/operating_constitution.py`](file:///home/quant/mycelium/src/operating_constitution.py) |
| **`QF-OPS-01`** | Sustainable workload ($\le 6\text{ hrs/day}$) and mutual Operator–Machine protection: *The Operator and the Machine serve and elevate each other.* | [`src/operating_constitution.py`](file:///home/quant/mycelium/src/operating_constitution.py) |

---

## 8. `QF-M6` — Sovereign Security Consolidation & Three-Domain Model

> **The Consolidation Rule:** *One capability, one authoritative implementation, one verification path, one accountable owner.* Preserve historical signed receipts (`build_check/qf_m5_signed_admission_receipt.json`) as immutable checkpoints rather than silently rewriting them.

### Three-Domain Security Architecture

| Domain | Responsibilities | Access Boundary |
| :--- | :--- | :--- |
| **1. Sovereign Core** | Offline/hardware keys, release signing, financial authorization (`Track 0`), household data (`household_financial`) | Strictly Operator-controlled (`Rahshaun Chambers`) |
| **2. Research Engine** | Athena, Mycelium, local Ollama (`127.0.0.1:11434`), security & dossier analysis | Restricted local access (zero signing or financial authority) |
| **3. Execution Environment** | Mobile Cockpit, APIs, automation, deployments | Least privilege (verifies signed outputs; zero access to signing keys) |

### Four-Phase `QF-M6` Consolidation Roadmap

| Phase | Objective | Acceptance Criteria |
| :--- | :--- | :--- |
| **`M6-A`** | Cryptographic Modernization | Documented cryptographic design ([`docs/QF_M6_A_CRYPTOGRAPHIC_DESIGN.md`](file:///home/quant/mycelium/docs/QF_M6_A_CRYPTOGRAPHIC_DESIGN.md)) + conjunctive `Ed25519 + ML-DSA-65` (FIPS 204) and `SHA-256 + SHA-384` verification (`qf.admission_receipt.v2`) |
| **`M6-B`** | Key Sovereignty | Offline root key hierarchy, `dev`/`test`/`prod` key separation, and hardware-protected release signing (gated on `M6-A`) |
| **`M6-C`** | Supply-Chain Integrity | Reproducible builds, signed SBOM/CBOM, anti-rollback counter, and SLSA / in-toto provenance |
| **`M6-D`** | Independent Assurance | Security review, adversarial tests, recovery exercises, and first verified sovereign economic return (`M6-01`..`M6-07`) |

