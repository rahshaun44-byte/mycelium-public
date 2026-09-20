# QuantumFlex Ghost Node sink

Isolated append-only absorption of Gatekeeper `h`. **Zero authority.**
Do not credit residues as KEM entropy. Do not bind engine mTLS `:9443`.

```
not allow  →  POST /v1/sink/anomaly  →  hash-chained JSONL
allow      →  never reaches this process (Y ∩ h = ∅)
```

## Run (host)

```sh
cd quantumflex-ghost-sink
SINK_LISTEN_ADDR=127.0.0.1:19443 cargo run --release
```

Storage defaults to `$XDG_DATA_HOME/quantumflex/ghost_sink` or
`~/.local/share/quantumflex/ghost_sink`. Container default is
`/var/log/quantumflex/sink` (volume-mount it).

`0.0.0.0` is refused unless `SINK_ALLOW_UNBOUND=1` (container netns only).

## Tests

```sh
cargo test
curl -sS http://127.0.0.1:19443/healthz
```

A Quadlet template lives in `systemd-backup/quantumflex-ghost-sink.container`.
It is not a live Yoga unit. Image digest is unpinned (QF-R3 OPEN).
