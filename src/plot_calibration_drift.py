"""Each sensor's drift uncalibrated and calibrated with a gain, one panel per
window.

usage: python src/plot_calibration_drift.py BASELINE.csv NAME=DRIFT.csv [NAME=DRIFT.csv ...] OUT.png

BASELINE is the uncalibrated drift table, each DRIFT one fitted to
readings calibrated with a gain and an offset over the window NAME (its id,
underscores for spaces). Sensors sorted by the uncalibrated drift; each
pair of intervals is offset vertically so both stay visible.
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import plot_style

plt = plot_style.plt


def main(baseline: str, *rest: str) -> None:
    *pairs, out = rest
    plot_style.apply()
    base = pd.read_csv(baseline).set_index("sensor")
    order = base["drift_c_per_year"].sort_values().index
    y = np.arange(len(order))
    fig, axes = plt.subplots(1, len(pairs), figsize=(3.4 * len(pairs), 9), sharex=True, sharey=True)
    for ax, pair in zip(np.atleast_1d(axes), pairs):
        name, path = pair.split("=", 1)
        cal = pd.read_csv(path).set_index("sensor")
        ax.axvline(0, color=plot_style.INK_2, lw=0.8, zorder=1)
        for table, colour, dy, label in [(base, plot_style.SERIES[0], 0.17, "uncalibrated"),
                                         (cal, plot_style.SERIES[1], -0.17, "gain and offset")]:
            t = table.loc[order]
            ax.hlines(y + dy, t["drift_ci95_low_c_per_year"], t["drift_ci95_high_c_per_year"],
                      color=colour, lw=2, zorder=2)
            ax.scatter(t["drift_c_per_year"], y + dy, s=26, color=colour,
                       edgecolors=plot_style.SURFACE, linewidths=1.5, zorder=3, label=label)
        ax.set_title(f"calibrated over {name.replace('_', ' ')}", loc="left")
        ax.grid(axis="y", visible=False)
        ax.set_xlabel("drift (°C per year), with 95% interval")
    first = np.atleast_1d(axes)[0]
    first.set_yticks(y, order, fontsize=7)
    first.set_ylim(-1, len(order))
    np.atleast_1d(axes)[-1].legend(loc="lower right", fontsize=8)
    fig.suptitle("How calibrating a gain moves the drift", x=0.01, ha="left", fontsize=9,
                 color=plot_style.INK)
    fig.tight_layout()
    fig.savefig(out, dpi=150)


if __name__ == "__main__":
    main(*sys.argv[1:])
