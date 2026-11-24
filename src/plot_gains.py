"""Each sensor's calibration gain with its 95% interval, one panel per window,
against the gains the Freiburg stations show over the same window.

usage: python src/plot_gains.py NAME=COEFFICIENTS.csv [NAME=COEFFICIENTS.csv ...] OUT.png

COEFFICIENTS are calibration/src/calibrate.py's tables under the gain
model, NAME the window (its id, underscores for spaces). Sensors are sorted
by their gain in the last table, in every panel. The grey band is the 5th–95th
percentile of the stations' gains against the reference: a gain inside it is
what two sites answering the weather differently give. The panels share an
axis wide enough for every gain and every band; an interval wider than that
is cut at the edge.
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import plot_style

plt = plot_style.plt


def main(*args: str) -> None:
    *pairs, out = args
    plot_style.apply()
    tables = [(name, pd.read_csv(path)) for name, path in (p.split("=", 1) for p in pairs)]
    last = tables[-1][1]
    order = last[last["kind"] == "sensor"].sort_values("gain")["name"].tolist()
    y = np.arange(len(order))
    bands = [np.percentile(c.loc[c["kind"] == "station", "gain"], [5, 95]) for _, c in tables]
    gains = np.concatenate([c.loc[c["kind"] == "sensor", "gain"] for _, c in tables])
    lo = min(min(b[0] for b in bands), gains.min()) - 0.03
    hi = max(max(b[1] for b in bands), gains.max()) + 0.03
    fig, axes = plt.subplots(1, len(tables), figsize=(3.4 * len(tables), 8.5), sharex=True,
                             sharey=True)
    for ax, (name, c), (low, high) in zip(np.atleast_1d(axes), tables, bands):
        sensors = c[c["kind"] == "sensor"].set_index("name").loc[order]
        ax.axvspan(low, high, color=plot_style.BAND, zorder=0, lw=0)
        ax.axvline(1, color=plot_style.INK_2, lw=0.8, zorder=1)
        ax.hlines(y, sensors["gain_ci95_low"], sensors["gain_ci95_high"],
                  color=plot_style.SERIES[0], lw=2, zorder=2)
        ax.scatter(sensors["gain"], y, s=30, color=plot_style.SERIES[0],
                   edgecolors=plot_style.SURFACE, linewidths=1.5, zorder=3)
        start, last_day = sensors["window_start"].iloc[0], sensors["window_last"].iloc[0]
        ax.set_title(f"{name.replace('_', ' ')}: {start} to {last_day}", loc="left")
        ax.grid(axis="y", visible=False)
        ax.set_xlabel("gain against the reference")
    first = np.atleast_1d(axes)[0]
    first.set_yticks(y, order, fontsize=7)
    first.set_ylim(-1, len(order))
    first.set_xlim(lo, hi)
    fig.suptitle("Calibration gain per sensor, with 95% interval, by window", x=0.01, y=0.995,
                 ha="left", va="top", fontsize=9, color=plot_style.INK)
    fig.text(0.01, 0.972, "grey: Freiburg's other stations against the reference, 5th–95th "
             "percentile of their gains; intervals wider than the axis are cut at its edge",
             ha="left", va="top", fontsize=7.5, color=plot_style.INK_2)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out, dpi=150)


if __name__ == "__main__":
    main(*sys.argv[1:])
