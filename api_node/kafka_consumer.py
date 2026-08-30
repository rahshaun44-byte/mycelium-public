import os
import sys
import json
import logging
import psycopg2
from pathlib import Path
from kafka import KafkaConsumer

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("KafkaConsumerDaemon")

# Correct paths for this host
BASE_DIR = Path(__file__).resolve().parent.parent

# Auto-load .env if present
env_file = BASE_DIR / ".env"
if env_file.exists():
    logger.info(f"Loading environment variables from {env_file}")
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

# Configuration settings
DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = int(os.environ.get("DB_PORT", 5432))
DB_NAME = os.environ.get("QUANTUM_DB_NAME", "quantum_flex")
DB_USER = os.environ.get("QUANTUM_SENTINEL_USER", "quantum_sentinel")
DB_PASS = os.environ.get("QUANTUM_SENTINEL_PASSWORD", os.environ.get("POSTGRES_PASSWORD", os.environ.get("SENTINEL_DB_PASSWORD", "")))

KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "100.64.1.15:9092")
KAFKA_TOPIC = "quantum-telemetry-raw"
KAFKA_GROUP = "quantum-flex-consumer-group"

def get_db_connection():
    """Returns a direct append-only connection to the persistence layer."""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        connect_timeout=3
    )

def main():
    logger.info("Initializing Quantum Flex Layer 4 Stream Consumer Daemon...")
    logger.info(f"Targeting Kafka Broker: {KAFKA_BOOTSTRAP_SERVERS}")
    logger.info(f"Targeting Database: {DB_HOST}:{DB_PORT}/{DB_NAME}")

    # Verify Database Connection on startup
    try:
        conn = get_db_connection()
        conn.close()
        logger.info("[+] Database connection check: SUCCESS")
    except Exception as e:
        logger.error(f"[-] Database connection failed: {e}")
        sys.exit(1)

    # Initialize Kafka Consumer
    try:
        consumer = KafkaConsumer(
            KAFKA_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(","),
            group_id=KAFKA_GROUP,
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            api_version=(3, 6, 0)
        )
        logger.info(f"[+] Subscribed successfully to topic: {KAFKA_TOPIC}")
    except Exception as e:
        logger.error(f"[-] Kafka Consumer initialization failed: {e}")
        sys.exit(1)

    logger.info("[*] Listening for incoming stream records...")
    
    conn = None
    cur = None
    try:
        for message in consumer:
            logger.info(f"[*] Received message: partition={message.partition}, offset={message.offset}")
            
            # Safe JSON deserialization
            try:
                raw_value = message.value.decode('utf-8') if message.value else ""
                data = json.loads(raw_value)
            except Exception as parse_err:
                logger.warning(f"[-] Failed to deserialize JSON payload at offset {message.offset}: {parse_err}")
                continue
                
            node_id = data.get("node_id")
            timestamp = data.get("timestamp")
            payload = data.get("payload")

            if not node_id or not timestamp or payload is None:
                logger.warning("[-] Skipping malformed telemetry packet")
                continue

            # Persistent database write with retry logic
            committed = False
            retries = 3
            while not committed and retries > 0:
                try:
                    if conn is None or conn.closed:
                        conn = get_db_connection()
                        cur = conn.cursor()
                    
                    cur.execute(
                        """
                        INSERT INTO quantum_telemetry_channel (node_id, timestamp, payload)
                        VALUES (%s, %s, %s);
                        """,
                        (node_id, timestamp, payload)
                    )
                    conn.commit()
                    committed = True
                    logger.info(f"[+] Committed record to PostgreSQL: node_id={node_id}, ts={timestamp}")
                except Exception as db_err:
                    retries -= 1
                    logger.error(f"[-] Database write failed (retries left: {retries}): {db_err}")
                    if conn:
                        try:
                            conn.rollback()
                            conn.close()
                        except:
                            pass
                        conn = None
                        cur = None
                    if retries > 0:
                        import time
                        time.sleep(1)
            
            if not committed:
                logger.critical("[-] FAILED to commit packet to database after retries. Message dropped or buffer needed.")

    except KeyboardInterrupt:
        logger.info("[*] Stopping consumer daemon gracefully...")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    main()
