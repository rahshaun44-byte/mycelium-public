#!/usr/bin/env python3
"""QuantumFlex / FinallyFungus LLC: Supervised Commercial Intake & Triage Engine.

Architectural Guarantees:
1. Decoupled immediate receipt (HTTP 202): Intake tickets are durably persisted to disk
   BEFORE any inference begins. The customer receipt is generated and returned immediately.
2. Scoped idempotency & deduplication: Keys factor tenant, client phone, location, and day bucket.
   Matching retries return existing tickets; mismatched payload reuse is strictly rejected (409).
3. Atomic work claiming: Workers atomically transition tickets from RECEIVED_PENDING_TRIAGE
   to CLAIMED_IN_TRIAGE, preventing concurrent worker races and duplicate processing.
4. Crash recovery: Abandoned or uncommitted pending tickets are discovered and processed
   upon worker restart.
5. Strict domain schema validation: Rejects extra keys, missing fields, invalid enums, and wrong types.
6. Fail-closed fallback: Model timeouts or validation errors record urgency=UNKNOWN with
   manual review required, rather than fabricating a measured severity.
7. Location preservation: Persists service address as an explicit field used across classification.
8. Zero outbound transmission: Outbound channels labeled DRAFT_NOT_SENT_OUTBOUND_DISABLED.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.intake_store import (
    HONEST_CUSTOMER_RECEIPT_TEXT,
    IdempotencyConflictError,
    IntakeStore,
    StaleClaimError,
    StorageError,
    StorageValidationError,
    TicketNotFoundError,
    compute_idempotency_key,
)


class ValidationError(ValueError):
    """Raised when model output violates strict domain schema."""
    pass


class WorkerTerminatedException(Exception):
    """Simulates worker crash/termination mid-operation before outcome commit."""
    pass


# --- 1. STRICT DOMAIN SCHEMA ---

class UrgencyLevel(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    STANDARD = "STANDARD"


class TradeCategory(str, Enum):
    COMMERCIAL_REFRIGERATION = "COMMERCIAL_REFRIGERATION"
    COMMERCIAL_HVAC = "COMMERCIAL_HVAC"
    PLUMBING = "PLUMBING"
    GENERAL = "GENERAL"


@dataclass(frozen=True)
class TriageRecommendation:
    urgency: UrgencyLevel
    trade_category: TradeCategory
    requires_urgent_review: bool
    incident_summary: str

    @classmethod
    def model_validate(cls, data: Any) -> "TriageRecommendation":
        if not isinstance(data, dict):
            raise ValidationError(f"Expected dict, got {type(data).__name__}")

        allowed_keys = {"urgency", "trade_category", "requires_urgent_review", "incident_summary"}
        extra_keys = set(data.keys()) - allowed_keys
        if extra_keys:
            raise ValidationError(f"Extra forbidden keys rejected: {extra_keys}")

        missing_keys = allowed_keys - set(data.keys())
        if missing_keys:
            raise ValidationError(f"Missing required keys: {missing_keys}")

        try:
            urgency = UrgencyLevel(data["urgency"])
        except ValueError:
            raise ValidationError(f"Invalid urgency enum: {data.get('urgency')}")

        try:
            trade_category = TradeCategory(data["trade_category"])
        except ValueError:
            raise ValidationError(f"Invalid trade_category enum: {data.get('trade_category')}")

        requires_urgent = data["requires_urgent_review"]
        if not isinstance(requires_urgent, bool):
            raise ValidationError(f"requires_urgent_review must be bool, got {type(requires_urgent).__name__}")

        summary = data["incident_summary"]
        if not isinstance(summary, str) or not (10 <= len(summary.strip()) <= 300):
            raise ValidationError("incident_summary must be a string between 10 and 300 characters")

        return cls(
            urgency=urgency,
            trade_category=trade_category,
            requires_urgent_review=requires_urgent,
            incident_summary=summary.strip(),
        )


# --- 2. LOCAL INFERENCE WITH STRICT PROMPT ---

TRIAGE_SYSTEM_PROMPT = """You are a specialized intake assistant for a commercial mechanical contractor.
Analyze this raw inbound service request and extract structured triage facts.

Raw Request:
Client: {business_name} ({location})
Contact: {phone}
Message: {message}

Output MUST be a single JSON object strictly matching this schema:
{{
  "urgency": "CRITICAL" | "HIGH" | "STANDARD",
  "trade_category": "COMMERCIAL_REFRIGERATION" | "COMMERCIAL_HVAC" | "PLUMBING" | "GENERAL",
  "requires_urgent_review": boolean,
  "incident_summary": "1 to 2 factual sentences summarizing the reported equipment failure"
}}
DO NOT include any estimated revenue or job values.
DO NOT promise arrival times or technician availability.
Return ONLY valid JSON. No explanations, no markdown fences.
"""


def evaluate_ticket_locally(
    ticket: dict[str, Any],
    *,
    endpoint: str = "http://127.0.0.1:11434/api/generate",
    model: str = "qwen2.5-coder:7b",
    timeout_seconds: float = 20.0,
) -> tuple[TriageRecommendation | None, float, str | None, dict[str, Any] | None]:
    prompt = TRIAGE_SYSTEM_PROMPT.format(
        business_name=ticket.get("client_name") or ticket.get("business_name", "Unknown"),
        location=ticket.get("location", "Unknown"),
        phone=ticket.get("client_phone") or ticket.get("phone", "Unknown"),
        message=ticket.get("raw_message") or ticket.get("message", ""),
    )

    req_body = json.dumps({
        "model": model,
        "prompt": prompt,
        "format": "json",
        "stream": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        endpoint,
        data=req_body,
        headers={"Content-Type": "application/json"},
    )

    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            raw_response_bytes = resp.read()
            elapsed = time.time() - t0
            ollama_resp = json.loads(raw_response_bytes.decode("utf-8"))
            model_output_str = ollama_resp.get("response", "")
            raw_parsed = json.loads(model_output_str)
            validated = TriageRecommendation.model_validate(raw_parsed)
            return validated, elapsed, None, raw_parsed

    except urllib.error.URLError as e:
        elapsed = time.time() - t0
        return None, elapsed, f"Transport/Timeout error: {e}", None
    except json.JSONDecodeError as e:
        elapsed = time.time() - t0
        return None, elapsed, f"Model emitted malformed JSON: {e}", None
    except ValidationError as e:
        elapsed = time.time() - t0
        return None, elapsed, f"Schema validation rejected output: {e}", None
    except Exception as e:
        elapsed = time.time() - t0
        return None, elapsed, f"Unexpected failure: {e}", None


# --- 3. INTAKE INGRESS: PERSISTENCE & IMMEDIATE 202 RECEIPT ---

def submit_intake(
    ticket_data: dict[str, Any],
    store: IntakeStore | None = None,
) -> tuple[int, dict[str, Any]]:
    """Commits ticket to disk and immediately returns an HTTP 202 Receipt.

    Returns:
        (202, receipt_dict) if newly accepted.
        (200, receipt_dict) if idempotent duplicate retry with matching payload.
        (409, error_dict) if idempotency key reused with mismatched payload.
        (500, error_dict) if storage persistence failed.
    """
    if store is None:
        store = IntakeStore()

    client_name = ticket_data.get("business_name") or ticket_data.get("client_name") or "UNKNOWN"
    client_phone = ticket_data.get("phone") or ticket_data.get("client_phone") or "UNKNOWN"
    location = ticket_data.get("location") or "UNKNOWN"
    raw_message = ticket_data.get("message") or ticket_data.get("raw_message") or ""
    tenant_id = ticket_data.get("tenant_id") or "default"

    idempotency_key = ticket_data.get("idempotency_key") or compute_idempotency_key(
        tenant_id=tenant_id,
        phone=client_phone,
        location=location,
        message=raw_message,
    )
    new_ticket_id = ticket_data.get("ticket_id") or f"TCK-{uuid.uuid4()}"

    try:
        is_new, record = store.persist_initial_intake(
            ticket_id=new_ticket_id,
            idempotency_key=idempotency_key,
            tenant_id=tenant_id,
            client_name=client_name,
            client_phone=client_phone,
            location=location,
            raw_message=raw_message,
            receipt_text=HONEST_CUSTOMER_RECEIPT_TEXT,
        )
    except IdempotencyConflictError as err:
        return 409, {
            "http_status": 409,
            "error": "IDEMPOTENCY_CONFLICT",
            "detail": str(err),
        }
    except Exception as err:
        return 500, {
            "http_status": 500,
            "error": "STORAGE_PERSISTENCE_FAILED",
            "detail": str(err),
        }

    status_code = 202 if is_new else 200
    receipt_response = {
        "http_status": status_code,
        "ticket_id": record["ticket_id"],
        "receipt_status": "ACCEPTED" if is_new else "EXISTING_TICKET_RETAINED",
        "is_duplicate_request": not is_new,
        "tenant_id": record.get("tenant_id", "default"),
        "client_name": record["client_name"],
        "client_phone": record["client_phone"],
        "location": record["location"],
        "intake_status": record["intake_status"],
        "customer_acknowledgment": {
            "channel": "SMS_DRAFT",
            "delivery_status": "DRAFT_NOT_SENT_OUTBOUND_DISABLED",
            "message_text": record["customer_receipt_text"],
        },
        "created_at_utc": record["created_at_utc"],
    }
    return status_code, receipt_response


# --- 4. ATOMIC WORKER TRIAGE & DISPATCH RECOMMENDATION ---

def claim_and_triage_ticket(
    ticket_id: str,
    store: IntakeStore | None = None,
    *,
    worker_id: str = "worker-default",
    timeout_seconds: float = 20.0,
    force_timeout: bool = False,
    simulate_crash_before_commit: bool = False,
    allow_reclaim_abandoned: bool = False,
) -> dict[str, Any]:
    """Atomically claims a persisted ticket and executes triage qualification."""
    if store is None:
        store = IntakeStore()

    # 1. Atomic claim with fencing token
    claimed, claim_token = store.claim_pending_ticket(
        ticket_id=ticket_id,
        worker_id=worker_id,
        allow_reclaim_abandoned=allow_reclaim_abandoned,
    )
    if not claimed:
        ticket = store.get_ticket(ticket_id)
        return {
            "ticket_id": ticket_id,
            "claim_status": "CLAIM_REJECTED_ALREADY_PROCESSED_OR_CLAIMED",
            "current_ticket_state": ticket,
        }

    ticket = store.get_ticket(ticket_id)
    if ticket is None:
        raise TicketNotFoundError(f"Ticket '{ticket_id}' vanished after claiming")

    client_name = ticket["client_name"]
    client_phone = ticket["client_phone"]
    location = ticket["location"]
    raw_message = ticket["raw_message"]

    # Crash recovery testing checkpoint: simulate abrupt termination mid-operation
    if simulate_crash_before_commit:
        raise WorkerTerminatedException(
            f"Worker '{worker_id}' abruptly terminated while processing ticket '{ticket_id}'"
        )

    # 2. Local model inference
    if force_timeout:
        recommendation, elapsed, error, raw_json = None, 0.001, "Simulated inference timeout", None
    else:
        recommendation, elapsed, error, raw_json = evaluate_ticket_locally(
            ticket, timeout_seconds=timeout_seconds
        )

    # 3. Derive wording from validated state (neutral vs urgent)
    if recommendation is not None:
        is_urgent = (
            recommendation.urgency in (UrgencyLevel.CRITICAL, UrgencyLevel.HIGH) or
            recommendation.requires_urgent_review
        )
        alert_prefix = "Urgent intake" if is_urgent else "Standard service intake"
        alert_draft = (
            f"[DRAFT ALERT - NOT SENT - REQUIRES HUMAN DISPATCH APPROVAL]\n"
            f"{alert_prefix}: {client_name} ({location})\n"
            f"Issue: {recommendation.incident_summary}\n"
            f"Contact: {client_phone}"
        )
        updated = store.update_triage_outcome(
            ticket_id=ticket_id,
            claim_token=claim_token,
            intake_status="TRIAGE_SUCCESS",
            urgency=recommendation.urgency.value,
            trade_category=recommendation.trade_category.value,
            requires_urgent_review=recommendation.requires_urgent_review,
            incident_summary=recommendation.incident_summary,
            dispatch_state="PENDING_HUMAN_APPROVAL",
            operator_alert_draft=alert_draft,
        )
        return {
            "ticket_id": ticket_id,
            "claim_status": "TRIAGE_COMPLETED",
            "claim_token": claim_token,
            "classification_status": "TRIAGE_SUCCESS",
            "inference_latency_seconds": round(elapsed, 2),
            "recommendation": {
                "urgency": recommendation.urgency.value,
                "trade_category": recommendation.trade_category.value,
                "requires_urgent_review": recommendation.requires_urgent_review,
                "incident_summary": recommendation.incident_summary,
            },
            "dispatch_execution": {
                "execution_state": "PENDING_HUMAN_APPROVAL",
                "technician_assigned": None,
                "arrival_confirmed": False,
                "operator_alert_draft": alert_draft,
            },
            "persisted_ticket": updated,
        }
    else:
        fallback_summary = "Automated classification unavailable. Manual review required."
        fallback_alert = (
            f"[FALLBACK ALERT - MANUAL REVIEW REQUIRED]\n"
            f"Classification failed: {error}\n"
            f"Client: {client_name} ({location}) - {client_phone}\n"
            f"Raw Message: {raw_message}"
        )
        updated = store.update_triage_outcome(
            ticket_id=ticket_id,
            claim_token=claim_token,
            intake_status="FALLBACK_MANUAL_REVIEW",
            urgency="UNKNOWN",
            trade_category="UNKNOWN",
            requires_urgent_review=True,
            incident_summary=fallback_summary,
            dispatch_state="MANUAL_REVIEW_REQUIRED",
            operator_alert_draft=fallback_alert,
            error_reason=error,
        )
        return {
            "ticket_id": ticket_id,
            "claim_status": "TRIAGE_COMPLETED_WITH_FALLBACK",
            "classification_status": "FALLBACK_MANUAL_REVIEW",
            "inference_latency_seconds": round(elapsed, 2),
            "fallback_reason": error,
            "recommendation": {
                "urgency": "UNKNOWN",
                "trade_category": "UNKNOWN",
                "requires_urgent_review": True,
                "incident_summary": fallback_summary,
            },
            "dispatch_execution": {
                "execution_state": "MANUAL_REVIEW_REQUIRED",
                "technician_assigned": None,
                "arrival_confirmed": False,
                "operator_alert_draft": fallback_alert,
            },
            "persisted_ticket": updated,
        }


# --- 5. CRASH RECOVERY SCANNER ---

def recover_and_process_pending_queue(
    store: IntakeStore | None = None,
    recovery_worker_id: str = "recovery-worker-1",
) -> list[dict[str, Any]]:
    """Recovers and processes any tickets orphaned mid-operation by worker termination."""
    if store is None:
        store = IntakeStore()

    pending = store.list_unprocessed_tickets()
    recovered_results = []
    for item in pending:
        t_id = item["ticket_id"]
        res = claim_and_triage_ticket(
            ticket_id=t_id,
            store=store,
            worker_id=recovery_worker_id,
            allow_reclaim_abandoned=True,
        )
        recovered_results.append(res)
    return recovered_results


# --- 6. END-TO-END CONVENIENCE DEMO PIPELINE ---

def process_intake_ticket(
    ticket: dict[str, Any],
    *,
    store: IntakeStore | None = None,
    timeout_seconds: float = 20.0,
    force_timeout: bool = False,
    worker_id: str = "demo-worker",
) -> dict[str, Any]:
    """Demonstrates full pipeline: immediate 202 ingress receipt, followed by worker triage."""
    if store is None:
        store = IntakeStore()

    http_code, receipt = submit_intake(ticket, store=store)
    if http_code not in (200, 202):
        return {
            "http_status": http_code,
            "receipt": receipt,
            "classification_status": "INTAKE_REJECTED",
        }

    ticket_id = receipt["ticket_id"]
    if receipt.get("is_duplicate_request") and receipt.get("intake_status") != "RECEIVED_PENDING_TRIAGE":
        existing_ticket = store.get_ticket(ticket_id)
        return {
            "ticket_id": ticket_id,
            "http_status": http_code,
            "is_duplicate_request": True,
            "deduplication_status": "EXISTING_TICKET_RETAINED",
            "intake_receipt": receipt,
            "classification_status": existing_ticket["intake_status"],
            "recommendation": {
                "urgency": existing_ticket["urgency"],
                "trade_category": existing_ticket["trade_category"],
                "requires_urgent_review": bool(existing_ticket["requires_urgent_review"]),
                "incident_summary": existing_ticket["incident_summary"],
            },
            "dispatch_execution": {
                "execution_state": existing_ticket["dispatch_state"],
                "technician_assigned": existing_ticket["technician_assigned"],
                "arrival_confirmed": False,
                "operator_alert_draft": existing_ticket["operator_alert_draft"],
            },
        }

    triage_result = claim_and_triage_ticket(
        ticket_id=ticket_id,
        store=store,
        worker_id=worker_id,
        timeout_seconds=timeout_seconds,
        force_timeout=force_timeout,
    )

    return {
        "ticket_id": ticket_id,
        "http_status": http_code,
        "is_duplicate_request": receipt.get("is_duplicate_request", False),
        "intake_receipt": receipt,
        "classification_status": triage_result["classification_status"],
        "inference_latency_seconds": triage_result.get("inference_latency_seconds", 0.0),
        "fallback_reason": triage_result.get("fallback_reason"),
        "recommendation": triage_result["recommendation"],
        "dispatch_execution": triage_result["dispatch_execution"],
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="QuantumFlex Commercial Intake & Triage Engine")
    parser.add_argument("--recover", action="store_true", help="Recover and process pending tickets in queue")
    args = parser.parse_args()

    if args.recover:
        recovered = recover_and_process_pending_queue()
        print(f"[*] Processed {len(recovered)} pending ticket(s):")
        print(json.dumps(recovered, indent=2))
    else:
        sample_ticket = {
            "business_name": "Dino's Italian Bistro (FICTIONAL TEST DATA)",
            "location": "Market St, Wilkes-Barre, PA",
            "phone": "(570) 555-0192",
            "message": "Commercial refrigeration failure at restaurant on Market St, Wilkes-Barre. Need emergency service before 6:00 AM.",
        }
        result = process_intake_ticket(sample_ticket)
        print(json.dumps(result, indent=2))
