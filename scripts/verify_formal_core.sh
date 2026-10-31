#!/usr/bin/env bash
# ==============================================================================
# QuantumFlex Formal Verification Runner (QF-A3 / QF-A4 Invariant Gate)
# Verifies formal/QuantumFlex_Core.fst against local F* binary,
# executes KaRaMeL machine extraction to C11 (QF-A4),
# and verifies differential bit-for-bit equivalence across 10,000+ vectors.
# Fail-closed: Exits non-zero if F*, KaRaMeL, or any proof obligation fails.
# ==============================================================================
set -euo pipefail

WORKSPACE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_FILE="${WORKSPACE}/formal/QuantumFlex_Core.fst"
FSTAR_BIN="${FSTAR_BIN:-$(which fstar.exe 2>/dev/null || echo "/home/quant/.local/bin/fstar.exe")}"

echo "================================================================================"
echo "QUANTUMFLEX FORMAL VERIFICATION: F* PROOF HARNESS (QF-A3 / QF-A4)"
echo "Target: ${TARGET_FILE}"
echo "================================================================================"

if [[ ! -x "${FSTAR_BIN}" ]]; then
    echo "[!] FATAL: F* binary not found or not executable at '${FSTAR_BIN}'" >&2
    exit 1
fi

if [[ ! -f "${TARGET_FILE}" ]]; then
    echo "[!] FATAL: Target formal specification '${TARGET_FILE}' not found." >&2
    exit 1
fi

echo "[*] Toolchain Version:"
"${FSTAR_BIN}" --version | sed 's/^/    /'

echo "[*] Step 1/3: Discharging QF-A3 formal verification conditions via SMT (Z3)..."
START_TIME=$(date +%s%N)

OUTPUT=$("${FSTAR_BIN}" "${TARGET_FILE}" 2>&1)
EXIT_CODE=$?

END_TIME=$(date +%s%N)
ELAPSED_SEC=$(awk "BEGIN {print (${END_TIME} - ${START_TIME}) / 1000000000}")

printf '%s\n' "${OUTPUT}" | sed 's/^/    /'

if [[ ${EXIT_CODE} -ne 0 ]]; then
    echo "[!] FORMAL VERIFICATION FAILED (Exit Code: ${EXIT_CODE})" >&2
    exit "${EXIT_CODE}"
fi

if ! printf '%s\n' "${OUTPUT}" | grep -q "All verification conditions discharged successfully"; then
    echo "[!] FAIL-CLOSED: Output did not confirm complete proof discharge." >&2
    exit 2
fi

printf "[PASS] QF-A3 FORMAL INVARIANTS DISCHARGED IN %.2fs\n" "${ELAPSED_SEC}"

echo "[*] Step 2/3: Executing QF-A4 KaRaMeL Machine Extraction (F* -> C11)..."
"${WORKSPACE}/scripts/extract_verified_core.sh" | sed 's/^/    /'

echo "[*] Step 3/3: Running QF-A4 Differential Invariant Equivalence Harness..."
cmake --build "${WORKSPACE}/build_check" --target test_differential_core -- -j"$(nproc)" >/dev/null
"${WORKSPACE}/build_check/test_differential_core" | sed 's/^/    /'

echo "================================================================================"
echo "[SUCCESS] QF-A4 MACHINE EXTRACTION OUT OF NULL: VERIFIED & COMPILING IN CI"
echo "          F* Mathematical Model == KaRaMeL C11 Extraction == Reference C"
echo "================================================================================"
exit 0
