#!/usr/bin/env python3
"""
Quantum Flex: Leaky Integrate-and-Fire (LIF) Sentinel Node
Simulates a spiking neuron analyzing network logs, applying 
the $Y=f(x-h)+k$ bias filter logic.
"""
import sys
import math
import time
import re
import subprocess
import logging
from datetime import datetime

log = logging.getLogger("lif_sentinel")

# SNN / LIF Threshold Parameters
V_THRESHOLD = 1500.0   # Action potential threshold
V_REST = 0.0           # Resting potential
TAU_MS = 5000.0        # Membrane decay time constant (milliseconds)
SPIKE_WEIGHT = 400.0   # Voltage added per failed login event (anomaly 'k')

class LIFNeuron:
    def __init__(self, ip):
        self.ip = ip
        self.v = V_REST
        self.last_t = None
        self.total_spikes_fired = 0

    def update(self, current_time_ms, event_is_threat):
        # Apply temporal decay (leak) if time has passed
        if self.last_t is not None:
            dt = current_time_ms - self.last_t
            if dt > 0:
                # Exponential decay formula: V(t) = V_prev * e^(-dt/tau)
                decay_factor = math.exp(-dt / TAU_MS)
                self.v = self.v * decay_factor
        
        # Integrate (accumulate charge) if event is a threat
        if event_is_threat:
            self.v += SPIKE_WEIGHT
            
        self.last_t = current_time_ms
        
        # Fire Action Potential (Spike)
        if self.v >= V_THRESHOLD:
            self.fire()
            
        return self.v

    def fire(self):
        # The neuron has crossed the threshold. Alert only — no automated
        # response. IPs aren't files; there's nothing here for quarantine_chamber
        # to act on, and auto-blocking risks locking out legitimate access on a
        # false positive.
        self.total_spikes_fired += 1
        self.v = V_REST
        log.warning(
            "ACTION POTENTIAL FIRED for %s — brute-force threshold (%.0f) breached at %s",
            self.ip, V_THRESHOLD, datetime.utcnow().isoformat() + "Z",
        )

FAILED_LOGIN_RE = re.compile(r'Failed password for (?:invalid user )?\S+ from (\S+)')

def tail_f(file_path):
    """Line generator over a plain file, tailed from EOF. Requires read access
    to file_path — on this host /var/log/secure is root-only, so this path is
    for manual/ad-hoc use where you already have that access. The daemon path
    (process_journal) doesn't need it."""
    with open(file_path, "r") as f:
        f.seek(0, 2)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.1)
                continue
            yield line

def journalctl_tail(unit="sshd"):
    """Line generator over `journalctl -u <unit> -f`, readable by any user in
    a group journald grants read access to (wheel/systemd-journal on this
    host) — no root required."""
    proc = subprocess.Popen(
        ["journalctl", "-u", unit, "-f", "-n", "0"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
    )
    for line in proc.stdout:
        yield line

def _scan(lines):
    """Core detection loop: watch a line stream for failed-login events, feed
    each source IP's LIF neuron, and yield the IP whenever one fires."""
    neurons = {}
    for line in lines:
        match = FAILED_LOGIN_RE.search(line)
        if not match:
            continue
        ip = match.group(1)
        if ip not in neurons:
            neurons[ip] = LIFNeuron(ip)

        neuron = neurons[ip]
        fired_before = neuron.total_spikes_fired
        v_current = neuron.update(time.time() * 1000.0, True)
        log.info("Threat event from %s | membrane potential: %.2f", ip, v_current)

        if neuron.total_spikes_fired > fired_before:
            yield ip

def process_logs(log_file):
    """Manual/ad-hoc entry point: `python lif_sentinel.py <log_file>`."""
    log.info("SNN Sentinel Node online (file mode) — watching %s", log_file)
    for ip in _scan(tail_f(log_file)):
        pass  # LIFNeuron.fire() already logs the alert; nothing else to do here.

def process_journal(unit="sshd"):
    """Daemon entry point — no root/file-permission requirements. Yields the
    source IP each time a neuron fires, for callers that want to react."""
    log.info("SNN Sentinel Node online (journal mode) — watching journalctl -u %s", unit)
    yield from _scan(journalctl_tail(unit))

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if len(sys.argv) < 2:
        print("Usage: python lif_sentinel.py <log_file>")
        sys.exit(1)
    process_logs(sys.argv[1])
