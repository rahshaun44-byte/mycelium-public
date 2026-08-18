# ═══════════════════════════════════════════════════════════════════
# QuantumFlex: Master n8n Automation Engine Launcher
# ═══════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  QUANTUM FLEX: N8N AUTONOMOUS WORKFLOW ENGINE (v2.8.4)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Environment & Paths
$nodeDir = "$env:LOCALAPPDATA\Programs\nodejs"
$env:Path = "$nodeDir;$env:LOCALAPPDATA\Programs\Ollama;$env:LOCALAPPDATA\Programs\OPA;$env:Path"

$env:N8N_PORT = "5678"
$env:N8N_HOST = "127.0.0.1"
$env:N8N_LISTEN_ADDRESS = "127.0.0.1"
$env:N8N_PROTOCOL = "http"
$env:WEBHOOK_URL = "http://127.0.0.1:5678/"
$env:N8N_USER_FOLDER = "$env:USERPROFILE\.n8n"
$env:N8N_METRICS_ENABLED = "false"
$env:N8N_DIAGNOSTICS_ENABLED = "false"
$env:N8N_DEFAULT_BINARY_DATA_MODE = "filesystem"

Write-Host "[*] Target Webhook URL: $env:WEBHOOK_URL" -ForegroundColor Yellow
Write-Host "[*] n8n Workflows Dir : $Root\n8n_workflows" -ForegroundColor Yellow

# 2. Check if n8n process is already active
$n8nProc = Get-Process -Name "node" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*n8n*" }
if ($n8nProc) {
    Write-Host "[+] n8n Engine is already running (PID $($n8nProc.Id)) on http://127.0.0.1:5678" -ForegroundColor Green
    Exit 0
}

Write-Host "[*] Launching n8n Autonomous Automation Daemon..." -ForegroundColor Yellow
Start-Process -FilePath "$nodeDir\node.exe" -ArgumentList "`"$nodeDir\node_modules\n8n\bin\n8n`" start" -WindowStyle Hidden

Start-Sleep -Seconds 5
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  N8N ENGINE ONLINE -> http://127.0.0.1:5678" -ForegroundColor Green
Write-Host "  Import workflows from: $Root\n8n_workflows" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
