# Living computation cycle — named method, actual estate

QuantumFlex is not a quantum computer, an AQFP chip, or a thermoelectric
organism. The organism diagram is the **named operating method**:

\[
Y = f(x - h) + k
\]

Possibility stays wide internally. Authority, execution, state, and
external effects collapse through evidence-backed boundaries. Missing
validation evidence is HALT, not a manufactured pass.

This file maps the essay onto what this repository and host actually
are. Metaphor that has no running referent is marked **NULL**. Do not
treat a NULL row as a QF-A5 artifact or as admission evidence.

Related facts: `quantum_flex_architecture.md` (swarm units and ports),
`docs/HOST_TRUST_ANCHOR.md` (QF-R2), `docs/MLKEM_STRICT_MIGRATION.md`
(live KEM), `docs/ASSURANCE_LEVELS.md` (QF-A1–A5).

## The security property that is real

> The repository supplies the object being verified. It does not supply
> the key that determines whether that object is trusted.

That is \(k\) on this host today: `~/.local/libexec/quantumflex/` holds
the judge and the pinned public key. The mycelium tree holds the
manifest, signature sidecar, and artifacts. Isolation from git is **not**
a same-user trust boundary.

## Name collisions (pin these)

| Name in the essay | What it is **not** | What it is **here** |
| --- | --- | --- |
| Ghost Node | The retired packet-sniffer (`/opt/ghost-node/ghost-agent.py`, `sentinel/decision_gate.py` — removed 2026-08-06) | Isolated fail-closed path for non-admitted flux: OPA `TOXIC`/`NONE`, engine `QUARANTINE`, forensic lockdown. Do not re-enable the sniffer and call it metabolism. |
| `ghostnode` | The sink | Postgres admin role on `telemetry` (`127.0.0.1:5432`) |
| Quantum / lattice | A quantum processor | Architectural state-collapse + **ML-KEM-768** (FIPS 203) on OpenSSL 3.5. Live IPC rejects legacy Frodo message types. |
| Film / aperiodic crystal | DNA hardware | OPA/Wasm membrane + QF-A5 provenance gate + mTLS listener |

## Cycle map

```
INGRESS x
  packets, telemetry, unit start, model output
        │
        ▼
APERIODIC GATEKEEPER  α  (admit / slide off)
        │
   ┌────┴────┐
x-h         h
   │         │
   ▼         ▼
f(·)        SINK
laminar     fail-closed / quarantine / evidence
   │         │
   └────┬────┘
        ▼
GROUND k  (host pin, not the repo)
        ▼
Y  one allowed external state
```

| Essay box | \(Y=f(x-h)+k\) | Running referent | Status |
| --- | --- | --- | --- |
| Ingress flux \(x\) | \(x\) | Loopback services, intake, IPC `9444`, systemd start, Q1 telemetry | LIVE (host-local; not a public membrane) |
| Aperiodic gatekeeper | \(\alpha\), first cut of \(h\) | `pqc-immune-daemon/membrane_health.rego` + Wasm; `host-trust/verify-provenance` as ExecStartPre; Quadlet `DropCapability=ALL` / `ReadOnly=true` | PARTIAL. Provenance judge is host-side. Yoga lock still requires a known-good tree (`docs/QF_R2_OPERATOR_RUNBOOK.md`). |
| Zero-adhesion rejection | \(h\) slides off | Fail-closed: empty OPA → deny; signature/hash mismatch → exit 1, process never starts | LIVE for those gates. Packets do not “physically fail to etch”; the kernel still sees sockets. |
| CBF \(\alpha(T,S)\), \(T \le T_{\mathrm{crit}}\) | thermal governor | Sentinel Euclidean drive \(D\) and `amara-predict` CPU shares | LIVE, coarse. No Q16.16 CBF, no Johnson-Nyquist ceiling as an enforced invariant. |
| Laminar core \(f(\cdot)\) | \(f\) | `quantumflex/` (`QuantumFlex::crypto` / `::wire` / `::runtime`); `quantum_flex_engine`; swarm workers on `task_queue` | LIVE software. **AQFP, incompressible Navier-Stokes, LT fountain, DNA homopolymer codec: NULL.** |
| Ghost Node sink | isolated \(h\) | OPA TOXIC halt; `SystemState` `QUARANTINE`/`LOCKDOWN_*`; `ForensicLockdown` (default dry-run) | PARTIAL. Not Bennett uncomputation. Not a Landauer shock absorber. |
| Recovered \(\Delta x\) recirculated | distillation | Intake ledger + Q1 replay db (`/state` tmpfs vs `/app/data`) | PARTIAL. Repair of malformed packets is not a second distillation pass. |
| Residue → TRNG → KEM | cryptographic fuel | OpenSSL CSPRNG / `MLKem768Engine`. Immune daemon fallback is policy-driven, not attack-energy harvesting | LIVE KEM. **Attack-to-Gaussian-error pipeline: NULL.** FrodoKEM is legacy/research, not the IPC KEM. |
| Homeostatic ground \(k\) | \(k\) | Host trust anchor (pinned Ed25519 pub + judge); LUKS; user-namespace keep-id; dual-role Postgres | PARTIAL. **Seebeck TEG harvest: NULL.** |
| Invariant \(Y\) | \(Y\) | Admitted execution only: signed manifest + matching artifacts, or the process does not start | INTENDED. This branch is **not** a known-good QF-A5 tree (4/13 hash mismatch). |

## What \(h\) is on this host (measurable)

Before QF-R2: verifier and key inside the judged tree, floating image
tags, SELinux label disable, unproven egress, mutable runtime.

Removed or bounded: rootless user, capabilities dropped in the Quadlet
*template*, read-only bind of `/app`, loopback publish, provenance gate
*designed* outside the repo.

Still open: QF-R1 SELinux, QF-R3 digest pin, QF-R4 egress, same-user
libexec rewrite, dirty QF-A5 tree.

\[
h \rightarrow \text{measurable, bounded, observable}
\]

not \(h = 0\).

## What this document forbids

- Implementing AQFP, Seebeck arrays, LT fountain meshes, or a DNA
  codec because the essay named them. Those stay NULL until there is
  hardware, a signed artifact, and a judge that is not the defendant.
- Re-enabling `/opt/ghost-node` or `decision_gate.py` and calling it
  the metabolic engine.
- Treating FrodoKEM-976 as the live IPC KEM. Wire types `0x12`/`0x13`/`0x14`
  are ML-KEM-768; legacy `0x02`/`0x03` are rejected.
- Claiming FIPS 140-3, CMVP, or QF-A4 extraction. QF-A4 remains NULL.
- Regex-transforming `scripts/verify_provenance_manifest.py` into the
  host judge. It is a pointer. See `scripts/assert_host_trust_source.py`.

## Collapse still in force

Mycelium governs. QuantumFlex implements crypto and QFXK. The host
judge admits. Observation (Q1) does not confer authority. UNKNOWN ≠
ALLOW.
