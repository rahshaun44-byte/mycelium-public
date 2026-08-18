#ifndef QUANTUM_FLEX_BAE_NODE_HPP
#define QUANTUM_FLEX_BAE_NODE_HPP

#include "quantum-flex/audit_proof.hpp"
#include "quantum-flex/crypto_signer.hpp"

#include <string>

namespace quantumflex::node {

    class BaeNode {
    public:
        BaeNode(std::string postgres_conninfo, crypto::HybridSigner& signer);

        BaeNode(const BaeNode&) = delete;
        auto operator=(const BaeNode&) -> BaeNode& = delete;
        BaeNode(BaeNode&&) = delete;
        auto operator=(BaeNode&&) -> BaeNode& = delete;
        ~BaeNode() = default;

        // Extracts, hashes, signs, and audits a Postgres partition, then drops it
        // inside the same transaction as the ledger write. Throws on any failure —
        // a partial purge (audited-but-not-dropped, or dropped-but-not-audited)
        // must never be observable.
        auto neurogenesis_purge(const std::string& partition_name) -> AuditProof;

    private:
        std::string conninfo_;
        crypto::HybridSigner& signer_;
    };

} // namespace quantumflex::node

#endif // QUANTUM_FLEX_BAE_NODE_HPP
