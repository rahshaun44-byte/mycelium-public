#!/usr/bin/env bash
# Issue an ephemeral A5 ceremony token. Does not mint keys.
# Requires an admin/root token in VAULT_TOKEN with policy-write + token-create.
set -euo pipefail

POLICY_FILE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)/vault/policies/mycelium-a5-ceremony.hcl"

if [[ -z "${VAULT_ADDR:-}" ]]; then
  echo "[HARD-STOP] VAULT_ADDR is unset." >&2
  exit 1
fi

vault policy write mycelium-a5-ceremony "${POLICY_FILE}"
vault token create \
  -policy=mycelium-a5-ceremony \
  -ttl=10m \
  -explicit-max-ttl=10m \
  -no-default-policy \
  -renewable=false \
  -display-name=mycelium-a5-ceremony
