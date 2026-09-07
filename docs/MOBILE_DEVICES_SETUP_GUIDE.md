# Quantum Flex: Dual Mobile Nodes Operations & Setup Guide

This guide details the network topology, security postures, and setup instructions for both mobile nodes connected to the Quantum Flex node stack over Tailscale.

---

## 1. Tailscale Mesh Topology & IP Assignments

| Node / Device | Hardware Role | Tailscale IP | MagicDNS Hostname | Operating Environment |
| :--- | :--- | :--- | :--- | :--- |
| **Fedora Yoga 7 (Master)** | Control Plane & PQC Engine |  |  /  | Fedora 44 x86_64 |
| **Google Pixel 11 Pro** | Hardware Root of Trust / OOB Signer |  |  | GrapheneOS / Titan M2 |
| **Samsung Galaxy S23 FE** | Mobile Ops Console & Terminal |  |  | Android / Knox / DeX |

---

## 2. Cryptographic & Security Division of Roles

### A. Google Pixel 11 Pro (Hardware Enclave Anchor)
- **Primary Function**: Shamir Shard Custodian & Out-of-Band (OOB) Quorum Signer.
- **Hardware Isolation**: Titan M2 Security Enclave.
- **Key Storage**: Holds Shamir Shard #2 in hardware keystore.
- **Execution**: Participates in 2-of-3 threshold recombination. Does **not** run intensive Frodo matrix arithmetic; acts as authorization gatekeeper for engine  and circuit-breaker overrides.

### B. Samsung Galaxy S23 FE (Operational Workstation)
- **Primary Function**: Field Operations, AMARA Dashboard monitoring, and mobile MCP agent execution.
- **Hardware Isolation**: Samsung Knox Vault.
- **Desktop Mode**: Samsung DeX turns the S23 FE into an external monitor Linux workstation running Termux and local AI agents.

---

## 3. Fast Setup via Termux / Mobile Shell

### Method 1: Local Kit Unpack (Recommended)
Transfer  to either phone via Tailscale Drop or ADB, then run:

./
./mcp_config.json
./qflex_cli.py
./setup-mobile.sh

### Method 2: Direct Execution from Host
From Termux on either phone (with Tailscale connected):



---

## 4. Mobile MCP Server Configuration

To connect mobile Claude Code, Antigravity, or Open-WebUI agents running on either phone to the master engine:



**Config File Paths on Android / Termux**:
- Claude CLI: 
- Mobile Root: 

---

## 5. Mobile CLI Reference ()

Once bootstrapped, both mobile devices provide the  CLI:

| Command | Action |
| :--- | :--- |
|  | Query health of all node engines, memory, and Euclidean Drive ($). |
|  | Query the neural RAG knowledge base from your phone. |
|  | Display active MCP server endpoints and registered tools. |
|  | Print direct browser links for the AMARA Dashboard. |

---

## 6. Mobile Browser Access

Open Samsung Internet or Vanadium/Chrome on either phone while Tailscale is active:
- **AMARA Dashboard**: 
- **API Status**: 
- **MCP SSE Stream**: 
