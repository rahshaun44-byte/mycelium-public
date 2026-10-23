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

BROKER_HOST = os.getenv("QF_KAFKA_BROKER", "100.64.1.19:9092")
TOPIC_NAME = os.getenv("QF_KAFKA_TOPIC", "qf-telemetry")
POLL_INTERVAL = int(os.getenv("QF_TELEMETRY_INTERVAL", "15"))

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

    # Read active PQC configuration
    conf_path = Path("/home/quant/mycelium/mcp_layer/crypto_provider.conf")
    active_kem = "ML-KEM-768"
    if conf_path.exists():
        for line in conf_path.read_text().splitlines():
            if line.startswith("active_kem="):
                active_kem = line.split("=", 1)[1].strip()
    vitals["active_kem"] = active_kem
    vitals["cmvp_certificate"] = None  # Strict NULL policy

    # Read CPU temperature
    tz_path = Path("/sys/class/thermal/thermal_zone0/temp")
    if tz_path.exists():
        try:
            vitals["temp_c"] = round(int(tz_path.read_text().strip()) / 1000.0, 1)
        except Exception:
            pass

    return vitals

def main():
    if not KAFKA_AVAILABLE:
        logger.error("kafka-python-ng is not installed in the active environment.")
        sys.exit(1)

    logger.info("Starting Quantum Flex Telemetry Forwarder...")
    logger.info("Connecting to Kafka broker at %s (topic: %s)...", BROKER_HOST, TOPIC_NAME)

    producer = None
    while producer is None:
        try:
            producer = KafkaProducer(
                bootstrap_servers=[BROKER_HOST],
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                request_timeout_ms=5000,
                retries=3
            )
            logger.info("Successfully connected to Kafka broker %s", BROKER_HOST)
        except Exception as e:
            logger.warning("Kafka broker not reachable (%s). Retrying in 5s...", e)
            time.sleep(5.0)

    try:
        while True:
            vitals = get_system_vitals()
            payload = {
                "source": "yoga7-master",
                "event": "NODE_TELEMETRY_PULSE",
                "data": vitals
            }

            try:
                future = producer.send(TOPIC_NAME, payload)
                record = future.get(timeout=5)
                logger.info(
                    "Published telemetry pulse (RAM: %s%%, Temp: %s°C, KEM: %s) -> partition %s offset %s",
                    vitals.get("ram_used_pct"),
                    vitals.get("temp_c", "N/A"),
                    vitals.get("active_kem"),
                    record.partition,
                    record.offset
                )
            except Exception as e:
                logger.error("Failed to publish telemetry packet: %s", e)

            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        logger.info("Shutting down telemetry forwarder...")
    finally:
        if producer:
            producer.close()

if __name__ == "__main__":
    main()
