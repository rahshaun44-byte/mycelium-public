<#
.SYNOPSIS
    intercept_url.ps1
    Unmask shortened URLs and log their true destination for OSINT analysis on Windows.
.EXAMPLE
    .\intercept_url.ps1 "https://bit.ly/example"
#>

param(
    [Parameter(Mandatory=$true, Position=0)]
    [string]$TargetUrl
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$logFile = Join-Path $scriptDir "intercepted_urls.log"

Write-Host "[*] Intercepting URL: $TargetUrl" -ForegroundColor Cyan

$userAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"

try {
    $request = [System.Net.HttpWebRequest]::Create($TargetUrl)
    $request.AllowAutoRedirect = $false
    $request.UserAgent = $userAgent
    $request.Method = "HEAD"
    $response = $request.GetResponse()
    $trueDestination = $response.GetResponseHeader("Location")
    $response.Close()
} catch [System.Net.WebException] {
    if ($_.Response) {
        $trueDestination = $_.Response.GetResponseHeader("Location")
        $_.Response.Close()
    } else {
        $trueDestination = $null
    }
} catch {
    $trueDestination = $null
}

$timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")

if ([string]::IsNullOrWhiteSpace($trueDestination)) {
    Write-Host "[!] No redirect (Location header) found for $TargetUrl" -ForegroundColor Yellow
    "$timestamp - $TargetUrl - [NO REDIRECT FOUND]" | Out-File -FilePath $logFile -Append -Encoding utf8
} else {
    Write-Host "[+] Unmasked Destination: $trueDestination" -ForegroundColor Green
    "$timestamp - $TargetUrl - $trueDestination" | Out-File -FilePath $logFile -Append -Encoding utf8
}

Write-Host "[*] Analysis logged to $logFile" -ForegroundColor Cyan
