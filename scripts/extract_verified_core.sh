#!/usr/bin/env bash
# ==============================================================================
# QuantumFlex Verified Core Extraction Harness (KaRaMeL Toolchain Pipeline)
# Translates formal/QuantumFlex_Core.fst to C via KaRaMeL.
# Outputs isolated generated artifacts into src/core/generated/.
# Preserves reference implementation in src/core/verified_core.c.
# Strict compilation gate: -Wall -Wextra -Werror -pedantic -std=c11
# ==============================================================================
set -euo pipefail

WORKSPACE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMAL_DIR="${WORKSPACE}/formal"
TARGET_FST="${FORMAL_DIR}/QuantumFlex_Core.fst"
OUT_DIR="${WORKSPACE}/src/core/generated"

FSTAR_BIN="${FSTAR_BIN:-$(which fstar.exe 2>/dev/null || echo "/home/quant/.local/bin/fstar.exe")}"
KRML_BIN="${KRML_BIN:-$(which krml 2>/dev/null || echo "/home/quant/.local/bin/krml")}"

echo "================================================================================"
echo "QUANTUMFLEX VERIFIED CORE: MACHINE EXTRACTION (F* -> KaRaMeL -> C)"
echo "Target: ${TARGET_FST}"
echo "Output: ${OUT_DIR}"
echo "================================================================================"

if [[ ! -x "${FSTAR_BIN}" ]]; then
    echo "[!] FATAL: F* binary not found or not executable at '${FSTAR_BIN}'" >&2
    exit 1
fi

if [[ ! -x "${KRML_BIN}" ]]; then
    echo "[!] FATAL: KaRaMeL binary not found or not executable at '${KRML_BIN}'" >&2
    exit 1
fi

if [[ ! -f "${TARGET_FST}" ]]; then
    echo "[!] FATAL: Target formal specification '${TARGET_FST}' not found." >&2
    exit 1
fi

echo "[*] Pinned Toolchain Provenance:"
echo "    F* Version:"
"${FSTAR_BIN}" --version | sed 's/^/        /'
echo "    KaRaMeL Location: ${KRML_BIN}"

KRML_INCLUDEDIR="$("${KRML_BIN}" -locate-include 2>/dev/null || echo "/home/quant/.local/fstar/fstar/include/krml")"
KRML_LIBDIR="$("${KRML_BIN}" -locate-krmllib 2>/dev/null || echo "/home/quant/.local/fstar/fstar/lib/krml")"
echo "    KaRaMeL Include: ${KRML_INCLUDEDIR}"
echo "    KaRaMeL Lib:     ${KRML_LIBDIR}"

mkdir -p "${OUT_DIR}"

echo "[*] Step 1/3: Verifying and emitting checked module..."
"${FSTAR_BIN}" -c --odir "${OUT_DIR}" "${TARGET_FST}"

echo "[*] Step 2/3: Generating KaRaMeL intermediate representation (.krml)..."
"${FSTAR_BIN}" --codegen krml --extract QuantumFlex_Core --odir "${OUT_DIR}" "${TARGET_FST}"

echo "[*] Step 3/3: KaRaMeL translation to C..."
"${KRML_BIN}" \
    -skip-compilation \
    -tmpdir "${OUT_DIR}" \
    -no-prefix QuantumFlex_Core \
    -bundle QuantumFlex_Core=* \
    -drop FStar \
    "${OUT_DIR}/QuantumFlex_Core.krml"

# Cleanup intermediate .checked and .krml from generated output
rm -f "${OUT_DIR}"/*.checked "${OUT_DIR}"/*.krml

echo "[*] Verifying generated C source files exist..."
if [[ ! -f "${OUT_DIR}/QuantumFlex_Core.c" || ! -f "${OUT_DIR}/QuantumFlex_Core.h" ]]; then
    echo "[!] FATAL: Expected generated files QuantumFlex_Core.c and QuantumFlex_Core.h missing." >&2
    exit 2
fi

echo "[*] Running strict compilation gate on extracted C code..."
echo "    Flags: -Wall -Wextra -Werror -pedantic -std=c11"
gcc -c \
    -I"${OUT_DIR}" \
    -isystem "${KRML_INCLUDEDIR}" \
    -isystem "${KRML_LIBDIR}/dist/minimal" \
    -D_DEFAULT_SOURCE \
    -D_GNU_SOURCE \
    -Wall -Wextra -Werror -pedantic -std=c11 \
    "${OUT_DIR}/QuantumFlex_Core.c" \
    -o "${OUT_DIR}/QuantumFlex_Core.o"

echo "================================================================================"
echo "[PASS] MACHINE EXTRACTION & COMPILATION GATE PASSED"
echo "Generated artifacts in ${OUT_DIR}:"
ls -lh "${OUT_DIR}/QuantumFlex_Core.c" "${OUT_DIR}/QuantumFlex_Core.h" "${OUT_DIR}/QuantumFlex_Core.o" | sed 's/^/    /'
echo "Reference implementation preserved at: ${WORKSPACE}/src/core/verified_core.c"
echo "================================================================================"
exit 0
