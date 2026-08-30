#!/usr/bin/env python3
"""
PQC Immune Daemon — Flight Test Harness
=======================================
Fault-injection suite for pqc-immune-daemon/immune_daemon.py.

Isolation guarantees (this harness never touches the live system):
  * Config under test is a fresh file in a tempdir. The live
    mcp_layer/crypto_provider.conf is never opened.
  * OPA is a mock HTTP server on an ephemeral port. The real sidecar on
    8181 is never contacted.
  * The child daemon is spawned with a scrubbed environment: PQC_DB_USER
    and PQC_DASHBOARD_WEBHOOK are stripped, so async_audit() takes its
    no-op path and never reaches the real Postgres or dashboard.
  * WORKER_PID, where a test needs one, points at a sacrificial sleeping
    process created for that test. No real service PID is ever signalled.

The daemon is run as a SUBPROCESS, not a thread: execute_collapse() calls
sys.exit(1) on fallback-chain exhaustion, which would tear down an
in-process runner.

Usage:
    python tools/run_pqc_flight_tests.py [-v] [--json OUT.json]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DAEMON = ROOT / "pqc-immune-daemon" / "immune_daemon.py"

VERDICT_PATH = "/v1/data/membrane/health/verdict"
FALLBACK_PATH = "/v1/data/membrane/health/fallback_map"
RECOVERY_PATH = "/v1/data/membrane/health/recovery_map"

FALLBACK_MAP = {
    "ML-KEM-512": "FrodoKEM-640-AES",
    "ML-KEM-768": "FrodoKEM-976-AES",
    "ML-KEM-1024": "FrodoKEM-1344-AES",
    "FrodoKEM-640-AES": "X25519",
    "FrodoKEM-976-AES": "X25519",
    "FrodoKEM-1344-AES": "X25519",
    "X25519": "NONE",
}
RECOVERY_MAP = {
    "max_retries": 3,
    "timeout_window_sec": 60,
    "quarantine_delay_ms": 700,   # shortened so tests run in seconds, not minutes
    "safe_mode_cipher": "FrodoKEM-976-AES",
    "quarantine_action": "isolate_and_hold",
}


# ── Mock OPA ──────────────────────────────────────────────────────
class MockOPA:
    """Programmable stand-in for the OPA sidecar.

    mode is read on every request, so a test can flip fault behaviour
    mid-flight and timestamp the moment it did.
    """

    def __init__(self):
        self.mode = "compliant"       # compliant | empty | unknown | toxic | http500
        self.toxic_fallback = "NONE"  # recommended_fallback returned when mode == toxic
        self.requests = []            # (timestamp, parsed active_kem)
        self._lock = threading.Lock()
        self._srv = None
        self._thread = None
        self.port = None

    def start(self, port: int = 0):
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass  # silence per-request stderr spam

            def _send(self, code, obj):
                body = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path.startswith(FALLBACK_PATH):
                    return self._send(200, {"result": FALLBACK_MAP})
                if self.path.startswith(RECOVERY_PATH):
                    return self._send(200, {"result": RECOVERY_MAP})
                return self._send(404, {})

            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(n) if n else b"{}"
                kem = None
                try:
                    inp = json.loads(raw).get("input", {})
                    for c in inp.get("components", []):
                        alg = (c.get("cryptoProperties", {})
                                .get("algorithmProperties", {})
                                .get("algorithm"))
                        if alg:
                            kem = alg
                            break
                except Exception:
                    pass

                with outer._lock:
                    outer.requests.append((time.monotonic(), kem))
                    mode = outer.mode
                    toxic_fb = outer.toxic_fallback

                if not self.path.startswith(VERDICT_PATH):
                    return self._send(404, {})

                if mode == "http500":
                    return self._send(500, {"error": "injected"})
                if mode == "empty":
                    # Undefined Rego rule: HTTP 200 with an empty object.
                    return self._send(200, {})
                if mode == "unknown":
                    return self._send(200, {"result": {
                        "node_status": "UNKNOWN", "findings": [],
                        "recommended_fallback": "NONE", "toxic_count": 0,
                    }})
                if mode == "toxic":
                    return self._send(200, {"result": {
                        "node_status": "TOXIC",
                        "findings": [{"algorithm": kem, "status": "TOXIC",
                                      "reason": "injected fault"}],
                        "recommended_fallback": toxic_fb,
                        "toxic_count": 1,
                    }})
                return self._send(200, {"result": {
                    "node_status": "COMPLIANT",
                    "findings": [{"algorithm": kem, "status": "COMPLIANT",
                                  "reason": "Approved"}],
                    "recommended_fallback": "NONE",
                    "toxic_count": 0,
                }})

        HTTPServer.allow_reuse_address = True
        self._srv = HTTPServer(("127.0.0.1", port), Handler)
        self.port = self._srv.server_address[1]
        self._thread = threading.Thread(target=self._srv.serve_forever, daemon=True)
        self._thread.start()
        return self

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}"

    def set(self, mode, toxic_fallback="NONE"):
        with self._lock:
            self.mode = mode
            self.toxic_fallback = toxic_fallback
        return time.monotonic()

    def stop(self):
        if self._srv:
            self._srv.shutdown()
            self._srv.server_close()
            self._srv = None


def free_port() -> int:
    """Bind and immediately release a port, so it is known-unbound."""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


# ── Daemon process wrapper with log latch ─────────────────────────
class DaemonProc:
    """Wraps the daemon subprocess and drains its log on a reader thread.

    Phases synchronise on log lines via wait_for() rather than on a
    wall-clock deadline. The daemon blocks ~2s in
    get_authoritative_recovery_map() and another ~2s on its first poll
    when OPA is unreachable, so any fixed timer is racing startup
    latency under load. Latching on the daemon's own output makes the
    assertion about behaviour rather than about scheduling luck: a slow
    machine takes longer, it does not fail.
    """

    def __init__(self, proc):
        self.proc = proc
        self.lines = []
        self._lock = threading.Lock()
        self._event = threading.Event()   # pulsed on every new line
        self._thread = threading.Thread(target=self._drain, daemon=True)
        self._thread.start()

    def _drain(self):
        try:
            for line in self.proc.stdout:
                with self._lock:
                    self.lines.append(line)
                self._event.set()
        except Exception:
            pass
        finally:
            self._event.set()

    @property
    def output(self) -> str:
        with self._lock:
            return "".join(self.lines)

    def wait_for(self, needle: str, timeout: float):
        """Block until `needle` appears in the daemon log.

        Returns (found, elapsed_seconds). Returns early with found=False
        if the daemon exits without ever emitting the line.
        """
        t0 = time.monotonic()
        while time.monotonic() - t0 < timeout:
            if needle in self.output:
                return True, time.monotonic() - t0
            if self.proc.poll() is not None:
                # Process gone: drain whatever is left, then decide.
                self._thread.join(timeout=1.0)
                return (needle in self.output), time.monotonic() - t0
            self._event.wait(0.05)
            self._event.clear()
        return (needle in self.output), time.monotonic() - t0

    # Drop-in Popen surface used by the phases
    def poll(self):
        return self.proc.poll()

    def wait(self, timeout=None):
        return self.proc.wait(timeout=timeout)

    @property
    def returncode(self):
        return self.proc.returncode

    @property
    def pid(self):
        return self.proc.pid


# ── Sandbox helpers ───────────────────────────────────────────────
def write_conf(path: Path, kem="ML-KEM-768", sig="ML-DSA-65"):
    path.write_text(
        "# crypto_provider.conf — flight test sandbox\n"
        f"active_kem={kem}\nactive_sig={sig}\n",
        encoding="utf-8",
    )


def read_kem(path: Path) -> str | None:
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("active_kem="):
                return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return None


def wait_for_kem(path: Path, want: str, timeout: float):
    """Poll the sandbox conf until active_kem == want. Returns (ok, elapsed_s)."""
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        if read_kem(path) == want:
            return True, time.monotonic() - t0
        time.sleep(0.01)
    return False, time.monotonic() - t0


def spawn_daemon(conf: Path, opa_url: str, poll_ms=100, worker_pid=None,
                 once=False, extra_env=None):
    env = dict(os.environ)
    # Scrub anything that could reach live infrastructure.
    for k in ("PQC_DB_USER", "PQC_DB_PASSWORD", "PQC_DB_HOST", "PQC_DB_NAME",
              "PQC_DB_PORT", "PQC_DASHBOARD_WEBHOOK", "AMARA_TELEMETRY_URL",
              "PQC_PROVIDER_CONF", "WORKER_PID", "OPA_ENDPOINT"):
        env.pop(k, None)
    # notify_amara() is fire-and-forget; point it at a dead port so it cannot
    # reach the real dashboard on 8000 even by default.
    env["AMARA_TELEMETRY_URL"] = f"http://127.0.0.1:{free_port()}/api/events"
    if worker_pid:
        env["WORKER_PID"] = str(worker_pid)
    if extra_env:
        env.update(extra_env)

    env["PYTHONUNBUFFERED"] = "1"   # so the log latch sees lines as they happen
    cmd = [sys.executable, str(DAEMON), "--conf", str(conf), "--opa", opa_url,
           "--poll-ms", str(poll_ms), "-v"]
    if once:
        cmd.append("--once")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace",
                            bufsize=1, env=env)
    return DaemonProc(proc)


def stop(proc, grace=3.0):
    """Terminate the daemon and return everything it logged."""
    if proc.poll() is None:
        proc.proc.terminate()
        try:
            proc.proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            proc.proc.kill()
            proc.proc.wait(timeout=grace)
    proc._thread.join(timeout=2.0)
    return proc.output


def sacrificial_worker():
    """A throwaway process that exists only to receive a SIGTERM."""
    return subprocess.Popen([sys.executable, "-c",
                             "import time\ntime.sleep(600)"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ── Log latches (exact substrings emitted by immune_daemon.py) ────
LATCH_QUARANTINE = "QUARANTINE: Isolating node"   # enter_quarantine_mode()
LATCH_RECOVERED = "Resuming ACTIVE posture"       # decision_loop() recovery leg
LATCH_RESTORE = "PQC RESTORATION"                 # upward restoration gate

# ── Test phases ───────────────────────────────────────────────────
RESULTS = []


def record(exp, name, passed, detail, metrics=None):
    RESULTS.append({"experiment": exp, "name": name,
                    "result": "PASS" if passed else "FAIL",
                    "detail": detail, "metrics": metrics or {}})
    tag = "PASS" if passed else "FAIL"
    print(f"  [{tag}] {exp}: {name}")
    if detail:
        print(f"         {detail}")
    for k, v in (metrics or {}).items():
        print(f"         {k} = {v}")


def phase_baseline(tmp):
    """Baseline: healthy OPA must produce no cipher change."""
    opa = MockOPA().start()
    conf = tmp / "baseline.conf"
    write_conf(conf)
    p = spawn_daemon(conf, opa.url, poll_ms=100)
    time.sleep(2.0)
    kem = read_kem(conf)
    alive = p.poll() is None
    stop(p)
    opa.stop()
    record("BASELINE", "COMPLIANT verdict leaves cipher untouched",
           kem == "ML-KEM-768" and alive,
           f"active_kem={kem} (expected ML-KEM-768), daemon_alive={alive}")


def phase_exp1(tmp):
    """EXP-1 / TEST 1: OPA socket unreachable -> quarantine, no worker kill."""
    conf = tmp / "exp1.conf"
    write_conf(conf)
    dead = f"http://127.0.0.1:{free_port()}"   # known-unbound
    worker = sacrificial_worker()
    p = spawn_daemon(conf, dead, poll_ms=100, worker_pid=worker.pid)

    # Latch on the daemon announcing quarantine, not on a wall-clock guess.
    latched, t_latch = p.wait_for(LATCH_QUARANTINE, timeout=60.0)
    # The config write follows the log line; give it a bounded settle window.
    ok, t_write = wait_for_kem(conf, "FrodoKEM-976-AES", timeout=10.0) if latched else (False, 0.0)

    alive = p.poll() is None
    worker_alive = worker.poll() is None
    out = stop(p)
    worker.kill(); worker.wait(timeout=5)
    record("EXP-1", "OPA unreachable -> QUARANTINE (safe-mode cipher)",
           latched and ok and alive and worker_alive,
           f"quarantine_logged={latched}, conf->FrodoKEM-976-AES={ok}, "
           f"daemon_survived={alive}, worker_NOT_killed={worker_alive}",
           {"T_spawn_to_quarantine_log_ms": round(t_latch * 1000, 1),
            "T_log_to_config_write_ms": round(t_write * 1000, 1)})
    return out


def phase_exp2a(tmp):
    """EXP-2 Case 2A: HTTP 200 with {} -> unusable verdict -> quarantine."""
    opa = MockOPA().start()
    opa.set("empty")
    conf = tmp / "exp2a.conf"
    write_conf(conf)
    p = spawn_daemon(conf, opa.url, poll_ms=100)
    ok, elapsed = wait_for_kem(conf, "FrodoKEM-976-AES", timeout=15.0)
    alive = p.poll() is None
    out = stop(p)
    opa.stop()
    saw = "no usable verdict" in out
    record("EXP-2A", "Empty {} body is NOT treated as healthy",
           ok and alive and saw,
           f"quarantined={ok}, daemon_survived={alive}, "
           f"logged_unusable_verdict={saw}",
           {"T_swap_ms": round(elapsed * 1000, 1)})


def phase_exp2b(tmp):
    """EXP-2 Case 2B: node_status UNKNOWN must never read as COMPLIANT."""
    opa = MockOPA().start()
    opa.set("unknown")
    conf = tmp / "exp2b.conf"
    write_conf(conf)
    p = spawn_daemon(conf, opa.url, poll_ms=100)
    ok, elapsed = wait_for_kem(conf, "FrodoKEM-976-AES", timeout=15.0)
    alive = p.poll() is None
    out = stop(p)
    opa.stop()
    # The critical safety property: UNKNOWN must not be silently accepted.
    not_compliant = ok or ("Unrecognised" in out or "Unrecognized" in out
                           or "UNKNOWN" in out)
    record("EXP-2B", "UNKNOWN status never treated as COMPLIANT",
           ok and alive and not_compliant,
           f"quarantined={ok}, daemon_survived={alive}, "
           f"rejected_unknown={not_compliant}",
           {"T_swap_ms": round(elapsed * 1000, 1)})


def phase_exp3(tmp):
    """EXP-3: TOXIC on ML-KEM-768 -> collapse to the mapped fallback."""
    opa = MockOPA().start()
    conf = tmp / "exp3.conf"
    write_conf(conf, kem="ML-KEM-768")
    p = spawn_daemon(conf, opa.url, poll_ms=100)
    time.sleep(1.2)                                    # settle on COMPLIANT
    t_fault = opa.set("toxic", toxic_fallback="FrodoKEM-976-AES")
    ok, _ = wait_for_kem(conf, "FrodoKEM-976-AES", timeout=15.0)
    t_swap = time.monotonic()
    alive = p.poll() is None
    stop(p)
    opa.stop()
    record("EXP-3", "TOXIC verdict collapses ML-KEM-768 -> FrodoKEM-976-AES",
           ok and alive,
           f"collapsed={ok}, daemon_survived={alive}",
           {"T_fault_to_swap_ms": round((t_swap - t_fault) * 1000, 1)})


def phase_exp4(tmp):
    """EXP-4: TOXIC at the end of the chain -> SIGTERM worker + daemon exit 1."""
    opa = MockOPA().start()
    opa.set("toxic", toxic_fallback="NONE")
    conf = tmp / "exp4.conf"
    write_conf(conf, kem="X25519")                     # chain floor
    worker = sacrificial_worker()
    p = spawn_daemon(conf, opa.url, poll_ms=100, worker_pid=worker.pid)
    try:
        rc = p.wait(timeout=15.0)
    except subprocess.TimeoutExpired:
        rc = None
    out = stop(p)
    time.sleep(1.0)
    worker_dead = worker.poll() is not None
    if not worker_dead:
        worker.kill()
    worker.wait(timeout=5)
    record("EXP-4", "Chain exhaustion halts fail-secure (exit 1 + worker SIGTERM)",
           rc == 1 and worker_dead,
           f"daemon_exit_code={rc} (expected 1), worker_terminated={worker_dead}, "
           f"logged_fatal={'FATAL' in out}")
    opa.stop()


def phase_exp5(tmp):
    """EXP-5: OPA drops, node quarantines, OPA returns -> recovery to ACTIVE.

    The daemon is pointed at a fixed port that is initially unbound. Once
    quarantine is confirmed, a mock OPA is bound to that same port and
    starts answering COMPLIANT, so the recovery leg is genuinely exercised.
    """
    conf = tmp / "exp5.conf"
    write_conf(conf, kem="ML-KEM-768")
    port = free_port()                                 # fixed, currently unbound
    p = spawn_daemon(conf, f"http://127.0.0.1:{port}", poll_ms=100)

    # Leg 1 — latch on the daemon announcing quarantine. No fixed deadline:
    # the daemon spends ~4s in startup timeouts before it can get here, and
    # that budget balloons under load right after EXP-4's process churn.
    quarantined, t_q = p.wait_for(LATCH_QUARANTINE, timeout=60.0)

    # Leg 2 — only once quarantine is confirmed, bring OPA up on that exact
    # port answering COMPLIANT. Sequencing off the latch means the recovery
    # leg can never start before the fault leg has actually landed.
    opa = MockOPA()
    opa.set("compliant")
    if quarantined:
        opa.start(port=port)
    t_restore = time.monotonic()

    recovered, t_r = (p.wait_for(LATCH_RECOVERED, timeout=60.0)
                      if quarantined else (False, 0.0))
    # The observable end state: promoted back off the safe-mode cipher.
    promoted, _ = (wait_for_kem(conf, "ML-KEM-768", timeout=15.0)
                   if recovered else (False, 0.0))

    alive = p.poll() is None
    out = stop(p)
    opa.stop()

    record("EXP-5", "OPA returns -> quarantine exits back to ACTIVE",
           quarantined and recovered and promoted and alive,
           f"entered_quarantine={quarantined}, logged_recovery={recovered}, "
           f"promoted_off_safe_mode={promoted}, daemon_alive={alive}",
           {"T_spawn_to_quarantine_ms": round(t_q * 1000, 1),
            "T_opa_return_to_recovery_ms": round(t_r * 1000, 1)})


def phase_exp6(tmp):
    """EXP-6: classical X25519 + COMPLIANT ML-KEM-768 probe -> auto-restore."""
    opa = MockOPA().start()
    opa.set("compliant")
    conf = tmp / "exp6.conf"
    write_conf(conf, kem="X25519")
    t0 = time.monotonic()
    p = spawn_daemon(conf, opa.url, poll_ms=100)
    ok, elapsed = wait_for_kem(conf, "ML-KEM-768", timeout=15.0)
    alive = p.poll() is None
    out = stop(p)
    opa.stop()
    probed = any(k == "ML-KEM-768" for _, k in opa.requests)
    record("EXP-6", "Classical X25519 auto-restores to ML-KEM-768",
           ok and alive,
           f"restored={ok}, daemon_alive={alive}, probed_ML-KEM-768={probed}, "
           f"logged_restoration={'RESTORATION' in out}",
           {"T_recover_ms": round(elapsed * 1000, 1)})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", type=Path, default=None)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    if not DAEMON.is_file():
        print(f"ERROR: daemon not found at {DAEMON}", file=sys.stderr)
        return 2

    print("=" * 68)
    print("  PQC IMMUNE DAEMON — FLIGHT TEST HARNESS")
    print("=" * 68)
    print(f"  daemon      : {DAEMON}")
    print(f"  sandbox     : tempdir (live crypto_provider.conf untouched)")
    print(f"  mock OPA    : ephemeral ports (real sidecar on 8181 untouched)")
    print("=" * 68)

    tmp = Path(tempfile.mkdtemp(prefix="pqc_flight_"))
    started = datetime.now(timezone.utc).isoformat()
    try:
        phase_baseline(tmp)
        phase_exp1(tmp)
        phase_exp2a(tmp)
        phase_exp2b(tmp)
        phase_exp3(tmp)
        phase_exp4(tmp)
        phase_exp5(tmp)
        phase_exp6(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    npass = sum(1 for r in RESULTS if r["result"] == "PASS")
    total = len(RESULTS)
    print("=" * 68)
    print(f"  RESULT: {npass}/{total} passed")
    print("=" * 68)

    if args.json:
        args.json.write_text(json.dumps({
            "started_utc": started,
            "finished_utc": datetime.now(timezone.utc).isoformat(),
            "passed": npass, "total": total, "results": RESULTS,
            "unmeasured": [
                "CPU utilization (requires psutil, not installed)",
                "RSS memory (requires psutil, not installed)",
                "T_detect / T_decision / T_response as separate values "
                "(not observable externally; reported as combined "
                "fault-to-config-write latency)",
            ],
        }, indent=2), encoding="utf-8")
        print(f"  flight trace written to {args.json}")

    return 0 if npass == total else 1


if __name__ == "__main__":
    sys.exit(main())
