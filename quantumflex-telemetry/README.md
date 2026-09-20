# QuantumFlex PCR 10 / IMA telemetry

Plane A measurement replay. Not an admission authority.

```
IMA ascii log → SHA-256 PCR 10 extend replay → OPA Gatekeeper
                     │
            ┌────────┴────────┐
         allow              not allow
            │                  │
      ledger commit      Ghost sink (h)
                         Δx ↛ f ; H_attack = 0
```

The engine lives here so it is not mixed into the C++ `src/` tree.
Path inside the crate is `src/telemetry/pcr10_replay.rs`.

```sh
cd quantumflex-telemetry
cargo test
opa test ../sentinel/policies/gatekeeper_attestation.rego \
         ../sentinel/policies/gatekeeper_attestation_test.rego
```

Do not `vault`-sign or lock a host judge from this crate. Do not credit
Ghost residue as entropy.
