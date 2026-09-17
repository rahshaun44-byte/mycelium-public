#include "quantum-flex/hybrid_kem.hpp"
#include "quantum-flex/wire_framing.hpp"
#include <openssl/crypto.h>
#include <iostream>
#include <stdexcept>
#include <fstream>
#include <iterator>

using namespace quantumflex;
void check(bool ok, const char* message) { if (!ok) throw std::runtime_error(message); }
template <typename F> void rejects(F f) {
    bool rejected = false;
    try { f(); } catch (const std::exception&) { rejected = true; }
    check(rejected, "Expected rejection");
}
int main(int argc, char** argv) {
    try {
        // Test fixture: export ciphertext/expected tag from a public key file.
        // Private/shared keys are never written to disk.
        if (argc == 5 && std::string(argv[1]) == "--prepare") {
            std::ifstream input(argv[2], std::ios::binary);
            check(input.is_open(), "Cannot read public key fixture");
            std::vector<uint8_t> public_key((std::istreambuf_iterator<char>(input)), {});
            auto [ciphertext, secret] = crypto::MLKem768Engine::encapsulate(public_key);
            auto tag = crypto::MLKem768Engine::confirmation(secret, ciphertext);
            OPENSSL_cleanse(secret.data(), secret.size());
            std::ofstream ct_out(argv[3], std::ios::binary), tag_out(argv[4], std::ios::binary);
            ct_out.write(reinterpret_cast<const char*>(ciphertext.data()), ciphertext.size());
            tag_out.write(reinterpret_cast<const char*>(tag.data()), tag.size());
            check(ct_out.good() && tag_out.good(), "Cannot write public exchange fixture");
            return 0;
        }
        check(argc == 1, "Unsupported test arguments");
        crypto::MLKem768Engine engine;
        const auto pk = engine.public_key();
        check(pk.size() == 1184, "Wrong public key size");
        auto [ct, ss] = crypto::MLKem768Engine::encapsulate(pk);
        auto recovered = engine.decapsulate(ct);
        check(ct.size() == 1088 && ss.size() == 32 && recovered.size() == 32, "Wrong output size");
        check(CRYPTO_memcmp(ss.data(), recovered.data(), 32) == 0, "Roundtrip mismatch");
        const auto tag = crypto::MLKem768Engine::confirmation(ss, ct);
        check(tag == crypto::MLKem768Engine::confirmation(recovered, ct), "Confirmation mismatch");
        check(tag != ss, "Confirmation exposed the secret");
        auto bad = ct; bad[0] ^= 1;
        auto rejected_secret = engine.decapsulate(bad);
        check(rejected_secret != ss, "Implicit rejection did not change secret");
        check(crypto::MLKem768Engine::confirmation(rejected_secret, bad) != tag, "Tampered confirmation accepted");
        rejects([&] { (void)engine.decapsulate({}); });
        rejects([&] { (void)engine.decapsulate(std::vector<uint8_t>(15776)); });
        rejects([&] { (void)crypto::MLKem768Engine::encapsulate(std::vector<uint8_t>(15664)); });
        rejects([&] { crypto::MLKem768Engine unavailable("provider=nonexistent"); });
        rejects([&] { (void)crypto::MLKem768Engine::encapsulate(pk, "provider=nonexistent"); });
        // Exercise empty request framing and ML-KEM response framing.
        wire::QuantumFlexReassemblyPool pool;
        auto frame = wire::serialize_frame(wire::MSG_MLKEM768_PK, 0, nullptr, 0);
        std::vector<uint8_t> payload; uint8_t type = 0;
        check(pool.ingest_stream("request", frame.data(), frame.size(), payload, type), "Empty PK request rejected");
        check(type == wire::MSG_MLKEM768_PK && payload.empty(), "PK request corrupted");
        frame = wire::serialize_frame(wire::MSG_MLKEM768_CT, 0, ct.data(), ct.size());
        check(!pool.ingest_stream("ct", frame.data(), 8, payload, type), "Partial header accepted");
        check(pool.ingest_stream("ct", frame.data()+8, frame.size()-8, payload, type), "Fragmented ciphertext rejected");
        check(payload == ct && type == wire::MSG_MLKEM768_CT, "Ciphertext framing mismatch");
        for (auto* secret : {&ss, &recovered, &rejected_secret}) OPENSSL_cleanse(secret->data(), secret->size());
        std::cout << "PASS: native ML-KEM-768 roundtrip, implicit rejection, confirmation, provider failure, lengths and wire framing\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
