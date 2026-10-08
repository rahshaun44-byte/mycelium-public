package quantumflex.gatekeeper

import rego.v1

# ═══════════════════════════════════════════════════════════════════
# QUANTUM FLEX — Gatekeeper Network Policy
# Decoupled Policy Evaluation for Tailscale & Application Mesh
#
# Answers strictly: "Given this input, is this source allowed?"
# Zero networking manipulation in Rego.
# ═══════════════════════════════════════════════════════════════════

default allow := false

# Known/trusted nodes are allowed
allow if {
    input.source_ip in data.quantumflex.trusted_ips
}

# Explicit deny for all other sources
deny if {
    not allow
}

# Structured decision response for REST API queries
decision := {
    "allow": allow,
    "reason": reason,
}

reason := "trusted_source" if {
    allow
}

reason := "untrusted_source" if {
    not allow
}
