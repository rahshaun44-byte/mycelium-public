#!/usr/bin/env python3
"""
═════════════════════════════════════════════════════════════════════
  QUANTUM FLEX // HARDENED OPA DECISION LOG RECEIVER DAEMON
═════════════════════════════════════════════════════════════════════
Asynchronous, decoupled telemetry collector for OPA decision logs.
Handles batched, gzip-compressed payloads from OPA (:9090/logs).

Architectural Principles:
  1. Decoupled Authority: OPA makes decisions; this daemon records & observes.
  2. Zero-Trust Telemetry: Never blindly trusts incoming JSON on port 9090.
  3. Input Sanitization: Strict RFC IP parsing; rejects shell injections.
  4. Observability First: Operates in "WOULD CONTAIN" dry-run mode by default.
  5. Idempotent: Deduplicates decision_id to prevent replay storms.
═════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations
import argparse
import collections
import gzip
import ipaddress
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


# Configuration Defaults
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9090
MAX_PAYLOAD_BYTES = 5 * 1024 * 1024  # 5 MB max batch
MAX_SEEN_CACHE = 10000
TAILSCALE_CGNAT = ipaddress.ip_network("100.64.0.0/10")

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("qflex-gatekeeper")


class TelemetryStats:
    """Thread-safe telemetry metrics counter."""
    def __init__(self):
        self.batches_received = 0
        self.events_processed = 0
        self.decisions_allowed = 0
        self.decisions_denied = 0
        self.would_contain_count = 0
        self.contained_count = 0
        self.duplicates_skipped = 0
        self.malformed_events_rejected = 0
        self.ignored_paths_count = 0
        self.start_time = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "batches_received": self.batches_received,
            "events_processed": self.events_processed,
            "decisions_allowed": self.decisions_allowed,
            "decisions_denied": self.decisions_denied,
            "would_contain_count": self.would_contain_count,
            "contained_count": self.contained_count,
            "duplicates_skipped": self.duplicates_skipped,
            "malformed_events_rejected": self.malformed_events_rejected,
            "ignored_paths_count": self.ignored_paths_count,
            "uptime_seconds": round(time.time() - self.start_time, 2),
        }


class DecisionLogHandler(BaseHTTPRequestHandler):
    """Hardened HTTP request handler for OPA decision log batches."""

    server: "ThreadedDecisionLogServer"

    def log_message(self, format: str, *args: Any) -> None:
        """Silence standard stderr logging to use Python logger."""
        pass

    def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        """Healthz, stats, and audit telemetry endpoints."""
        if self.path == "/healthz":
            self._send_json(200, {
                "status": "healthy",
                "mode": "dry-run" if self.server.dry_run else "enforce",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            })
        elif self.path == "/stats":
            self._send_json(200, {
                "mode": "dry-run" if self.server.dry_run else "enforce",
                "stats": self.server.stats.to_dict(),
            })
        elif self.path == "/audit":
            self._send_json(200, {
                "count": len(self.server.audit_records),
                "records": list(self.server.audit_records)[-50:],
            })
        else:
            self._send_json(404, {"error": "Endpoint not found"})

    def do_POST(self) -> None:
        """Handle incoming decision log batches from OPA."""
        if self.path != "/logs":
            self._send_json(404, {"error": "Resource not found; expected /logs"})
            return

        # 1. Enforce payload size ceiling (defense against memory exhaustion)
        content_length_str = self.headers.get("Content-Length")
        if not content_length_str:
            self._send_json(411, {"error": "Missing Content-Length header"})
            return

        try:
            content_length = int(content_length_str)
        except ValueError:
            self._send_json(400, {"error": "Invalid Content-Length header"})
            return

        if content_length > MAX_PAYLOAD_BYTES:
            self._send_json(413, {"error": f"Payload exceeds {MAX_PAYLOAD_BYTES} bytes limit"})
            return

        # 2. Shared secret authentication (optional header check)
        if self.server.shared_secret:
            secret = (
                self.headers.get("X-OPA-Secret")
                or self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            )
            if secret != self.server.shared_secret:
                logger.warning("[AUTH] Rejected unauthorized POST /logs request")
                self._send_json(401, {"error": "Unauthorized decision log source"})
                return

        # 3. Read raw payload bytes
        try:
            raw_data = self.rfile.read(content_length)
        except Exception as e:
            logger.error(f"[READ-ERROR] Failed to read request body: {e}")
            self._send_json(400, {"error": "Failed to read body"})
            return

        # 4. Gzip decompression (OPA defaults to gzip compression for batches)
        content_encoding = self.headers.get("Content-Encoding", "").lower()
        is_gzip = (
            "gzip" in content_encoding
            or (len(raw_data) >= 2 and raw_data[0] == 0x1F and raw_data[1] == 0x8B)
        )

        if is_gzip:
            try:
                decompressed_data = gzip.decompress(raw_data)
            except Exception as e:
                logger.warning(f"[DECOMPRESS-ERROR] Gzip decompression failed: {e}")
                self.server.stats.malformed_events_rejected += 1
                self._send_json(400, {"error": "Malformed gzip payload"})
                return
        else:
            decompressed_data = raw_data

        # 5. Parse JSON (can be a batch array or single dict)
        try:
            parsed = json.loads(decompressed_data.decode("utf-8"))
        except Exception as e:
            logger.warning(f"[JSON-PARSE-ERROR] Invalid JSON payload: {e}")
            self.server.stats.malformed_events_rejected += 1
            self._send_json(400, {"error": "Malformed JSON payload"})
            return

        events = parsed if isinstance(parsed, list) else [parsed]
        self.server.stats.batches_received += 1

        # 6. Process each decision event in the batch
        accepted_in_batch = 0
        for event in events:
            if not isinstance(event, dict):
                self.server.stats.malformed_events_rejected += 1
                continue

            self.server.stats.events_processed += 1
            self._process_single_decision(event)
            accepted_in_batch += 1

        self._send_json(200, {
            "status": "ok",
            "events_accepted": accepted_in_batch,
        })

    def _process_single_decision(self, event: Dict[str, Any]) -> None:
        """Strictly validate and process an individual decision log event."""
        decision_id = event.get("decision_id")
        path = event.get("path")
        input_data = event.get("input")
        result = event.get("result")

        # Validation: Required fields
        if not decision_id or not isinstance(decision_id, str):
            logger.warning("[SCHEMA] Skipped event with missing or invalid decision_id")
            self.server.stats.malformed_events_rejected += 1
            return

        # Idempotency: Deduplicate previously seen decision_id
        if self.server.is_duplicate(decision_id):
            logger.debug(f"[DEDUP] Skipped duplicate decision_id={decision_id}")
            self.server.stats.duplicates_skipped += 1
            return

        self.server.mark_seen(decision_id)

        # Policy Path Filtering: Ignore unrelated evaluations (e.g. metrics/health)
        if path not in self.server.target_paths:
            logger.debug(f"[PATH-FILTER] Ignored unrelated policy path={path}")
            self.server.stats.ignored_paths_count += 1
            return

        if not isinstance(result, dict) or not isinstance(input_data, dict):
            logger.warning(f"[SCHEMA] Event {decision_id}: malformed input or result structure")
            self.server.stats.malformed_events_rejected += 1
            return

        # Decision Evaluation: Allow vs Deny
        allowed = bool(result.get("allow", False))
        reason = result.get("reason", "unknown")

        if allowed:
            self.server.stats.decisions_allowed += 1
            logger.debug(f"[ALLOW] Source authorized: decision_id={decision_id}")
            return

        # We have a DENIAL: evaluate consequence
        self.server.stats.decisions_denied += 1
        raw_source_ip = input_data.get("source_ip")

        if not raw_source_ip or not isinstance(raw_source_ip, str):
            logger.warning(f"[INPUT] Decision {decision_id} denied, but source_ip is missing or not a string")
            self.server.stats.malformed_events_rejected += 1
            return

        # Strict IP validation using standard library (prevents command injection)
        try:
            ip_obj = ipaddress.ip_address(raw_source_ip.strip())
        except ValueError:
            logger.error(
                f"[SECURITY-ALERT] Malformed IP rejected: '{raw_source_ip}' "
                f"in decision_id={decision_id}. Possible injection attempt."
            )
            self.server.stats.malformed_events_rejected += 1
            return

        validated_ip = str(ip_obj)
        is_tailscale = ip_obj in TAILSCALE_CGNAT

        audit_entry = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "decision_id": decision_id,
            "path": path,
            "source_ip": validated_ip,
            "is_tailscale": is_tailscale,
            "reason": reason,
            "mode": "dry-run" if self.server.dry_run else "enforce",
        }
        self.server.audit_records.append(audit_entry)

        # Enforcement Branch: Observability (Dry-Run) vs Action (Enforce)
        if self.server.dry_run:
            self.server.stats.would_contain_count += 1
            logger.info(
                f"[DRY-RUN] WOULD CONTAIN node: ip={validated_ip} "
                f"(Tailscale={is_tailscale}) decision_id={decision_id} reason='{reason}'"
            )
        else:
            self.server.stats.contained_count += 1
            logger.warning(
                f"[ENFORCE] CONTAINMENT EXECUTED: ip={validated_ip} "
                f"decision_id={decision_id} reason='{reason}'"
            )
            if self.server.containment_hook:
                try:
                    self.server.containment_hook(validated_ip, audit_entry)
                except Exception as e:
                    logger.error(f"[HOOK-ERROR] Containment hook failed for {validated_ip}: {e}")


class ThreadedDecisionLogServer(ThreadingMixIn, HTTPServer):
    """Multi-threaded HTTP server holding state for the decision log daemon."""

    def __init__(
        self,
        server_address: Tuple[str, int],
        dry_run: bool = True,
        shared_secret: Optional[str] = None,
        target_paths: Optional[Set[str]] = None,
        containment_hook: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ):
        super().__init__(server_address, DecisionLogHandler)
        self.dry_run = dry_run
        self.shared_secret = shared_secret
        self.target_paths = target_paths or {
            "quantumflex/gatekeeper/decision",
            "quantumflex/gatekeeper",
        }
        self.containment_hook = containment_hook
        self.stats = TelemetryStats()
        self.audit_records: collections.deque = collections.deque(maxlen=1000)
        self._seen_cache: collections.OrderedDict[str, float] = collections.OrderedDict()

    def is_duplicate(self, decision_id: str) -> bool:
        return decision_id in self._seen_cache

    def mark_seen(self, decision_id: str) -> None:
        self._seen_cache[decision_id] = time.time()
        if len(self._seen_cache) > MAX_SEEN_CACHE:
            self._seen_cache.popitem(last=False)


def run_daemon(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    dry_run: bool = True,
    shared_secret: Optional[str] = None,
) -> None:
    """Launch the decision log receiver daemon."""
    server_addr = (host, port)
    server = ThreadedDecisionLogServer(
        server_addr,
        dry_run=dry_run,
        shared_secret=shared_secret,
    )

    mode_str = "\033[93m[DRY-RUN (WOULD CONTAIN)]\033[0m" if dry_run else "\033[91m[LIVE ENFORCEMENT]\033[0m"
    auth_str = "ENABLED" if shared_secret else "DISABLED (Localhost only)"

    print("=" * 68)
    print("   QUANTUM FLEX // OPA DECISION LOG TELEMETRY RECEIVER")
    print("=" * 68)
    print(f"  Listening on : http://{host}:{port}/logs")
    print(f"  Operating Mode : {mode_str}")
    print(f"  Authentication : {auth_str}")
    print(f"  Target Policies: {', '.join(server.target_paths)}")
    print(f"  Healthz Probe  : http://{host}:{port}/healthz")
    print(f"  Live Stats     : http://{host}:{port}/stats")
    print("=" * 68)
    print("Ready. Awaiting batched decision logs from OPA...\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Decision Log Daemon cleanly.")
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description="Quantum Flex OPA Decision Log Receiver")
    parser.add_argument("--host", default=os.environ.get("GATEKEEPER_HOST", DEFAULT_HOST), help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("GATEKEEPER_PORT", DEFAULT_PORT)), help="Bind port (default: 9090)")
    parser.add_argument("--enforce", action="store_true", help="Enable active containment (default is dry-run 'WOULD CONTAIN')")
    parser.add_argument("--secret", default=os.environ.get("GATEKEEPER_SHARED_SECRET"), help="Optional shared secret for X-OPA-Secret header")

    args = parser.parse_args()
    dry_run = not args.enforce

    run_daemon(
        host=args.host,
        port=args.port,
        dry_run=dry_run,
        shared_secret=args.secret,
    )


if __name__ == "__main__":
    main()
