#include "quantum-flex/hybrid_kem.hpp"

#include <openssl/crypto.h>
#include <cassert>
#include <chrono>
#include <iostream>
#include <vector>

int main() {
    using namespace quantumflex::crypto;

    std::cout << "[TEST] ── Starting FrodoKEM-976 + X25519 Hybrid Combiner Tests ──\n";

    // 1. Key Generation
    auto t0 = std::chrono::high_resolution_clock::now();
    HybridKeyPair server_kp = HybridKemEngine::generate_keypair();
    auto t1 = std::chrono::high_resolution_clock::now();
    auto ms_keygen = std::chrono::duration_cast<std::chrono::milliseconds>(t1 - t0).count();

    std::cout << "[+] Keypair generated in " << ms_keygen << "ms\n";
    assert(server_kp.public_key.x25519_pk.size() == X25519_PUBLIC_KEY_BYTES);
    assert(server_kp.public_key.frodo_pk.size() == FRODO976_PUBLIC_KEY_BYTES);
    assert(server_kp.public_key.serialize().size() == HYBRID_PUBLIC_KEY_BYTES);

    // 2. Encapsulation
    auto t2 = std::chrono::high_resolution_clock::now();
    auto [ct, client_ss] = HybridKemEngine::encapsulate(server_kp.public_key);
    auto t3 = std::chrono::high_resolution_clock::now();
    auto ms_encap = std::chrono::duration_cast<std::chrono::milliseconds>(t3 - t2).count();

    std::cout << "[+] Encapsulation completed in " << ms_encap << "ms\n";
    assert(ct.x25519_ct.size() == X25519_PUBLIC_KEY_BYTES);
    assert(ct.frodo_ct.size() == FRODO976_CIPHERTEXT_BYTES);
    assert(ct.serialize().size() == HYBRID_CIPHERTEXT_BYTES);
    assert(client_ss.size() == HYBRID_SHARED_SECRET_BYTES);

    // 3. Decapsulation (Nominal Path)
    std::vector<uint8_t> server_ss;
    auto t4 = std::chrono::high_resolution_clock::now();
    bool decap_ok = HybridKemEngine::decapsulate_constant_time(ct, server_kp.private_key, server_kp.public_key, server_ss);
    auto t5 = std::chrono::high_resolution_clock::now();
    auto ms_decap = std::chrono::duration_cast<std::chrono::milliseconds>(t5 - t4).count();

    std::cout << "[+] Decapsulation completed in " << ms_decap << "ms (nominal ok=" << decap_ok << ")\n";
    assert(decap_ok == true);
    assert(server_ss.size() == HYBRID_SHARED_SECRET_BYTES);
    assert(CRYPTO_memcmp(client_ss.data(), server_ss.data(), HYBRID_SHARED_SECRET_BYTES) == 0);
    std::cout << "[PASS] Invariant 1: Shared secrets converged identically over hybrid wire!\n";

    // 4. Adversarial Perturbation Test: Corrupt Frodo Ciphertext
    HybridCiphertext corrupted_frodo_ct = ct;
    corrupted_frodo_ct.frodo_ct[42] ^= 0xFF; // Invert byte in lattice matrix
    std::vector<uint8_t> perturbed_ss;
    auto t6 = std::chrono::high_resolution_clock::now();
    bool perturbed_decap = HybridKemEngine::decapsulate_constant_time(corrupted_frodo_ct, server_kp.private_key, server_kp.public_key, perturbed_ss);
    auto t7 = std::chrono::high_resolution_clock::now();
    auto ms_pert_decap = std::chrono::duration_cast<std::chrono::milliseconds>(t7 - t6).count();

    std::cout << "[+] Perturbed Frodo decap returned ok=" << perturbed_decap << " in " << ms_pert_decap << "ms\n";
    assert(perturbed_decap == false);
    assert(CRYPTO_memcmp(client_ss.data(), perturbed_ss.data(), HYBRID_SHARED_SECRET_BYTES) != 0);
    std::cout << "[PASS] Invariant 2: Corrupted Frodo ciphertext rejected fail-closed!\n";

    // 5. Adversarial Perturbation Test: Low-Order Point on X25519
    HybridCiphertext low_order_ct = ct;
    low_order_ct.x25519_ct.assign(32, 0); // Point at infinity / low-order point 0
    std::vector<uint8_t> low_order_ss;
    bool low_order_decap = HybridKemEngine::decapsulate_constant_time(low_order_ct, server_kp.private_key, server_kp.public_key, low_order_ss);
    assert(low_order_decap == false);
    assert(CRYPTO_memcmp(client_ss.data(), low_order_ss.data(), HYBRID_SHARED_SECRET_BYTES) != 0);
    std::cout << "[PASS] Invariant 3: Low-order X25519 point rejected fail-closed (RFC 7748)!\n";

    // 6. Adversarial Perturbation Test: Tampered X25519 Ciphertext Divergence
    HybridCiphertext tampered_x25519_ct = ct;
    tampered_x25519_ct.x25519_ct[15] ^= 0xAA;
    std::vector<uint8_t> tampered_x25519_ss;
    static_cast<void>(HybridKemEngine::decapsulate_constant_time(tampered_x25519_ct, server_kp.private_key, server_kp.public_key, tampered_x25519_ss));
    assert(CRYPTO_memcmp(client_ss.data(), tampered_x25519_ss.data(), HYBRID_SHARED_SECRET_BYTES) != 0);
    std::cout << "[PASS] Invariant 4: Tampered X25519 point strictly diverges from client secret!\n";

    // 7. Verify Wire Serialization Round-trip
    auto wire_pk = server_kp.public_key.serialize();
    auto deserialized_pk = HybridPublicKey::deserialize(wire_pk.data(), wire_pk.size());
    assert(deserialized_pk.x25519_pk == server_kp.public_key.x25519_pk);
    assert(deserialized_pk.frodo_pk == server_kp.public_key.frodo_pk);

    auto wire_ct = ct.serialize();
    auto deserialized_ct = HybridCiphertext::deserialize(wire_ct.data(), wire_ct.size());
    assert(deserialized_ct.x25519_ct == ct.x25519_ct);
    assert(deserialized_ct.frodo_ct == ct.frodo_ct);
    std::cout << "[PASS] Invariant 5: Wire serialization round-trip 100% byte-accurate!\n";

    std::cout << "\n[ALL 5 HYBRID KEM COMBINER INVARIANTS 100% VERIFIED]\n";
    return 0;
}
