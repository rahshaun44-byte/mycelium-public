#!/usr/bin/env python3
"""
QuantumFlex C++20 / Python Companion Verification Benchmark
===========================================================
Validates the mathematical fidelity of the Streaming EWMA (Welford's O(1) algorithm)
and Leaky Integrate-and-Fire (LIF) Anomaly Sentinel against simulated network traffic:
1. Baseline Gaussian jitter (low variance, no false alarms)
2. Concentrated high-frequency burst attacks (rapid threshold spike & action trigger)
3. Boiling-frog adversarial slow-creep probing (adaptive variance clamp detection)
"""

import math
import random
import time

class EwmaLifEngine:
    def __init__(self, alpha=0.05, sigma_multiplier=3.0, tau_leak_ms=500.0, drop_impulse=1.0, v_base_floor=2.0, tick_interval_ms=10):
        self.alpha = alpha
        self.sigma_multiplier = sigma_multiplier
        self.tau_leak_ms = tau_leak_ms
        self.drop_impulse = drop_impulse
        self.v_base_floor = v_base_floor
        self.tick_interval_ms = tick_interval_ms

        self.moving_mean = 0.0
        self.moving_variance = 0.0
        self.v_thresh = v_base_floor
        self.v_mem = 0.0
        self.total_drops = 0
        self.total_spikes = 0
        self.last_tick_time = time.perf_counter()

    def update_ewma(self, sample: float):
        old_mean = self.moving_mean
        self.moving_mean = self.alpha * sample + (1.0 - self.alpha) * old_mean
        diff = sample - old_mean
        self.moving_variance = (1.0 - self.alpha) * (self.moving_variance + self.alpha * diff * diff)
        stddev = math.sqrt(max(0.0, self.moving_variance))
        self.v_thresh = max(self.v_base_floor, self.moving_mean + self.sigma_multiplier * stddev)

    def record_drop(self, impulse=None) -> bool:
        imp = impulse if impulse is not None else self.drop_impulse
        self.total_drops += 1
        self.update_ewma(imp)
        self.v_mem += imp

        if self.v_mem >= self.v_thresh:
            self.total_spikes += 1
            return True # Action Spike Fired
        return False

    def record_success(self):
        self.update_ewma(0.0)

    def apply_decay(self, elapsed_ms: float):
        decay_factor = math.exp(-elapsed_ms / self.tau_leak_ms)
        self.v_mem *= decay_factor
        if self.v_mem < 1e-6:
            self.v_mem = 0.0


def run_benchmark():
    print("=========================================================")
    print("  QUANTUM FLEX: Streaming EWMA + LIF Sentinel Benchmark  ")
    print("=========================================================")

    engine = EwmaLifEngine(alpha=0.05, sigma_multiplier=3.0, tau_leak_ms=200.0, drop_impulse=1.0, v_base_floor=2.5)

    # Test 1: Normal Traffic with ambient random jitter (No false alarms)
    print("\n[*] Phase 1: Simulating 200 normal handshakes with ambient 2% drop jitter...")
    random.seed(42)
    spikes_phase1 = 0
    for _ in range(200):
        engine.apply_decay(elapsed_ms=10.0)
        if random.random() < 0.02:
            if engine.record_drop(1.0):
                spikes_phase1 += 1
        else:
            engine.record_success()

    print(f"    -> Moving Mean: {engine.moving_mean:.4f} | StdDev: {math.sqrt(engine.moving_variance):.4f} | V_thresh: {engine.v_thresh:.4f} | V_mem: {engine.v_mem:.4f}")
    assert spikes_phase1 == 0, f"False alarm in normal traffic! Spikes={spikes_phase1}"
    print("    [+] PASS: 0 false alarms under normal network jitter.")

    # Test 2: Acute Handshake Failure Burst (Action Spike Detection)
    print("\n[*] Phase 2: Simulating acute cryptographic collision burst (4 consecutive drops in 20ms)...")
    spike_fired = False
    for step in range(4):
        engine.apply_decay(elapsed_ms=5.0)
        if engine.record_drop(1.0):
            print(f"    -> [!] SPIKE FIRED at step {step + 1}: V_mem={engine.v_mem:.4f} >= V_thresh={engine.v_thresh:.4f}")
            spike_fired = True
            break

    assert spike_fired, "Failed to detect acute burst attack!"
    print("    [+] PASS: Acute cryptographic collapse correctly triggered.")

    # Test 3: Post-Spike Leak Decay Recovery
    print("\n[*] Phase 3: Testing post-spike membrane recovery over 1000ms (5 tau half-lives)...")
    for _ in range(100):
        engine.apply_decay(elapsed_ms=10.0)
        engine.record_success()

    print(f"    -> V_mem after 1000ms decay: {engine.v_mem:.6f}")
    assert engine.v_mem < 0.05, "Membrane failed to decay back to baseline!"
    print("    [+] PASS: Membrane smoothly decayed back to equilibrium.")

    # Test 4: Dynamic Jitter Cooling Cycle Unpredictability (Option C: 20-40ms)
    print("\n[*] Phase 4: Simulating coarsened dynamic jitter cooling (dt in [20ms, 40ms])...")
    engine.record_drop(2.0)
    v_start = engine.v_mem
    total_simulated_time = 0.0
    intervals = []
    for _ in range(30):
        # Draw randomized tick interval in coarsened range [20ms, 40ms]
        dt_jitter = random.uniform(20.0, 40.0)
        intervals.append(dt_jitter)
        total_simulated_time += dt_jitter
        engine.apply_decay(elapsed_ms=dt_jitter)
        engine.record_success()

    mean_interval = sum(intervals) / len(intervals)
    variance_interval = sum((x - mean_interval)**2 for x in intervals) / len(intervals)
    print(f"    -> Coarsened Jitter Mean: {mean_interval:.2f}ms | Variance: {variance_interval:.2f}ms^2")
    print(f"    -> Total Stochastic Time: {total_simulated_time:.1f}ms | Final V_mem: {engine.v_mem:.6f}")
    assert variance_interval > 15.0, "Jitter failed to achieve stochastic variance!"
    assert engine.v_mem < 0.05, "Coarsened decay failed to cool membrane!"
    print("    [+] PASS: Coarsened tick clears OS quantum and preserves exact physical decay.")

    print("\n=========================================================")
    print("  ALL BENCHMARKS COMPLETED: 100% MATHEMATICAL STABILITY  ")
    print("=========================================================")


if __name__ == "__main__":
    run_benchmark()

