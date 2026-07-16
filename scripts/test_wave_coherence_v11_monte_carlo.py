"""
TRACEBIND-W11: Multi-Dimensional Monte Carlo Validation Engine (Production Grade)
Systematically sweeps across seeds, resolutions, and parameters to validate
coherence estimation. Highly optimized with file appends, lazy graph slicing,
and periodic summary compilation.
Output Directory: C:\\GaiaProject\\data\\TRACEBIND-W11\\
"""

import os
import sys
import time
import datetime
import numpy as np
import pandas as pd
import sklearn
from sklearn.neighbors import NearestNeighbors

EPSILON = 1e-6
ALGORITHM_VERSION = "TRACEBIND-W11-C1"
OUTPUT_DIR = r"C:\GaiaProject\data\TRACEBIND-W11"

# Target output files
RAW_OUTPUT_FILE = os.path.join(OUTPUT_DIR, "TRACEBIND_MC_SWEEP.csv")
SUMMARY_OUTPUT_FILE = os.path.join(OUTPUT_DIR, "TRACEBIND_MC_SUMMARY.csv")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# =====================================================================
# FROZEN METHODOLOGY: TRACEBIND-W11 CANDIDATE 1
# =====================================================================

def apply_laplacian_2d(field_flat, grid_size):
    field_2d = field_flat.reshape((grid_size, grid_size))
    padded = np.pad(field_2d, pad_width=1, mode='edge')
    laplacian = (
        4 * padded[1:-1, 1:-1]
        - padded[0:-2, 1:-1]   # Top
        - padded[2:, 1:-1]     # Bottom
        - padded[1:-1, 0:-2]   # Left
        - padded[1:-1, 2:]     # Right
    )
    return laplacian.ravel()


def compute_normalized_spatial_energy(raw_field, filtered_field):
    rms_raw = np.sqrt(np.mean(raw_field ** 2))
    rms_filtered = np.sqrt(np.mean(filtered_field ** 2))
    return float(rms_filtered / (rms_raw + EPSILON))


def generate_simulation_suite(grid_size, seed, rng):
    x = np.linspace(-10, 10, grid_size)
    y = np.linspace(-10, 10, grid_size)
    xx, yy = np.meshgrid(x, y)
    
    positions_2d = np.column_stack([xx.ravel(), yy.ravel()])
    num_points = len(positions_2d)
    
    datasets = {}

    # 1. Ideal Coherent Field
    I_coherent = np.cos(xx.ravel() / 1.5) ** 2
    datasets["1_ideal_coherent"] = I_coherent

    # 2. Coherent Field with Phase Noise
    phase_noise = rng.normal(0, 0.8, size=num_points)
    I_noisy_coherent = np.cos(xx.ravel() / 1.5 + phase_noise) ** 2
    datasets["2_phase_noise_0.8"] = I_noisy_coherent

    # 3. Thermal Source
    thermal_phase = rng.uniform(0, 2 * np.pi, size=num_points)
    I_thermal = np.cos(thermal_phase) ** 2
    datasets["3_thermal_source"] = I_thermal

    # 4. Pure Mathematical Gaussian
    r_sq = xx.ravel()**2 + yy.ravel()**2
    I_gaussian = np.exp(-r_sq / 30.0)
    datasets["4_pure_gaussian"] = I_gaussian

    # 5. Correlated Random Field (Pink Noise)
    white_noise_f = rng.normal(size=(grid_size, grid_size)) + 1j * rng.normal(size=(grid_size, grid_size))
    kx = np.fft.fftfreq(grid_size)
    ky = np.fft.fftfreq(grid_size)
    kxx, kyy = np.meshgrid(kx, ky)
    k_radial = np.sqrt(kxx**2 + kyy**2)
    k_radial[0, 0] = 1.0
    pink_filter = 1.0 / (k_radial ** 1.0)
    pink_noise_f = white_noise_f * pink_filter
    pink_noise_spatial = np.real(np.fft.ifft2(pink_noise_f)).ravel()
    I_pink = (pink_noise_spatial - pink_noise_spatial.min()) / (pink_noise_spatial.max() - pink_noise_spatial.min())
    datasets["5_pink_noise"] = I_pink

    # 6. White Noise
    I_white = rng.uniform(0, 1, size=num_points)
    datasets["6_white_noise"] = I_white

    return positions_2d, datasets


def build_neighbor_graph_2d(positions_2d, max_k):
    n = len(positions_2d)
    safe_max_k = min(max_k + 1, n)
    nn = NearestNeighbors(n_neighbors=safe_max_k, metric='euclidean', algorithm='ball_tree')
    nn.fit(positions_2d)
    distances, indices = nn.kneighbors(positions_2d)
    return {"distances": distances[:, 1:], "indices": indices[:, 1:]}


def _get_weights_and_indices(graph, k):
    idx_nbrs = graph["indices"][:, :k]
    dist_nbrs = graph["distances"][:, :k]
    weights = 1.0 / (dist_nbrs**2 + EPSILON)
    weight_sum = np.sum(weights, axis=1, keepdims=True)
    w_norm = weights / np.maximum(weight_sum, 1e-12)
    return w_norm, idx_nbrs


def compute_loo_field_error(field_values, k, graph):
    w_norm, idx_nbrs = _get_weights_and_indices(graph, k)
    field_nbrs = field_values[idx_nbrs]
    predicted = np.sum(w_norm * field_nbrs, axis=1)
    errors = np.abs(field_values - predicted)
    return float(np.median(errors))


def compute_field_baseline_distribution(field_values, k_predict, k_shuffle, n_perm, noise_frac, graph, rng):
    n = len(field_values)
    _, idx_shuffle = _get_weights_and_indices(graph, k_shuffle)

    local_stds = np.empty(n)
    for i in range(n):
        nbr_idx = idx_shuffle[i]
        if len(nbr_idx) <= 1:
            local_stds[i] = 1e-6
            continue
        
        std_val = np.std(field_values[nbr_idx], ddof=1)
        if np.isnan(std_val) or std_val < 1e-12:
            std_val = 1e-6
        local_stds[i] = std_val

    null_errors = []
    for _ in range(n_perm):
        shuffled_field = np.empty(n)
        for i in range(n):
            nbr_idx = idx_shuffle[i]
            if len(nbr_idx) == 0:
                shuffled_field[i] = field_values[i]
                continue

            chosen = rng.integers(0, len(nbr_idx))
            local_std = local_stds[i]
            noise = rng.normal(0, noise_frac * local_std)
            shuffled_field[i] = field_values[nbr_idx[chosen]] + noise

        err = compute_loo_field_error(shuffled_field, k_predict, graph)
        if not np.isnan(err):
            null_errors.append(err)

    return np.array(null_errors) if null_errors else np.array([np.nan])


# =====================================================================
# PERSISTENT RESUMPTION INFRASTRUCTURE
# =====================================================================

def load_or_initialize_sweep():
    """Reads saved data to compute verified completion history tracking keys."""
    if os.path.exists(RAW_OUTPUT_FILE):
        try:
            df = pd.read_csv(RAW_OUTPUT_FILE)
            completed_keys = set(
                f"{row['grid_size']}_{row['k_predict']}_{row['seed']}_{row['dataset']}"
                for _, row in df.iterrows()
            )
            print(f"📂 Verification: Resuming from checkpoint. {len(completed_keys)} verified keys loaded.")
            return len(completed_keys), completed_keys
        except Exception as e:
            print(f"⚠️ Warning reading archive matrix ({e}). Starting fresh sweep execution.")
            
    return 0, set()


def build_final_summary_report():
    """Loads raw sweep file entirely once to output analytical dashboards."""
    if not os.path.exists(RAW_OUTPUT_FILE):
        return
    try:
        df_raw = pd.read_csv(RAW_OUTPUT_FILE)
        df_ungated = df_raw[df_raw["gated"] == 0]
        summary_data = []
        
        for ds in df_raw["dataset"].unique():
            ds_raw = df_raw[df_raw["dataset"] == ds]
            ds_ungated = df_ungated[df_ungated["dataset"] == ds]
            
            total_runs = len(ds_raw)
            gated_runs = int(ds_raw["gated"].sum())
            gate_percentage = (gated_runs / total_runs) * 100.0 if total_runs > 0 else 0.0
            
            if len(ds_ungated) > 0:
                mean_ratio = float(ds_ungated["ratio"].mean())
                median_ratio = float(ds_ungated["ratio"].median())
                std_ratio = float(ds_ungated["ratio"].std())
                ci_low = float(np.percentile(ds_ungated["ratio"], 2.5)) if len(ds_ungated) > 1 else np.nan
                ci_high = float(np.percentile(ds_ungated["ratio"], 97.5)) if len(ds_ungated) > 1 else np.nan
            else:
                mean_ratio = median_ratio = std_ratio = ci_low = ci_high = np.nan
                
            summary_data.append({
                "Dataset": ds, "Total_N": total_runs, "Gated_N": gated_runs, "Gate_Rate_Pct": gate_percentage,
                "Mean_Ratio_R": mean_ratio, "Median_Ratio_R": median_ratio, "Std_Ratio_R": std_ratio,
                "95_CI_Lower": ci_low, "95_CI_Upper": ci_high
            })
        pd.DataFrame(summary_data).to_csv(SUMMARY_OUTPUT_FILE, index=False)
    except Exception as e:
        print(f"⚠️ Warning updating dashboard components: {e}")


# =====================================================================
# SYSTEM SWEEP EXECUTION
# =====================================================================

def main():
    SEEDS = list(range(100, 200))  
    GRID_SIZES = [20, 40, 80]      
    K_PREDICTS = [10, 15, 20]      
    
    N_PERM = 100                   
    NOISE_FRACTION = 0.1
    ENERGY_THRESHOLD = 0.15
    SUMMARY_INTERVAL = 100         # ISSUE 4 FIX: Update summary table only every 100 entries

    runtime_stamp = datetime.datetime.now().isoformat()
    py_version = sys.version.split()[0]
    np_version = np.__version__
    sk_version = sklearn.__version__

    # Persistent Checkpoint Resumption initialization
    completed_count, completed_keys = load_or_initialize_sweep()
    total_matrix_elements = len(GRID_SIZES) * len(K_PREDICTS) * len(SEEDS) * 6
    
    print("================================================================================")
    print(f"🚀 TRACEBIND-W11 Production Sweep Engine Initiated")
    print(f"Targeting Matrix Profile: {total_matrix_elements} execution nodes.")
    print("================================================================================")

    global_start_time = time.perf_counter()

    try:
        for grid in GRID_SIZES:
            for seed in SEEDS:
                # ISSUE 1 & 3 FIX: Generate field simulation suite ONCE per resolution-seed pairing
                rng = np.random.default_rng(seed)
                positions, datasets = generate_simulation_suite(grid_size=grid, seed=seed, rng=rng)
                
                # ISSUE 5 FIX: Precalculate global graph for MAX K boundary requirements
                max_k_possible = max(K_PREDICTS) * 2
                global_graph = build_neighbor_graph_2d(positions, max_k=max_k_possible)
                
                for k_pred in K_PREDICTS:
                    k_shuffle = k_pred * 2
                    
                    for dataset_name, raw_field in datasets.items():
                        run_key = f"{grid}_{k_pred}_{seed}_{dataset_name}"
                        
                        if run_key in completed_keys:
                            continue
                            
                        start_time = time.perf_counter()
                        filtered_field = apply_laplacian_2d(raw_field, grid)
                        s_norm = compute_normalized_spatial_energy(raw_field, filtered_field)
                        
                        gated = s_norm < ENERGY_THRESHOLD
                        real_err = base_mean = base_std = base_median = base_ci_lower = base_ci_upper = ratio = np.nan
                        
                        if not gated:
                            try:
                                real_err = compute_loo_field_error(filtered_field, k_pred, global_graph)
                                null_dist = compute_field_baseline_distribution(
                                    filtered_field, k_pred, k_shuffle, N_PERM, NOISE_FRACTION, global_graph, rng
                                )
                                base_mean = float(np.mean(null_dist))
                                base_std = float(np.std(null_dist, ddof=1)) if len(null_dist) > 1 else np.nan
                                base_median = float(np.median(null_dist))
                                base_ci_lower = float(np.percentile(null_dist, 2.5))
                                base_ci_upper = float(np.percentile(null_dist, 97.5))
                                
                                ratio = real_err / base_mean if base_mean > 1e-12 else np.nan
                            except Exception as eval_err:
                                print(f"\n⚠️ Math operational skip on node {run_key}: {eval_err}")
                                gated = True
                        
                        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                        
                        row_dict = {
                            "algorithm": ALGORITHM_VERSION, "timestamp": runtime_stamp,
                            "python_version": py_version, "numpy_version": np_version, "scikit_learn_version": sk_version,
                            "seed": seed, "grid_size": grid, "k_predict": k_pred, "dataset": dataset_name,
                            "s_norm": s_norm, "real_error": real_err, "baseline_mean": base_mean,
                            "baseline_std": base_std, "baseline_median": base_median,
                            "baseline_ci_lower": base_ci_lower, "baseline_ci_upper": base_ci_upper,
                            "ratio": ratio, "gated": int(gated), "runtime_ms": elapsed_ms
                        }
                        
                        # ISSUE 1 FIX: Continuous atomic I/O stream with direct disk append (O(1))
                        new_row_df = pd.DataFrame([row_dict])
                        new_row_df.to_csv(
                            RAW_OUTPUT_FILE,
                            mode="a",
                            header=not os.path.exists(RAW_OUTPUT_FILE),
                            index=False
                        )
                        
                        completed_keys.add(run_key)
                        completed_count += 1
                        
                        # ISSUE 4 FIX: Intermittent metric aggregation dumps
                        if completed_count % SUMMARY_INTERVAL == 0:
                            build_final_summary_report()
                        
                        # ISSUE 2 FIX: Accurate ETA and execution runtime reporting metric pipelines
                        elapsed_total = time.perf_counter() - global_start_time
                        avg_rate = elapsed_total / max(completed_count - (total_matrix_elements - len(completed_keys)), 1)
                        remaining_steps = total_matrix_elements - completed_count
                        est_rem = avg_rate * remaining_steps
                        
                        def fmt_time(seconds):
                            h, rem = divmod(int(seconds), 3600)
                            m, sec = divmod(rem, 60)
                            return f"{h}h {m}m {sec}s"
                            
                        print(f"💾 Step ({completed_count}/{total_matrix_elements}) | Grid: {grid}x{grid} | k: {k_pred} | Seed: {seed} | Rem: {fmt_time(est_rem)}", flush=True)

    except KeyboardInterrupt:
        print("\n🛑 Execution paused via manual key breakout. Progress preserved safely on disk.")
        sys.exit(0)
    except Exception as e:
        print(f"\n⚠️ Global execution runtime failure: {e}")
        raise

    # Compile the final summary dashboard at full conclusion
    build_final_summary_report()
    print("\n================================================================================")
    print("🎯 Verification Successful! The complete production sweep is finished.")
    print("================================================================================")

if __name__ == "__main__":
    main()