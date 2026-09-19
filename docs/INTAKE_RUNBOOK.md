# QuantumFlex Commercial Intake & Triage Prototype — Operational Runbook

**Document ID:** `QF-OPS-INTAKE-001`  
**Classification:** Prototype Runbook & Functional Verification Scope  
**Status:** FROZEN LOCAL PROTOTYPE

---

## 1. System Scope & Functional Baseline

This service is a **local, loopback-bound prototype** for commercial service request intake and advisory triage qualification. It is designed to persist inbound tickets locally and generate structured recommendations and draft operator alerts.

**Important Operational Boundaries:**
- **No Automated Dispatch:** The system does not dispatch technicians or confirm appointments.
- **No Active Outbound Messaging:** All outbound customer SMS and operator notifications are hard-disabled in the software (`customer_receipt_delivered = 0`, `operator_alert_delivered = 0`, `DRAFT_NOT_SENT_OUTBOUND_DISABLED`).
- **Loopback, Not Airgapped:** The intake service (`127.0.0.1:5680`) and Ollama (`127.0.0.1:11434`) bind to localhost. This restricts external inbound connections to those listeners, but does **not** constitute an airgapped system; the host machine maintains active network interfaces and Tailscale connectivity.
- **Development HTTP Engine:** Built using Python's standard `http.server`, which is suitable for local functional testing but is explicitly not production-hardened or security-certified for public networks.

```
Inbound Lead (Local HTTP POST)
            │
            ▼
┌──────────────────────────────────────────────┐
│  Intake Service (127.0.0.1:5680)             │
│  - Loopback-bound Python http.server         │
│  - Computes Idempotency Key                  │
│  - Persists Ticket to SQLite (WAL mode)      │
└──────────────────────────────────────────────┘
            │
            ├─────────────────────────────────────────► Immediate HTTP 202 Receipt (3.9–8.5 ms in local tests)
            │                                           (Expectation-setting disclaimer)
            ▼
┌──────────────────────────────────────────────┐
│  Queue Worker (Atomic Claim Lease)           │
│  - Fencing Token (claim_token)               │
│  - Reclaims Expired Leases                   │
└──────────────────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────────────────┐
│  Local Model Inference (Ollama / Qwen2.5)    │
│  - Localhost inference on host hardware      │
│  - Strict JSON Schema Output Validation      │
└──────────────────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────────────────┐
│  Draft Alert & Persistence                   │
│  - Suggested Urgency & Trade Classification  │
│  - State: PENDING_HUMAN_APPROVAL             │
│  - Outbound: DRAFT ONLY (Disabled)           │
└──────────────────────────────────────────────┘
```

---

## 2. Verified Technical Mechanisms & Inherent Limits

| Mechanism | Demonstrated Function | Boundary & Limitation |
|---|---|---|
| **Pre-Inference Persistence** | Tickets are written to SQLite before local inference begins. Survives process restart during tests. | SQLite WAL mode + `synchronous=FULL` provides documented ACID durability under normal OS operations, but does not prove survival of physical power-loss or storage hardware failure without destructive testing. |
| **Loopback Receipt Latency** | Measured at **3.9–8.5 ms** for isolated local requests. | Decouples HTTP client acknowledgment from model inference locally. Does not predict response times under high concurrency, slow network clients, disk saturation, or database lock contention. |
| **Lease-Based Claiming** | Database updates enforce `claim_token` matching and lease expiration, rejecting stale worker updates with HTTP `409 StaleClaimError`. | Rejects stale writes to the local SQLite database. Does not manage external physical resources or prevent duplicate actions in third-party services. |
| **Fail-Closed Exception Handling** | Timeouts, connection errors, and schema violations record `urgency = "UNKNOWN"` and `dispatch_state = "MANUAL_REVIEW_REQUIRED"`. | Enforces strict JSON structure and handles errors defensively. **Does not evaluate factual truth.** A model may emit a schema-valid response that is factually inaccurate. |
| **Advisory Draft Alerts** | Alerts are explicitly formatted as `[DRAFT ALERT - NOT SENT - REQUIRES HUMAN DISPATCH APPROVAL]`. | Prevents software-driven dispatch; human review is required. It does not ensure the human reviewer will catch all model misclassifications. |

---

## 3. Legal, Regulatory & Licensing Disclosures

This analysis reviews technical mechanisms and design intent. It does not constitute formal legal certification, contractual protection, or regulatory clearance.

### A. Telecommunications & TCPA (47 U.S.C. § 227)
- **Current Prototype:** Outbound transmission is completely disabled. No SMS messages or phone calls are placed.
- **Future Integration Requirement:** Connecting to live carrier gateways (Twilio, Telnyx) requires independent legal assessment of message classification (informational vs. promotional), recipient consent, autodialer definitions, delivery confirmation, and opt-out processing. "Transactional," "one-to-one," and "Reply STOP" are not blanket legal immunities.

### B. Expectations Management vs. Contractual Warranty Disclaimer
- **Receipt Text:** 
  > *"Your service request has been received. A technician has not yet been assigned, and no arrival time is confirmed. For immediate assistance, call our published emergency number."*
- **Legal Scope:** This text manages customer expectations by explicitly stating that no arrival time or technician has been confirmed. It is **not** a universal contract, does not contain a comprehensive warranty disclaimer or limitation of liability, and does not replace signed terms of service or customer contracts.

### C. Network & Data Privacy (CFAA, ECPA, CCPA, GDPR)
- **Localhost Binding:** Binding services to `127.0.0.1` restricts network listening to the local machine. It does not establish statutory compliance with CFAA/ECPA, which govern authorization and consent.
- **Data Privacy Scope:** Local model execution keeps prompt data on the local machine during inference. Comprehensive CCPA/GDPR compliance depends on complete corporate data governance, access logs, backups, and data retention policies across the entire host system, not solely on local inference endpoints.

### D. Software Licensing
- **Python:** Python Software Foundation (PSF) License, with component-specific licenses.
- **Qwen2.5-Coder-7B-Instruct:** Apache 2.0 (per official upstream model card; exact downstream distribution terms must be confirmed).
- **n8n:** **Sustainable Use License** (contains non-commercial / commercial restrictions and enterprise exclusions; not an unrestricted MIT/Apache component). Commercial packaging and deployment must be verified against n8n's specific licensing conditions.

### E. Corporate Entity & Contracts
- Proposed commercial terms ($750 setup fee + $350/mo retainer) represent a target pricing hypothesis.
- Formal Master Services Agreements (MSAs), liability caps, entity filings, and contractor onboarding documents require formal legal review prior to executing commercial customer contracts.

---

## 4. Operational Commands (Local Functional Verification)

### 1. Launching the Local Service
```bash
python3 scripts/intake_service.py
```
*Listens on `http://127.0.0.1:5680` (loopback only).*

### 2. Checking Service Health
```bash
curl -s http://127.0.0.1:5680/api/v1/health
# Expected: {"status": "ok", "service": "quantumflex-intake-service"}
```

### 3. Ingesting a Test Service Request
```bash
curl -i -X POST http://127.0.0.1:5680/api/v1/intake \
  -H "Content-Type: application/json" \
  -d '{
    "business_name": "Scranton Cold Storage",
    "phone": "570-555-0144",
    "location": "Scranton, PA",
    "message": "Compressor bank 2 locked up, room temp at 38F and rising"
  }'
```
*Expected: HTTP 202 Accepted (<10 ms local loopback response).*

### 4. Running the Model Triage Worker
```bash
# Processes pending persisted tickets through local Ollama model:
python3 scripts/run_lead_triage_demo.py --recover
```

### 5. Running the 9-Suite Functional Benchmark
```bash
python3 scripts/benchmark_lead_triage.py
```

---

## 5. Measured Performance Baseline

- **Loopback Receipt Response Latency:** **3.9–8.5 ms** (measured on isolated local requests).
- **Warm Repeat Model Inference (Qwen2.5-Coder-7B on host):** **5.04–9.79 seconds (average ~7.22s)** across repeated warm runs.
- **Initial / Cold Inference Runs:** **11.11–18.24 seconds** observed during initial execution (cold-start conditions not formally benchmarked).
- **Outbound Transmission Record:** 0 tickets delivered outbound across all local tests.

---

## 6. Prototype Assurance Statement

> **The local intake prototype has reported passing functional tests for persistence, receipt handling, claiming, validation, and manual-review fallback. It is designed to generate recommendations and draft alerts without automated dispatch. These results do not establish air-gap isolation, universal failure resistance, production readiness, or comprehensive legal compliance. Licensing, business registration, contractual protections, and any future outbound messaging require separate verification.**
