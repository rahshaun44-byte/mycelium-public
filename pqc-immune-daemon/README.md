# PQC Crypto-Agility Immune Daemon

A supervisor daemon that monitors the cryptographic posture of a post-quantum-capable worker environment and executes autonomous, fail-secure configuration rollover when an Open Policy Agent (OPA) policy engine flags an active algorithm as compromised.

Built as an engineering reference pattern to explore the mechanics of crypto-agility described in [NIST FIPS 203/204/205](https://csrc.nist.gov/pubs/fips/203/final) and [OMB M-26-15](https://postquantum.com/security-pqc/omb-m-26-15-pqc-migration/): continuous cryptographic inventory, provider-based configuration, declarative policy evaluation, and atomic rollover without process rebuilds.

> **Engineering Prototype Notice:** This repository is an independent technical demonstration and reference pattern. It is **not** a certified C3PAO/3PAO audit artifact, does not possess formal FIPS validation certificates, and does not claim federal agency compliance status. It serves as a verifiable demonstration of crypto-agility control-plane mechanisms.

---

## Architecture & Scope

This repository implements the **Supervisor Control Plane**:
- **Automated Inventory Snapshot:** Periodically constructs a CycloneDX-shaped Cryptographic Bill of Materials (CBOM) from active provider configurations.
- **Declarative Policy Evaluation:** Queries an Open Policy Agent (OPA) sidecar running `membrane_health.rego`.
- **Single Source of Truth:** The fallback chain (`fallback_map`) and self-healing parameters (`recovery_map`) are defined authoritatively in OPA / `membrane_health.rego` and parsed dynamically by the daemon. Nothing is hardcoded in Python.
- **Fail-Secure Atomic Configuration Rollover:** When a `TOXIC` verdict is returned or OPA becomes unreachable, the daemon atomically updates `crypto_provider.conf` and signals/notifies the worker process.
- **Self-Healing Quarantine:** Transient failures enter a controlled quarantine state before terminal collapse. See [Self-Healing Architecture](#self-healing-architecture) below.
- **Scope Boundary:** This daemon is a **supervisor control plane**. Mid-stream in-band session survival requires socket-framing and epoch support within the worker protocol plane (BYO Worker) and is not implemented here. Algorithm rollovers apply to subsequent sessions established by the worker.

---

## How It Works

Every `POLL_INTERVAL_MS` (default 500ms), the daemon:

1. Assembles a minimal CycloneDX v1.5 CBOM representation of the active cryptographic primitives.
2. POSTs the CBOM to the local OPA endpoint (`/v1/data/membrane/health/verdict`).
3. Evaluates the verdict:
   - **`COMPLIANT`**: Normal operation continues. If recovering from quarantine, logs recovery event and resets circuit breaker.
   - **`TOXIC`**: The daemon atomically rewrites `crypto_provider.conf` via `tempfile` + `fsync` + `os.replace`, updates state metrics, and sends a `SIGHUP` nudge to `WORKER_PID` (POSIX) or allows `ConfigWatcher` to detect the update.
   - **OPA Unreachable / Empty / Untrusted**: Routes through the `CircuitBreaker`. Enters `QUARANTINE` (applies `safe_mode_cipher`, retries). After `max_retries` consecutive failures within `timeout_window_sec`, the breaker **trips** and executes terminal fail-secure collapse.
   - **Chain Exhaustion**: If no valid fallback algorithm remains, the daemon raises a critical alert and halts (`exit 1`), refusing silent insecure downgrade.

---

## Self-Healing Architecture

The daemon implements a **three-state circuit breaker** to distinguish transient environmental failures (OPA briefly unreachable, policy bundle not yet mounted) from structural cryptographic threats (genuine TOXIC verdict).

```
OPA unreachable /       Circuit Breaker     Max retries        Terminal
empty response  ------> QUARANTINE      --> exhausted      --> COLLAPSE
                                                               (exit 1)
                        |
                        | OPA returns COMPLIANT before max_retries
                        v
                        RECOVERY -> ACTIVE (circuit breaker reset)
```

### State Transitions

| State | Trigger | Action |
|:---|:---|:---|
| `ACTIVE` | OPA returns `COMPLIANT` | Normal 500ms polling continues |
| `QUARANTINE` | OPA unreachable / empty / untrusted (< `max_retries`) | Atomically writes `safe_mode_cipher` to conf; waits `quarantine_delay_ms`; retries |
| `COLLAPSED` | `max_retries` failures within `timeout_window_sec` | Terminal `execute_vein_collapse()` then `exit 1` |

### OPA as Single Source of Truth for Recovery Parameters

Circuit breaker parameters are **never hardcoded in Python**. At daemon startup, `decision_loop()` queries:

```
GET /v1/data/membrane/health/recovery_map
```

The authoritative values come from `membrane_health.rego`:

```rego
recovery_map := {
    "max_retries": 3,
    "timeout_window_sec": 60,
    "quarantine_delay_ms": 5000,
    "safe_mode_cipher": "FrodoKEM-976-AES",
    "quarantine_action": "isolate_and_hold",
}
```

To change retry behavior for a specific deployment environment, update the `.rego` file — not the Python binary.

### Supervisor Restart Policy

`exit 1` on `COLLAPSED` is intentional fail-loud design. The daemon must be supervised:

- **Linux (systemd):** `Restart=on-failure` in the `.service` unit file
- **Windows:** Task Scheduler with "Restart task if it fails" enabled, or wrap `Start-ImmuneDaemon.ps1` in a monitoring loop

Without a supervisor, three consecutive failures within 60 seconds permanently removes the crypto-agility layer. This is a deliberate tradeoff — silent continuation in a degraded state is the failure mode being prevented.

---

## Fallback Chain (OPA Single Source of Truth)

The fallback map is defined directly in `membrane_health.rego`:

| Active Algorithm | Fallback |
|:---|:---|
| `ML-KEM-512` (Level 1) | `FrodoKEM-640-AES` |
| `ML-KEM-768` (Level 3) | `FrodoKEM-976-AES` |
| `ML-KEM-1024` (Level 5) | `FrodoKEM-1344-AES` |
| `FrodoKEM-*` | `X25519` (Classical Hybrid) |
| `X25519` | `NONE` (Exhaustion Halt) |

FrodoKEM uses unstructured lattice assumptions distinct from ML-KEM (Module-LWE), preventing common-mode failure across the cryptographic boundary.

---

## Files

| File | Purpose |
|:---|:---|
| `immune_daemon.py` | Supervisor daemon: CBOM generation, OPA query, circuit breaker, quarantine mode, atomic conf rewrite, fail-secure rollover. |
| `membrane_health.rego` | Authoritative OPA policy: approved algorithm registry, threat flags, `fallback_map`, `recovery_map`. |
| `membrane_health_test.rego` | OPA policy unit tests. |
| `crypto_provider.conf.example` | Template provider configuration file. |
| `test_immune_daemon.py` | Test suite verifying all **12** security, fail-secure, quarantine, and single-source-of-truth invariants. |
| `Start-ImmuneDaemon.ps1` | Windows launcher. |
| `Get-ImmuneDaemonStatus.ps1` | Windows status check: reads PID file, tails live logs. |

---

## Running It

```bash
cp crypto_provider.conf.example crypto_provider.conf

export PQC_PROVIDER_CONF="$(pwd)/crypto_provider.conf"
export WORKER_PID=$(pgrep -f your_worker.py)
export OPA_ENDPOINT="http://127.0.0.1:8181"

python3 immune_daemon.py
```

### Environment Variables

| Variable | Default | Purpose |
|:---|:---|:---|
| `OPA_ENDPOINT` | `http://127.0.0.1:8181` | OPA sidecar base URL |
| `PQC_PROVIDER_CONF` | `crypto_provider.conf` | Path to the provider config file |
| `WORKER_PID` | _(unset)_ | Worker PID to signal on rollover (POSIX SIGHUP) |
| `POLL_INTERVAL_MS` | `500` | OPA poll interval in milliseconds |
| `PQC_REGO_POLICY` | _(auto-discovered)_ | Override path to `membrane_health.rego` |
| `AMARA_TELEMETRY_URL` | `http://127.0.0.1:8000/api/events` | Local AMARA telemetry bus (fire-and-forget) |
| `PQC_DASHBOARD_WEBHOOK` | _(unset)_ | HTTP webhook for rollover audit events |
| `PQC_DB_USER` | _(unset)_ | Postgres audit log user (opt-in) |

### Windows

```powershell
.\Start-ImmuneDaemon.ps1
.\Get-ImmuneDaemonStatus.ps1
```

### Running the Tests

```bash
python3 test_immune_daemon.py
```

Expected output:
```
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

## What This Is, and Isn't

This grew out of a personal, self-hosted security project and is offered as a demonstration of working crypto-agility mechanics — a piece of evidence, not a finished product. It is not deployed anywhere, has no users, and isn't seeking to be a drop-in dependency for production systems. If you're evaluating it as part of a hiring process or technical review: read the code, run the tests yourself, and judge it on that.

## License

Apache License 2.0 — see [LICENSE](LICENSE). Chosen over MIT for the explicit patent grant (Section 3), which matters more than usual for cryptographic code: it gives downstream users an express patent license and a patent-retaliation clause, not just a copyright permission.
