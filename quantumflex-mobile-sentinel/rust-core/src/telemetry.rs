/// QuantumFlex Edge Telemetry Structure

#[derive(Debug, Clone)]
pub struct EdgeTelemetry {
    pub timestamp_ms: u64,
    pub available_ram_mb: u64,
    pub obligated_ram_mb: u64,
    pub is_solvent: bool,
    pub battery_level: u8,
    pub is_charging: bool,
    pub thermal_headroom_c: f32,
}

impl EdgeTelemetry {
    pub fn new(
        timestamp_ms: u64,
        available_ram_mb: u64,
        obligated_ram_mb: u64,
        measurement_valid: bool,
        battery_level: u8,
        is_charging: bool,
        thermal_headroom_c: f32,
    ) -> Self {
        let is_solvent = crate::invariant::evaluate_solvency(
            available_ram_mb,
            obligated_ram_mb,
            measurement_valid,
        )
        .is_allowed();

        Self {
            timestamp_ms,
            available_ram_mb,
            obligated_ram_mb,
            is_solvent,
            battery_level,
            is_charging,
            thermal_headroom_c,
        }
    }
}
