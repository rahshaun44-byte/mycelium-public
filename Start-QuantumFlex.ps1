<#
.SYNOPSIS
    Start-QuantumFlex.ps1
    Starts all Quantum Flex Python services as managed Windows background processes.
#>

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$logsDir = Join-Path $root "logs"
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
}

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  QUANTUM FLEX: Windows Service Starter  " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# Load .env if present
$envFile = Join-Path $root ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | Where-Object { $_ -match "^[A-Za-z0-9_]+=" } | ForEach-Object {
        $parts = $_ -split "=", 2
        [System.Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim(), [System.EnvironmentVariableTarget]::Process)
    }
    Write-Host "[+] Loaded environment variables from .env" -ForegroundColor Green
}

# Resolve Python executable
$pythonExe = $null
$candidates = @(
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
    "C:\Python312\python.exe",
    "C:\Python311\python.exe"
)
foreach ($c in $candidates) {
    if (Test-Path $c) {
        $pythonExe = $c
        break
    }
}
if (-not $pythonExe) {
    $pythonExe = "python"
}
Write-Host "[+] Using Python: $pythonExe" -ForegroundColor Cyan

$services = @(
    @{
        Name = "Athena-Node"
        Script = "mcp_layer\athena_api.py"
        Args = ""
        Pattern = "athena_api.py"
    },
    @{
        Name = "Amara-Dashboard"
        Script = "amara\dashboard.py"
        Args = ""
        Pattern = "dashboard.py"
    },
    @{
        Name = "Api-Node"
        Script = "api_node\main.py"
        Args = ""
        Pattern = "api_node\main.py"
    },
    @{
        Name = "Quantum-Flex-MCP"
        Script = "mcp_layer\quantum_flex_mcp.py"
        Args = ""
        Pattern = "quantum_flex_mcp.py"
    },
    @{
        Name = "Sentinel-Tripwire"
        Script = "sentinel\tripwire_daemon.py"
        Args = ""
        Pattern = "tripwire_daemon.py"
    },
    @{
        Name = "Immune-Daemon"
        Script = "pqc-immune-daemon\immune_daemon.py"
        Args = ""
        Pattern = "immune_daemon.py"
    }
)

# 1. Clean up any existing instances of these services
$procs = Get-CimInstance Win32_Process -Filter "Name LIKE 'python%.exe'"
foreach ($svc in $services) {
    $matched = $procs | Where-Object { $_.CommandLine -and $_.CommandLine.Contains($svc.Pattern) }
    if ($matched) {
        foreach ($m in $matched) {
            Write-Host "[*] Stopping existing $($svc.Name) (PID: $($m.ProcessId))..." -ForegroundColor DarkYellow
            Stop-Process -Id $m.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }
}

Start-Sleep -Seconds 1

# 2. Start all services with explicit WorkingDirectory and unbuffered output
foreach ($svc in $services) {
    $scriptPath = Join-Path $root $svc.Script
    if (Test-Path $scriptPath) {
        $logOut = Join-Path $logsDir "$($svc.Name).log"
        $logErr = Join-Path $logsDir "$($svc.Name).err.log"
        Write-Host "[*] Starting $($svc.Name)..." -ForegroundColor Yellow
        Start-Process -FilePath $pythonExe -ArgumentList "-u `"$scriptPath`" $($svc.Args)" -WorkingDirectory $root -RedirectStandardOutput $logOut -RedirectStandardError $logErr -WindowStyle Hidden
        Write-Host "    -> Started (Logs: $logOut)" -ForegroundColor Green
    } else {
        Write-Host "[!] Script not found: $scriptPath" -ForegroundColor Red
    }
}

Write-Host "`nAll 6 Quantum Flex services started." -ForegroundColor Green
Write-Host "Run .\Get-QuantumFlexStatus.ps1 to inspect live status." -ForegroundColor Cyan
