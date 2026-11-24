"""Each sensor's drift with and without the temperature term, side by side.

usage: python src/plot_model_comparison.py TIME_ONLY.csv WITH_TEMPERATURE.csv OUT.png

Sensors sorted by the time-only drift; each pair of intervals is offset
vertically so both stay visible.
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import plot_style

plt = plot_style.plt


def main(time_only: str, with_temperature: str, out: str) -> None:
    plot_style.apply()
    a = pd.read_csv(time_only).set_index("sensor")
    b = pd.read_csv(with_temperature).set_index("sensor")
    order = a["drift_c_per_year"].sort_values().index
    y = np.arange(len(order))
    fig, ax = plt.subplots(figsize=(6.5, 9))
    ax.axvline(0, color=plot_style.INK_2, lw=0.8, zorder=1)
    for table, colour, dy, label in [(a, plot_style.SERIES[0], 0.17, "time only"),
                                     (b, plot_style.SERIES[1], -0.17, "time and temperature")]:
        t = table.loc[order]
        ax.hlines(y + dy, t["drift_ci95_low_c_per_year"], t["drift_ci95_high_c_per_year"],
                  color=colour, lw=2, zorder=2)
        ax.scatter(t["drift_c_per_year"], y + dy, s=30, color=colour, edgecolors=plot_style.SURFACE,
                   linewidths=1.5, zorder=3, label=label)
    ax.set_yticks(y, order, fontsize=7)
    ax.set_ylim(-1, len(order))
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("drift against the reference (°C per year), with 95% interval")
    ax.legend(loc="lower right", title="drift model", title_fontsize=8, fontsize=8)
    ax.set_title("How a temperature-dependent bias moves the drift", loc="left")
    fig.tight_layout()
    fig.savefig(out, dpi=150)


if __name__ == "__main__":
    main(*sys.argv[1:])
