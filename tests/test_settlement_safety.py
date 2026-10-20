import hashlib
import json
from unittest.mock import patch

from api_node.circle_usdc_settlement import QuantumFlexUSDCSettler


def proof():
    payload = json.dumps({'job_id': 'example', 'correlation': 0.9},
                         sort_keys=True, separators=(',', ':'))
    return dict(job_id='example', correlation=0.9, zero_entropy=0.0,
                canonical_payload=payload,
                block_hash=hashlib.sha256(payload.encode()).hexdigest())


def test_nonfinite_and_unbound_metrics_rejected():
    for value in (float('nan'), float('inf'), '0.9', True, 1.1, 0.95):
        assert not QuantumFlexUSDCSettler.verify_quantum_proof(dict(proof(), correlation=value))


def test_noncanonical_payload_rejected_even_with_matching_digest():
    candidate = proof()
    candidate['canonical_payload'] = json.dumps(json.loads(candidate['canonical_payload']), indent=2)
    candidate['block_hash'] = hashlib.sha256(candidate['canonical_payload'].encode()).hexdigest()
    assert not QuantumFlexUSDCSettler.verify_quantum_proof(candidate)


def test_live_cannot_fall_back_to_simulated_success_or_send_request():
    with patch('urllib.request.urlopen') as network:
        result = QuantumFlexUSDCSettler(live=True).execute_micro_settlement('recipient', '20', proof())
        assert result['status'] == 'INDETERMINATE'
        assert result['submitted'] is False
        network.assert_not_called()


def test_dry_run_explicitly_reports_no_submission():
    result = QuantumFlexUSDCSettler().execute_micro_settlement('recipient', '20', proof())
    assert result['status'] == 'PROOF_VERIFIED_DRY_RUN'
    assert result['submitted'] is False


def test_authenticated_evidence_requires_signature_and_trust_anchor():
    assert not QuantumFlexUSDCSettler.verify_authenticated_evidence({}, lambda _: True)
    assert QuantumFlexUSDCSettler.verify_authenticated_evidence(
        {'signature': 'detached-signature'}, lambda evidence: True)
    assert not QuantumFlexUSDCSettler.verify_authenticated_evidence(
        {'signature': 'detached-signature'}, lambda evidence: False)


def test_reconciliation_is_conservative_and_binds_intent():
    key = 'idem'
    confirmed = QuantumFlexUSDCSettler.reconcile_transaction(
        {'status': 'COMPLETED', 'id': 'tx-1', 'idempotencyKey': key,
         'amount': '20.00', 'destinationAddress': 'recipient'}, key, '20.00', 'recipient')
    assert confirmed == {'status': 'CONFIRMED', 'transaction_id': 'tx-1'}
    mismatch = QuantumFlexUSDCSettler.reconcile_transaction(
        {'status': 'COMPLETED', 'idempotencyKey': key, 'amount': '99',
         'destinationAddress': 'recipient'}, key, '20.00', 'recipient')
    assert mismatch['status'] == 'INDETERMINATE'
    assert QuantumFlexUSDCSettler.reconcile_transaction(
        {'status': 'PROCESSING', 'id': 'tx-2'}, key, '20.00', 'recipient')['status'] == 'PENDING'
    assert QuantumFlexUSDCSettler.reconcile_transaction(
        {'status': 'FAILED', 'error': 'declined'}, key, '20.00', 'recipient')['status'] == 'FAILED'
