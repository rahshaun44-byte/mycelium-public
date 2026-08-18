# Start-ImmuneDaemon.ps1
# Starts the improved PQC immune daemon, bound to Tailscale constraints.

param(
    [switch]$DryRun,
    [switch]$Once,
    [string]$ConfPath = "$PSScriptRoot\crypto_provider.conf",
    [string]$Python   = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $Python)) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $Python = "python" }
}

$daemonDir = Split-Path $ConfPath -Parent
if (-not $daemonDir) { $daemonDir = $PSScriptRoot }
$logDir    = Join-Path $daemonDir "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$stdoutLog = Join-Path $logDir "immune_daemon.log"
$stderrLog = Join-Path $logDir "immune_daemon.err.log"

$env:PQC_PROVIDER_CONF = $ConfPath
$env:OPA_ENDPOINT      = "http://127.0.0.1:8181"

$argList = @("immune_daemon.py", "--conf", "`"$ConfPath`"")
if ($DryRun) { $argList += "--dry-run" }
if ($Once)   { $argList += "--once" }
$argList += "-v"

Write-Host "Starting immune_daemon | Conf: $ConfPath" -ForegroundColor Cyan

$proc = Start-Process -FilePath $Python `
    -ArgumentList ($argList -join " ") `
    -WorkingDirectory $daemonDir `
    -RedirectStandardOutput $stdoutLog `
    -RedirectStandardError  $stderrLog `
    -PassThru `
    -WindowStyle Hidden

# Record PID for later signaling / stop
$proc.Id | Out-File -FilePath (Join-Path $logDir "immune_daemon.pid") -Encoding ascii
Write-Host "Daemon started (PID $($proc.Id)). Logs -> $logDir" -ForegroundColor Green
