---
name: quantumflex-telemetry-triage
description: >-
  Real-time Sentinel intrusion detection, high-integrity lead triage & incident processing,
  Ghost Sink shock absorber anomaly absorption, OPA Rego policy gating, and immutable ledger audits.
---

# QuantumFlex Telemetry, Sentinel & Lead Triage Playbook

This skill provides procedures for operating the QuantumFlex intrusion detection system, processing real-time telemetry, running benchmark lead triage, and managing the Ghost Sink shock absorber.

---

## 1. Real-Time Sentinel Intrusion Detection

The Sentinel subsystem monitors system state, process integrity, and network anomalous events.

### Running Sentinel Manually:
```bash
/home/quant/mycelium/venv/bin/python3 run_sentinel.py
```

### Pushing Telemetry to C++ Evidence Engine:
```bash
./build_check/sentinel_push --event "SYSTEM_HEALTH_CHECK" --payload '{"status": "nominal", "entropy": 0.0}'
```

### Checking Sentinel Service Status:
```bash
systemctl --user status sentinel.timer sentinel.service
```

---

## 2. High-Integrity Intake & Lead Triage Pipeline

The lead triage pipeline ingests customer incidents/leads, delivers sub-50ms HTTP 202 receipts, enforces strict idempotency, and performs local AI-assisted triage without external data leakage.

### Starting the Intake Service:
```bash
/home/quant/mycelium/venv/bin/python3 scripts/intake_service.py --port 8088
```

### Running the Full Verification & Benchmark Suite (9 Test Vectors):
```bash
/home/quant/mycelium/venv/bin/python3 scripts/benchmark_lead_triage.py
```
*Validates:*
1. Acknowledgment-before-inference (<50ms HTTP 202 receipt)
2. Concurrent work claiming & atomic state transitions
3. Idempotency conflicts (HTTP 409) vs legitimate retries
4. Strict schema validation & type enforcement
5. Worker crash recovery & pending queue drain
6. Fail-closed timeout containment (`MANUAL_REVIEW_REQUIRED`)
7. Zero outbound transmission audit (all notifications remain draft-only)

### Running the Live Lead Triage Interactive Demo:
```bash
/home/quant/mycelium/venv/bin/python3 scripts/run_lead_triage_demo.py
```

---

## 3. Ghost Sink Shock Absorber & Anomaly Simulation

The Ghost Sink (`quantumflex-ghost-sink` on loopback `:19443`) absorbs anomalous/untrusted telemetry ($h$) without allowing it to corrupt the active state root or mint false authorization.

### Running Ghost Node Shock Absorber Invariant Test:
```bash
/home/quant/mycelium/venv/bin/python3 scripts/test_ghost_node_shock_absorber.py
```

### Simulating Adversarial Anomaly Injection:
```bash
/home/quant/mycelium/venv/bin/python3 scripts/simulate_anomaly_injection.py
```

---

## 4. OPA Policy Gatekeeper Verification

QuantumFlex evaluates admission and crypto-agility policies against Open Policy Agent (OPA):
```bash
/home/quant/mycelium/venv/bin/python3 scripts/qf_hybrid_gatekeeper.py --test
```
