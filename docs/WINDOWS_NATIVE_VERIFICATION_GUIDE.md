# 🌌 QUANTUM FLEX: WINDOWS NATIVE OPERATIONAL & VERIFICATION GUIDE
**Document:** QF-VERIFY-WIN-001  
**Architecture:** Windows 11 Native (MSVC / `wevtapi` / PostgreSQL 15)  
**Security Posture:** Zero-Trust Immutable / Append-Only Ingestion  
**Root Architect:** Rahshaun Chambers

---

## 1. Executive Overview
This guide validates the operational baseline for the Quantum Flex telemetry engine running bare-metal on Windows 11. It supersedes all legacy Linux (`libsystemd` / Fedora) documentation.

---

## 2. Hardened Security Controls

### Control 1: Database Immutability & Least Privilege
The `quantum_sentinel` engine role is strictly bound to append-only semantics.

```sql
-- Privilege Lock Applied in enforce_immutability.sql
REVOKE ALL PRIVILEGES ON TABLE quantum_telemetry_channel FROM PUBLIC;
REVOKE ALL PRIVILEGES ON TABLE quantum_telemetry_channel FROM quantum_sentinel;

-- Append-only & Audit Access
GRANT INSERT, SELECT ON TABLE quantum_telemetry_channel TO quantum_sentinel;
GRANT USAGE, SELECT ON SEQUENCE quantum_telemetry_channel_id_seq TO quantum_sentinel;
```

#### Immutability Verification Suite:
| Action Attempted | Role | Result | Status |
|---|---|---|---|
| `INSERT INTO quantum_telemetry_channel` | `quantum_sentinel` | `INSERT 0 1` | ✅ **PERMITTED (Append-Only)** |
| `SELECT * FROM quantum_telemetry_channel` | `quantum_sentinel` | Rows returned | ✅ **PERMITTED (Audit)** |
| `UPDATE quantum_telemetry_channel ...` | `quantum_sentinel` | `ERROR: permission denied` | 🛡️ **BLOCKED (Tamper-Proof)** |
| `DELETE FROM quantum_telemetry_channel` | `quantum_sentinel` | `ERROR: permission denied` | 🛡️ **BLOCKED (Tamper-Proof)** |
| `TRUNCATE quantum_telemetry_channel` | `quantum_sentinel` | `ERROR: permission denied` | 🛡️ **BLOCKED (Tamper-Proof)** |

---

### Control 2: mTLS & Cryptographic Transport
The ingestion pipeline supports mutual TLS validation via the Ed25519 PKI forge (`forge_pki.py`):

- **Root CA:** `pki/ca/ca.crt`
- **Server Identity:** `pki/server/server.crt` + `server.key` (SAN: `127.0.0.1`, `localhost`)
- **Client Identity:** `pki/client/client.crt` + `client.key`

#### Connection String for mTLS Enforcement:
```cpp
const char* conninfo = "host=127.0.0.1 port=5432 dbname=quantum_flex user=quantum_sentinel "
                       "sslmode=verify-full sslrootcert=pki/ca/ca.crt "
                       "sslcert=pki/client/client.crt sslkey=pki/client/client.key";
```

---

## 3. Build & Compilation Guide

### Prerequisites
- Visual Studio 2022 Build Tools (`Microsoft.VisualStudio.Workload.VCTools`)
- Windows 11 SDK (`Microsoft.VisualStudio.Component.Windows11SDK.22621`)
- PostgreSQL 15 for Windows (Header & Library directories)

### CMake Build
```powershell
cmake -B build -S .
cmake --build build --config Release
```

### Direct MSVC Build
```powershell
& "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\Launch-VsDevShell.ps1" -Arch amd64
cl.exe /std:c++20 /EHsc /I"C:\Program Files\PostgreSQL\15\include" sentinel_push.cpp wevtapi.lib /link /LIBPATH:"C:\Program Files\PostgreSQL\15\lib" libpq.lib /out:sentinel_push.exe
```

---

## 4. Live Telemetry Verification Sequence

1. **Launch Sentinel Engine:**
   ```powershell
   .\sentinel_push.exe
   ```
2. **Inject Windows Event:**
   ```powershell
   [System.Diagnostics.EventLog]::WriteEntry(".NET Runtime", "Quantum Flex live verification pulse - Node: yoga-win11-master", [System.Diagnostics.EventLogEntryType]::Information, 1337)
   ```
3. **Verify PostgreSQL Persistence:**
   ```powershell
   & "C:\Program Files\PostgreSQL\15\bin\psql.exe" -U quantum_sentinel -h 127.0.0.1 -p 5432 -d quantum_flex -c "SELECT id, node_id, timestamp, substring(payload from 1 for 100) AS payload_preview, created_at FROM quantum_telemetry_channel ORDER BY id DESC LIMIT 5;"
   ```
