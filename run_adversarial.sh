#!/usr/bin/env bash
set -euo pipefail

echo "[*] QuantumFlex Adversarial Benchmark Gate"
echo "[*] Target Model: amara:workstation @ http://127.0.0.1:11434"

if [ ! -f "run_amara_adversarial_benchmark.py" ]; then
echo "[!] Error: run_amara_adversarial_benchmark.py not found in current directory."
exit 1
fi

python3 run_amara_adversarial_benchmark.py
echo "[*] Complete. Inspecting amara_adversarial_benchmark_result.md..."
tail -n 30 amara_adversarial_benchmark_result.md
