#ifndef QUANTUM_FLEX_EWMA_LIF_SENTINEL_HPP
#define QUANTUM_FLEX_EWMA_LIF_SENTINEL_HPP

#include <atomic>
#include <chrono>
#include <cstdint>
#include <memory>
#include <thread>

namespace quantumflex::node {
    class LocalNode;
}

namespace quantumflex::security {

    struct LifConfig {
        double alpha{0.05};            // EWMA smoothing coefficient (0.0 < alpha <= 1.0)
        double sigma_multiplier{3.0};   // Variance scaling factor (n * sigma)
        double tau_leak_ms{500.0};      // Membrane leak half-life in milliseconds
        double drop_impulse{1.0};       // Voltage impulse per dropped connection / error
        double v_base_floor{2.0};       // Minimum firing threshold floor
        uint32_t tick_interval_ms{30};  // Background quantized decay baseline resolution (ms)
        uint32_t jitter_min_ms{20};     // Lower bound for dynamic jitter tick (ms)
        uint32_t jitter_max_ms{40};     // Upper bound for dynamic jitter tick (ms)
    };

    struct AnomalySnapshot {
        double moving_mean{0.0};
        double moving_variance{0.0};
        double moving_stddev{0.0};
        double v_thresh{2.0};
        double v_mem{0.0};
        uint64_t total_drops{0};
        uint64_t total_spikes{0};
    };

    class EwmaLifSentinel {
    public:
        explicit EwmaLifSentinel(node::LocalNode& target_node, LifConfig config = LifConfig{});
        ~EwmaLifSentinel();

        EwmaLifSentinel(const EwmaLifSentinel&) = delete;
        auto operator=(const EwmaLifSentinel&) -> EwmaLifSentinel& = delete;
        EwmaLifSentinel(EwmaLifSentinel&&) = delete;
        auto operator=(EwmaLifSentinel&&) -> EwmaLifSentinel& = delete;

        // Starts the background quantized tick decay loop
        void start();

        // Gracefully halts the background decay thread
        void stop();

        // Hot-path method called on socket drop / handshake failure / verification error
        // O(1) lock-free atomic CAS execution
        void record_drop(double impulse = -1.0);

        // Called on successful handshake to update baseline mean downward
        void record_success();

        // Returns thread-safe snapshot of all statistical & membrane metrics
        [[nodiscard]] auto get_snapshot() const -> AnomalySnapshot;

        // Manually reset membrane potential (e.g. post-recovery)
        void reset_membrane();

    private:
        node::LocalNode& node_;
        LifConfig config_;

        // Lock-free atomic state
        std::atomic<double> moving_mean_{0.0};
        std::atomic<double> moving_variance_{0.0};
        std::atomic<double> v_thresh_{2.0};
        std::atomic<double> v_mem_{0.0};

        std::atomic<uint64_t> total_drops_{0};
        std::atomic<uint64_t> total_spikes_{0};

        std::atomic<bool> running_{false};
        std::thread tick_thread_;

        // Internal lock-free Welford EWMA update
        void update_ewma(double sample);

        // Background worker applying quantized batch leak decay
        void tick_loop();
    };

} // namespace quantumflex::security

#endif // QUANTUM_FLEX_EWMA_LIF_SENTINEL_HPP
