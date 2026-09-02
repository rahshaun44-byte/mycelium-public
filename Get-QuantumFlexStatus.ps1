<#
.SYNOPSIS
    Get-QuantumFlexStatus.ps1
    Queries and reports the health of Quantum Flex services, ports, and Tailscale connection on Windows.
#>

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "     QUANTUM FLEX: System Status         " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# Match against the command lines Start-QuantumFlexStack.ps1 actually produces:
#   Ollama : ollama ... serve
#   OPA    : opa.exe run -s --addr 127.0.0.1:8181 ...
#   Athena : python -m uvicorn athena_api:app --host 127.0.0.1 --port 8001
#   Amara  : python -m uvicorn dashboard:app  --host 127.0.0.1 --port 8000
#   Immune : python immune_daemon.py
#   Swarm  : python mcp_layer\swarm_worker.py
# Each entry lists alternative substrings; a process matches if its CommandLine
# contains ANY of them (so both the `uvicorn <module>:app` and legacy `<file>.py`
# invocations are recognised).
$services = @(
    @{ Name = "Ollama";          Patterns = @("ollama"); Port = 11434 },
    @{ Name = "OPA-Sidecar";     Patterns = @("opa.exe", "\opa "); Port = 8181 },
    @{ Name = "Athena-Node";     Patterns = @("uvicorn athena_api:app", "athena_api:app", "athena_api.py"); Port = 8001 },
    @{ Name = "Amara-Dashboard"; Patterns = @("uvicorn dashboard:app", "dashboard:app", "dashboard.py"); Port = 8000 },
    @{ Name = "Immune-Daemon";   Patterns = @("immune_daemon.py", "immune_daemon"); Port = $null },
    @{ Name = "Swarm-Worker";    Patterns = @("swarm_worker.py", "swarm_worker"); Port = $null }
)

$procs = Get-CimInstance Win32_Process -Filter "Name LIKE 'python%' OR Name = 'ollama.exe' OR Name = 'opa.exe'"

foreach ($svc in $services) {
    $matched = $procs | Where-Object {
        $cl = $_.CommandLine
        if (-not $cl) { return $false }
        $hit = $false
        foreach ($p in $svc.Patterns) { if ($cl.ToLower().Contains($p.ToLower())) { $hit = $true } }
        $hit
    }
    $running = [bool]$matched

    if ($running) {
        $pids = ($matched | ForEach-Object { $_.ProcessId }) -join ", "
        Write-Host "  [RUNNING] $($svc.Name.PadRight(20)) PID(s): $pids" -ForegroundColor Green
    } else {
        Write-Host "  [STOPPED] $($svc.Name.PadRight(20))" -ForegroundColor Gray
    }

    if ($svc.Port) {
        $conn = Get-NetTCPConnection -LocalPort $svc.Port -State Listen -ErrorAction SilentlyContinue
        $listening = [bool]$conn
        if ($listening) {
            Write-Host "              Port $($svc.Port): LISTENING" -ForegroundColor Green
        } else {
            Write-Host "              Port $($svc.Port): Inactive" -ForegroundColor DarkGray
        }
        if ($running -ne $listening) {
            $note = if ($listening) { "process not matched but port IS listening" } else { "process matched but port NOT listening" }
            Write-Host "              [!] INCONSISTENT: $note" -ForegroundColor Yellow
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
