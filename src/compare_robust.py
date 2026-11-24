"""What a step at each battery swap and a robust fit do to the drifts.

usage: python src/compare_robust.py BASELINE.csv BATTERY_SWAPS.csv NAME=DRIFT.csv [NAME=DRIFT.csv ...] OUT.json

For each alternative against the baseline: how far the drifts move
(src/compare_universes.py). Where the alternative steps at battery swaps,
for each sensor with a step: its drift with and without the step, the step
and its error, flat as `<sensor>_<field>`; and the largest change among the
sensors without one. Where it fits by Huber's
M-estimate, how many days it down-weighted, in all, as a share of the days
fitted and at most for one sensor; with c = 1.345 it would down-weight
about 18% of Gaussian residuals. Above them, the swaps found (src/battery_swaps.py).
"""

from __future__ import annotations

import json
import sys

import pandas as pd

from compare_universes import changes


def main(baseline: str, battery_swaps: str, *rest: str) -> None:
    *pairs, out = rest
    base = pd.read_csv(baseline).set_index("sensor")
    sw = pd.read_csv(battery_swaps)
    report: dict = {"battery_swaps": {
        "n_swaps": len(sw),
        "sensors": ";".join(sorted(sw["sensor"])),
        "dates": ";".join(f"{k}:{d}" for k, d in sorted(zip(sw["sensor"], sw["swap_date"]))),
    }}
    for pair in pairs:
        name, path = pair.split("=", 1)
        alt = pd.read_csv(path, keep_default_na=False, na_values=[""]).set_index("sensor")
        item = changes(base, alt, name)
        if "n_battery_swaps" in alt:
            unstepped = alt.index[alt["n_battery_swaps"] == 0]
            item["max_abs_drift_change_unstepped_c_per_year"] = round(float(
                (alt.loc[unstepped, "drift_c_per_year"] - base.loc[unstepped, "drift_c_per_year"])
                .abs().max()), 4)
            for sensor in alt.index[alt["n_battery_swaps"] > 0]:
                a = alt.loc[sensor]
                item[f"{sensor}_baseline_drift_c_per_year"] = round(float(base.loc[sensor, "drift_c_per_year"]), 4)
                item[f"{sensor}_drift_c_per_year"] = round(float(a["drift_c_per_year"]), 4)
                item[f"{sensor}_drift_se_c_per_year"] = round(float(a["drift_se_c_per_year"]), 4)
                item[f"{sensor}_step_dates"] = a["battery_step_dates"]
                item[f"{sensor}_steps_c"] = str(a["battery_steps_c"])
                item[f"{sensor}_steps_se_c"] = str(a["battery_steps_se_c"])
        if "n_days_downweighted" in alt:
            item["n_days_downweighted"] = int(alt["n_days_downweighted"].sum())
            item["share_days_downweighted"] = round(
                float(alt["n_days_downweighted"].sum() / alt["n_days_used"].sum()), 3)
            item["max_days_downweighted_per_sensor"] = int(alt["n_days_downweighted"].max())
        report[name] = item
    with open(out, "w") as fh:
        json.dump(report, fh, indent=2)
        fh.write("\n")


if __name__ == "__main__":
    main(*sys.argv[1:])
