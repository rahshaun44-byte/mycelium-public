<#
.SYNOPSIS
    start_bundle_server.ps1
    Quantum Flex - OPA Bundle Server for Windows.
    Serves localized bundle.tar.gz for OPA sidecars on port 8182.
#>

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$bundleDir = Join-Path $scriptDir "bundle_server"
$policiesDir = Join-Path $scriptDir "policies"

if (-not (Test-Path $bundleDir)) {
    New-Item -ItemType Directory -Force -Path $bundleDir | Out-Null
}

$bundleTar = Join-Path $bundleDir "bundle.tar.gz"
$dataJson = Join-Path $bundleDir "data.json"

if (-not (Test-Path $bundleTar)) {
    Set-Location $bundleDir
    '{"threat_flags": {}}' | Out-File -FilePath $dataJson -Encoding utf8 -NoNewline
    tar -czf bundle.tar.gz data.json -C $policiesDir membrane_health.rego
    $timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    Write-Host "[$timestamp] Initial OPA bundle created on Windows." -ForegroundColor Green
}

# Stop any existing listener on port 8182
$existing = Get-NetTCPConnection -LocalPort 8182 -ErrorAction SilentlyContinue
if ($existing) {
    foreach ($conn in $existing) {
        Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
    }
}

Set-Location $bundleDir
Start-Process -FilePath "python" -ArgumentList "-m http.server 8182" -WindowStyle Hidden
$timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
Write-Host "[$timestamp] Bundle server listening on http://127.0.0.1:8182" -ForegroundColor Cyan
