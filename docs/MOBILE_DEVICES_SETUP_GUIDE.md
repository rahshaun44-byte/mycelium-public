# Quantum Flex: Dual Mobile Nodes Operations & Setup Guide

This guide details the network topology, security postures, and setup instructions for mobile nodes connected to the Quantum Flex distributed stack over Tailscale mesh and local Wi-Fi.

---

## 1. Mesh Topology & IP Registry

| Node / Device | Hardware Role | Interface IP | Tailscale Mesh IP | MagicDNS Hostname | Operating Environment |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Master Node (Yoga 7)** | Control Plane & PQC Core | `192.168.100.11` | `100.64.1.17` | `fedora` | Fedora Linux 44 x86_64 |
| **Worker Node 2 (Pavilion)** | Stream Compute / KRaft Kafka | `192.168.100.17` | `100.64.1.34` | `qf-pavilion-worker` | Debian 13 (Trixie) Linux |
| **Mobile Node 1 (Pixel 11 Pro)** | Hardware Shard Anchor / OOB Signer | DHCP | `100.64.1.18` | `pixel-11-pro` | GrapheneOS / Titan M2 |
| **Mobile Node 2 (Galaxy S23 FE)** | Mobile Ops Console & Terminal | DHCP | `100.64.1.32` | `rahshauns-s23-fe` | Android / Knox Vault / DeX |

---

## 2. Cryptographic & Security Division of Roles

### A. Google Pixel 11 Pro (Hardware Enclave Anchor)
- **Primary Function**: Shamir Shard Custodian & Out-of-Band (OOB) Quorum Signer.
- **Hardware Isolation**: Titan M2 Security Enclave.
- **Key Storage**: Holds Shamir Shard #2 in hardware keystore.
- **Execution**: Participates in 2-of-3 threshold recombination. Does **not** run intensive Frodo matrix arithmetic; acts as authorization gatekeeper for engine unlocking and circuit-breaker overrides.

### B. Samsung Galaxy S23 FE (Operational Workstation)
- **Primary Function**: Field Operations, AMARA Dashboard monitoring, and mobile MCP agent execution.
- **Hardware Isolation**: Samsung Knox Vault.
- **Desktop Mode**: Samsung DeX turns the S23 FE into an external monitor Linux workstation running Termux and local AI agents.

---

## 3. Fast Setup via Termux / Mobile Shell

### Method 1: Mobile Web App (Zero-Install PWA)
Open either browser (Chrome, Vanadium, Samsung Internet) over Tailscale:
- **Quantum Flex Mobile HUD**: `http://100.64.1.17:9050`
- **PWA Direct Download Portal**: `http://100.64.1.17:9050/download`
- Tap **"Add to Home Screen"** to install standalone mobile progressive web app.
- Toggle between **Wi-Fi (`192.168.100.11:9050`)** and **Tailscale (`100.64.1.17:9050`)** using the top host bar.

### Method 2: Termux Mobile CLI Kit
From Termux on either phone (with Tailscale connected):
```bash
# Fetch mobile status directly from master
curl -s http://100.64.1.17:9050/api/status | jq .

# Query live mesh topology
curl -s http://100.64.1.17:9050/api/mesh/nodes | jq .
```

---

## 4. Mobile Browser Endpoints Summary

| Service | Tailscale Mesh URL | Local Wi-Fi URL | Purpose |
| :--- | :--- | :--- | :--- |
| **Quantum Flex Mobile Bot HUD** | `http://100.64.1.17:9050` | `http://192.168.100.11:9050` | Teammate AI chat, mesh status, alert triage |
| **AMARA Biological HUD** | `http://100.64.1.17:8000` | `http://192.168.100.11:8000` | Vitals, Euclidean Drive, memory gauges |
| **Kafka UI Stream Console** | `http://100.64.1.34:8090` | `http://192.168.100.17:8090` | Real-time Kafka topic inspector on Pavilion |
| **Core API Gateway Health** | `http://100.64.1.17:8080/health` | `http://192.168.100.11:8080/health` | API gate status & telemetry health |
| **Quantum Flex MCP SSE** | `http://100.64.1.17:9000/sse` | `http://192.168.100.11:9000/sse` | Model Context Protocol stream |

---

## 5. Mobile Security & Compliance Mandate
- **Pre-Validation Notice**: All telemetry payloads transmitted to mobile devices strictly enforce `cmvp_certificate: null`.
- **Zero Public Exposure**: Mobile endpoints are accessible exclusively via authenticated WireGuard Tailscale tunnels or WPA3-secured local LAN. No public ports or dynamic DNS forwarding exist.
