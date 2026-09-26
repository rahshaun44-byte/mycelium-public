# QUANTUM FLEX: WORKER NODE 2 (HP PAVILION) TECHNICAL HANDOFF

**System**: Quantum Flex Distributed PQC Network  
**Node**: `qf-pavilion-worker` (Worker Node 2 / Layer 4 Stream Compute)  
**Host Master**: `fedora` (Lenovo Yoga 7 Master Node)  
**Date**: September 9, 2026  
**Security Classification**: Operational Ground Truth (Zero Public Exposure)

---

## 1. Network Topology & Device Registry

| Device / Node | Hardware Role | Interface IP | Tailscale Mesh IP | OS / Kernel | Access Method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Master Node (Yoga 7)** | Control Plane & PQC Core | `192.168.100.11` | `100.64.1.17` | Fedora 44 x86_64 | Local Console |
| **Worker Node 2 (Pavilion)** | Stream Compute / Kafka Cluster | `192.168.100.17` | `100.64.1.34` | Debian 13 (Trixie) Linux 6.12 | Ed25519 Passwordless SSH |
| **Mobile Node 1 (Pixel 11)** | Titan M2 Hardware Shard Anchor | DHCP | `100.64.1.18` | GrapheneOS / Titan M2 | Tailscale Mesh |
| **Mobile Node 2 (S23 FE)** | Field Ops / Matrix HUD Terminal | DHCP | `100.64.1.32` | Android / Knox / DeX | Tailscale Mesh |

---

## 2. HP Pavilion Provisioning Specifications

### A. Hardware Profile
- **CPU**: Intel Celeron 450 (1 physical core @ 2.20 GHz, x86_64)
- **RAM**: 1.9 GB DDR (Active allocation: ~570 MB used, 1.37 GB free, 0 B swap)
- **Storage**: 456 GB HDD (`/dev/sda1`, ~1.8 GB used, 432 GB available)
- **Lid Power Policy**: `HandleLidSwitch=ignore` in `/etc/systemd/logind.conf.d/ignore-lid.conf`  
  *(Lid can be closed completely; system runs silently 24/7 without suspending)*.

### B. Software & Runtime Stack
- **OS Base**: Debian GNU/Linux 13 (Trixie) minimal netinst.
- **Package Repositories**: Repaired `/etc/apt/sources.list` targeting official Debian Trixie security and non-free firmware channels.
- **Zero-Trust Mesh**: Tailscale v1.102.3 active with Tailscale SSH capability.
- **Container Engine**: Native Docker CE v29.8.0 + Docker Compose Plugin v5.5.1.
- **Authentication**: Ed25519 key authorized for `root` (Yoga 7 public key `AAAAC3NzaC1lZDI1NTE5AAAAINBdRhbDNmGhmV5xxONtajpjb1q/DcS3bkHQ1bu18p5n`).

---

## 3. Layer 4 Kafka Cluster Architecture

The Kafka streaming cluster runs in **KRaft Mode** (Kafka Raft Metadata mode without ZooKeeper dependency) deployed at `/opt/quantumflex/docker-compose.yml`.

### A. Network & Interface Binding Policy
To prevent unintended exposure on the local home router, all container ports are bound **strictly to the Tailscale mesh IP (`100.64.1.34`)**:
- **Kafka Broker**: `100.64.1.34:9092`
- **Kafka-UI Console**: `100.64.1.34:8090`
- **Inter-broker internal network**: `29092` (isolated within `quantumflex_default` bridge).

### B. Memory & Resource Clamping
- **Kafka Broker (`qf-kafka-broker`)**:
  - Heap: `-Xmx512m -Xms512m`
  - Memory Limit: `900M`
- **Kafka Web UI (`qf-kafka-ui`)**:
  - Heap: `-Xmx256m`
  - Memory Limit: `400M`

---

## 4. Master Node (Yoga 7) Strata Status

| Stratum | Service | Local Port | Status | Function |
| :--- | :--- | :--- | :--- | :--- |
| **Stratum 0** | Open Policy Agent | `127.0.0.1:8181` | **ONLINE** | Fallback policy engine & Invariant Gate |
| **Stratum 0** | Track C Invariant Gate | In-Memory | **ADMIT** | Universal Reserve Invariant ($R \ge O$) |
| **Stratum 1** | Amara Matrix PostgreSQL | `127.0.0.1:5432` | **ONLINE** | Hardened containerized telemetry database |
| **Stratum 2** | Quantum Flex Engine | `127.0.0.1:9443` | **LOCKED** | Genesis sealed (193 B); awaiting SSS quorum |
| **Stratum 3** | AMARA Intelligence HUD | `127.0.0.1:8000` | **ONLINE** | Real-time biological vitals & Euclidean Drive |
| **Stratum 3** | Athena Neural RAG | `127.0.0.1:8001` | **ONLINE** | ChromaDB vector memory & knowledge base |
| **Stratum 3** | API Gateway | `127.0.0.1:8080` | **ONLINE** | Telemetry ingestion endpoint |
| **Stratum 3** | Quantum Flex MCP Server | `127.0.0.1:9000` | **ONLINE** | Model Context Protocol SSE stream |

---

## 5. Operator Runbook

### A. Accessing the HP Pavilion
From your Yoga laptop:
```bash
# Connect via local Wi-Fi:
ssh root@192.168.100.17

# Connect over Tailscale mesh (from anywhere):
ssh root@100.64.1.34
```

### B. Managing Kafka Cluster
```bash
# View running containers on Pavilion:
ssh root@192.168.100.17 "docker ps"

# Stream live container stats:
ssh root@192.168.100.17 "docker stats"

# Inspect Kafka broker logs:
ssh root@192.168.100.17 "docker logs --tail 50 -f qf-kafka-broker"

# Restart Kafka cluster:
ssh root@192.168.100.17 "docker compose -f /opt/quantumflex/docker-compose.yml restart"
```

### C. System Vitals & Invariant Audits
From your Yoga laptop:
```bash
# Run composite invariant check (RAM, TPM 2.0, Water):
python qflex.py invariant

# Check system status HUD:
python qflex.py status
```

---

## 6. Live Verification & Telemetry Re-Admission (2026-09-25)

- **Operational State**: **ACTIVE** (Recovered from degraded/offline posture)
- **Mesh Connection**: `100.64.1.34` direct over LAN (`192.168.100.17:41641`) via Tailscale mesh.
- **SSH Access**: Tailscale SSH as `rocky@100.64.1.34` (root login strictly denied by Tailscale ACL tag `tag:worker`).
- **Container Health**:
  - `qf-kafka-broker` (confluentinc/cp-kafka:7.6.0): `Up 42+ hours`, listening on `127.0.0.1:9092` (exposed to Tailnet via Tailscale Serve TCP proxy `100.64.1.34:9092`).
  - `qf-kafka-ui` (provectuslabs/kafka-ui:latest): `Up 42+ hours`, listening on `127.0.0.1:8090` (exposed via Tailscale Serve HTTPS & HTTP 8090).
- **Worker Sentinel**: `qf-worker-sentinel.service` running active:
  - RAM Utilization: ~63% (1.2 GB used / 1.9 GB total, 0 B swap).
  - Disk Utilization: 0.8% used (428 GB free).
- **Master Ingestion Pipeline**:
  - `qf-kafka-telemetry.service` on Yoga 7 is publishing pulses every 15s (`partition 0, offset > 2000`).
  - `qf-kafka-consumer.service` on Yoga 7 is actively consuming pulses, inserting to AMARA PostgreSQL (`telemetry` DB), and embedding into Athena neural memory (`athena-node.service` port 8001).

