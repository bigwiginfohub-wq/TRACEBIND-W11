import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import seaborn as sns

# Set scientific style
if 'seaborn-v0_8-whitegrid' in plt.style.available:
    plt.style.use('seaborn-v0_8-whitegrid')
else:
    plt.style.use('default')

plt.rcParams.update({
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'font.family': 'sans-serif'
})

RAW_FILE = r"C:\GaiaProject\data\TRACEBIND-W11\Candidate1\TRACEBIND_MC_SWEEP.csv"
FIG_OUT = r"C:\GaiaProject\data\TRACEBIND-W11\Candidate1\figures\Figure_02_Parameter_Sensitivity.png"

os.makedirs(os.path.dirname(FIG_OUT), exist_ok=True)

# 1. Load raw dataset and drop gated cases
df = pd.read_csv(RAW_FILE)
df_clean = df[df["gated"] == 0].copy()

# Map grid sizes to explicit resolution strings
grid_map = {20: "20×20", 40: "40×40", 80: "80×80"}
df_clean["grid_resolution"] = df_clean["grid_size"].map(grid_map)

active_datasets = [
    "1_ideal_coherent",
    "2_phase_noise_0.8",
    "3_thermal_source",
    "5_pink_noise",
    "6_white_noise"
]

display_names = {
    "1_ideal_coherent": "Ideal Coherent",
    "2_phase_noise_0.8": "Phase Noise ($\sigma = 0.8$)",
    "3_thermal_source": "Random Phase (Thermal-like)",
    "5_pink_noise": "Pink Noise ($1/f$)",
    "6_white_noise": "White Noise"
}

# 2. Mathematically correct TwoSlopeNorm to force balanced color scaling around R=1.0
global_min = df_clean["ratio"].min()
global_max = df_clean["ratio"].max()

norm = mcolors.TwoSlopeNorm(
    vmin=global_min,
    vcenter=1.0,
    vmax=global_max
)

# Set up a 2x3 subplot structure
fig, axes = plt.subplots(2, 3, figsize=(15, 9.5), gridspec_kw={'width_ratios': [1, 1, 1]})
axes = axes.flatten()

# 3. Draw consistent subplots
for i, ds_name in enumerate(active_datasets):
    ax = axes[i]
    ds_data = df_clean[df_clean["dataset"] == ds_name]
    
    # Calculate the mean R-ratio across grid resolution and neighborhood size (k)
    pivot_table = ds_data.pivot_table(
        values="ratio", 
        index="grid_resolution", 
        columns="k_predict", 
        aggfunc="mean"
    )
    
    # Reindex to guarantee all three spatial resolutions are represented
    pivot_table = pivot_table.reindex(["20×20", "40×40", "80×80"])
    
    # Draw heatmaps using TwoSlopeNorm (cbar=False, as we use a shared colorbar)
    sns.heatmap(
        pivot_table,
        annot=True,
        fmt=".3f",
        cmap="RdBu_r",
        norm=norm,
        cbar=False,
        linewidths=0.5,
        ax=ax
    )
    
    # Explicitly check if the 80x80 row is completely empty/NaN (gated)
    if pivot_table.loc["80×80"].isna().all():
        ax.text(
            1.5, 2.5, "Gated (Low Energy)", 
            ha='center', va='center', fontsize=9, color='0.5', style='italic',
            bbox=dict(facecolor='0.97', edgecolor='0.8', boxstyle='round,pad=0.3', linestyle=':')
        )
    
    ax.set_title(f"{display_names[ds_name]}", fontsize=11, fontweight='bold', pad=8)
    ax.set_xlabel("Neighborhood Size ($k$)", fontsize=9)
    ax.set_ylabel("Grid Resolution", fontsize=9)

# 4. Create the Single, Unified Colorbar using the exact same norm
cbar_ax = fig.add_axes([0.93, 0.15, 0.015, 0.7])  # [left, bottom, width, height]
sm = plt.cm.ScalarMappable(cmap="RdBu_r", norm=norm)
sm.set_array([])

# Customize the shared colorbar ticks and label
cbar = fig.colorbar(sm, cax=cbar_ax)
cbar.set_label("Mean Coherence Ratio ($R = E_{\\text{real}} / \\mu_{\\text{baseline}}$)", rotation=275, labelpad=15, fontsize=11)

# 5. Transform the 6th subplot into a safe, text-only Interpretation Guide
ax_legend = axes[-1]
ax_legend.axis('off')

legend_text = (
    "TRACEBIND-W11-C1\n"
    "Interpretation Guide\n\n"
    "R < 1.0 (Blue Range):\n"
    "  Spatial coherence detected.\n"
    "  (Coherent wave structure dominates\n"
    "   the localized permutation space)\n\n"
    "R = 1.0 (White Zone):\n"
    "  Null benchmark limit.\n"
    "  (Indistinguishable from stochastic baseline)\n\n"
    "R > 1.0 (Red Range):\n"
    "  Stochastic behavior.\n"
    "  (Prediction error exceeds the\n"
    "   localized baseline null model)"
)

ax_legend.text(
    0.45, 0.5, legend_text, 
    ha='center', va='center', fontsize=10, style='normal', color='0.2',
    bbox=dict(facecolor='0.98', edgecolor='0.8', boxstyle='round,pad=1.2', linestyle='-')
)

plt.suptitle("Parameter Sensitivity of TRACEBIND-W11", fontsize=14, y=0.97)

# Leave space on the right for the colorbar
plt.subplots_adjust(right=0.90, hspace=0.3, wspace=0.3)

# Save high-resolution figure
plt.savefig(FIG_OUT, dpi=300, bbox_inches='tight')
plt.close()

print(f"🎯 Perfect, mathematically rigorous Figure 2 saved to:\n   {FIG_OUT}")