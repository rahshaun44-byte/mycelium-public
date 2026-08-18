# ═══════════════════════════════════════════════════════════════════
# Quantum Flex: Bare-Metal Windows Production Stack Launcher
# ═══════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  QUANTUM FLEX: BARE-METAL BIOLOGICAL STACK LAUNCHER" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Environment & Path configuration
$env:Path = "$env:LOCALAPPDATA\Programs\Ollama;$env:LOCALAPPDATA\Programs\OPA;C:\Program Files\Git\cmd;$env:Path"
$env:PQC_PROVIDER_CONF = "$Root\mcp_layer\crypto_provider.conf"
$env:OPA_ENDPOINT = "http://127.0.0.1:8181"

# 2. Check / Start Ollama Daemon
Write-Host "[1/6] Initializing Ollama Server..." -ForegroundColor Yellow
$ollamaProc = Get-Process -Name "ollama" -ErrorAction SilentlyContinue
if (-not $ollamaProc) {
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 2
}
Write-Host "  [+] Ollama Server active at http://127.0.0.1:11434" -ForegroundColor Green

# 3. Check / Start OPA Sidecar
Write-Host "[2/6] Initializing Open Policy Agent (OPA) Sidecar..." -ForegroundColor Yellow
$opaProc = Get-Process -Name "opa" -ErrorAction SilentlyContinue
if (-not $opaProc) {
    $policyPath = "$Root\sentinel\policies"
    if (-not (Test-Path $policyPath)) { $policyPath = "$Root\pqc-immune-daemon" }
    Start-Process -FilePath "$env:LOCALAPPDATA\Programs\OPA\opa.exe" -ArgumentList "run -s --addr 127.0.0.1:8181 `"$policyPath`"" -WindowStyle Hidden
    Start-Sleep -Seconds 2
}
Write-Host "  [+] OPA Sidecar active at http://127.0.0.1:8181" -ForegroundColor Green

# 4. Launch Athena RAG Node (Port 8001)
Write-Host "[3/6] Starting A.T.H.E.N.A. Neural RAG Node (Port 8001)..." -ForegroundColor Yellow
Start-Process -FilePath "python" -ArgumentList "-m uvicorn athena_api:app --host 127.0.0.1 --port 8001" -WorkingDirectory "$Root\mcp_layer" -WindowStyle Hidden
Write-Host "  [+] Athena Node active at http://127.0.0.1:8001" -ForegroundColor Green

# 5. Launch Amara Matrix Dashboard (Port 8000)
Write-Host "[4/6] Starting A.M.A.R.A. Dashboard (Port 8000)..." -ForegroundColor Yellow
Start-Process -FilePath "python" -ArgumentList "-m uvicorn dashboard:app --host 127.0.0.1 --port 8000" -WorkingDirectory "$Root\amara" -WindowStyle Hidden
Write-Host "  [+] Amara Dashboard active at http://127.0.0.1:8000" -ForegroundColor Green

# 6. Launch PQC Immune Daemon
Write-Host "[5/6] Launching PQC Crypto-Agility Immune Daemon..." -ForegroundColor Yellow
Start-Process -FilePath "python" -ArgumentList "immune_daemon.py" -WorkingDirectory "$Root\pqc-immune-daemon" -WindowStyle Hidden
Write-Host "  [+] PQC Immune Daemon active" -ForegroundColor Green

# 7. Launch Swarm Worker
Write-Host "[6/6] Launching Swarm Worker (SKIP LOCKED Consumer)..." -ForegroundColor Yellow
Start-Process -FilePath "python" -ArgumentList "mcp_layer\swarm_worker.py" -WorkingDirectory "$Root" -WindowStyle Hidden
Write-Host "  [+] Swarm Worker online" -ForegroundColor Green

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  ALL BIOLOGICAL STRATA DEPLOYED AND RUNNING ON LOCALHOST" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
