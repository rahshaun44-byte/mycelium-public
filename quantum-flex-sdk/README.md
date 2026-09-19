# Quantum Flex Node SDK privacy filter

This dependency-free Rust crate provides the `_optout` SSID exclusion step for
edge Wi-Fi telemetry. `should_exclude_ssid` matches the literal `_optout`
substring anywhere in an SSID, ignoring ASCII case. `prepare_telemetry` drops
matching scan results before constructing telemetry observations. Empty or
hidden SSIDs pass through. This crate does not scan Wi-Fi, send packets, or
apply the separate `_nomap` convention.

The scanner integration should pass raw results to `prepare_telemetry` **before**
BSSID anonymization, signing, logging, persistence, or transmission. Do not
write excluded scan results to debug logs.

```rust
use quantum_flex_sdk::{prepare_telemetry, ScanResult};

let observations = prepare_telemetry(vec![ScanResult {
    ssid: "Home_optout".into(),
    bssid: "aa:bb:cc:dd:ee:ff".into(),
    rssi_dbm: -48,
}]);
assert!(observations.is_empty());
```

## Fully offline use

Install a Rust toolchain and this source tree while connected, or transfer
both using trusted removable media. This crate has no third-party dependencies,
so after the toolchain is installed you can build and test with networking
disabled:

```sh
cd quantum-flex-sdk
CARGO_NET_OFFLINE=true cargo test --offline
CARGO_NET_OFFLINE=true cargo build --release --offline
```

The compiled library and these commands need no internet. The wider Quantum
Flex stack is a separate deployment: local database, model files, and any
other service dependencies must also be installed locally. Disable cloud
endpoints and outbound networking, then verify each required service while the
machine is disconnected. Wi-Fi scanning itself requires a supported local
radio and OS permissions, even with no internet connection.
