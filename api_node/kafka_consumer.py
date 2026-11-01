import json
import logging
import os
import sys
import urllib.request
from pathlib import Path

base_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(base_dir))
from src.privacy_filter import PrivacyFilter

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("qf-ingestion-node")

# Load environment variables from .env if present
for env_path in [Path(".env"), base_dir / ".env"]:
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())
        break

KAFKA_BROKER = os.environ.get("KAFKA_BROKER", "127.0.0.1:9092")
KAFKA_TOPIC = os.environ.get("KAFKA_TOPIC", "qf-telemetry")
KAFKA_GROUP = "qf-amara-athena-group"
ATHENA_INGEST_URL = "http://127.0.0.1:8001/ingest"


def get_amara_connection():
    """
    Acquires an append-only (qf_writer) PostgreSQL connection via role-credential isolation.
    Fails closed if credentials cannot be resolved or connection cannot be established.
    Never falls back to administrative or shared credentials.
    """
    from src.db_credentials import DatabaseRole, open_role_connection
    return open_role_connection(
        role=DatabaseRole.WRITER,
        dbname=os.environ.get("AMARA_DB_NAME", os.environ.get("DB_NAME", "telemetry")),
    )



def athena_ingest_headers():
    """Athena /ingest is fail-closed unless x-api-key matches the configured secret."""
    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get("ATHENA_API_KEY") or os.environ.get("DASHBOARD_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key
    return headers


def push_to_athena(payload):
    try:
        req = urllib.request.Request(
            ATHENA_INGEST_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers=athena_ingest_headers()
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.error(f"Athena neural ingest failed: {e}")
        return None


def process_pulse(msg_value):
    """Persist one telemetry pulse.

    Returns True when the Kafka offset is safe to commit:
    - AMARA insert succeeded (Athena is best-effort and must not duplicate rows)
    - or the payload is dropped due to opt-out privacy filter
    - or the payload is a poison pill that will never succeed
    Returns False on transient AMARA/DB failure so the message is retried.
    """
    try:
        data = json.loads(msg_value)
    except (TypeError, json.JSONDecodeError) as e:
        logger.error(f"Pulse processing failure: dropping malformed payload: {e}")
        return True

    try:
        vitals = data.get("data") if isinstance(data.get("data"), dict) else data

        # Edge privacy & opt-out filter: check node-level SSID
        top_level_ssid = vitals.get("ssid") or (data.get("ssid") if isinstance(data, dict) else None)
        if top_level_ssid and PrivacyFilter.should_exclude_ssid(top_level_ssid):
            logger.warning(f"Dropping telemetry pulse from {data.get('hostname', 'unknown') if isinstance(data, dict) else 'unknown'}: opt-out SSID detected ({top_level_ssid})")
            return True

        if "frames" in vitals and isinstance(vitals["frames"], list):
            sanitized = [
                f for f in vitals["frames"]
                if isinstance(f, dict) and PrivacyFilter.sanitize_telemetry_frame(f) is not None
            ]
            if vitals["frames"] and not sanitized:
                logger.warning(f"Dropping telemetry pulse from {data.get('hostname', 'unknown') if isinstance(data, dict) else 'unknown'}: all telemetry frames opted out")
                return True
            vitals["frames"] = sanitized
        elif PrivacyFilter.contains_optout(data):
            logger.warning(f"Dropping telemetry pulse from {data.get('hostname', 'unknown') if isinstance(data, dict) else 'unknown'}: opt-out privacy tag detected")
            return True

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

        # 2. Athena ChromaDB Neural Embedding (best-effort; do not block AMARA commit)
        narrative = f"Host {node_id} telemetry pulse: RAM {ram_used}%, Temp {temp_c}°C, KEM {active_kem}, Gate: {verdict}"
        athena_payload = {
            "text": narrative,
            "source": "qf-telemetry-stream",
            "metadata": {"hostname": node_id, "verdict": verdict, "status": status}
        }
        athena_ok = push_to_athena(athena_payload) is not None
        if athena_ok:
            logger.info(f"[INGESTED] Pulse from {node_id} anchored in AMARA and embedded in Athena.")
        else:
            logger.warning(f"[INGESTED] Pulse from {node_id} anchored in AMARA; Athena embedding skipped.")
        return True

    except Exception as e:
        logger.error(f"Pulse processing failure: {e}")
        return False


def consume_messages(consumer):
    """Commit offsets only after AMARA persistence succeeds (or a poison pill)."""
    for message in consumer:
        if process_pulse(message.value):
            consumer.commit()


def main():
    from kafka import KafkaConsumer

    logger.info(f"Initializing Gatekeeper Ingestion Membrane on {KAFKA_BROKER}")
    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=[KAFKA_BROKER],
        group_id=KAFKA_GROUP,
        auto_offset_reset='latest',
        enable_auto_commit=False,
        value_deserializer=lambda x: x.decode('utf-8')
    )

    consume_messages(consumer)

if __name__ == "__main__":
    main()
