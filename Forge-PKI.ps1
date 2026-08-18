# Forge-PKI.ps1
# Generates local Ed25519 Root CA, Server Cert, and Client Cert for mTLS

param(
    [string]$OutputDir = "$PSScriptRoot\pki",
    [string]$Python    = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $Python)) {
    $Python = "python"
}

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  QUANTUM FLEX: Ed25519 PKI Generator    " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

& $Python "$PSScriptRoot\forge_pki.py" $OutputDir
