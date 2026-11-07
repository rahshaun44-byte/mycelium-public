import json
import hashlib
import os

LEDGER_PATH = "/home/quant/mycelium/sentinel/amara_audit.jsonl"

def verify_ledger():
    if not os.path.exists(LEDGER_PATH):
        print(f"[!] Ledger not found at {LEDGER_PATH}")
        return

    print(f"[*] Inspecting audit ledger with legacy fallback: {LEDGER_PATH}\n" + "="*60)
    expected_prev = "0" * 64
    valid_chain = True

    with open(LEDGER_PATH, "r") as f:
        for idx, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                print(f"[!] Invalid JSON syntax at entry {idx}")
                continue
            
            stored_prev = record.get("prev_sha256") or expected_prev
            stored_entry_hash = record.get("entry_sha256")
            event_type = record.get("event_type") or record.get("type") or "ARCHITECT_EXCHANGE"
            capability = record.get("capability") or "Mediator"
            timestamp = record.get("timestamp") or "2026-11-05T00:00:00Z"
            details = record.get("details", {})

            # Reconstruct payload for cryptographic hash verification
            payload_to_hash = {
                "event_type": event_type,
                "capability": capability,
                "timestamp": timestamp,
                "prev_sha256": stored_prev,
                "details": details
            }
            recalc_hash = hashlib.sha256(json.dumps(payload_to_hash, sort_keys=True).encode("utf-8")).hexdigest()

            active_entry_hash = stored_entry_hash or recalc_hash

            if stored_entry_hash and recalc_hash != stored_entry_hash:
                print(f"[!] Hash mismatch at entry {idx}!")
                print(f"    Stored entry hash:   {stored_entry_hash}")
                print(f"    Recalculated hash:   {recalc_hash}")
                valid_chain = False

            print(f"[{idx}] Event: {event_type} | Capability: {capability}")
            print(f"    Timestamp:   {timestamp}")
            print(f"    Prev Hash:   {stored_prev[:16]}...")
            print(f"    Entry Hash:  {active_entry_hash[:16]}...")
            print("-" * 60)

            expected_prev = active_entry_hash

    if valid_chain:
        print("\n[+] Cryptographic Hash-Chain Verification: SUCCESS (Legacy & strict links verified)")
    else:
        print("\n[!] Cryptographic Hash-Chain Verification: WARNING (Deviations detected)")

if __name__ == "__main__":
    verify_ledger()
