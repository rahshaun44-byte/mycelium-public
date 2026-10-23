# QF-A7 Close Record: TLS Floor & Operational Continuity

```text
QF-A7 close
commit: 9fd9569
TLS floor: PASS (live 9444)
restart→LOCKED: PASS
re-unseal 3/5: PASS (USB unmounted)
A5 host judge: PASS
ghost-sink seq1: PASS
decision: FREEZE_A7
```

---

## 1. Summary of Gate Verification

| Boundary | Final Status | Verification Mechanism |
|---|---|---|
| **TLS 1.3 Minimum Floor** | **PASS** | `SSL_CTX_set_min_proto_version(ssl_ctx_, TLS1_3_VERSION)` enforced with fatal error handling |
| **TLS 1.2 Negative Control** | **PASS (REJECTED)** | Client forced to TLS 1.2 rejected on production port `9444` (`TLSV1_ALERT_PROTOCOL_VERSION`) |
| **Client Auth & Rogue CA** | **PASS (FAIL-CLOSED)** | No cert rejected (`TLSV13_ALERT_CERTIFICATE_REQUIRED`); foreign CA rejected (`TLSV1_ALERT_UNKNOWN_CA`) |
| **Cold Restart Invariant** | **PASS (LIVE-VERIFIED)** | `systemctl --user restart` destroyed in-memory salt; returned `ERR|NODE_LOCKED` |
| **3-of-5 Re-Unseal** | **PASS** | Unlocked via `shard_1.txt`, `shard_2.txt`, and transient USB `shard_3.txt` -> `ACK|NODE_UNLOCKED` |
| **Media Hygiene** | **PASS** | `QFX_VAULT` (`/dev/sda1`) unmounted immediately post-ceremony (`findmnt` empty; `/run/media/quant` clean) |
| **Core Dump Lockdown** | **PASS** | `prlimit --core=0:0` active on PID `34325` (engine) and PID `35959` (ghost sink); `LimitCORE=0` in systemd units |
| **Host Judge (QF-A5)** | **PASS** | 13/13 artifacts byte-accurate against signed manifest; `verify-provenance` verdict `TRUSTED -> ALLOW` |
| **Local Anomaly Sink** | **PASS** | `quantumflex-ghost-sink` running on `127.0.0.1:19443`; synthetic event `synth-ev-20260920-001` absorbed |
| **Hash-Chain Continuity** | **PASS** | Ledger sequence `1`, `previous_hash = 0000...`, `record_hash = ffb9e9d6...` recorded on disk |

---

## 2. Security Claim Verification

- **CL-02 (Local Ghost Sink Absorption)**: Updated with live verified SHA-256 hash-chained JSONL ledger receipts on `127.0.0.1:19443` ($H_{\text{attack}} = 0$).
- **CL-15 (TLS 1.3 Protocol Floor & Downgrade Rejection)**: Added and verified with 4/4 live transport controls.
- **Commit Baseline**: Bumped to `507e046` / `9fd9569`.

---

## 3. Post-Ceremony Operational Posture

The node maintains complete local correctness, deterministic admission, and evidence containment without external infrastructure dependencies.
Decision: **FREEZE_A7**.
