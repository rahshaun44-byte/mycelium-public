#!/usr/bin/env python3
"""
Empirical Windows Scheduler & LIF Integrator Characterization
=============================================================
Four strict measurements:
1. Fixed 10ms vs Jittered (6-14ms) integrator divergence against exact continuous decay.
2. Max |requested - actual| sleep duration on this specific Windows host.
3. 200-iteration histogram of sleep(6ms) under default Windows timer resolution.
4. Closed-loop probe: Constant drop injection near threshold (Jitter ON vs OFF, N=10,000).
"""

import math
import random
import time

def exp1_integrator_divergence():
    print("===================================================================")
    print("  EXPERIMENT 1: Fixed 10ms vs Jittered (6-14ms) vs Exact Decay   ")
    print("===================================================================")
    V0 = 5.0
    tau = 200.0 # ms
    total_time_ms = 1000.0 # 1 second run

    # 1. Exact continuous reference: V(t) = V0 * exp(-t / tau)
    # 2. Fixed 10ms discrete integrator:
    # 3. Jittered (6-14ms) discrete integrator:

    random.seed(1337)
    
    # Simulate step by step
    t_fixed = 0.0
    v_fixed = V0
    
    t_jitter = 0.0
    v_jitter = V0

    history_fixed = [(0.0, V0)]
    while t_fixed < total_time_ms:
        dt = 10.0
        v_fixed *= math.exp(-dt / tau)
        t_fixed += dt
        history_fixed.append((t_fixed, v_fixed))

    history_jitter = [(0.0, V0)]
    while t_jitter < total_time_ms:
        dt = random.uniform(6.0, 14.0)
        v_jitter *= math.exp(-dt / tau)
        t_jitter += dt
        history_jitter.append((t_jitter, v_jitter))

    # Measure divergence at matching evaluation points (interp)
    max_err_fixed_vs_exact = 0.0
    for t, v in history_fixed:
        v_exact = V0 * math.exp(-t / tau)
        err = abs(v - v_exact)
        if err > max_err_fixed_vs_exact:
            max_err_fixed_vs_exact = err

    max_err_jitter_vs_exact = 0.0
    for t, v in history_jitter:
        v_exact = V0 * math.exp(-t / tau)
        err = abs(v - v_exact)
        if err > max_err_jitter_vs_exact:
            max_err_jitter_vs_exact = err

    print(f"[*] Initial V_mem: {V0:.4f}, Tau: {tau:.1f} ms, Total Horizon: {total_time_ms:.1f} ms")
    print(f"    -> Fixed 10ms Steps: {len(history_fixed)-1} ticks | Final V: {history_fixed[-1][1]:.6f}")
    print(f"    -> Jittered Steps:   {len(history_jitter)-1} ticks | Final V: {history_jitter[-1][1]:.6f}")
    print(f"    -> Exact Continuous Final V(1000ms): {V0 * math.exp(-1000.0 / tau):.6f}")
    print(f"    -> Max |V_fixed - V_exact|:   {max_err_fixed_vs_exact:.2e} (IEEE-754 roundoff)")
    print(f"    -> Max |V_jitter - V_exact|:  {max_err_jitter_vs_exact:.2e} (IEEE-754 roundoff)")
    print(f"    -> Mathematical Equivalence: TRUE in pure floating-point arithmetic (Euler integration of exponential is exact when step is exp(-dt/tau)).")


def exp2_sleep_requested_vs_actual():
    print("\n===================================================================")
    print("  EXPERIMENT 2: Requested vs Actual Sleep Delta on Windows Host   ")
    print("===================================================================")
    random.seed(42)
    iterations = 50
    requested_list = [random.uniform(6.0, 14.0) for _ in range(iterations)]
    actual_list = []
    deltas = []

    for req_ms in requested_list:
        t0 = time.perf_counter_ns()
        time.sleep(req_ms / 1000.0)
        t1 = time.perf_counter_ns()
        act_ms = (t1 - t0) / 1e6
        actual_list.append(act_ms)
        deltas.append(abs(act_ms - req_ms))

    max_delta = max(deltas)
    mean_delta = sum(deltas) / len(deltas)
    mean_req = sum(requested_list) / len(requested_list)
    mean_act = sum(actual_list) / len(actual_list)

    print(f"[*] Sampled {iterations} randomized sleep calls in range [6.0ms, 14.0ms]:")
    print(f"    -> Mean Requested: {mean_req:.2f} ms | Mean Actual: {mean_act:.2f} ms")
    print(f"    -> Max |Requested - Actual|:  {max_delta:.2f} ms")
    print(f"    -> Mean |Requested - Actual|: {mean_delta:.2f} ms")
    print(f"    -> Hazard if dt=requested: Error compounds by up to {max_delta:.2f} ms per tick if actual elapsed time is not measured with high-res clock!")


def exp3_windows_timer_histogram():
    print("\n===================================================================")
    print("  EXPERIMENT 3: 200-Iteration Histogram of sleep(6ms) (Default)   ")
    print("===================================================================")
    iterations = 200
    times = []

    for _ in range(iterations):
        t0 = time.perf_counter_ns()
        time.sleep(0.006) # Requested 6.0 ms
        t1 = time.perf_counter_ns()
        times.append((t1 - t0) / 1e6)

    min_t = min(times)
    max_t = max(times)
    avg_t = sum(times) / len(times)

    print(f"[*] 200 Iterations of sleep_for(6.0ms) on Windows (Default Resolution):")
    print(f"    -> Min: {min_t:.2f} ms | Max: {max_t:.2f} ms | Mean: {avg_t:.2f} ms\n")

    # Histogram Bins (1ms buckets from 0 to 20ms)
    buckets = {}
    for i in range(4, 22):
        buckets[i] = 0

    for t in times:
        b = int(math.floor(t))
        if b in buckets:
            buckets[b] += 1
        elif b < 4:
            buckets[4] += 1
        else:
            buckets[21] += 1

    print("    Bucket (ms) | Count | Distribution")
    print("    ------------|-------|-------------------------------------------")
    for b in sorted(buckets.keys()):
        count = buckets[b]
        bar = "#" * int(count / 2)
        print(f"    [{b:2d} - {b+1:2d} ms] | {count:5d} | {bar}")

    piled_at_15_16 = buckets.get(15, 0) + buckets.get(16, 0)
    pct_15_16 = (piled_at_15_16 / iterations) * 100.0
    print(f"\n    -> Piled at 15-16ms (Windows 64Hz default scheduler tick): {piled_at_15_16}/{iterations} ({pct_15_16:.1f}%)")
    if pct_15_16 > 50.0:
        print("    -> CONCLUSION: The 6-14ms sleep window is FICTIONAL on default Windows timer resolution without timeBeginPeriod(1).")


def exp4_closed_loop_probe():
    print("\n===================================================================")
    print("  EXPERIMENT 4: Closed-Loop Near-Threshold Probe (N=10,000)        ")
    print("===================================================================")
    N = 10000
    tau = 200.0 # ms
    v_thresh = 2.5
    drop_impulse = 1.0

    # Inject drops at steady interval near critical threshold
    # Equilibrium potential for drop every T_inj: V_eq = I / (1 - exp(-T_inj / tau))
    # For V_eq ~ 2.4 (just below 2.5 threshold):
    # 2.4 = 1.0 / (1 - exp(-T_inj / 200)) => exp(-T_inj/200) = 1 - 1/2.4 = 0.5833 => T_inj ~ 107.8 ms
    T_inj = 108.0 # ms

    # Case A: Fixed 10ms tick loop
    v_mem_fixed = 0.0
    spikes_fixed = 0
    t_fixed = 0.0
    next_drop_fixed = T_inj

    for _ in range(N):
        dt = 10.0
        t_fixed += dt
        v_mem_fixed *= math.exp(-dt / tau)
        if t_fixed >= next_drop_fixed:
            v_mem_fixed += drop_impulse
            next_drop_fixed += T_inj
            if v_mem_fixed >= v_thresh:
                spikes_fixed += 1

    # Case B: Jittered 6-14ms tick loop
    random.seed(999)
    v_mem_jitter = 0.0
    spikes_jitter = 0
    t_jitter = 0.0
    next_drop_jitter = T_inj

    for _ in range(N):
        dt = random.uniform(6.0, 14.0)
        t_jitter += dt
        v_mem_jitter *= math.exp(-dt / tau)
        if t_jitter >= next_drop_jitter:
            v_mem_jitter += drop_impulse
            next_drop_jitter += T_inj
            if v_mem_jitter >= v_thresh:
                spikes_jitter += 1

    print(f"[*] Probing N={N} cycles with steady drop injection every {T_inj}ms (Target V_eq ~ 2.40, Threshold={v_thresh}):")
    print(f"    -> Fixed 10ms Integrator Fires:    {spikes_fixed} spikes / {int(t_fixed/T_inj)} total drops")
    print(f"    -> Jittered 6-14ms Integrator Fires: {spikes_jitter} spikes / {int(t_jitter/T_inj)} total drops")
    print(f"    -> False-Positive Burst Shift: Discretization noise under randomized tick boundaries altered trigger count by {abs(spikes_fixed - spikes_jitter)} events.")


if __name__ == "__main__":
    exp1_integrator_divergence()
    exp2_sleep_requested_vs_actual()
    exp3_windows_timer_histogram()
    exp4_closed_loop_probe()
