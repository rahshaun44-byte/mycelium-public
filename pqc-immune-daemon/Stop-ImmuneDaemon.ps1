# Stop-ImmuneDaemon.ps1
$ErrorActionPreference = "Stop"

$pidFile = Join-Path $PSScriptRoot "logs\immune_daemon.pid"
if (-not (Test-Path $pidFile)) {
    Write-Host "No PID file found - daemon may not be running." -ForegroundColor Yellow
    exit 0
}

$daemonPid = Get-Content $pidFile -ErrorAction SilentlyContinue
if ($daemonPid -and (Get-Process -Id $daemonPid -ErrorAction SilentlyContinue)) {
    Stop-Process -Id $daemonPid -Force
    Write-Host "Stopped immune_daemon (PID $daemonPid)" -ForegroundColor Green
} else {
    Write-Host "Process not found or already stopped." -ForegroundColor Gray
}

Remove-Item $pidFile -ErrorAction SilentlyContinue
