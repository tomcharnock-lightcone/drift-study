"""Each sensor's drift error from its residuals against the one its noise
model gives.

usage: python src/plot_errors.py DRIFT.csv OUT.png

Sensors sorted by the ratio of the two. Left of the line where the two meet,
the residuals' scatter (sites, weather, the reference) outweighs the sensor's
own noise; right of it, the sensor's slow 1/f wander, as its chamber model
extrapolates it over a year, outweighs what the residuals show.
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import plot_style

plt = plot_style.plt


def main(drift: str, out: str) -> None:
    plot_style.apply()
    d = pd.read_csv(drift)
    d = d.assign(ratio=d["drift_se_noise_model_c_per_year"] / d["drift_se_residual_c_per_year"])
    d = d.sort_values("ratio").reset_index(drop=True)
    y = np.arange(len(d))
    fig, ax = plt.subplots(figsize=(6.5, 8.5))
    ax.hlines(y, d[["drift_se_residual_c_per_year", "drift_se_noise_model_c_per_year"]].min(axis=1),
              d[["drift_se_residual_c_per_year", "drift_se_noise_model_c_per_year"]].max(axis=1),
              color=plot_style.GRID, lw=2, zorder=1)
    for col, colour, label in [("drift_se_residual_c_per_year", plot_style.SERIES[0], "from the residuals (AR(1))"),
                               ("drift_se_noise_model_c_per_year", plot_style.SERIES[1], "from the sensor's noise model")]:
        ax.scatter(d[col], y, s=36, color=colour, edgecolors=plot_style.SURFACE, linewidths=1.5,
                   zorder=3, label=label)
    ax.set_yticks(y, d["sensor"], fontsize=7)
    ax.set_ylim(-1, len(d))
    ax.set_xlim(left=0)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("standard error of the drift (°C per year)")
    ax.legend(loc="upper right", title="drift error", title_fontsize=8, fontsize=8)
    ax.set_title("Where the drift's uncertainty comes from", loc="left")
    fig.tight_layout()
    fig.savefig(out, dpi=150)


if __name__ == "__main__":
    main(*sys.argv[1:])
