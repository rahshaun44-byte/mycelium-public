# PATCH SUMMARY: D-1 through D-4

**Component:** `pqc-immune-daemon`
**Status:** Verified and Merged

This document summarizes the specific patches applied to resolve the four structural gaps (D-1 through D-4) identified during the SBIR technical readiness audit.

## Patch D-1: Cold-Start Default Configuration
* **Vulnerability:** The daemon assumed a hardcoded `/opt/pqc-worker/crypto_provider.conf` path, leading to a `FileNotFoundError` crash during a cold start with `--once --dry-run` if the environment wasn't fully scaffolded.
* **Resolution:** Replaced hardcoded paths with a dynamically resolved `PQC_PROVIDER_CONF` environment variable, falling back to a local `crypto_provider.conf` if unset.
* **Verification:** `test_immune_daemon.py::test_cold_start_dry_run_success` passes. The daemon executes cleanly without crashing on a cold start.

## Patch D-2: Fail-Secure on Empty OPA Response (CRITICAL)
* **Vulnerability:** If the OPA sidecar was reachable (HTTP 200) but returned an empty JSON body `{}` (e.g., policy bundle failed to mount), the daemon silently assigned an `UNKNOWN` status. Because `UNKNOWN` != `TOXIC`, the daemon continued normal polling, failing open instead of failing secure.
* **Resolution:** `query_opa()` was updated to validate the structure of the JSON response. If `node_status` is missing or the response is empty, it returns `None`. The main `decision_loop()` routes any untrusted or missing verdict directly into the `CircuitBreaker` quarantine flow.
* **Verification:** `test_immune_daemon.py::test_empty_opa_result_is_not_compliant` passes.

## Patch D-3: Explicit Halt on Algorithm Exhaustion
* **Vulnerability:** When the fallback chain was completely exhausted (active algorithm resolving to `NONE`), the daemon attempted to silently downgrade or crashed during the config rewrite phase.
* **Resolution:** The daemon explicitly checks for `NONE`. If encountered, it logs `FATAL: TOXIC verdict with no usable fallback (recommended=NONE)`, raises an audit event, and halts via `sys.exit(1)` without touching the configuration file.
* **Verification:** `test_immune_daemon.py::test_all_algorithms_exhausted_halts` passes.

## Patch D-4: POSIX SIGHUP Worker Notification
* **Vulnerability:** The daemon rewrote the configuration file but lacked a mechanism to notify the worker process (terminating the PQC tunnel) that a rollover had occurred, requiring the worker to implement its own file watcher.
* **Resolution:** The daemon now tracks `WORKER_PID`. After an atomic config rewrite, it issues `os.kill(WORKER_PID, signal.SIGHUP)` (on POSIX systems), enabling zero-downtime rotation for workers that support SIGHUP reloads.
* **Verification:** `test_immune_daemon.py::test_worker_pid_signaling` passes.
