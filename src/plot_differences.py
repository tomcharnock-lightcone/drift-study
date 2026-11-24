"""Every sensor's daily difference from the reference, with its fitted drift.

usage: python src/plot_differences.py DIFFERENCES.csv DRIFT.csv OUT.png

One panel per sensor. Used days are dots, excluded days hollow rings (all of
them where they fall in the panel's range); the line is the fitted drift
a + b·t, drawn at the reference's mean temperature under the model with a
temperature term, and with its steps where the fit has a step at each
battery swap. Panels share their x axis; each has its own y range,
since offsets differ by more than drifts do.
"""

from __future__ import annotations

import sys

import matplotlib.dates as mdates
import numpy as np
import pandas as pd

import plot_style
from fit_drift import DAYS_PER_YEAR, MID_YEAR

plt = plot_style.plt


def main(differences: str, drift: str, out: str) -> None:
    plot_style.apply()
    d = pd.read_csv(differences, parse_dates=["date"], keep_default_na=False, na_values=[""])
    fits = pd.read_csv(drift).set_index("sensor")
    sensors = sorted(d["sensor"].unique())
    ncol = 5
    nrow = int(np.ceil(len(sensors) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(12, 1.9 * nrow), sharex=True)
    ends = pd.to_datetime(["2023-01-01", "2023-12-31"])
    t_ends = (ends - MID_YEAR).days / DAYS_PER_YEAR
    daily = pd.date_range(ends[0], ends[1], freq="D")
    t_daily = (daily - MID_YEAR).days / DAYS_PER_YEAR
    for ax, sensor in zip(axes.flat, sensors):
        x = d[d["sensor"] == sensor]
        used = x[x["used"]]
        lo, hi = used["difference_c"].quantile([0.0, 1.0])
        pad = 0.15 * (hi - lo)
        ax.set_ylim(lo - pad, hi + pad)
        ax.scatter(used["date"], used["difference_c"], s=3, color=plot_style.MUTED,
                   linewidths=0, zorder=2)
        dropped = x[~x["used"] & x["difference_c"].notna()]
        ax.scatter(dropped["date"], dropped["difference_c"].clip(lo - pad * 0.8, hi + pad * 0.8),
                   s=9, facecolors="none", edgecolors=plot_style.INK_2, linewidths=0.6, zorder=3)
        f = fits.loc[sensor]
        x_line, line = ends, f["offset_c"] + f["drift_c_per_year"] * t_ends
        if isinstance(f.get("battery_step_dates"), str):
            x_line, line = daily, f["offset_c"] + f["drift_c_per_year"] * t_daily
            for date, size in zip(f["battery_step_dates"].split(";"),
                                  str(f["battery_steps_c"]).split(";")):
                line = line + float(size) * (daily >= pd.Timestamp(date))
        ax.plot(x_line, line, color=plot_style.SERIES[0], zorder=4)
        ax.set_title(f"{sensor}   {f['drift_c_per_year']:+.2f} ± {f['drift_se_c_per_year']:.2f} °C/yr",
                     loc="left", pad=3)
        ax.tick_params(labelsize=7)
    for ax in axes.flat[len(sensors):]:
        ax.set_visible(False)
    for ax in axes[:, 0]:
        ax.set_ylabel("sensor − ref (°C)", fontsize=7)
    for ax in axes[-1, :]:
        ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    handles = [
        plt.Line2D([], [], ls="", marker="o", ms=3, color=plot_style.MUTED, label="daily difference, used"),
        plt.Line2D([], [], ls="", marker="o", ms=4, mfc="none", mec=plot_style.INK_2,
                   label="excluded (pinned to the panel edge if beyond it)"),
        plt.Line2D([], [], color=plot_style.SERIES[0], label="fitted drift"),
    ]
    fig.legend(handles=handles, loc="upper left", ncol=3, bbox_to_anchor=(0.01, 1.0))
    fig.tight_layout(rect=(0, 0, 1, 0.975))
    fig.savefig(out, dpi=150)


if __name__ == "__main__":
    main(*sys.argv[1:])
