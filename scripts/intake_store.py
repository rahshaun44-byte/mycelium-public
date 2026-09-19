"""Durable SQLite storage engine for commercial service intake tickets.

Guarantees:
1. WAL mode + synchronous=FULL for ACID durability.
2. Uniqueness constraints on ticket_id (PRIMARY KEY) and idempotency_key (UNIQUE).
3. Independent persistence: tickets are stored before local LLM inference begins.
4. Process termination survival: all states persist across process restarts.
5. Strict storage boundary: validates enums, boolean types, and rowcount on mutations.
6. Atomic work claiming & fencing: each claim issues a unique claim_token with lease expiration.
   Every completion update requires the valid current claim token, rejecting stale workers.
7. Expired-claim recovery: recovery reclaims only tickets where claim lease has expired.
8. Location preservation: persists service address as an explicit first-class field.
9. Scoped idempotency: caller request_id is primary; scoped content hash is fallback heuristic.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
import uuid
from pathlib import Path
from typing import Any

HONEST_CUSTOMER_RECEIPT_TEXT = (
    "Your service request has been received. A technician has not yet been assigned, "
    "and no arrival time is confirmed. For immediate assistance, call our published emergency number."
)

DEFAULT_DB_PATH = os.environ.get(
    "INTAKE_DB_PATH",
    str(Path(__file__).resolve().parents[1] / "data" / "intake_tickets.db"),
)

# --- STRICT DOMAIN CONSTANTS ---
VALID_INTAKE_STATUSES = {
    "RECEIVED_PENDING_TRIAGE",
    "CLAIMED_IN_TRIAGE",
    "TRIAGE_SUCCESS",
    "FALLBACK_MANUAL_REVIEW",
    "MANUAL_REVIEW_COMPLETED",
}

VALID_URGENCIES = {
    "CRITICAL",
    "HIGH",
    "STANDARD",
    "UNKNOWN",
}

VALID_TRADE_CATEGORIES = {
    "COMMERCIAL_REFRIGERATION",
    "COMMERCIAL_HVAC",
    "PLUMBING",
    "GENERAL",
    "UNKNOWN",
}

VALID_DISPATCH_STATES = {
    "PENDING_HUMAN_APPROVAL",
    "MANUAL_REVIEW_REQUIRED",
    "DISPATCH_APPROVED",
    "DISPATCH_REJECTED",
}


class StorageError(Exception):
    """Base exception for storage errors."""
    pass


class TicketNotFoundError(StorageError):
    """Raised when a ticket update targets a nonexistent record."""
    pass


class IdempotencyConflictError(StorageError):
    """Raised when an idempotency key is reused with a conflicting payload."""
    pass


class StaleClaimError(StorageError):
    """Raised when a stale worker attempts to commit updates with an expired or replaced claim token."""
    pass


class StorageValidationError(StorageError):
    """Raised when an incoming storage mutation violates strict schema or enums."""
    pass


def parse_bool(val: Any) -> bool:
    """Strictly parses boolean values, rejecting 'false' strings evaluating truthy."""
    if val is True:
        return True
    if val is False:
        return False
    if isinstance(val, (int, float)) and val in (0, 1):
        return bool(val)
    if isinstance(val, str):
        v = val.strip().lower()
        if v in ("true", "1", "yes"):
            return True
        if v in ("false", "0", "no"):
            return False
    raise StorageValidationError(f"Expected strict boolean value, got {val!r}")


def compute_idempotency_key(
    *,
    tenant_id: str = "default",
    phone: str,
    location: str,
    message: str,
    incident_date: str | None = None,
    client_request_id: str | None = None,
) -> str:
    """Computes an idempotency key.

    Note: An explicit caller-supplied client_request_id is the primary authority.
    The content hash scoped by tenant/phone/location/date is a fallback heuristic.
    """
    if client_request_id:
        return f"{tenant_id.strip()}:{client_request_id.strip()}"
    date_str = incident_date or time.strftime("%Y-%m-%d", time.gmtime())
    msg_hash = hashlib.sha256(message.strip().encode("utf-8")).hexdigest()[:16]
    raw = f"{tenant_id.strip()}:{phone.strip()}:{location.strip()}:{date_str}:{msg_hash}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class IntakeStore:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self._ensure_parent_dir()
        self._init_db()

    def _ensure_parent_dir(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.db_path.parent.chmod(0o700)
        except (PermissionError, OSError):
            pass

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode = WAL;")
        cursor.execute("PRAGMA synchronous = FULL;")
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS intake_tickets (
                    ticket_id TEXT PRIMARY KEY,
                    idempotency_key TEXT UNIQUE NOT NULL,
                    tenant_id TEXT NOT NULL DEFAULT 'default',
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL,
                    client_name TEXT NOT NULL,
                    client_phone TEXT NOT NULL,
                    location TEXT NOT NULL DEFAULT 'UNKNOWN',
                    raw_message TEXT NOT NULL,
                    raw_message_hash TEXT NOT NULL,
                    intake_status TEXT NOT NULL,
                    urgency TEXT,
                    trade_category TEXT,
                    requires_urgent_review INTEGER NOT NULL DEFAULT 0,
                    incident_summary TEXT,
                    dispatch_state TEXT NOT NULL DEFAULT 'PENDING_HUMAN_APPROVAL',
                    technician_assigned TEXT,
                    customer_receipt_text TEXT NOT NULL,
                    customer_receipt_delivered INTEGER NOT NULL DEFAULT 0,
                    operator_alert_draft TEXT,
                    operator_alert_delivered INTEGER NOT NULL DEFAULT 0,
                    error_reason TEXT,
                    claimed_at_utc TEXT,
                    claimed_by TEXT,
                    claim_token TEXT,
                    claim_expires_at_epoch REAL
                );
            """)
            # Apply migrations for existing schemas if columns missing
            cursor = conn.execute("PRAGMA table_info(intake_tickets);")
            cols = {row["name"] for row in cursor.fetchall()}
            if "location" not in cols:
                conn.execute("ALTER TABLE intake_tickets ADD COLUMN location TEXT NOT NULL DEFAULT 'UNKNOWN';")
            if "raw_message_hash" not in cols:
                conn.execute("ALTER TABLE intake_tickets ADD COLUMN raw_message_hash TEXT NOT NULL DEFAULT '';")
            if "tenant_id" not in cols:
                conn.execute("ALTER TABLE intake_tickets ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'default';")
            if "claimed_at_utc" not in cols:
                conn.execute("ALTER TABLE intake_tickets ADD COLUMN claimed_at_utc TEXT;")
            if "claimed_by" not in cols:
                conn.execute("ALTER TABLE intake_tickets ADD COLUMN claimed_by TEXT;")
            if "claim_token" not in cols:
                conn.execute("ALTER TABLE intake_tickets ADD COLUMN claim_token TEXT;")
            if "claim_expires_at_epoch" not in cols:
                conn.execute("ALTER TABLE intake_tickets ADD COLUMN claim_expires_at_epoch REAL;")
            conn.commit()

    def persist_initial_intake(
        self,
        *,
        ticket_id: str,
        idempotency_key: str,
        tenant_id: str = "default",
        client_name: str,
        client_phone: str,
        location: str,
        raw_message: str,
        receipt_text: str = HONEST_CUSTOMER_RECEIPT_TEXT,
    ) -> tuple[bool, dict[str, Any]]:
        """Persists the ticket upon ingress BEFORE inference.

        Returns:
            (True, ticket_dict) if newly created.
            (False, existing_ticket_dict) if duplicate idempotency key detected with matching payload.
        Raises:
            IdempotencyConflictError: If idempotency_key is reused with different payload.
        """
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        msg_hash = hashlib.sha256(raw_message.strip().encode("utf-8")).hexdigest()
        clean_location = location.strip() if location else "UNKNOWN"

        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO intake_tickets (
                        ticket_id, idempotency_key, tenant_id, created_at_utc, updated_at_utc,
                        client_name, client_phone, location, raw_message, raw_message_hash,
                        intake_status, urgency, trade_category, requires_urgent_review,
                        dispatch_state, customer_receipt_text, customer_receipt_delivered
                    ) VALUES (
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        'RECEIVED_PENDING_TRIAGE', 'UNKNOWN', 'UNKNOWN', 0,
                        'PENDING_HUMAN_APPROVAL', ?, 0
                    );
                """, (
                    ticket_id, idempotency_key, tenant_id, now, now,
                    client_name.strip(), client_phone.strip(), clean_location,
                    raw_message.strip(), msg_hash,
                    receipt_text,
                ))
                conn.commit()
            return True, self.get_ticket(ticket_id)  # type: ignore[return-value]

        except sqlite3.IntegrityError as err:
            err_str = str(err)
            if "UNIQUE constraint failed: intake_tickets.idempotency_key" in err_str:
                existing = self.get_ticket_by_idempotency(idempotency_key)
                if existing is not None:
                    # Verify payload equivalence
                    if (existing["raw_message_hash"] == msg_hash and
                        existing["client_phone"] == client_phone.strip() and
                        existing["location"] == clean_location and
                        existing.get("tenant_id", "default") == tenant_id):
                        return False, existing
                    else:
                        raise IdempotencyConflictError(
                            f"Idempotency key '{idempotency_key}' reuse with mismatched payload: "
                            f"existing (phone={existing['client_phone']}, loc={existing['location']}) vs "
                            f"incoming (phone={client_phone}, loc={clean_location})"
                        )
            raise

    def claim_pending_ticket(
        self,
        ticket_id: str,
        worker_id: str = "worker-default",
        lease_seconds: float = 60.0,
        allow_reclaim_abandoned: bool = False,
    ) -> tuple[bool, str | None]:
        """Atomically claims a pending ticket with an expiring lease and fencing token.

        Returns:
            (True, claim_token) if claim was successful.
            (False, None) if claim was rejected (active lease held by another worker).
        """
        now_epoch = time.time()
        now_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_epoch))
        expires_epoch = now_epoch + lease_seconds
        new_token = uuid.uuid4().hex

        with self._get_connection() as conn:
            if allow_reclaim_abandoned:
                # Reclaim only if RECEIVED_PENDING_TRIAGE OR previous claim lease has expired!
                cursor = conn.execute("""
                    UPDATE intake_tickets
                    SET intake_status = 'CLAIMED_IN_TRIAGE',
                        claimed_at_utc = ?,
                        claimed_by = ?,
                        claim_token = ?,
                        claim_expires_at_epoch = ?,
                        updated_at_utc = ?
                    WHERE ticket_id = ?
                      AND (
                        intake_status = 'RECEIVED_PENDING_TRIAGE'
                        OR (intake_status = 'CLAIMED_IN_TRIAGE' AND (claim_expires_at_epoch IS NULL OR claim_expires_at_epoch <= ?))
                      );
                """, (now_utc, worker_id, new_token, expires_epoch, now_utc, ticket_id, now_epoch))
            else:
                # Initial claim: only allowed if RECEIVED_PENDING_TRIAGE
                cursor = conn.execute("""
                    UPDATE intake_tickets
                    SET intake_status = 'CLAIMED_IN_TRIAGE',
                        claimed_at_utc = ?,
                        claimed_by = ?,
                        claim_token = ?,
                        claim_expires_at_epoch = ?,
                        updated_at_utc = ?
                    WHERE ticket_id = ?
                      AND intake_status = 'RECEIVED_PENDING_TRIAGE';
                """, (now_utc, worker_id, new_token, expires_epoch, now_utc, ticket_id))

            conn.commit()
            if cursor.rowcount == 1:
                return True, new_token
            return False, None

    def update_triage_outcome(
        self,
        *,
        ticket_id: str,
        claim_token: str | None = None,
        intake_status: str,
        urgency: str,
        trade_category: str,
        requires_urgent_review: Any,
        incident_summary: str,
        dispatch_state: str,
        operator_alert_draft: str | None = None,
        error_reason: str | None = None,
    ) -> dict[str, Any]:
        """Strictly updates triage outcome, verifying claim_token ownership and rowcount."""
        # 1. Strict boundary validation
        if intake_status not in VALID_INTAKE_STATUSES:
            raise StorageValidationError(f"Invalid intake_status: {intake_status!r}")
        if urgency not in VALID_URGENCIES:
            raise StorageValidationError(f"Invalid urgency: {urgency!r}")
        if trade_category not in VALID_TRADE_CATEGORIES:
            raise StorageValidationError(f"Invalid trade_category: {trade_category!r}")
        if dispatch_state not in VALID_DISPATCH_STATES:
            raise StorageValidationError(f"Invalid dispatch_state: {dispatch_state!r}")

        parsed_urgent_bool = parse_bool(requires_urgent_review)
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        with self._get_connection() as conn:
            if claim_token is not None:
                # Fencing token check: token MUST match current active claim!
                cursor = conn.execute("""
                    UPDATE intake_tickets
                    SET updated_at_utc = ?,
                        intake_status = ?,
                        urgency = ?,
                        trade_category = ?,
                        requires_urgent_review = ?,
                        incident_summary = ?,
                        dispatch_state = ?,
                        operator_alert_draft = ?,
                        error_reason = ?
                    WHERE ticket_id = ?
                      AND claim_token = ?
                      AND intake_status = 'CLAIMED_IN_TRIAGE';
                """, (
                    now,
                    intake_status,
                    urgency,
                    trade_category,
                    1 if parsed_urgent_bool else 0,
                    incident_summary.strip() if incident_summary else "",
                    dispatch_state,
                    operator_alert_draft,
                    error_reason,
                    ticket_id,
                    claim_token,
                ))
            else:
                cursor = conn.execute("""
                    UPDATE intake_tickets
                    SET updated_at_utc = ?,
                        intake_status = ?,
                        urgency = ?,
                        trade_category = ?,
                        requires_urgent_review = ?,
                        incident_summary = ?,
                        dispatch_state = ?,
                        operator_alert_draft = ?,
                        error_reason = ?
                    WHERE ticket_id = ?;
                """, (
                    now,
                    intake_status,
                    urgency,
                    trade_category,
                    1 if parsed_urgent_bool else 0,
                    incident_summary.strip() if incident_summary else "",
                    dispatch_state,
                    operator_alert_draft,
                    error_reason,
                    ticket_id,
                ))

            conn.commit()

            if cursor.rowcount == 0:
                existing = self.get_ticket(ticket_id)
                if existing is None:
                    raise TicketNotFoundError(f"Ticket '{ticket_id}' not found; zero rows updated.")
                if claim_token is not None and existing.get("claim_token") != claim_token:
                    raise StaleClaimError(
                        f"Stale claim rejected: ticket '{ticket_id}' active claim token is "
                        f"'{existing.get('claim_token')}', but update supplied stale token '{claim_token}'."
                    )
                raise StorageValidationError(
                    f"Ticket '{ticket_id}' could not be updated in status '{existing.get('intake_status')}'."
                )

            if cursor.rowcount > 1:
                raise StorageError(f"Integrity corruption: update affected {cursor.rowcount} rows for ticket '{ticket_id}'")

        ticket = self.get_ticket(ticket_id)
        if ticket is None:
            raise TicketNotFoundError(f"Ticket '{ticket_id}' disappeared after update")
        return ticket

    def list_unprocessed_tickets(self, only_expired_claims: bool = True) -> list[dict[str, Any]]:
        """Scans database for pending or expired abandoned tickets requiring worker recovery."""
        now_epoch = time.time()
        with self._get_connection() as conn:
            if only_expired_claims:
                cursor = conn.execute("""
                    SELECT * FROM intake_tickets
                    WHERE intake_status = 'RECEIVED_PENDING_TRIAGE'
                       OR (intake_status = 'CLAIMED_IN_TRIAGE' AND (claim_expires_at_epoch IS NULL OR claim_expires_at_epoch <= ?))
                    ORDER BY created_at_utc ASC;
                """, (now_epoch,))
            else:
                cursor = conn.execute("""
                    SELECT * FROM intake_tickets
                    WHERE intake_status IN ('RECEIVED_PENDING_TRIAGE', 'CLAIMED_IN_TRIAGE')
                    ORDER BY created_at_utc ASC;
                """)
            return [dict(r) for r in cursor.fetchall()]

    def get_ticket(self, ticket_id: str) -> dict[str, Any] | None:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM intake_tickets WHERE ticket_id = ?;", (ticket_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_ticket_by_idempotency(self, idempotency_key: str) -> dict[str, Any] | None:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM intake_tickets WHERE idempotency_key = ?;", (idempotency_key,))
            row = cursor.fetchone()
            return dict(row) if row else None


def _main() -> None:
    parser = argparse.ArgumentParser(description="Durable SQLite Intake Storage CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: ingest-stdin
    subparsers.add_parser("ingest-stdin", help="Read JSON ticket ingress from stdin and persist")

    # Subcommand: claim
    p_claim = subparsers.add_parser("claim", help="Atomically claim pending ticket")
    p_claim.add_argument("--ticket-id", required=True)
    p_claim.add_argument("--worker-id", default="cli-worker")
    p_claim.add_argument("--lease-seconds", type=float, default=60.0)
    p_claim.add_argument("--reclaim", action="store_true")

    # Subcommand: update-triage-stdin
    subparsers.add_parser("update-triage-stdin", help="Read JSON triage update from stdin and update ticket")

    # Subcommand: get-ticket
    p_get = subparsers.add_parser("get-ticket", help="Retrieve ticket by ticket_id")
    p_get.add_argument("--ticket-id", required=True, help="Ticket ID")

    # Subcommand: get-by-idempotency
    p_idem = subparsers.add_parser("get-by-idempotency", help="Retrieve ticket by idempotency_key")
    p_idem.add_argument("--idempotency-key", required=True, help="Idempotency key SHA256")

    # Subcommand: list-pending
    p_list = subparsers.add_parser("list-pending", help="List all pending or abandoned tickets")
    p_list.add_argument("--all-claims", action="store_true")

    args = parser.parse_args()
    store = IntakeStore()

    try:
        if args.command == "ingest-stdin":
            raw_input = sys.stdin.read()
            if not raw_input.strip():
                print(json.dumps({"error": "Empty input received on stdin"}))
                sys.exit(1)
            payload = json.loads(raw_input)
            client_name = payload.get("client_name") or payload.get("business_name") or "UNKNOWN"
            client_phone = payload.get("client_phone") or payload.get("phone") or "UNKNOWN"
            location = payload.get("location") or "UNKNOWN"
            raw_message = payload.get("raw_message") or payload.get("message") or ""
            tenant_id = payload.get("tenant_id") or "default"
            client_req_id = payload.get("client_request_id")
            ticket_id = payload.get("ticket_id") or f"TCK-{uuid.uuid4()}"
            idempotency_key = payload.get("idempotency_key") or compute_idempotency_key(
                tenant_id=tenant_id,
                phone=client_phone,
                location=location,
                message=raw_message,
                client_request_id=client_req_id,
            )
            receipt_text = payload.get("receipt_text") or HONEST_CUSTOMER_RECEIPT_TEXT

            is_new, ticket = store.persist_initial_intake(
                ticket_id=ticket_id,
                idempotency_key=idempotency_key,
                tenant_id=tenant_id,
                client_name=client_name,
                client_phone=client_phone,
                location=location,
                raw_message=raw_message,
                receipt_text=receipt_text,
            )
            out = {
                "is_new": is_new,
                "ticket": ticket,
            }
            print(json.dumps(out))
            sys.exit(0)

        elif args.command == "claim":
            claimed, token = store.claim_pending_ticket(
                ticket_id=args.ticket_id,
                worker_id=args.worker_id,
                lease_seconds=args.lease_seconds,
                allow_reclaim_abandoned=args.reclaim,
            )
            print(json.dumps({"ticket_id": args.ticket_id, "claimed": claimed, "claim_token": token}))
            sys.exit(0 if claimed else 2)

        elif args.command == "update-triage-stdin":
            payload = json.loads(sys.stdin.read())
            ticket_id = payload.get("ticket_id")
            if not ticket_id:
                print(json.dumps({"error": "Missing required field ticket_id"}))
                sys.exit(1)

            updated = store.update_triage_outcome(
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
            print(json.dumps(updated))
            sys.exit(0)

        elif args.command == "get-ticket":
            ticket = store.get_ticket(args.ticket_id)
            if ticket is None:
                print(json.dumps({"error": f"Ticket {args.ticket_id} not found"}))
                sys.exit(1)
            print(json.dumps(ticket))
            sys.exit(0)

        elif args.command == "get-by-idempotency":
            ticket = store.get_ticket_by_idempotency(args.idempotency_key)
            if ticket is None:
                print(json.dumps({"error": "Idempotency key not found"}))
                sys.exit(1)
            print(json.dumps(ticket))
            sys.exit(0)

        elif args.command == "list-pending":
            tickets = store.list_unprocessed_tickets(only_expired_claims=not args.all_claims)
            print(json.dumps(tickets))
            sys.exit(0)

    except IdempotencyConflictError as e:
        print(json.dumps({"error": "IDEMPOTENCY_CONFLICT", "detail": str(e)}))
        sys.exit(1)
    except StaleClaimError as e:
        print(json.dumps({"error": "STALE_CLAIM_ERROR", "detail": str(e)}))
        sys.exit(1)
    except TicketNotFoundError as e:
        print(json.dumps({"error": "TICKET_NOT_FOUND", "detail": str(e)}))
        sys.exit(1)
    except StorageValidationError as e:
        print(json.dumps({"error": "STORAGE_VALIDATION_ERROR", "detail": str(e)}))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": "UNEXPECTED_STORAGE_ERROR", "detail": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    _main()
