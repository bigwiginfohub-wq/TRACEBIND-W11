import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Set scientific publication style
if 'seaborn-v0_8-whitegrid' in plt.style.available:
    plt.style.use('seaborn-v0_8-whitegrid')
else:
    plt.style.use('default')

plt.rcParams.update({
    'font.size': 10,
    'axes.labelsize': 12,
    'axes.titlesize': 12,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'figure.titlesize': 14,
    'font.family': 'sans-serif'
})

RAW_FILE = r"C:\GaiaProject\data\TRACEBIND-W11\Candidate1\TRACEBIND_MC_SWEEP.csv"
FIG_OUT = r"C:\GaiaProject\data\TRACEBIND-W11\Candidate1\figures\Figure_01_Ratio_Distribution.png"

os.makedirs(os.path.dirname(FIG_OUT), exist_ok=True)

# 1. Load raw dataset and filter out gated runs
df = pd.read_csv(RAW_FILE)
df_clean = df[df["gated"] == 0].copy()

# 2. Hardcoded scientific dataset ordering & shortened, formal display names
dataset_order = [
    "1_ideal_coherent",
    "2_phase_noise_0.8",
    "3_thermal_source",
    "4_pure_gaussian",
    "5_pink_noise",
    "6_white_noise"
]

display_names = {
    "1_ideal_coherent": "Ideal Coherent",
    "2_phase_noise_0.8": "Phase Noise\n($\sigma = 0.8$)",
    "3_thermal_source": "Random Phase\n(Thermal-like)",
    "4_pure_gaussian": "Pure Gaussian",
    "5_pink_noise": "Pink Noise\n($1/f$)",
    "6_white_noise": "White Noise"
}

# 3. Calculate sample sizes (n) for each category to append to the x-tick labels
xtick_labels = []
for ds in dataset_order:
    n_samples = len(df_clean[df_clean["dataset"] == ds])
    xtick_labels.append(f"{display_names[ds]}\n(n={n_samples})")

# 4. Initialize Plot
fig, ax = plt.subplots(figsize=(10, 6.5))

# Draw the main Violin Plot (shaded distribution shapes)
sns.violinplot(
    data=df_clean, 
    x="dataset", 
    y="ratio", 
    hue="dataset",
    order=dataset_order,
    palette="muted", 
    inner=None,  
    cut=0,
    legend=False,
    ax=ax
)

# 5. Overlay the Journal-Style Narrow Boxplot
sns.boxplot(
    data=df_clean,
    x="dataset",
    y="ratio",
    order=dataset_order,
    width=0.12,
    showcaps=True,
    boxprops={'facecolor': 'white', 'edgecolor': '0.3', 'linewidth': 1.2},
    whiskerprops={'color': '0.3', 'linewidth': 1.2},
    capprops={'color': '0.3', 'linewidth': 1.2},
    medianprops={'color': 'crimson', 'linewidth': 1.8},
    showfliers=False,  
    ax=ax
)

# 6. Explicitly set tick locations before defining tick labels to eliminate UserWarning
ax.set_xticks(range(len(dataset_order)))
ax.set_xticklabels(xtick_labels, rotation=15, ha="right")

# 7. Dynamic y-axis setting & centered placeholder for Dataset 4 (Gaussian)
ax.set_ylim(0.25, 1.30)
ymin, ymax = ax.get_ylim()
y_center = ymin + 0.45 * (ymax - ymin)

ax.text(
    3, y_center, "No Evaluations\n\nAll realization passes\nflagged as low-energy\nby validity gate.", 
    ha='center', va='center', fontsize=9, color='0.4', style='italic',
    bbox=dict(facecolor='0.95', edgecolor='0.8', boxstyle='round,pad=1.0', linestyle='--')
)

# 8. Null expectation baseline reference
ax.axhline(y=1.0, color="dimgray", linestyle="--", linewidth=1.5, label="R = 1.0 (Null Baseline Limit)")

# 9. Formatted Labels and Metadata
ax.set_title("TRACEBIND-W11-C1: Monte Carlo Distribution of the Coherence Ratio ($R$)", pad=15)
ax.set_xlabel("Synthetic Benchmark Environment", labelpad=18)
ax.set_ylabel(r"Coherence Ratio ($R = E_{\text{real}} / \mu_{\text{baseline}}$)", labelpad=10)
ax.legend(loc="upper left", frameon=True)


# Corrected, formal peer-reviewed caption
caption_text = (
    "Note: Dataset '4_pure_gaussian' was systematically excluded by the validity gate because "
    "normalized spatial energy remained below the evaluation threshold across all tested Monte Carlo realizations."
)
plt.figtext(0.1, 0.02, caption_text, wrap=True, horizontalalignment='left', fontsize=9, style='italic', color='0.3')

plt.tight_layout()
plt.subplots_adjust(bottom=0.22)  # Changed from 0.18 to 0.22 to give the caption room 

# Save to target directory
plt.savefig(FIG_OUT, dpi=300)
plt.close()


print(f"🎯 Publication-quality Figure 1 saved to:\n   {FIG_OUT}")