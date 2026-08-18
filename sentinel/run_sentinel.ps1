<#
.SYNOPSIS
    run_sentinel.ps1
    Build and execute the SNN Sentinel container in Docker / Podman Desktop on Windows.
#>

$ErrorActionPreference = "Stop"

Write-Host "=== Quantum Flex: Compiling SNN Sentinel Node on Windows ===" -ForegroundColor Cyan
podman build -t localhost/qflex/snn_sentinel:v1 -f Containerfile.snn .

Write-Host "=== Detonating Sentinel Sandbox (Windows Mode) ===" -ForegroundColor Green
podman run --rm --security-opt label=disable `
    localhost/qflex/snn_sentinel:v1 python lif_sentinel.py
