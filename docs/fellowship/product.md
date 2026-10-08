# Product

## What we are building

QuantumFlex / Mycelium: a self-hosted security and telemetry system for a single host,
being hardened from a prototype that *reports* security state into a deterministic,
fail-closed admission system. Python control plane (sentinel, mcp_layer, amara, api_node)
plus a C++20 evidence/ledger engine, sharing Postgres.

Governing principle: absence of evidence is never interpreted as verification.
Every security claim must resolve to one distinct verification state — verified,
observed-unverified, missing, stale, failed, simulation/dev, or admitted — and
NULL/None, swallowed exceptions, missing modules, simulation paths, and fallback
evaluators must never collapse into a success.

## Who it is for

A single operator (Rock) running one host. No multi-tenant users.

## What success looks like

- Every gate decision traces to hardware-anchored evidence (TPM 2.0, PCR/IMA replay) or
  denies — no simulation path reachable in production.
- Verification states are typed and distinct end-to-end; no state is inferred from absence.
- Admission is fail-closed on DB loss, anchor loss, stale evidence, or evaluator unavailability.

## Out of scope

Multi-node replication in practice (single node today); Plane C research (AQFP, Seebeck,
LT fountain codes); remotes/push.

## Constraints

Operator executes or orders every action under QF-ALIGN; recovery never grants authority;
credited attack entropy is 0; the agent does not write ~/.local/libexec.
