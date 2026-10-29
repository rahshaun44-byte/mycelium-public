# QUANTUMFLEX

## System Architecture, Security Posture & Execution Priorities
**Format:** 11-Slide System Briefing Deck  
**Classification:** Internal Operating Briefing (Fail-Closed / Evidence-Based)  
**Target Hosts:** `qfx-yoga` (Ubuntu 26.04.1 LTS), `qfx-pixel` (Pixel 11 Pro), `g6pro` (HP ProBook 450 G6)  

---

### Slide 01 — Cover

**QUANTUMFLEX**  
*Local-First Systems. Verifiable Security. Controlled Execution.*

- **Operating model:** Single operator
- **Deployment posture:** Local-first, local-only by policy
- **Security principle:** Fail closed
- **Governance:** Legal and financial gates before public expansion

**Governing principle:** No external action without authorization, no security bypass, and no public expansion before readiness criteria are met.

---

### Slide 02 — System Definition

## Three Pillars

### 1. Edge-First
- Local execution and data ownership.
- Explicitly controlled external dependencies.
- Measurable resource consumption.
- No assumed dependency on cloud infrastructure.

### 2. Fail-Closed
- Deny by default when authorization or validation fails.
- Reject malformed, untrusted, or policy-violating inputs.
- Preserve auditable decisions and failure evidence.
- Require explicit recovery from security-critical failures.

### 3. Legally Gated
- Separate internal engineering from public-facing operations.
- Validate corporate records and obligations before making external commitments.
- Keep outreach and commercialization behind documented readiness gates.

**Invariant:** Every privileged operation must have an authorized path, an auditable outcome, and a defined failure state.

---

### Slide 03 — Data Classification & Privacy

## What the System Collects—and What It Does Not

### Collected: Operational Telemetry
Subject to the configured privacy policy and retention rules:
- Event timestamps and processing outcomes.
- Component health and error categories.
- Queue and persistence metrics.
- Security-policy decisions and relevant audit events.
- Sanitized diagnostic information required for troubleshooting.

### Not Collected by Default
- Unnecessary personal information.
- Raw secrets, credentials, or authentication tokens.
- Unredacted payloads when only metadata is required.
- Unnecessary copies of user content.
- Telemetry fields prohibited by the active privacy policy.

### Enforcement
- Sanitize telemetry before persistence or downstream forwarding.
- Reject or safely handle inputs that cannot be sanitized.
- Minimize retained data and access permissions.
- Test every ingestion path, including error and fallback paths.

**Evidence requirement:** Demonstrate the privacy boundary through automated tests and inspection of actual ingestion paths. Do not equate a passing unit test with proof that every deployed path is protected.

---

### Slide 04 — System Architecture

## Six-Layer Architecture

### Layer 1 — Physical & Host Infrastructure
- `qfx-yoga`: Primary host engine; target metadata is Ubuntu 26.04.1 LTS (Microsoft Pluton TPM 2.0).
- `qfx-pixel`: Pixel endpoint for device operations and security maintenance (Titan M2).
- `g6pro`: HP ProBook 450 G6; designated Apache Kafka broker & streaming node.

### Layer 2 — Runtime & Execution
- Local process execution.
- Controlled service lifecycle.
- Explicit resource and dependency boundaries.

### Layer 3 — Messaging & Persistence
- Kafka streaming on designated node (`g6pro`).
- Durable local journaling.
- Queue processing and persistence-integrity checks.

### Layer 4 — Security & Cryptography
- FIPS 203 ML-KEM implementation (ML-KEM-768 / ML-KEM-1024).
- Hybrid key-establishment design where configured.
- Ed25519 signatures.
- Explicit key, identity, and trust boundaries.

### Layer 5 — Policy & Admission
- OPA policy evaluation using Rego v1.
- Admission checks and explicit deny decisions.
- Rejection of deprecated or prohibited cryptographic configurations.

### Layer 6 — Observability & Governance
- Privacy-filtered telemetry.
- Durable audit records.
- Legal and operational release gates.
- Evidence-driven verification.

**Architecture invariant:** Every layer must fail safely when a required dependency, validation step, or authorization decision is unavailable.

---

### Slide 05 — Security Architecture

## Cryptographic Baseline & Policy Enforcement

### Approved Design Elements

**Post-quantum key establishment**
- ML-KEM-768 and ML-KEM-1024.
- Standard: NIST FIPS 203.
- Select parameter set according to the documented security profile (`fips_strict`).

**Classical key establishment**
- X25519 for elliptic-curve Diffie–Hellman key agreement.
- Hybrid operation only where protocol explicitly defines and correctly implements the combination of classical and post-quantum shared secrets.

**Digital signatures**
- Ed25519 for signature generation and verification under the configured protocol.

**Authorization and policy**
- Open Policy Agent (OPA).
- Rego v1 policy definitions.
- Deny-by-default admission decisions.

### Legacy Cipher Control
- FrodoKEM is excluded from the strict production profile described by the migration policy.
- Legacy research code must remain isolated from production IPC and admission paths.
- Deprecated algorithms must be rejected by explicit policy enforcement.
- Migration exceptions must not silently weaken the active security profile.

### Critical Implementation Qualification
Listing an algorithm does not establish that a complete protocol is secure. Production readiness also requires correct implementation, key handling, transcript binding, algorithm negotiation, downgrade protection, and interoperability testing.

**Security invariant:** No deprecated cryptographic configuration may enter the strict production path.

---

### Slide 06 — Protocol & Hard-Stop Semantics

## The Hard Stop Protocol

### Decision Sequence
1. **Receive:** Accept an operation request.
2. **Validate:** Check structure, identity, policy, and required metadata.
3. **Authorize:** Evaluate applicable admission rules.
4. **Execute:** Perform only the authorized operation.
5. **Record:** Persist the permitted audit outcome.
6. **Stop:** Deny execution when a required validation or authorization step fails.

### Required Failure Behavior
- Missing policy: deny.
- Invalid identity or authorization: deny.
- Deprecated cryptographic configuration: deny.
- Invalid or unsanitizable telemetry: follow explicit fail-closed handling policy.
- Persistence failure: stop dependent operations when durable recording is a required invariant.
- Circuit-breaker activation: reject or defer work according to configured recovery policy.

### Governing Equation

$$Y = f(x - h) + k$$

Use this expression as the system's conceptual model for controlled transformation and adjustment.

**Invariant:** An error must never be silently converted into authorization.

---

### Slide 07 — Current Operating State

## Single-Operator Control & Cost Discipline

### Operating Model
- One accountable operator.
- Explicit authorization for privileged actions.
- Controlled changes with auditable outcomes.
- No implicit expansion of access or autonomy.

### Infrastructure Topology
- `qfx-yoga`: Primary host engine.
- `qfx-pixel`: Device endpoint.
- `g6pro`: Dedicated Kafka streaming node.

### Financial Invariant
**Target: $0.00 in unapproved cloud spend.**
- Prefer local execution where practical.
- Review external dependencies before enabling them.
- Require explicit authorization for paid services.
- Track actual expenditure rather than treating a target as a verified balance.

### Current-State Reporting Classification
- **Implemented:** Present in the codebase or configuration.
- **Tested:** Supported by identifiable test results.
- **Deployed:** Confirmed active on intended host.
- **Verified:** Supported by recorded evidence and an explicit acceptance criterion.
- **Pending:** Not yet demonstrated or awaiting confirmation.

**Invariant:** A documented design is not automatically an implemented or deployed control.

---

### Slide 08 — Legal & Commercialization Gates

## Governance Before Public Expansion

### P0 — Mandatory Verification
- Confirm the legal entity's current registration status.
- Verify legal name and Pennsylvania entity number against official records.
- Identify any outstanding obligations that could affect operations.
- Confirm proposed activity is consistent with applicable legal and contractual requirements.

### P1 — Controlled Preparation
- Document ownership of intellectual property and project assets.
- Establish appropriate financial and operational recordkeeping.
- Review privacy, security, and public-facing claims.
- Prepare accurate product and system documentation.

### Public-Surface Gate
Keep public outreach, marketing, and commercialization restricted until the required readiness criteria have been met.

- **Entity under review:** FINALLYFUNGUS LLC
- **Reported Pennsylvania entity number:** 13706513

**Invariant:** No unverified legal, financial, or security claim should be presented as an established fact.

---

### Slide 09 — Verification & Evidence

## Durable Storage, Telemetry Privacy & Admission Controls

### A. Durable Storage
**Component:** C++ DurableRing
- Enqueue and dequeue correctness verified in reference tests.
- Persistence, power-loss resilience, and restart integrity benchmarks documented.

### B. Telemetry Privacy Boundary
**Reported test result:** 13/13 automated tests passing.  
**Referenced test:** `tests/test_telemetry_wiring_proof.py`
- Confirmed `PrivacyFilter.sanitize_telemetry_frame` executes on every required ingestion path (`api_node/main.py`, `api_node/kafka_consumer.py`, and direct persistence).
- Verified downstream database persistence and forwarding cannot bypass sanitization.
- Error paths and adversarial injections (`_optout`, `_nomap`, deeply nested malformed payloads) fail closed.

### C. Two-Stage Ingress Gatekeeper
**Reported test result:** 23/23 barrier scenarios passing.  
**Stage 1:** Bash-based preliminary admission & symlink/boundary resolution.  
**Stage 2:** Mandatory OPA policy evaluation using Rego v1.
- Both stages execute in deterministic order with mandatory dependency enforcement.
- Denials route payload digest and Landauer entropy to `antigravity_entropy_sink.jsonl`.
- Zero fail-open paths.

### Evidence Status Matrix

| Evidence Item | Reported Status | Supporting Artifact |
| :--- | :--- | :--- |
| **DurableRing** | Reference tests identified | Test logs and recovery results |
| **Telemetry Wiring** | 13/13 passing | `tests/test_telemetry_wiring_proof.py` |
| **Ingress Gatekeeper** | 23/23 passing | `tests/` integration barrier matrix |
| **Production Deployment** | Requires confirmation | Host-level service state (`systemctl status`) |

---

### Slide 10 — Five Immediate Next Actions

## Execution Sequence

### 1. Clear External Security P0s
- Review September 2026 Pixel security bulletin (`CVE-2026-58704`) and apply on `qfx-pixel`.
- Investigate and resolve the 3 account-security alerts (CircleCI OAuth grant, TP-Link ID resets, Uber sign-in).

### 2. Verify Corporate State Records
- Check FINALLYFUNGUS LLC against official Pennsylvania Department of State records (Entity #13706513).
- Document current standing, EIN, and banking separation.

### 3. Wire the Agent Circuit Breaker
- Integrate the circuit breaker into the `mcp_layer` dispatcher.
- Define activation thresholds, trip/reset states, and fail-closed deferral paths.
- Add deterministic test coverage for trip, reset, timeout, and recovery.

### 4. Benchmark Durable JSONL Operations
- Execute JSONL enqueue and persistence benchmarks on `qfx-yoga`.
- Measure enqueue latency, burst throughput, and fsync latency percentiles (p50, p95, p99).
- Document baseline performance and durability limits under heavy load.

### 5. Maintain the Gated Public Surface
- Hold all public outreach and marketing until the 6–12 month household reserve target is met.
- Document and track reserve baseline in private financial records.

---

### Slide 11 — Closing Principle

## Preserve Control. Preserve Evidence. Preserve Optionality.

QuantumFlex is governed by three commitments:
- **Control:** Every consequential operation has an authorized execution path.
- **Evidence:** Security and reliability claims are backed by reproducible results.
- **Restraint:** Expansion occurs only when operational, legal, and financial conditions permit it.

### Governing Invariant
$$\mathbf{Local\text{-}first.\ Fail\text{-}closed.\ Evidence\text{-}driven.\ Legally\ gated.}$$

### Landauer & Information Preservation
Landauer's principle establishes a physical lower bound on the heat dissipated when logically irreversible information processing erases information under specified thermodynamic conditions.  
In QuantumFlex, anomalous and violating payloads ($h$) are never silently dropped; they are hashed, enveloped, and preserved in the Ghost Node Entropy Sink to preserve auditable provenance without compromising operational safety.

### Final Decision Rule
- If authorization is absent, do not proceed.
- If a required security check fails, stop.
- If evidence is missing, mark the claim unverified.
- If a release gate remains open, defer external expansion.

$$\mathbf{Build\ locally.\ Verify\ rigorously.\ Expand\ deliberately.}$$

