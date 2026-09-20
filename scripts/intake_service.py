#!/usr/bin/env python3
"""QuantumFlex / FinallyFungus LLC — Loopback Structured Intake Service.

Provides a structured HTTP interface on 127.0.0.1:5680 for intake ingestion,
immediate 202 receipt delivery, atomic worker claiming, and triage state updates.
Avoids shell command string interpolation in workflow nodes.
"""
from __future__ import annotations

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.intake_store import (
    HONEST_CUSTOMER_RECEIPT_TEXT,
    IdempotencyConflictError,
    IntakeStore,
    StaleClaimError,
    StorageError,
    StorageValidationError,
    TicketNotFoundError,
)
from scripts.run_lead_triage_demo import submit_intake


class IntakeRequestHandler(BaseHTTPRequestHandler):
    store: IntakeStore = IntakeStore()

    def _send_json(self, status_code: int, data: dict[str, Any]) -> None:
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/api/v1/health":
            self._send_json(200, {"status": "ok", "service": "quantumflex-intake-service"})
            return

        if path.startswith("/api/v1/ticket/"):
            ticket_id = path[len("/api/v1/ticket/"):]
            ticket = self.store.get_ticket(ticket_id)
            if ticket is None:
                self._send_json(404, {"error": "TICKET_NOT_FOUND", "ticket_id": ticket_id})
            else:
                self._send_json(200, ticket)
            return

        if path == "/api/v1/pending":
            tickets = self.store.list_unprocessed_tickets()
            self._send_json(200, {"pending_tickets": tickets, "count": len(tickets)})
            return

        self._send_json(404, {"error": "NOT_FOUND", "path": self.path})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        try:
            content_len = int(self.headers.get("Content-Length", 0))
            if content_len == 0:
                self._send_json(400, {"error": "EMPTY_PAYLOAD", "detail": "Missing request body"})
                return

            raw_body = self.rfile.read(content_len).decode("utf-8")
            payload = json.loads(raw_body)
        except json.JSONDecodeError as err:
            self._send_json(400, {"error": "INVALID_JSON", "detail": str(err)})
            return
        except Exception as err:
            self._send_json(400, {"error": "BAD_REQUEST", "detail": str(err)})
            return

        # 1. Ingest Endpoint (Returns immediate 202 Receipt)
        if path == "/api/v1/intake":
            status_code, receipt = submit_intake(payload, store=self.store)
            self._send_json(status_code, receipt)
            return

        # 2. Update Triage Outcome Endpoint
        if path == "/api/v1/update-triage":
            ticket_id = payload.get("ticket_id")
            if not ticket_id:
                self._send_json(400, {"error": "MISSING_TICKET_ID"})
                return

            if not payload.get("claim_token"):
                self._send_json(400, {
                    "error": "MISSING_CLAIM_TOKEN",
                    "detail": "Triage updates require the claim_token issued by /api/v1/claim.",
                })
                return

            try:
                updated = self.store.update_triage_outcome(
                    ticket_id=ticket_id,
                    claim_token=payload.get("claim_token"),
                    intake_status=payload.get("intake_status", "TRIAGE_SUCCESS"),
                    urgency=payload.get("urgency", "UNKNOWN"),
                    trade_category=payload.get("trade_category", "UNKNOWN"),
                    requires_urgent_review=payload.get("requires_urgent_review", False),
                    incident_summary=payload.get("incident_summary", ""),
                    dispatch_state=payload.get("dispatch_state", "PENDING_HUMAN_APPROVAL"),
                    operator_alert_draft=payload.get("operator_alert_draft"),
                    error_reason=payload.get("error_reason"),
                )
                self._send_json(200, updated)
            except StaleClaimError as err:
                self._send_json(409, {"error": "STALE_CLAIM_ERROR", "detail": str(err)})
            except TicketNotFoundError as err:
                self._send_json(404, {"error": "TICKET_NOT_FOUND", "detail": str(err)})
            except StorageValidationError as err:
                self._send_json(400, {"error": "STORAGE_VALIDATION_ERROR", "detail": str(err)})
            except Exception as err:
                self._send_json(500, {"error": "UPDATE_FAILED", "detail": str(err)})
            return

        # 3. Claim Pending Ticket Endpoint
        if path == "/api/v1/claim":
            ticket_id = payload.get("ticket_id")
            worker_id = payload.get("worker_id", "worker-default")
            lease_seconds = float(payload.get("lease_seconds", 60.0))
            reclaim = bool(payload.get("reclaim", False))
            if not ticket_id:
                self._send_json(400, {"error": "MISSING_TICKET_ID"})
                return

            claimed, claim_token = self.store.claim_pending_ticket(
                ticket_id=ticket_id,
                worker_id=worker_id,
                lease_seconds=lease_seconds,
                allow_reclaim_abandoned=reclaim,
            )
            code = 200 if claimed else 409
            self._send_json(code, {
                "ticket_id": ticket_id,
                "claimed": claimed,
                "claim_token": claim_token,
                "worker_id": worker_id
            })
            return

        self._send_json(404, {"error": "NOT_FOUND", "path": self.path})

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress noisy standard logging during unit tests unless env var set
        if os.environ.get("INTAKE_SERVICE_DEBUG"):
            sys.stderr.write(f"[IntakeService] {format % args}\n")


def create_server(host: str = "127.0.0.1", port: int = 5680) -> HTTPServer:
    return HTTPServer((host, port), IntakeRequestHandler)


if __name__ == "__main__":
    host = os.environ.get("INTAKE_HOST", "127.0.0.1")
    port = int(os.environ.get("INTAKE_PORT", 5680))
    server = create_server(host, port)
    print(f"[*] Intake Service listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Shutting down Intake Service...")
        server.server_close()
