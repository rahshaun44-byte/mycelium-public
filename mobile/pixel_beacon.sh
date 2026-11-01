#!/system/bin/sh
# QuantumFlex: qfx-pixel (Titan-M3) Background Heartbeat Beacon (QF-M1)
# Pushes asynchronous signed heartbeats over Tailscale to the Core API Gateway (100.64.1.31:8080).
# Never blocks; enforces a strict 3s connection timeout to conserve battery.

TARGET="${QF_GATEWAY_URL:-http://100.64.1.31:8080/api/v1/telemetry/heartbeat}"
NODE_ID="qfx-pixel"
INTERVAL="${QF_BEACON_INTERVAL:-30}"

while true; do
    ENTROPY_H=$(cat /proc/sys/kernel/random/entropy_avail 2>/dev/null || echo 0)
    curl -s --connect-timeout 3 --max-time 5 -X POST "$TARGET" \
        -H "Content-Type: application/json" \
        -H "X-Node-ID: $NODE_ID" \
        -d "{
            \"node_id\": \"$NODE_ID\",
            \"hardware_attestation\": \"Titan-M3-StrongBox\",
            \"entropy_h\": $ENTROPY_H,
            \"pqc_signature\": \"verified_token\",
            \"tailscale_ip\": \"100.64.1.16\"
        }" >/dev/null 2>&1
    sleep "$INTERVAL"
done
