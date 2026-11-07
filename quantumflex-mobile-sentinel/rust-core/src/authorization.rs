/// QuantumFlex Mobile Node Authorization Gate
/// Principle: UNKNOWN != ALLOW, MISSING = DENY

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PolicyDecision {
    Allow,
    Deny(&'static str),
}

pub fn evaluate_node_action(
    node_id: &str,
    has_valid_signature: bool,
    action_permission: &str,
) -> PolicyDecision {
    if node_id.is_empty() {
        return PolicyDecision::Deny("MISSING_NODE_IDENTITY");
    }
    if !has_valid_signature {
        return PolicyDecision::Deny("INVALID_CRYPTOGRAPHIC_SIGNATURE");
    }
    match action_permission {
        "READ_TELEMETRY" | "RUN_LOCAL_INFERENCE" | "CHECK_INVARIANT" => PolicyDecision::Allow,
        "SUBSTRATE_MUTATE" | "EXPORT_KEYS" => {
            PolicyDecision::Deny("PRIVILEGED_ACTION_FORBIDDEN_ON_EDGE")
        }
        _ => PolicyDecision::Deny("UNKNOWN_ACTION_DEFAULT_DENY"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_valid_action() {
        assert_eq!(
            evaluate_node_action("pixel11pro", true, "READ_TELEMETRY"),
            PolicyDecision::Allow
        );
    }

    #[test]
    fn test_missing_signature_denied() {
        assert_eq!(
            evaluate_node_action("pixel11pro", false, "READ_TELEMETRY"),
            PolicyDecision::Deny("INVALID_CRYPTOGRAPHIC_SIGNATURE")
        );
    }

    #[test]
    fn test_unknown_action_denied() {
        assert_eq!(
            evaluate_node_action("pixel11pro", true, "EXECUTE_ARBITRARY_SHELL"),
            PolicyDecision::Deny("UNKNOWN_ACTION_DEFAULT_DENY")
        );
    }
}

