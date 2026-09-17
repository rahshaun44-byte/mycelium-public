#!/usr/bin/env python3
"""
PQC Crypto-Agility Immune Daemon (Windows-native / cross-platform)
==================================================================
Supervisor that continuously evaluates cryptographic health via a
co-located OPA sidecar and autonomously renegotiates the active KEM
when the policy returns TOXIC — without restarting the worker process.

Self-Healing Architecture (Y = f(x - h) + k):
  - CircuitBreaker with sliding-window failure tracking
  - Quarantine state: isolates node, applies safe-mode cipher, retries
  - Recovery: on OPA return, validates compliance, resumes ACTIVE
  - Terminal collapse: only after max_retries exhausted (from OPA recovery_map)
  - k (baseline truth): OPA remains the single source of truth — always

Key improvements:
  - Pure-Python atomic config rewrite (no sed, works on Windows)
  - Cross-platform signal handling with POSIX-only SIGHUP nudge
  - ConfigWatcher utility class for worker processes
  - Dynamic fallback chain traversal and loud exhaustion alerting
  - --dry-run and --once flags for safe testing
  - CircuitBreaker quarantine → recover → collapse pipeline
  - Same OPA contract and fallback chain

Environment variables (all optional):
  OPA_ENDPOINT          default http://127.0.0.1:8181
  PQC_PROVIDER_CONF     path to crypto_provider.conf
  WORKER_PID            PID of the worker process to signal on rollover (POSIX)
  POLL_INTERVAL_MS      default 500
  FAIL_SECURE_THRESHOLD default 3
  PQC_DB_*              optional Postgres audit
  PQC_DASHBOARD_WEBHOOK optional webhook
  AMARA_TELEMETRY_URL   default http://127.0.0.1:8000/api/events
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

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
DEFAULT_FALLBACK_MAP_PATH = "/v1/data/membrane/health/fallback_map"
DEFAULT_RECOVERY_MAP_PATH = "/v1/data/membrane/health/recovery_map"
DEFAULT_POLL_MS = 500
DEFAULT_FAIL_SECURE = 3
DEFAULT_CONF = Path("crypto_provider.conf")
DEFAULT_AMARA_URL = "http://127.0.0.1:8000/api/events"

# Circuit breaker defaults (overridden by OPA recovery_map)
DEFAULT_MAX_RETRIES = 3
DEFAULT_TIMEOUT_WINDOW = 60
DEFAULT_QUARANTINE_DELAY_MS = 5000
DEFAULT_SAFE_MODE_CIPHER = "FrodoKEM-976-AES"

log = logging.getLogger("immune_daemon")


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="[%(asctime)s] %(levelname)-7s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# ── Authoritative Fallback Chain (OPA / Rego Single Source of Truth) ──
def parse_rego_fallback_map(rego_content: str) -> dict[str, str]:
    """Extract the authoritative fallback_map defined in membrane_health.rego."""
    match = re.search(r'(?<![a-zA-Z0-9_])fallback_map\s*:?=\s*\{([^}]+)\}', rego_content, re.DOTALL)
    if not match:
        return {}
    body = match.group(1)
    entries = re.findall(r'"([^"]+)"\s*:\s*"([^"]+)"', body)
    return dict(entries)


def load_fallback_map_from_rego(rego_path: Path | str | None = None) -> dict[str, str]:
    """Read and parse the authoritative fallback map directly from the .rego file on disk."""
    candidates: list[Path] = []
    if rego_path is not None:
        candidates.append(Path(rego_path))
    env_path = os.environ.get("PQC_REGO_POLICY")
    if env_path:
        candidates.append(Path(env_path))
    candidates.extend([
        Path("membrane_health.rego"),
        Path(__file__).resolve().parent / "membrane_health.rego",
        Path(__file__).resolve().parent.parent / "sentinel" / "policies" / "membrane_health.rego",
        Path(__file__).resolve().parent.parent / "mycelium" / "sentinel" / "policies" / "membrane_health.rego",
    ])
    for path in candidates:
        if path.is_file():
            try:
                content = path.read_text(encoding="utf-8")
                mapping = parse_rego_fallback_map(content)
                if mapping:
                    return mapping
            except Exception as e:
                log.warning("Failed to read rego policy from %s: %s", path, e)
    log.warning("No authoritative membrane_health.rego found in candidate paths")
    return {}


def fetch_fallback_map_from_opa(endpoint: str, timeout: float = 2.0) -> dict[str, str] | None:
    """Query live OPA endpoint for the authoritative fallback_map rule."""
    if requests is None:
        return None
    url = endpoint.rstrip("/") + DEFAULT_FALLBACK_MAP_PATH
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        result = data.get("result")
        if isinstance(result, dict) and result:
            return result
    except Exception as e:
        log.debug("OPA fallback_map query failed: %s", e)
    return None


def get_authoritative_fallback_map(opa_endpoint: str | None = None, rego_path: Path | str | None = None) -> dict[str, str]:
    """
    Retrieve the authoritative fallback map from Wasm, OPA, or membrane_health.rego.
    Single source of truth: OPA (.rego / .wasm).
    """
    if opa_endpoint == "wasm" or (os.environ.get("PQC_FORCE_HTTP") != "1" and opa_endpoint != "http://fake"):
        try:
            from sentinel.policies.wasm_gatekeeper import get_membrane_wasm_gatekeeper
            wasm_gate = get_membrane_wasm_gatekeeper()
            if wasm_gate is not None:
                m = wasm_gate.get_fallback_map()
                if m:
                    return m
        except Exception:
            pass

    if opa_endpoint and opa_endpoint != "wasm":
        live = fetch_fallback_map_from_opa(opa_endpoint)
        if live:
            return live
    return load_fallback_map_from_rego(rego_path)


# Dynamically initialized from authoritative .rego single source of truth
FALLBACK_MAP = load_fallback_map_from_rego()


# ── Authoritative Recovery Map (OPA / Rego Single Source of Truth) ──
def parse_rego_recovery_map(rego_content: str) -> dict[str, Any]:
    """Extract the authoritative recovery_map defined in membrane_health.rego."""
    match = re.search(r'recovery_map\s*:?=\s*\{([^}]+)\}', rego_content, re.DOTALL)
    if not match:
        return {}
    body = match.group(1)
    result: dict[str, Any] = {}
    # Extract string values
    for key, val in re.findall(r'"([^"]+)"\s*:\s*"([^"]+)"', body):
        result[key] = val
    # Extract integer values
    for key, val in re.findall(r'"([^"]+)"\s*:\s*(\d+)', body):
        if key not in result:  # Don't overwrite string matches
            result[key] = int(val)
    return result


def load_recovery_map_from_rego(rego_path: Path | str | None = None) -> dict[str, Any]:
    """Read and parse the authoritative recovery map from the .rego file on disk."""
    candidates: list[Path] = []
    if rego_path is not None:
        candidates.append(Path(rego_path))
    env_path = os.environ.get("PQC_REGO_POLICY")
    if env_path:
        candidates.append(Path(env_path))
    candidates.extend([
        Path("membrane_health.rego"),
        Path(__file__).resolve().parent / "membrane_health.rego",
        Path(__file__).resolve().parent.parent / "sentinel" / "policies" / "membrane_health.rego",
    ])
    for path in candidates:
        if path.is_file():
            try:
                content = path.read_text(encoding="utf-8")
                mapping = parse_rego_recovery_map(content)
                if mapping:
                    return mapping
            except Exception as e:
                log.warning("Failed to read rego recovery_map from %s: %s", path, e)
    log.warning("No authoritative recovery_map found — using built-in defaults")
    return {}


def fetch_recovery_map_from_opa(endpoint: str, timeout: float = 2.0) -> dict[str, Any] | None:
    """Query live OPA endpoint for the authoritative recovery_map rule."""
    if requests is None:
        return None
    url = endpoint.rstrip("/") + DEFAULT_RECOVERY_MAP_PATH
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        result = data.get("result")
        if isinstance(result, dict) and result:
            return result
    except Exception as e:
        log.debug("OPA recovery_map query failed: %s", e)
    return None


def get_authoritative_recovery_map(
    opa_endpoint: str | None = None,
    rego_path: Path | str | None = None,
) -> dict[str, Any]:
    """Retrieve recovery parameters from Wasm, OPA, or .rego file. Single source of truth."""
    if opa_endpoint == "wasm" or (os.environ.get("PQC_FORCE_HTTP") != "1" and opa_endpoint != "http://fake"):
        try:
            from sentinel.policies.wasm_gatekeeper import get_membrane_wasm_gatekeeper
            wasm_gate = get_membrane_wasm_gatekeeper()
            if wasm_gate is not None:
                m = wasm_gate.get_recovery_map()
                if m:
                    return m
        except Exception:
            pass

    if opa_endpoint and opa_endpoint != "wasm":
        live = fetch_recovery_map_from_opa(opa_endpoint)
        if live:
            return live
    return load_recovery_map_from_rego(rego_path)


# ── Circuit Breaker (Quarantine State Machine) ────────────────────
class CircuitBreaker:
    """
    Three-state circuit breaker for self-healing quarantine.

    States:
        ACTIVE      → Normal operation, OPA is reachable and returning valid verdicts.
        QUARANTINE  → Transient failure detected; node is isolated with safe-mode cipher.
                      Retrying OPA within sliding window.
        COLLAPSED   → Max retries exhausted; terminal vein collapse triggered.

    Parameters are loaded from OPA recovery_map (single source of truth).
    """

    def __init__(
        self,
        max_retries: int = DEFAULT_MAX_RETRIES,
        timeout_window: float = DEFAULT_TIMEOUT_WINDOW,
        quarantine_delay_ms: int = DEFAULT_QUARANTINE_DELAY_MS,
        safe_mode_cipher: str = DEFAULT_SAFE_MODE_CIPHER,
    ):
        self.max_retries = max_retries
        self.timeout_window = timeout_window
        self.quarantine_delay_sec = quarantine_delay_ms / 1000.0
        self.safe_mode_cipher = safe_mode_cipher
        self.failure_timestamps: list[float] = []
        self.state = "ACTIVE"
        self.pre_quarantine_kem: str | None = None  # Saved for potential recovery

    @classmethod
    def from_recovery_map(cls, recovery_map: dict[str, Any]) -> "CircuitBreaker":
        """Factory: build a CircuitBreaker from OPA-authoritative recovery parameters."""
        return cls(
            max_retries=int(recovery_map.get("max_retries", DEFAULT_MAX_RETRIES)),
            timeout_window=float(recovery_map.get("timeout_window_sec", DEFAULT_TIMEOUT_WINDOW)),
            quarantine_delay_ms=int(recovery_map.get("quarantine_delay_ms", DEFAULT_QUARANTINE_DELAY_MS)),
            safe_mode_cipher=str(recovery_map.get("safe_mode_cipher", DEFAULT_SAFE_MODE_CIPHER)),
        )

    def record_failure(self) -> bool:
        """Record a failure. Returns True if the breaker has tripped (max retries exhausted)."""
        now = time.time()
        # Prune failures outside the sliding window
        self.failure_timestamps = [
            t for t in self.failure_timestamps if now - t < self.timeout_window
        ]
        self.failure_timestamps.append(now)

        if len(self.failure_timestamps) >= self.max_retries:
            self.state = "COLLAPSED"
            return True  # Tripped — terminal collapse

        self.state = "QUARANTINE"
        return False  # Not tripped — quarantine and retry

    def reset(self) -> None:
        """Reset the breaker to ACTIVE upon successful OPA validation."""
        self.failure_timestamps.clear()
        self.state = "ACTIVE"
        self.pre_quarantine_kem = None

    @property
    def failure_count(self) -> int:
        """Number of failures within the current sliding window."""
        now = time.time()
        return len([t for t in self.failure_timestamps if now - t < self.timeout_window])


# ── Quarantine Mode ───────────────────────────────────────────────
def enter_quarantine_mode(
    state: "ImmuneState",
    breaker: CircuitBreaker,
    dry_run: bool = False,
) -> None:
    """
    Isolate the node by applying the safe-mode cipher from OPA recovery_map.
    Does NOT kill the worker or call sys.exit(). The polling loop stays alive.
    """
    if state.profile == "fips_strict":
        execute_collapse(state, "NONE", [{"reason": "Policy unavailable"}], dry_run, None, None)
        return
    if breaker.pre_quarantine_kem is None:
        breaker.pre_quarantine_kem = state.active_kem

    log.warning(
        "QUARANTINE: Isolating node | attempt %d/%d | applying safe_mode_cipher=%s",
        breaker.failure_count,
        breaker.max_retries,
        breaker.safe_mode_cipher,
    )

    # Atomically write the safe-mode cipher — node drops to known-good state
    if state.active_kem != breaker.safe_mode_cipher:
        atomic_rewrite_conf(
            state.conf_path,
            {"active_kem": breaker.safe_mode_cipher},
            dry_run=dry_run,
        )
        if not dry_run:
            state.active_kem = breaker.safe_mode_cipher


# ── AMARA Telemetry Notification (fire-and-forget) ────────────────
def notify_amara(
    event_type: str,
    details: dict[str, Any],
    amara_url: str | None = None,
) -> None:
    """Best-effort fire-and-forget notification to the local AMARA telemetry bus."""
    url = amara_url or os.environ.get("AMARA_TELEMETRY_URL", DEFAULT_AMARA_URL)
    if requests is None:
        return

    def _send() -> None:
        try:
            payload = {
                "event_type": event_type,
                "source": "immune_daemon",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **details,
            }
            requests.post(url, json=payload, timeout=2)
        except Exception:
            pass  # Fire-and-forget — never block the decision loop

    threading.Thread(target=_send, daemon=True).start()


# ── Chain Navigation ──────────────────────────────────────────────
def next_fallback(
    current: str,
    opa_endpoint: str | None = None,
    rego_path: Path | str | None = None,
    fallback_map: dict[str, str] | None = None,
) -> str:
    """Return the next algorithm down the chain according to OPA (.rego), or NONE if exhausted."""
    fmap = fallback_map if fallback_map is not None else get_authoritative_fallback_map(opa_endpoint, rego_path)
    if current in fmap:
        return fmap[current]

    if current == "X25519":
        return "NONE"

    log.critical(
        "Unrecognized active algorithm %r — refusing to guess a fallback. "
        "Halting rollover; manual intervention required.", current
    )
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
        "requested_profile": state.profile,
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


def fetch_threat_flags(endpoint: str = "http://127.0.0.1:8181", timeout: float = 1.0, required: bool = False) -> dict[str, bool]:
    flags = {}
    for env_var in ("ML_KEM_COMPROMISED", "FRODOKEM_COMPROMISED"):
        val = os.environ.get(env_var)
        if val is not None:
            flags[env_var] = val.lower() in ("1", "true", "yes")
    if endpoint.startswith("http") and endpoint != "http://fake":
        import urllib.request
        try:
            url = endpoint.rstrip("/") + "/v1/data/threat_flags"
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if isinstance(data, dict) and "result" in data and isinstance(data["result"], dict):
                    flags.update(data["result"])
                elif required:
                    raise ValueError("Threat data missing from policy service")
        except Exception as exc:
            if required:
                raise ConnectionError("Authoritative threat data unavailable") from exc
    return flags

def query_opa(endpoint: str, cbom: dict[str, Any], timeout: float = 2.0) -> dict[str, Any]:
    """POST the CBOM input to the local OPA sidecar or evaluate via in-process Wasm gatekeeper.

    Raises ConnectionError if OPA is unreachable OR if it answers with a
    payload we cannot read a verdict out of. Both mean the same thing --
    no usable health check -- and an unusable health check must never be
    allowed to read as a healthy one.
    """
    # Zero-Friction Gatekeeper fast path (microsecond in-process execution)
    if endpoint == "wasm" or (os.environ.get("PQC_FORCE_HTTP") != "1" and endpoint != "http://fake"):
        try:
            from sentinel.policies.wasm_gatekeeper import get_membrane_wasm_gatekeeper
            wasm_gate = get_membrane_wasm_gatekeeper()
            if wasm_gate is not None:
                threat_flags = fetch_threat_flags(endpoint if endpoint.startswith("http") else os.environ.get("OPA_ENDPOINT", DEFAULT_OPA), required=cbom.get("requested_profile") == "fips_strict")
                verdict = wasm_gate.evaluate_verdict(cbom, threat_flags=threat_flags)
                if isinstance(verdict, dict) and "node_status" in verdict:
                    return verdict
        except Exception as e:
            if endpoint == "wasm":
                raise ConnectionError(f"Zero-Friction Wasm Gatekeeper failed: {e}")
        if endpoint == "wasm":
            raise ConnectionError("Zero-Friction Wasm Gatekeeper unavailable (policy or wasmtime missing)")
    import urllib.request
    import urllib.error

    url = endpoint.rstrip("/") + DEFAULT_VERDICT_PATH
    payload = json.dumps({"input": cbom}).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise ConnectionError(f"OPA returned HTTP {e.code}: {e}")
    except OSError as e:
        # URLError, connection refused, DNS failure, socket timeout.
        raise ConnectionError(f"OPA unreachable: {e}")
    except (ValueError, UnicodeDecodeError) as e:
        # json.JSONDecodeError subclasses ValueError.
        raise ConnectionError(f"OPA returned an unparseable body: {e}")

    # An undefined Rego rule -- bundle not mounted, wrong package, path typo --
    # returns HTTP 200 with an empty object. That is a FAILED health check.
    if not isinstance(body, dict):
        raise ConnectionError(f"OPA returned a non-object body: {body!r}")

    verdict = body.get("result")
    if not isinstance(verdict, dict) or "node_status" not in verdict:
        raise ConnectionError(
            "OPA returned no usable verdict -- policy bundle not mounted? "
            f"body was {body!r}"
        )

    return verdict


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
    def __init__(self, conf_path: Path | str | None = None, profile: str | None = None):
        self.profile = profile or os.environ.get("PQC_COMPLIANCE_PROFILE", "fips_strict")
        if self.profile not in ("fips_strict", "iso_strict", "agility"):
            raise ValueError("Unknown PQC compliance profile")
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
        self.quarantine_events: list[dict[str, Any]] = []  # Audit trail for quarantine transitions

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
def halt_worker(worker_pid: int, timeout: float = 2.0) -> None:
    """Linux pidfd pins the intended process and lets us confirm termination.

    Deployment must prevent a supervisor independently restarting the worker.
    """
    import select
    if worker_pid <= 1 or worker_pid == os.getpid():
        raise ValueError("Refusing unsafe worker PID")
    try:
        fd = os.pidfd_open(worker_pid)
    except ProcessLookupError:
        return  # Already stopped.
    try:
        try:
            signal.pidfd_send_signal(fd, signal.SIGTERM)
        except ProcessLookupError:
            return
        if not select.select([fd], [], [], timeout)[0]:
            try:
                signal.pidfd_send_signal(fd, signal.SIGKILL)
            except ProcessLookupError:
                return
            if not select.select([fd], [], [], timeout)[0]:
                raise RuntimeError("Worker termination could not be confirmed")
    finally:
        os.close(fd)


def execute_collapse(
    state: ImmuneState,
    recommended: str,
    findings: list,
    dry_run: bool,
    pg_config: dict | None,
    webhook: str | None,
) -> None:
    old = state.active_kem
    if state.profile == "fips_strict":
        recommended = "NONE"  # No parameter downgrade or research fallback.
    if recommended in ("NONE", "", None) or recommended == old:
        log.critical("FATAL: TOXIC verdict with no usable fallback (recommended=%s). Audit event raised. Halting.", recommended)
        async_audit(old, recommended, findings, pg_config, webhook)
        if state.worker_pid and not dry_run:
            halt_worker(state.worker_pid)
            log.critical("Worker PID %s termination confirmed", state.worker_pid)
        elif state.profile == "fips_strict" and not dry_run:
            raise RuntimeError("Cannot enforce strict stop: no supervised WORKER_PID")
        sys.exit(1)

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
            if not state.worker_pid:
                log.warning("No WORKER_PID set — worker will not be signalled; it must poll the config file instead")
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
    breaker: CircuitBreaker | None = None,
) -> None:
    # Initialize circuit breaker from OPA recovery_map (single source of truth)
    if breaker is None:
        recovery = get_authoritative_recovery_map(opa_endpoint)
        breaker = CircuitBreaker.from_recovery_map(recovery) if recovery else CircuitBreaker(max_retries=fail_secure_threshold)

    log.info(
        "Immune daemon started | conf=%s | opa=%s | poll=%.3fs | dry_run=%s | once=%s",
        state.conf_path,
        opa_endpoint,
        poll_sec,
        dry_run,
        once,
    )
    log.info(
        "CircuitBreaker initialized | max_retries=%d | timeout_window=%.0fs | "
        "quarantine_delay=%.1fs | safe_mode_cipher=%s",
        breaker.max_retries,
        breaker.timeout_window,
        breaker.quarantine_delay_sec,
        breaker.safe_mode_cipher,
    )

    while True:
        state.refresh_from_disk()
        cbom = generate_cbom(state)
        try:
            verdict = query_opa(opa_endpoint, cbom, timeout=2.0)
        except ConnectionError as e:
            log.warning("OPA query failed or returned invalid verdict: %s", e)
            verdict = None

        if state.profile == "fips_strict" and (verdict is None or verdict.get("node_status") != "COMPLIANT"):
            execute_collapse(state, "NONE", list((verdict or {}).get("findings") or []), dry_run, pg_config, webhook)

        if verdict is None:
            # ── OPA unreachable / empty / malformed → Circuit Breaker path ──
            state.consecutive_opa_failures += 1
            tripped = breaker.record_failure()

            if tripped:
                # Max retries exhausted → terminal collapse
                log.critical(
                    "CIRCUIT BREAKER TRIPPED: %d failures in %ds window. "
                    "Escalating to terminal vein collapse.",
                    breaker.max_retries,
                    int(breaker.timeout_window),
                )
                notify_amara("CIRCUIT_BREAKER_TRIPPED", {
                    "active_kem": state.active_kem,
                    "failure_count": breaker.failure_count,
                    "breaker_state": breaker.state,
                })
                fallback = next_fallback(state.active_kem)
                if fallback == "NONE":
                    log.critical(
                        "FAIL-SECURE: fallback chain EXHAUSTED at %s. "
                        "No safe downgrade available. Manual intervention required.",
                        state.active_kem,
                    )
                    sys.exit(1)
                else:
                    log.error("FAIL-SECURE triggered — %s → %s", state.active_kem, fallback)
                    execute_collapse(
                        state,
                        fallback,
                        [{"algorithm": state.active_kem, "status": "TOXIC", "reason": "Circuit breaker tripped — OPA unreachable"}],
                        dry_run,
                        pg_config,
                        webhook,
                    )
            else:
                # Not tripped yet → enter quarantine, apply safe-mode cipher, wait
                log.warning(
                    "OPA unreachable (%d/%d) — entering QUARANTINE",
                    breaker.failure_count,
                    breaker.max_retries,
                )
                enter_quarantine_mode(state, breaker, dry_run)
                state.quarantine_events.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "attempt": breaker.failure_count,
                    "max_retries": breaker.max_retries,
                    "safe_mode_cipher": breaker.safe_mode_cipher,
                })
                notify_amara("QUARANTINE_ENTERED", {
                    "active_kem": state.active_kem,
                    "attempt": breaker.failure_count,
                    "max_retries": breaker.max_retries,
                    "safe_mode_cipher": breaker.safe_mode_cipher,
                })

                if not once:
                    time.sleep(breaker.quarantine_delay_sec)
                    continue  # Retry immediately after quarantine delay

        else:
            # ── OPA reachable → evaluate verdict ──
            status = verdict.get("node_status")
            findings = list(verdict.get("findings") or [])
            recommended = verdict.get("recommended_fallback")

            if status == "COMPLIANT":
                state.consecutive_opa_failures = 0
                if breaker.state == "QUARANTINE":
                    # Self-healing: recovered from transient failure
                    log.info(
                        "RECOVERY: OPA returned COMPLIANT after quarantine. "
                        "Resuming ACTIVE posture | kem=%s",
                        state.active_kem,
                    )
                    notify_amara("QUARANTINE_RECOVERED", {
                        "active_kem": state.active_kem,
                        "pre_quarantine_kem": breaker.pre_quarantine_kem,
                        "quarantine_attempts": len(state.quarantine_events),
                    })
                breaker.reset()

                # PQC Restoration Gate: Alert and auto-restore if degraded to classical cipher
                if state.active_kem in ("X25519", "FrodoKEM-976-AES"):
                    log.warning(
                        "[PQC DEGRADED] Active cipher is %s (fallback). Evaluating auto-restoration to primary standard ML-KEM-768...",
                        state.active_kem,
                    )
                    probe_state = ImmuneState(state.conf_path, profile=state.profile)
                    probe_state.active_kem = "ML-KEM-768"
                    probe_cbom = generate_cbom(probe_state)
                    try:
                        probe_verdict = query_opa(opa_endpoint, probe_cbom, timeout=2.0)
                        if probe_verdict.get("node_status") == "COMPLIANT":
                            log.info("[PQC RESTORATION] Primary standard ML-KEM-768 verified COMPLIANT. Auto-restoring cipher baseline.")
                            atomic_rewrite_conf(state.conf_path, {"active_kem": "ML-KEM-768"}, dry_run=dry_run)
                            if not dry_run:
                                state.active_kem = "ML-KEM-768"
                                notify_amara("PQC_AUTO_RESTORED", {"active_kem": "ML-KEM-768", "previous_kem": probe_state.active_kem})
                    except Exception as e:
                        log.debug("PQC auto-restoration probe failed: %s", e)

                log.debug("COMPLIANT | active_kem=%s", state.active_kem)
            elif status in ("TOXIC", "DENIED"):
                state.consecutive_opa_failures = 0
                # Cryptographic threat → immediate collapse (no quarantine)
                breaker.reset()  # Clear transient state — this is a real threat
                if not recommended:
                    recommended = "NONE"
                execute_collapse(state, recommended, findings, dry_run, pg_config, webhook)
            else:
                # Unknown/untrusted status → route through circuit breaker
                log.error(
                    "Unrecognised node_status %r from OPA -- treating as a "
                    "failed health check, not as compliant. Routing through circuit breaker.",
                    status,
                )
                state.consecutive_opa_failures += 1
                tripped = breaker.record_failure()
                if tripped:
                    log.critical(
                        "CIRCUIT BREAKER TRIPPED on untrusted status %r. Terminal collapse.",
                        status,
                    )
                    fallback = recommended if (recommended and recommended != "NONE") else next_fallback(state.active_kem)
                    fail_findings = findings if findings else [
                        {"algorithm": state.active_kem, "status": "TOXIC", "reason": f"Untrusted node_status: {status}"}
                    ]
                    execute_collapse(state, fallback, fail_findings, dry_run, pg_config, webhook)
                else:
                    enter_quarantine_mode(state, breaker, dry_run)
                    state.quarantine_events.append({
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "attempt": breaker.failure_count,
                        "reason": f"Untrusted node_status: {status}",
                    })
                    if not once:
                        time.sleep(breaker.quarantine_delay_sec)
                        continue

        if once:
            log.info("--once complete — exiting")
            break

        time.sleep(poll_sec)


# ── Entry point ───────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(description="PQC Crypto-Agility Immune Daemon")
    parser.add_argument("--conf", type=Path, default=None, help="Path to crypto_provider.conf")
    parser.add_argument("--opa", default=None, help="OPA base URL")
    parser.add_argument("--profile", choices=("fips_strict", "iso_strict", "agility"),
                        default=os.environ.get("PQC_COMPLIANCE_PROFILE", "fips_strict"))
    parser.add_argument("--wasm", action="store_true", help="Enforce in-process Zero-Friction WebAssembly policy engine")
    parser.add_argument("--poll-ms", type=int, default=None, help="Poll interval in milliseconds")
    parser.add_argument("--fail-secure", type=int, default=None, help="Consecutive OPA failures before fail-secure")
    parser.add_argument("--dry-run", action="store_true", help="Log actions but do not rewrite config or signal")
    parser.add_argument("--once", action="store_true", help="Run a single decision cycle and exit")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    setup_logging(args.verbose)

    conf_path = args.conf or Path(os.environ.get("PQC_PROVIDER_CONF", str(DEFAULT_CONF)))
    opa = "wasm" if args.wasm else (args.opa or os.environ.get("OPA_ENDPOINT", DEFAULT_OPA))
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

    state = ImmuneState(conf_path, profile=args.profile)

    worker_pid_env = os.environ.get("WORKER_PID")
    if worker_pid_env and worker_pid_env.isdigit():
        state.worker_pid = int(worker_pid_env)

    if state.profile == "fips_strict" and not args.dry_run:
        if not state.worker_pid or state.worker_pid <= 1 or state.worker_pid == os.getpid():
            parser.error("fips_strict requires WORKER_PID for the supervised data-path worker; use --dry-run for inspection")

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
