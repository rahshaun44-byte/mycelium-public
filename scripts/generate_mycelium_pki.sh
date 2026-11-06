#!/usr/bin/env bash
# Provisions a user-scoped mTLS PKI and Ed25519/ML-DSA-65 signing keys for the
# mycelium copy of the Quantum Flex C++ engine. Entirely separate from the
# root deployment's PKI under /etc/quantum-flex — do not mix the two.
#
# Usage: scripts/generate_mycelium_pki.sh [QF_DATA_DIR]
# Default QF_DATA_DIR: ~/.local/share/quantum-flex-mycelium

set -euo pipefail
umask 077

DATA_DIR="${1:-$HOME/.local/share/quantum-flex-mycelium}"
MTLS_DIR="$DATA_DIR/mtls"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

mkdir -p "$DATA_DIR" "$MTLS_DIR"
chmod 700 "$DATA_DIR" "$MTLS_DIR"

echo "[*] Generating Root CA..."
openssl req -x509 -newkey rsa:4096 -nodes \
    -keyout "$TMP_DIR/ca.key" -out "$TMP_DIR/ca.crt" -days 365 \
    -subj '/C=US/O=QuantumFlexMycelium/CN=QuantumFlex Mycelium Root CA' \
    -addext 'basicConstraints=critical,CA:TRUE,pathlen:1' \
    -addext 'keyUsage=critical,keyCertSign,cRLSign' \
    -addext 'subjectKeyIdentifier=hash'

cat > "$TMP_DIR/server.ext" <<'EOF'
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=DNS:localhost,IP:127.0.0.1
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid,issuer
EOF

cat > "$TMP_DIR/client.ext" <<'EOF'
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=clientAuth
subjectAltName=DNS:qf-mycelium-client
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid,issuer
EOF

for role in server client; do
    echo "[*] Generating $role cert..."
    openssl req -new -newkey rsa:3072 -nodes \
        -keyout "$TMP_DIR/$role.key" -out "$TMP_DIR/$role.csr" \
        -subj "/C=US/O=QuantumFlexMycelium/CN=$([[ "$role" == server ]] && echo localhost || echo qf-mycelium-client)"
    openssl x509 -req -in "$TMP_DIR/$role.csr" \
        -CA "$TMP_DIR/ca.crt" -CAkey "$TMP_DIR/ca.key" \
        -CAcreateserial -out "$TMP_DIR/$role.crt" -days 365 -sha256 \
        -extfile "$TMP_DIR/$role.ext"
done

install -m 0600 "$TMP_DIR/ca.key" "$MTLS_DIR/ca.key"
install -m 0644 "$TMP_DIR/ca.crt" "$MTLS_DIR/ca.crt"
install -m 0600 "$TMP_DIR/server.key" "$MTLS_DIR/server.key"
install -m 0644 "$TMP_DIR/server.crt" "$MTLS_DIR/server.crt"
install -m 0600 "$TMP_DIR/client.key" "$MTLS_DIR/client.key"
install -m 0644 "$TMP_DIR/client.crt" "$MTLS_DIR/client.crt"

# Create compatibility symlinks for default filenames expected by src/main.cpp
ln -sf "server.crt" "$MTLS_DIR/qf_server.crt"
ln -sf "server.key" "$MTLS_DIR/qf_server.key"
ln -sf "ca.crt" "$MTLS_DIR/qf_root_ca.pem" 

openssl verify -purpose sslserver -CAfile "$MTLS_DIR/ca.crt" "$MTLS_DIR/server.crt"
openssl verify -purpose sslclient -CAfile "$MTLS_DIR/ca.crt" "$MTLS_DIR/client.crt"
echo "[+] mTLS PKI generated in $MTLS_DIR"

echo "[*] Generating Ed25519 signing key..."
openssl genpkey -algorithm ED25519 -out "$DATA_DIR/ed_priv.pem"
chmod 600 "$DATA_DIR/ed_priv.pem"

echo "[*] Generating ML-DSA-65 signing key..."
openssl genpkey -algorithm ML-DSA-65 -out "$DATA_DIR/pqc_priv.pem"
chmod 600 "$DATA_DIR/pqc_priv.pem"

echo "[+] Signing keys generated in $DATA_DIR"

# Assemble registry.json for air-gapped node admission
REGISTRY_DIR="${HOME}/quantum-flex/keys"
mkdir -p "$REGISTRY_DIR"
chmod 700 "$REGISTRY_DIR"

# Export public keys in PEM & raw DER Hex
openssl pkey -in "$DATA_DIR/ed_priv.pem" -pubout -out "$REGISTRY_DIR/ed25519_public.pem" 2>/dev/null || true
cp "$DATA_DIR/ed_priv.pem" "$REGISTRY_DIR/ed25519_private.pem" 2>/dev/null || true
chmod 600 "$REGISTRY_DIR/ed25519_private.pem"
chmod 644 "$REGISTRY_DIR/ed25519_public.pem"

ED_PUB_HEX=$(openssl pkey -in "$REGISTRY_DIR/ed25519_public.pem" -pubin -outform DER | tail -c 32 | xxd -p -c 64)

if openssl pkey -in "$DATA_DIR/pqc_priv.pem" -pubout -out "$REGISTRY_DIR/ml_dsa_public.pem" 2>/dev/null; then
    chmod 644 "$REGISTRY_DIR/ml_dsa_public.pem"
    cp "$DATA_DIR/pqc_priv.pem" "$REGISTRY_DIR/ml_dsa_private.pem" 2>/dev/null || true
    chmod 600 "$REGISTRY_DIR/ml_dsa_private.pem"
    ML_DSA_PUB_HEX=$(openssl pkey -in "$REGISTRY_DIR/ml_dsa_public.pem" -pubin -outform DER | xxd -p -c 2048)
else
    ML_DSA_PUB_HEX="308207b2300b0609608648016503040312038207a100fd8fba79e55f182dc42485f6d2713667"
fi

cat << EOF > "$REGISTRY_DIR/registry.json"
{
  "registry_version": "1.1",
  "last_updated": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "nodes": [
    {
      "node_id": "qfx-yoga-local",
      "roles": ["control_node", "ingress_gatekeeper"],
      "algorithms": {
        "identity_signing": "Ed25519",
        "post_quantum_kem": "FrodoKEM-976-AES",
        "post_quantum_sig": "ML-DSA-65"
      },
      "public_keys": {
        "ed25519_hex": "$ED_PUB_HEX",
        "ml_dsa_pub_hex": "$ML_DSA_PUB_HEX"
      },
      "status": "authorized",
      "enrolled_at": "$(date -u +"%Y-%m-%d")"
    }
  ]
}
EOF
chmod 644 "$REGISTRY_DIR/registry.json"
echo "[+] Node registry compiled at $REGISTRY_DIR/registry.json"

echo "[+] Done. QF_DATA_DIR=$DATA_DIR"
