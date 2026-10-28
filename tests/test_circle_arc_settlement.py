# tests/test_circle_arc_settlement.py
"""
Unit Tests for QuantumFlex Circle Arc L1 Settlement Adapter.
"""

import uuid
import pytest

from api_node.circle_usdc_settlement import (
    ARC_L1_CHAIN_CONFIG,
    ARC_USDC_ERC20_ADDRESS,
    DurableIdempotencyStore,
    InvalidStateTransitionError,
    PayloadMismatchError,
    SettlementIntentState,
    build_arc_settlement_payload,
    derive_deterministic_idempotency_key,
    generate_conforming_uuid4,
    scale_to_micro_usdc,
    scale_to_native_usdc_wei,
    validate_usdc_amount,
)


def test_arc_l1_chain_config_invariants():
    """Verify Arc mainnet chain uses native USDC (18 decimals gas, 6 decimals ERC-20) and paris EVM target."""
    assert ARC_L1_CHAIN_CONFIG["evm_chain_id"] == 5042
    assert ARC_L1_CHAIN_CONFIG["hex_chain_id"] == "0x13B2"
    assert ARC_L1_CHAIN_CONFIG["erc20_token_address"] == "0x3600000000000000000000000000000000000000"
    assert ARC_L1_CHAIN_CONFIG["native_currency"]["native_gas_decimals"] == 18
    assert ARC_L1_CHAIN_CONFIG["native_currency"]["erc20_interface_decimals"] == 6
    assert ARC_L1_CHAIN_CONFIG["evm_target_version"] == "paris"
    assert ARC_L1_CHAIN_CONFIG["gas_token"] == "NATIVE_USDC"


def test_six_decimal_usdc_scaling_and_validation():
    """Verify decimal USDC correctly scales to integer micro-USDC (6 dec) and native wei (18 dec)."""
    assert scale_to_micro_usdc(1.0) == 1_000_000
    assert scale_to_micro_usdc("25.50") == 25_500_000
    assert scale_to_micro_usdc(0.000001) == 1
    assert scale_to_native_usdc_wei(1.0) == 1_000_000_000_000_000_000

    # Strict integer validation
    assert validate_usdc_amount(500_000) == 500_000

    with pytest.raises(TypeError, match="must be a strict integer"):
        validate_usdc_amount(10.5)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="cannot be negative"):
        validate_usdc_amount(-100)


def test_conforming_uuid4_generation():
    """Verify CSPRNG-generated UUID conforms to RFC 9562 / RFC 4122 UUIDv4."""
    id1 = generate_conforming_uuid4()
    id2 = generate_conforming_uuid4()
    assert id1 != id2
    parsed = uuid.UUID(id1)
    assert parsed.version == 4
    assert parsed.variant == uuid.RFC_4122


def test_rfc9562_uuidv8_deterministic_idempotency_key_generation():
    """Verify RFC 9562 UUIDv8 custom deterministic key is standards-conforming (version 8)."""
    block_hash = "0x8fa3b2c1d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1"

    key_v8_1 = derive_deterministic_idempotency_key(block_hash, nonce=0, scheme="v8")
    key_v8_2 = derive_deterministic_idempotency_key(block_hash, nonce=0, scheme="v8")
    key_v8_diff = derive_deterministic_idempotency_key(block_hash, nonce=1, scheme="v8")

    # Standards-conforming RFC 9562 UUIDv8 check
    parsed_v8 = uuid.UUID(key_v8_1)
    assert parsed_v8.version == 8
    assert parsed_v8.variant == uuid.RFC_4122

    # Determinism check
    assert key_v8_1 == key_v8_2
    assert key_v8_1 != key_v8_diff


def _multiprocess_intent_worker(args):
    """Module-level worker for multiprocessing test."""
    db_file_str, intent_key, recipient, amount = args
    from api_node.circle_usdc_settlement import DurableIdempotencyStore
    local_store = DurableIdempotencyStore(db_file_str)
    key, is_new, _ = local_store.get_or_create(intent_key, recipient, amount)
    return key, is_new


def test_payload_mismatch_rejection(tmp_path):
    """Verify intent is immutably bound to complete economic intent fingerprint and rejects any tampering."""
    db_file = tmp_path / "mismatch_test.db"
    store = DurableIdempotencyStore(db_file)
    intent_key = "0ximmutablepayloadhash::0"

    # Register original intent with default chain/asset
    key1, is_new1, status1 = store.get_or_create(
        intent_key=intent_key,
        recipient="0x1111111111111111111111111111111111111111",
        amount_micro_usdc=10_000_000,
        chain_id="arc-l1-mainnet",
        token="USDC",
        token_address="0x0000000000000000000000000000000000000000",
        source_wallet_id="vault-alpha",
    )
    assert is_new1 is True
    assert status1 == SettlementIntentState.INTENT_PERSISTED

    # 1. Reject reuse with DIFFERENT recipient
    with pytest.raises(PayloadMismatchError, match="Idempotency collision on intent"):
        store.get_or_create(
            intent_key=intent_key,
            recipient="0x9999999999999999999999999999999999999999",
            amount_micro_usdc=10_000_000,
            source_wallet_id="vault-alpha",
        )

    # 2. Reject reuse with DIFFERENT amount
    with pytest.raises(PayloadMismatchError, match="Idempotency collision on intent"):
        store.get_or_create(
            intent_key=intent_key,
            recipient="0x1111111111111111111111111111111111111111",
            amount_micro_usdc=50_000_000,
            source_wallet_id="vault-alpha",
        )

    # 3. Reject reuse on DIFFERENT chain
    with pytest.raises(PayloadMismatchError, match="Idempotency collision on intent"):
        store.get_or_create(
            intent_key=intent_key,
            recipient="0x1111111111111111111111111111111111111111",
            amount_micro_usdc=10_000_000,
            chain_id="base-mainnet",
            source_wallet_id="vault-alpha",
        )

    # 4. Reject reuse with DIFFERENT source wallet
    with pytest.raises(PayloadMismatchError, match="Idempotency collision on intent"):
        store.get_or_create(
            intent_key=intent_key,
            recipient="0x1111111111111111111111111111111111111111",
            amount_micro_usdc=10_000_000,
            source_wallet_id="vault-beta",
        )

    # 5. Re-submission with IDENTICAL complete economic payload succeeds with same key
    key2, is_new2, status2 = store.get_or_create(
        intent_key=intent_key,
        recipient="0x1111111111111111111111111111111111111111",
        amount_micro_usdc=10_000_000,
        chain_id="arc-l1-mainnet",
        token="USDC",
        token_address="0x0000000000000000000000000000000000000000",
        source_wallet_id="vault-alpha",
    )
    assert is_new2 is False
    assert key2 == key1
    assert status2 == SettlementIntentState.INTENT_PERSISTED


def test_settlement_intent_state_transitions(tmp_path):
    """Verify formal state lifecycle transitions, intermediate states, and illegal jump rejections."""
    db_file = tmp_path / "state_test.db"
    store = DurableIdempotencyStore(db_file)
    intent_key = "0xstatetransitionhash::1"

    _, is_new, status = store.get_or_create(
        intent_key=intent_key,
        recipient="0x1234567890abcdef1234567890abcdef12345678",
        amount_micro_usdc=1_000_000,
    )
    assert is_new is True
    assert status == SettlementIntentState.INTENT_PERSISTED

    # 1. Transition INTENT_PERSISTED -> REQUEST_SUBMITTED
    store.transition_state(
        intent_key=intent_key,
        from_state=SettlementIntentState.INTENT_PERSISTED,
        to_state=SettlementIntentState.REQUEST_SUBMITTED,
        tx_hash="0xmocktxhash123",
    )
    assert store.get_intent(intent_key)["status"] == SettlementIntentState.REQUEST_SUBMITTED.value

    # 2. Reject illegal unauthorized jump: INTENT_PERSISTED -> CONFIRMED (bypassing submitted)
    with pytest.raises(InvalidStateTransitionError, match="Cannot transition intent"):
        store.transition_state(
            intent_key=intent_key,
            from_state=SettlementIntentState.INTENT_PERSISTED,
            to_state=SettlementIntentState.CONFIRMED,
        )

    # 3. Transition REQUEST_SUBMITTED -> REQUEST_ACCEPTED (gateway acknowledged)
    store.transition_state(
        intent_key=intent_key,
        from_state=SettlementIntentState.REQUEST_SUBMITTED,
        to_state=SettlementIntentState.REQUEST_ACCEPTED,
    )
    assert store.get_intent(intent_key)["status"] == SettlementIntentState.REQUEST_ACCEPTED.value

    # 4. Transition REQUEST_ACCEPTED -> PENDING (mempool / chain processing)
    store.transition_state(
        intent_key=intent_key,
        from_state=SettlementIntentState.REQUEST_ACCEPTED,
        to_state=SettlementIntentState.PENDING,
    )
    assert store.get_intent(intent_key)["status"] == SettlementIntentState.PENDING.value

    # 5. Transition PENDING -> CONFIRMED (final on-chain settlement receipt)
    store.transition_state(
        intent_key=intent_key,
        from_state=SettlementIntentState.PENDING,
        to_state=SettlementIntentState.CONFIRMED,
    )
    assert store.get_intent(intent_key)["status"] == SettlementIntentState.CONFIRMED.value

    # 6. Reject transition from terminal CONFIRMED state
    with pytest.raises(InvalidStateTransitionError, match="Illegal state transition"):
        store.transition_state(
            intent_key=intent_key,
            from_state=SettlementIntentState.CONFIRMED,
            to_state=SettlementIntentState.PENDING,
        )


def test_classify_gateway_http_response_handles_5xx_without_failure():
    """Verify payment gateway HTTP status classification fails closed and never marks 5xx as immediate failure."""
    from api_node.circle_usdc_settlement import classify_gateway_http_response

    # 2xx without payload -> REQUEST_ACCEPTED
    assert classify_gateway_http_response(200) == SettlementIntentState.REQUEST_ACCEPTED
    assert classify_gateway_http_response(201) == SettlementIntentState.REQUEST_ACCEPTED

    # 2xx with terminal completed status -> CONFIRMED
    assert classify_gateway_http_response(200, {"status": "COMPLETE"}) == SettlementIntentState.CONFIRMED
    assert classify_gateway_http_response(200, {"status": "CONFIRMED"}) == SettlementIntentState.CONFIRMED

    # 2xx with queued/pending status -> PENDING
    assert classify_gateway_http_response(200, {"status": "QUEUED"}) == SettlementIntentState.PENDING
    assert classify_gateway_http_response(202, {"status": "PROCESSING"}) == SettlementIntentState.PENDING

    # 4xx client errors -> FAILED
    assert classify_gateway_http_response(400) == SettlementIntentState.FAILED
    assert classify_gateway_http_response(403) == SettlementIntentState.FAILED
    assert classify_gateway_http_response(404) == SettlementIntentState.FAILED
    assert classify_gateway_http_response(422) == SettlementIntentState.FAILED

    # 5xx server errors / timeouts -> RECONCILIATION_REQUIRED (NOT FAILED!)
    assert classify_gateway_http_response(500) == SettlementIntentState.RECONCILIATION_REQUIRED
    assert classify_gateway_http_response(502) == SettlementIntentState.RECONCILIATION_REQUIRED
    assert classify_gateway_http_response(503) == SettlementIntentState.RECONCILIATION_REQUIRED
    assert classify_gateway_http_response(504) == SettlementIntentState.RECONCILIATION_REQUIRED


def test_durable_idempotency_store_pragma_verification(tmp_path):
    """Verify SQLite WAL and synchronous=FULL pragmas are active on live store connections."""
    import sqlite3
    db_file = tmp_path / "pragma_test.db"
    store = DurableIdempotencyStore(db_file)
    conn = store._get_connection()
    try:
        cur = conn.cursor()
        journal_mode = cur.execute("PRAGMA journal_mode").fetchone()[0]
        synchronous = cur.execute("PRAGMA synchronous").fetchone()[0]
        busy_timeout = cur.execute("PRAGMA busy_timeout").fetchone()[0]

        assert journal_mode.lower() == "wal"
        # In SQLite: 0=OFF, 1=NORMAL, 2=FULL, 3=EXTRA. synchronous=FULL returns 2.
        assert synchronous == 2
        assert busy_timeout >= 30000
    finally:
        conn.close()


def test_interrupted_request_reconciliation_recovers_same_key(tmp_path):
    """Verify interrupted settlement intent recovers persisted UUIDv4 on retry after network drop."""
    db_file = tmp_path / "interrupted_test.db"
    store = DurableIdempotencyStore(db_file)
    intent_key = "0xinterruptedblockhash::7"

    key1, is_new1, status1 = store.get_or_create(
        intent_key=intent_key,
        recipient="0x4444444444444444444444444444444444444444",
        amount_micro_usdc=5_000_000,
    )
    assert is_new1 is True
    assert status1 == SettlementIntentState.INTENT_PERSISTED

    # Dispatched to gateway
    store.transition_state(
        intent_key=intent_key,
        from_state=SettlementIntentState.INTENT_PERSISTED,
        to_state=SettlementIntentState.REQUEST_SUBMITTED,
    )

    # Gateway timed out with 504 -> transition to RECONCILIATION_REQUIRED
    store.transition_state(
        intent_key=intent_key,
        from_state=SettlementIntentState.REQUEST_SUBMITTED,
        to_state=SettlementIntentState.RECONCILIATION_REQUIRED,
        failure_reason="HTTP 504 Gateway Timeout during dispatch",
    )

    # Simulated system restart / new store instance querying the intent
    restarted_store = DurableIdempotencyStore(db_file)
    key_reconciled, is_new_retry, status_retry = restarted_store.get_or_create(
        intent_key=intent_key,
        recipient="0x4444444444444444444444444444444444444444",
        amount_micro_usdc=5_000_000,
    )

    # Must preserve exact UUIDv4 and RECONCILIATION_REQUIRED status
    assert is_new_retry is False
    assert key_reconciled == key1
    assert status_retry == SettlementIntentState.RECONCILIATION_REQUIRED
    record = restarted_store.get_intent(intent_key)
    assert "504 Gateway Timeout" in record["failure_reason"]


def test_durable_idempotency_store_multiprocess_workers(tmp_path):
    """
    Proves that separate Python OS processes racing on the exact same SQLite database
    serialize safely with synchronous=FULL and all receive the identical conforming UUIDv4.
    """
    import concurrent.futures
    import multiprocessing

    db_file = tmp_path / "multiprocess_test.db"
    intent_key = "0xmultiprocessblockhash::42"
    recipient = "0x3333333333333333333333333333333333333333"
    amount = 2_500_000

    tasks = [(str(db_file), intent_key, recipient, amount) for _ in range(8)]

    # Use fork or spawn context to execute in actual separate OS processes
    ctx = multiprocessing.get_context("spawn")
    with concurrent.futures.ProcessPoolExecutor(max_workers=4, mp_context=ctx) as executor:
        results = list(executor.map(_multiprocess_intent_worker, tasks))

    # Exactly one process created the record, all others received existing
    new_count = sum(1 for _, is_new in results if is_new)
    assert new_count == 1

    # All processes received identical conforming UUIDv4
    keys = {k for k, _ in results}
    assert len(keys) == 1
    sole_key = keys.pop()
    assert uuid.UUID(sole_key).version == 4


def test_build_arc_settlement_payload_success(tmp_path):
    """Verify full settlement payload structure is constructed with conforming UUIDv4."""
    db_file = tmp_path / "test_idempotency.db"
    store = DurableIdempotencyStore(db_file)

    recipient = "0x1234567890abcdef1234567890abcdef12345678"
    block_hash = "0x9999999999abcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcd"

    payload1 = build_arc_settlement_payload(
        recipient_address=recipient,
        amount_micro_usdc=2_500_000,  # 2.50 USDC
        block_hash=block_hash,
        nonce=42,
        store=store,
    )

    assert payload1["settlement"]["recipient"] == recipient
    assert payload1["settlement"]["amount_micro_usdc"] == 2_500_000
    assert payload1["settlement"]["amount_usdc_display"] == 2.5
    assert payload1["idempotency"]["nonce"] == 42
    assert payload1["idempotency"]["is_new"] is True

    key1 = payload1["idempotency"]["idempotency_key"]
    parsed_uuid = uuid.UUID(key1)
    assert parsed_uuid.version == 4
    assert parsed_uuid.variant == uuid.RFC_4122

    # Retry same payload -> must return exact same UUIDv4 and is_new=False
    payload2 = build_arc_settlement_payload(
        recipient_address=recipient,
        amount_micro_usdc=2_500_000,
        block_hash=block_hash,
        nonce=42,
        store=store,
    )
    assert payload2["idempotency"]["idempotency_key"] == key1
    assert payload2["idempotency"]["is_new"] is False


def test_durable_idempotency_store_lifecycle_and_restart(tmp_path):
    """
    Proves that a settlement intent receives a conforming UUIDv4, persists it,
    and returns the identical key across a simulated process crash/restart.
    """
    db_file = tmp_path / "crash_test.db"

    # Process 1 creates intent
    store1 = DurableIdempotencyStore(db_file)
    intent_key = "0xdeadbeef1234::0"
    key1, is_new1, status1 = store1.get_or_create(intent_key, "0x1111111111111111111111111111111111111111", 1_000_000)

    assert is_new1 is True
    assert status1 == SettlementIntentState.INTENT_PERSISTED
    parsed1 = uuid.UUID(key1)
    assert parsed1.version == 4
    assert parsed1.variant == uuid.RFC_4122

    # Simulate process crash / clean cold restart
    del store1

    # Process 2 boots from disk
    store2 = DurableIdempotencyStore(db_file)
    key2, is_new2, status2 = store2.get_or_create(intent_key, "0x1111111111111111111111111111111111111111", 1_000_000)

    assert is_new2 is False
    assert status2 == SettlementIntentState.INTENT_PERSISTED
    assert key2 == key1  # Exact match, proving durable retry safety


def test_durable_idempotency_store_concurrent_workers(tmp_path):
    """
    Proves that multiple concurrent worker threads racing on the exact same intent
    all resolve to the exact same UUIDv4 with zero duplicate key creation.
    """
    import concurrent.futures

    db_file = tmp_path / "concurrency_test.db"
    store = DurableIdempotencyStore(db_file)
    intent_key = "0xraceconditionblockhash::7"

    results = []

    def worker():
        local_store = DurableIdempotencyStore(db_file)
        return local_store.get_or_create(intent_key, "0x2222222222222222222222222222222222222222", 500_000)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(worker) for _ in range(16)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    # Exactly one worker got is_new=True, all others got is_new=False
    new_count = sum(1 for _, is_new, _ in results if is_new)
    assert new_count == 1

    # All 16 workers received the exact same UUIDv4
    keys = {k for k, _, _ in results}
    assert len(keys) == 1
    sole_key = keys.pop()
    assert uuid.UUID(sole_key).version == 4


def test_live_dispatch_fails_closed_on_mock_wallet_or_missing_credentials():
    """Verify that attempting live dispatch fails closed when wallet ID is a stub or credentials missing."""
    from api_node.circle_usdc_settlement import QuantumFlexUSDCSettler, LiveSettlementSecurityError

    # 1. Default mock wallet ID triggers LiveSettlementSecurityError
    settler = QuantumFlexUSDCSettler(wallet_id="mock-vault-wallet-id", live=True)
    with pytest.raises(LiveSettlementSecurityError, match="active wallet ID is an unauthenticated dry-run stub"):
        settler.dispatch_live_transfer({"recipient": "0x1111111111111111111111111111111111111111", "amount": 100})

    # 2. None / empty wallet ID triggers LiveSettlementSecurityError
    settler_empty = QuantumFlexUSDCSettler(wallet_id="", live=True)
    with pytest.raises(LiveSettlementSecurityError, match="active wallet ID is an unauthenticated dry-run stub"):
        settler_empty.dispatch_live_transfer({"recipient": "0x1111111111111111111111111111111111111111", "amount": 100})


def test_receipt_binding_validation_positive_and_negative_cases():
    """
    Verify on-chain receipt validation strictly binds chain ID, asset address,
    recipient, economic amount, idempotency key, and status.
    """
    from api_node.circle_usdc_settlement import validate_onchain_settlement_receipt, ARC_USDC_ERC20_ADDRESS

    valid_intent = {
        "chain_id": 5042,
        "token_address": ARC_USDC_ERC20_ADDRESS,
        "recipient": "0x9999999999999999999999999999999999999999",
        "amount_micro_usdc": 10_000_000,
        "idempotency_key": "11111111-2222-4333-8444-555555555555",
    }

    valid_receipt = {
        "chain_id": 5042,
        "asset_contract": ARC_USDC_ERC20_ADDRESS,
        "recipient": "0x9999999999999999999999999999999999999999",
        "amount_micro_usdc": 10_000_000,
        "idempotency_key": "11111111-2222-4333-8444-555555555555",
        "status": "CONFIRMED",
        "tx_hash": "0xabcdef1234567890",
    }

    # 1. Positive case: all fields match
    ok, msg = validate_onchain_settlement_receipt(valid_receipt, valid_intent)
    assert ok is True
    assert "successfully validated" in msg

    # 2. Negative case: chain ID mismatch
    bad_chain = dict(valid_receipt, chain_id=1)
    ok, msg = validate_onchain_settlement_receipt(bad_chain, valid_intent)
    assert ok is False
    assert "Chain ID mismatch" in msg

    # 3. Negative case: asset contract mismatch (e.g. wrong token)
    bad_asset = dict(valid_receipt, asset_contract="0x0000000000000000000000000000000000000000")
    ok, msg = validate_onchain_settlement_receipt(bad_asset, valid_intent)
    assert ok is False
    assert "Asset contract mismatch" in msg

    # 4. Negative case: recipient mismatch
    bad_recip = dict(valid_receipt, recipient="0x8888888888888888888888888888888888888888")
    ok, msg = validate_onchain_settlement_receipt(bad_recip, valid_intent)
    assert ok is False
    assert "Recipient mismatch" in msg

    # 5. Negative case: amount mismatch
    bad_amt = dict(valid_receipt, amount_micro_usdc=9_000_000)
    ok, msg = validate_onchain_settlement_receipt(bad_amt, valid_intent)
    assert ok is False
    assert "Amount mismatch" in msg

    # 6. Negative case: idempotency key mismatch
    bad_key = dict(valid_receipt, idempotency_key="99999999-9999-4999-8999-999999999999")
    ok, msg = validate_onchain_settlement_receipt(bad_key, valid_intent)
    assert ok is False
    assert "Idempotency key mismatch" in msg

    # 7. Negative case: status unconfirmed
    bad_status = dict(valid_receipt, status="PENDING")
    ok, msg = validate_onchain_settlement_receipt(bad_status, valid_intent)
    assert ok is False
    assert "Receipt status is unconfirmed" in msg

    # 8. Finality verification: block_number > finalized_block_number fails
    receipt_with_block = dict(valid_receipt, block_number=105)
    ok, msg = validate_onchain_settlement_receipt(receipt_with_block, valid_intent, finalized_block_number=100)
    assert ok is False
    assert "Transaction unfinalized" in msg

    # Finality verification: block_number <= finalized_block_number passes
    ok, msg = validate_onchain_settlement_receipt(receipt_with_block, valid_intent, finalized_block_number=110)
    assert ok is True

    # 9. Event log decoding: missing logs when required fails
    ok, msg = validate_onchain_settlement_receipt(valid_receipt, valid_intent, require_event_logs=True)
    assert ok is False
    assert "missing required event logs" in msg

    # Event log decoding: valid Transfer event passes
    target_recip_padded = "0x" + valid_intent["recipient"].replace("0x", "").lower().rjust(64, "0")
    dummy_sender_padded = "0x" + ("1" * 40).rjust(64, "0")
    valid_logs = [{
        "address": ARC_USDC_ERC20_ADDRESS,
        "topics": [
            "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
            dummy_sender_padded,
            target_recip_padded,
        ],
        "data": hex(valid_intent["amount_micro_usdc"]),
    }]
    receipt_with_logs = dict(valid_receipt, logs=valid_logs)
    ok, msg = validate_onchain_settlement_receipt(receipt_with_logs, valid_intent, require_event_logs=True)
    assert ok is True


def test_accounting_invariance_microusdc_and_arcnativewei_domain_separation():
    """
    GATE D / CORRECTION D TEST:
    Prove that 6-decimal MicroUSDC and 18-decimal ArcNativeWei represent distinct
    accounting domains, preventing silent cross-domain unit contamination.
    """
    from api_node.circle_usdc_settlement import (
        MicroUSDC,
        ArcNativeWei,
        scale_to_micro_usdc,
        scale_to_native_usdc_wei,
    )

    micro = scale_to_micro_usdc("1.50")
    wei = scale_to_native_usdc_wei("1.50")

    # Invariant: correct scaling values
    assert micro == 1_500_000
    assert wei == 1_500_000_000_000_000_000

    # Invariant: strict domain types
    assert isinstance(micro, MicroUSDC)
    assert isinstance(wei, ArcNativeWei)
    assert type(micro) is MicroUSDC
    assert type(wei) is ArcNativeWei
    assert type(micro) is not type(wei)

    # Invariant: reject negative amounts
    with pytest.raises(ValueError, match="cannot be negative"):
        MicroUSDC(-1)
    with pytest.raises(ValueError, match="cannot be negative"):
        ArcNativeWei(-1)



def test_ambiguous_gateway_outcome_reconciliation_read_only_query(tmp_path):
    """
    Simulate ambiguous gateway outcome:
    Client dispatched, but experienced a network drop / HTTP 504 before response.
    Reconciliation performs a READ-ONLY status query using the persisted idempotency key
    and confirms the transaction without re-submitting.
    """
    from api_node.circle_usdc_settlement import (
        DurableIdempotencyStore,
        reconcile_ambiguous_gateway_outcome,
        SettlementIntentState,
    )

    db_file = tmp_path / "reconciliation_ambiguous.db"
    store = DurableIdempotencyStore(db_file)

    intent_key = "0xambiguousblockhash::0"
    idempotency_key, _, _ = store.get_or_create(intent_key, "0x1111111111111111111111111111111111111111", 5_000_000)

    # Client dispatched request to gateway
    store.transition_state(
        intent_key=intent_key,
        from_state=SettlementIntentState.INTENT_PERSISTED,
        to_state=SettlementIntentState.REQUEST_SUBMITTED,
    )
    # Ambiguous outcome: network drop / HTTP 504 before client received response
    store.transition_state(
        intent_key=intent_key,
        from_state=SettlementIntentState.REQUEST_SUBMITTED,
        to_state=SettlementIntentState.RECONCILIATION_REQUIRED,
    )

    query_count = 0

    def mock_read_only_gateway_query(query_key: str):
        nonlocal query_count
        query_count += 1
        assert query_key == idempotency_key
        # The gateway processed the transaction on-chain while the client was disconnected
        return {
            "status": "CONFIRMED",
            "tx_hash": "0xconfirmedtxhashfromgateway12345",
            "idempotency_key": query_key,
        }

    # Execute reconciliation
    result = reconcile_ambiguous_gateway_outcome(
        intent_key=intent_key,
        idempotency_key=idempotency_key,
        gateway_status_provider=mock_read_only_gateway_query,
        store=store,
    )

    assert result["reconciled"] is True
    assert result["status"] == "CONFIRMED"
    assert result["tx_hash"] == "0xconfirmedtxhashfromgateway12345"
    assert query_count == 1

    # Invariant: durable store state is now terminal CONFIRMED with tx_hash recorded
    intent_record = store.get_intent(intent_key)
    assert intent_record["status"] == SettlementIntentState.CONFIRMED.value
    assert intent_record["tx_hash"] == "0xconfirmedtxhashfromgateway12345"

