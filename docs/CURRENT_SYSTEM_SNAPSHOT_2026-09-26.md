# QuantumFlex current evidence snapshot — 2026-09-26

Observed 2026-09-26 00:05–00:17 EDT. Read-only except the simulator run noted below.
Supersedes the runtime observations in `CURRENT_SYSTEM_SNAPSHOT_2026-09-25.md`; that file
remains dated evidence. Recheck volatile facts before acting on them.

## Revision

- `/home/quant/mycelium` HEAD `d440e6a` (pushed; `main` == `origin/main`), working tree clean.
- Engine binary `build_check/quantum_flex_engine` SHA-256
  `f197f50de15854b4e6678189c083114f96568090585cfa8ae61ded8cfb38c318`.

## Services (systemd --user)

| Unit | State | PID | Active since (EDT) |
|---|---|---|---|
| quantum-flex-engine-mycelium | active | 52416 | 09-25 23:12:03 |
| immune-daemon | active | 53382 | 09-25 23:14:02 |
| swarm-worker | active | 56879 | 09-25 23:22:54 |
| opa-immune, amara-dashboard, amara-matrix, api-node, athena-node, qf-bot, qf-monitor, qf-kafka-telemetry, quantumflex-ghost-sink | active | — | 09-25 21:32:36 |
| qf-kafka-consumer | active | 5150 | 09-25 21:32:44 |
| quantumflex-witness | active | 3679 | 09-25 21:32:37 |
| qflex-mcp | inactive | — | — |

All `NRestarts=0`. Timers: `sentinel-drive.timer` (~30 s), `neurogenesis.timer` (daily 03:00).

Loopback listeners: engine mTLS `9444`, ghost sink `19443`, OPA `8181`, Postgres `5432`,
Open WebUI `3000`. No `5433` listener.

## Engine — UNSEALED

`engine.log` shows boot `LOCKED` after the 23:12:03 start, then at **23:15:24 EDT**:
`Node Unlocked ... ACTIVE` / `Genesis Authority authenticated via mTLS ... Node unsealed (threshold=3)`.
The engine is ACTIVE, not LOCKED. Who unsealed it was not established. PostgreSQL
integration is disabled (`QF_POSTGRES_CONNINFO` unset). Returning it to LOCKED requires a
restart; not done here.

## Swarm worker — fix deployed

`mcp_layer/swarm_worker.py` last written 23:10:22, before the 23:22:54 process start, and equal
to HEAD (last change `bf209c6`: unwired AMARA/IaC/unknown targets now fail instead of reporting
COMPLETED). The 09-25 snapshot's "return success text without performing the action" is
superseded. The fixed paths have not yet run on a live task (log shows only startup).

## Immune daemon — source drift resolved, gaps remain

- Now runs from `/home/quant/mycelium` via `~/.config/systemd/user/immune-daemon.service`;
  the `/home/quant/pqc-immune-daemon` copy (`7c922487…`) is no longer running. Loaded file
  `pqc-immune-daemon/immune_daemon.py` SHA-256 `dc6c6bc8…43b03a2`, clean vs HEAD. One instance.
- `--profile agility`, `PQC_PROVIDER_CONF=mcp_layer/crypto_provider.conf`, `WORKER_PID` unset:
  on TOXIC it rewrites the conf and signals/halts nothing. No single supervised worker identified.
- `ExecStartPre` provenance gate passes (13/13), but `release/PROVENANCE_MANIFEST.json` does not
  list `immune_daemon.py`, so the gate does not cover the running entrypoint.
- Interpreter is repo `.venv`; swarm-worker uses `venv -> ~/.venv/qflex`. Both Python 3.14;
  package sets not compared.

## Ghost sink simulator

`scripts/simulate_anomaly_injection.py` (commit `ed84a58`) runs on `127.0.0.1:19543` with a temp
ledger, refuses `19443` and busy ports. Run at 00:16: exit 0, 7/7 attacks rejected, 2 admits.
Live ledger `~/.local/share/quantumflex/ghost_sink/entropy_sink_ledger.jsonl` (7 lines,
`6d0d181e…`) byte-identical before and after.

## Deferred

- PostHog wizard output is gitignored (`d440e6a`), not wired into any runtime.

## Decisions (00:30 EDT follow-up)

1. **Engine policy:** boots LOCKED; ACTIVE only via a deliberate 3-of-5 unseal for a named
   operator session; return to LOCKED with `systemctl --user restart quantum-flex-engine-mycelium`
   when the session ends.
   - 23:15:24 unseal attributed to the operator: `~/.bash_history` holds two
     `SHARD_FILES=…shard_1,2,3… ./scripts/unlock_engine.sh` invocations (history is untimestamped,
     so the time match is by log only). Engine stays ACTIVE for the current session.
   - Limit: all 5 shards sit together in `~/qfx-shards/` (0700) on this host, so the 3-of-5
     threshold gives no separation against a local compromise of `quant`.
2. **Immune daemon scope (unsigned helper):**
   - May: poll OPA every 500 ms with a CBOM snapshot and atomically rewrite
     `mcp_layer/crypto_provider.conf` to the fallback on TOXIC.
   - May not: signal any process without a verified `WORKER_PID`, change firewall rules, unseal,
     make non-loopback requests, or claim QF-A5 provenance until `immune_daemon.py` is in the
     signed manifest.
3. **Harvester:** no `quantum-flex-harvester.service` exists (system or user), no timer, no socket.
   `~/quantum-flex-archive` does not exist; the prototype is at `~/qflex/quantum-flex`.
   `/usr/local/libexec/quantum-flex`, `/etc/quantum-flex`, `/opt/quantum-flex-ingest` are absent.
   One leftover: `/etc/systemd/system/quantum_flex_engine.service` (root unit, `User=quant`),
   disabled and inactive, pointing at `/home/quant/pqc-immune-daemon/mycelium/build/`. Left archived.

CLAUDE.md's "second deployment" and harvester notes are stale per item 3.
