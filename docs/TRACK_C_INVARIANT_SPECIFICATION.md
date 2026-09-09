# QUANTUM FLEX // TRACK C: UNIVERSAL INVARIANT SPECIFICATION ($R \ge O$)

## 1. Executive Principle: The Physical Imperative

The core vulnerability in distributed cryptographic networks is the confusion of **consensus** with **truth**.

In the **Liquid Network exploit**, 11-of-15 honest signers approved $320M in unbacked BTC issuance. The signers performed cryptographic signature validation correctly, but the system lacked an invariant check against real, measured physical reserves. 

In QuantumFlex, consensus and authorization are subordinate to the **Universal Reserve Invariant**:

$$\mathbf{R \ge O}$$

Where:
- $\mathbf{R}$ (**Reserve Measured**): The ground-truth physical or hardware-measured capacity.
- $\mathbf{O}$ (**Obligations / Claims**): The sum of all active allocations, claims, and requested draw deltas ($\Delta$).

If at any instant $R < O$, the system immediately defaults to **FAIL-CLOSED** (`verdict = "DENY"`, `allow = false`). No quorum, no administrative key, and no automated script can override an invariant breach.

---

## 2. Protected Strata

### A. Digital Infrastructure (Lenovo Yoga 7 Host)
1. **Memory Headroom Invariant ($R_{\text{RAM}} \ge O_{\text{CLAIMED}}$)**:
   - $R_{\text{RAM}}$: Measured directly from `/proc/meminfo` (`MemTotal`).
   - $O_{\text{CLAIMED}}$: Active host RAM consumption (`MemTotal - MemAvailable`).
   - Headroom verification ensures no container, worker, or neural inference task (e.g. MiniCPM on `:11435`) can be spawned if it threatens to push the kernel into swap thrashing or OOM panic.
2. **Hardware Pluton TPM 2.0 Anchor ($R_{\text{TPM}} == O_{\text{LEDGER}}$)**:
   - $R_{\text{TPM}}$: 32-byte cryptographic root hash stored in physical Pluton TPM 2.0 NVRAM index `0x1c00010`.
   - $O_{\text{LEDGER}}$: Root block hash from the tip of PostgreSQL `sentinel_ledger`.
   - Protects against Evil Maid physical attacks, cold-boot disk cloning, and offline ledger rollbacks.

### B. Physical Operations (FinallyFungus LLC)
1. **Water Reservoir Solvency ($R_{\text{WATER}} \ge O_{\text{WATER}} + \Delta$)**:
   - $R_{\text{WATER}}$: Ultrasonic / hydrostatic sensor reading of actual gallons in the reservoir.
   - $O_{\text{WATER}}$: Outstanding irrigation, misting, and humidity schedule claims.
   - $\Delta$: Requested draw for a new flush or sterilization cycle.
2. **Sensor Freshness SLA ($\Delta t \le 60\text{s}$)**:
   - Sensor measurements must have a telemetry timestamp $\le 60$ seconds old.
   - Telemetry older than 60 seconds is rejected fail-securely (`Stale telemetry: measurement age exceeds maximum SLA`), preventing frozen-sensor exploits or replay attacks.

---

## 3. Policy Implementation (Open Policy Agent)

The policy is loaded directly into the live OPA sidecar (`127.0.0.1:8181/v1/data/quantumflex/invariant`):

- **Package**: `quantumflex.invariant`
- **Default Posture**: `allow = false`, `verdict = "DENY"`
- **Rules Evaluated**:
  - `is_fresh`: Telemetry timestamp within SLA window.
  - `is_anchor_valid`: Exact 64-char hex match between TPM index `0x1c00010` and `sentinel_ledger`.
  - `is_numeric_solvent`: $R \ge O$ and $(R - \Delta) \ge (O - \Delta)$.

---

## 4. Audit & Verification Trail

All invariant evaluations across all callers are permanently recorded into the PostgreSQL `telemetry` database:

```sql
SELECT id, timestamp, domain, resource_type, reserve_measured, units_claimed, verdict, allow, evaluator 
FROM invariant_audit_ledger 
ORDER BY id DESC;
```

### Registered Evaluators:
- `cli_all` / `cli_single`: Host administrator manual verification.
- `qflex_status` / `qflex_hud`: Unified QuantumFlex HUD console.
- `api_node_rest`: REST queries via `:8080/api/invariant`.
- `pixel_11_pro` / `s23_fe_operator`: Authenticated mobile mesh operators over Tailscale.
- `amara_dashboard_hud` / `amara_dashboard_api`: Live Matrix Dashboard HUD.
- `qf_monitor_daemon`: Autonomic 30s biological monitoring reflex.

---

## 5. Operator Quick Reference

### CLI Commands:
```bash
# Full composite audit (Digital RAM + TPM 2.0 + Physical Water)
python qflex.py invariant

# Check system health with Stratum 0 Invariant Gate
python qflex.py status

# Direct gate interrogation
./venv/bin/python3 sentinel/invariant_gate.py all
./venv/bin/python3 sentinel/invariant_gate.py memory
./venv/bin/python3 sentinel/invariant_gate.py tpm
./venv/bin/python3 sentinel/invariant_gate.py water --reserve 500 --claimed 350 --delta 50
```

### Mobile / REST API (`:8080`):
```bash
# Check composite status
curl -s http://127.0.0.1:8080/api/invariant | jq .

# Submit physical sensor reading
curl -s -X POST http://127.0.0.1:8080/api/invariant/evaluate \
  -H "Content-Type: application/json" \
  -H "X-Operator-ID: mobile_operator" \
  -d '{"domain": "physical", "resource_type": "WATER_GALLONS", "reserve_measured": 500, "units_claimed": 350, "requested_delta": 50}' | jq .
```
