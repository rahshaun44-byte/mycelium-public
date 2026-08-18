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
echo "[+] Done. QF_DATA_DIR=$DATA_DIR"
