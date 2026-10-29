#!/usr/bin/env bash
# ==============================================================================
# QuantumFlex Formal Verification Runner (QF-A3 Invariant Gate)
# Verifies formal/QuantumFlex_Core.fst against local F* binary.
# Fail-closed: Exits non-zero if F* is missing or any proof obligation fails.
# ==============================================================================
set -euo pipefail

WORKSPACE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_FILE="${WORKSPACE}/formal/QuantumFlex_Core.fst"
FSTAR_BIN="${FSTAR_BIN:-$(which fstar.exe 2>/dev/null || echo "/home/quant/.local/bin/fstar.exe")}"

echo "================================================================================"
echo "QUANTUMFLEX FORMAL VERIFICATION: F* PROOF HARNESS (QF-A3)"
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

echo "[*] Discharging verification conditions via SMT (Z3)..."
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

echo "================================================================================"
printf "[PASS] QF-A3 FORMAL INVARIANTS DISCHARGED IN %.2fs\n" "${ELAPSED_SEC}"
echo "NOTE: QF-A4 (Machine Extraction) remains strictly NULL until automated KaRaMeL"
echo "      extraction and bit-level C equivalence proofs are integrated into CI."
echo "================================================================================"
exit 0
