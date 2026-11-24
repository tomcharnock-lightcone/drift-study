"""Each sensor's drift with its 95% interval, against what two maintained
stations show against each other over the same year.

usage: python src/plot_drift.py DRIFT.csv REFERENCE_CHECK.json DRIFT_MODEL OUT.png

Sensors sorted by drift. The grey band is the 5th–95th percentile of the
apparent drifts of Freiburg's other stations against the reference, under
the same drift model (reference_check): a drift inside it cannot be told
apart from two sites responding differently to one year's weather.
"""

from __future__ import annotations

import json
import sys

import pandas as pd

import plot_style

plt = plot_style.plt


def main(drift: str, reference_check: str, model: str, out: str) -> None:
    plot_style.apply()
    d = pd.read_csv(drift).sort_values("drift_c_per_year").reset_index(drop=True)
    floor = json.load(open(reference_check))["stations_vs_reference"]["summary"][model]
    fig, ax = plt.subplots(figsize=(6.5, 8.5))
    ax.axvspan(floor["drift_p05_c_per_year"], floor["drift_p95_c_per_year"], color=plot_style.BAND,
               zorder=0, lw=0)
    ax.axvline(0, color=plot_style.INK_2, lw=0.8, zorder=1)
    y = range(len(d))
    ax.hlines(y, d["drift_ci95_low_c_per_year"], d["drift_ci95_high_c_per_year"],
              color=plot_style.SERIES[0], lw=2, zorder=2)
    ax.scatter(d["drift_c_per_year"], y, s=36, color=plot_style.SERIES[0],
               edgecolors=plot_style.SURFACE, linewidths=1.5, zorder=3)
    ax.set_yticks(list(y), d["sensor"], fontsize=7)
    ax.set_ylim(-1, len(d))
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("drift against the reference (°C per year), with 95% interval")
    ax.text(floor["drift_p95_c_per_year"], -0.6,
            " grey: Freiburg stations against the reference,\n 5th–95th percentile of their drifts",
            ha="left", va="bottom", fontsize=7, color=plot_style.INK_2)
    ax.set_title(f"Linear drift per sensor ({model.replace('_', ' ')})", loc="left")
    fig.tight_layout()
    fig.savefig(out, dpi=150)


if __name__ == "__main__":
    main(*sys.argv[1:])
