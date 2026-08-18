<#
.SYNOPSIS
    launch_immune_pod.ps1
    Quantum Flex - Immune Pod Launcher for Windows (Podman / Docker Desktop)
    Creates: qflex-immune-pod (PQC Worker + OPA Sidecar + CBOM Theia)
#>

$ErrorActionPreference = "Continue"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$podName = "qflex-immune-pod"
$bundleServerUrl = "http://127.0.0.1:8182/bundle.tar.gz"

$timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
Write-Host "[$timestamp] IMMUNE POD: Initializing $podName on Windows..." -ForegroundColor Cyan

# 0. Cleanup previous pod
podman pod rm -f $podName 2>$null

# 1. Create Pod
podman pod create --name $podName -p 127.0.0.1:9090:9090 -p 127.0.0.1:8181:8181 --share net
Write-Host "[$timestamp] IMMUNE POD: Pod created with shared network." -ForegroundColor Green

# 2. Deploy OPA sidecar
$opaConfigTmp = Join-Path $env:TEMP "opa-config.yaml"
@"
services:
  default:
    url: $bundleServerUrl
bundles:
  default:
    service: default
    resource: bundle.tar.gz
    polling:
      min_delay_seconds: 1
      max_delay_seconds: 2
"@ | Out-File -FilePath $opaConfigTmp -Encoding utf8

podman run -d `
    --pod $podName `
    --name qflex-opa-sidecar `
    --memory 128m `
    --cpus 0.25 `
    -v "${opaConfigTmp}:/config.yaml:ro" `
    docker.io/openpolicyagent/opa:latest-static `
    run --server --addr 127.0.0.1:8181 --config-file /config.yaml --log-level info

Write-Host "[$timestamp] IMMUNE POD: OPA sidecar deployed." -ForegroundColor Green

# 3. Deploy PQC Worker
if (-not (podman image exists qflex-pqc-worker:latest)) {
    Write-Host "[$timestamp] IMMUNE POD: Building PQC worker container..." -ForegroundColor Cyan
    podman build -t qflex-pqc-worker:latest -f "$scriptDir\Containerfile.pqc-worker" "$scriptDir"
}

$envFile = Join-Path (Split-Path -Parent $scriptDir) ".env"
if (Test-Path $envFile) {
    podman run -d --pod $podName --name qflex-pqc-worker --memory 512m --cpus 1.0 --env-file $envFile qflex-pqc-worker:latest
} else {
    podman run -d --pod $podName --name qflex-pqc-worker --memory 512m --cpus 1.0 qflex-pqc-worker:latest
}

Write-Host "[$timestamp] IMMUNE POD: Deployment complete. OPA at http://127.0.0.1:8181" -ForegroundColor Green
