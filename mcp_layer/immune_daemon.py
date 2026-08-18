#!/usr/bin/env python3
"""
PQC Crypto-Agility Immune Daemon (Windows-native / cross-platform)
==================================================================
Supervisor that continuously evaluates cryptographic health via a
co-located OPA sidecar and autonomously renegotiates the active KEM
when the policy returns TOXIC — without restarting the worker process.

Key improvements:
  - Pure-Python atomic config rewrite (no sed, works on Windows)
  - Cross-platform signal handling with POSIX-only SIGHUP nudge
  - ConfigWatcher utility class for worker processes
  - Dynamic fallback chain traversal and loud exhaustion alerting
  - --dry-run and --once flags for safe testing
  - Explicit fail-secure path with consecutive-failure counter
  - Same OPA contract and fallback chain
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:
    requests = None  # type: ignore

try:
    import psycopg2
except ImportError:
    psycopg2 = None  # type: ignore


# ── Defaults & Constants ──────────────────────────────────────────
DEFAULT_OPA = "http://127.0.0.1:8181"
DEFAULT_VERDICT_PATH = "/v1/data/membrane/health/verdict"
DEFAULT_POLL_MS = 500
DEFAULT_FAIL_SECURE = 3
DEFAULT_CONF = Path("crypto_provider.conf")

FALLBACK_CHAIN = ["ML-KEM-768", "FrodoKEM-976-AES", "X25519"]

log = logging.getLogger("immune_daemon")


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="[%(asctime)s] %(levelname)-7s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# ── Chain Navigation ──────────────────────────────────────────────
def next_fallback(current: str) -> str:
    """Return the next algorithm down the chain, or NONE if exhausted."""
    try:
        idx = FALLBACK_CHAIN.index(current)
    except ValueError:
        # Unknown current algorithm — fail to the most conservative option
        log.warning("Unknown active KEM %r — falling to chain tail", current)
        return FALLBACK_CHAIN[-1]
    if idx + 1 < len(FALLBACK_CHAIN):
        return FALLBACK_CHAIN[idx + 1]
    return "NONE"


# ── Config helpers & Watcher ──────────────────────────────────────
class ConfigWatcher:
    """
    Detects atomic config replacement by watching (mtime, size, inode/index).
    os.replace() guarantees the swap is atomic, so a changed stat means a
    fully-written new file — never a partial read.
    """
    def __init__(self, path: Path):
        self.path = Path(path)
        self._sig = self._stat_sig()

    def _stat_sig(self) -> tuple[int, int, int] | None:
        try:
            st = self.path.stat()
            return (st.st_mtime_ns, st.st_size, st.st_ino)
        except FileNotFoundError:
            return None

    def changed(self) -> bool:
        new = self._stat_sig()
        if new != self._sig:
            self._sig = new
            return True
        return False


def read_provider_conf(path: Path) -> dict[str, str]:
    """Parse simple key=value config. Returns dict with at least active_kem / active_sig."""
    result = {"active_kem": "ML-KEM-768", "active_sig": "ML-DSA-65"}
    if not path.exists():
        return result
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            result[key.strip()] = val.strip()
    except Exception as e:
        log.warning("Could not read %s: %s", path, e)
    return result


def atomic_rewrite_conf(path: Path, updates: dict[str, str], dry_run: bool = False) -> None:
    """
    Atomically update key=value pairs in the provider conf.
    Creates the file if missing. Never uses sed.
    """
    current = read_provider_conf(path)
    current.update(updates)

    lines = [
        "# crypto_provider.conf — managed by immune_daemon",
        f"# last_updated={datetime.now(timezone.utc).isoformat()}",
        "",
    ]
    for k, v in sorted(current.items()):
        lines.append(f"{k}={v}")

    content = "\n".join(lines) + "\n"

    if dry_run:
        log.info("[dry-run] Would write to %s:\n%s", path, content)
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".immune_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
        log.info("Config rewritten atomically → %s", path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


# ── OPA interaction ───────────────────────────────────────────────
def generate_cbom(state: "ImmuneState") -> dict[str, Any]:
    """Minimal CycloneDX-shaped CBOM for the active algorithms."""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "metadata": {"timestamp": now},
        "components": [
            {
                "type": "crypto-asset",
                "name": state.active_kem,
                "cryptoProperties": {
                    "assetType": "algorithm",
                    "algorithmProperties": {"algorithm": state.active_kem},
                },
            },
            {
                "type": "crypto-asset",
                "name": state.active_sig,
                "cryptoProperties": {
                    "assetType": "algorithm",
                    "algorithmProperties": {"algorithm": state.active_sig},
                },
            },
        ],
    }


def query_opa(endpoint: str, cbom: dict[str, Any], timeout: float = 2.0) -> dict[str, Any] | None:
    """POST CBOM to OPA and return the verdict object, or None on failure."""
    if requests is None:
        log.error("requests library not installed — cannot query OPA")
        return None
    url = endpoint.rstrip("/") + DEFAULT_VERDICT_PATH
    try:
        r = requests.post(url, json={"input": cbom}, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        return data.get("result") or data
    except Exception as e:
        log.warning("OPA query failed: %s", e)
        return None


# ── Optional async audit ──────────────────────────────────────────
def async_audit(old_kem: str, new_kem: str, findings: list, pg_config: dict | None, webhook: str | None) -> None:
    def _run() -> None:
        action = f"VEIN COLLAPSE: {old_kem} -> {new_kem}"
        outcome = f"TOXIC findings: {[f.get('algorithm') for f in findings]}"

        if pg_config and psycopg2 is not None:
            try:
                conn = psycopg2.connect(**pg_config)
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO memory_logs (agent_id, action_taken, outcome) VALUES (%s, %s, %s)",
                    ("immune_daemon", action, outcome),
                )
                conn.commit()
                cur.close()
                conn.close()
                log.info("Audit log written to Postgres")
            except Exception as e:
                log.error("Postgres audit failed: %s", e)

        if webhook and requests is not None:
            try:
                requests.post(
                    webhook,
                    json={
                        "old_kem": old_kem,
                        "new_kem": new_kem,
                        "findings": findings,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                    timeout=2,
                )
                log.info("Dashboard webhook sent")
            except Exception as e:
                log.error("Webhook failed: %s", e)

    threading.Thread(target=_run, daemon=True).start()


# ── State ─────────────────────────────────────────────────────────
class ImmuneState:
    def __init__(self, conf_path: Path | str | None = None):
        if conf_path is None:
            self.conf_path = Path(os.environ.get("PQC_PROVIDER_CONF", str(DEFAULT_CONF)))
        else:
            self.conf_path = Path(conf_path)
        data = read_provider_conf(self.conf_path)
        self.active_kem = data.get("active_kem", "ML-KEM-768")
        self.active_sig = data.get("active_sig", "ML-DSA-65")
        self.consecutive_opa_failures = 0
        self.transition_count = 0
        self.last_transition: str | None = None
        self.worker_pid: int | None = None

    def refresh_from_disk(self) -> None:
        data = read_provider_conf(self.conf_path)
        self.active_kem = data.get("active_kem", self.active_kem)
        self.active_sig = data.get("active_sig", self.active_sig)


def execute_vein_collapse(state: ImmuneState, verdict: dict[str, Any]) -> None:
    """Compatibility wrapper for execute_collapse."""
    recommended = verdict.get("recommended_fallback", "NONE")
    findings = list(verdict.get("findings") or [])
    execute_collapse(state, recommended, findings, dry_run=False, pg_config=None, webhook=None)


# ── Core decision + action ────────────────────────────────────────
def execute_collapse(
    state: ImmuneState,
    recommended: str,
    findings: list,
    dry_run: bool,
    pg_config: dict | None,
    webhook: str | None,
) -> None:
    old = state.active_kem
    if recommended in ("NONE", "", None) or recommended == old:
        log.info("No useful fallback recommended — skipping collapse")
        return

    log.warning("TOXIC -> collapsing %s -> %s", old, recommended)
    atomic_rewrite_conf(state.conf_path, {"active_kem": recommended}, dry_run=dry_run)

    if not dry_run:
        state.active_kem = recommended
        state.transition_count += 1
        state.last_transition = datetime.now(timezone.utc).isoformat()
        state.consecutive_opa_failures = 0

        # Signal the worker if SIGHUP is supported (POSIX only)
        if state.worker_pid and hasattr(signal, "SIGHUP"):
            try:
                os.kill(state.worker_pid, signal.SIGHUP)
                log.info("SIGHUP nudge sent to worker PID %s", state.worker_pid)
            except ProcessLookupError:
                log.warning("Worker PID %s no longer exists", state.worker_pid)
                state.worker_pid = None
            except Exception as e:
                log.error("Failed to signal worker: %s", e)
        else:
            log.debug("No SIGHUP on this platform — worker will pick up config via watcher")

        async_audit(old, recommended, findings, pg_config, webhook)


def decision_loop(
    state: ImmuneState,
    opa_endpoint: str,
    poll_sec: float,
    fail_secure_threshold: int,
    dry_run: bool,
    once: bool,
    pg_config: dict | None,
    webhook: str | None,
) -> None:
    log.info(
        "Immune daemon started | conf=%s | opa=%s | poll=%.3fs | dry_run=%s | once=%s",
        state.conf_path,
        opa_endpoint,
        poll_sec,
        dry_run,
        once,
    )

    while True:
        state.refresh_from_disk()
        cbom = generate_cbom(state)
        verdict = query_opa(opa_endpoint, cbom)

        if verdict is None:
            state.consecutive_opa_failures += 1
            log.warning(
                "OPA unreachable (%d/%d)",
                state.consecutive_opa_failures,
                fail_secure_threshold,
            )
            if state.consecutive_opa_failures >= fail_secure_threshold:
                fallback = next_fallback(state.active_kem)
                if fallback == "NONE":
                    log.critical(
                        "FAIL-SECURE: fallback chain EXHAUSTED at %s. "
                        "No safe downgrade available. Manual intervention required.",
                        state.active_kem,
                    )
                else:
                    log.error("FAIL-SECURE triggered — %s → %s", state.active_kem, fallback)
                    execute_collapse(
                        state,
                        fallback,
                        [{"algorithm": state.active_kem, "status": "TOXIC", "reason": "OPA unreachable"}],
                        dry_run,
                        pg_config,
                        webhook,
                    )
        else:
            state.consecutive_opa_failures = 0
            status = verdict.get("node_status", "COMPLIANT")
            findings = list(verdict.get("findings") or [])
            recommended = verdict.get("recommended_fallback", "NONE")

            if status == "TOXIC":
                execute_collapse(state, recommended, findings, dry_run, pg_config, webhook)
            else:
                log.debug("COMPLIANT | active_kem=%s", state.active_kem)

        if once:
            log.info("--once complete — exiting")
            break

        time.sleep(poll_sec)


# ── Entry point ───────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(description="PQC Crypto-Agility Immune Daemon")
    parser.add_argument("--conf", type=Path, default=None, help="Path to crypto_provider.conf")
    parser.add_argument("--opa", default=None, help="OPA base URL")
    parser.add_argument("--poll-ms", type=int, default=None, help="Poll interval in milliseconds")
    parser.add_argument("--fail-secure", type=int, default=None, help="Consecutive OPA failures before fail-secure")
    parser.add_argument("--dry-run", action="store_true", help="Log actions but do not rewrite config or signal")
    parser.add_argument("--once", action="store_true", help="Run a single decision cycle and exit")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    setup_logging(args.verbose)

    conf_path = args.conf or Path(os.environ.get("PQC_PROVIDER_CONF", str(DEFAULT_CONF)))
    opa = args.opa or os.environ.get("OPA_ENDPOINT", DEFAULT_OPA)
    poll_ms = args.poll_ms or int(os.environ.get("POLL_INTERVAL_MS", DEFAULT_POLL_MS))
    fail_secure = args.fail_secure or int(os.environ.get("FAIL_SECURE_THRESHOLD", DEFAULT_FAIL_SECURE))

    pg_config = None
    if psycopg2 is not None and os.environ.get("PQC_DB_USER"):
        pg_config = {
            "host": os.environ.get("PQC_DB_HOST", "127.0.0.1"),
            "port": int(os.environ.get("PQC_DB_PORT", "5432")),
            "dbname": os.environ.get("PQC_DB_NAME", "telemetry"),
            "user": os.environ["PQC_DB_USER"],
            "password": os.environ.get("PQC_DB_PASSWORD", ""),
        }

    webhook = os.environ.get("PQC_DASHBOARD_WEBHOOK")

    state = ImmuneState(conf_path)

    worker_pid_env = os.environ.get("WORKER_PID")
    if worker_pid_env and worker_pid_env.isdigit():
        state.worker_pid = int(worker_pid_env)

    try:
        decision_loop(
            state=state,
            opa_endpoint=opa,
            poll_sec=poll_ms / 1000.0,
            fail_secure_threshold=fail_secure,
            dry_run=args.dry_run,
            once=args.once,
            pg_config=pg_config,
            webhook=webhook,
        )
    except KeyboardInterrupt:
        log.info("Shutting down cleanly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
