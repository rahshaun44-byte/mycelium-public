# QuantumFlex Operator Acceptable Use Policy (AUP)

**Policy Document:** `QF-GOV-AUP-001`  
**Governance Layer:** QuantumFlex Legal & Operational Assurance Layer (QF-LOAL)  
**Standard:** QF-LEGAL-001 Authorized Operation Invariant  
**Classification:** Operator Ethics, Agent Governance & Safety  
**Last Reviewed:** 2026-11-01  

---

## 1. Principles of Authorized Operation

This policy governs the conduct of human operators, software agents, and automated orchestrators interacting with the QuantumFlex substrate.

Every operator action must align with the **QuantumFlex Operating Constitution**:
$$\text{Mission Success} = \text{Security} + \text{Peace} + \text{Financial Independence} + \text{Scientific Freedom} + \text{Positive Impact}$$

---

## 2. Mandatory Operator Directives

1. **The Zero Cloud Spend Invariant ($0.00):**  
   Operators and agents must never route prompt data or operational contexts to paid cloud LLM endpoints. All local neural inference must route exclusively to the local Ollama daemon on `127.0.0.1:11434`.
2. **Pedagogical & Algorithmic Rigor:**  
   Autonomous tools must act as tutors, boundary condition checkers, and test automation coaches. Code generation must strictly preserve step-by-step human comprehension and formal correctness.
3. **Web3 & Circle USDC Settlement Safety:**  
   - All USDC transactions must strictly use 6-decimal precision (`1_000_000n` per 1 USDC). 18-decimal scaling is strictly prohibited and denied by constitutional policy (`QF-AUTH-01`).
   - Every mutating transaction must derive a deterministic UUID v4 idempotency key from proof block hashes (`sha256(blockHash)`).
   - Read operations must use the Smart Contract Platform SDK; state-mutating executions must use the Developer-Controlled Wallets SDK.
4. **Hardware Key Discipline:**  
   Private keys must never leave their designated hardware trust anchors (Microsoft Pluton TPM 2.0 on `qfx-yoga`, Google Titan-M3 StrongBox on `qfx-pixel`). Exporting unencrypted `.pem` or seed data to shared or unencrypted storage is grounds for immediate credential revocation.

---

## 3. Prohibited Operator Actions

- **Destructive Commands:** Running `rm -rf`, `DROP TABLE`, `TRUNCATE`, or force-pushing Git branches without verified backup and explicit Chief Architect confirmation is prohibited.
- **Credential Logging:** Printing, echoing, committing, or displaying private keys, API secrets, or passwords in terminal outputs, PRs, or public repositories is strictly barred.
- **Fabrication of Hardware Telemetry:** Generating mock devices, fake hostnames (e.g. "HP Pavilion", "Galaxy S23 FE"), or artificial attestation strings is prohibited. Live Tailscale and live hardware props must always be queried directly.
