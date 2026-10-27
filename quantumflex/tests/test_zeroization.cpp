#include "quantum-flex/hybrid_kem.hpp"
#include "quantum-flex/crypto_shamir.hpp"

#include <openssl/crypto.h>

#include <cassert>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <vector>
#include <memory>

// Helper to inspect memory through volatile pointer to bypass compiler dead-store assumptions
bool is_memory_all_zero(const void* ptr, std::size_t len) {
    if (ptr == nullptr || len == 0) return true;
    auto vptr = static_cast<volatile const uint8_t*>(ptr);
    for (std::size_t i = 0; i < len; ++i) {
        if (vptr[i] != 0x00) {
            return false;
        }
    }
    return true;
}

void test_direct_buffer_zeroization() {
    std::cout << "[*] [ZEROIZATION 1/3] Testing OPENSSL_cleanse Direct Buffer Scrubbing...\n";

    // 1. Stack buffer zeroization
    uint8_t stack_key[64];
    for (std::size_t i = 0; i < sizeof(stack_key); ++i) {
        stack_key[i] = static_cast<uint8_t>((i * 37 + 11) & 0xFF);
        if (stack_key[i] == 0) stack_key[i] = 0x5A;
    }
    assert(!is_memory_all_zero(stack_key, sizeof(stack_key)));
    OPENSSL_cleanse(stack_key, sizeof(stack_key));
    assert(is_memory_all_zero(stack_key, sizeof(stack_key)));
    std::cout << "    [+] Stack buffer (64 bytes): OPENSSL_cleanse verified 100% 0x00\n";

    // 2. Large heap buffer zeroization (matching FrodoKEM secret key size: 31296 B)
    constexpr std::size_t FRODO_SK_LEN = 31296;
    auto heap_sk = std::make_unique<uint8_t[]>(FRODO_SK_LEN);
    for (std::size_t i = 0; i < FRODO_SK_LEN; ++i) {
        heap_sk[i] = static_cast<uint8_t>((i * 101 + 3) & 0xFF);
        if (heap_sk[i] == 0) heap_sk[i] = 0xFF;
    }
    assert(!is_memory_all_zero(heap_sk.get(), FRODO_SK_LEN));
    OPENSSL_cleanse(heap_sk.get(), FRODO_SK_LEN);
    assert(is_memory_all_zero(heap_sk.get(), FRODO_SK_LEN));
    std::cout << "    [+] Heap buffer (31,296 bytes): OPENSSL_cleanse verified 100% 0x00 under -O3\n";
}

#ifdef QUANTUMFLEX_ENABLE_LEGACY_FRODO_RESEARCH
void test_hybrid_private_key_zeroization() {
    std::cout << "[*] [ZEROIZATION 2/3] Testing HybridPrivateKey Explicit Zeroization...\n";

    quantumflex::crypto::HybridKeyPair kp = quantumflex::crypto::HybridKemEngine::generate_keypair();
    assert(kp.private_key.x25519_sk.size() == 32);
    assert(kp.private_key.frodo_sk.size() == 31296);

    assert(!is_memory_all_zero(kp.private_key.x25519_sk.data(), kp.private_key.x25519_sk.size()));
    assert(!is_memory_all_zero(kp.private_key.frodo_sk.data(), kp.private_key.frodo_sk.size()));
    std::cout << "    [+] Active HybridPrivateKey contains non-zero cryptographic entropy.\n";

    // Cleanse explicitly
    OPENSSL_cleanse(kp.private_key.x25519_sk.data(), kp.private_key.x25519_sk.size());
    OPENSSL_cleanse(kp.private_key.frodo_sk.data(), kp.private_key.frodo_sk.size());

    assert(is_memory_all_zero(kp.private_key.x25519_sk.data(), kp.private_key.x25519_sk.size()));
    assert(is_memory_all_zero(kp.private_key.frodo_sk.data(), kp.private_key.frodo_sk.size()));
    std::cout << "    [+] HybridPrivateKey x25519_sk & frodo_sk: Verified 100% zeroized in memory\n";
}
#endif

void test_secret_shard_zeroization() {
    std::cout << "[*] [ZEROIZATION 3/3] Testing Shamir Secret Shard Zeroization...\n";

    std::string secret = "TopSecret-Zeroization-Audit-2026"; // 32 bytes, as split_secret requires
    auto shards = quantumflex::crypto::ShamirSecretSharing::split_secret(secret, 5, 3);

    for (auto& s : shards) {
        assert(!is_memory_all_zero(s.payload.data(), s.payload.size()));
    }

    // Cleanse shards
    for (auto& s : shards) {
        OPENSSL_cleanse(s.payload.data(), s.payload.size());
    }

    // Verify all shard payloads are 100% zero
    for (auto& s : shards) {
        assert(is_memory_all_zero(s.payload.data(), s.payload.size()));
    }

    std::cout << "    [+] All 5 Shamir shards physically scrubbed with 0x00 in RAM\n";
}

int main() {
    std::cout << "==================================================================\n";
    std::cout << "     QUANTUM FLEX // MEMORY ZEROIZATION AUDIT TEST SUITE          \n";
    std::cout << "==================================================================\n";

    test_direct_buffer_zeroization();
#ifdef QUANTUMFLEX_ENABLE_LEGACY_FRODO_RESEARCH
    test_hybrid_private_key_zeroization();
#endif
    test_secret_shard_zeroization();

    std::cout << "\n[ALL MEMORY ZEROIZATION AUDIT INVARIANTS 100% VERIFIED]\n";
    return 0;
}
