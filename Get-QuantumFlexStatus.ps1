<#
.SYNOPSIS
    Get-QuantumFlexStatus.ps1
    Queries and reports the health of Quantum Flex services, ports, and Tailscale connection on Windows.
#>

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "     QUANTUM FLEX: System Status         " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

$services = @(
    @{ Name = "Athena-Node"; Pattern = "athena_api.py"; Port = 8001 },
    @{ Name = "Amara-Dashboard"; Pattern = "dashboard.py"; Port = 8000 },
    @{ Name = "Api-Node"; Pattern = "api_node\main.py"; Port = 8080 },
    @{ Name = "Quantum-Flex-MCP"; Pattern = "quantum_flex_mcp.py"; Port = 9000 },
    @{ Name = "Sentinel-Tripwire"; Pattern = "tripwire_daemon.py"; Port = $null },
    @{ Name = "Immune-Daemon"; Pattern = "immune_daemon.py"; Port = $null }
)

$procs = Get-CimInstance Win32_Process -Filter "Name LIKE 'python%.exe'"

foreach ($svc in $services) {
    $matched = $procs | Where-Object { $_.CommandLine -and $_.CommandLine.Contains($svc.Pattern) }
    if ($matched) {
        $pids = ($matched | ForEach-Object { $_.ProcessId }) -join ", "
        Write-Host "  [RUNNING] $($svc.Name.PadRight(20)) PID(s): $pids" -ForegroundColor Green
    } else {
        Write-Host "  [STOPPED] $($svc.Name.PadRight(20))" -ForegroundColor Gray
    }
    
    if ($svc.Port) {
        $conn = Get-NetTCPConnection -LocalPort $svc.Port -ErrorAction SilentlyContinue
        if ($conn) {
            Write-Host "              Port $($svc.Port): LISTENING" -ForegroundColor Green
        } else {
            Write-Host "              Port $($svc.Port): Inactive" -ForegroundColor DarkGray
        }
    }
}

Write-Host "-----------------------------------------" -ForegroundColor Cyan
Write-Host "  TAILSCALE MESH STATUS:                 " -ForegroundColor Cyan
Write-Host "-----------------------------------------" -ForegroundColor Cyan

try {
    $tsOut = tailscale status 2>&1
    Write-Host $tsOut -ForegroundColor White
} catch {
    Write-Host "  Tailscale CLI not reachable" -ForegroundColor Red
}

Write-Host "=========================================" -ForegroundColor Cyan
