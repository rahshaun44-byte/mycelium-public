#!/usr/bin/env python3
"""
Quantum Flex Kafka Telemetry Forwarder
======================================
Streams live operational metrics, PQC invariant states, and biological vitals
from the Yoga 7 master host to the g6pro Kafka broker (HP ProBook 450 G6, KRaft).

Target Broker: 100.64.1.19:9092 (g6pro, Tailscale mesh)
Target Topic:  qf-telemetry
"""

import os
import sys
import time
import json
import uuid
import signal
import socket
import logging
from pathlib import Path
from datetime import datetime, timezone

try:
    from kafka import KafkaProducer
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [QF-KAFKA-FORWARDER] %(message)s"
)
logger = logging.getLogger("qf_kafka_forwarder")

# Signal handling for clean systemd shutdown
shutdown_requested = False

def handle_shutdown(signum, frame):
    global shutdown_requested
    try:
        sig_name = signal.Signals(signum).name
    except Exception:
        sig_name = str(signum)
    logger.info("Received %s signal. Requesting graceful shutdown...", sig_name)
    shutdown_requested = True

signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)

# Configuration with validation
BROKER_HOST = os.getenv("QF_KAFKA_BROKER", "100.64.1.19:9092")
TOPIC_NAME = os.getenv("QF_KAFKA_TOPIC", "qf-telemetry")

try:
    raw_interval = os.getenv("QF_TELEMETRY_INTERVAL", "15")
    POLL_INTERVAL = int(raw_interval)
    if POLL_INTERVAL <= 0:
        raise ValueError("interval must be greater than 0")
except ValueError as e:
    logger.warning("Invalid QF_TELEMETRY_INTERVAL (%s). Defaulting to 15s.", e)
    POLL_INTERVAL = 15

# Unique session identifier across process lifecycles
PRODUCER_SESSION_ID = str(uuid.uuid4())

def get_system_vitals():
    vitals = {
        "hostname": socket.gethostname(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "load_1m": os.getloadavg()[0] if hasattr(os, "getloadavg") else 0.0,
    }

    # Read memory info
    meminfo_path = Path("/proc/meminfo")
    if meminfo_path.exists():
        mem = {}
        for line in meminfo_path.read_text().splitlines():
            parts = line.split(":")
            if len(parts) == 2:
                mem[parts[0].strip()] = parts[1].strip()
        total_kb = int(mem.get("MemTotal", "0 kB").split()[0])
        avail_kb = int(mem.get("MemAvailable", "0 kB").split()[0])
        vitals["ram_total_mb"] = round(total_kb / 1024, 2)
        vitals["ram_available_mb"] = round(avail_kb / 1024, 2)
        vitals["ram_used_pct"] = round((1.0 - (avail_kb / total_kb)) * 100, 2) if total_kb > 0 else 0.0

    # Distinguish configured PQC parameters from runtime verification
    conf_path = Path("/home/quant/mycelium/mcp_layer/crypto_provider.conf")
    configured_kem = "ML-KEM-768"
    if conf_path.exists():
        for line in conf_path.read_text().splitlines():
            if line.startswith("active_kem="):
                configured_kem = line.split("=", 1)[1].strip()
    vitals["configured_kem"] = configured_kem
    vitals["runtime_kem"] = "ML-KEM-768"
    vitals["runtime_kem_verified"] = False  # Strictly False until proven by session handshake
    vitals["cmvp_certificate"] = None       # Strict NULL policy

    # TPM 2.0 Silicon Evidence Reference (explicitly distinguished from verified attestation)
    tpm_available = Path("/dev/tpmrm0").exists() or Path("/dev/tpm0").exists()
    vitals["tpm"] = {
        "device_available": tpm_available,
        "pcr_bank": "sha256",
        "pcr_selection": [15],
        "quote_verified": False,
        "attestation_status": "UNVERIFIED"
    }

    # Read CPU temperature
    tz_path = Path("/sys/class/thermal/thermal_zone0/temp")
    if tz_path.exists():
        try:
            vitals["temp_c"] = round(int(tz_path.read_text().strip()) / 1000.0, 1)
        except Exception:
            pass

    return vitals

def responsive_sleep(seconds: float):
    """Sleep in 0.25s slices so shutdown_requested responds immediately."""
    end_time = time.monotonic() + seconds
    while not shutdown_requested and time.monotonic() < end_time:
        time.sleep(min(0.25, end_time - time.monotonic()))

def main():
    if not KAFKA_AVAILABLE:
        logger.error("kafka-python-ng is not installed in the active environment.")
        sys.exit(1)

    logger.info("Starting Quantum Flex Telemetry Forwarder (Session: %s)...", PRODUCER_SESSION_ID)
    logger.info("Configured Broker: %s | Topic: %s | Interval: %ds", BROKER_HOST, TOPIC_NAME, POLL_INTERVAL)

    producer = None
    backoff = 2.0
    while producer is None and not shutdown_requested:
        try:
            producer = KafkaProducer(
                bootstrap_servers=[BROKER_HOST],
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                request_timeout_ms=5000,
                retries=3
            )
            logger.info("Successfully connected to Kafka broker %s", BROKER_HOST)
        except Exception as e:
            logger.warning("Kafka broker not reachable (%s). Retrying in %.1fs...", e, backoff)
            responsive_sleep(backoff)
            backoff = min(backoff * 1.5, 30.0)

    sequence_id = 0
    consecutive_failures = 0
    total_failures = 0

    try:
        while not shutdown_requested:
            sequence_id += 1
            vitals = get_system_vitals()
            payload = {
                "schema_version": "1.0.0",
                "event_id": str(uuid.uuid4()),
                "producer_session": PRODUCER_SESSION_ID,
                "sequence_id": sequence_id,
                "source": "yoga7-master",
                "event": "NODE_TELEMETRY_PULSE",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": vitals
            }

            try:
                future = producer.send(TOPIC_NAME, payload)
                record = future.get(timeout=5)

                if consecutive_failures > 0:
                    logger.info("Kafka connection recovered after %d consecutive failure(s).", consecutive_failures)
                    consecutive_failures = 0

                logger.info(
                    "Published telemetry seq=%d (RAM: %s%%, Temp: %s°C, KEM: %s) -> partition %s offset %s",
                    sequence_id,
                    vitals.get("ram_used_pct"),
                    vitals.get("temp_c", "N/A"),
                    vitals.get("configured_kem"),
                    record.partition,
                    record.offset
                )
            except Exception as e:
                consecutive_failures += 1
                total_failures += 1
                logger.error(
                    "Failed to publish telemetry packet seq=%d (consecutive: %d, total: %d): %s",
                    sequence_id,
                    consecutive_failures,
                    total_failures,
                    e
                )

            responsive_sleep(POLL_INTERVAL)

    except Exception as e:
        logger.exception("Unexpected error in telemetry loop: %s", e)
    finally:
        if producer is not None:
            logger.info("Flushing pending messages and closing Kafka producer (timeout=10s)...")
            try:
                producer.flush(timeout=5)
                producer.close(timeout=10)
                logger.info("Producer successfully closed.")
            except Exception as e:
                logger.warning("Error during producer close: %s", e)
        logger.info("Telemetry forwarder shutdown complete. Total pulses generated: %d, total failures: %d", sequence_id, total_failures)

if __name__ == "__main__":
    main()
