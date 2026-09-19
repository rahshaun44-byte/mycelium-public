#!/usr/bin/env python3
"""Q1 host collector. Passive read-only observation. Zero execution authority.

Emits canonical Q1 space-separated key-value grammar.
Eliminates active network probes and non-authoritative engine assumptions.
"""
from __future__ import annotations

import os
import subprocess
import time

# --- FIX 4: Accurate WAL Storage Mount Path ---
# Target the actual Podman volume mount for pg_data
WAL_VOLUME_PATH = os.environ.get(
    "Q1_WAL_PATH",
    os.path.expanduser("~/.local/share/containers/storage/volumes/pg_data/_data")
)


def get_disk_metric(path: str = WAL_VOLUME_PATH) -> str:
    target = path if os.path.exists(path) else os.path.expanduser("~")
    try:
        st = os.statvfs(target)
        if st.f_blocks == 0:
            return "DU"
        pct_free = 100.0 * st.f_bavail / st.f_blocks
        return f"{pct_free:.16g}"
    except OSError:
        return "DU"


# --- FIX 2 & FIX 3: Fail-Closed Engine State & Passive Mesh ---
def get_engine_state() -> str:
    # Service lifecycle (systemd) has zero engine authority.
    # Fails closed to Unknown unless signed engine_state_response is present.
    return "EU"


def get_mesh_status() -> str:
    # No active network ping/probes allowed under passive observation.
    return "?"


def get_admission_state() -> str:
    # Cannot rely on process presence ('opa'). Must query authoritative state or fail closed.
    return "AU"


# --- FIX 5: Strip Interface Scope (%lo) from Listeners ---
def clean_listener_address(addr: str) -> str:
    """Strip interface specifiers (e.g. 127.0.0.53%lo -> 127.0.0.53 or tcp4:127.0.0.53%lo:53 -> tcp4:127.0.0.53:53)."""
    if ":" in addr:
        parts = addr.rsplit(":", 1)
        first_colon = parts[0].find(":")
        if first_colon >= 0:
            proto = parts[0][:first_colon]
            raw_addr = parts[0][first_colon + 1 :]
            clean_ip = raw_addr.split("%")[0]
            return f"{proto}:{clean_ip}:{parts[1]}"
    return addr.split("%")[0]


def get_listeners() -> list[str]:
    """Parses ss -ltn to capture protocol and bind targets.

    Filters out ephemeral ports (>32768) to eliminate noise.
    """
    try:
        out = subprocess.check_output(["ss", "-ltn"], text=True).strip().split("\n")
        listeners = []
        for line in out[1:]:  # Skip header
            parts = line.split()
            if len(parts) >= 4 and parts[0] == "LISTEN":
                local_addr_port = parts[3]
                if "]" in local_addr_port:
                    addr, port_str = local_addr_port.rsplit(":", 1)
                    addr = addr.strip("[]")
                    proto = "tcp6"
                else:
                    addr, port_str = local_addr_port.rsplit(":", 1)
                    proto = "tcp4"

                port = int(port_str)
                if port < 32768:
                    clean_ip = addr.split("%")[0]
                    listeners.append(f"{proto}:{clean_ip}:{port}")
        return listeners
    except Exception:
        return []


def format_canonical_record(listeners: list[str], timestamp: int | None = None) -> str:
    if timestamp is None:
        timestamp = int(time.time())

    # Format: Q1 E=... A=... P=... M=... D=... T=...
    e_val = get_engine_state()
    a_val = get_admission_state()
    m_val = get_mesh_status()
    d_val = get_disk_metric()

    # Sort and join canonical listeners
    cleaned_listeners = sorted(set(clean_listener_address(p) for p in listeners))
    p_val = ",".join(cleaned_listeners) if cleaned_listeners else "NONE"

    # --- FIX 1: Canonical Space-Separated Key-Value Grammar ---
    return f"Q1 E={e_val} A={a_val} P={p_val} M={m_val} D={d_val} T={timestamp}"


def main() -> None:
    listeners = get_listeners()
    print(format_canonical_record(listeners))


if __name__ == "__main__":
    main()
