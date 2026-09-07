# QuantumFlex Deployment Baseline

**Date:** 2026-09-07
**Host:** Fedora Linux 44 Workstation (Kernel: 7.1.13-200.fc44.x86_64)

## Architecture Configuration
- **Payload Constraint (Option A):** `MAX_PAYLOAD_SIZE = 16384`. Enforced strictly on the payload chunk, independent of header size.
- **Header:** 16-byte packed `QFXKHeader` with strict `ntohl`/`htonl` conversions.
- **Systemd Autonomy:** Isolated under user `quant` with `loginctl enable-linger quant`.

## Known States
- **Production Status:** "Operationally controlled personal research deployment."
- **Commercial Validation:** Not started (qf-audit pipeline pending execution against public repository).
