#ifndef QUANTUM_FLEX_HYBRID_KEM_HPP
#define QUANTUM_FLEX_HYBRID_KEM_HPP

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>
#include <utility>
#include <memory>
#include <openssl/evp.h>

namespace quantumflex::crypto {

    // Production IPC KEM. Algorithm implementation != FIPS 140-3 module validation.
    constexpr std::size_t MLKEM768_PUBLIC_KEY_BYTES = 1184;
    constexpr std::size_t MLKEM768_CIPHERTEXT_BYTES = 1088;
    constexpr std::size_t MLKEM768_SHARED_SECRET_BYTES = 32;

    class MLKem768Engine {
    public:
        explicit MLKem768Engine(std::string properties = {});
        MLKem768Engine(const MLKem768Engine&) = delete;
        auto operator=(const MLKem768Engine&) -> MLKem768Engine& = delete;
        [[nodiscard]] auto public_key() const -> std::vector<uint8_t>;
        [[nodiscard]] static auto encapsulate(const std::vector<uint8_t>& public_key,
                                             const std::string& properties = {})
            -> std::pair<std::vector<uint8_t>, std::vector<uint8_t>>;
        // ML-KEM uses implicit rejection: a correctly sized corrupt ciphertext may
        // return a different secret, not an error. Confirm possession separately.
        [[nodiscard]] auto decapsulate(const std::vector<uint8_t>& ciphertext) const -> std::vector<uint8_t>;
        [[nodiscard]] static auto confirmation(const std::vector<uint8_t>& secret,
                                              const std::vector<uint8_t>& ciphertext,
                                              const std::string& properties = {}) -> std::vector<uint8_t>;
    private:
        std::string properties_;
        std::unique_ptr<EVP_PKEY, decltype(&EVP_PKEY_free)> key_{nullptr, EVP_PKEY_free};
    };

#ifdef QUANTUMFLEX_ENABLE_LEGACY_FRODO_RESEARCH
    // Legacy research implementation below is not selected by the IPC server.
    // ── Parameter Specification ─────────────────────────────────────────────
    // FrodoKEM-976-AES / FrodoKEM-976-SHAKE: n=976, q=65536 (2^16), n_bar=8
    // Wire sizes strictly match NIST submission & RFC draft specifications
    constexpr std::size_t FRODO976_PUBLIC_KEY_BYTES   = 15632;
    constexpr std::size_t FRODO976_CIPHERTEXT_BYTES    = 15744;
    constexpr std::size_t FRODO976_SHARED_SECRET_BYTES = 32;
    constexpr std::size_t FRODO976_SECRET_KEY_BYTES    = 31296;

    constexpr std::size_t X25519_PUBLIC_KEY_BYTES      = 32;
    constexpr std::size_t X25519_PRIVATE_KEY_BYTES     = 32;
    constexpr std::size_t X25519_SHARED_SECRET_BYTES   = 32;

    constexpr std::size_t HYBRID_PUBLIC_KEY_BYTES      = X25519_PUBLIC_KEY_BYTES + FRODO976_PUBLIC_KEY_BYTES; // 15664 B
    constexpr std::size_t HYBRID_CIPHERTEXT_BYTES     = X25519_PUBLIC_KEY_BYTES + FRODO976_CIPHERTEXT_BYTES; // 15776 B
    constexpr std::size_t HYBRID_SHARED_SECRET_BYTES   = 32; // CFRG HKDF output

    // ── Hybrid Wire Structures ──────────────────────────────────────────────
    struct HybridPublicKey {
        std::vector<uint8_t> x25519_pk; // 32 bytes
        std::vector<uint8_t> frodo_pk;  // 15632 bytes

        [[nodiscard]] auto serialize() const -> std::vector<uint8_t>;
        static auto deserialize(const uint8_t* data, std::size_t len) -> HybridPublicKey;
    };

    struct HybridCiphertext {
        std::vector<uint8_t> x25519_ct; // 32 bytes ephemeral public key
        std::vector<uint8_t> frodo_ct;  // 15744 bytes Frodo ciphertext

        [[nodiscard]] auto serialize() const -> std::vector<uint8_t>;
        static auto deserialize(const uint8_t* data, std::size_t len) -> HybridCiphertext;
    };

    struct HybridPrivateKey {
        std::vector<uint8_t> x25519_sk; // 32 bytes
        std::vector<uint8_t> frodo_sk;  // 31296 bytes
        
        ~HybridPrivateKey();
    };

    struct HybridKeyPair {
        HybridPublicKey  public_key;
        HybridPrivateKey private_key;
    };

    // ── Hybrid Combiner Engine (CFRG draft-irtf-cfrg-hybrid-kems) ───────────
    class HybridKemEngine {
    public:
        // Generates hybrid ephemeral/static keypair (X25519 + FrodoKEM-976)
        [[nodiscard]] static auto generate_keypair() -> HybridKeyPair;

        // Encapsulate: generates ephemeral secret, returns hybrid ciphertext and derived shared secret
        [[nodiscard]] static auto encapsulate(const HybridPublicKey& pk) 
            -> std::pair<HybridCiphertext, std::vector<uint8_t>>;

        // Decapsulate (Constant-Time Fail-Closed):
        // Unconditionally executes both decapsulation legs (X25519 ECDH + Frodo matrix decap).
        // Error flags are combined bitwise. If decapsulation fails on either primitive,
        // generates a deterministic pseudo-secret from an ephemeral salt, zeroes intermediate
        // secrets with OPENSSL_cleanse, and returns false without leaking which algorithm failed.
        [[nodiscard]] static auto decapsulate_constant_time(
            const HybridCiphertext& ct,
            const HybridPrivateKey& sk,
            const HybridPublicKey& local_pk,
            std::vector<uint8_t>& out_shared_secret
        ) -> bool;

        // CFRG Dual-PRF HKDF Context-Bound Combiner
        // K = HKDF-Extract-and-Expand(Salt, IKM = ss_x25519 || ss_frodo, Info = Context)
        [[nodiscard]] static auto derive_cfrg_combiner(
            const std::vector<uint8_t>& ss_x25519,
            const std::vector<uint8_t>& ss_frodo,
            const HybridPublicKey& pk,
            const HybridCiphertext& ct
        ) -> std::vector<uint8_t>;

    private:
        // Constant-time memory comparison
        [[nodiscard]] static auto constant_time_memcmp(const void* a, const void* b, std::size_t len) -> int;
    };
#else
    // =========================================================================
    // QUARANTINE NOTICE:
    // Hand-written FrodoKEM-976 matrix arithmetic and the legacy X25519 +
    // FrodoKEM hybrid engine are un-audited research prototypes and are
    // quarantined by default.
    //
    // The live production IPC gateway uses MLKem768Engine (native OpenSSL 3.5).
    //
    // To enable quarantined Frodo research structures for offline study only,
    // build with: -DQUANTUMFLEX_ENABLE_LEGACY_FRODO_RESEARCH=ON
    // =========================================================================
#endif // QUANTUMFLEX_ENABLE_LEGACY_FRODO_RESEARCH

} // namespace quantumflex::crypto

#endif // QUANTUM_FLEX_HYBRID_KEM_HPP
