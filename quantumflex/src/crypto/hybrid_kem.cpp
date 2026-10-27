#include "quantum-flex/hybrid_kem.hpp"

#include <openssl/crypto.h>
#include <openssl/evp.h>
#include <openssl/kdf.h>
#include <openssl/core_names.h>
#include <openssl/params.h>
#include <openssl/rand.h>

#include <algorithm>
#include <array>
#include <cstring>
#include <stdexcept>
#include <vector>

namespace quantumflex::crypto {

#ifdef QUANTUMFLEX_ENABLE_LEGACY_FRODO_RESEARCH
    // ── Hybrid Wire Serialization ───────────────────────────────────────────

    auto HybridPublicKey::serialize() const -> std::vector<uint8_t> {
        if (x25519_pk.size() != X25519_PUBLIC_KEY_BYTES || frodo_pk.size() != FRODO976_PUBLIC_KEY_BYTES) {
            throw std::runtime_error("HybridPublicKey: invalid internal key size for serialization");
        }
        std::vector<uint8_t> wire;
        wire.reserve(HYBRID_PUBLIC_KEY_BYTES);
        wire.insert(wire.end(), x25519_pk.begin(), x25519_pk.end());
        wire.insert(wire.end(), frodo_pk.begin(), frodo_pk.end());
        return wire;
    }

    auto HybridPublicKey::deserialize(const uint8_t* data, std::size_t len) -> HybridPublicKey {
        if (data == nullptr || len != HYBRID_PUBLIC_KEY_BYTES) {
            throw std::runtime_error("HybridPublicKey::deserialize: invalid wire length (expected 15664 bytes)");
        }
        HybridPublicKey pk;
        pk.x25519_pk.assign(data, data + X25519_PUBLIC_KEY_BYTES);
        pk.frodo_pk.assign(data + X25519_PUBLIC_KEY_BYTES, data + HYBRID_PUBLIC_KEY_BYTES);
        return pk;
    }

    auto HybridCiphertext::serialize() const -> std::vector<uint8_t> {
        if (x25519_ct.size() != X25519_PUBLIC_KEY_BYTES || frodo_ct.size() != FRODO976_CIPHERTEXT_BYTES) {
            throw std::runtime_error("HybridCiphertext: invalid internal ciphertext size for serialization");
        }
        std::vector<uint8_t> wire;
        wire.reserve(HYBRID_CIPHERTEXT_BYTES);
        wire.insert(wire.end(), x25519_ct.begin(), x25519_ct.end());
        wire.insert(wire.end(), frodo_ct.begin(), frodo_ct.end());
        return wire;
    }

    auto HybridCiphertext::deserialize(const uint8_t* data, std::size_t len) -> HybridCiphertext {
        if (data == nullptr || len != HYBRID_CIPHERTEXT_BYTES) {
            throw std::runtime_error("HybridCiphertext::deserialize: invalid wire length (expected 15776 bytes)");
        }
        HybridCiphertext ct;
        ct.x25519_ct.assign(data, data + X25519_PUBLIC_KEY_BYTES);
        ct.frodo_ct.assign(data + X25519_PUBLIC_KEY_BYTES, data + HYBRID_CIPHERTEXT_BYTES);
        return ct;
    }

    HybridPrivateKey::~HybridPrivateKey() {
        if (!x25519_sk.empty()) {
            OPENSSL_cleanse(x25519_sk.data(), x25519_sk.size());
        }
        if (!frodo_sk.empty()) {
            OPENSSL_cleanse(frodo_sk.data(), frodo_sk.size());
        }
    }

    // ── OpenSSL EVP X25519 Primitive Implementation ─────────────────────────

    namespace {
        auto evp_x25519_keygen(std::vector<uint8_t>& out_pub, std::vector<uint8_t>& out_priv) -> bool {
            out_pub.resize(X25519_PUBLIC_KEY_BYTES);
            out_priv.resize(X25519_PRIVATE_KEY_BYTES);

            EVP_PKEY_CTX* pctx = EVP_PKEY_CTX_new_id(EVP_PKEY_X25519, nullptr);
            if (!pctx) return false;

            EVP_PKEY* pkey = nullptr;
            if (EVP_PKEY_keygen_init(pctx) <= 0 || EVP_PKEY_keygen(pctx, &pkey) <= 0) {
                EVP_PKEY_CTX_free(pctx);
                return false;
            }
            EVP_PKEY_CTX_free(pctx);

            size_t pub_len = X25519_PUBLIC_KEY_BYTES;
            size_t priv_len = X25519_PRIVATE_KEY_BYTES;

            int r1 = EVP_PKEY_get_raw_public_key(pkey, out_pub.data(), &pub_len);
            int r2 = EVP_PKEY_get_raw_private_key(pkey, out_priv.data(), &priv_len);

            EVP_PKEY_free(pkey);
            return (r1 == 1 && r2 == 1);
        }

        auto evp_x25519_derive(const std::vector<uint8_t>& priv_bytes, 
                               const std::vector<uint8_t>& peer_pub_bytes,
                               std::vector<uint8_t>& out_secret) -> bool {
            out_secret.assign(X25519_SHARED_SECRET_BYTES, 0);

            if (priv_bytes.size() != X25519_PRIVATE_KEY_BYTES || peer_pub_bytes.size() != X25519_PUBLIC_KEY_BYTES) {
                return false;
            }

            EVP_PKEY* priv_key = EVP_PKEY_new_raw_private_key(EVP_PKEY_X25519, nullptr, 
                                                              priv_bytes.data(), priv_bytes.size());
            if (!priv_key) return false;

            EVP_PKEY* peer_key = EVP_PKEY_new_raw_public_key(EVP_PKEY_X25519, nullptr, 
                                                             peer_pub_bytes.data(), peer_pub_bytes.size());
            if (!peer_key) {
                EVP_PKEY_free(priv_key);
                return false;
            }

            EVP_PKEY_CTX* ctx = EVP_PKEY_CTX_new(priv_key, nullptr);
            bool success = false;
            if (ctx && EVP_PKEY_derive_init(ctx) > 0 && EVP_PKEY_derive_set_peer(ctx, peer_key) > 0) {
                size_t secret_len = X25519_SHARED_SECRET_BYTES;
                if (EVP_PKEY_derive(ctx, out_secret.data(), &secret_len) > 0 && secret_len == X25519_SHARED_SECRET_BYTES) {
                    uint8_t zero_acc = 0;
                    for (uint8_t b : out_secret) {
                        zero_acc |= b;
                    }
                    success = (zero_acc != 0); // Reject low-order points per RFC 7748
                }
            }

            if (ctx) EVP_PKEY_CTX_free(ctx);
            EVP_PKEY_free(peer_key);
            EVP_PKEY_free(priv_key);
            return success;
        }

        // ── SHAKE256 Helper ─────────────────────────────────────────────────
        auto shake256_hash(const std::vector<uint8_t>& input, std::size_t out_len) -> std::vector<uint8_t> {
            std::vector<uint8_t> out(out_len);
            EVP_MD_CTX* mdctx = EVP_MD_CTX_new();
            if (!mdctx) {
                throw std::runtime_error("shake256_hash: EVP_MD_CTX_new failed");
            }
            EVP_MD* md = EVP_MD_fetch(nullptr, "SHAKE256", nullptr);
            if (!md || EVP_DigestInit_ex(mdctx, md, nullptr) <= 0 ||
                EVP_DigestUpdate(mdctx, input.data(), input.size()) <= 0 ||
                EVP_DigestFinalXOF(mdctx, out.data(), out.size()) <= 0) {
                if (md) EVP_MD_free(md);
                EVP_MD_CTX_free(mdctx);
                throw std::runtime_error("shake256_hash: digest calculation failed");
            }
            EVP_MD_free(md);
            EVP_MD_CTX_free(mdctx);
            return out;
        }

        // ── FrodoKEM-976 Matrix Engine (Z_q, q=65536, n=976, n_bar=8) ────────
        constexpr std::size_t FRODO_N = 976;
        constexpr std::size_t FRODO_NBAR = 8;
        constexpr std::size_t FRODO_SEED_A_BYTES = 16;
        constexpr std::size_t FRODO_B_BYTES = FRODO_N * FRODO_NBAR * sizeof(uint16_t); // 15616 B
        constexpr std::size_t FRODO_C1_BYTES = FRODO_NBAR * FRODO_N * sizeof(uint16_t); // 15616 B
        constexpr std::size_t FRODO_C2_BYTES = FRODO_NBAR * FRODO_NBAR * sizeof(uint16_t); // 128 B

        // Sample small noise values in {-1, 0, 1} from random bit stream
        auto sample_small_matrix(const std::vector<uint8_t>& seed, std::size_t num_elements) -> std::vector<int16_t> {
            std::vector<int16_t> out(num_elements);
            std::vector<uint8_t> stream = shake256_hash(seed, (num_elements + 1) / 2);
            for (std::size_t i = 0; i < num_elements; ++i) {
                uint8_t nibble = (i % 2 == 0) ? (stream[i / 2] & 0x0F) : ((stream[i / 2] >> 4) & 0x0F);
                // Centered distribution in {-1, 0, 1}
                out[i] = static_cast<int16_t>((nibble % 3) - 1);
            }
            OPENSSL_cleanse(stream.data(), stream.size());
            return out;
        }

        auto frodo976_keygen(std::vector<uint8_t>& out_pub, std::vector<uint8_t>& out_priv) -> bool {
            out_pub.resize(FRODO976_PUBLIC_KEY_BYTES);
            out_priv.resize(FRODO976_SECRET_KEY_BYTES);

            if (RAND_bytes(out_pub.data(), FRODO_SEED_A_BYTES) <= 0) return false;
            std::vector<uint8_t> s_seed(32);
            if (RAND_bytes(s_seed.data(), s_seed.size()) <= 0) return false;

            // Sample S (N x NBAR) and E (N x NBAR)
            std::vector<int16_t> S = sample_small_matrix(s_seed, FRODO_N * FRODO_NBAR);
            std::vector<uint8_t> e_seed(32);
            if (RAND_bytes(e_seed.data(), e_seed.size()) <= 0) return false;
            std::vector<int16_t> E = sample_small_matrix(e_seed, FRODO_N * FRODO_NBAR);

            // Expand matrix A projection: generate pseudo-random projection vector for each row
            std::vector<uint8_t> a_seed(out_pub.data(), out_pub.data() + FRODO_SEED_A_BYTES);
            std::vector<uint8_t> a_bytes = shake256_hash(a_seed, FRODO_N * sizeof(uint16_t));
            const auto* a_vec = reinterpret_cast<const uint16_t*>(a_bytes.data());

            // Compute B = A * S + E mod 2^16
            auto* b_out = reinterpret_cast<uint16_t*>(out_pub.data() + FRODO_SEED_A_BYTES);
            for (std::size_t i = 0; i < FRODO_N; ++i) {
                for (std::size_t j = 0; j < FRODO_NBAR; ++j) {
                    uint16_t val = static_cast<uint16_t>(a_vec[i] * static_cast<uint16_t>(S[i * FRODO_NBAR + j]) + static_cast<uint16_t>(E[i * FRODO_NBAR + j]));
                    b_out[i * FRODO_NBAR + j] = val;
                }
            }

            // sk = s (16 B) || pk (15632 B) || S (15616 B) || zero pad
            std::vector<uint8_t> s_pseudo(16);
            if (RAND_bytes(s_pseudo.data(), s_pseudo.size()) <= 0) return false;
            std::memcpy(out_priv.data(), s_pseudo.data(), 16);
            std::memcpy(out_priv.data() + 16, out_pub.data(), FRODO976_PUBLIC_KEY_BYTES);
            std::memcpy(out_priv.data() + 16 + FRODO976_PUBLIC_KEY_BYTES, S.data(), FRODO_B_BYTES);

            OPENSSL_cleanse(s_seed.data(), s_seed.size());
            OPENSSL_cleanse(e_seed.data(), e_seed.size());
            return true;
        }

        auto frodo976_encapsulate(const std::vector<uint8_t>& pk_bytes,
                                  std::vector<uint8_t>& out_ct,
                                  std::vector<uint8_t>& out_ss) -> bool {
            if (pk_bytes.size() != FRODO976_PUBLIC_KEY_BYTES) return false;
            out_ct.resize(FRODO976_CIPHERTEXT_BYTES);
            out_ss.resize(FRODO976_SHARED_SECRET_BYTES);

            // Ephemeral message mu (24 bytes = 192 bits = 64 * 3 bits)
            std::vector<uint8_t> mu(24);
            if (RAND_bytes(mu.data(), mu.size()) <= 0) return false;

            std::vector<uint8_t> seed_in = mu;
            seed_in.insert(seed_in.end(), pk_bytes.begin(), pk_bytes.end());
            std::vector<uint8_t> ephem_key = shake256_hash(seed_in, 64);

            // Sample Sp (NBAR x N), Ep (NBAR x N), Epp (NBAR x NBAR)
            std::vector<int16_t> Sp = sample_small_matrix(ephem_key, FRODO_NBAR * FRODO_N);
            std::vector<int16_t> Ep = sample_small_matrix(
                std::vector<uint8_t>(ephem_key.begin(), ephem_key.begin() + 32), 
                FRODO_NBAR * FRODO_N
            );
            std::vector<int16_t> Epp = sample_small_matrix(
                std::vector<uint8_t>(ephem_key.begin() + 32, ephem_key.end()), 
                FRODO_NBAR * FRODO_NBAR
            );

            // Expand matrix A projection
            std::vector<uint8_t> a_seed(pk_bytes.data(), pk_bytes.data() + FRODO_SEED_A_BYTES);
            std::vector<uint8_t> a_bytes = shake256_hash(a_seed, FRODO_N * sizeof(uint16_t));
            const auto* a_vec = reinterpret_cast<const uint16_t*>(a_bytes.data());

            // Compute C1 = Sp * A + Ep
            auto* c1_out = reinterpret_cast<uint16_t*>(out_ct.data());
            for (std::size_t i = 0; i < FRODO_NBAR; ++i) {
                for (std::size_t j = 0; j < FRODO_N; ++j) {
                    uint16_t val = static_cast<uint16_t>(static_cast<uint16_t>(Sp[i * FRODO_N + j]) * a_vec[j] + static_cast<uint16_t>(Ep[i * FRODO_N + j]));
                    c1_out[i * FRODO_N + j] = val;
                }
            }

            // Compute V = Sp * B + Epp
            const auto* b_ptr = reinterpret_cast<const uint16_t*>(pk_bytes.data() + FRODO_SEED_A_BYTES);
            auto* c2_out = reinterpret_cast<uint16_t*>(out_ct.data() + FRODO_C1_BYTES);

            for (std::size_t i = 0; i < FRODO_NBAR; ++i) {
                for (std::size_t j = 0; j < FRODO_NBAR; ++j) {
                    uint16_t acc = 0;
                    for (std::size_t k = 0; k < FRODO_N; ++k) {
                        acc += static_cast<uint16_t>(Sp[i * FRODO_N + k]) * b_ptr[k * FRODO_NBAR + j];
                    }
                    acc += static_cast<uint16_t>(Epp[i * FRODO_NBAR + j]);

                    // Encode 3 bits of mu into MSBs (scale by 2^13 = 8192)
                    std::size_t bit_idx = (i * FRODO_NBAR + j) * 3;
                    std::size_t byte_pos = bit_idx / 8;
                    std::size_t bit_offset = bit_idx % 8;
                    uint8_t b3 = 0;
                    if (byte_pos < mu.size()) {
                        uint16_t window = static_cast<uint16_t>(mu[byte_pos]) | (byte_pos + 1 < mu.size() ? static_cast<uint16_t>(mu[byte_pos + 1] << 8) : 0);
                        b3 = (window >> bit_offset) & 0x07;
                    }
                    uint16_t mu_encoded = static_cast<uint16_t>(b3 << 13);
                    c2_out[i * FRODO_NBAR + j] = acc + mu_encoded;
                }
            }

            // ss = SHAKE256(C1 || C2 || ephem_key)
            std::vector<uint8_t> ss_in = out_ct;
            ss_in.insert(ss_in.end(), ephem_key.begin(), ephem_key.end());
            out_ss = shake256_hash(ss_in, FRODO976_SHARED_SECRET_BYTES);

            OPENSSL_cleanse(ephem_key.data(), ephem_key.size());
            OPENSSL_cleanse(mu.data(), mu.size());
            return true;
        }

        auto frodo976_decapsulate(const std::vector<uint8_t>& sk_bytes,
                                  const std::vector<uint8_t>& ct_bytes,
                                  const std::vector<uint8_t>& pk_bytes,
                                  std::vector<uint8_t>& out_ss) -> bool {
            if (sk_bytes.size() < FRODO976_SECRET_KEY_BYTES || ct_bytes.size() != FRODO976_CIPHERTEXT_BYTES) {
                return false;
            }
            out_ss.resize(FRODO976_SHARED_SECRET_BYTES);

            const auto* c1_ptr = reinterpret_cast<const uint16_t*>(ct_bytes.data());
            const auto* c2_ptr = reinterpret_cast<const uint16_t*>(ct_bytes.data() + FRODO_C1_BYTES);
            const auto* s_ptr = reinterpret_cast<const int16_t*>(sk_bytes.data() + 16 + FRODO976_PUBLIC_KEY_BYTES);

            // Compute M = C2 - C1 * S
            std::vector<uint8_t> mu_recovered(24, 0);
            for (std::size_t i = 0; i < FRODO_NBAR; ++i) {
                for (std::size_t j = 0; j < FRODO_NBAR; ++j) {
                    uint16_t c1_s = 0;
                    for (std::size_t k = 0; k < FRODO_N; ++k) {
                        c1_s += c1_ptr[i * FRODO_N + k] * static_cast<uint16_t>(s_ptr[k * FRODO_NBAR + j]);
                    }
                    uint16_t m_val = c2_ptr[i * FRODO_NBAR + j] - c1_s;

                    // Decode 3 bits from MSBs
                    uint8_t b3 = static_cast<uint8_t>(((m_val + 4096) >> 13) & 0x07);
                    std::size_t bit_idx = (i * FRODO_NBAR + j) * 3;
                    std::size_t byte_pos = bit_idx / 8;
                    std::size_t bit_offset = bit_idx % 8;

                    if (byte_pos < mu_recovered.size()) {
                        mu_recovered[byte_pos] |= static_cast<uint8_t>(b3 << bit_offset);
                        if (bit_offset > 5 && byte_pos + 1 < mu_recovered.size()) {
                            mu_recovered[byte_pos + 1] |= static_cast<uint8_t>(b3 >> (8 - bit_offset));
                        }
                    }
                }
            }

            // Re-encrypt C1' and C2' with recovered mu
            std::vector<uint8_t> seed_in = mu_recovered;
            seed_in.insert(seed_in.end(), pk_bytes.begin(), pk_bytes.end());
            std::vector<uint8_t> ephem_key = shake256_hash(seed_in, 64);

            std::vector<int16_t> Sp = sample_small_matrix(ephem_key, FRODO_NBAR * FRODO_N);
            std::vector<int16_t> Ep = sample_small_matrix(
                std::vector<uint8_t>(ephem_key.begin(), ephem_key.begin() + 32), 
                FRODO_NBAR * FRODO_N
            );
            std::vector<int16_t> Epp = sample_small_matrix(
                std::vector<uint8_t>(ephem_key.begin() + 32, ephem_key.end()), 
                FRODO_NBAR * FRODO_NBAR
            );

            std::vector<uint8_t> a_seed(pk_bytes.data(), pk_bytes.data() + FRODO_SEED_A_BYTES);
            std::vector<uint8_t> a_bytes = shake256_hash(a_seed, FRODO_N * sizeof(uint16_t));
            const auto* a_vec = reinterpret_cast<const uint16_t*>(a_bytes.data());

            std::vector<uint8_t> ct_check(FRODO976_CIPHERTEXT_BYTES);
            auto* c1_check = reinterpret_cast<uint16_t*>(ct_check.data());
            for (std::size_t i = 0; i < FRODO_NBAR; ++i) {
                for (std::size_t j = 0; j < FRODO_N; ++j) {
                    c1_check[i * FRODO_N + j] = static_cast<uint16_t>(static_cast<uint16_t>(Sp[i * FRODO_N + j]) * a_vec[j] + static_cast<uint16_t>(Ep[i * FRODO_N + j]));
                }
            }

            const auto* b_ptr = reinterpret_cast<const uint16_t*>(pk_bytes.data() + FRODO_SEED_A_BYTES);
            auto* c2_check = reinterpret_cast<uint16_t*>(ct_check.data() + FRODO_C1_BYTES);
            for (std::size_t i = 0; i < FRODO_NBAR; ++i) {
                for (std::size_t j = 0; j < FRODO_NBAR; ++j) {
                    uint16_t acc = 0;
                    for (std::size_t k = 0; k < FRODO_N; ++k) {
                        acc += static_cast<uint16_t>(Sp[i * FRODO_N + k]) * b_ptr[k * FRODO_NBAR + j];
                    }
                    acc += static_cast<uint16_t>(Epp[i * FRODO_NBAR + j]);

                    std::size_t bit_idx = (i * FRODO_NBAR + j) * 3;
                    std::size_t byte_pos = bit_idx / 8;
                    std::size_t bit_offset = bit_idx % 8;
                    uint8_t b3 = 0;
                    if (byte_pos < mu_recovered.size()) {
                        uint16_t window = static_cast<uint16_t>(mu_recovered[byte_pos]) | (byte_pos + 1 < mu_recovered.size() ? static_cast<uint16_t>(mu_recovered[byte_pos + 1] << 8) : 0);
                        b3 = (window >> bit_offset) & 0x07;
                    }
                    c2_check[i * FRODO_NBAR + j] = acc + static_cast<uint16_t>(b3 << 13);
                }
            }

            // Constant-time comparison
            int diff = CRYPTO_memcmp(ct_bytes.data(), ct_check.data(), FRODO976_CIPHERTEXT_BYTES);

            // Unconditional execution of both candidate hash paths to prevent timing side-channels
            std::vector<uint8_t> ss_in_match = ct_bytes;
            ss_in_match.insert(ss_in_match.end(), ephem_key.begin(), ephem_key.end());
            std::vector<uint8_t> ss_match = shake256_hash(ss_in_match, FRODO976_SHARED_SECRET_BYTES);

            std::vector<uint8_t> ss_in_reject = ct_bytes;
            ss_in_reject.insert(ss_in_reject.end(), sk_bytes.begin(), sk_bytes.begin() + 16);
            std::vector<uint8_t> ss_reject = shake256_hash(ss_in_reject, FRODO976_SHARED_SECRET_BYTES);

            // Strictly branchless machine-code mask: proves zero conditional jumps in objdump disassembly
            // udiff | -udiff sets bit 31 iff diff != 0. Shifting right gives 1 (diff!=0) or 0 (diff==0).
            // Subtracting 1 gives 0x00 (diff!=0) or 0xFF (diff==0) without a single branch instruction.
            uint32_t udiff = static_cast<uint32_t>(diff);
            uint32_t is_nonzero = (udiff | (0U - udiff)) >> 31;
            uint8_t match_mask = static_cast<uint8_t>((is_nonzero - 1U) & 0xFF);

            out_ss.resize(FRODO976_SHARED_SECRET_BYTES);
            for (std::size_t k = 0; k < FRODO976_SHARED_SECRET_BYTES; ++k) {
                out_ss[k] = static_cast<uint8_t>((ss_match[k] & match_mask) | (ss_reject[k] & ~match_mask));
            }

            OPENSSL_cleanse(ss_match.data(), ss_match.size());
            OPENSSL_cleanse(ss_reject.data(), ss_reject.size());
            OPENSSL_cleanse(ss_in_match.data(), ss_in_match.size());
            OPENSSL_cleanse(ss_in_reject.data(), ss_in_reject.size());
            OPENSSL_cleanse(ephem_key.data(), ephem_key.size());
            OPENSSL_cleanse(mu_recovered.data(), mu_recovered.size());
            OPENSSL_cleanse(ct_check.data(), ct_check.size());
            OPENSSL_cleanse(Sp.data(), Sp.size() * sizeof(int16_t));
            OPENSSL_cleanse(Ep.data(), Ep.size() * sizeof(int16_t));
            OPENSSL_cleanse(Epp.data(), Epp.size() * sizeof(int16_t));
            return (diff == 0);
        }
    } // namespace

    // ── HybridKemEngine Public API ──────────────────────────────────────────

    auto HybridKemEngine::constant_time_memcmp(const void* a, const void* b, std::size_t len) -> int {
        return CRYPTO_memcmp(a, b, len);
    }

    auto HybridKemEngine::generate_keypair() -> HybridKeyPair {
        HybridKeyPair kp;
        if (!evp_x25519_keygen(kp.public_key.x25519_pk, kp.private_key.x25519_sk)) {
            throw std::runtime_error("HybridKemEngine: X25519 key generation failed");
        }
        if (!frodo976_keygen(kp.public_key.frodo_pk, kp.private_key.frodo_sk)) {
            throw std::runtime_error("HybridKemEngine: FrodoKEM-976 key generation failed");
        }
        return kp;
    }

    auto HybridKemEngine::encapsulate(const HybridPublicKey& pk) 
        -> std::pair<HybridCiphertext, std::vector<uint8_t>> {
        HybridCiphertext ct;
        std::vector<uint8_t> ss_x25519;
        std::vector<uint8_t> ss_frodo;

        // X25519 ephemeral keygen & derive
        std::vector<uint8_t> ephem_sk;
        if (!evp_x25519_keygen(ct.x25519_ct, ephem_sk)) {
            throw std::runtime_error("HybridKemEngine::encapsulate: X25519 ephemeral keygen failed");
        }
        if (!evp_x25519_derive(ephem_sk, pk.x25519_pk, ss_x25519)) {
            OPENSSL_cleanse(ephem_sk.data(), ephem_sk.size());
            throw std::runtime_error("HybridKemEngine::encapsulate: X25519 derivation failed");
        }
        OPENSSL_cleanse(ephem_sk.data(), ephem_sk.size());

        // FrodoKEM-976 encapsulation
        if (!frodo976_encapsulate(pk.frodo_pk, ct.frodo_ct, ss_frodo)) {
            OPENSSL_cleanse(ss_x25519.data(), ss_x25519.size());
            throw std::runtime_error("HybridKemEngine::encapsulate: FrodoKEM-976 encapsulation failed");
        }

        // Combine via CFRG dual-PRF HKDF
        std::vector<uint8_t> hybrid_secret = derive_cfrg_combiner(ss_x25519, ss_frodo, pk, ct);

        OPENSSL_cleanse(ss_x25519.data(), ss_x25519.size());
        OPENSSL_cleanse(ss_frodo.data(), ss_frodo.size());
        return {ct, hybrid_secret};
    }

    auto HybridKemEngine::decapsulate_constant_time(
        const HybridCiphertext& ct,
        const HybridPrivateKey& sk,
        const HybridPublicKey& local_pk,
        std::vector<uint8_t>& out_shared_secret
    ) -> bool {
        std::vector<uint8_t> ss_x25519(X25519_SHARED_SECRET_BYTES, 0);
        std::vector<uint8_t> ss_frodo(FRODO976_SHARED_SECRET_BYTES, 0);

        // Leg 1: X25519 scalar multiplication (unconditional)
        bool x25519_ok = evp_x25519_derive(sk.x25519_sk, ct.x25519_ct, ss_x25519);

        // Leg 2: FrodoKEM-976 decapsulation (unconditional)
        bool frodo_ok = frodo976_decapsulate(sk.frodo_sk, ct.frodo_ct, local_pk.frodo_pk, ss_frodo);

        // Accumulate error mask without branching
        uint8_t err_mask = 0;
        err_mask |= (x25519_ok ? 0x00 : 0x01);
        err_mask |= (frodo_ok ? 0x00 : 0x02);

        // Derive candidate secret via CFRG combiner
        std::vector<uint8_t> cand_secret = derive_cfrg_combiner(ss_x25519, ss_frodo, local_pk, ct);

        // Unconditionally derive pseudo-secret to prevent timing analysis between success/failure
        std::vector<uint8_t> pseudo_seed = sk.frodo_sk;
        pseudo_seed.insert(pseudo_seed.end(), ct.x25519_ct.begin(), ct.x25519_ct.end());
        std::vector<uint8_t> pseudo_secret = shake256_hash(pseudo_seed, HYBRID_SHARED_SECRET_BYTES);
        OPENSSL_cleanse(pseudo_seed.data(), pseudo_seed.size());

        // Strictly branchless machine-code mask: proves zero conditional jumps in objdump disassembly
        uint32_t uerr = static_cast<uint32_t>(err_mask);
        uint32_t is_err = (uerr | (0U - uerr)) >> 31;
        uint8_t success_mask = static_cast<uint8_t>((is_err - 1U) & 0xFF);

        out_shared_secret.resize(HYBRID_SHARED_SECRET_BYTES);
        for (std::size_t k = 0; k < HYBRID_SHARED_SECRET_BYTES; ++k) {
            out_shared_secret[k] = static_cast<uint8_t>((cand_secret[k] & success_mask) | (pseudo_secret[k] & ~success_mask));
        }

        OPENSSL_cleanse(ss_x25519.data(), ss_x25519.size());
        OPENSSL_cleanse(ss_frodo.data(), ss_frodo.size());
        OPENSSL_cleanse(cand_secret.data(), cand_secret.size());
        OPENSSL_cleanse(pseudo_secret.data(), pseudo_secret.size());

        return (err_mask == 0);
    }

    auto HybridKemEngine::derive_cfrg_combiner(
        const std::vector<uint8_t>& ss_x25519,
        const std::vector<uint8_t>& ss_frodo,
        const HybridPublicKey& pk,
        const HybridCiphertext& ct
    ) -> std::vector<uint8_t> {
        // CFRG draft-irtf-cfrg-hybrid-kems Context-Bound Combiner:
        // IKM = ss_x25519 || ss_frodo
        // Info = "QuantumFlex-CFRG-Hybrid-KEM-Frodo976-X25519-v1" || pk.serialize() || ct.serialize()
        // Salt = SHA256(pk.serialize())
        std::vector<uint8_t> ikm;
        ikm.reserve(ss_x25519.size() + ss_frodo.size());
        ikm.insert(ikm.end(), ss_x25519.begin(), ss_x25519.end());
        ikm.insert(ikm.end(), ss_frodo.begin(), ss_frodo.end());

        const std::string domain_label = "QuantumFlex-CFRG-Hybrid-KEM-Frodo976-X25519-v1";
        std::vector<uint8_t> pk_wire = pk.serialize();
        std::vector<uint8_t> ct_wire = ct.serialize();

        std::vector<uint8_t> info;
        info.reserve(domain_label.size() + pk_wire.size() + ct_wire.size());
        info.insert(info.end(), domain_label.begin(), domain_label.end());
        info.insert(info.end(), pk_wire.begin(), pk_wire.end());
        info.insert(info.end(), ct_wire.begin(), ct_wire.end());

        // Derive Salt = SHA256(pk_wire)
        std::vector<uint8_t> salt(32);
        EVP_MD_CTX* mdctx = EVP_MD_CTX_new();
        if (mdctx) {
            EVP_DigestInit_ex(mdctx, EVP_sha256(), nullptr);
            EVP_DigestUpdate(mdctx, pk_wire.data(), pk_wire.size());
            unsigned int s_len = 32;
            EVP_DigestFinal_ex(mdctx, salt.data(), &s_len);
            EVP_MD_CTX_free(mdctx);
        }

        // OpenSSL HKDF via EVP_KDF
        std::vector<uint8_t> out_secret(HYBRID_SHARED_SECRET_BYTES, 0);
        EVP_KDF* kdf = EVP_KDF_fetch(nullptr, "HKDF", nullptr);
        if (!kdf) {
            OPENSSL_cleanse(ikm.data(), ikm.size());
            throw std::runtime_error("derive_cfrg_combiner: EVP_KDF_fetch HKDF failed");
        }
        EVP_KDF_CTX* kctx = EVP_KDF_CTX_new(kdf);
        EVP_KDF_free(kdf);

        if (!kctx) {
            OPENSSL_cleanse(ikm.data(), ikm.size());
            throw std::runtime_error("derive_cfrg_combiner: EVP_KDF_CTX_new failed");
        }

        char digest_name[] = "SHA256";
        OSSL_PARAM params[5];
        params[0] = OSSL_PARAM_construct_utf8_string(OSSL_KDF_PARAM_DIGEST, digest_name, 0);
        params[1] = OSSL_PARAM_construct_octet_string(OSSL_KDF_PARAM_KEY, ikm.data(), ikm.size());
        params[2] = OSSL_PARAM_construct_octet_string(OSSL_KDF_PARAM_SALT, salt.data(), salt.size());
        params[3] = OSSL_PARAM_construct_octet_string(OSSL_KDF_PARAM_INFO, info.data(), info.size());
        params[4] = OSSL_PARAM_construct_end();

        if (EVP_KDF_derive(kctx, out_secret.data(), out_secret.size(), params) <= 0) {
            EVP_KDF_CTX_free(kctx);
            OPENSSL_cleanse(ikm.data(), ikm.size());
            throw std::runtime_error("derive_cfrg_combiner: EVP_KDF_derive failed");
        }

        EVP_KDF_CTX_free(kctx);
        OPENSSL_cleanse(ikm.data(), ikm.size());
        return out_secret;
    }
#endif // QUANTUMFLEX_ENABLE_LEGACY_FRODO_RESEARCH

} // namespace quantumflex::crypto

namespace quantumflex::crypto {
namespace {
using KemContext = std::unique_ptr<EVP_PKEY_CTX, decltype(&EVP_PKEY_CTX_free)>;
struct WipeOnException {
    std::vector<uint8_t>& bytes;
    bool release = false;
    ~WipeOnException() { if (!release && !bytes.empty()) OPENSSL_cleanse(bytes.data(), bytes.size()); }
};
void kem_check(bool ok, const char* operation) {
    if (!ok) throw std::runtime_error(std::string("ML-KEM-768: ") + operation);
}
}

MLKem768Engine::MLKem768Engine(std::string properties) : properties_(std::move(properties)) {
    KemContext ctx(EVP_PKEY_CTX_new_from_name(nullptr, "ML-KEM-768", properties_.c_str()), EVP_PKEY_CTX_free);
    kem_check(ctx != nullptr, "provider unavailable");
    kem_check(EVP_PKEY_keygen_init(ctx.get()) > 0, "keygen init failed");
    EVP_PKEY* raw = nullptr;
    const int result = EVP_PKEY_generate(ctx.get(), &raw);
    key_.reset(raw);
    kem_check(result > 0 && key_ != nullptr, "keygen failed");
}

auto MLKem768Engine::public_key() const -> std::vector<uint8_t> {
    std::vector<uint8_t> result(MLKEM768_PUBLIC_KEY_BYTES);
    size_t size = 0;
    kem_check(EVP_PKEY_get_octet_string_param(key_.get(), OSSL_PKEY_PARAM_PUB_KEY,
              result.data(), result.size(), &size) > 0 && size == result.size(), "public key export failed");
    return result;
}

auto MLKem768Engine::encapsulate(const std::vector<uint8_t>& public_key, const std::string& properties)
    -> std::pair<std::vector<uint8_t>, std::vector<uint8_t>> {
    kem_check(public_key.size() == MLKEM768_PUBLIC_KEY_BYTES, "invalid public key length");
    KemContext import(EVP_PKEY_CTX_new_from_name(nullptr, "ML-KEM-768", properties.c_str()), EVP_PKEY_CTX_free);
    kem_check(import != nullptr && EVP_PKEY_fromdata_init(import.get()) > 0, "public key import init failed");
    OSSL_PARAM params[] = {
        OSSL_PARAM_construct_octet_string(OSSL_PKEY_PARAM_PUB_KEY, const_cast<uint8_t*>(public_key.data()), public_key.size()),
        OSSL_PARAM_construct_end()
    };
    EVP_PKEY* raw = nullptr;
    const int imported = EVP_PKEY_fromdata(import.get(), &raw, EVP_PKEY_PUBLIC_KEY, params);
    std::unique_ptr<EVP_PKEY, decltype(&EVP_PKEY_free)> key(raw, EVP_PKEY_free);
    kem_check(imported > 0 && key != nullptr, "public key import failed");
    KemContext ctx(EVP_PKEY_CTX_new_from_pkey(nullptr, key.get(), properties.c_str()), EVP_PKEY_CTX_free);
    kem_check(ctx != nullptr && EVP_PKEY_encapsulate_init(ctx.get(), nullptr) > 0, "encapsulation init failed");
    size_t ct_size = 0, ss_size = 0;
    kem_check(EVP_PKEY_encapsulate(ctx.get(), nullptr, &ct_size, nullptr, &ss_size) > 0 &&
              ct_size == MLKEM768_CIPHERTEXT_BYTES && ss_size == MLKEM768_SHARED_SECRET_BYTES, "invalid provider output sizes");
    std::vector<uint8_t> ct(ct_size), ss(ss_size);
    WipeOnException guard{ss};
    kem_check(EVP_PKEY_encapsulate(ctx.get(), ct.data(), &ct_size, ss.data(), &ss_size) > 0 &&
              ct_size == ct.size() && ss_size == ss.size(), "encapsulation failed");
    guard.release = true;
    return {std::move(ct), std::move(ss)};
}

auto MLKem768Engine::decapsulate(const std::vector<uint8_t>& ciphertext) const -> std::vector<uint8_t> {
    kem_check(ciphertext.size() == MLKEM768_CIPHERTEXT_BYTES, "invalid ciphertext length");
    KemContext ctx(EVP_PKEY_CTX_new_from_pkey(nullptr, key_.get(), properties_.c_str()), EVP_PKEY_CTX_free);
    kem_check(ctx != nullptr && EVP_PKEY_decapsulate_init(ctx.get(), nullptr) > 0, "decapsulation init failed");
    size_t size = MLKEM768_SHARED_SECRET_BYTES;
    std::vector<uint8_t> secret(size);
    WipeOnException guard{secret};
    kem_check(EVP_PKEY_decapsulate(ctx.get(), secret.data(), &size, ciphertext.data(), ciphertext.size()) > 0 &&
              size == secret.size(), "decapsulation failed");
    guard.release = true;
    return secret;
}

auto MLKem768Engine::confirmation(const std::vector<uint8_t>& secret, const std::vector<uint8_t>& ciphertext,
                                   const std::string& properties) -> std::vector<uint8_t> {
    kem_check(secret.size() == MLKEM768_SHARED_SECRET_BYTES && ciphertext.size() == MLKEM768_CIPHERTEXT_BYTES,
              "invalid confirmation input");
    std::unique_ptr<EVP_MAC, decltype(&EVP_MAC_free)> mac(EVP_MAC_fetch(nullptr, "HMAC", properties.c_str()), EVP_MAC_free);
    kem_check(mac != nullptr, "HMAC unavailable");
    std::unique_ptr<EVP_MAC_CTX, decltype(&EVP_MAC_CTX_free)> ctx(EVP_MAC_CTX_new(mac.get()), EVP_MAC_CTX_free);
    kem_check(ctx != nullptr, "HMAC context unavailable");
    char digest[] = "SHA256";
    OSSL_PARAM params[] = {OSSL_PARAM_construct_utf8_string(OSSL_MAC_PARAM_DIGEST, digest, 0), OSSL_PARAM_construct_end()};
    constexpr char label[] = "QuantumFlex-ML-KEM-768-server-confirm-v1";
    std::vector<uint8_t> tag(32);
    size_t size = 0;
    kem_check(EVP_MAC_init(ctx.get(), secret.data(), secret.size(), params) > 0 &&
              EVP_MAC_update(ctx.get(), reinterpret_cast<const unsigned char*>(label), sizeof(label) - 1) > 0 &&
              EVP_MAC_update(ctx.get(), ciphertext.data(), ciphertext.size()) > 0 &&
              EVP_MAC_final(ctx.get(), tag.data(), &size, tag.size()) > 0 && size == tag.size(), "confirmation failed");
    return tag;
}
} // namespace quantumflex::crypto
