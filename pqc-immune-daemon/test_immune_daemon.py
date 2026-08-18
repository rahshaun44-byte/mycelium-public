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

        # No worker_pid set, so this just needs to not raise and not rewrite.
        immune_daemon.execute_vein_collapse(state, verdict)

        assert "active_kem=X25519" in conf_path.read_text(), (
            "conf should be untouched when no fallback is available"
        )
        print("PASS: exhausted fallback chain halts without rewriting config")


if __name__ == "__main__":
    test_vein_collapse_rewrites_conf()
    test_all_algorithms_exhausted_halts()
    print("\nAll tests passed.")
