#!/usr/bin/env python3
"""
Minimal end-to-end test for the immune daemon's core behavior:
feed a synthetic TOXIC verdict into execute_vein_collapse() and assert
that crypto_provider.conf is actually rewritten to the recommended
fallback. No test framework required -- run directly with:

    python test_immune_daemon.py
"""

import shutil
import sys
import tempfile
from pathlib import Path

import immune_daemon


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


def test_daemon_starts_with_default_conf(tmp_path=None, monkeypatch=None):
    """Guards D-1: the documented no-arg entry point must not crash."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        orig_cwd = Path.cwd()
        orig_argv = sys.argv.copy()
        try:
            import os
            os.chdir(tmp_path)
            (tmp_path / "crypto_provider.conf").write_text("active_kem=ML-KEM-768\n")
            sys.argv = ["immune_daemon.py", "--once", "--dry-run"]
            immune_daemon.main()   # must not raise
            print("PASS: daemon starts with default config path")
        finally:
            os.chdir(orig_cwd)
            sys.argv = orig_argv

def test_empty_opa_result_is_not_compliant():
    """Guards D-2: HTTP 200 with {} must be treated as failure."""
    import immune_daemon
    # A mock class for requests response
    class MockResponse:
        def json(self): return {}
        def raise_for_status(self): pass

    # Mock requests post
    import requests
    orig_post = requests.post
    requests.post = lambda *args, **kwargs: MockResponse()
    try:
        verdict = immune_daemon.query_opa("http://fake", {})
        assert verdict is None, "Empty OPA response must return None to trigger fail-secure"
        print("PASS: empty OPA result returns None")
    finally:
        requests.post = orig_post


def test_unknown_algorithm_does_not_downgrade():
    """Guards D-3."""
    fallback = immune_daemon.next_fallback("ML-KEM-768-hybrid")
    assert fallback == "NONE", "Unknown algorithm must return NONE to trigger exhaustion halt"
    print("PASS: unknown algorithm does not downgrade silently")


if __name__ == "__main__":
    test_vein_collapse_rewrites_conf()
    test_all_algorithms_exhausted_halts()
    test_daemon_starts_with_default_conf()
    test_empty_opa_result_is_not_compliant()
    test_unknown_algorithm_does_not_downgrade()
    print("\nAll tests passed.")
