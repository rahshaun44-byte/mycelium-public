/// QuantumFlex Edge Audit Record

#[derive(Debug, Clone)]
pub struct AuditEntry {
    pub sequence: u64,
    pub event_type: &'static str,
    pub allowed: bool,
    pub details: String,
}

impl AuditEntry {
    pub fn new(sequence: u64, event_type: &'static str, allowed: bool, details: String) -> Self {
        Self {
            sequence,
            event_type,
            allowed,
            details,
        }
    }
}

