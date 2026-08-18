#include "quantum-flex/ewma_lif_sentinel.hpp"
#include "quantum-flex/local_node.hpp"

#include <algorithm>
#include <cmath>
#include <iostream>
#include <random>

namespace quantumflex::security {

    EwmaLifSentinel::EwmaLifSentinel(node::LocalNode& target_node, LifConfig config)
        : node_(target_node), config_(config) {
        v_thresh_.store(config_.v_base_floor, std::memory_order_relaxed);
    }

    EwmaLifSentinel::~EwmaLifSentinel() {
        stop();
    }

    void EwmaLifSentinel::start() {
        if (running_.exchange(true, std::memory_order_acq_rel)) {
            return; // Already running
        }
        tick_thread_ = std::thread(&EwmaLifSentinel::tick_loop, this);
    }

    void EwmaLifSentinel::stop() {
        if (running_.exchange(false, std::memory_order_acq_rel)) {
            if (tick_thread_.joinable()) {
                tick_thread_.join();
            }
        }
    }

    void EwmaLifSentinel::update_ewma(double sample) {
        const double alpha = config_.alpha;

        // 1. Lock-free Atomic CAS for moving mean
        double old_mean = moving_mean_.load(std::memory_order_relaxed);
        double new_mean = 0.0;
        do {
            new_mean = alpha * sample + (1.0 - alpha) * old_mean;
        } while (!moving_mean_.compare_exchange_weak(
            old_mean, new_mean, std::memory_order_release, std::memory_order_relaxed));

        // 2. Lock-free Atomic CAS for moving variance (Welford EWMA)
        double old_var = moving_variance_.load(std::memory_order_relaxed);
        double new_var = 0.0;
        do {
            const double diff = sample - old_mean;
            new_var = (1.0 - alpha) * (old_var + alpha * diff * diff);
        } while (!moving_variance_.compare_exchange_weak(
            old_var, new_var, std::memory_order_release, std::memory_order_relaxed));

        // 3. Compute adaptive threshold: V_thresh = max(V_base, mean + n * stddev)
        const double stddev = std::sqrt(std::max(0.0, new_var));
        const double calculated_thresh = new_mean + (config_.sigma_multiplier * stddev);
        const double final_thresh = std::max(config_.v_base_floor, calculated_thresh);

        v_thresh_.store(final_thresh, std::memory_order_release);
    }

    void EwmaLifSentinel::record_drop(double impulse) {
        const double effective_impulse = (impulse > 0.0) ? impulse : config_.drop_impulse;

        total_drops_.fetch_add(1, std::memory_order_relaxed);

        // Update statistical background baseline
        update_ewma(effective_impulse);

        // Lock-free Atomic CAS for membrane potential charge accumulation
        double old_vmem = v_mem_.load(std::memory_order_relaxed);
        double new_vmem = 0.0;
        do {
            new_vmem = old_vmem + effective_impulse;
        } while (!v_mem_.compare_exchange_weak(
            old_vmem, new_vmem, std::memory_order_release, std::memory_order_relaxed));

        // Evaluate firing condition against dynamic statistical threshold
        const double current_thresh = v_thresh_.load(std::memory_order_acquire);
        if (new_vmem >= current_thresh) {
            total_spikes_.fetch_add(1, std::memory_order_relaxed);

            std::cerr << "[AUDIT ALERT] LIF Sentinel Action Spike FIRED: V_mem (" << new_vmem 
                      << ") >= V_thresh (" << current_thresh << "). Anomaly threshold breached on socket.\n";

            // HARD STOP: Disarmed from terminal process exit to prevent unauthenticated listener self-DoS.
            // Emits security event / backoff metric without killing the daemon.
        }
    }

    void EwmaLifSentinel::record_success() {
        // Successful handshakes sample 0.0, dragging moving mean and variance down
        update_ewma(0.0);
    }

    auto EwmaLifSentinel::get_snapshot() const -> AnomalySnapshot {
        const double mean = moving_mean_.load(std::memory_order_relaxed);
        const double var = moving_variance_.load(std::memory_order_relaxed);
        const double stddev = std::sqrt(std::max(0.0, var));
        const double thresh = v_thresh_.load(std::memory_order_relaxed);
        const double vmem = v_mem_.load(std::memory_order_relaxed);
        const uint64_t drops = total_drops_.load(std::memory_order_relaxed);
        const uint64_t spikes = total_spikes_.load(std::memory_order_relaxed);

        return AnomalySnapshot{
            .moving_mean = mean,
            .moving_variance = var,
            .moving_stddev = stddev,
            .v_thresh = thresh,
            .v_mem = vmem,
            .total_drops = drops,
            .total_spikes = spikes
        };
    }

    void EwmaLifSentinel::reset_membrane() {
        v_mem_.store(0.0, std::memory_order_release);
    }

    void EwmaLifSentinel::tick_loop() {
        // Fast PRNG seeded with monotonic clock entropy
        std::minstd_rand rng(static_cast<unsigned int>(
            std::chrono::steady_clock::now().time_since_epoch().count()));
        std::uniform_int_distribution<uint32_t> jitter_dist(
            config_.jitter_min_ms, config_.jitter_max_ms);

        while (running_.load(std::memory_order_relaxed)) {
            const uint32_t requested_sleep_ms = jitter_dist(rng);
            
            const auto t0 = std::chrono::steady_clock::now();
            std::this_thread::sleep_for(std::chrono::milliseconds(requested_sleep_ms));
            const auto t1 = std::chrono::steady_clock::now();
            
            if (!running_.load(std::memory_order_relaxed)) {
                break;
            }

            // Compute exact physical elapsed time from high-res monotonic clock
            const double dt_actual_ms = std::chrono::duration<double, std::milli>(t1 - t0).count();
            const double decay_factor = std::exp(-dt_actual_ms / config_.tau_leak_ms);

            // Lock-free Atomic CAS for physical membrane potential decay
            double old_vmem = v_mem_.load(std::memory_order_relaxed);
            double new_vmem = 0.0;
            do {
                new_vmem = old_vmem * decay_factor;
                // Clamp tiny residual floats to zero to avoid subnormal arithmetic
                if (new_vmem < 1e-6) {
                    new_vmem = 0.0;
                }
            } while (!v_mem_.compare_exchange_weak(
                old_vmem, new_vmem, std::memory_order_release, std::memory_order_relaxed));
        }
    }

} // namespace quantumflex::security
