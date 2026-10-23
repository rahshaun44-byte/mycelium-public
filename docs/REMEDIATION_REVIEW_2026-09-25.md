# Source-checked review of the proposed remediation

Reviewed September 25, 2026 (America/New_York), against current workspace and read-only host checks; network correction verified at approximately 23:19 EDT. This records which recommendations are supported, corrected, or still require deployment design. No live service was restarted or reconfigured by this review task.

## Applied source correction

`mcp_layer/swarm_worker.py`: unwired AMARA, IaC, and unsupported targets now return `FAILED` with an explicit reason, rather than synthetic `COMPLETED` results. This uses the existing queue-state/error contract; an HTTP 501 is not the protocol of this database worker. Existing Athena HTTP failure handling is retained. Seven isolated regression tests pass in `tests/test_swarm_worker_dispatch.py`.

The running worker has not been restarted, so this source correction is not claimed as deployed. No task rows were altered. Intake already documents disabled outbound delivery and explicit draft status; do not replace real persisted intake outcomes with a blanket simulated label.

## Immune daemon deployment

Source drift is confirmed in CURRENT_SYSTEM_SNAPSHOT_2026-09-25.md. However, the proposed `--component immune-daemon` verifier flag does not exist in the checked verifier. The repository wrapper delegates to an external host trust anchor; replacing it with self-verification would weaken the existing separation. The current manifest does not list the daemon Python entrypoint (it does list membrane policy/test files).

A valid migration needs the intended daemon and dependencies covered by the signed release, an externally pinned judge, the actual supervised worker identity, and verified restart/stop behavior. Strict source startup requires WORKER_PID; the observed older daemon process has none. Merely changing WorkingDirectory or introducing a second `qf-immune-daemon` unit could cause startup failure or competing supervisors. No manifest, signature, live unit, or worker identity was changed.

## Engine and database

LOCKED is deliberate in `src/core/local_node.cpp`: startup suspends the ledger; successful Shamir recovery permits the LOCKED -> ACTIVE transition. It is not evidence of a failed database health check or missing master KEM material. `src/main.cpp` explicitly supports PostgreSQL integration being disabled. `scripts/unlock_engine.sh` already implements recovery/unlock over the existing engine path.

The proposed `quantumflex-core --unseal --key-vault` command was not established as a project interface. A Podman API socket is not a PostgreSQL wire-protocol endpoint. Do not redirect the engine to telemetry port 5432 without establishing the intended database, schema, grants, and isolation. No unseal, shard access, or database activation was performed.

## Network findings

Historical observation, now superseded: Open WebUI PID 3668 listened on 0.0.0.0:3000 during the original inspection. At approximately 23:19 EDT, `ss -lntp 'sport = :3000'` instead shows PID 52962 listening only on 127.0.0.1:3000. The operator-supplied update reports `--host 127.0.0.1 --port 3000`; the socket binding is independently confirmed here.

Podman events show old container `bc624f0fba57` removed at 23:12:58.966 EDT and replacement `a41fbb8cb151` started at 23:12:59.044 EDT. This was container recreation, not simply a restart of the old container. **Initiating person/agent: UNKNOWN.** The inspected Podman events and user-service journal do not attribute the caller; ownership under the user account is not personal attribution. This task did not perform that change, and the supplied update states its author did not either. Do not credit either with remediation without additional evidence.

Container `amara-matrix` publishes 127.0.0.1:5432. `tailscale serve status` confirms TCP port 8000 on 100.64.1.17 and fd7a:115c:a1e0::672c:f441 forwards to 127.0.0.1:8000. Thus the AMARA backend is loopback-bound but the dashboard is published to the tailnet, subject to access policy; it is not host-only. No external connectivity test was performed.

The supplied port list mislabels Athena: current local Athena is 8001; AMARA dashboard is 8000. n8n/intake were not observed listening in the earlier snapshot. Tailscale proxy listeners are expected to bind overlay addresses. A grep excluding localhost is only triage; it cannot establish an authorization policy or that OPA mediates each socket. No binds or firewall rules were changed by this task. The earlier Open WebUI wildcard-binding finding is resolved at this observation; persistence across future recreation and caller attribution were not established.

## Signed release working-tree drift

`git status` at 23:19 EDT confirms both `release/PROVENANCE_MANIFEST.json` and `release/PROVENANCE_MANIFEST.sig` differ from the committed revision. The supplied operator update reports successful verification against the pinned key, consistent with the earlier successful engine startup log; signature verification was not rerun in this follow-up. A valid working-tree signature does not establish that committed history reproduces the running release. Reconcile and commit the manifest/signature pair with the corresponding covered source changes and retain the release artifacts identified by their hashes, including any ignored build outputs. Neither signed file was changed or committed by this task.

## HS-ISE and HS-SC checks

Neither identifier was found in the checked operator blueprint or scoped documentation/skill search. The supplied task-extractor records and a canonical clearance criterion were not available in this review. No gate was cleared and no Notion record was changed.

Read-only checks performed:
- Yoga: RPM package names/versions filtered for Cisco, AnyConnect, ScreenConnect, ConnectWise, and Secure Client; process command names checked for those plus acise/vpnagent; /opt searched to depth 2 for relevant vendor directory names. No matches returned; /opt/daemons was inaccessible.

These are bounded negative observations, not proof of absence. Command names may truncate; unpackaged or renamed agents, other directories, service files, extensions, and inaccessible paths are outside this check. The paste's generic `ise` pattern would also match unrelated names. Clearing governance gates requires the actual acceptance criteria and adequate evidence coverage, not an automatically generated NONE DETECTED string.

## Teammates and telemetry

`docs/INTAKE_RUNBOOK.md` marks intake FROZEN LOCAL PROTOTYPE. No evidence supports the pasted instruction to 'keep running' or add Kafka publication to it. Kafka producers address topics/partitions; observed offsets are records of progress, not destinations to target.

`scripts/q1_collector.py` deliberately emits EU, AU, and M=?. Its disk calculation is filesystem free-space percentage, not PostgreSQL WAL utilization, and falls back to the home filesystem if the configured volume path is absent. It should not be represented as verified WAL headroom without resolving the real mount.

No new teammates, PostHog event export, or outbound communication was deployed. Proposals should cite the dated baseline with the evidence limits intact.
