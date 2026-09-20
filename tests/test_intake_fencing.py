"""Fencing tests for the intake ticket store.

Guarantees:
- Triage completion requires the live claim_token.
- A webhook retry / stale worker cannot overwrite TRIAGE_SUCCESS.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.intake_store import (  # noqa: E402
    IntakeStore,
    StaleClaimError,
    StorageValidationError,
)


class IntakeFencingTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = IntakeStore(str(Path(self._tmpdir.name) / "intake.db"))

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _ingest(self, ticket_id: str, message: str = "Walk-in cooler compressor down") -> None:
        created, _ = self.store.persist_initial_intake(
            ticket_id=ticket_id,
            idempotency_key=f"idem-{ticket_id}",
            client_name="Dino's Bistro",
            client_phone="(570) 555-0192",
            location="Market St, Wilkes-Barre, PA",
            raw_message=message,
        )
        self.assertTrue(created)

    def _complete(self, ticket_id: str, token: str, urgency: str = "CRITICAL") -> None:
        self.store.update_triage_outcome(
            ticket_id=ticket_id,
            claim_token=token,
            intake_status="TRIAGE_SUCCESS",
            urgency=urgency,
            trade_category="COMMERCIAL_REFRIGERATION",
            requires_urgent_review=True,
            incident_summary="Walk-in cooler compressor failure reported.",
            dispatch_state="PENDING_HUMAN_APPROVAL",
        )

    def test_update_without_claim_token_is_rejected(self) -> None:
        self._ingest("TCK-no-token")
        claimed, token = self.store.claim_pending_ticket("TCK-no-token")
        self.assertTrue(claimed)
        self.assertTrue(token)

        with self.assertRaises(StorageValidationError) as ctx:
            self.store.update_triage_outcome(
                ticket_id="TCK-no-token",
                claim_token=None,
                intake_status="TRIAGE_SUCCESS",
                urgency="STANDARD",
                trade_category="GENERAL",
                requires_urgent_review=False,
                incident_summary="Unfenced overwrite attempt.",
                dispatch_state="PENDING_HUMAN_APPROVAL",
            )
        self.assertIn("claim_token is required", str(ctx.exception))
        self.assertEqual(self.store.get_ticket("TCK-no-token")["intake_status"], "CLAIMED_IN_TRIAGE")

    def test_webhook_retry_cannot_clobber_completed_ticket(self) -> None:
        """n8n continueOnFail + omitted token used to overwrite TRIAGE_SUCCESS."""
        self._ingest("TCK-retry")
        claimed, token = self.store.claim_pending_ticket("TCK-retry", worker_id="n8n-first")
        self.assertTrue(claimed)
        self._complete("TCK-retry", token, urgency="CRITICAL")

        # Retry path: persist is idempotent, claim fails, update had no token.
        with self.assertRaises(StorageValidationError):
            self.store.update_triage_outcome(
                ticket_id="TCK-retry",
                claim_token=None,
                intake_status="FALLBACK_MANUAL_REVIEW",
                urgency="UNKNOWN",
                trade_category="UNKNOWN",
                requires_urgent_review=True,
                incident_summary="Automated classification unavailable. Manual review required.",
                dispatch_state="MANUAL_REVIEW_REQUIRED",
            )

        ticket = self.store.get_ticket("TCK-retry")
        self.assertEqual(ticket["intake_status"], "TRIAGE_SUCCESS")
        self.assertEqual(ticket["urgency"], "CRITICAL")
        self.assertEqual(ticket["dispatch_state"], "PENDING_HUMAN_APPROVAL")

    def test_stale_worker_cannot_overwrite_after_reclaim(self) -> None:
        self._ingest("TCK-stale")
        claimed, first_token = self.store.claim_pending_ticket(
            "TCK-stale", worker_id="worker-a", lease_seconds=0.0
        )
        self.assertTrue(claimed)

        reclaimed, second_token = self.store.claim_pending_ticket(
            "TCK-stale",
            worker_id="recovery-worker",
            allow_reclaim_abandoned=True,
        )
        self.assertTrue(reclaimed)
        self.assertNotEqual(first_token, second_token)

        self._complete("TCK-stale", second_token, urgency="HIGH")

        with self.assertRaises(StaleClaimError):
            self.store.update_triage_outcome(
                ticket_id="TCK-stale",
                claim_token=first_token,
                intake_status="TRIAGE_SUCCESS",
                urgency="STANDARD",
                trade_category="GENERAL",
                requires_urgent_review=False,
                incident_summary="Stale worker trying to rewrite completed triage.",
                dispatch_state="PENDING_HUMAN_APPROVAL",
            )

        ticket = self.store.get_ticket("TCK-stale")
        self.assertEqual(ticket["urgency"], "HIGH")
        self.assertEqual(ticket["claimed_by"], "recovery-worker")


if __name__ == "__main__":
    unittest.main()
