/// QuantumFlex Universal Solvency Invariant (R >= O)
/// Enforces fail-closed deterministic policy with explicit typed states:
/// ALLOW (1), DENY (2), UNKNOWN (3).

#[repr(i32)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum InvariantDecision {
    Allow = 1,
    Deny = 2,
    Unknown = 3,
}

impl InvariantDecision {
    pub fn is_allowed(self) -> bool {
        matches!(self, InvariantDecision::Allow)
    }

    pub fn to_code(self) -> i32 {
        self as i32
    }

    pub fn from_code(code: i32) -> Self {
        match code {
            1 => InvariantDecision::Allow,
            2 => InvariantDecision::Deny,
            _ => InvariantDecision::Unknown,
        }
    }
}

/// Evaluates solvency: Resources must strictly cover or exceed Obligations.
/// If measurement validity is false, produces UNKNOWN (fail-closed, never ALLOW).
pub fn evaluate_solvency(
    resources: u64,
    obligations: u64,
    measurement_valid: bool,
) -> InvariantDecision {
    // Fail-closed rule: Missing, stale, or unverified measurements are UNKNOWN
    if !measurement_valid {
        return InvariantDecision::Unknown;
    }

    // Zero resources cannot service non-zero obligations
    if resources == 0 && obligations > 0 {
        return InvariantDecision::Deny;
    }

    if resources >= obligations {
        InvariantDecision::Allow
    } else {
        InvariantDecision::Deny
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn allows_sufficient_resources_with_valid_measurement() {
        assert_eq!(
            evaluate_solvency(100, 90, true),
            InvariantDecision::Allow
        );
    }

    #[test]
    fn allows_exact_solvency_with_valid_measurement() {
        assert_eq!(
            evaluate_solvency(100, 100, true),
            InvariantDecision::Allow
        );
    }

    #[test]
    fn rejects_insufficient_resources() {
        assert_eq!(
            evaluate_solvency(90, 100, true),
            InvariantDecision::Deny
        );
    }

    #[test]
    fn rejects_zero_resources_for_active_obligations() {
        assert_eq!(
            evaluate_solvency(0, 100, true),
            InvariantDecision::Deny
        );
    }

    #[test]
    fn produces_unknown_when_measurement_is_invalid_or_missing() {
        // CRITICAL REFINEMENT: Even if hypothetical numbers are high,
        // invalid measurement produces UNKNOWN, NEVER ALLOW.
        assert_eq!(
            evaluate_solvency(1000, 100, false),
            InvariantDecision::Unknown
        );
    }

    #[test]
    fn produces_unknown_for_zero_obligations_if_measurement_unverified() {
        assert_eq!(
            evaluate_solvency(0, 0, false),
            InvariantDecision::Unknown
        );
    }
}
