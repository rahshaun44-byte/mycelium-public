pub mod invariant;
pub mod authorization;
pub mod telemetry;
pub mod audit;

use std::ffi::{c_char, CString};
use jni::JNIEnv;
use jni::objects::JClass;
use jni::sys::{jboolean, jint, jlong, jstring};
use invariant::InvariantDecision;

// =========================================================================
// Native C ABI Exports
// =========================================================================

#[no_mangle]
pub extern "C" fn qflex_evaluate_solvency(
    resources: u64,
    obligations: u64,
    measurement_valid: bool,
) -> i32 {
    invariant::evaluate_solvency(resources, obligations, measurement_valid).to_code()
}

#[no_mangle]
pub extern "C" fn qflex_version() -> *mut c_char {
    CString::new("QuantumFlex Mobile Sentinel v0.1.0 (Native ARM64)")
        .unwrap()
        .into_raw()
}

// =========================================================================
// JNI Exports for com.quantumflex.sentinel.NativeBridge
// =========================================================================

#[no_mangle]
pub extern "system" fn Java_com_quantumflex_sentinel_NativeBridge_initialize(
    _env: JNIEnv,
    _class: JClass,
) -> jboolean {
    1 // JNI_TRUE
}

#[no_mangle]
pub extern "system" fn Java_com_quantumflex_sentinel_NativeBridge_getVersion(
    mut env: JNIEnv,
    _class: JClass,
) -> jstring {
    let output = env.new_string("QuantumFlex Mobile Sentinel v0.1.0 [Rust Core]");
    match output {
        Ok(s) => s.into_raw(),
        Err(_) => std::ptr::null_mut(),
    }
}

#[no_mangle]
pub extern "system" fn Java_com_quantumflex_sentinel_NativeBridge_evaluateSolvency(
    _env: JNIEnv,
    _class: JClass,
    resources: jlong,
    obligations: jlong,
    measurement_valid: jboolean,
) -> jint {
    if resources < 0 || obligations < 0 || measurement_valid == 0 {
        return InvariantDecision::Unknown.to_code();
    }

    invariant::evaluate_solvency(resources as u64, obligations as u64, true).to_code()
}

#[no_mangle]
pub extern "system" fn Java_com_quantumflex_sentinel_NativeBridge_shutdown(
    _env: JNIEnv,
    _class: JClass,
) {
    // Graceful release of native background resources
}
