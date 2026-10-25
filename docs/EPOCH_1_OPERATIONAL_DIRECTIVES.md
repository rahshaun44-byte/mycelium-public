# 🚀 Epoch-1 Sovereign Operational Directives (QuantumFlex)

## 1. Executive Context & Invariant Posture
With the successful completion of the Epoch-1 Sovereign Genesis Reboot:
- All legacy Shamir Secret Sharing (SSS) ceremony overhead has been permanently tombstoned in [`evidence_ledger.jsonl`](file:///home/quant/Documents/qf/evidence_ledger.jsonl) (Entry #39).
- The C++ Evidence Engine (`quantum_flex_engine`) is running in `ACTIVE` state on `127.0.0.1:9444`, directly anchored to local Microsoft Pluton TPM 2.0 hardware and local OPA policy evaluation (`127.0.0.1:8181`).
- The Zero-Entropy Invariant is permanent: remote QPU data carries 0 assessed secret entropy bits and is strictly barred from cryptographic key derivation. All cryptographic keys derive exclusively from local hardware roots (Pluton TPM 2.0, Titan M2 StrongBox, Linux `/dev/urandom`).

---

## 2. Immediate Priorities for Epoch-1

### Priority 1: Base Mainnet USDC Settlement & DCW Relayer Execution
* **Objective:** Complete on-chain deployment and dispatch of IBM hardware-attested USDC micro-settlements.
* **Smart Contract:** Verify [`QuantumFlexUSDCSettler.sol`](file:///home/quant/Documents/qf/contracts/QuantumFlexUSDCSettler.sol) on Base Mainnet (Chain ID 8453) under `evm_version = "paris"`.
* **Zero Gas Burn Guarantee:** Pre-flight check on `executedProofs(blockHash)` mapping to skip already-settled proofs with 0 gas consumed.
* **Concurrency Lock:** Enforce strict `asyncio.Semaphore(1)` in [`dcw_relayer.py`](file:///home/quant/Documents/qf/dcw_relayer.py) to prevent nonce collisions and mempool races.
* **Attestation:** Authenticate settlement digests using P-256 (`secp256r1`) signatures with low-s normalization matching `qf-attester-key` on the Pixel 11 Pro Titan M2 StrongBox.

### Priority 2: Pluton TPM 2.0 Local Node Governance (Zero Ceremony Friction)
* **Objective:** Keep `quantum_flex_engine` lean, unsealed, and listening without manual Shamir shard unsealing ceremony prompts.
* **Local Invariant:** System boots directly into `SystemState::ACTIVE`. All authorization decisions defer to the local OPA Gatekeeper (`membrane_health.rego` on `:8181`).
* **Continuous Monitoring:** Maintain A.M.A.R.A. Biological Monitor daemon (`qf-monitor.service`) to keep iowait and memory overhead optimal.

### Priority 3: Real-Node Mesh Telemetry & Kafka Streaming
* **Objective:** Stream verifiable telemetry events across the 3 real nodes on Tailnet `example-tailnet.ts.net`:
  1. **`qfx-yoga` (`100.64.1.31`)**: Primary host engine, local AI inference (Ollama `:11434`), and telemetry forwarder.
  2. **`g6pro` (`100.64.1.19`)**: Dedicated Apache Kafka broker (`:9092`) and monitoring UI (`:8090`).
  3. **`qfx-pixel` (`100.64.1.16`)**: Chief Architect HUD and out-of-band transaction signer.
* **Zero Fabrication:** Strictly ignore and reject phantom devices (no "HP Pavilion", no "Galaxy S23 FE").

### Priority 4: IBM Quantum Quota Preservation (558s Intact)
* **Objective:** Preserve the remaining 558.0 quantum seconds of free Open Plan quota.
* **Policy:** Zero unvetted QPU jobs. Remaining seconds are reserved strictly for pre-registered multi-qubit entanglement parity oscillation runs ($R_\phi^{\otimes N}$).
* **Clarification:** Do NOT spend quantum seconds on brute-force 1,000,000-shot noise collection for NIST SP 800-90B. The zero-entropy invariant makes QRNG key generation obsolete.
