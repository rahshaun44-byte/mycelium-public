#include "quantum-flex/bae_node.hpp"

#include "quantum-flex/crypto_hasher.hpp"

#include <pqxx/pqxx>

#include <cstdint>
#include <ctime>
#include <regex>
#include <sstream>
#include <stdexcept>
#include <utility>

namespace quantumflex::node {

    namespace {
        // Identifiers only: defense in depth on top of pqxx::quote_name before a
        // caller-supplied partition name reaches raw SQL.
        auto is_safe_identifier(const std::string& name) -> bool {
            static const std::regex pattern("^[a-zA-Z_][a-zA-Z0-9_]*$");
            return std::regex_match(name, pattern);
        }

        // Deterministic row/column serialization: identical partition contents
        // must always produce identical bytes, or the K(t) hash chain breaks.
        auto serialize_partition(pqxx::work& txn, const std::string& partition_name) -> std::string {
            pqxx::result rows = txn.exec(
                "SELECT * FROM " + txn.quote_name(partition_name) + " ORDER BY id ASC");

            std::ostringstream payload;
            for (const auto& row : rows) {
                for (const auto& field : row) {
                    payload << (field.is_null() ? "\\N" : field.c_str()) << '|';
                }
                payload << '\n';
            }
            return payload.str();
        }
    } // namespace

    BaeNode::BaeNode(std::string postgres_conninfo, crypto::HybridSigner& signer)
        : conninfo_(std::move(postgres_conninfo)), signer_(signer) {}

    auto BaeNode::neurogenesis_purge(const std::string& partition_name) -> AuditProof {
        if (!is_safe_identifier(partition_name)) {
            throw std::runtime_error("Refusing unsafe partition identifier: " + partition_name);
        }

        pqxx::connection conn(conninfo_);
        pqxx::work txn(conn);

        txn.exec(
            "CREATE TABLE IF NOT EXISTS akashic_ledger ("
            "  pulse_id BIGSERIAL PRIMARY KEY,"
            "  k_value TEXT NOT NULL,"
            "  hybrid_sig TEXT NOT NULL,"
            "  volume_purged BIGINT NOT NULL,"
            "  audit_proof JSONB NOT NULL,"
            "  committed_at TIMESTAMPTZ DEFAULT NOW()"
            ")");

        const pqxx::result exists = txn.exec("SELECT to_regclass($1)", pqxx::params{partition_name});
        if (exists[0][0].is_null()) {
            throw std::runtime_error("Partition does not exist: " + partition_name);
        }

        const pqxx::result prev = txn.exec("SELECT k_value FROM akashic_ledger ORDER BY pulse_id DESC LIMIT 1");
        const std::string prev_k = prev.empty() ? std::string(64, '0') : prev[0][0].as<std::string>();

        const std::string payload = serialize_partition(txn, partition_name);
        const std::string pre_purge_hash = crypto::Hasher::generate_sha256(payload);
        const std::string base_hash = crypto::Hasher::generate_sha256(payload + prev_k);
        const std::string signature = signer_.sign_payload(base_hash);
        const std::string k_t = crypto::Hasher::generate_sha256(payload + prev_k + signature);

        AuditProof proof;
        proof.pre_purge_hash = pre_purge_hash;
        proof.k_t_ascension_hash = k_t;
        proof.hybrid_signature = signature;
        proof.volume_purged_bytes = payload.size();
        proof.timestamp = static_cast<int64_t>(std::time(nullptr));

        if (!proof.verify_proof()) {
            throw std::runtime_error("AuditProof failed structural verification for partition: " + partition_name);
        }

        txn.exec(
            "INSERT INTO akashic_ledger (k_value, hybrid_sig, volume_purged, audit_proof) "
            "VALUES ($1, $2, $3, $4::jsonb)",
            pqxx::params{
                proof.k_t_ascension_hash,
                proof.hybrid_signature,
                static_cast<int64_t>(proof.volume_purged_bytes),
                proof.to_canonical_json()});

        // Same transaction as the ledger insert above: if this fails, the
        // INSERT rolls back too, so the ledger can never claim a purge that
        // didn't happen.
        txn.exec("DROP TABLE " + txn.quote_name(partition_name));

        txn.commit();
        return proof;
    }

} // namespace quantumflex::node
