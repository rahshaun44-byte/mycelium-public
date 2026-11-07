# IPC challenge-response authentication

The engine IPC listener requires both TLS 1.3 mutual TLS and an Ed25519
challenge-response proof before it reads any application command or QFXK
frame. The source protocol identifier is `qf-ipc-auth-v1`.

## Exchange

1. After the TLS handshake, the engine sends
   `QF_AUTH_CHALLENGE|v1|<server-unix-time>|<64-hex-character-nonce>`.
2. The client signs the canonical JSON `message` object and sends a JSON
   envelope containing that object and its lowercase-hex signature. The
   signed fields are `client_id`, `client_timestamp`, `nonce`, `protocol`,
   and `server_timestamp`. Canonical JSON uses sorted keys, compact
   separators, and ASCII encoding.
3. The engine checks the protocol, client identity, one-connection nonce,
   exact server timestamp, client timestamp freshness (60 seconds), and
   Ed25519 signature. The public key must belong to an `authorized` Ed25519
   node in `registry.json`, or be supplied as `<client_id>.pem` in the
   configured trusted-key directory.
4. An accepted proof receives `ACK|AUTHENTICATED|v1`; a rejected proof
   receives `ERR|AUTHENTICATION_FAILED|<reason>` and the connection closes
   before application processing. Both outcomes are written as `AUTH_AUDIT`
   records.

The receiver gets its trust directory from `QF_DEVICE_KEYS_DIR`; if unset,
it uses `$QF_DATA_DIR/device_keys`. Production service configuration must
point this variable at the operator-managed public-key registry. Do not put
client private keys in the engine's trust directory.

## Verification

The isolated IPC tests create temporary TLS certificates and Ed25519
identities; they do not restart or use the live engine:

```bash
QF_TEST_BUILD_DIR=<isolated-build-dir> PYTHONPATH=. \
  ./venv/bin/python3 -m pytest -q \
  tests/test_adversarial_failure_modes.py tests/test_mlkem_ipc.py
```

The tests cover an authorized client, invalid signatures, an unsigned legacy
command, an unregistered identity, challenge replay, expired timestamps,
application-command denial, fragmented frames, and ML-KEM IPC.

These source changes are not live until an A5-signed build is deployed. The
systemd unit must have `QF_DEVICE_KEYS_DIR` configured before that deployment;
never bypass its existing provenance preflight.
