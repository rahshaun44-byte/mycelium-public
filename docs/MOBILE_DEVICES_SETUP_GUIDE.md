# QuantumFlex: Mobile Operator Plane Architecture & Setup Guide (QF-M1)

Consolidated operational guide for the QuantumFlex mobile command plane on the single mobile node (Google Pixel 11 Pro: Hardware Custody & OOB Signer) over the Tailscale WireGuard mesh.

---

## 1. The Core Architectural Invariant

$$\text{ONE interface} \neq \text{ONE authority}$$

QuantumFlex unifies the mobile protocol and operator interface into a single, zero-dependency command line (`qf`) and sovereign mobile HUD, while strictly enforcing hardware and cryptographic division of authority:

```text
          QuantumFlex Mobile Command Plane

                 Unified qf CLI
                       │
                       ▼
         qfx-pixel (Google Pixel 11 Pro)
         custody-anchor · 100.64.1.16

         CUSTODY ROLE
         ────────────
         Titan M2 StrongBox
         OOB signer
         share custody (#5)
         quorum state
         emergency freeze
```

---

## 2. Mesh Topology & Device Registry

| Node / Device | Hardware Role | Interface IP | Tailscale Mesh IP | MagicDNS Hostname | Authority Domain |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **qfx-yoga** (Lenovo Yoga 7 2-in-1 14AKP10, Ubuntu 26.04.1 LTS) | Control Plane & PQC Core | `192.168.100.15` (Wi-Fi) | `100.64.1.31` | `quant-yoga-7-2-in-1-14akp10` | Pluton TPM 2.0, Share 1, Admission Authority |
| **qfx-pixel** (Google Pixel 11 Pro) | Hardware Share Anchor / OOB Signer | DHCP / USB | `100.64.1.16` | `pixel-11-pro-1` | Titan M2 StrongBox, Share 5, Quorum Signer |
| **g6pro** (HP ProBook 450 G6, Debian 13) | Kafka Broker (`:9092`, UI `:8090`) | `192.168.100.13` | `100.64.1.19` | `g6pro` | Share 2, event streaming |


---

## 3. Verified OTA Bootstrap Protocol

QuantumFlex enforces **verify-before-execute** on all mobile artifacts. Piping unverified HTTP responses directly into execution shells is strictly rejected.

### Cryptographic Bootstrap Flow:
```text
download artifact
      ↓
download signed manifest + signature
      ↓
verify against pinned mobile trust anchor (release_signing_key.pub)
      ↓
verify SHA-256
      ↓
install / execute
```

### Setup Command on Android (Termux):
```bash
# 1. Fetch bootstrap installer and pinned trust anchor
curl -fsS http://100.64.1.31:9000/mobile/download/trust-anchor -o ~/.quantumflex/release_signing_key.pub
curl -fsS http://100.64.1.31:9000/mobile/download/setup -o ~/setup-mobile.sh
chmod +x ~/setup-mobile.sh

# 2. Run verified installation
bash ~/setup-mobile.sh
```

---

## 4. Mobile Operator CLI (`qf`) Reference

The unified mobile CLI operates with **observational-by-default** semantics. Read-only commands inspect engine telemetry; state mutations require explicit operator confirmation and role verification.

### Observational Commands:
| Command | Description |
| :--- | :--- |
| `qf node` | Inspects local node identity, assigned role, transport link, and authority scope. |
| `qf status` | Queries cluster health, Sentinel drive score ($D$), TPM match, and peer latencies. |
| `qf verify` | Authoritative lens for QF-A4 artifact hashes, QF-A5 Ed25519 provenance, and QF-A6 runtime binding ($EXECUTED\_FD == VERIFIED\_FD$). |
| `qf invariant` | Evaluates Universal Invariant ($R \ge O$), physical reserves, and obligations. |
| `qf custody` | Displays Shamir 3-of-5 threshold state, Titan M2 shard status, and circuit-breaker status. |
| `qf doctor` | System diagnostic verifying trust anchors, host handshake, and network paths. |
| `qf drafts` | Inspects staged agent actions awaiting human operator review. |
| `qf chat <agent> "<prompt>"` | Interrogates multi-agent swarm (`mycelia`, `sentinel`, `aria`, `athena`) backed by local Ollama neural engine. |

### Privileged Transitions:
| Command | Required Role | Description |
| :--- | :--- | :--- |
| `qf approve <draft_id>` | `shard-custodian` | Authorizes staged draft action with a fresh, timestamped node authorization receipt. |
| `qf discard <draft_id>` | `shard-custodian` | Discards staged draft. |

> [!CAUTION]
> If a node is identified as `unknown` / `observer`, all privileged actions are fail-closed with `PRIVILEGED_ACTIONS=DENY`.

---

## 5. Direct Physical Provisioning via ADB (`sync_mobile_nodes.py`)

For physical USB provisioning:
```bash
# Inspection only (default, zero modifications)
python3 scripts/sync_mobile_nodes.py

# Verified push of CLI, manifests, and HUD to /sdcard/Download/QuantumFlex/
python3 scripts/sync_mobile_nodes.py --push

# Install or update native Capacitor Cockpit APK (com.quantumflex.cockpit)
python3 scripts/sync_mobile_nodes.py --apk

# Full dual provisioning targeting specific serial
python3 scripts/sync_mobile_nodes.py --push --apk --device <SERIAL>
```

---

## 6. Over-The-Air (OTA) Distribution Endpoints

All OTA endpoints are served strictly on the authenticated loopback / Tailscale boundary (`100.64.1.31:9000`):

| Endpoint | Artifact | Description |
| :--- | :--- | :--- |
| `/mobile/bootstrap` | JSON Handshake | Authenticated handshake (`schema: qf-mobile-v1`). |
| `/mobile/admission/evidence` | JSON Proof | Authoritative host A4/A5/A6 cryptographic admission state. |
| `/mobile/manifest` | JSON Catalog | Manifest index of all available signed artifacts. |
| `/mobile/download/cli` | `qflex_cli.py` | Unified mobile operator CLI. |
| `/mobile/download/cli/manifest` | `qflex_cli.py.manifest.json` | Signed distribution manifest with SHA-256. |
| `/mobile/download/cli/sig` | `qflex_cli.py.sig` | Detached Ed25519 signature. |
| `/mobile/download/apk` | `qf-cockpit.apk` | Native Capacitor mobile cockpit APK (`com.quantumflex.cockpit`). |
| `/mobile/download/apk/manifest` | `app-debug.apk.manifest.json` | Signed APK manifest. |
| `/mobile/download/apk/sig` | `app-debug.apk.sig` | Detached Ed25519 signature for APK. |
| `/mobile/download/setup` | `setup-mobile.sh` | Verified Termux bootstrap script. |
| `/mobile/download/trust-anchor` | `release_signing_key.pub` | Pinned Ed25519 public key. |
