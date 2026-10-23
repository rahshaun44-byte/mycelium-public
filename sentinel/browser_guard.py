"""Browser-side guard for the QuantumFlex web UIs (amara-dashboard, qf-bot).

Protects code where it executes — the browser — rather than only at the
network edge. Two layers:

1. Hardening headers, enforced on every HTTP response (never overriding a
   header a route already set).
2. A Content-Security-Policy in REPORT-ONLY mode. Browsers run the page
   unchanged and POST each would-be violation to ``/__csp-report``, which
   appends one deduplicated JSON line per distinct violation to
   ``$QF_CSP_LOG`` (default ``<repo>/logs/csp_violations.jsonl``).

The UIs still depend on inline scripts and ``onclick=`` handlers, so the
policy cannot be enforced yet. The violation log is the inventory of what
has to move into external files before ``Content-Security-Policy`` replaces
the report-only header.
"""

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import Response

REPORT_PATH = "/__csp-report"
MAX_REPORT_BYTES = 16 * 1024
MAX_DISTINCT_VIOLATIONS = 1000

CSP_REPORT_ONLY = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data:",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'self'",
    f"report-uri {REPORT_PATH}",
])

HARDENING_HEADERS = {
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "x-frame-options": "SAMEORIGIN",
    "permissions-policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    "content-security-policy-report-only": CSP_REPORT_ONLY,
}

_REPORT_FIELDS = ("document-uri", "violated-directive", "effective-directive",
                  "blocked-uri", "source-file", "line-number", "disposition")


def _default_log_path() -> Path:
    return Path(__file__).resolve().parent.parent / "logs" / "csp_violations.jsonl"


class _SecurityHeadersMiddleware:
    """Pure ASGI middleware: adds headers to HTTP responses, ignores websockets."""

    def __init__(self, app):
        self.app = app
        self._encoded = [(k.encode("latin-1"), v.encode("latin-1"))
                         for k, v in HARDENING_HEADERS.items()]

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {k.lower() for k, _ in headers}
                headers.extend((k, v) for k, v in self._encoded if k not in present)
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)


class _ViolationLog:
    def __init__(self, app_name: str, path: Path):
        self.app_name = app_name
        self.path = path
        self._seen: set = set()
        self._lock = threading.Lock()

    def record(self, report: dict) -> None:
        fields = {k.replace("-", "_"): report.get(k) for k in _REPORT_FIELDS}
        key = (fields["violated_directive"], fields["blocked_uri"],
               fields["source_file"], fields["line_number"])
        with self._lock:
            if key in self._seen or len(self._seen) >= MAX_DISTINCT_VIOLATIONS:
                return
            self._seen.add(key)
            entry = {"utc": datetime.now(timezone.utc).isoformat(),
                     "app": self.app_name, **fields}
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            with os.fdopen(fd, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, sort_keys=True) + "\n")


def install(app: FastAPI, *, app_name: str) -> None:
    """Attach hardening headers and the report-only CSP collector to ``app``."""
    log = _ViolationLog(app_name, Path(os.environ.get("QF_CSP_LOG") or _default_log_path()))

    async def csp_report(request: Request) -> Response:
        body = await request.body()
        if len(body) > MAX_REPORT_BYTES:
            return Response(status_code=413)
        try:
            payload = json.loads(body)
        except ValueError:
            return Response(status_code=400)
        # report-uri delivers {"csp-report": {...}} with hyphenated keys.
        report = payload.get("csp-report") if isinstance(payload, dict) else None
        if isinstance(report, dict):
            log.record(report)
        return Response(status_code=204)

    app.add_api_route(REPORT_PATH, csp_report, methods=["POST"], include_in_schema=False)
    app.add_middleware(_SecurityHeadersMiddleware)
