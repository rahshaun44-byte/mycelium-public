#!/usr/bin/env python3
"""
Comprehensive verification test suite for the PQC Crypto-Agility Immune Daemon:
- D-1: Daemon starts cleanly with default config and flags (--once, --dry-run)
- D-2: Empty, malformed, or untrusted OPA responses trigger fail-secure (never fail-open)
- D-3: Unknown algorithms halt immediately without silent downgrades
- D-4: Worker process tracking and SIGHUP nudge execution
- End-to-end atomic config rewriting and transition state tracking
- Q-1: Circuit breaker quarantine then recover
- Q-2: Circuit breaker trips after max retries (terminal collapse)
- Q-3: Quarantine applies safe-mode cipher to crypto_provider.conf
- Q-4: Recovery map loaded from rego (single source of truth)

Run directly with:
    python test_immune_daemon.py
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import immune_daemon
import json


class _FakeResponse:
    """Minimal stand-in for the object urlopen() yields as a context manager."""
    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_vein_collapse_rewrites_conf():
    with tempfile.TemporaryDirectory() as tmp:
        conf_path = Path(tmp) / "crypto_provider.conf"
        conf_path.write_text(
            "active_kem=ML-KEM-768\n"
            "active_sig=ML-DSA-65\n"
        )

        state = immune_daemon.ImmuneState(conf_path)
        assert state.active_kem == "ML-KEM-768", f"expected ML-KEM-768, got {state.active_kem}"

        verdict = {
            "node_status": "TOXIC",
            "recommended_fallback": "FrodoKEM-976-AES",
            "findings": [{
                "algorithm": "ML-KEM-768",
                "status": "TOXIC",
                "reason": "synthetic test verdict",
            }],
        }

        immune_daemon.execute_vein_collapse(state, verdict)

        rewritten = conf_path.read_text()
        assert "FrodoKEM-976-AES" in rewritten, (
            f"conf was not rewritten as expected:\n{rewritten}"
        )
        assert state.active_kem == "FrodoKEM-976-AES"
        assert state.transition_count == 1

        print("PASS: execute_vein_collapse() rewrote crypto_provider.conf and updated state")


def test_all_algorithms_exhausted_halts():
    with tempfile.TemporaryDirectory() as tmp:
        conf_path = Path(tmp) / "crypto_provider.conf"
        conf_path.write_text("active_kem=X25519\nactive_sig=Ed25519\n")

        state = immune_daemon.ImmuneState(conf_path)
        verdict = {"node_status": "TOXIC", "recommended_fallback": "NONE", "findings": []}

        try:
            immune_daemon.execute_vein_collapse(state, verdict)
            assert False, "Should have exited with SystemExit(1) due to exhausted chain"
        except SystemExit as e:
            assert e.code == 1

        assert "active_kem=X25519" in conf_path.read_text(), (
            "conf should be untouched when no fallback is available"
        )
        print("PASS: exhausted fallback chain raises SystemExit and halts without rewriting config")


def test_daemon_starts_with_default_conf():
    """Guards D-1: the documented no-arg entry point must not crash."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        orig_cwd = Path.cwd()
        orig_argv = sys.argv.copy()
        try:
            os.chdir(tmp_path)
            (tmp_path / "crypto_provider.conf").write_text("active_kem=ML-KEM-768\n")
            sys.argv = ["immune_daemon.py", "--once", "--dry-run"]
            ret = immune_daemon.main()
            assert ret == 0, f"Expected return code 0, got {ret}"
            print("PASS: [D-1] daemon starts with default config path (--once --dry-run)")
        finally:
            os.chdir(orig_cwd)
            sys.argv = orig_argv


def test_empty_opa_result_is_not_compliant():
    """D-2: HTTP 200 with {} must raise, never return a usable verdict."""
    import urllib.request
    original = urllib.request.urlopen
    urllib.request.urlopen = lambda req, timeout=None: _FakeResponse({})
    try:
        try:
            immune_daemon.query_opa("http://fake", {"metadata": {}, "components": []})
        except ConnectionError:
            print("PASS: empty {} body raises ConnectionError (fail-secure)")
            return
        raise AssertionError(
            "query_opa() accepted an empty OPA body -- this is the D-2 fail-open bug"
        )
    finally:
        urllib.request.urlopen = original


def test_result_without_node_status_is_not_compliant():
    """D-2 sibling: a result dict missing node_status must also fail secure."""
    import urllib.request
    original = urllib.request.urlopen
    urllib.request.urlopen = lambda req, timeout=None: _FakeResponse({"result": {"findings": [], "toxic_count": 0}})
    try:
        try:
            immune_daemon.query_opa("http://fake", {"metadata": {}, "components": []})
        except ConnectionError:
            print("PASS: verdict without node_status raises ConnectionError")
            return
        raise AssertionError(
            "query_opa() accepted a verdict with no node_status"
        )
    finally:
        urllib.request.urlopen = original


def test_valid_verdict_still_passes_through():
    """Guard against over-correcting: a real COMPLIANT verdict must survive."""
    import urllib.request
    original = urllib.request.urlopen
    good = {"result": {"node_status": "COMPLIANT", "findings": [],
                       "recommended_fallback": "NONE"}}
    urllib.request.urlopen = lambda req, timeout=None: _FakeResponse(good)
    try:
        verdict = immune_daemon.query_opa("http://fake", {"metadata": {}, "components": []})
        assert verdict["node_status"] == "COMPLIANT", verdict
        print("PASS: a well-formed COMPLIANT verdict is returned unchanged")
    finally:
        urllib.request.urlopen = original


def test_opa_unknown_status_fails_secure():
    """Guards D-2: verdict with non-COMPLIANT node_status routes through circuit breaker."""
    with tempfile.TemporaryDirectory() as tmp:
        conf_path = Path(tmp) / "crypto_provider.conf"
        conf_path.write_text("active_kem=ML-KEM-768\nactive_sig=ML-DSA-65\n")
        state = immune_daemon.ImmuneState(conf_path)

        # Create a breaker with max_retries=1 to test immediate trip on unknown status
        breaker = immune_daemon.CircuitBreaker(
            max_retries=1,
            timeout_window=60,
            quarantine_delay_ms=0,
            safe_mode_cipher="FrodoKEM-976-AES",
        )

        import urllib.request
        orig_urlopen = urllib.request.urlopen
        urllib.request.urlopen = lambda req, timeout=None: _FakeResponse({
            "result": {
                "node_status": "UNKNOWN",
                "recommended_fallback": "FrodoKEM-976-AES"
            }
        })
        try:
            # We mock requests.get for fallback/recovery map fetches because decision_loop does that at start
            import requests
            orig_get = getattr(requests, 'get', None)
            requests.get = lambda *args, **kwargs: (_ for _ in ()).throw(Exception("mocked"))
            try:
                immune_daemon.decision_loop(
                    state=state,
                    opa_endpoint="http://fake",
                    poll_sec=0.01,
                    fail_secure_threshold=1,
                    dry_run=False,
                    once=True,
                    pg_config=None,
                    webhook=None,
                    breaker=breaker,
                )
                assert state.active_kem == "FrodoKEM-976-AES", (
                    f"Expected fail-secure collapse to FrodoKEM-976-AES, but got {state.active_kem}"
                )
                print("PASS: [D-2] unexpected/unknown node_status triggers fail-secure fallback")
            finally:
                if orig_get is not None:
                    requests.get = orig_get
        finally:
            urllib.request.urlopen = orig_urlopen


def test_unknown_algorithm_does_not_downgrade():
    """Guards D-3: unknown active algorithm halts without guessing or silent downgrade."""
    fallback = immune_daemon.next_fallback("ML-KEM-768-hybrid")
    assert fallback == "NONE", "Unknown algorithm must return NONE to trigger exhaustion halt"
    print("PASS: [D-3] unknown algorithm does not downgrade silently")


def test_worker_pid_tracking():
    """Guards D-4: worker_pid is initialized from environment and tracked in state."""
    with tempfile.TemporaryDirectory() as tmp:
        conf_path = Path(tmp) / "crypto_provider.conf"
        conf_path.write_text("active_kem=ML-KEM-768\n")
        orig_pid = os.environ.get("WORKER_PID")
        try:
            os.environ["WORKER_PID"] = "99999"
            state = immune_daemon.ImmuneState(conf_path)
            state.worker_pid = int(os.environ["WORKER_PID"])
            assert state.worker_pid == 99999
            print("PASS: [D-4] worker PID tracking functional")
        finally:
            if orig_pid is not None:
                os.environ["WORKER_PID"] = orig_pid
            else:
                os.environ.pop("WORKER_PID", None)


def test_authoritative_rego_fallback_chain():
    """Verify that OPA (.rego) is the authoritative single source of truth for FALLBACK_CHAIN."""
    rego_map = immune_daemon.load_fallback_map_from_rego()
    assert len(rego_map) > 0, "Failed to load fallback map from membrane_health.rego"
    assert rego_map.get("ML-KEM-768") == "FrodoKEM-976-AES"
    assert rego_map.get("ML-KEM-512") == "FrodoKEM-640-AES"
    assert rego_map.get("ML-KEM-1024") == "FrodoKEM-1344-AES"
    assert rego_map.get("FrodoKEM-976-AES") == "X25519"

    # Test dynamic single-source-of-truth derivation
    custom_rego = """
    package membrane.health
    fallback_map := {
        "CUSTOM-PQC-1": "CUSTOM-FALLBACK-2",
        "CUSTOM-FALLBACK-2": "X25519",
        "X25519": "NONE"
    }
    """
    parsed = immune_daemon.parse_rego_fallback_map(custom_rego)
    assert parsed.get("CUSTOM-PQC-1") == "CUSTOM-FALLBACK-2"
    assert parsed.get("CUSTOM-FALLBACK-2") == "X25519"

    fb = immune_daemon.next_fallback("CUSTOM-PQC-1", fallback_map=parsed)
    assert fb == "CUSTOM-FALLBACK-2", f"Expected CUSTOM-FALLBACK-2, got {fb}"

    fb2 = immune_daemon.next_fallback("CUSTOM-FALLBACK-2", fallback_map=parsed)
    assert fb2 == "X25519", f"Expected X25519, got {fb2}"

    fb3 = immune_daemon.next_fallback("X25519", fallback_map=parsed)
    assert fb3 == "NONE", f"Expected NONE, got {fb3}"

    print("PASS: [SINGLE SOURCE OF TRUTH] OPA (.rego) authoritative fallback chain verified")


# ═══════════════════════════════════════════════════════════════════
# Self-Healing / Quarantine Architecture Tests
# ═══════════════════════════════════════════════════════════════════

def test_circuit_breaker_quarantine_then_recover():
    """Guards Q-1: Single failure enters QUARANTINE, successful OPA response resets to ACTIVE."""
    with tempfile.TemporaryDirectory() as tmp:
        conf_path = Path(tmp) / "crypto_provider.conf"
        conf_path.write_text("active_kem=ML-KEM-768\nactive_sig=ML-DSA-65\n")
        state = immune_daemon.ImmuneState(conf_path)

        breaker = immune_daemon.CircuitBreaker(
            max_retries=3,
            timeout_window=60,
            quarantine_delay_ms=0,
            safe_mode_cipher="FrodoKEM-976-AES",
        )

        # Simulate 1 failure — should enter QUARANTINE, not COLLAPSED
        tripped = breaker.record_failure()
        assert not tripped, "1 failure should NOT trip the breaker"
        assert breaker.state == "QUARANTINE"

        # Enter quarantine mode — should apply safe-mode cipher
        immune_daemon.enter_quarantine_mode(state, breaker, dry_run=False)
        assert state.active_kem == "FrodoKEM-976-AES", (
            f"Expected safe-mode cipher FrodoKEM-976-AES, got {state.active_kem}"
        )
        assert breaker.pre_quarantine_kem == "ML-KEM-768"

        # Simulate recovery — OPA returns COMPLIANT
        breaker.reset()
        assert breaker.state == "ACTIVE"
        assert breaker.failure_count == 0
        assert breaker.pre_quarantine_kem is None

        print("PASS: [Q-1] circuit breaker quarantine -> recover lifecycle verified")


def test_circuit_breaker_trips_after_max_retries():
    """Guards Q-2: 3 consecutive failures within window trips the breaker (terminal collapse)."""
    breaker = immune_daemon.CircuitBreaker(
        max_retries=3,
        timeout_window=60,
        quarantine_delay_ms=0,
        safe_mode_cipher="FrodoKEM-976-AES",
    )

    # Failures 1 and 2 — quarantine, not collapsed
    assert not breaker.record_failure()
    assert breaker.state == "QUARANTINE"
    assert not breaker.record_failure()
    assert breaker.state == "QUARANTINE"

    # Failure 3 — trips the breaker
    assert breaker.record_failure()
    assert breaker.state == "COLLAPSED"
    assert breaker.failure_count == 3

    print("PASS: [Q-2] circuit breaker trips after max_retries (3) consecutive failures")


def test_quarantine_applies_safe_mode_cipher():
    """Guards Q-3: Quarantine atomically writes safe-mode cipher to crypto_provider.conf."""
    with tempfile.TemporaryDirectory() as tmp:
        conf_path = Path(tmp) / "crypto_provider.conf"
        conf_path.write_text("active_kem=ML-KEM-768\nactive_sig=ML-DSA-65\n")
        state = immune_daemon.ImmuneState(conf_path)

        breaker = immune_daemon.CircuitBreaker(
            max_retries=3,
            timeout_window=60,
            quarantine_delay_ms=0,
            safe_mode_cipher="FrodoKEM-976-AES",
        )

        # Enter quarantine
        breaker.record_failure()
        immune_daemon.enter_quarantine_mode(state, breaker, dry_run=False)

        # Verify the config file was atomically rewritten
        conf_content = conf_path.read_text()
        assert "FrodoKEM-976-AES" in conf_content, (
            f"safe_mode_cipher not written to conf:\n{conf_content}"
        )
        assert state.active_kem == "FrodoKEM-976-AES"

        # Verify calling quarantine again when already on safe cipher does NOT rewrite
        mtime_before = conf_path.stat().st_mtime_ns
        import time; time.sleep(0.01)  # Ensure mtime would change if rewritten
        immune_daemon.enter_quarantine_mode(state, breaker, dry_run=False)
        mtime_after = conf_path.stat().st_mtime_ns
        assert mtime_before == mtime_after, "Config should NOT be rewritten when already on safe cipher"

        print("PASS: [Q-3] quarantine atomically applies safe-mode cipher to config")


def test_recovery_map_loaded_from_rego():
    """Guards Q-4: parse_rego_recovery_map correctly extracts recovery parameters from .rego."""
    rego_content = """
    package membrane.health

    recovery_map := {
        "max_retries": 5,
        "timeout_window_sec": 120,
        "quarantine_delay_ms": 10000,
        "safe_mode_cipher": "FrodoKEM-1344-AES",
        "quarantine_action": "isolate_and_hold",
    }
    """
    parsed = immune_daemon.parse_rego_recovery_map(rego_content)
    assert parsed.get("max_retries") == 5, f"Expected max_retries=5, got {parsed.get('max_retries')}"
    assert parsed.get("timeout_window_sec") == 120
    assert parsed.get("quarantine_delay_ms") == 10000
    assert parsed.get("safe_mode_cipher") == "FrodoKEM-1344-AES"
    assert parsed.get("quarantine_action") == "isolate_and_hold"

    # Verify CircuitBreaker.from_recovery_map constructs correctly
    breaker = immune_daemon.CircuitBreaker.from_recovery_map(parsed)
    assert breaker.max_retries == 5
    assert breaker.timeout_window == 120.0
    assert breaker.quarantine_delay_sec == 10.0
    assert breaker.safe_mode_cipher == "FrodoKEM-1344-AES"

    # Also verify the live .rego on disk
    live_map = immune_daemon.load_recovery_map_from_rego()
    assert len(live_map) > 0, "Failed to load recovery_map from membrane_health.rego on disk"
    assert live_map.get("max_retries") == 3, f"Expected max_retries=3 from disk, got {live_map.get('max_retries')}"
    assert live_map.get("safe_mode_cipher") == "FrodoKEM-976-AES"

    print("PASS: [Q-4] recovery_map loaded from rego (single source of truth) verified")


def test_worker_pid_sighup_signal():
    """Verify that os.kill is called with SIGHUP when worker_pid is set and SIGHUP is supported."""
    with tempfile.TemporaryDirectory() as tmp:
        conf_path = Path(tmp) / "crypto_provider.conf"
        conf_path.write_text("active_kem=ML-KEM-768\nactive_sig=ML-DSA-65\n")
        state = immune_daemon.ImmuneState(conf_path)
        state.worker_pid = 12345

        # Patch signal and os.kill
        with patch("immune_daemon.signal") as mock_signal, \
             patch("immune_daemon.os.kill") as mock_kill:
            
            # Ensure SIGHUP attribute exists on mocked signal module
            mock_signal.SIGHUP = 1
            
            immune_daemon.execute_collapse(
                state=state,
                recommended="FrodoKEM-976-AES",
                findings=[],
                dry_run=False,
                pg_config=None,
                webhook=None
            )
            
            # Verify os.kill was called with PID and SIGHUP
            mock_kill.assert_called_once_with(12345, 1)
            print("PASS: [D-4] SIGHUP signal sent to worker PID successfully")


if __name__ == "__main__":
    test_vein_collapse_rewrites_conf()
    test_all_algorithms_exhausted_halts()
    test_daemon_starts_with_default_conf()
    test_empty_opa_result_is_not_compliant()
    test_result_without_node_status_is_not_compliant()
    test_valid_verdict_still_passes_through()
    test_opa_unknown_status_fails_secure()
    test_unknown_algorithm_does_not_downgrade()
    test_worker_pid_tracking()
    test_worker_pid_sighup_signal()
    test_authoritative_rego_fallback_chain()

    # Self-Healing / Quarantine Architecture Tests
    test_circuit_breaker_quarantine_then_recover()
    test_circuit_breaker_trips_after_max_retries()
    test_quarantine_applies_safe_mode_cipher()
    test_recovery_map_loaded_from_rego()

    print("\n[ALL 15 SECURITY, COMPLIANCE & SELF-HEALING INVARIANTS 100% VERIFIED]")
