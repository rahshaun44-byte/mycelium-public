# REFERENCE PATTERN: CRYPTO-AGILITY SUPERVISOR & CONTINUOUS POLICY ENFORCEMENT
**Autonomous Algorithmic Fallback & Control-Plane Policy Verification**

*Author:* Rahshaun Chambers (FinallyFungus LLC / QuantumFlex Systems)  
*Date:* August 2026  
*Classification:* Technical Reference Pattern & Architectural Prototype

---

## 1. Executive Summary & Context

The cryptographic landscape is transitioning toward post-quantum standards under guidance from NIST (FIPS 203/204/205), NSA CNSA 2.0 timelines, and federal migration planning memos (e.g., OMB M-26-15). Organizations face the challenge of designing crypto-agile architectures capable of responding to algorithmic vulnerabilities without requiring destructive code refactoring or scheduled application rebuilds.

This document presents an **Engineering Reference Pattern for a Crypto-Agility Supervisor**: a lightweight, cross-platform control plane that combines CycloneDX-shaped active algorithm self-inventories with an Open Policy Agent (OPA) declarative policy engine. The supervisor autonomously evaluates cryptographic health and executes **fail-secure atomic configuration updates** (e.g., `ML-KEM-768` $\rightarrow$ `FrodoKEM-976-AES` $\rightarrow$ `X25519` $\rightarrow$ `HALT`) without restarting the supervisor process.

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

### 2.3 Atomic Configuration Rollover (Control-Plane Migration)
Upon receiving a `TOXIC` verdict from OPA, the supervisor executes an **Atomic Configuration Rollover**:
1. Generates an updated `crypto_provider.conf` within a secure staging buffer.
2. Performs an atomic file system swap (`os.replace` / POSIX `rename`) to prevent partial reads.
3. Worker processes, monitoring via native inode/mtime watchers (`ConfigWatcher`) or POSIX `SIGHUP`, detect the swap and adopt the fallback algorithm for subsequent session negotiations — **zero process restarts, zero rebuilds**.
4. *Protocol Boundary:* In-band mid-stream socket re-framing (epoch tracking, framed record markers) is a separate worker data-plane protocol design milestone and is distinct from this supervisor control plane.

### 2.4 Self-Healing Quarantine Architecture (Circuit Breaker)

The supervisor implements a **three-state circuit breaker** to distinguish *transient environmental failures* (OPA briefly unreachable, policy bundle not yet mounted) from *structural cryptographic threats* (genuine `TOXIC` verdict). This prevents a 2-second network timeout from permanently halting the node.

```
OPA unreachable /       Circuit Breaker     max_retries        Terminal
empty response  ------> QUARANTINE      --> exhausted      --> COLLAPSE
                                                               (exit 1)
                        |
                        | OPA returns COMPLIANT before max_retries
                        v
                        RECOVERY --> ACTIVE (circuit breaker reset)
```

**State definitions:**

| State | Trigger | Action |
|:---|:---|:---|
| `ACTIVE` | OPA returns `COMPLIANT` | Normal polling continues |
| `QUARANTINE` | OPA unreachable / empty / untrusted (within retry budget) | Atomically writes `safe_mode_cipher`; waits `quarantine_delay_ms`; retries |
| `COLLAPSED` | `max_retries` failures within `timeout_window_sec` | Terminal `execute_vein_collapse()` then `exit 1` |

**OPA as single source of truth for recovery parameters** — circuit breaker configuration is never hardcoded in Python. At startup the daemon queries `GET /v1/data/membrane/health/recovery_map` and builds the `CircuitBreaker` from the authoritative Rego values:

```rego
recovery_map := {
    "max_retries": 3,
    "timeout_window_sec": 60,
    "quarantine_delay_ms": 5000,
    "safe_mode_cipher": "FrodoKEM-976-AES",
    "quarantine_action": "isolate_and_hold",
}
```

To adjust retry behavior for a specific tactical deployment (e.g., contested-environment edge sensors with higher transient failure rates), update the `.rego` file — not the Python binary.

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

Automated test suite verification (12 invariants, all passing):

```
PASS: execute_vein_collapse() rewrote crypto_provider.conf and updated state
PASS: exhausted fallback chain raises SystemExit and halts without rewriting config
PASS: [D-1] daemon starts with default config path (--once --dry-run)
PASS: [D-2] empty OPA result returns None (fail-secure trigger)
PASS: [D-2] unexpected/unknown node_status triggers fail-secure fallback
PASS: [D-3] unknown algorithm does not downgrade silently
PASS: [D-4] worker PID tracking functional
PASS: [SINGLE SOURCE OF TRUTH] OPA (.rego) authoritative fallback chain verified
PASS: [Q-1] circuit breaker quarantine -> recover lifecycle verified
PASS: [Q-2] circuit breaker trips after max_retries (3) consecutive failures
PASS: [Q-3] quarantine atomically applies safe-mode cipher to config
PASS: [Q-4] recovery_map loaded from rego (single source of truth) verified

[ALL 12 SECURITY, COMPLIANCE & SELF-HEALING INVARIANTS 100% VERIFIED]
```

---

## 4. Scope and Limitations

- **Control Plane Only (No Cryptography Performed):** The supervisor is a control-plane orchestration component that performs no cryptography directly. It contains no cryptographic module, validated or otherwise, and performs no key establishment, encryption, or signing. It is designed to sit *around* an organization's existing cryptographic modules.
- **Reference Pattern, Not Certification:** This work represents an engineering reference pattern and prototype. It is not an accredited 3PAO/C3PAO compliance certificate.
- **KEM-Scoped Rollover:** Automated fallback is currently scoped to key-establishment algorithms. Signature schemes are evaluated and reported in the CBOM, but not automatically rotated.
- **Session Boundary:** Algorithm updates take effect for new sessions established under the rewritten provider configuration. Mid-stream in-flight socket rollover is a separate protocol specification.
- **Supervisor Restart Required:** `exit 1` on `COLLAPSED` is intentional fail-loud design. The daemon must be supervised (systemd `Restart=on-failure` on Linux; Task Scheduler on Windows) to achieve full self-healing without operator intervention.

---

## 5. Enterprise Advisory & Prototyping Scope

For engineering teams planning crypto-agility roadmaps:
- **Phase 1: Cryptographic Inventory & CBOM Automated Pipeline Setup**
- **Phase 2: OPA Policy Customization & Threat Feed Integration**
- **Phase 3: Daemon Hardening & Fail-Secure Fallback Verification**
- **Phase 4: Technical Evidence Artifacts for Internal Governance**
- **Phase 5: Self-Healing Quarantine & Circuit Breaker Integration** — deploying `recovery_map`-driven quarantine, sliding-window failure tracking, and AMARA telemetry bus integration for autonomous recovery in contested/degraded environments.

*Contact:* advisory@finallyfungus.com | Enterprise Architectural Services

