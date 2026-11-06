# QUANTUMFLEX TRUTH LOG & ARCHITECTURAL SPECIFICATION
**Document ID:** QF-TL-2026-11-05-001  
**Component:** `pqc-immune-daemon` / Mycelium Service Plane / Stratum 0 Witness  
**External Grant Reference:** NLnet Foundation Application `2026-11-4af`  
**Hardware Baseline:** `qfx-yoga` (Ubuntu 26.04.1 LTS, Pluton TPM 2.0, Loopback Air-Gap)  
**Governing Invariant:** $Y = f(x - h) + k$  

## 1. Executive Abstract
QuantumFlex resolves Byzantine fault tolerance (BFT) and TOCTOU race conditions on bare-metal edge nodes without O(n^2) consensus voting storms by implementing the physical mechanics of a biological nervous system's intracellular microtubule lattice and axonal refractory window: Y = f(x - h) + k.

## 2. Variable Mapping
- x (Event-vs-Hold Cycle): Raw ingress payload arriving at the loopback/Tailscale boundary (100.64.0.0/10 -> 127.0.0.1).
- h (Entropy Shunting): Malformed packets, forged Ed25519/ML-DSA-65 tokens, or D-2 policy failures shunted to the Ghost Node quarantine sink (Landauer-compliant shock absorber).
- k (Refractory Memory Window Hold): Synchronous policy lock across OPA Gate (127.0.0.1:8181) and Stratum 0 Monotonic Witness (127.0.0.1:8444) preventing TOCTOU state mutation during PQC cipher transitions (FrodoKEM-976-AES <-> ML-KEM-768).
- Y (Deterministic Commit): Append-only state transition committed to quantum_flex_engine (127.0.0.1:9444) and hash-chained SQLite ledger.db, anchored by QF-A5 provenance and IBM Quantum GHZ coherence certification (ibm_kingston Job dbl33e56p51s73cnltvg, F = 0.9355, W = -0.4355).
