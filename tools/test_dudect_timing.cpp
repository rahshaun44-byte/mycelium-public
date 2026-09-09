#include "quantum-flex/hybrid_kem.hpp"
#include <chrono>
#include <cmath>
#include <iostream>
#include <vector>
#include <cassert>
#include <x86intrin.h>

using namespace quantumflex::crypto;

class OnlineStats {
public:
    void add(double x) {
        count++;
        double delta = x - mean;
        mean += delta / count;
        double delta2 = x - mean;
        M2 += delta2 * delta;
    }
    double get_mean() const { return mean; }
    double get_variance() const { return count > 1 ? M2 / (count - 1) : 0.0; }
    size_t get_count() const { return count; }
private:
    size_t count = 0;
    double mean = 0.0;
    double M2 = 0.0;
};

int main() {
    std::cout << "==================================================================" << std::endl;
    std::cout << "   QUANTUM FLEX // DUDECT STATISTICAL TIMING ANALYSIS (WELCH T)  " << std::endl;
    std::cout << "==================================================================" << std::endl;

    HybridKeyPair server_kp = HybridKemEngine::generate_keypair();
    auto [nominal_ct, nominal_ss] = HybridKemEngine::encapsulate(server_kp.public_key);

    HybridCiphertext corrupted_ct = nominal_ct;
    corrupted_ct.frodo_ct[42] ^= 0xFF;

    OnlineStats stats_fixed;
    OnlineStats stats_random;

    constexpr size_t NUM_SAMPLES = 2500;
    std::vector<uint8_t> ss_dummy;

    // Warm-up cache
    for (int i = 0; i < 50; ++i) {
        static_cast<void>(HybridKemEngine::decapsulate_constant_time(nominal_ct, server_kp.private_key, server_kp.public_key, ss_dummy));
    }

    std::cout << "[*] Executing " << (NUM_SAMPLES * 2) << " interleaved decapsulation measurements..." << std::endl;

    for (size_t i = 0; i < NUM_SAMPLES; ++i) {
        unsigned int aux;
        // Class A: Fixed Nominal Ciphertext
        uint64_t t0 = __rdtscp(&aux);
        static_cast<void>(HybridKemEngine::decapsulate_constant_time(nominal_ct, server_kp.private_key, server_kp.public_key, ss_dummy));
        uint64_t t1 = __rdtscp(&aux);
        stats_fixed.add(static_cast<double>(t1 - t0));

        // Class B: Corrupted Ciphertext
        uint64_t t2 = __rdtscp(&aux);
        static_cast<void>(HybridKemEngine::decapsulate_constant_time(corrupted_ct, server_kp.private_key, server_kp.public_key, ss_dummy));
        uint64_t t3 = __rdtscp(&aux);
        stats_random.add(static_cast<double>(t3 - t2));
    }

    double mean_a = stats_fixed.get_mean();
    double var_a = stats_fixed.get_variance();
    double mean_b = stats_random.get_mean();
    double var_b = stats_random.get_variance();

    double n_a = static_cast<double>(stats_fixed.get_count());
    double n_b = static_cast<double>(stats_random.get_count());

    double welch_t = (mean_a - mean_b) / std::sqrt((var_a / n_a) + (var_b / n_b));

    std::cout << "[*] Class A (Nominal) Mean Cycles:   " << mean_a << " (stddev=" << std::sqrt(var_a) << ")" << std::endl;
    std::cout << "[*] Class B (Corrupted) Mean Cycles: " << mean_b << " (stddev=" << std::sqrt(var_b) << ")" << std::endl;
    std::cout << "[*] Welch t-statistic:               " << welch_t << " (|t|=" << std::abs(welch_t) << ")" << std::endl;
    std::cout << "[*] dudect Threshold (|t| < 4.5):    " << (std::abs(welch_t) < 4.5 ? "PASS (Constant-time behavior NOT rejected)" : "FAIL (Potential timing leak)") << std::endl;

    assert(std::abs(welch_t) < 4.5);
    std::cout << "\n[DUDECT TIMING STATISTICAL INDISTINGUISHABILITY VERIFIED (t < 4.5)]" << std::endl;
    return 0;
}
