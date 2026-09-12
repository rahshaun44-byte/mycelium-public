# QuantumFlex Deployment Baseline

**Date:** 2026-09-07 (architecture lock)  
**Verified on host:** 2026-09-11  
**Host:** Fedora Linux 44 Workstation  
**Kernel (live):** `7.2.4-200.fc44.x86_64`  
**Kernel (original lock):** `7.1.13-200.fc44.x86_64`

Interactive operator: `quant`. Repo: `/home/quant/mycelium`.

## Architecture Configuration
- **Payload Constraint (Option A):** `MAX_PAYLOAD_SIZE = 16384`. Enforced strictly on the payload chunk, independent of header size (`include/quantum-flex/wire_framing.hpp`).
- **Header:** 16-byte packed `QFXKHeader` with strict `ntohl`/`htonl` conversions. Live serialize uses 2-byte magic `QF`, not a 4-byte `"QFXK"` uint32.
- **Systemd Autonomy:** Isolated under user `quant` with `loginctl enable-linger quant`.
- **Engine IPC:** mTLS on `127.0.0.1:9444` (`quantum-flex-engine-mycelium.service`).
- **Application binds:** loopback only. Remote access is Tailscale Serve, not `0.0.0.0`.

## Known States
- **Production Status:** Operationally controlled personal research deployment.
- **Commercial Validation:** Not started against the public repository. Local `qf-audit-output/` on this host is not a public-repo CMVP/qf-audit pipeline.
- **CMVP / CAVP:** Unvalidated. Internal KATs are not certificates.
