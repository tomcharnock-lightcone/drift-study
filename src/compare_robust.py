"""What a step at each battery swap and a robust fit do to the drifts.

usage: python src/compare_robust.py BATTERY_SWAPS.csv NAME=DRIFT.csv,FIT_INPUT.csv,COUNTERPART [...] OUT.json

Each NAME is a universe, with its drift table and the table it was fitted
to (src/differences.py's, or the calibration's), and COUNTERPART the name
of an earlier entry that is the same fit without the steps and the robust
fit, or `-`. The first entry is the one the others are compared with, and
its name stands in the keys that depend on it.

For each: how far the drifts move from the first entry's
(src/compare_universes.py). Where it fits by Huber's M-estimate: how many
days it down-weighted, in all and as a share of the days fitted (with
c = 1.345 it would down-weight about 18% of Gaussian residuals). Where it
steps at battery swaps: the largest change from its counterpart among the
sensors without a step, and for each sensor with one, flat as
`<sensor>_<field>`, its drift and its counterpart's, the step and its
error, and the mean residual of the fit over the 28 days before the first
day on the new battery and the 28 from it: a step that fits leaves both
near zero. Above them, the swaps found (src/battery_swaps.py).
"""

from __future__ import annotations

import json
import sys

import pandas as pd

from compare_universes import changes
from fit_drift import fitted

WINDOW = 28  # days either side of a swap


def residual_means(days: pd.DataFrame, row: pd.Series, first_new: str) -> tuple[float, float]:
    used = days[days["used"]]
    e = used["difference_c"].to_numpy() - fitted(used, row)
    k = (pd.to_datetime(used["date"]) - pd.Timestamp(first_new)).dt.days.to_numpy()
    return float(e[(k >= -WINDOW) & (k < 0)].mean()), float(e[(k >= 0) & (k < WINDOW)].mean())


def main(battery_swaps: str, *rest: str) -> None:
    *entries, out = rest
    sw = pd.read_csv(battery_swaps)
    first_new = dict(zip(sw["sensor"], sw["first_new_date"]))
    report: dict = {"battery_swaps": {
        "n_swaps": len(sw),
        "sensors": ";".join(sorted(sw["sensor"])),
        "dates": ";".join(f"{k}:{d}" for k, d in sorted(zip(sw["sensor"], sw["swap_date"]))),
    }}
    drifts: dict[str, pd.DataFrame] = {}
    base = against = None
    for entry in entries:
        name, paths = entry.split("=", 1)
        drift_path, input_path, counterpart = paths.split(",")
        alt = pd.read_csv(drift_path, keep_default_na=False, na_values=[""]).set_index("sensor")
        drifts[name] = alt
        if base is None:
            base, against = alt, name
        item = changes(base, alt, name, against)
        if "n_days_downweighted" in alt:
            item["n_days_downweighted"] = int(alt["n_days_downweighted"].sum())
            item["share_days_downweighted"] = round(
                float(alt["n_days_downweighted"].sum() / alt["n_days_used"].sum()), 3)
        if "n_battery_swaps" in alt:
            other = drifts[counterpart]
            days = pd.read_csv(input_path, keep_default_na=False, na_values=[""])
            unstepped = alt.index[alt["n_battery_swaps"] == 0]
            item["counterpart"] = counterpart
            item["max_abs_drift_change_unstepped_vs_counterpart_c_per_year"] = round(float(
                (alt.loc[unstepped, "drift_c_per_year"] - other.loc[unstepped, "drift_c_per_year"])
                .abs().max()), 4)
            for sensor in alt.index[alt["n_battery_swaps"] > 0]:
                a = alt.loc[sensor]
                before, after = residual_means(days[days["sensor"] == sensor], a, first_new[sensor])
                item[f"{sensor}_counterpart_drift_c_per_year"] = round(float(other.loc[sensor, "drift_c_per_year"]), 4)
                item[f"{sensor}_drift_c_per_year"] = round(float(a["drift_c_per_year"]), 4)
                item[f"{sensor}_drift_se_c_per_year"] = round(float(a["drift_se_c_per_year"]), 4)
                item[f"{sensor}_step_dates"] = a["battery_step_dates"]
                item[f"{sensor}_steps_c"] = str(a["battery_steps_c"])
                item[f"{sensor}_steps_se_c"] = str(a["battery_steps_se_c"])
                item[f"{sensor}_residual_before_swap_c"] = round(before, 3)
                item[f"{sensor}_residual_after_swap_c"] = round(after, 3)
        report[name] = item
    with open(out, "w") as fh:
        json.dump(report, fh, indent=2)
        fh.write("\n")


if __name__ == "__main__":
    main(*sys.argv[1:])
