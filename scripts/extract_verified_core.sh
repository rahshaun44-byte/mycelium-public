#!/usr/bin/env bash
set -euo pipefail

WORKSPACE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[*] Building local FStar+KaRaMeL extraction image..."
podman build -t fstar-krml-extractor -f "$WORKSPACE/scripts/Containerfile.fstar" "$WORKSPACE/scripts"

echo "[*] Extracting QuantumFlex_Core.fst..."
# F* emits QuantumFlex_Core.krml
# KaRaMeL translates it to C. We output to QuantumFlex_Core.c and drop FStar standard library dependencies.
podman run --rm -v "$WORKSPACE:/workspace:z" -w /workspace/formal fstar-krml-extractor \
    bash -c "fstar.exe --codegen krml QuantumFlex_Core.fst && \
             krml -bundle QuantumFlex_Core=* -drop FStar -o ../src/core/QuantumFlex_Core.c QuantumFlex_Core.krml"

echo "[*] Extraction complete. Generated C sources in src/core/."
