"""The residuals of the step fits around each battery swap, one column per
universe.

usage: python src/plot_swap_residuals.py BATTERY_SWAPS.csv NAME=FIT_INPUT.csv,DRIFT.csv [...] OUT.png

One row per sensor with a swap (src/battery_swaps.py), one column per
universe, each a fit with a step at the swap: the residuals of the sensor's
used days from 90 days before the first day on its new battery to 120 after,
and their 7-day running mean on either side of the swap. A step that fits
leaves them level across it; a seasonal cycle the fit misses shows as a
slope or a hump that a step cannot follow.
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import plot_style
from fit_drift import fitted

plt = plot_style.plt
BEFORE, AFTER = 90, 120


def main(battery_swaps: str, *rest: str) -> None:
    *entries, out = rest
    plot_style.apply()
    sw = pd.read_csv(battery_swaps).sort_values("sensor")
    columns = []
    for entry in entries:
        name, paths = entry.split("=", 1)
        input_path, drift_path = paths.split(",")
        columns.append((name, pd.read_csv(input_path, keep_default_na=False, na_values=[""]),
                        pd.read_csv(drift_path, keep_default_na=False, na_values=[""]).set_index("sensor")))
    fig, axes = plt.subplots(len(sw), len(columns), figsize=(3.4 * len(columns), 2.3 * len(sw)),
                             sharex=True, sharey="row", squeeze=False)
    for i, swap in enumerate(sw.itertuples()):
        for j, (name, table, drift) in enumerate(columns):
            ax = axes[i, j]
            used = table[(table["sensor"] == swap.sensor) & table["used"]]
            e = used["difference_c"].to_numpy() - fitted(used, drift.loc[swap.sensor])
            k = (pd.to_datetime(used["date"]) - pd.Timestamp(swap.first_new_date)).dt.days.to_numpy()
            near = (k >= -BEFORE) & (k < AFTER)
            ax.axhline(0, color=plot_style.GRID, lw=0.8, zorder=1)
            ax.axvline(0, color=plot_style.INK_2, lw=0.8, zorder=1)
            ax.scatter(k[near], e[near], s=3, color=plot_style.MUTED, linewidths=0, zorder=2)
            mean = pd.Series(e, index=k).sort_index().rolling(7, center=True).mean()
            for side in (mean[(mean.index >= -BEFORE) & (mean.index < 0)],
                         mean[(mean.index >= 0) & (mean.index < AFTER)]):
                ax.plot(side.index, side.to_numpy(), color=plot_style.SERIES[0], lw=1.5, zorder=3)
            if i == 0:
                ax.set_title(name.replace("_", " "), loc="left")
            if j == 0:
                ax.set_ylabel(f"{swap.sensor} residual (°C)")
            if i == len(sw) - 1:
                ax.set_xlabel("days from the first day on the new battery")
    fig.suptitle("Residuals of a step fit around each battery swap, with a 7-day running mean",
                 x=0.01, ha="left", fontsize=9, color=plot_style.INK)
    fig.tight_layout()
    fig.savefig(out, dpi=150)


if __name__ == "__main__":
    main(*sys.argv[1:])
