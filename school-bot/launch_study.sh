#!/usr/bin/env bash
# ═══════════════════════════════════════════════════
#  STUDY SESSION LAUNCHER — One-click school mode
# ═══════════════════════════════════════════════════
set -euo pipefail

VENV="/home/quant/mycelium/.venv/bin/python3"
TUTOR="/home/quant/mycelium/school-bot/study_tutor.py"

# Use 7b for rich explanations by default
export STUDY_MODEL="${STUDY_MODEL:-qwen2.5-coder:7b}"
export FAST_MODEL="${FAST_MODEL:-gemma2:2b}"
export OLLAMA_HOST="http://127.0.0.1:11434"

exec "$VENV" "$TUTOR" "$@"
