#!/usr/bin/env python3
"""
QuantumFlex Formal Invariant & Differential Equivalence Suite (QF-A3 / QF-A4).
Proves mathematical equivalence between F* formal specification
(formal/QuantumFlex_Core.fst) and C implementations (src/core/verified_core.c
and src/core/generated/QuantumFlex_Core.c).
"""

import os
import subprocess
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_formal_invariants_proof_discharge():
    """QF-A3 Invariant Gate: Discharges all F* verification conditions via SMT (Z3)."""
    script = REPO_ROOT / "scripts" / "verify_formal_core.sh"
    assert script.is_file(), f"Verification script missing: {script}"

    proc = subprocess.run(
        [str(script)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"Formal verification failed:\n{proc.stderr}\n{proc.stdout}"
    assert "All verification conditions discharged successfully" in proc.stdout
    assert "[PASS] QF-A3 FORMAL INVARIANTS DISCHARGED" in proc.stdout


def test_karamel_machine_extraction_pipeline():
    """QF-A4 Extraction Pipeline: Verifies F* -> KaRaMeL -> C machine extraction."""
    script = REPO_ROOT / "scripts" / "extract_verified_core.sh"
    assert script.is_file(), f"Extraction script missing: {script}"

    proc = subprocess.run(
        [str(script)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"Extraction failed:\n{proc.stderr}\n{proc.stdout}"
    assert "[PASS] MACHINE EXTRACTION & COMPILATION GATE PASSED" in proc.stdout

    gen_c = REPO_ROOT / "src" / "core" / "generated" / "QuantumFlex_Core.c"
    gen_h = REPO_ROOT / "src" / "core" / "generated" / "QuantumFlex_Core.h"
    gen_o = REPO_ROOT / "src" / "core" / "generated" / "QuantumFlex_Core.o"
    ref_c = REPO_ROOT / "src" / "core" / "verified_core.c"

    assert gen_c.is_file(), "Generated C source missing"
    assert gen_h.is_file(), "Generated C header missing"
    assert gen_o.is_file(), "Generated object missing"
    assert ref_c.is_file(), "Reference C implementation must remain intact"


def test_differential_equivalence_harness():
    """QF-A4 Invariant Equivalence: Compares reference C vs KaRaMeL-extracted C across 10,000+ vectors."""
    diff_bin = REPO_ROOT / "build_check" / "test_differential_core"

    # If binary does not exist, build it via cmake
    if not diff_bin.is_file():
        subprocess.run(
            ["cmake", "--build", "build_check", "--target", "test_differential_core"],
            cwd=str(REPO_ROOT),
            check=True,
            capture_output=True,
        )

    proc = subprocess.run(
        [str(diff_bin)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"Differential test failed:\n{proc.stderr}\n{proc.stdout}"
    assert "ZERO DIVERGENCE ACROSS ALL INVARIANTS" in proc.stdout
    assert "TOTAL CHECKS" in proc.stdout
    assert "matched bit-for-bit" in proc.stdout
