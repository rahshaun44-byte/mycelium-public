# 📖 QuantumFlex: Sovereign Owner & Operator Handbook
**System:** QuantumFlex Sovereign Core  
**Hardware Host:** Lenovo Yoga 7 2-in-1 14AKP10 (AMD Ryzen AI 5 340, Ubuntu 26.04.1 LTS)  
**Security Standard:** Zero-Trust Loopback (`127.0.0.1`), Shamir (3-of-5) Airgap Custody, Offline-First Architecture

---

## 1. Guiding Principles: Security, Integrity, and Understanding

Technology should never feel like a confusing chore, a source of stress, or a mysterious black box. 

This machine was built on three uncompromising principles:
1. **Security Through Inaction:** When you are not actively using QuantumFlex, it sleeps. Zero background processes running, zero network ports open, zero data moving. It never does anything behind your back.
2. **Integrity of Custody:** You know where every piece of your system lives. No single computer, cloud provider, or person holds all your keys.
3. **Calm Understanding:** You operate this machine with patience, discipline, and clarity. No rushing, no hype, no unnecessary complexity.

---

## 2. The Custody Matrix: Where Your System Lives

Your system is split using Shamir's Secret Sharing ($k=3, n=5$). It requires **3 pieces** to reconstruct master access. 

| Shard | Custody Location | Physical Security State |
| :--- | :--- | :--- |
| **Shard 1** | Yoga Laptop (`~/qfx-shards/shard_1.txt`) | Stored on LUKS-encrypted NVMe (`chmod 600`) |
| **Shard 2** | Yoga Laptop (`~/qfx-shards/shard_2.txt`) | Stored on LUKS-encrypted NVMe (`chmod 600`) |
| **Shard 3** | Physical USB Drive (`QFX_VAULT`) | Ext4 partition, unmounted, stored in a drawer |
| **Shard 4** | Physical USB Drive (`QFX_VAULT`) | Ext4 partition, unmounted, stored in a drawer |
| **Shard 5** | Physical Paper | Handwritten transcription, stored in a physical safe |

> **Why this matters:** If your laptop is lost or stolen, an attacker holds at most 2 shards. Mathematically, 2 shards reveal **zero information** about your master key. Your system cannot be unlocked without physical access to your USB drive or paper safe.

---

## 3. The System Lifecycle: Powering Up and Shutting Down

QuantumFlex is designed to be **dormant by default**. You only turn it on when you intentionally sit down to work or research.

### A. The Cold State (How It Sits Right Now)
* **Status:** **DORMANT / SECURED**
* **Database (`amara-matrix`):** Stopped (`Exited 0`)
* **HUD & Agents (`qf-bot` & `dashboard`):** Stopped
* **Tailscale Serve Proxy:** Reset & Closed
* **Listening Ports (5432, 8000, 9000):** **100% Closed**
* **Webcam:** De-authorized at kernel USB level (`authorized = 0`)

In this state, your laptop is just a normal, ultra-secure personal computer. You can browse the web, write documents, travel, or sleep with zero battery drain and zero exposure.

---

### B. The 1-Command Startup (When You Want to Work)
When you are ready to use your HUD, query your local AI, or run research, open a terminal and run:

```bash
# Start the core database and user interface
systemctl --user start amara-matrix amara-dashboard qf-bot
```

Once started, open Google Chrome to:
* **Tactical Swarm HUD:** `http://127.0.0.1:9000/ui/`
* **Telemetry & Metrics:** `http://127.0.0.1:8000/`

---

### C. The 1-Command Secure Shutdown (Putting It to Bed)
When you are done with your session and want everything closed down cleanly:

```bash
# Stop all services and verify ports close
systemctl --user stop qf-bot amara-dashboard amara-matrix
```

To verify that nothing is running or listening:
```bash
ss -tulpn | grep -E "5432|8000|9000"
```
*(If this command prints nothing, your system is 100% dark and quiet).*

---

## 4. The Research Engine: How to Use It for Deep Study

The greatest practical power of this machine is **ATHENA**—your local, offline research assistant.

### How to Ingest Books, Notes, and Research Papers:
1. Put any PDF, text file, or markdown notes you want to study into your research folder:
   ```bash
   mkdir -p ~/mycelium/research_vault
   ```
2. Athena digests the text using your local embedding model (`nomic-embed-text`) on your AMD Ryzen processor and indexes the concepts into SQLite/PostgreSQL.
3. Open your HUD (`http://127.0.0.1:9000/ui/`), tap **🧠 ATHENA**, and ask your research questions.
4. **Privacy Guarantee:** Your documents and thoughts never leave your local SSD.

---

## 5. The Golden Invariants: Operating with Integrity

Whenever you make decisions for yourself or QuantumFlex, remember the three core rules built into this machine:

1. **$R \ge O$ (Reserves Always Exceed Obligations):**
   * Never commit to an expense, debt, or task unless your liquid reserves strictly cover it.
   * Protect your family and your dependents first by maintaining a permanent safety buffer.
2. **Zero-Trust Perimeter:**
   * Never bind services to `0.0.0.0` or expose raw ports to public Wi-Fi.
   * If you need remote access from your phone, use your private Tailscale tunnel.
3. **No Key Shipping:**
   * Never paste passwords, private keys, or Shamir shards into chat windows, emails, or Git commits.
   * Keep your physical shards offline.

---

## 6. Quick Reference Cheat Sheet

| Action | Command |
| :--- | :--- |
| **Check Port Status** | `ss -tulpn \| grep -E "5432\|8000\|9000"` |
| **Start QuantumFlex** | `systemctl --user start amara-matrix amara-dashboard qf-bot` |
| **Stop QuantumFlex** | `systemctl --user stop qf-bot amara-dashboard amara-matrix` |
| **Check Memory/CPU** | `free -h && uptime` |
| **Check Mesh Status** | `tailscale status` |
| **Emergency Kill Switch** | Tap `⛔ /hardstop` in HUD or run `systemctl --user stop qf-bot` |

---

*“Security is not a product, but a process. Sovereignty is not a gift, but a discipline.”*  
**QuantumFlex // Operator Master Copy**
