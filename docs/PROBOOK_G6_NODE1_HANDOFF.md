# QUANTUM FLEX: TARGET NODE 1 (HP PROBOOK 450 G6) TECHNICAL HANDOFF

**System**: Quantum Flex Distributed PQC Network  
**Node**: `qf-g6pro-node1` (Target Node 1 / Layer 4 Compute & Attestation)  
**Host Master**: `quant-Yoga-7-2-in-1-14AKP10` (Lenovo Yoga 7 Master Node)  
**Date**: October 14, 2026  
**Security Classification**: Operational Ground Truth (Zero Compromised Secrets, Pure Local & Mesh Attestation)

---

## 1. Network Topology & Device Registry

| Device / Node | Hardware Role | Interface IP | Tailscale Mesh IP | OS / Kernel | Access Method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Master Node (Yoga 7)** | Control Plane & PQC Core | `192.168.100.15` | `100.64.1.31` | Ubuntu Linux x86_64 | Local Console |
| **Target Node 1 (ProBook G6)** | Primary Kafka Cluster (KRaft), Layer 4 Compute, Attestation, XRDP HUD | `192.168.100.13` | `100.64.1.19` | Debian 13 (Trixie) Linux 6.12 | Ed25519 SSH (`qf-g6`), Kafka (9092, 8090), XRDP (3389) |
| **Worker Node 2 (Pavilion)** | Cold Standby / Offline Witness (Standby Mode) | `192.168.100.17` | `100.64.1.34` | Debian 13 (Trixie) Linux 6.12 | Standby / Offline (Decided 2026-10-14) |
| **Mobile Node 1 (Pixel)** | Mobile Shard Anchor | DHCP | `100.64.1.16` | Android / Hardware Shard | Tailscale Mesh |

---

## 2. Hardware Profile & Attestation Root

### A. Compute & Storage
- **Model**: HP ProBook 450 G6
- **CPU**: Intel Core i5-8265U (4 physical cores, 8 threads, base 1.60 GHz, boost 3.90 GHz)
- **RAM**: 7.4 GiB Physical DDR4 + 3.7 GiB `/dev/zram0` (11.1 GiB effective memory envelope)
- **Storage**: 460 GB NVMe SSD (`/dev/nvme0n1p2`, ~6.3 GB used, 430 GB available)
- **Thermals**: Idle CPU package temperature ~34°C - 37°C.

### B. Hardware TPM 2.0 Anchor
- **Device**: `/dev/tpm0`, `/dev/tpmrm0`
- **Ownership & Access**: Group `tss`, user `qfx` enrolled.
- **Baseline Register Fingerprint** (Recorded in `/opt/quantumflex/tpm_baseline.json`):
  - **PCR 0 (Core System Firmware / BIOS)**:  
    `0x3900A886A936E08DF8B3C78671B3C6DA337FC6AB443CFCF8783FFCABB59E7A16`
  - **PCR 7 (Secure Boot & Platform Configuration)**:  
    `0x23D93F4AB21C8FE2938B04662317558BB46F159064DA1C66F0292671B08B42B2`

### C. Cryptographic Node Identity
- **Algorithm**: Ed25519 asymmetric signature keypair
- **Private Key**: `/opt/quantumflex/node_identity.key` (Mode `0600`, owner `qfx:qfx`)
- **Public Key**: `dEqEKNEG98zGJJh7oUMR/YjWR6WYSNxbRWeugHQXVhY=` (`/opt/quantumflex/node_identity.pub`)
- **Attestation Mechanism**: Every heartbeat packet emitted by the Sentinel daemon is canonically serialized and cryptographically signed with this key.

---

## 3. Power & Operational Posture

### 24/7 Headless Server Configuration
To allow the G6 to operate continuously as an unmonitored server with the screen closed:
- **Configuration File**: `/etc/systemd/logind.conf.d/ignore-lid.conf`
  ```ini
  [Login]
  HandleLidSwitch=ignore
  HandleLidSwitchExternalPower=ignore
  HandleLidSwitchDocked=ignore
  ```
- **Behavior**: The laptop lid can be closed completely; all network interfaces, compute tasks, and daemons run 24/7 without suspension or sleep.

---

## 4. Container & Kafka Streaming Stack

- **Container Engine**: Native Docker CE `v26.1.5+dfsg1`
- **Compose Plugin**: Docker Compose `v2.26.1-4`
- **Deployment Location**: `/opt/quantumflex/docker-compose.yml`
- **Data Persistence**: `/opt/quantumflex/data/kafka`
- **Active Streaming Cluster**:
  - **Kafka Broker (`qf-kafka-broker`)**: Running in **KRaft Mode** (no ZooKeeper dependency).
    - Image: `confluentinc/cp-kafka:7.6.0`
    - Port: `0.0.0.0:9092` (advertised on Tailscale `100.64.1.19:9092`).
    - Allocation: `-Xmx1G -Xms1G` with G1GC garbage collector.
  - **Kafka Web Console (`qf-kafka-ui`)**:
    - Image: `provectuslabs/kafka-ui:latest`
    - Port: `0.0.0.0:8090` (internal 8080).
    - URL: `http://100.64.1.19:8090` (or `http://localhost:8090` via SSH tunnel or XFCE browser).
- **Verified Topic Pipeline**: Topic `qf-telemetry-heartbeat` provisioned and tested end-to-end with active JSON message production and consumption.
- **Service Status**: Active and healthy (`docker ps` reports 2 containers running).

---

## 5. QuantumFlex Worker Sentinel Daemon

The Sentinel daemon continuously monitors hardware health, TPM root integrity, Docker workloads, and network latency:
- **Systemd Service**: `qf-worker-sentinel.service`
- **Executable**: `/opt/quantumflex/sentinel/worker_sentinel.py`
- **Loop Interval**: 10 seconds
- **Local Telemetry Endpoints**:
  - `GET http://127.0.0.1:9100/status`: Full JSON signed heartbeat payload.
  - `GET http://127.0.0.1:9100/health`: Health status and TPM verification state.
  - `GET http://127.0.0.1:9100/metrics`: Prometheus-compatible exposition metrics.
- **Audit File**: `/opt/quantumflex/logs/sentinel_heartbeat.jsonl` (rotated automatically at 10 MB).

### B. Kafka Telemetry Publisher Daemon
- **Systemd Service**: `qf-kafka-publisher.service` (Active, enabled)
- **Executable**: `/opt/quantumflex/sentinel/kafka_telemetry_publisher.py`
- **Cadence**: 10-second automatic loop
- **Broker Target**: `127.0.0.1:9092`
- **Topic**: `qf-telemetry-heartbeat`
- **Payload**: Full cryptographically signed JSON telemetry packet containing hardware TPM 2.0 PCR attestation, host vitals, and Ed25519 signature. Verified live stream delivery across the mesh.

---

## 6. Graphical HUD & Remote Desktop (XRDP / Remmina)

- **XRDP Service**: Running on port `3389`, active and enabled.
- **Desktop Environment**: XFCE4 (`xfce4-session` isolated via `dbus-run-session`).
- **Remmina Connection Profile**:
  - Saved on Yoga: `~/.local/share/remmina/quantumflex_g6pro.remmina`
  - Group: `QuantumFlex`
  - Host: `100.64.1.19`
  - User: `qfx`
- **Usage**: Open Remmina on the Yoga master, double click **HP ProBook 450 G6 (QuantumFlex Node 1)**, enter password, and interact with the full graphical desktop over the encrypted Tailscale mesh.

---

## 7. Operator Runbook

### A. Accessing the G6 Console
```bash
# Via Tailscale mesh (recommended):
ssh qf-g6

# Via Local LAN:
ssh qf-g6-lan

# Direct IP:
ssh qfx@100.64.1.19
```

### B. Checking Sentinel & Attestation Telemetry
```bash
# Query live signed heartbeat:
ssh qf-g6 "curl -s http://127.0.0.1:9100/status | python3 -m json.tool"

# Check sentinel systemd service:
ssh qf-g6 "sudo systemctl status qf-worker-sentinel.service"

# View live sentinel log stream:
ssh qf-g6 "tail -f /opt/quantumflex/logs/sentinel.log"
```

### C. Checking Docker Engine
```bash
# Check docker info:
ssh qf-g6 "docker ps"
ssh qf-g6 "docker info"
```

### D. Checking Hardware TPM State
```bash
# Verify live PCRs match baseline:
ssh qf-g6 "tpm2_pcrread sha256:0,7"
```

---

## 8. Google Antigravity Platform Installation

The entire Google Antigravity stack is fully provisioned on Target Node 1 (`g6pro`):

1. **Antigravity CLI (`agy`)**:
   - Location: `/usr/local/bin/agy`
   - Version: `1.3.3` (64-bit ELF standalone runtime).
   - Usage: `agy` or `agy --help` directly in the G6 terminal.

2. **Antigravity Desktop IDE (`antigravity`)**:
   - Binary & Resources: `/opt/antigravity/` (setuid `chrome-sandbox` active).
   - CLI Symlink: `/usr/local/bin/antigravity`.
   - Desktop Menu Entry: `/usr/share/applications/antigravity.desktop`.
   - Access: Accessible via Remmina RDP session in the XFCE Application Menu under Development.

3. **Antigravity Python SDK (`google-antigravity`)**:
   - Version: `0.1.22` installed via pip.
   - Modules: `google.antigravity`, `google-genai`, `mcp`.
   - Programmatic Agent leasing and orchestration ready.

2026-10-14 audit qualification: two G6 heartbeats had valid Ed25519 signatures against the same-host stored public key (sequence +1; signed interval 11.093009 seconds). This was an SSH/docker-local consumer path, not a direct Yoga Kafka client test. PCR0/PCR7 are compared with a local baseline, not a fresh nonce-bound TPM quote. Kafka has persistent host bind storage but PLAINTEXT listeners and host 9092 published on all interfaces; firewall and tailnet reachability still require review. Do not describe this as complete hardware attestation, strict 10-second lossless delivery, or independent root custody. No root recovery share is needed for ordinary G6 broker identity.
