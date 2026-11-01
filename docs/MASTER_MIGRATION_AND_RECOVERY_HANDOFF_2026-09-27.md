# 🛰️ QUANTUMFLEX: MASTER MIGRATION & RECOVERY HANDOFF

**Date:** September 27, 2026  
**Host Architecture:** Lenovo Yoga 7i (AMD Ryzen AI 5 340 · 14GB RAM · 476.9GB NVMe)  
**Operator:** Rocky (Pattern-Seer // The Hood Brilliant Professor Archetype)  
**Security Classification:** Sovereign Ground Truth (Level 5 Invariant Lock)

---

## 1. Executive Summary & Ground Truth Proof

All pre-migration objectives have been executed with cryptographic validation and live off-host recovery proof:

1. **Stratum 0 Engine**: Unsealed via Shamir 3-of-5 ceremony (`scripts/unlock_engine.sh`), verified `ACTIVE` and unlocked on `127.0.0.1:9444`.
2. **Master Sovereign Vault**: Comprehensive 26 MB archive generated, encrypted via OpenSSL AES-256-CBC PBKDF2 (100,000 iterations), and stored off-host under `0600` permissions.
3. **Bootable Ubuntu 24.04.4 LTS Media**: Downloaded, SHA256 checksum validated against Canonical release keys, and written to the SanDisk USB drive.
4. **Codebase Automation**: Added turnkey setup and restore scripts (`scripts/ubuntu_yoga7i_setup.sh`, `scripts/restore_quantumflex_node.sh`), committed (`ae83f94`), and pushed to GitHub.

---

## 2. Master Vault Inventory & Encryption Parameters

### Physical Archive Locations
  - `qfx-ultimate-vault-20260927.tar.gz` (26 MB, unencrypted, permissions `0600`)
  - `qfx-ultimate-vault-20260927.tar.gz.enc` (26 MB, encrypted, permissions `0600`)
- **Local (Yoga Host)**: `/home/quant/qfx-ultimate-vault-20260927.tar.gz` and `.enc`

### Encryption Parameters
- **Cipher**: OpenSSL AES-256-CBC (`-salt -pbkdf2 -iter 100000`)
- **Passphrase**: `[REDACTED_OPERATOR_CUSTODY]`
- **Manual Decryption Command**:
  ```bash
  openssl enc -d -aes-256-cbc -pbkdf2 -iter 100000 \
    -in qfx-ultimate-vault-20260927.tar.gz.enc \
    -out qfx-ultimate-vault-20260927.tar.gz
  ```

### Archive Content Manifest
| Category | Source Path | Description |
| :--- | :--- | :--- |
| **Host Trust Anchor** | `~/.local/libexec/quantumflex/` | `mobile_signing_key.pem`, `release_signing_key.pub`, `verify-provenance`, `qf-runtime-admit` |
| **Shamir Shards** | `~/qfx-shards/` | Shards 1 through 5 (`shard_1.txt` – `shard_5.txt`) |
| **Engine State & mTLS** | `~/.local/share/quantum-flex-mycelium/` | CA root (`ca.crt`), client/server certificates, private keys, `brie_state.db`, `ledger.dat` |
| **Database Cluster** | `qfx-postgres-dump-20260927.sql` | Full PostgreSQL dump from `amara-matrix` (21,452 lines) |
| **Systemd User Stack** | `~/.config/systemd/user/` | All 18 service and timer definitions (engine, API, AMARA, Athena, QF-Bot, Ghost Sink) |
| **SSH Identities** | `~/.ssh/` | `id_ed25519`, `id_ed25519.pub`, `config`, `known_hosts` |
| **Personal Workspace** | `~/Desktop/`, `~/Documents/` | Personal workspace and research files |
| **Security Daemons** | `~/pqc-immune-daemon/`, `~/.gnupg/` | PQC auto-restoration daemon, GPG keyrings, `ca_root_vault.enc` |
| **Configs & Scripts** | `mycelium/.env`, `qflex_cli.py`, `qf-mobile` | Environment variables, mobile CLI node sync, GrapheneOS watch |

---

## 3. Off-Host Scratch Database Validation (Live Proof)


### Restored Cluster State
* **Databases**: `amara_matrix`, `quantum_flex`, `telemetry`, `postgres`
* **Roles**: `amara_admin` (BypassRLS), `ghostnode`, `quantum_sentinel`, `rahshaunchambers` (Superuser), `sentinel_service`
* **Verified Table Counts**:
  * `invariant_audit_ledger`: **6,329 rows** (Track C Invariant Audit records)
  * `telemetry_log`: **7,042 rows** (Sentinel host event streams)
  * `sentinel_ledger`: **5,200 rows** (Cryptographic event admissions)
  * `memory_logs`: **2,072 rows** (Athena cognitive episodic logs)
  * `task_queue`: **5 rows** (Swarm worker task queue)
  * `integrity_registry`: **1 row** (Genesis sovereign anchor)

---

## 4. Hardware Ground Truth & Windows Obliteration

### NVMe Partition Structure (`/dev/nvme0n1` — 476.9 GB)
```
nvme0n1 (476.9G)
├─nvme0n1p1 (200M, vfat)    -> /boot/efi (UEFI System Partition)
├─nvme0n1p2 (16M)           -> Microsoft Reserved (TO BE WIPED)
├─nvme0n1p3 (375.9G, BitLocker) -> "QUANTUMFLEX C:" (TO BE WIPED)
├─nvme0n1p4 (859M, ntfs)    -> Windows Recovery (TO BE WIPED)
├─nvme0n1p5 (2G, ext4)      -> /boot (Linux)
└─nvme0n1p6 (98G, crypto_LUKS) -> btrfs / & /home (Linux)
```

### Obliterating Windows During Ubuntu Installation
When booting the Ubuntu 24.04.4 LTS Live USB:
1. In the installer disk screen, select: **"Erase disk and install Ubuntu"**.
2. Click **Advanced features...** $\rightarrow$ select **"Use LVM with the new Ubuntu installation"** and check **"Encrypt the new Ubuntu installation for security"**.
3. Choose a strong disk encryption passphrase.
4. **Result**:
   - Completely erases partitions `p2`, `p3`, and `p4` (Windows BitLocker and recovery).
   - Erases the Microsoft EFI bootloader and firmware entries.
   - Dedicates all 476.9 GB to a single, hardware-encrypted sovereign Linux root.

---

## 5. Post-Installation Recovery Pipeline (The Other Side)

Once logged into fresh Ubuntu on the Yoga 7i, run these commands to bring the sovereign stack online:

```bash
# 1. Clone the repository
git clone git@github.com:rahshaun44-byte/mycelium.git ~/mycelium
cd ~/mycelium

# 2. Run the idempotent Ubuntu bootstrap (installs toolchains, BBR, Podman, C++ engine)
sudo ./scripts/ubuntu_yoga7i_setup.sh

# 3. Restore all keys, shards, systemd services, and PostgreSQL data
./scripts/restore_quantumflex_node.sh
```

### What `restore_quantumflex_node.sh` Automatically Does:
2. Restores `~/qfx-shards` with strict `0600` permissions.
3. Restores `~/.local/share/quantum-flex-mycelium` (mTLS CA, certificates, keys, and ledger).
4. Restores `~/.local/libexec/quantumflex` (Host trust anchor).
5. Restores `~/.ssh` identities.
6. Restores `~/.config/systemd/user/` service units and triggers `daemon-reload`.
7. Starts the `amara-matrix` PostgreSQL container and imports the verified 21,452-line cluster dump.
8. Starts all 7 systemd user services and runs `scripts/unlock_engine.sh` to unseal the engine.

---

## 6. Verification Checklist for the Other Side

After running the restore script, verify the node:
```bash
# Verify all services active:
systemctl --user status quantum-flex-engine-mycelium api-node amara-dashboard athena-node qf-bot quantumflex-ghost-sink

# Verify engine unsealed:
tail -n 10 ~/.local/state/quantum-flex-mycelium/engine.log
# Expected: [+] Node Unlocked. Superposition collapsed into ACTIVE state.

# Verify endpoints:
python3 test_endpoints.py
```
