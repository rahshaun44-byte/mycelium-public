# Living computation cycle — frozen architecture

**Classification:** a bio-thermodynamically inspired, fail-secure
computing architecture with a speculative physical-computing research
layer.

That distinction is load-bearing. Reviewers who circle “bit flips are
mathematically barred” and write “no” are correct. Those claims are not
part of deployable QuantumFlex.

**Philosophy (human-readable):**

\[
Y = f(x - h) + k
\]

**Engineering specification:**

\[
Y_t = F\bigl(A(x_t, k_t), k_t\bigr)
\]

Admission is not arithmetic subtraction:

\[
A(x,s) \rightarrow (x_a, x_q)
\]

\(x_a\) is admitted input. \(x_q\) is quarantined input. \(s\) is
measured system state (folded into \(k_t\) below). The Ghost path is:

\[
G(x_q, k_t) \rightarrow (\Delta x, r)
\qquad
\Delta x \not\rightarrow f
\qquad
\Delta x \rightarrow A(\Delta x, k_t)
\]

**Recovery never grants authority. Recovery only creates another
admission candidate.**

**Observation may change knowledge. It may never create authority.**

Missing validation evidence is HALT, not a manufactured pass. Do not
treat a **NULL** row as a QF-A5 artifact.

Related: `quantum_flex_architecture.md`, `docs/HOST_TRUST_ANCHOR.md`,
`docs/MLKEM_STRICT_MIGRATION.md`, `docs/ASSURANCE_LEVELS.md`,
`docs/QF_R2_OPERATOR_RUNBOOK.md`.

## Invariant \(k\)

\(k\) is not an additive constant. It is the invariant state vector:

\[
k =
\{
K_{\mathrm{trust}},\
P_{\mathrm{policy}},\
B_{\mathrm{thermal}},\
R_{\mathrm{provenance}},\
I_{\mathrm{identity}},\
C_{\mathrm{crypto}}
\}
\]

| Slice | Meaning here | Status |
| --- | --- | --- |
| \(K_{\mathrm{trust}}\) | Host judge + pinned Ed25519 pub under `~/.local/libexec/quantumflex/` | PARTIAL (template + installer exist; Yoga lock needs a known-good tree) |
| \(P_{\mathrm{policy}}\) | `membrane_health.rego` / Wasm; empty OPA → deny | LIVE |
| \(B_{\mathrm{thermal}}\) | Sentinel Euclidean \(D\), `amara-predict` CPU shares | LIVE, coarse. Not a proven \(T < T_{\mathrm{crit}}\) bit-flip barrier |
| \(R_{\mathrm{provenance}}\) | QF-A5 manifest + `SIGNATURE_B64=` sidecar | LIVE format; **this branch is not known-good** (4/13 hash mismatch) |
| \(I_{\mathrm{identity}}\) | mTLS CN, Shamir unlock, user-namespace keep-id | PARTIAL |
| \(C_{\mathrm{crypto}}\) | OpenSSL 3.5 **ML-KEM-768** IPC (`0x12`/`0x13`/`0x14`); Frodo types rejected | LIVE. Not FIPS 140-3 / CMVP |

**Property \(K_{\mathrm{trust}}\) can actually state:** the repository
supplies the object being verified. It does not supply the key that
determines whether that object is trusted. Isolation from git is not a
same-user trust boundary.

## The flow that survives audit

```
UNTRUSTED INGRESS x
        │
        ▼
ADMISSION A(x, k)     policy + parser + envelope
        │
   ┌────┴────┐
 xa          xq
   │          │
   ▼          ▼
 f(xa, k)    GHOST G(xq, k)   isolated only
   │          │
   │          Δx  (candidate only)
   │          │
   │          ▼
   │     RE-ADMISSION A(Δx, k)
   │          │
   └────┬─────┘
        ▼
      k  then  Y
```

Credited entropy is a **separate** path. Ghost residue does not join it:

```
Physical noise source → health tests → conditioning → approved RBG/DRBG
        ├─► ML-KEM-768
        └─► FrodoKEM (research/legacy only; not live IPC)

Ghost / attack residue ──► telemetry / optional auxiliary mixer
                           credited entropy H_attack = 0
```

Security must hold if the attacker controls every bit of that auxiliary
pool (SP 800-90B/90C posture). Collect noise. Do not credit it.

## Three planes (freeze)

| Plane | What it is | Helium required |
| --- | --- | --- |
| **A — deployable** | Admission, signed provenance, OPA/Wasm, rootless Podman, fail-closed gates, append-only receipts, ML-KEM-768, isolated Ghost analysis, Q1 telemetry, replay vs ledger split, re-admission | No |
| **B — measurable physical control** | \( \alpha = g(T,V,P,E,\text{queue},\text{error}) \), \(0 \le \alpha \le 1 \): telemetry that actually throttles or isolates | Commodity sensors; not implemented as a single CBF yet |
| **C — research** | AQFP/RQFP, Bennett uncomputation on reversible substrates, TEG harvest, DNA/molecular storage, characterized noise sources | Future substrate. Not properties of Yoga/Ubuntu |

Plane C ideas are design languages and substrate mappings. They are not
proofs about the current node.

## Name collisions

| Name | Not this | This |
| --- | --- | --- |
| Ghost Node | Retired sniffer `/opt/ghost-node`, `sentinel/decision_gate.py` (removed 2026-08-06) | Isolated analysis of \(x_q\). Outputs have **zero authority** until \(A(\Delta x, k)\) |
| `ghostnode` | The sink | Postgres admin role on `telemetry` (`127.0.0.1:5432`) |
| Quantum / lattice | A quantum processor | State-collapse method + ML-KEM-768 |

## Physics and cryptography audit (do not re-inflate)

| Claim | Audit | QuantumFlex interpretation |
| --- | --- | --- |
| OPA as aperiodic membrane | Analogy | Policy defines admissible structure. Software still parses hostile input. Isolation and a small attack surface are required. |
| Invalid packets “cannot etch” | Too strong | They still exercise parsers, kernels, runtimes, policy engines. |
| Navier-Stokes = packet storms | Model, not equivalence | Congestion/anomaly as dissipative-flow analogy. |
| AQFP ultra-low energy | Real research | Plane C only. |
| Bennett uncomputation, zero heat | Only on reversible physical machines | Inverse ops on CMOS are not thermodynamically reversible. |
| Reversible ops avoid Landauer cost | Qualified | In principle for logically reversible ops; practical machines still dissipate; erasure still costs. |
| Uncomputation kills power side channels | **False** | Timing, EM, power, implementation leakage remain. |
| Attack residue drives the TRNG | **Unsafe** | \(H_{\mathrm{attack}} = 0\) for credited entropy. |
| FrodoKEM uses small LWE errors | Correct as crypto | Legacy/research here; not live IPC. |
| ML-KEM-768 needs discrete Gaussians | **Incorrect** | Centered binomial sampling. Fresh approved RBG (FIPS 203). |
| ML-KEM from refined hostile noise | **No** | Randomness secrecy is a security assumption. |
| LT decode instantly at \(K(1+\varepsilon)\) | Too deterministic | Probabilistic; ripple can empty. Use only if the network model justifies erasure coding (Plane A optional). |
| Homopolymer ≤3 / ~50% GC | DNA-storage specific | No automatic win for ordinary packets. |
| TEG powers boundary sensors | Possible, not guaranteed | Plane C. Low-\(\Delta T\) power can be negligible. |
| \(T < T_{\mathrm{crit}}\) bars bit flips | **False** | Lowers thermal-noise contribution. Does not eliminate radiation, supply noise, defects, EMI, metastability. |
| \(k\) physically anchors modulus \(q\) | Conceptual only | Parameters and trust roots are logical invariants. |

## Plane A map (this estate)

| Box | Referent | Status |
| --- | --- | --- |
| \(x\) | Loopback services, intake, IPC `:9444`, systemd start, Q1 | LIVE, host-local |
| \(A\) | OPA/Wasm; `host-trust/verify-provenance` ExecStartPre; Quadlet capability drop / read-only (template); PCR 10 IMA replay (`quantumflex-telemetry`) + `gatekeeper_attestation.rego` | PARTIAL. Replay crate and policy exist; not wired into live ExecStart |
| \(x_q\) / Ghost | OPA `TOXIC`/`NONE`; `QUARANTINE`/`LOCKDOWN_*`; `ForensicLockdown` (default dry-run); `quantumflex-ghost-sink` JSONL absorber + `GatekeeperDispatcher` (`Y ∩ h = ∅`) | PARTIAL. Sink crate exists; not a live Yoga unit. Zero authority |
| \(\Delta x \rightarrow A\) | Intake / replay may produce candidates; they do not skip provenance or policy | INTENDED. Do not wire Ghost output into `f` |
| \(f\) | `quantumflex/` runtime, `quantum_flex_engine`, swarm `task_queue` | LIVE software |
| \(Y\) | Admitted execution only | INTENDED. This branch must not start as if verified |

## What this freeze forbids

- Crediting adversarial or Ghost residue as KEM entropy.
- Feeding \(\Delta x\) into \(f\) without \(A(\Delta x, k_t)\).
- Stating bit flips are mathematically impossible under a temperature cap.
- Treating Plane C substrates as properties of Ubuntu/Yoga.
- Re-enabling the retired sniffer and calling it the Ghost path.
- Using FrodoKEM-976 as the live IPC KEM.
- Claiming FIPS 140-3, CMVP, or QF-A4 extraction (still NULL).
- Regex-transforming `scripts/verify_provenance_manifest.py` (pointer, not judge).

Mycelium governs. QuantumFlex implements crypto and QFXK. The host judge
admits. Q1 observes. UNKNOWN ≠ ALLOW.
