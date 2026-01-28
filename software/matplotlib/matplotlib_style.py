"""
BHT Thesis Matplotlib Style Configuration

Matplotlib styling for thesis figures that matches LaTeX formatting.
Import this module in plotting scripts for consistent theming.

Usage:
    from matplotlib_style import FONTSIZE, FONTSIZE_SMALL, FIGURE_WIDTH, apply_thesis_style

    apply_thesis_style()  # Call once at start of script
    fig, ax = plt.subplots(figsize=(FIGURE_WIDTH, 4))
"""

import matplotlib.pyplot as plt

# =============================================================================
# Figure dimensions (matches LaTeX \linewidth of 426.79pt)
# =============================================================================
FIGURE_WIDTH = 5.7  # inches (adjusted to fit LaTeX linewidth with margins)

# =============================================================================
# Font sizes
# =============================================================================
FONTSIZE = 9  # Standard size for most text (title, axis labels, ticks, legend)
FONTSIZE_SMALL = 7  # Smaller annotations (e.g., value labels on bars)
FONTSIZE_XSMALL = 6  # Very small annotations (e.g., dense bar charts)


def apply_thesis_style():
    """Apply thesis-consistent matplotlib style. Call once at start of script."""
    plt.rcParams.update(
        {
            # Font family: Latin Modern Roman with fallbacks
            "font.family": "serif",
            "font.serif": ["Latin Modern Roman", "Times New Roman", "DejaVu Serif"],
            # Mathtext with Computer Modern for numerals
            "mathtext.fontset": "cm",
            "mathtext.rm": "serif",
            "mathtext.it": "serif:italic",
            "mathtext.bf": "serif:bold",
            # No LaTeX required
            "text.usetex": False,
            # Font sizes
            "font.size": FONTSIZE,
            "axes.labelsize": FONTSIZE,
            "axes.titlesize": FONTSIZE,
            "xtick.labelsize": FONTSIZE,
            "ytick.labelsize": FONTSIZE,
            "legend.fontsize": FONTSIZE,
            # Misc
            "axes.unicode_minus": False,
            # Axis lines
            "axes.linewidth": 0.8,
            "xtick.major.width": 0.8,
            "ytick.major.width": 0.8,
            "xtick.minor.width": 0.6,
            "ytick.minor.width": 0.6,
            "xtick.major.pad": 6,
            "ytick.major.pad": 6,
            "figure.constrained_layout.use": True,
        }
    )
