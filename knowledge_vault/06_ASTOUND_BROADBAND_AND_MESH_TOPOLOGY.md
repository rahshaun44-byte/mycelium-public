# Knowledge Vault: 06 — Astound Broadband Integration & Mesh Topology

**Document ID:** KV-06  
**Security Classification:** Sovereign Internal — Cryptographically Pinned  
**Effective Date:** 2026-09-20  
**Target Platform:** Lenovo Yoga 7i (AMD Ryzen 7 8840HS) & Tailscale Mesh  

---

## 1. Executive Summary & Operational Invariant

With the deployment of the dedicated **Astound Broadband** connection, QuantumFlex achieves low-latency, high-throughput sovereign networking across its distributed hardware mesh. The core invariant remains intact:

$$\text{Local WAN/LAN} \ne \text{Exposed Services} \implies \text{Exposure}(0.0.0.0) \equiv \emptyset$$

All application databases, vector stores, neural models, and consensus engines remain strictly locked to loopback (`127.0.0.1`). Remote access is mediated exclusively across the private Tailscale WireGuard overlay (`100.x.x.x`) via authenticated **Tailscale Serve** reverse proxy tunnels.

---

## 2. Network Topology & Physical Ingress

| Parameter | Configuration Value | Verification Method |
| :--- | :--- | :--- |
| **ISP / Carrier** | Astound Broadband | WAN NAT Endpoint: `23.28.34.188` |
| **Physical Interface** | `enp6s0f3u1i1` | High-speed Ethernet / USB-C Dock NIC |
| **Local Gateway** | `10.0.0.254/24` | DHCP Dynamic Allocation (`10.0.0.15`) |
| **NAT Mapping Type** | Full-Cone / Endpoint-Independent | `tailscale netcheck` (`MappingVariesByDestIP: false`) |
| **Nearest DERP Region** | NYC Relay (`25.8 ms`) | `tailscale netcheck` |
| **WireGuard Direct Peer** | Verified (`20 ms` direct to Pixel 11 Pro) | `tailscale ping 100.64.1.11` |

---

## 3. High-Throughput Kernel Stack Tuning

Astound Broadband delivers high burst bandwidth. Default Linux network buffers throttle UDP packet rates and cause bufferbloat during model synchronization and artifact transmission. The following kernel parameters optimize the host stack:

### 3.1 UDP Buffer Tuning for Tailscale WireGuard
```ini
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.core.rmem_default = 1048576
net.core.wmem_default = 1048576
net.core.optmem_max = 65536
net.ipv4.udp_rmem_min = 8192
net.ipv4.udp_wmem_min = 8192
```

### 3.2 TCP BBR Congestion Control & Latency Reduction
```ini
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216
net.ipv4.tcp_fastopen = 3
net.ipv4.tcp_slow_start_after_idle = 0
```
* **BBR Advantage:** Unlike loss-based Cubic, Google BBR models network bottleneck bandwidth and round-trip propagation time, preventing packet queue buildup on cable broadband buffers.

---

## 4. Mesh Node Authority & Device Registry

| Node Identifier | Hardware Role | Interface IP | Tailnet IP | MagicDNS FQDN | Authority Scope |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`fedora`** | Master Control & PQC Core | `10.0.0.15` | `100.64.1.17` | `fedora.example-tailnet.ts.net` | TPM 2.0 / PCR-7, Shards 1 & 2, Admission Authority |
| **`pixel-11-pro-1`** | Mobile Shard Custody Anchor | Dynamic / USB | `100.64.1.11` | `pixel-11-pro-1.example-tailnet.ts.net` | Titan M2 Hardware Security Module, Shamir Shard Custody |
| **`qf-pavilion-worker`** | Stream Compute & Kafka | `192.168.100.17` | `100.64.1.34` | `qf-pavilion-worker.example-tailnet.ts.net` | KRaft Kafka Broker, High-Throughput Stream Compute |
| **`rahshauns-s23-fe`** | Mobile Operator Console | Dynamic | `100.64.1.32` | `rahshauns-s23-fe.example-tailnet.ts.net` | Samsung DeX Workstation, Tactical Telemetry Cockpit |

---

## 5. Tailscale Serve Publication Matrix

| Ingress Port | Target Local Socket | Service Description | Security Boundary |
| :--- | :--- | :--- | :--- |
| `8000` | `127.0.0.1:8000` | AMARA Matrix Real-Time HUD | Authenticated Tailnet Only |
| `8080` | `127.0.0.1:8080` | Quantum Flex Core API Gateway | Authenticated Tailnet Only |
| `9000` | `127.0.0.1:9000` | QF-Bot AI Teammates & MCP SSE Stream | Authenticated Tailnet Only |
| `443` (HTTPS) | `127.0.0.1:9000` | Mobile HUD / PWA Cockpit | TLS 1.3 via Tailscale MagicDNS Cert |
| `9444` | `127.0.0.1:9444` | Stratum 0 C++ Evidence Engine | **Loopback mTLS Only (Never Served)** |
| `8001` | `127.0.0.1:8001` | Athena RAG Cognitive Node | **Loopback Only** |
| `5432` | `127.0.0.1:5432` | PostgreSQL System Datastore | **Loopback Only** |
| `11434`| `127.0.0.1:11434` | Ollama Neural Inference Engine | **Loopback Only** |

---

## 6. Shamir Threshold Unsealing & Airgap Hygiene

1. The C++ Evidence Engine boots in a sealed `LOCKED` posture by default.
2. Unsealing requires a 3-of-5 threshold ceremony via `scripts/unlock_engine.sh`:
   - Shard 1 & 2: Local NVMe (`~/qfx-shards/`)
   - Shard 3: Transient USB Vault (`QFX_VAULT`)
3. **Zero Airgap Residual Invariant:** `QFX_VAULT` is mounted strictly for the duration of secret reconstruction and unmounted immediately post-ceremony (`udisksctl unmount -b /dev/sda1`), leaving zero physical disk mounts exposed.
