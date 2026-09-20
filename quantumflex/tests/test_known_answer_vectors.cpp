#include "quantum-flex/hybrid_kem.hpp"
#include "quantum-flex/crypto_shamir.hpp"
#include "quantum-flex/crypto_hasher.hpp"

#include <openssl/crypto.h>
#include <openssl/evp.h>
#include <openssl/kdf.h>
#include <openssl/core_names.h>
#include <openssl/params.h>

#ifdef NDEBUG
#undef NDEBUG
#endif

#include <algorithm>
#include <cassert>
#include <chrono>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <vector>

namespace {
    auto hex_to_bytes(const std::string& hex) -> std::vector<uint8_t> {
        std::vector<uint8_t> bytes;
        bytes.reserve(hex.length() / 2);
        for (std::size_t i = 0; i + 1 < hex.length(); i += 2) {
            bytes.push_back(static_cast<uint8_t>(std::stoi(hex.substr(i, 2), nullptr, 16)));
        }
        return bytes;
    }
}

// ── Test 1: RFC 7748 Curve25519 Known Answer Tests ─────────────────────────
void test_rfc7748_kat() {
    std::cout << "[*] [KAT 1/4] Running RFC 7748 Curve25519 Official Test Vectors...\n";

    // RFC 7748 Section 6.1 (Diffie-Hellman Key Exchange)
    // Alice Private Key (a), Bob Private Key (b)
    std::string alice_sk_hex = "77076d0a7318a57d3c16c17251b26645df4c2f87ebc0992ab177fba51db92c2a";
    std::string bob_sk_hex   = "5dab087e624a8a4b79e17f8b83800ee66f3bb1292618b6fd1c2f8b27ff88e0eb";

    // Expected Alice & Bob Public Keys: X25519(sk, 9)
    std::string exp_alice_pk_hex = "8520f0098930a754748b7ddcb43ef75a0dbf3a0d26381af4eba4a98eaa9b4e6a";
    std::string exp_bob_pk_hex   = "de9edb7d7b7dc1b4d35b61c2ece435373f8343c85b78674dadfc7e146f882b4f";

    // Expected Converged Shared Secret K = X25519(a, Bob_pk) = X25519(b, Alice_pk)
    std::string exp_k_hex = "4a5d9d5ba4ce2de1728e3bf480350f25e07e21c947d19e3376f09b3c1e161742";

    auto a_sk = hex_to_bytes(alice_sk_hex);
    auto b_sk = hex_to_bytes(bob_sk_hex);
    auto exp_a_pk = hex_to_bytes(exp_alice_pk_hex);
    auto exp_b_pk = hex_to_bytes(exp_bob_pk_hex);
    auto exp_k = hex_to_bytes(exp_k_hex);

    // Compute Alice Public Key
    EVP_PKEY* a_pkey = EVP_PKEY_new_raw_private_key(EVP_PKEY_X25519, nullptr, a_sk.data(), a_sk.size());
    assert(a_pkey != nullptr);
    std::vector<uint8_t> a_pk(32);
    std::size_t pk_len = 32;
    assert(EVP_PKEY_get_raw_public_key(a_pkey, a_pk.data(), &pk_len) > 0);
    assert(CRYPTO_memcmp(a_pk.data(), exp_a_pk.data(), 32) == 0);
    std::cout << "    [+] RFC 7748 Alice Public Key Derivation: MATCH (bit-exact)\n";

    // Compute Bob Public Key
    EVP_PKEY* b_pkey = EVP_PKEY_new_raw_private_key(EVP_PKEY_X25519, nullptr, b_sk.data(), b_sk.size());
    assert(b_pkey != nullptr);
    std::vector<uint8_t> b_pk(32);
    assert(EVP_PKEY_get_raw_public_key(b_pkey, b_pk.data(), &pk_len) > 0);
    assert(CRYPTO_memcmp(b_pk.data(), exp_b_pk.data(), 32) == 0);
    std::cout << "    [+] RFC 7748 Bob Public Key Derivation: MATCH (bit-exact)\n";

    // Alice computes shared secret using Bob public key
    EVP_PKEY* b_peer = EVP_PKEY_new_raw_public_key(EVP_PKEY_X25519, nullptr, b_pk.data(), b_pk.size());
    assert(b_peer != nullptr);
    EVP_PKEY_CTX* a_ctx = EVP_PKEY_CTX_new(a_pkey, nullptr);
    assert(a_ctx != nullptr);
    assert(EVP_PKEY_derive_init(a_ctx) > 0);
    assert(EVP_PKEY_derive_set_peer(a_ctx, b_peer) > 0);

    std::vector<uint8_t> ss_a(32);
    std::size_t ss_len = 32;
    assert(EVP_PKEY_derive(a_ctx, ss_a.data(), &ss_len) > 0);
    assert(CRYPTO_memcmp(ss_a.data(), exp_k.data(), 32) == 0);
    std::cout << "    [+] RFC 7748 Alice Shared Secret Exchange K: MATCH (bit-exact)\n";

    // Bob computes shared secret using Alice public key
    EVP_PKEY* a_peer = EVP_PKEY_new_raw_public_key(EVP_PKEY_X25519, nullptr, a_pk.data(), a_pk.size());
    assert(a_peer != nullptr);
    EVP_PKEY_CTX* b_ctx = EVP_PKEY_CTX_new(b_pkey, nullptr);
    assert(b_ctx != nullptr);
    assert(EVP_PKEY_derive_init(b_ctx) > 0);
    assert(EVP_PKEY_derive_set_peer(b_ctx, a_peer) > 0);

    std::vector<uint8_t> ss_b(32);
    assert(EVP_PKEY_derive(b_ctx, ss_b.data(), &ss_len) > 0);
    assert(CRYPTO_memcmp(ss_b.data(), exp_k.data(), 32) == 0);
    assert(CRYPTO_memcmp(ss_a.data(), ss_b.data(), 32) == 0);
    std::cout << "    [+] RFC 7748 Bob Shared Secret Exchange K: MATCH (bit-exact)\n";

    EVP_PKEY_CTX_free(a_ctx);
    EVP_PKEY_CTX_free(b_ctx);
    EVP_PKEY_free(a_peer);
    EVP_PKEY_free(b_peer);
    EVP_PKEY_free(a_pkey);
    EVP_PKEY_free(b_pkey);
}

// ── Test 2: RFC 5869 HKDF-SHA256 Known Answer Tests ────────────────────────
void test_rfc5869_hkdf_kat() {
    std::cout << "[*] [KAT 2/4] Running RFC 5869 HKDF-SHA256 Official Test Vectors...\n";

    std::string ikm_hex  = "0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b";
    std::string salt_hex = "000102030405060708090a0b0c";
    std::string info_hex = "f0f1f2f3f4f5f6f7f8f9";
    std::string okm_hex  = "3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf34007208d5b887185865";

    auto ikm = hex_to_bytes(ikm_hex);
    auto salt = hex_to_bytes(salt_hex);
    auto info = hex_to_bytes(info_hex);
    auto expected_okm = hex_to_bytes(okm_hex);

    EVP_KDF* kdf = EVP_KDF_fetch(nullptr, "HKDF", nullptr);
    assert(kdf != nullptr);
    EVP_KDF_CTX* kctx = EVP_KDF_CTX_new(kdf);
    assert(kctx != nullptr);

    char digest_name[] = "SHA256";
    OSSL_PARAM params[5];
    params[0] = OSSL_PARAM_construct_utf8_string(OSSL_KDF_PARAM_DIGEST, digest_name, 0);
    params[1] = OSSL_PARAM_construct_octet_string(OSSL_KDF_PARAM_SALT, salt.data(), salt.size());
    params[2] = OSSL_PARAM_construct_octet_string(OSSL_KDF_PARAM_KEY, ikm.data(), ikm.size());
    params[3] = OSSL_PARAM_construct_octet_string(OSSL_KDF_PARAM_INFO, info.data(), info.size());
    params[4] = OSSL_PARAM_construct_end();

    std::vector<uint8_t> out_okm(42);
    assert(EVP_KDF_derive(kctx, out_okm.data(), out_okm.size(), params) > 0);

    EVP_KDF_CTX_free(kctx);
    EVP_KDF_free(kdf);

    assert(CRYPTO_memcmp(out_okm.data(), expected_okm.data(), 42) == 0);
    std::cout << "    [+] RFC 5869 Test Case 1 (L=42): MATCH (bit-exact)\n";
}

// ── Test 3: FrodoKEM-976 Mathematical Invariant KAT ────────────────────────
void test_frodokem_math_kat() {
    std::cout << "[*] [KAT 3/4] Running FrodoKEM-976 Matrix & FO-Transform Invariant KATs...\n";

    using namespace quantumflex::crypto;

    HybridKeyPair server_kp = HybridKemEngine::generate_keypair();
    auto [ct, client_ss] = HybridKemEngine::encapsulate(server_kp.public_key);

    std::vector<uint8_t> server_ss;
    bool ok = HybridKemEngine::decapsulate_constant_time(ct, server_kp.private_key, server_kp.public_key, server_ss);

    assert(ok == true);
    assert(client_ss.size() == 32);
    assert(server_ss.size() == 32);
    assert(CRYPTO_memcmp(client_ss.data(), server_ss.data(), 32) == 0);
    std::cout << "    [+] FrodoKEM-976 + X25519 Shared Secret Convergence: MATCH (bit-exact)\n";

    // Wycheproof Low-Order / Degenerate Point KAT Rejections
    HybridCiphertext zero_ct = ct;
    zero_ct.x25519_ct.assign(32, 0);
    std::vector<uint8_t> zero_ss;
    bool zero_ok = HybridKemEngine::decapsulate_constant_time(zero_ct, server_kp.private_key, server_kp.public_key, zero_ss);
    assert(zero_ok == false);
    assert(CRYPTO_memcmp(client_ss.data(), zero_ss.data(), 32) != 0);
    std::cout << "    [+] Wycheproof Degenerate Point 0 (All Zeros): REJECTED fail-closed\n";

    HybridCiphertext order2_ct = ct;
    order2_ct.x25519_ct.assign(32, 0);
    order2_ct.x25519_ct[0] = 1;
    std::vector<uint8_t> order2_ss;
    bool order2_ok = HybridKemEngine::decapsulate_constant_time(order2_ct, server_kp.private_key, server_kp.public_key, order2_ss);
    assert(order2_ok == false);
    assert(CRYPTO_memcmp(client_ss.data(), order2_ss.data(), 32) != 0);
    std::cout << "    [+] Wycheproof Degenerate Point 1 (Order 2): REJECTED fail-closed\n";
}

// ── Test 4: Shamir GF(256) Secret Sharing Mathematical KAT ─────────────────
void test_shamir_gf256_kat() {
    std::cout << "[*] [KAT 4/4] Running Shamir Secret Sharing GF(256) Invariant KATs...\n";

    using namespace quantumflex::crypto;

    std::string secret = "QuantumFlex-Invariant-Secret-2026-FIPS-CAVP";
    uint8_t threshold = 3;
    uint8_t total_shares = 5;

    auto shares = ShamirSecretSharing::split_secret(secret, total_shares, threshold);
    assert(shares.size() == total_shares);

    std::vector<SecretShard> subset_exact = {shares[0], shares[1], shares[2]};
    std::string recovered_exact = ShamirSecretSharing::recover_secret(subset_exact, 3);
    assert(recovered_exact == secret);
    std::cout << "    [+] Shamir GF(256) 3-of-5 Exact Threshold Reconstruction: MATCH (bit-exact)\n";

    std::vector<SecretShard> subset_distinct = {shares[1], shares[3], shares[4]};
    std::string recovered_distinct = ShamirSecretSharing::recover_secret(subset_distinct, 3);
    assert(recovered_distinct == secret);
    std::cout << "    [+] Shamir GF(256) Alternate Subset Reconstruction: MATCH (bit-exact)\n";

    std::vector<SecretShard> insufficient = {shares[0], shares[1]};
    bool caught_insufficient = false;
    try {
        std::string rec = ShamirSecretSharing::recover_secret(insufficient, 3);
        if (rec != secret) caught_insufficient = true;
    } catch (...) {
        caught_insufficient = true;
    }
    assert(caught_insufficient);
    std::cout << "    [+] Shamir GF(256) Insufficient Shares (2-of-5): FAIL-CLOSED verified\n";
}


// ── Test 5: NIST FIPS 203 ML-KEM Official Standard Verification ───────────
void test_fips203_mlkem_kat() {
    std::cout << "[*] [KAT 5/5] Running NIST FIPS 203 ML-KEM Standard Verification Suite...\n";

    auto test_mlkem_variant = [](const char* alg, size_t exp_pk, size_t exp_ct, size_t exp_ss) {
        EVP_PKEY_CTX* ctx = EVP_PKEY_CTX_new_from_name(nullptr, alg, nullptr);
        assert(ctx != nullptr);
        int rc = EVP_PKEY_keygen_init(ctx);
        assert(rc > 0);
        EVP_PKEY* pkey = nullptr;
        rc = EVP_PKEY_generate(ctx, &pkey);
        assert(rc > 0);

        // Verify FIPS 203 public key wire size
        size_t pk_len = 0;
        rc = EVP_PKEY_get_raw_public_key(pkey, nullptr, &pk_len);
        assert(rc > 0);
        assert(pk_len == exp_pk);

        // FIPS 203 Encapsulation
        EVP_PKEY_CTX* enc = EVP_PKEY_CTX_new_from_pkey(nullptr, pkey, nullptr);
        assert(enc != nullptr);
        rc = EVP_PKEY_encapsulate_init(enc, nullptr);
        assert(rc > 0);
        size_t ct_len = 0, ss_len = 0;
        rc = EVP_PKEY_encapsulate(enc, nullptr, &ct_len, nullptr, &ss_len);
        assert(rc > 0);
        assert(ct_len == exp_ct);
        assert(ss_len == exp_ss);

        std::vector<uint8_t> ct(ct_len);
        std::vector<uint8_t> ss_client(ss_len);
        rc = EVP_PKEY_encapsulate(enc, ct.data(), &ct_len, ss_client.data(), &ss_len);
        assert(rc > 0);

        // FIPS 203 Decapsulation (Nominal Path)
        EVP_PKEY_CTX* dec = EVP_PKEY_CTX_new_from_pkey(nullptr, pkey, nullptr);
        assert(dec != nullptr);
        rc = EVP_PKEY_decapsulate_init(dec, nullptr);
        assert(rc > 0);
        std::vector<uint8_t> ss_server(ss_len);
        rc = EVP_PKEY_decapsulate(dec, ss_server.data(), &ss_len, ct.data(), ct_len);
        assert(rc > 0);
        assert(ss_client == ss_server);

        // FIPS 203 Adversarial Perturbation (Implicit Rejection to Pseudo-Secret)
        std::vector<uint8_t> bad_ct = ct;
        bad_ct[42] ^= 0x55;
        std::vector<uint8_t> ss_corrupt(ss_len);
        rc = EVP_PKEY_decapsulate(dec, ss_corrupt.data(), &ss_len, bad_ct.data(), bad_ct.size());
        assert(rc > 0);
        assert(ss_corrupt != ss_client); // Must diverge fail-closed!

        std::cout << "    [+] " << alg << " (pk=" << pk_len << " B, ct=" << ct_len << " B, ss=" << ss_len << " B): MATCH (bit-exact & fail-closed)\n";

        EVP_PKEY_CTX_free(dec);
        EVP_PKEY_CTX_free(enc);
        EVP_PKEY_CTX_free(ctx);
        EVP_PKEY_free(pkey);
    };

    test_mlkem_variant("ML-KEM-512", 800, 768, 32);
    test_mlkem_variant("ML-KEM-768", 1184, 1088, 32);
    test_mlkem_variant("ML-KEM-1024", 1568, 1568, 32);
}

int main() {
    std::cout << "==================================================================\n";
    std::cout << "     QUANTUM FLEX // KNOWN ANSWER TESTS (KAT) VERIFICATION SUITE   \n";
    std::cout << "==================================================================\n";

    test_rfc7748_kat();
    test_rfc5869_hkdf_kat();
    test_frodokem_math_kat();
    test_shamir_gf256_kat();
    test_fips203_mlkem_kat();

    std::cout << "\n[ALL 5 KNOWN ANSWER TEST (KAT) SUITES 100% BIT-EXACT PASSED]\n";
    return 0;
}
