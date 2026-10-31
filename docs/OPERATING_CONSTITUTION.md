# QuantumFlex Operating Constitution & Permanent Mycelium Controls

**Document ID:** QF-CONST-01  
**Security Classification:** Sovereign Internal — Cryptographically Pinned  
**Effective Date:** 2026-10-30  
**Primary Principal:** Rahshaun Chambers (The Operator / Chief Architect)  
**Target Topology:** `qfx-yoga` (Ubuntu 26.04.1 LTS, Pluton TPM 2.0), `qfx-pixel` (Pixel 11 Pro, Titan M2 StrongBox), `g6pro` (HP ProBook 450 G6)  
**Executable Enforcement:** [`sentinel/policies/operating_constitution.rego`](file:///home/quant/mycelium/sentinel/policies/operating_constitution.rego), [`sentinel/policies/operating_constitution.wasm`](file:///home/quant/mycelium/sentinel/policies/operating_constitution.wasm), [`src/operating_constitution.py`](file:///home/quant/mycelium/src/operating_constitution.py)  

---

## 0. Preamble: The Mission Serves Life

Technology, wealth, research, and commercial growth are instruments. The security, peace, health, loved ones, helpers, and freedom of **Rahshaun Chambers** are the outcomes.

A system that generates substantial revenue while exhausting its operator or transferring uncompensated risk onto its helpers has failed its purpose.

$$\text{Mission Success} = \text{Security} + \text{Peace} + \text{Financial Independence} + \text{Scientific Freedom} + \text{Positive Impact}$$

---

## 1. The Five Constitutional Principles

### Principle I — Operator First
The Operator's well-being takes precedence over expansion:
- Protect household stability before funding external opportunities.
- Preserve physical and mental health, recovery windows, and personal peace.
- Protect personal time and freedom (retreats, study, family, cabins in the snow).
- Never confuse technical accumulation with personal prosperity.

### Principle II — The Golden Financial Invariant ($R \ge 6O$)
$$\boxed{R \ge 6O}$$
Where $R$ represents protected liquid reserves and $O$ represents average monthly obligations (living expenses, debt service, and fixed operating commitments).

| Financial Condition | Constitutional Operating Decision | Enforcement Gate |
| :--- | :--- | :--- |
| $R < 6O$ | `PROTECT_AND_REBUILD_RESERVES` | **DENY** all capital allocations & discretionary expansion |
| $R = 6O$ | `MAINTAIN_RESERVE_RESTRICT_EXPANSION` | **ALLOW** steady zero-outlay ops only; **DENY** discretionary expansion |
| $R > 6O$ and $(R - \Delta) < 6O$ | `POST_ALLOCATION_RESERVE_BREACH` | **DENY** allocation that pierces the 6-month floor |
| $R > 6O$ and $(R - \Delta) \ge 6O$ | `EVALUATE_FUNDED_OPPORTUNITY` | **ADMIT** only from productive/surplus buckets (never Bucket 1) |
| `financial_shock == true` | `FREEZE_DISCRETIONARY_SPENDING` | **DENY** immediately; recalculate obligations |

**Sacred Bucket 1 Rule:** Bucket 1 (`IRON_RESERVE`) is permanently locked for household protection and may never be allocated to venture or speculative expenditure. Raw household dollar figures are never persisted into logs, telemetry, or external reports; `QF-CAPITAL-01` emits dimensionless month-coverage ratios only.

### Principle III — Sovereign Intelligence
Athena, Amara, Ollama, and Mycelium enforce strict epistemic and data sovereignty:
- Local-first inference exclusively via loopback (`127.0.0.1:11434`) at **\$0.00 external cloud spend**.
- Zero transmission of proprietary research, client confidential corpora, or household financial records to public cloud APIs.
- Mandatory SHA-256 document and chunk provenance (`doc_sha256`, `chunk_sha256`) on ingested research.
- Zero Ambient Data collection (`PrivacyFilter.sanitize_telemetry_frame`).

### Principle IV — Protect the Helpers
QuantumFlex never succeeds at the expense of the people supporting it:
- Sustainable workloads and clear, bounded responsibilities.
- Fair compensation and honest, evidence-backed reporting.
- Secure infrastructure with zero uncompensated operational or legal risk transferred to helpers.

### Principle V — Peaceful Wealth Creation
Wealth is built with patience, integrity, and discipline—never turf wars or ego—to purchase permanent financial independence, time sovereignty, scientific freedom, and positive impact from overflowing stability.

---

## 2. Four Permanent Enforceable Mycelium Controls

| Control ID | Domain | Executable Enforcement Invariants |
| :--- | :--- | :--- |
| **`QF-CAPITAL-01`** | Capital & Reserve Gate | Enforces $R \ge 6O$ and $(R - \Delta) \ge 6O$, blocks `IRON_RESERVE` venture drawdowns, freezes discretionary outlays on `financial_shock`, and strips raw dollar figures from emitted audit details. |
| **`QF-PRIVACY-01`** | Sovereign Data & Inference | Enforces loopback-only inference (`127.0.0.1:11434`), `cloud_spend_usd == 0`, blocks confidential egress, blocks household financial exposure, verifies SHA-256 provenance, and enforces `PrivacyFilter`. |
| **`QF-AUTH-01`** | Human Financial Authority | Blocks autonomous agent self-authorization on consequential financial actions; requires verified Operator approval (`rahshaun_chambers` / `qf-operator-key`), cryptographic attestation (`CredTwoManAttestation`, `PlutonTPM2`, `TitanM2StrongBox`, `CredMtlsCertVerified`, or `CredShamirThresholdMet`), RFC 4122 UUIDv4 idempotency, and the 6-decimal USDC invariant. |
| **`QF-OPS-01`** | Workload Sustainability | Enforces $\le 90\text{ min}$ continuous deep-work blocks, $\le 1$ named object per block, $\le 8\text{ hours}$ daily deep work, $\ge 7\text{ hours}$ rest in 24h, halts expansion on `operator_fatigue_flag`, and requires `helper_fairness_verified == true`. |

---

## 3. Dual-Engine Verification Architecture

Every constitutional check in [`evaluate_operating_constitution()`](file:///home/quant/mycelium/src/operating_constitution.py) executes across **two independent layers**:
1. **Deterministic Python Invariant Engine** ([`src/operating_constitution.py`](file:///home/quant/mycelium/src/operating_constitution.py))
2. **Hermetic In-Process OPA WebAssembly Gatekeeper** ([`sentinel/policies/operating_constitution.wasm`](file:///home/quant/mycelium/sentinel/policies/operating_constitution.wasm) via `OPAWasmEngine` with zero external host builtins)

If either engine denies—or if any single control's `allow` boolean or `decision` code diverges between Python and WebAssembly—the composite gate fails closed (`verdict = "DENY"`).

