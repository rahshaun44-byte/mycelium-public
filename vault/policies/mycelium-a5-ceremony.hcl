# mycelium-a5-ed25519-v1 ceremony — least privilege.
# vault write transit/sign/<name>  → capability "update"
# vault read  transit/keys/<name>  → capability "read"
#
# Issue only as a short-lived token:
#   vault token create \
#     -policy=mycelium-a5-ceremony \
#     -ttl=10m -explicit-max-ttl=10m \
#     -no-default-policy -renewable=false

path "transit/sign/mycelium-a5-ed25519-v1" {
  capabilities = ["update"]
}

path "transit/keys/mycelium-a5-ed25519-v1" {
  capabilities = ["read"]
}
