# QuantumFlex current evidence snapshot

Observed September 25, 2026, approximately 23:01–23:06 America/New_York.
This is a read-only operational refresh plus this documentation file, not a security certification or deployment change. Recheck volatile facts before operational decisions.

**Superseded 2026-09-26:** runtime observations below are replaced by CURRENT_SYSTEM_SNAPSHOT_2026-09-26.md (immune daemon now runs the Mycelium copy; swarm-worker fix deployed).

**23:19 EDT follow-up:** The earlier Open WebUI wildcard listener below is historical. Current socket inspection shows 127.0.0.1:3000 (PID 52962). Podman records container replacement at 23:12:58–23:12:59; initiating person/agent remains unknown. Tailscale Serve confirms AMARA port 8000 is published on the tailnet. See REMEDIATION_REVIEW_2026-09-25.md for event timestamps, attribution limits, and the uncommitted signed-release warning. Original observations below are preserved as dated evidence.

## Corrected baseline

QuantumFlex/Mycelium is an implemented, running personal security, evidence, policy, telemetry, and local-model system. It is not merely skill folders or a proposed architecture. Mycelium governs/adopts the independently buildable QuantumFlex crypto/wire runtime. The Python control plane, C++ evidence engine, distributed Kafka pipeline, and agent task worker must be assessed separately. Zenith's proposed adaptive agents are not established by the existence of that worker.

## Evidence observed directly

- Workspace `/home/quant/mycelium`, HEAD `bc5c9156c9e6466067c9d9121cedfb2908d75d0e`. Existing tracked modifications and untracked files were present before inspection and left intact. No fetch/pull performed; remote parity is unknown.
- Host `fedora`, kernel `7.2.7-200.fc44.x86_64`, AMD Ryzen AI 5 340, 6 cores/12 threads, approximately 15,127 MiB RAM. At sampling, approximately 3,143 MiB RAM available and 7,638 of 8,191 MiB swap used. CPU boost sysfs value was `1`; older boost-disabled assertions are not current.
- User services active/running: `quantum-flex-engine-mycelium`, `opa-immune`, `immune-daemon`, `amara-dashboard`, `amara-matrix`, `api-node`, `athena-node`, `qf-bot`, `qf-monitor`, `qf-kafka-telemetry`, `qf-kafka-consumer`, `quantumflex-witness`, `quantumflex-ghost-sink`, `swarm-worker`.
- `qflex-mcp` user unit inactive. System Ollama active; user Ollama unit inactive. Distinguish the two scopes.
- Engine ExecStart: `/home/quant/mycelium/build_check/quantum_flex_engine`, PID 38101 at sampling, active since 22:34:31 EDT. Listener `127.0.0.1:9444`.
- Latest engine file-log startup reports signature verification, 13/13 artifact hash matches, then `LOCKED`, and PostgreSQL integration disabled because `QF_POSTGRES_CONNINFO` is unset. These are startup/log observations, not a fresh authenticated engine-state query or independent manifest verification. Earlier entries show a binary hash mismatch and systemd restart count reaching 706 before successful startup; do not erase that history or infer its repair cause.
- Other local TCP listeners include 8181, 5432, 8000, 8001, 8080, 9000, 11434, and 19443. No 5433 or 5678 listener appeared in the TCP snapshot. This does not prove absence of stopped databases or n8n installations.
- A Python process (PID 3668) listens on `0.0.0.0:3000`. Its application identity and firewall reachability were not established. Therefore the blanket assertion that every host service is loopback-only is false. Tailnet-address listeners also exist.
- Kafka forwarder logs show pulses at roughly 15-second intervals with partition 0 offsets 2421–2437, ending at 23:01:46 EDT in the captured slice. Consumer logs report each pulse persisted in AMARA and embedded in Athena. Source confirms that success message follows a committed DB insert and successful Athena response. No independent DB/vector query was performed.
- Ollama `/api/tags` lists `amara:latest`, `athena:latest`, `qwen2.5-coder:1.5b`, `qwen2.5-coder:7b`, `gemma2:2b`, and `nomic-embed-text:latest`. Amara/Athena model metadata names the 1.5B coder parent. Inventory is not an inference-quality test.

## Critical source/deployment distinction

The running `immune-daemon.service` working directory is `/home/quant/pqc-immune-daemon/pqc-immune-daemon`. Its parent repository HEAD is `f749a60d8d3421fc3f8488dd15f540d019235836`, with an already-dirty working tree.

The on-disk daemon selected by that unit has SHA-256:
`7c922487987c2961e35956369e82cb957d85c751f91680c0da6382b4e5532930`.
This matches the historical daemon hash in the supplied August transcript. It contains the older quarantine/recovery path. The inspected file contains no `fips_strict` or `notify_kafka` symbol. Process environment inspection selected only non-secret policy variables: `OPA_ENDPOINT` was present; `WORKER_PID` and `PQC_COMPLIANCE_PROFILE` were absent. No claim is made that a Python process's loaded code was cryptographically attested from memory.

The Mycelium copy `pqc-immune-daemon/immune_daemon.py` instead hashes to:
`dc6c6bc88514f70c6b7c5bfac1ac18980c6a1d656118fd5fb54eaf0db43b03a2`.
It implements strict profiles and requires a worker PID for non-dry strict startup. Do not attribute this copy's enforcement to the running older service.

## Implemented source and bounded claims

- `src/core/ipc_server.cpp` selects `MLKem768Engine`, enforces TLS 1.3 minimum, and contains locked-state rejection. Native ML-KEM IPC and the crypto/wire package split supersede broad historical Frodo descriptions. Runtime binary/source equivalence was not rebuilt or independently verified here.
- `docs/MLKEM_STRICT_MIGRATION.md` explicitly distinguishes KEM confirmation over mTLS from ML-KEM-derived application encryption and FIPS module validation. Strict denial stops rather than following the historical Frodo/X25519 ladder. The document marks deployment pending; the live daemon-path distinction confirms that caution remains necessary.
- `mcp_layer/swarm_worker.py` implements PostgreSQL queue polling with `FOR UPDATE SKIP LOCKED`, task-state updates, and an Athena HTTP dispatch. AMARA, IaC, and generic branches currently return success text without performing the named action. The Athena request in this file has no API-key header. Running service status does not establish successful authorized task execution or four autonomous teammates.
- Intake code and fencing tests exist (`scripts/intake_service.py`, `scripts/intake_store.py`, `tests/test_intake_fencing.py`). No live intake or n8n execution was verified.
- Five QuantumFlex skill directories and four replay-vision skill directories exist; directory presence is separate from invocation and runtime capability.
- `package.json` declares `posthog-js`, `posthog-node`, and `@posthog/ai`. The local `posthog-self-driving-report.md` records three enabled scouts, two replay scanners, and a GitHub Issues warehouse connection, with other sources dormant. This refresh did not query PostHog remotely. A scoped source search found no `posthog.init`, `new PostHog`, or `PostHog(` in api_node, mcp_layer, amara, or scripts. Dependencies/report assertions do not establish browser instrumentation or current remote state.

## Documentation precedence and unresolved scope

Use direct runtime observations for this snapshot, then exact deployed files, then current source and dated records. Do not let old README/CLAUDE/skill wording override measured state. In particular:

- CLAUDE.md's statement that the C++ engine is not wired into a running service is stale.
- The September 15 optimization handoff's CPU model and boost-disabled/all-loopback claims conflict with this host snapshot.
- Older dual-Postgres descriptions do not establish an active 5433 backend, and the engine startup explicitly disables its PostgreSQL integration.
- Historical test counts, benchmark timings, cryptographic guarantees, sponsor/funding assertions, and regulatory claims were not revalidated. No test suite, failure injection, unseal ceremony, credential/shard inspection, or live mutation was performed.

This file is a durable handoff for future sessions to read. It does not assert automatic cross-task memory synchronization or continuous monitoring.
