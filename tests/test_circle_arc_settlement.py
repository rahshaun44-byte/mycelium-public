# tests/test_circle_arc_settlement.py
"""
Unit Tests for QuantumFlex Circle Arc L1 Settlement Adapter.
"""

import uuid
import pytest

from api_node.circle_usdc_settlement import (
    ARC_L1_CHAIN_CONFIG,
    build_arc_settlement_payload,
    derive_rfc4122_idempotency_key,
    scale_to_micro_usdc,
    validate_usdc_amount,
)


def test_arc_l1_chain_config_invariants():
    """Verify Arc L1 chain uses native USDC with exactly 6 decimals and paris EVM target."""
    assert ARC_L1_CHAIN_CONFIG["native_currency"]["decimals"] == 6
    assert ARC_L1_CHAIN_CONFIG["evm_target_version"] == "paris"
    assert ARC_L1_CHAIN_CONFIG["gas_token"] == "NATIVE_USDC"


def test_six_decimal_usdc_scaling_and_validation():
    """Verify floating-point USDC correctly scales to integer micro-USDC (1 USDC = 1,000,000)."""
    assert scale_to_micro_usdc(1.0) == 1_000_000
    assert scale_to_micro_usdc("25.50") == 25_500_000
    assert scale_to_micro_usdc(0.000001) == 1

    # Strict integer validation
    assert validate_usdc_amount(500_000) == 500_000

    with pytest.raises(TypeError, match="must be a strict integer"):
        validate_usdc_amount(10.5)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="cannot be negative"):
        validate_usdc_amount(-100)


def test_rfc4122_deterministic_idempotency_key_generation():
    """Verify idempotency key is a valid UUID v4 and is deterministic for identical block hashes."""
    block_hash = "0x8fa3b2c1d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1"

    key1 = derive_rfc4122_idempotency_key(block_hash, nonce=0)
    key2 = derive_rfc4122_idempotency_key(block_hash, nonce=0)
    key_different_nonce = derive_rfc4122_idempotency_key(block_hash, nonce=1)

    # Must be valid UUID v4
    parsed_uuid = uuid.UUID(key1)
    assert parsed_uuid.version == 4

    # Determinism check
    assert key1 == key2
    assert key1 != key_different_nonce


def test_build_arc_settlement_payload_success():
    """Verify full settlement payload structure is constructed correctly."""
    recipient = "0x1234567890abcdef1234567890abcdef12345678"
    block_hash = "0x9999999999abcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcd"

    payload = build_arc_settlement_payload(
        recipient_address=recipient,
        amount_micro_usdc=2_500_000,  # 2.50 USDC
        block_hash=block_hash,
        nonce=42,
    )

    assert payload["settlement"]["recipient"] == recipient
    assert payload["settlement"]["amount_micro_usdc"] == 2_500_000
    assert payload["settlement"]["amount_usdc_display"] == 2.5
    assert payload["idempotency"]["nonce"] == 42
    assert "idempotency_key" in payload["idempotency"]
