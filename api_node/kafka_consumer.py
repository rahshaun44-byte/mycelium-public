#!/usr/bin/env python3
import json
import logging
import os
import psycopg2
import urllib.request
from pathlib import Path
from kafka import KafkaConsumer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("qf-ingestion-node")

# Load environment variables from .env if present
base_dir = Path(__file__).resolve().parent.parent
for env_path in [Path(".env"), base_dir / ".env"]:
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())
        break

KAFKA_BROKER = "100.64.1.34:9092"
KAFKA_TOPIC = "qf-telemetry"
KAFKA_GROUP = "qf-amara-athena-group"
ATHENA_INGEST_URL = "http://127.0.0.1:8001/ingest"

def get_amara_connection():
    return psycopg2.connect(
        host="127.0.0.1",
        port=5432,
        dbname="telemetry",
        user=os.environ.get("DB_USER", "ghostnode"),
        password=os.environ.get("DB_PASSWORD", ""),
        connect_timeout=3
    )

def push_to_athena(payload):
    try:
        req = urllib.request.Request(
            ATHENA_INGEST_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.error(f"Athena neural ingest failed: {e}")

def process_pulse(msg_value):
    try:
        data = json.loads(msg_value)
        vitals = data.get("data") if isinstance(data.get("data"), dict) else data
        
        node_id = vitals.get("hostname") or data.get("hostname") or data.get("source", "unknown-node")
        cpu_load = vitals.get("cpu_load_1m", vitals.get("load_1m", data.get("cpu_load_1m", 0.0)))
        ram_used = vitals.get("ram_used_pct", data.get("ram_used_pct", 0.0))
        timestamp = vitals.get("timestamp", data.get("timestamp"))
        status = vitals.get("status", data.get("status", "PULSE_OK"))
        temp_c = vitals.get("temp_c", data.get("temp_c", "N/A"))
        active_kem = vitals.get("active_kem", data.get("active_kem", "NULL"))
        verdict = vitals.get("verdict", data.get("verdict", "ADMIT"))
        
        note = f"PQC KEM: {active_kem} | Temp: {temp_c}°C | Gate: {verdict}"

        # 1. AMARA PostgreSQL Structured Insert
        with get_amara_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO telemetry_log (node_id, cpu_load_1m, ram_used_pct, timestamp, status, note)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (node_id, cpu_load, ram_used, timestamp, status, note))
            conn.commit()

        # 2. Athena ChromaDB Neural Embedding
        narrative = f"Host {node_id} telemetry pulse: RAM {ram_used}%, Temp {temp_c}°C, KEM {active_kem}, Gate: {verdict}"
        athena_payload = {
            "text": narrative,
            "source": "qf-telemetry-stream",
            "metadata": {"hostname": node_id, "verdict": verdict, "status": status}
        }
        push_to_athena(athena_payload)
        
        logger.info(f"[INGESTED] Pulse from {node_id} anchored in AMARA and embedded in Athena.")

    except Exception as e:
        logger.error(f"Pulse processing failure: {e}")

def main():
    logger.info(f"Initializing Gatekeeper Ingestion Membrane on {KAFKA_BROKER}")
    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=[KAFKA_BROKER],
        group_id=KAFKA_GROUP,
        auto_offset_reset='latest',
        enable_auto_commit=True,
        value_deserializer=lambda x: x.decode('utf-8')
    )

    for message in consumer:
        process_pulse(message.value)

if __name__ == "__main__":
    main()
