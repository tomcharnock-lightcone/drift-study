"""One look for every figure of the analysis.

Two series at most, in fixed order: blue, then orange (the first two slots of
a colour-blind-checked categorical order). Text in ink, never in a series
colour; grids and axes recessive.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#8a8985"
GRID = "#e4e3df"
BAND = "#e9e8e4"
SERIES = ("#2a78d6", "#eb6834")


def apply() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "axes.edgecolor": GRID,
            "axes.labelcolor": INK_2,
            "axes.titlecolor": INK,
            "axes.grid": True,
            "grid.color": GRID,
            "grid.linewidth": 0.6,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "xtick.color": INK_2,
            "ytick.color": INK_2,
            "xtick.major.size": 0,
            "ytick.major.size": 0,
            "text.color": INK,
            "font.size": 9,
            "axes.titlesize": 9,
            "legend.frameon": False,
            "lines.linewidth": 2,
        }
    )
