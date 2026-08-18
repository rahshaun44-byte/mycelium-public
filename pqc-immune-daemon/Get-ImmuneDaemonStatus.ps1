# Get-ImmuneDaemonStatus.ps1
$pidFile = Join-Path $PSScriptRoot "logs\immune_daemon.pid"
$logFile = Join-Path $PSScriptRoot "logs\immune_daemon.log"

if (Test-Path $pidFile) {
    $daemonPid = Get-Content $pidFile
    $proc = Get-Process -Id $daemonPid -ErrorAction SilentlyContinue
    if ($proc) {
        Write-Host "immune_daemon : RUNNING (PID $daemonPid)" -ForegroundColor Green
        Write-Host "Start time    : $($proc.StartTime)" -ForegroundColor Cyan
    } else {
        Write-Host "immune_daemon : PID file exists but process is dead" -ForegroundColor Red
    }
} else {
    Write-Host "immune_daemon : NOT RUNNING" -ForegroundColor Gray
}

if (Test-Path $logFile) {
    Write-Host "`nLast 8 log lines:" -ForegroundColor Yellow
    Get-Content $logFile -Tail 8
}
