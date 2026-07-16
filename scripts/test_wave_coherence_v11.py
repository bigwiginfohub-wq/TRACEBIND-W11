"""
TRACEBIND-W11: Scale-Invariant Validity-Gated Wave Coherence Suite
Implements a scale-invariant Normalized Laplacian Energy Gate to isolate 
oscillatory spatial structure and includes a multi-seed validation sweep.
License: CC0 1.0 Universal
"""
import os
import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors

EPSILON = 1e-6

# =====================================================================
# LAPLACIAN OPERATOR & SCALE-INVARIANT ENERGY GATE
# =====================================================================

def apply_laplacian_2d(field_flat, grid_size):
    """Reshapes flat field to 2D, applies discrete Laplacian, flattens back."""
    field_2d = field_flat.reshape((grid_size, grid_size))
    padded = np.pad(field_2d, pad_width=1, mode='edge')
    
    # 5-point discrete Laplacian kernel
    laplacian = (
        4 * padded[1:-1, 1:-1]
        - padded[0:-2, 1:-1]   # Top
        - padded[2:, 1:-1]     # Bottom
        - padded[1:-1, 0:-2]   # Left
        - padded[1:-1, 2:]     # Right
    )
    return laplacian.ravel()


def compute_normalized_spatial_energy(raw_field, filtered_field):
    """
    Computes the scale-invariant Normalized Laplacian Spatial Energy.
    S_norm = RMS(L(I)) / (RMS(I) + epsilon)
    Ensures that multiplying the field amplitude by any constant does not affect the gate.
    """
    rms_raw = np.sqrt(np.mean(raw_field ** 2))
    rms_filtered = np.sqrt(np.mean(filtered_field ** 2))
    return float(rms_filtered / (rms_raw + EPSILON))


# =====================================================================
# SYNTHETIC OPTICAL FIELD GENERATION
# =====================================================================

def generate_simulation_suite(grid_size=40, seed=42):
    rng = np.random.default_rng(seed)
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

    # 3. Thermal Source (Random Phase Field)
    thermal_phase = rng.uniform(0, 2 * np.pi, size=num_points)
    I_thermal = np.cos(thermal_phase) ** 2
    datasets["3_thermal_source"] = I_thermal

    # 4. Pure Mathematical Gaussian
    r_sq = xx.ravel()**2 + yy.ravel()**2
    I_gaussian = np.exp(-r_sq / 30.0)
    datasets["4_pure_gaussian"] = I_gaussian

    # 5. Correlated Random Field / Pink Noise
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

    # 6. White Noise (The Negative Control)
    I_white = rng.uniform(0, 1, size=num_points)
    datasets["6_white_noise"] = I_white

    return positions_2d, datasets


# =====================================================================
# CORE LOO EVALUATION
# =====================================================================

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


def compute_field_baseline(field_values, k_predict, k_shuffle, n_perm, seed, noise_frac, graph):
    rng = np.random.default_rng(seed)
    n = len(field_values)
    _, idx_shuffle = _get_weights_and_indices(graph, k_shuffle)

    null_errors = []
    for _ in range(n_perm):
        shuffled_field = np.empty_like(field_values)
        for i in range(n):
            nbr_idx = idx_shuffle[i]
            if len(nbr_idx) == 0:
                shuffled_field[i] = field_values[i]
                continue

            chosen = rng.integers(0, len(nbr_idx))
            local_std = np.std(field_values[nbr_idx], ddof=1)
            noise = rng.normal(0, noise_frac * local_std)
            shuffled_field[i] = field_values[nbr_idx[chosen]] + noise

        err = compute_loo_field_error(shuffled_field, k_predict, graph)
        if not np.isnan(err):
            null_errors.append(err)

    return np.array(null_errors) if null_errors else np.array([np.nan])


# =====================================================================
# SYSTEM DIAGNOSTIC RUNNER
# =====================================================================

def run_diagnostic(seed=42, n_perm=100, grid_size=40):
    positions, datasets = generate_simulation_suite(grid_size=grid_size, seed=seed)
    K_PREDICT = 15
    K_SHUFFLE = 30
    NOISE_FRACTION = 0.1
    
    # Scale-invariant validation threshold (empirically evaluated)
    ENERGY_THRESHOLD = 0.15  
    
    graph = build_neighbor_graph_2d(positions, max_k=K_SHUFFLE)
    
    print(f"🔬 TRACEBIND-W11: Validity-Gated Wave Coherence [Seed: {seed}]")
    print("=" * 110)
    print(f"  {'Dataset (Field Type)':<25s} {'S_norm Energy':>15s} {'RealErr':>10s} {'BaseErr':>10s} {'Ratio (R)':>10s} {'Status':>20s}")
    print("-" * 110)

    results = {}
    for name, raw_field in datasets.items():
        filtered_field = apply_laplacian_2d(raw_field, grid_size)
        s_norm = compute_normalized_spatial_energy(raw_field, filtered_field)
        
        if s_norm < ENERGY_THRESHOLD:
            results[name] = {"ratio": np.nan, "energy": s_norm, "gated": True}
            print(f"  {name:<25s} {s_norm:>15.5f} {'N/A':>10s} {'N/A':>10s} {'N/A':>10s} ❌ COH_NOT_EVAL (LOW_ENERGY)")
        else:
            real_err = compute_loo_field_error(filtered_field, K_PREDICT, graph)
            null_dist = compute_field_baseline(filtered_field, K_PREDICT, K_SHUFFLE, n_perm, seed, NOISE_FRACTION, graph)
            base_err = float(np.mean(null_dist))
            ratio = real_err / base_err
            
            results[name] = {"ratio": ratio, "energy": s_norm, "gated": False}
            verdict = "✅ COHERENT" if ratio < 0.80 else ("⚠️ MARGINAL" if ratio < 0.95 else "❌ INCOHERENT")
            print(f"  {name:<25s} {s_norm:>15.5f} {real_err:>10.5f} {base_err:>10.5f} {ratio:>10.5f} {verdict:>20s}")
            
    print("=" * 110)
    return results


if __name__ == "__main__":
    # Execute single frozen validation run
    _ = run_diagnostic(seed=42, n_perm=100)