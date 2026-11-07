import json
import hashlib
import os
from datetime import datetime, timezone

LEDGER_PATH = "/home/quant/mycelium/sentinel/amara_audit.jsonl"
RESULT_PATH = "amara_advanced_adversarial_result.md"

def sha256_file(filepath):
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            sha.update(chunk)
    return sha.hexdigest()

def get_last_entry_hash(ledger_path):
    if not os.path.exists(ledger_path):
        return "0" * 64
    with open(ledger_path, "r") as f:
        lines = f.readlines()
        if not lines:
            return "0" * 64
        last_entry = json.loads(lines[-1].strip())
        return last_entry.get("entry_sha256", "0" * 64)

def append_audit():
    if not os.path.exists(RESULT_PATH):
        print(f"[!] Error: {RESULT_PATH} not found.")
        return

    result_hash = sha256_file(RESULT_PATH)
    prev_hash = get_last_entry_hash(LEDGER_PATH)
    timestamp = datetime.now(timezone.utc).isoformat()

    details = {
        "evaluation": "advanced_multi_vector_adversarial",
        "model": "amara:workstation",
        "result_file": RESULT_PATH,
        "result_sha256": result_hash,
        "status": "PROVISIONAL_PASS_INJECTION_RESISTANCE"
    }

    raw_payload = json.dumps({
        "event_type": "ADVERSARIAL_BENCHMARK_PASS",
        "capability": "Guardian",
        "timestamp": timestamp,
        "prev_sha256": prev_hash,
        "details": details
    }, sort_keys=True)
    
    entry_hash = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()

    record = {
        "event_type": "ADVERSARIAL_BENCHMARK_PASS",
        "capability": "Guardian",
        "timestamp": timestamp,
        "prev_sha256": prev_hash,
        "details": details,
        "entry_sha256": entry_hash
    }

    os.makedirs(os.path.dirname(LEDGER_PATH), exist_ok=True)
    with open(LEDGER_PATH, "a") as f:
        f.write(json.dumps(record) + "\n")

    print(f"[+] Successfully archived adversarial pass into ledger.")
    print(f"[+] Entry SHA-256: {entry_hash}")

if __name__ == "__main__":
    append_audit()
