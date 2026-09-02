#!/usr/bin/env python3
"""
Quantum Flex: Alpha Node Packaging Engine (P0 Compliance & Live Gateway Locked)
==============================================================================
Bundles the compiled Sentinel engine, runtime dependencies, PKI identities,
and one-click installer with embedded Node Operator Agreement into a standalone distribution bundle.
"""

import os
import shutil
import zipfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT_DIR / "dist" / "quantum-flex-alpha-node"

def package():
    print("[*] Packaging Quantum Flex Alpha Node Bundle...")
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Copy Binary
    bin_source = ROOT_DIR / "build" / "Release" / "sentinel_push.exe"
    if not bin_source.exists():
        bin_source = ROOT_DIR / "sentinel_push.exe"
    
    if bin_source.exists():
        shutil.copy(bin_source, DIST_DIR / "sentinel_push.exe")
        print(f"    [+] Copied binary: {bin_source.name}")
    else:
        print("    [-] ERROR: sentinel_push.exe not found. Build first.")
        return

    # 2. Copy PostgreSQL Runtime DLLs
    dll_count = 0
    for dll in ROOT_DIR.glob("*.dll"):
        shutil.copy(dll, DIST_DIR / dll.name)
        dll_count += 1
    print(f"    [+] Packaged {dll_count} native runtime DLLs.")

    # 3. Copy PKI trust anchors — PUBLIC CERTIFICATES ONLY.
    #
    # This previously did copytree(ROOT_DIR/"pki"), which shipped ca.key,
    # server.key and client.key to every node operator. ca.key is the root
    # that signed both leaf certs, so anyone holding a bundle could mint a
    # certificate for any node and impersonate the gateway. .gitignore hides
    # *.key from git but does nothing to shutil.
    #
    # A node needs the CA certificate to verify the server, and its own
    # per-node keypair — which must be generated at install time on the
    # operator's machine, never shipped and never shared between nodes.
    pki_src = ROOT_DIR / "pki"
    pki_dest = DIST_DIR / "pki"
    if pki_src.exists():
        copied, skipped = 0, []
        for src in pki_src.rglob("*"):
            if src.is_dir():
                continue
            if src.suffix.lower() in {".key", ".pem", ".p12", ".pfx"}:
                skipped.append(src.name)
                continue
            rel = src.relative_to(pki_src)
            dst = pki_dest / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, dst)
            copied += 1
        print(f"    [+] Embedded {copied} public mTLS certificate(s).")
        if skipped:
            print(f"    [!] Excluded {len(skipped)} private key file(s) from the "
                  f"bundle: {', '.join(sorted(skipped))}")

    # 3b. Fail closed: never emit a bundle containing private key material.
    leaked = [p for p in DIST_DIR.rglob("*")
              if p.is_file() and p.suffix.lower() in {".key", ".pem", ".p12", ".pfx"}]
    if not leaked:
        for p in DIST_DIR.rglob("*"):
            if p.is_file() and p.stat().st_size < 65536:
                try:
                    if "PRIVATE KEY" in p.read_text(errors="ignore"):
                        leaked.append(p)
                except OSError:
                    pass
    if leaked:
        shutil.rmtree(DIST_DIR, ignore_errors=True)
        raise SystemExit(
            "ABORT: private key material found in the staged bundle "
            f"({', '.join(str(p.name) for p in leaked)}). Bundle discarded; nothing packaged."
        )

    # 4. Generate Node Operator Agreement (Legal P0 Shield)
    agreement_file = DIST_DIR / "NODE_OPERATOR_AGREEMENT.txt"
    agreement_file.write_text("""================================================================================
QUANTUM FLEX: ALPHA NODE OPERATOR TERMS & PRIVACY CHARTER (v1.0)
================================================================================

1. INDEPENDENT CONTRACTOR STATUS
The Operator acts strictly as an independent contractor, contributing hardware,
electricity, and radio frequency broadcast telemetry. No employment or agency
relationship is created.

2. ZERO CONTENT SNOOPING & TELEMETRY SCOPE
Quantum Flex only reads publicly broadcast beacon signals (SSID, anonymized BSSID,
RSSI, channel) and local operating system security state. Payload data and network
traffic content are strictly ignored and never intercepted.

3. PRIVACY & OPTOUT EXCLUSION
Networks broadcasting '_optout' or '_nomap' in their SSID are excluded at the edge
and dropped prior to transmission.

4. TOKEN UTILITY REWARDS
Rewards ($QFX) represent algorithmic compensation for verified telemetry work,
uptime, and proof-of-work. Rewards are not an investment, debt, or equity security.
The Operator is solely responsible for local tax reporting (IRS Form 1099-DA).

5. PROHIBITION OF TAMPERING
The Operator agrees not to submit fraudulent, synthetic, or replayed RF beacons.
================================================================================""", encoding="utf-8")
    print(f"    [+] Embedded legal charter: {agreement_file.name}")

    # 5. Generate One-Click Installer with Affirmative Consent
    installer_script = DIST_DIR / "Install-Node.ps1"
    installer_script.write_text("""# Quantum Flex: One-Click Node Installer (Windows Native)
[CmdletBinding()]
param(
    [string]$GatewayEndpoint = "http://100.64.1.29:8080/api/v1/telemetry/submit",
    [string]$NodeId = "$env:COMPUTERNAME-node",
    [switch]$AcceptLicense
)

Clear-Host
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "  QUANTUM FLEX // ALPHA NODE INSTALLER (DePIN Layer 1)" -ForegroundColor Cyan
Write-Host "  Zero-Trust Telemetry Engine | Target Gateway: $GatewayEndpoint" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host ""

# Legal P0 Shield Gate
$AgreementPath = "$PSScriptRoot\\NODE_OPERATOR_AGREEMENT.txt"
if (Test-Path $AgreementPath) {
    Get-Content $AgreementPath | ForEach-Object { Write-Host $_ -ForegroundColor Gray }
    Write-Host ""
}

if (-not $AcceptLicense) {
    $Prompt = Read-Host "Do you accept the Node Operator Terms & Privacy Charter? (Y/N)"
    if ($Prompt -ne 'Y' -and $Prompt -ne 'y') {
        Write-Host "[-] Installation aborted. Node Operator Agreement must be accepted." -ForegroundColor Red
        exit 1
    }
}

$InstallDir = "$env:LOCALAPPDATA\\QuantumFlex"
Write-Host "[*] Target Installation Directory: $InstallDir" -ForegroundColor Yellow

if (!(Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}

Write-Host "[*] Deploying binary and runtime libraries..." -ForegroundColor Yellow
Copy-Item -Path "$PSScriptRoot\\*" -Destination $InstallDir -Recurse -Force

Write-Host "[*] Creating Quantum Flex Background Task..." -ForegroundColor Yellow
$Action = New-ScheduledTaskAction -Execute "$InstallDir\\sentinel_push.exe" -WorkingDirectory $InstallDir
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName "QuantumFlexSentinel" -Action $Action -Trigger $Trigger -Settings $Settings -Description "Quantum Flex Zero-Trust Telemetry Sentinel" -Force | Out-Null

Write-Host "[+] Installation Complete!" -ForegroundColor Green
Write-Host "[+] Alpha Node is registered to Gateway: $GatewayEndpoint" -ForegroundColor Green
Write-Host "[+] To launch telemetry daemon immediately, run: Start-ScheduledTask -TaskName 'QuantumFlexSentinel'" -ForegroundColor Green
""", encoding="utf-8")
    print(f"    [+] Generated hardened installer: {installer_script.name}")

    # 6. Create Zip Archive
    zip_path = ROOT_DIR / "dist" / "quantum-flex-alpha-node-windows-x64.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in DIST_DIR.rglob("*"):
            if file.is_file():
                zf.write(file, arcname=file.relative_to(DIST_DIR))
    print(f"\n[+] Distribution Package Ready: {zip_path}")
    print(f"    Size: {zip_path.stat().st_size / (1024 * 1024):.2f} MB")

if __name__ == "__main__":
    package()
