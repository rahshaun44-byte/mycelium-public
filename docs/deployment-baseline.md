# QuantumFlex Deployment Baseline

**Date:** 2026-09-07 (architecture lock)  
**Verified on host:** 2026-09-11  
**Host:** Ubuntu 26.04.1 LTS (Resolute Raccoon) on Lenovo Yoga 7 2-in-1 14AKP10 (`qfx-yoga`)  
**Kernel (live):** `7.0.0-38-generic` (Ubuntu SMP PREEMPT_DYNAMIC)  
**Historical Note:** Migrated from pre-production testbed; Zero Fedora invariant strictly enforced.

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
