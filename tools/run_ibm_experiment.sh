#!/usr/bin/env bash
# Wrapper to run IBM Quantum experiments using the virtual environment
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec /home/quant/.venv/bin/python3 "${SCRIPT_DIR}/ibm_experiment_runner.py" "$@"
