#include "quantum-flex/ewma_lif_sentinel.hpp"
#include "quantum-flex/local_node.hpp"
#include "quantum-flex/forensic_lockdown.hpp"

#include <cassert>
#include <chrono>
#include <cmath>
#include <iostream>
#include <thread>
#include <vector>

using namespace quantumflex;

void test_ewma_math_convergence() {
    std::cout << "[*] Testing EWMA statistical variance convergence...\n";

    security::DryRunCommandExecutor dry_run_executor;
    node::LocalNode mock_node(&dry_run_executor, security::LockdownPolicy{.dry_run = true});

    security::LifConfig config{
        .alpha = 0.1,
        .sigma_multiplier = 2.0,
        .tau_leak_ms = 1000.0,
        .drop_impulse = 1.0,
        .v_base_floor = 1.0,
        .tick_interval_ms = 10
    };

    security::EwmaLifSentinel sentinel(mock_node, config);

    // Initial state
    auto s0 = sentinel.get_snapshot();
    assert(s0.moving_mean == 0.0);
    assert(s0.v_thresh == 1.0);

    // Record repeated drops (sample = 1.0)
    for (int i = 0; i < 20; ++i) {
        sentinel.record_drop(1.0);
    }

    auto s1 = sentinel.get_snapshot();
    // Mean should asymptotically converge toward 1.0
    assert(s1.moving_mean > 0.85);
    // Standard deviation should be small because all samples were identical
    assert(s1.moving_stddev < 0.3);
    assert(s1.total_drops == 20);

    std::cout << "    -> Mean: " << s1.moving_mean << ", StdDev: " << s1.moving_stddev 
              << ", V_thresh: " << s1.v_thresh << "\n";
    std::cout << "[+] PASS: EWMA math convergence verified.\n";
}

void test_quantized_leak_decay() {
    std::cout << "[*] Testing Quantized Background Leak Decay Loop...\n";

    security::DryRunCommandExecutor dry_run_executor;
    node::LocalNode mock_node(&dry_run_executor, security::LockdownPolicy{.dry_run = true});

    security::LifConfig config{
        .alpha = 0.05,
        .sigma_multiplier = 3.0,
        .tau_leak_ms = 100.0, // Fast 100ms decay for test
        .drop_impulse = 0.5,
        .v_base_floor = 10.0, // High threshold so it doesn't fire
        .tick_interval_ms = 10
    };

    security::EwmaLifSentinel sentinel(mock_node, config);
    sentinel.start();

    // Inject charge
    sentinel.record_drop(2.0);
    auto s_charged = sentinel.get_snapshot();
    assert(s_charged.v_mem >= 1.9);

    std::cout << "    -> Initial V_mem: " << s_charged.v_mem << "\n";

    // Wait 250ms (2.5 half-lives)
    std::this_thread::sleep_for(std::chrono::milliseconds(250));

    auto s_decayed = sentinel.get_snapshot();
    std::cout << "    -> Decayed V_mem after 250ms: " << s_decayed.v_mem << "\n";

    // V_mem should have decayed significantly (< 0.5)
    assert(s_decayed.v_mem < 0.5);

    sentinel.stop();
    std::cout << "[+] PASS: Quantized leak decay verified.\n";
}

void test_multithreaded_lockfree_atomics() {
    std::cout << "[*] Testing Lock-Free Multi-Threaded Ingress Contention...\n";

    security::DryRunCommandExecutor dry_run_executor;
    node::LocalNode mock_node(&dry_run_executor, security::LockdownPolicy{.dry_run = true});

    security::LifConfig config{
        .alpha = 0.01,
        .sigma_multiplier = 3.0,
        .tau_leak_ms = 5000.0,
        .drop_impulse = 0.01,
        .v_base_floor = 1000.0, // Prevent quarantine during load test
        .tick_interval_ms = 10
    };

    security::EwmaLifSentinel sentinel(mock_node, config);

    constexpr int NUM_THREADS = 8;
    constexpr int DROPS_PER_THREAD = 1000;

    std::vector<std::thread> workers;
    workers.reserve(NUM_THREADS);

    for (int t = 0; t < NUM_THREADS; ++t) {
        workers.emplace_back([&sentinel]() {
            for (int i = 0; i < DROPS_PER_THREAD; ++i) {
                sentinel.record_drop(0.01);
            }
        });
    }

    for (auto& w : workers) {
        w.join();
    }

    auto snapshot = sentinel.get_snapshot();
    assert(snapshot.total_drops == NUM_THREADS * DROPS_PER_THREAD);
    assert(snapshot.moving_mean > 0.0);

    std::cout << "    -> Processed " << snapshot.total_drops << " concurrent lock-free updates across " 
              << NUM_THREADS << " threads.\n";
    std::cout << "[+] PASS: Multi-threaded lock-free CAS atomics verified.\n";
}

int main() {
    std::cout << "=========================================\n";
    std::cout << "  QUANTUM FLEX: EwmaLifSentinel Test Suite\n";
    std::cout << "=========================================\n";

    try {
        test_ewma_math_convergence();
        test_quantized_leak_decay();
        test_multithreaded_lockfree_atomics();

        std::cout << "=========================================\n";
        std::cout << "  ALL C++20 EWMA-LIF TESTS PASSED (100%)\n";
        std::cout << "=========================================\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "[FATAL TEST FAILURE] " << e.what() << "\n";
        return 1;
    }
}
