"""
Test script for BHT matplotlib style configuration.
Creates a sample figure to verify styling and dimensions.
"""

import matplotlib.pyplot as plt
import numpy as np
from matplotlib_style import (
    FONTSIZE,
    FONTSIZE_SMALL,
    FIGURE_WIDTH,
    apply_thesis_style,
)
from bht_colors import BHT_COLORS

# =============================================================================
# Configuration
# =============================================================================
OUTPUT_FILE = "../../figures/test_figure.svg"
FIGURE_HEIGHT = 4.0  # inches
DPI = 300

# Sample data
CATEGORIES = ["Method A", "Method B", "Method C", "Method D"]
VALUES = [23.5, 31.2, 18.7, 27.9]

# =============================================================================
# Create figure
# =============================================================================
apply_thesis_style()

fig, ax = plt.subplots(figsize=(FIGURE_WIDTH, FIGURE_HEIGHT))

# Create bar chart
bars = ax.bar(
    CATEGORIES,
    VALUES,
    color=[
        BHT_COLORS["blue"],
        BHT_COLORS["turquoise"],
        BHT_COLORS["yellow"],
        BHT_COLORS["red"],
    ],
    width=0.6,
)

# Add value labels on bars
for bar in bars:
    height = bar.get_height()
    ax.text(
        bar.get_x() + bar.get_width() / 2.0,
        height,
        f"{height:.1f}",
        ha="center",
        va="bottom",
        fontsize=FONTSIZE_SMALL,
    )

# Styling
ax.set_ylabel("Performance Score")
ax.set_title("Sample BHT Thesis Figure")
ax.set_ylim(0, 35)
ax.grid(axis="y", alpha=0.3, linestyle="--", linewidth=0.5)
ax.set_axisbelow(True)

# Save figure
plt.savefig(OUTPUT_FILE, dpi=DPI, bbox_inches="tight")
print(f"Figure saved to: {OUTPUT_FILE}")
print(f"Figure dimensions: {FIGURE_WIDTH} × {FIGURE_HEIGHT} inches")

plt.close()
