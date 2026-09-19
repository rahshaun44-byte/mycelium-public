# QuantumFlex Commercial Intake & Triage Engine — Operational Runbook

**Document ID:** `QF-OPS-INTAKE-001`  
**Entity:** FINALLYFUNGUS LLC (PA Entity ID: 13706513) DBA QuantumFlex  
**Classification:** Operational Runbook & Assurance Guide  
**Status:** ACTIVE & FROZEN (Main Branch Baseline)

---

## 1. System Architecture & Invariants

The QuantumFlex Lead Intake Service is an airgapped, high-assurance B2B intake qualification daemon. It eliminates missed after-hours commercial emergency calls without exposing contractors to promissory estoppel liability or TCPA violations.

```
Inbound Lead (Web / Phone API)
            │
            ▼
┌──────────────────────────────────────┐
│  Intake Service (127.0.0.1:5680)     │
│  - Computes Idempotency Key          │
│  - Persists Ticket to SQLite (WAL)   │
└──────────────────────────────────────┘
            │
            ├─────────────────────────────────────────► Immediate HTTP 202 Receipt (<10 ms)
            │                                           (Non-Promissory Disclaimer)
            ▼
┌──────────────────────────────────────┐
│  Queue Worker (Atomic Claim Lease)   │
│  - Fencing Token (claim_token)       │
│  - Reclaims Expired Leases           │
└──────────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────────┐
│  Local LLM (Ollama / Qwen2.5-Coder)  │
│  - 100% Airgapped (Zero Cloud PII)   │
│  - Strict JSON Schema Validation     │
└──────────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────────┐
│  Draft Alert & Persistence           │
│  - Urgency & Trade Categorized       │
│  - State: PENDING_HUMAN_APPROVAL     │
│  - Outbound: DRAFT ONLY (Disabled)   │
└──────────────────────────────────────┘
```

### Core Invariants
1. **Pre-Inference Persistence:** Tickets are durably committed to SQLite before any inference runs. Network crashes or model timeouts never drop a lead.
2. **Immediate HTTP 202 Receipt:** Callers receive a confirmed receipt in under 10 ms (`time_total < 0.010s`).
3. **Atomic Lease Fencing:** Multi-worker execution uses `claim_token` and `claim_expires_at_epoch` to eliminate double-dispatch and reject stale completions (`HTTP 409 StaleClaimError`).
4. **Fail-Closed Triage:** Any model failure, schema violation, or timeout records `urgency = "UNKNOWN"` and `dispatch_state = "MANUAL_REVIEW_REQUIRED"`. The system never hallucinates critical status or confirms technicians.
5. **Strict Human Dispatch Boundary:** Machines summarize and categorize; only a authorized human operator can assign a technician or confirm arrival times.

---

## 2. Legal & Regulatory Compliance

### A. TCPA Compliance (Telephone Consumer Protection Act — 47 U.S.C. § 227)
- **Status:** Outbound automated messaging is hard-disabled in the prototype (`DRAFT_NOT_SENT_OUTBOUND_DISABLED`, `customer_receipt_delivered = 0`).
- **Production Boundary:** When carrier SMS integrations (Twilio/Telnyx) are activated:
  - Messaging is strictly 1-to-1 transactional confirmation in response to customer-initiated emergency calls.
  - No marketing broadcasts or automated telephone dialing systems (ATDS) are used.
  - Every message includes explicit contractor identification and standard opt-out instructions ("Reply STOP to opt out").

### B. Promissory Estoppel & Tort Defense (Restatement (Second) of Contracts § 90 / UCC)
- Standard answering services often create liability by promising arrival windows ("We'll have someone there in 30 minutes"), exposing contractors to food spoilage, water damage, or breach claims if delayed.
- QuantumFlex enforces deterministic, legally vetted receipt language:
  > *"Your service request has been received. A technician has not yet been assigned, and no arrival time is confirmed. For immediate assistance, call our published emergency number."*
- This contractually disclaims warranties and unassigned arrival guarantees at the instant of ingress.

### C. CFAA & ECPA Compliance (18 U.S.C. § 1030 & 18 U.S.C. § 2510)
- The service binds strictly to loopback (`127.0.0.1`).
- No unauthorized network access, port scanning, or payload interception.
- SQLite database directory is locked to `0700` permissions.

### D. Data Privacy & Zero Cloud Leakage (CCPA, FTC Act § 5, GDPR)
- 100% on-premises inference via local Ollama weights (`qwen2.5-coder:7b`).
- Customer PII (phone numbers, addresses, incident logs) is **never** transmitted to OpenAI, Anthropic, or any third-party cloud.
- Data remains under the exclusive custody of the deploying contractor.

---

## 3. Operational Quickstart

### Starting the Service Daemon
```bash
python3 scripts/intake_service.py
```
*Listens on `http://127.0.0.1:5680`.*

### Health Check
```bash
curl -s http://127.0.0.1:5680/api/v1/health
# Output: {"status": "ok", "service": "quantumflex-intake-service"}
```

### Submitting a Live Inbound Service Request
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
**Expected Response (<10 ms):**
- HTTP Status: `202 Accepted`
- Body:
  ```json
  {
    "http_status": 202,
    "ticket_id": "TCK-...",
    "receipt_status": "ACCEPTED",
    "is_duplicate_request": false,
    "customer_acknowledgment": {
      "channel": "SMS_DRAFT",
      "delivery_status": "DRAFT_NOT_SENT_OUTBOUND_DISABLED",
      "message_text": "Your service request has been received. A technician has not yet been assigned, and no arrival time is confirmed. For immediate assistance, call our published emergency number."
    }
  }
  ```

### Processing Pending Queue (Ollama Triage)
```bash
# Process pending tickets with local model:
python3 scripts/run_lead_triage_demo.py --recover
```

### Running Full Automated Regression & Invariant Benchmark
```bash
python3 scripts/benchmark_lead_triage.py
```
*Expected: 9/9 suites passing (100% test coverage over persistence, deduplication, schema validation, crash recovery, and lease fencing).*

---

## 4. Commercial Offer & Terms

| Component | Specification |
|---|---|
| **Contracting Entity** | FINALLYFUNGUS LLC (PA Entity ID: 13706513) DBA QuantumFlex |
| **Product Tier** | High-Margin Local B2B Workflow Automation (Tier 1) |
| **Target Clients** | Commercial HVAC, Commercial Refrigeration, Emergency Plumbing |
| **Setup Fee** | **$750** (One-time installation, local model configuration, call flow setup) |
| **Monthly Retainer** | **$350 / month** (WAL database maintenance, model updates, queue monitoring) |
| **Service Level Scope** | Deterministic intake receipt (<10 ms) + local AI triage recommendation; human operator retains exclusive dispatch authority |
| **Liability Scope** | Standard MSA with limited liability; disclaims consequential equipment damages and emergency dispatch warranties |
