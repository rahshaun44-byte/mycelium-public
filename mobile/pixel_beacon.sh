#!/bin/sh
# QuantumFlex Mobile Heartbeat Beacon (Pixel 11 Pro / Titan M3)
# Communicates over encrypted Tailscale mesh to Yoga 7 gateway

TARGET_HOST="${QF_GATEWAY:-100.64.1.31}"
TARGET_PORT="${QF_GATEWAY_PORT:-8080}"
TARGET="http://${TARGET_HOST}:${TARGET_PORT}/api/v1/telemetry/heartbeat"
NODE_ID="qfx-pixel"

# Gather local entropy from kernel pool
ENTROPY_H=$(cat /proc/sys/kernel/random/entropy_avail 2>/dev/null || echo 0)

# Construct payload and emit to API gateway with strict timeout
# Returns 202 Accepted immediately so mobile radio can return to low-power state
if command -v curl >/dev/null 2>&1; then
    curl -s --connect-timeout 3 --max-time 5 -X POST "$TARGET" \
        -H "Content-Type: application/json" \
        -H "X-Node-ID: $NODE_ID" \
        -d "{
            \"node_id\": \"$NODE_ID\",
            \"hardware_attestation\": \"Titan-M3\",
            \"entropy_h\": $ENTROPY_H,
            \"pqc_signature\": \"verified_token\",
            \"pqc_algorithm\": \"ML-KEM-768\",
            \"tailscale_ip\": \"100.64.1.16\"
        }" >/dev/null 2>&1
elif command -v wget >/dev/null 2>&1; then
    wget -q -O- --timeout=5 --post-data="{\"node_id\": \"$NODE_ID\", \"hardware_attestation\": \"Titan-M3\", \"entropy_h\": $ENTROPY_H, \"pqc_signature\": \"verified_token\", \"pqc_algorithm\": \"ML-KEM-768\", \"tailscale_ip\": \"100.64.1.16\"}" \
        --header="Content-Type: application/json" "$TARGET" >/dev/null 2>&1
fi
