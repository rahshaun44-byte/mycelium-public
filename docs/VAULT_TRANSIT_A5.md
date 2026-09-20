# Vault Transit for mycelium-a5-ed25519-v1

Operational release authority lives in Vault Transit. GitHub Actions +
Cosign is a **different plane** (pipeline attestation). A compromised
runner can forge build metadata; it cannot sign A5 manifests without a
ceremony token.

This is not a fourth workflow. It is the signer backend for Workflow 1.

## Create vs import

```text
vault write transit/keys/mycelium-a5-ed25519-v1 type=ed25519
```

That command instructs Transit to **generate a fresh random Ed25519
keypair inside Vault's cryptographic boundary**. The label stays
`mycelium-a5-ed25519-v1`; the public/private pair is entirely different.
Downstream verifiers that already pin `release/release_signing_key.pub`
see an identity mismatch.

Preserving the existing identity requires Transit's Bring Your Own Key
import (`transit/keys/<name>/import`) using a temporary wrapping key:

1. `vault read transit/wrapping_key`
2. Wrap the existing Ed25519 private key to that wrapping public key.
3. `vault write transit/keys/mycelium-a5-ed25519-v1/import ... type=ed25519`
   with `exportable=false` (Vault default; **immutable** after
   create/import). `allow_plaintext_backup` likewise defaults to false
   and cannot be flipped later.

```bash
vault read -format=json transit/keys/mycelium-a5-ed25519-v1
# expect exportable=false, allow_plaintext_backup=false
# expect public_key == raw 32 bytes of the pinned PEM

python3 scripts/vault_a5_transit.py   # HALTs on missing key or pin mismatch
```

Do not try to flip `exportable` later. Transit will refuse.

## Sign the file bytes, not a digest

Standard Ed25519 (RFC 8032) operates on the **full, unhashed message**.
Vault `transit/sign/<name>` `input` is standard Base64 of those raw
bytes, with `prehashed=false`. That is **not** Ed25519ph.

If a script SHA-256s the manifest and Base64s the 32-byte digest, Vault
signs the digest as if it were the complete message. A standard Ed25519
verifier fed the original file will reject the signature.

JSON encoding is not a byte stream. Sign the exact serialized file
written to disk. This repo freezes `json.dumps(..., indent=2,
sort_keys=True) + "\n"` (`scripts/qf_signing_ceremony.py`) and
re-reads those on-disk bytes before the Transit call. RFC 8785 is an
equivalent alternative; mixing the two encodings is a different
message.

`signing.key_id` (and `signing.plane`) live **inside** the signed
payload so a valid signature from Key B cannot satisfy a manifest that
claims Key A.

## Policy and tokens

`vault write transit/sign/<name>` (HTTP POST) maps to capability
**update**. `vault read transit/keys/<name>` maps to **read**. The
ceremony policy is exactly:

```hcl
path "transit/sign/mycelium-a5-ed25519-v1" {
  capabilities = ["update"]
}

path "transit/keys/mycelium-a5-ed25519-v1" {
  capabilities = ["read"]
}
```

Ephemeral ceremony tokens:

```bash
./scripts/vault_a5_token.sh
# -ttl=10m -explicit-max-ttl=10m -no-default-policy -renewable=false
```

Do not put `VAULT_TOKEN` in GitHub Actions, Quadlets, or long-lived env
blocks. CI remains Cosign/OIDC (other plane) and verify-only for A5.

## Verify

The host judge checks `(plane, key_id)` against an explicit whitelist
and refuses fallback lookups (no keyring roulette).

Schema **2.2.0** requires `signing.key_id`, `signing.plane`, and sidecar
`KEY_ID`. Failure does **not** fall back to 2.1.0. A 2.2.0 payload that
has those fields stripped is still 2.2.0 and is denied at that
boundary. Historical 2.1.0 releases (no `key_id`) still verify by
pubkey file only; a 2.1.0 payload that carries 2.2.0 identity fields is
denied as a protocol downgrade.
