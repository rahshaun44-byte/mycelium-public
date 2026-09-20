//! Host telemetry for QuantumFlex Plane A: Linux IMA → PCR 10 replay → OPA.
//!
//! This crate does not admit execution. It prepares the measurement so
//! `sentinel/policies/gatekeeper_attestation.rego` can split \(x_a\) from
//! \(x_q\). Ghost output has zero authority.

pub mod dispatch;
pub mod telemetry;

pub use telemetry::pcr10_replay::*;
