# QuantumFlex Secure Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore only the verified, local-only QuantumFlex stack after preserving evidence, reconciling provenance and credentials, and validating host controls.

**Architecture:** Keep the engine, policy gate, telemetry, and application services as separate systemd user units. Re-establish a fail-closed provenance gate before the engine starts, keep all application listeners on loopback, and publish through Tailscale only after local health checks pass. Autonomous workers and external billing/settlement paths remain disabled until separately reviewed.

**Tech Stack:** Ubuntu/Linux, systemd user services, firewalld/nftables, Tailscale Serve, C++20/CMake, Python/uvicorn, OPA/Rego, PostgreSQL/Podman, Ed25519 provenance, gitleaks.

**Spec:** `docs/fellowship/specs/pqc-differential-tester.md` and `docs/fellowship/codebase-map.md` operational constraints; QuantumFlex operations and telemetry playbooks.

## Global Constraints

- Do not delete or rewrite evidence, ledgers, backups, unreachable Git objects, or uncommitted worktree changes during the audit.
- Do not paste or expose Shamir shares, private keys, API tokens, database passwords, or signature material.
- Do not run the Windows-oriented `tools/rotate_credentials.py`.
- The engine must remain bound to `127.0.0.1:9444`; application services must remain loopback-bound.
- Use firewalld as the single host firewall control plane; do not mix UFW edits or ad-hoc nftables rules into the recovery.
- Tailscale Serve must remain reset until local health checks and firewall reconciliation pass.
- Do not enable `qf-bot`, `swarm-worker`, predictive/autonomous timers, public settlement, or external outreach during the initial recovery.
- No service is declared recovered until a fresh command proves its status, listener, logs, and health endpoint.

## Review Focus

- Stale signed manifest versus rebuilt engine: verifier must reject a mismatched binary before systemd starts it.
- Locked engine shutdown: a locked/unverified state must not be treated as a successful persisted recovery.
- Live versus permanent firewalld drift: the same allowlist must be observed after reload and across reboot configuration.
- Credential fan-out: every consumer must receive a new provider-issued credential, and old credentials must be revoked rather than merely replaced in `.env`.
- Re-enabling automation: disabled timers and user units must not silently restart workers or mutate state during recovery.

### Task 1: Preserve the audit baseline

**Files:**
- Create: `docs/audits/2026-10-20-quantumflex-recovery-baseline.md`
- Read-only inputs: systemd status/journals, firewalld status, Tailscale status, repo status, gitleaks reports, credential file metadata.

**Interfaces:**
- Produces: timestamped evidence and hashes for later comparison.

- [x] **Step 1: Record current host state without secrets**

  Capture service states, listeners, active and permanent firewall zones, Tailscale Serve state, file permissions, repo HEAD/status/reflogs, and the engine journal. Redact all secret values.

- [x] **Step 2: Record the current provenance verdict**

  Run `/home/quant/.local/libexec/quantumflex/verify-provenance /home/quant/mycelium/release/PROVENANCE_MANIFEST.json --repo-root /home/quant/mycelium` and preserve the exit code and mismatch paths.

- [x] **Step 3: Record gitleaks classifications**

  Store redacted finding metadata (rule, path, line, and whether the value is synthetic/public-key/signature material or a credential requiring revocation).

### Task 2: Reconcile repository and artifact provenance

**Files:**
- Modify only after review: `release/PROVENANCE_MANIFEST.json`, `release/PROVENANCE_MANIFEST.sig`, and the engine unit.
- Preserve: all current uncommitted files in `/home/quant/mycelium` and the untracked `qf/ibm_research_pilot.py`.

**Interfaces:**
- Consumes: the reviewed source commit and the external host trust anchor.
- Produces: a build whose exact hash is covered by a valid signed manifest.

- [ ] **Step 1: Freeze the source revision**

  Select one reviewed Mycelium commit; do not include the current uncommitted qf-bot/API changes without explicit review. Record the commit and working-tree diff separately.

- [ ] **Step 2: Build in a clean, reproducible directory**

  Run the existing CMake configure/build and the relevant C++/Python admission tests. Do not overwrite the live binary until the build is verified.

- [ ] **Step 3: Generate and sign a new manifest through the existing operator ceremony**

  Use the external signing key only through the repository’s signing procedure. Never place private signing material in Git or service environment files.

- [ ] **Step 4: Restore the correct fail-closed `ExecStartPre`**

  Point the engine unit at the manifest path plus `--repo-root /home/quant/mycelium`; do not use the incorrect repo-root-only argument present in the backup unit. Verify the unit fails closed when the binary is changed.

### Task 3: Replace unsafe credential rotation

**Files:**
- Modify: `tools/rotate_credentials.py`
- Create: `tools/rotate_credentials_linux.py` only if a separate implementation is safer.
- Test: `tests/test_credential_rotation.py`

**Interfaces:**
- Produces: dry-run inventory, explicit provider rotation checklist, atomic local updates, and no secret output.

- [x] **Step 1: Add tests for Linux paths and non-destructive dry-run behavior**

  Assert that Windows paths are rejected, existing values are never printed, `.env` backups are not overwritten, and missing provider credentials stop the operation.

- [x] **Step 2: Implement provider-aware rotation**

  Separate local database roles, service API keys, Tailscale credentials, and third-party credentials. Require explicit provider revocation/issuance before updating each consumer file.

- [x] **Step 3: Fix duplicate-secret detection**

  Treat `DB_PASSWORD`/`GHOSTNODE_DB_PASSWORD` and `DASHBOARD_API_KEY`/`ATHENA_API_KEY` reuse as failures until intentionally separated.

- [x] **Step 4: Run tests and a redacted dry-run**

  Verify file modes remain `0600`, no secret values appear in stdout/stderr, and every service environment source is accounted for.

### Task 4: Reconcile host controls

**Files:**
- Modify only with root-authorized host session: firewalld zone configuration and relevant service enablement.
- Documentation: `scripts/enable_quantumflex_mesh.sh` and the Ubuntu setup scripts if their allowlists disagree with the chosen policy.

**Interfaces:**
- Produces: one authoritative firewalld policy, no public SSH, and Tailscale-only application ingress.

- [ ] **Step 1: Inspect and document nftables/firewalld ownership**

  Confirm whether `nftables.service` loads any independent ruleset; do not remove rules without recording their source and purpose.

- [ ] **Step 2: Reconcile live and permanent `qf-tailscale` rules**

  Allow only the ports needed by the staged recovery, bind them to `tailscale0`/the tailnet source, remove stale public allows, reload, and re-query both live and permanent state.

- [ ] **Step 3: Verify no public listener exists**

  Use `ss -lntup` and firewalld queries to prove application services remain loopback-only and TCP 22 remains disabled unless separately authorized.

### Task 5: Staged service recovery

**Files:**
- Modify: systemd user enablement only after Tasks 2–4 pass.
- Test: existing `test_endpoints.py`, engine admission/recovery tests, and targeted health checks.

**Interfaces:**
- Consumes: verified binary, valid credentials, reconciled firewall, and clean local health checks.
- Produces: a minimal running stack with an explicit service inventory.

- [ ] **Step 1: Start the engine locked and local-only**

  Start only after provenance verification passes. Confirm `127.0.0.1:9444`, journal health, and locked-state behavior. Do not perform the 3-of-5 unseal ceremony automatically.

- [ ] **Step 2: Start OPA and telemetry/monitoring**

  Enable `opa-immune` and the selected monitoring path, then verify local policy health and logs before starting application APIs.

- [ ] **Step 3: Start application services one at a time**

  Bring up `athena-node`, `api-node`, `amara-dashboard`, and `qflex-mcp` only after each dependency and health endpoint passes. Keep `qf-bot`, `swarm-worker`, autonomous timers, and settlement/outreach workflows disabled.

- [ ] **Step 4: Re-enable Tailscale Serve last**

  Run the saved mesh script only after all local endpoints pass; verify no Funnel/public exposure and confirm the resulting Serve configuration.

### Task 6: Independent review and final verification

**Files:**
- Review all modified files and the final audit report.

- [ ] **Step 1: Run the complete verification set**

  Re-run provenance verification, gitleaks, repository tests, CMake tests, systemd status, listeners, firewalld live/permanent state, Tailscale Serve status, and endpoint health checks.

- [ ] **Step 2: Request a code review**

  Dispatch an independent reviewer against the final diff and this plan; fix all critical/important findings before any commit or push.

- [ ] **Step 3: Publish the recovery report**

  Report exact evidence, remaining blockers, services intentionally held, and rollback commands. Do not claim recovery until every required verification has fresh passing output.

---

## Current blockers recorded before implementation

1. The signed manifest rejects the current engine binary (`build_check/quantum_flex_engine` hash mismatch).
2. The engine’s live provenance `ExecStartPre` is commented out.
3. The engine last exited with status 1 while locked, after serialization refusal.
4. Credential rotation is Windows-specific and unsafe for this Linux host.
5. `mycelium`, `quantumflex`, and `qf-public` have gitleaks findings requiring classification.
6. The host firewall query needs a polkit-capable session for exact rule reconciliation.

