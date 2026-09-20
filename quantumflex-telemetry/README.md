# QuantumFlex PCR 10 / IMA telemetry

Plane A measurement replay. Not an admission authority.

```
IMA ascii log → SHA-256 PCR 10 extend replay → OPA Gatekeeper
                     │
            ┌────────┴────────┐
         allow      →  ledger commit (Y)
not allow  →  Ghost sink (h) via GatekeeperDispatcher
                         Δx ↛ f ; H_attack = 0
```

The engine lives here so it is not mixed into the C++ `src/` tree.
Path inside the crate is `src/telemetry/pcr10_replay.rs`.
Dispatch is `src/dispatch/ghost_dispatcher.rs`. The HTTP absorber is
the sibling crate `quantumflex-ghost-sink` (loopback `:19443`, not
engine mTLS `:9443`).

```sh
cd quantumflex-telemetry
cargo test
opa test ../sentinel/policies/gatekeeper_attestation.rego \
         ../sentinel/policies/gatekeeper_attestation_test.rego
cd ../quantumflex-ghost-sink && cargo test
```

Do not `vault`-sign or lock a host judge from this crate. Do not credit
Ghost residue as entropy.
