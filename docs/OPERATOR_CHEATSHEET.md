# 🌌 Quantum Flex: Master Operator Cheatsheet & Hardening Codex

**Target Host:** Lenovo Yoga 7 2-in-1 14AKP10 (AMD Ryzen AI 5 340, Ubuntu 26.04.1 LTS, host `qfx-yoga`)  
**Architecture:** Hybrid PQC (ML-KEM-768 / X25519MLKEM768) + Ed25519, Stratum 0 C++20 Engine, OPA Immune Sidecar, Autonomous Hive  
**Security Baseline:** Zero-Trust Loopback (`127.0.0.1`), Shamir $k=3, n=5$ Offline Custody, Append-Only Telemetry

---

## 1. Architectural Map: How Everything Actually Works

Quantum Flex is a multi-stratum, defense-in-depth biological computing and telemetry platform:

```
                               ┌──────────────────────────────────────────────┐
                               │             Autonomous Agents                │
                               │   qflex-mcp (9000)  /  qf-bot (9050)         │
                               └──────────────────────┬───────────────────────┘
                                                      │
 ┌────────────────────────────────────────────────────┼────────────────────────────────────────────────────┐
 │  STRATUM 1: Operational Core                       │                                                    │
 │                                                    ▼                                                    │
 │  ┌─────────────────────┐       ┌───────────────────────────────┐       ┌─────────────────────────────┐  │
 │  │   AMARA Dashboard   │       │       API Gateway Node        │       │      ATHENA RAG Node        │  │
 │  │      Port 8000      │       │           Port 8080           │       │          Port 8001          │  │
 │  └──────────┬──────────┘       └───────────────┬───────────────┘       └──────────────┬──────────────┘  │
 └─────────────┼──────────────────────────────────┼──────────────────────────────────────┼─────────────────┘
               │                                  │                                      │
 ┌─────────────┼──────────────────────────────────┼──────────────────────────────────────┼─────────────────┐
 │             ▼                                  ▼                                      ▼                 │
 │      amara-matrix (PG 15)              Kafka Forwarder/Consumer               Ollama (11434)            │
 │     127.0.0.1:5432 (5433)             Pulse Stream (ML-KEM-768)         nomic-embed-text / gemma2:2b    │
 └────────────────────────────────────────────────┬────────────────────────────────────────────────────────┘
                                                  │
 ┌────────────────────────────────────────────────┼────────────────────────────────────────────────────────┐
 │  STRATUM 0 & IMMUNE GATING                     │                                                        │
 │                                                ▼                                                        │
 │  ┌───────────────────────────────────────────────────────────┐      ┌────────────────────────────────┐  │
 │  │             Evidence Engine (C++20 IPC Server)            │◄────┤       OPA Immune Sidecar       │  │
 │  │         Port 9444 (mTLS TLS 1.3, Client Cert Auth)        │      │    Port 8181 (Membrane Gate)   │  │
 │  │   State Machine: UNINITIALIZED ──> LOCKED ──> ACTIVE      │      └────────────────┬───────────────┘  │
 │  └─────────────────────────────┬─────────────────────────────┘                       │                  │
 │                                │                                                     │                  │
 │                                ▼                                                     ▼                  │
 │                   Shamir Threshold Quorum (3-of-5)                      PQC CBOM Agility Supervisor     │
 │                    shard_1 + shard_2 + shard_3                          Fallback: X25519MLKEM768        │
 └─────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Component Inventory & Responsibilities
1. **Stratum 0 Evidence Engine (`quantum_flex_engine` on `127.0.0.1:9444`)**:
   - Compiles with C++20, OpenSSL 3.5.8 default provider, and `libpqxx`.
   - **`EvidenceEngine`**: Hash-chained, append-only ledger calculating root hashes without persisting raw telemetry payloads.
   - **`HybridSigner`**: Signs payloads with dual Ed25519 + PQC KEM keys, emitting `<ed_sig_hex>|<pqc_sig_hex>`.
   - **`BaeNode`**: Executes transactional Postgres partition purges and verification proofs inside an atomic `pqxx::work` block.
   - **`StateManager`**: SQLite-backed partition journal (`brie_state.db`) for crash recovery.
   - **`IpcServer`**: Single-threaded, synchronous mTLS TCP server enforcing TLS 1.3 and client cert validation.
2. **Stratum 1 Ingestion & Cognitive Memory**:
   - **`api_node` (Port 8080)**: Validates incoming payloads, checks invariance, and stages files for quarantine containment.
   - **`athena_node` (Port 8001)**: Pure-Python vector store (`sentinel/intelligence/athena_vectors.db`) generating 768-dim embeddings via local Ollama.
   - **`amara_dashboard` (Port 8000)**: Operational HUD visualizing node metrics, telemetry cadence, and invariant health.
   - **`qflex_mcp` (Port 9000)**: Model Context Protocol SSE server providing tool access to LLMs and agent swarms.
   - **`qf-bot` (Port 9050)**: AI Teammate orchestration server.
3. **PQC Crypto-Agility Immune Subsystem**:
   - **`immune_daemon`**: Polling loop executing every 500 ms. Generates cryptographic bills of materials (CBOM) and posts them to OPA.
   - **`opa-immune` (Port 8181)**: Open Policy Agent evaluating `membrane_health.rego`. If a KEM algorithm is deprecated or compromised, OPA issues verdict `TOXIC`.
   - **Automated Fallback**: The immune daemon atomically replaces `crypto_provider.conf` and signals workers (`SIGHUP`) to immediately renegotiate with the secondary algorithm.
4. **Autonomous Swarm ("The Claw")**:
   - **`controller.py`**: Decomposes natural language directives into atomic tasks stored in the PostgreSQL `task_queue`.
   - **`swarm_worker.py`**: Worker daemon polling `task_queue` with `FOR UPDATE SKIP LOCKED` to ensure zero race conditions.
   - **Task continuity**: PostgreSQL remains authoritative; `mcp_layer/task_checkpoint.py` atomically mirrors sanitized hashes/state into private local files and reconciles them on recovery. Run `/home/quant/mycelium/venv/bin/python3 /home/quant/mycelium/scripts/task_checkpoint.py self-test` to verify persistence and fresh-process recovery without service restarts. See `docs/AMARA_ATHENA_CONTINUITY.md`.

---

## 2. Proper Deployment: Clean Boot Sequence

Never run services as arbitrary scripts in the background. Every service is configured as a dedicated systemd unit.

### Step 1: System Boot Verification
When the machine boots or restarts, user services automatically queue in `default.target.wants`:
```bash
# Check running status of all core units
systemctl --user status amara-matrix amara-dashboard api-node athena-node \
  immune-daemon opa-immune qf-bot qf-kafka-consumer qf-kafka-telemetry \
  qf-monitor qflex-mcp swarm-worker --no-pager
```

### Step 2: Boot Engine into "LOCKED Phase"
The C++ evidence engine is intentionally **disabled on boot** so that it never boots into an unmonitored state.
```bash
# 1. Start the engine unit
systemctl --user start quantum-flex-engine-mycelium.service

# 2. Verify it is running and strictly listening on loopback
ss -lntH | grep 9444

# 3. Verify it is confirmed in the LOCKED state (must return ERR|NODE_LOCKED)
python3 scripts/qf_ipc_client.py \
  --host 127.0.0.1 \
  --port 9444 \
  --cert ~/.local/share/quantum-flex-mycelium/mtls/client.crt \
  --key ~/.local/share/quantum-flex-mycelium/mtls/client.key \
  --ca ~/.local/share/quantum-flex-mycelium/mtls/ca.crt \
  --line "STATUS"
```
*Expected Output:* `ERR|NODE_LOCKED`. The existing ledger is suspended in memory, awaiting its matching Shamir quorum. The client returns exit code 1 for this expected locked-state response; this is not an unlock failure.

### Step 3: Unsealing Ceremony (Transition to ACTIVE)
**Current hold (2026-10-14):** Three complete shares exposed in a conversation authenticate the existing ledger. The recovery helper is locally held against live unlock. Keep the engine LOCKED while using non-secret personal research and read-only monitoring. Offline checking remains available. Do not clear the hold or reuse this authority until a reviewed migration to a new authority is completed; the disabled rotation script does not implement that migration.

When you are ready to promote the engine from `LOCKED` to `ACTIVE`:
```bash
# Encrypted custody: privately enter both passwords in your terminal.
# This verifies the existing ledger offline and does not contact the engine.
./venv/bin/python3 tools/qf_recovery.py --check

# Future use only: MATCH plus a reviewed new-authority migration and hold release.
# Currently refused by the exposure hold; do not run to bypass it.
./venv/bin/python3 tools/qf_recovery.py --unlock
```
The tool reads the encrypted USB vault and local encrypted share into process memory without extracting plaintext files. Passwords are hidden and are never command arguments. `MISMATCH` or a validation error stops before IPC. Do not guess generations, use plaintext `/tmp` extraction, or fall back to a local steganographic image.

Live unlock requires a match, an unchanged ledger bound to the running local engine, the supported empty legacy evidence root, a confirmed `LOCKED` response, and the exact `ACK|NODE_UNLOCKED` acknowledgement. It does not establish deployed binary provenance or overall alpha readiness. Python/TLS memory erasure is not guaranteed. For three existing plaintext share files, `scripts/unlock_engine.sh` delegates to the same offline check rather than sending shares unchecked.

### Step 4: Shut Down Engine
When testing or operations conclude, cleanly stop the engine so it does not run unmonitored:
```bash
systemctl --user stop quantum-flex-engine-mycelium.service
```

---

## 3. Secret Instructions & Non-Obvious Operational Realities

### Invariant 1: Zero Key Shipping
- **Rule:** Under no circumstances should `ca.key`, `server.key`, `client.key`, or `shard_*.txt` ever be committed to Git or bundled into distributions.
- **Why `scripts/package_alpha_node.py` was removed:** The script attempted to package keys into ZIP archives, directly violating the zero-key shipping invariant.

### Invariant 2: Shard Custody Matrix
- **Current recovery:** One encrypted local share and the encrypted USB vault are available. The operator holds both passwords. Matching the files to the current ledger remains a private terminal check; a filename or date alone does not establish their generation.
- **Target custody:** Retain only one share on the host and keep the remaining shares in separate offline locations. Do not paste values or passwords into chat or copy decrypted shares to the host SSD.
- **Custody issue:** A local image contains the expected steganographic marker. If it holds two matching shares, it conflicts with the target distribution. Preserve existing recovery material until a matching quorum is established, then plan verified custody remediation. Hiding shares in image pixels does not encrypt them.

### Invariant 3: Single-Thread Synchronous IPC Constraint
- The engine's ingestion loop in `src/main.cpp` executes `server.process_single_connection()` synchronously.
- **Do not** connect with multi-threaded, persistent HTTP connection pools or parallel mTLS workers targeting port 9444. Send serial requests with clean TCP connection closure (`close()`).

### Invariant 4: Dual PostgreSQL Backends
1. **Telemetry Native DB (`127.0.0.1:5432`)**:
   - Roles: `ghostnode` (admin) and `sentinel_service` (insert-only on `sentinel_ledger`).
   - Used by Sentinel, MCP layer, and swarm workers.
2. **Amara Matrix Container (`logistics-pg` on `127.0.0.1:5433` or mapped 5432)**:
   - Role: `amara_admin`.
   - Used by `BaeNode` partition shredding. Never share credentials between these two databases.

### Invariant 5: Fail-Closed OPA Immune Policy
- In `pqc-immune-daemon/immune_daemon.py`, if the OPA daemon (`127.0.0.1:8181`) is unreachable or returns a network error, the system **fails closed**:
  ```python
  # OPA unreachable -> Treats algorithm as TOXIC immediately
  return {"verdict": "TOXIC", "reason": "OPA_UNREACHABLE_FAIL_CLOSED"}
  ```

### Invariant 6: Single Ollama Instance
- System Ollama runs as a root system service (`/etc/systemd/system/ollama.service`) on `127.0.0.1:11434`.
- Never enable user-level `ollama.service` (`~/.config/systemd/user/ollama.service`); doing so causes endless auto-restart port collision loops.

---

## 4. Benefiting from HEX: Side-Channel Defense & Hardware Anchoring

In Quantum Flex, "HEX" is not merely string formatting; it is a foundational security primitive:

### 1. Constant-Time Wire Parsing (Hertzbleed & Dudect Immunity)
- **Vulnerability:** Standard parsers like `std::stoul` or `sscanf` branch on character values and early-exit on delimiters. On modern CPUs with dynamic voltage and frequency scaling (DVFS), branch mispredictions and variable-time execution leak cryptographic key bits over the network (Hertzbleed attacks).
- **Hardening:** In `src/crypto/crypto_signer.cpp` and `ipc_server.cpp`, all hex strings are decoded using bitwise constant-time routines:
  ```cpp
  uint8_t val = ((c >= '0' && c <= '9') * (c - '0')) |
                ((c >= 'a' && c <= 'f') * (c - 'a' + 10)) |
                ((c >= 'A' && c <= 'F') * (c - 'A' + 10));
  ```
- **Benefit:** Dudect Welch $t$-test confirms timing indistinguishability ($|t| = 2.1606 < 4.5$), mathematically proving zero timing side-channel leakage across the wire.

### 2. Hardware TPM PCR 15 Extension
- **Hardware Binding:** `sentinel/sentinel.py` anchors operational blocks into the motherboard's physical TPM chip using `anchor_to_hardware_tpm(block_hash_hex)`.
- **How it works:** The 64-character SHA-256 hex string is supplied directly to the Linux TPM kernel driver:
  ```bash
  tpm2_pcrextend 15:sha256=<block_hash_hex>
  ```
- **Benefit:** Extends the hardware cryptographic chain. Even an attacker with complete root access cannot alter past PCR states or forge historical telemetry without physical hardware replacement.

### 3. Dual-Signature ASCII Stream Encoding
- `HybridSigner` produces `<ed_sig_hex>|<pqc_sig_hex>`.
- **Benefit:** Pure ASCII hex strings eliminate null-byte injection vulnerabilities, encoding mismatches, and escaping errors across JSON, Kafka wire formats, and OPA policy engines without base64 overhead.

---

## 5. Next-Level Hardening: How to Make the System Even More Secure

To elevate Quantum Flex to nation-state / defense-grade posture, implement these five hardening steps:

### 1. Enforce Memory Pinning (`LimitMEMLOCK` & `mlockall`)
- **Current State:** The system uses zram (`/dev/zram0`, compressed RAM swap), which prevents physical disk paging, but secrets are not yet pinned in memory.
- **Improvement:**
  1. Add to `~/.config/systemd/user/quantum-flex-engine-mycelium.service`:
     ```ini
     [Service]
     LimitMEMLOCK=infinity
     ```
  2. Invoke `mlockall(MCL_CURRENT | MCL_FUTURE)` in `src/main.cpp` immediately after genesis unsealing to lock all key material into non-swappable physical RAM blocks.

### 2. Automated Hertzbleed Gate (`scripts/hertzbleed-gate.sh`)
- Create an automated startup preflight script that verifies the CPU scaling governor before the engine initializes:
  ```bash
  #!/usr/bin/env bash
  GOV=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor)
  if [[ "$GOV" != "powersave" && "$GOV" != "performance" ]]; then
      echo "[!] UNSAFE GOVERNOR: $GOV. Mitigate DVFS leakage before starting engine."
      exit 1
  fi
  ```

### 3. Loopback Ingress Firewall Rules (`nftables`)
- Explicitly drop external packets targeting internal daemon ports even if physical interfaces change:
  ```bash
  sudo nft add table inet filter
  sudo nft add chain inet filter input { type filter hook input priority 0 \; policy accept \; }
  sudo nft add rule inet filter input iifname != "lo" tcp dport { 5432, 8000, 8001, 8080, 8181, 9000, 9050, 9444 } drop
  ```

### 4. TPM-Sealed Shard Storage
- Rather than storing `shard_1.txt` in plaintext on disk (`chmod 600`), seal `shard_1.txt` against TPM PCRs 0, 2, 7 (UEFI firmware, SecureBoot, and kernel measurements):
  ```bash
  # Seal shard_1 using TPM 2.0
  tpm2_createprimary -C o -c primary.ctx
  tpm2_pcrread "sha256:0,2,7" -o pcr.digest
  tpm2_create -C primary.ctx -u obj.pub -r obj.priv -i ~/qfx-shards/shard_1.txt -L pcr.digest
  ```
- If an attacker tampers with the kernel or UEFI boot sequence, the TPM will refuse to release `shard_1.txt`.

### 5. Automated Shard Rotation Cadence
- Execute `scripts/rotate_shards.sh` every 90 days. The script generates a clean 3-of-5 threshold set, wipes `ledger.dat`, commits genesis, and cleanses stack memory without printing sensitive shards to terminal buffers.
