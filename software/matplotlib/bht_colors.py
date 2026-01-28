"""
BHT Berlin Official Colors

Official color definitions for BHT Berlin branding.
You can use these constants for consistent theming 
in plots and figures but its not mandatory.

Usage:
    from bht_colors import BHT_COLORS, GRAY_SCALE

    plt.bar(..., color=BHT_COLORS["blue"])
"""

# Primary BHT colors - not mandatory to use these
BHT_COLORS = {
    "gray": "#555555",  # bhtGray (0.333, 0.333, 0.333) - base gray
    "turquoise": "#00A0AA",  # bhtTurquoise (0, 0.627, 0.666)
    "cyan": "#00A0AA",  # bhtCyan (same as turquoise)
    "yellow": "#FFC900",  # bhtYellow (1, 0.788, 0)
    "red": "#EA3B06",  # bhtRed (0.918, 0.231, 0.025)
    "blue": "#004282",  # bhtBlue (0, 0.259, 0.510)
}

# Gray scale variants of bht gray (light to dark)
GRAY_SCALE = {
    "very_light": "#EEEEEE",
    "light": "#BBBBBB",
    "medium": "#888888",
    "base": "#555555",
    "dark": "#3B3B3B",
    "very_dark": "#222222",
}
