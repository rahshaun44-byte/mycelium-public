---
name: quantumflex-mobile-mesh
description: >-
  Mobile node provisioning (QF-M1), ADB cryptographic synchronization, Capacitor
  Cockpit APK deployment, Mobile Web HUD on HTTPS 443, and mobile CLI operations.
---

# QuantumFlex Mobile Mesh & Edge Provisioning Playbook

This skill provides procedures for deploying, synchronizing, and operating QuantumFlex mobile nodes (Google Pixel 11 Pro) across ADB and the encrypted Tailscale mesh.

---

## 1. Supported Mobile Nodes

| Device Identifier | Hardware Model | Connection Modes | Primary Role |
|---|---|---|---|
| `pixel11pro` | Google Pixel 11 Pro | ADB USB / Wi-Fi, Tailnet | Primary Operator Tactical HUD & Mobile Sentinel |

---

## 2. Cryptographic Mobile Node Synchronization (`sync_mobile_nodes.py`)

All files deployed to mobile devices are pre-verified with Ed25519 signatures and post-validated on-device via `sha256sum`.

### Inspection & Health Check (Zero Mutations):
```bash
/home/quant/mycelium/venv/bin/python3 scripts/sync_mobile_nodes.py
```
*Checks:* ADB connection status, device authorization, Tailscale reachability, and compares local vs on-device SHA-256 digests.

### Deploy Verified Scripts & Manifests:
Pushes `qflex_cli.py`, `setup-mobile.sh`, and the Web HUD to `/sdcard/Download/QuantumFlex/`:
```bash
/home/quant/mycelium/venv/bin/python3 scripts/sync_mobile_nodes.py --push
```

### Full Deployment (Files + Cockpit APK):
Installs or updates the native Capacitor Cockpit APK (`com.quantumflex.cockpit`) after verifying the APK cryptographic signature:
```bash
/home/quant/mycelium/venv/bin/python3 scripts/sync_mobile_nodes.py --push --apk
```

### Targeting a Specific Device Serial:
```bash
/home/quant/mycelium/venv/bin/python3 scripts/sync_mobile_nodes.py --device <SERIAL> --push
```

---

## 3. Signing Mobile Artifacts (`sign_mobile_artifacts.py`)

Before distributing updated mobile scripts or APKs, re-sign the payloads:
```bash
/home/quant/mycelium/venv/bin/python3 scripts/sign_mobile_artifacts.py --sign
```
To verify all mobile artifact signatures locally:
```bash
/home/quant/mycelium/venv/bin/python3 scripts/sign_mobile_artifacts.py --verify
```

---

## 4. Mobile Web HUD via Tailscale Mesh

Enables encrypted HTTPS access on port 443 to the QuantumFlex Mobile Cockpit UI over Tailscale:
```bash
./scripts/enable_mobile_hud.sh
```
*Access URL:* `https://quant-yoga-7-2-in-1-14akp10.example-tailnet.ts.net/` on any authorized device in the Tailnet.

---

## 5. Mobile CLI Operations (`mobile/qflex_cli.py`)

Run on-device or via ADB shell:
```bash
python3 /sdcard/Download/QuantumFlex/qflex_cli.py status
python3 /sdcard/Download/QuantumFlex/qflex_cli.py ping
python3 /sdcard/Download/QuantumFlex/qflex_cli.py telemetry --tail 20
```
