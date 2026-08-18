<#
.SYNOPSIS
    Stop-QuantumFlex.ps1
    Gracefully halts all Quantum Flex processes on Windows.
#>

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  QUANTUM FLEX: Windows Service Stopper  " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

$targets = @("athena_api.py", "dashboard.py", "tripwire_daemon.py", "immune_daemon.py", "main.py")

$pythonProcesses = Get-CimInstance Win32_Process -Filter "Name LIKE 'python%.exe'"

$stopped = 0
foreach ($proc in $pythonProcesses) {
    $cmd = $proc.CommandLine
    foreach ($target in $targets) {
        if ($cmd -and $cmd.Contains($target)) {
            Write-Host "[*] Stopping PID $($proc.ProcessId): $target" -ForegroundColor Yellow
            Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
            $stopped++
            break
        }
    }
}

if ($stopped -eq 0) {
    Write-Host "[i] No active Quantum Flex Python services found." -ForegroundColor Gray
} else {
    Write-Host "[+] Successfully stopped $stopped Quantum Flex service process(es)." -ForegroundColor Green
}
