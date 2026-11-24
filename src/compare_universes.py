"""How far each alternative universe moves the sensors' drifts from the baseline.

usage: python src/compare_universes.py BASELINE.csv NAME=DRIFT.csv [NAME=DRIFT.csv ...] OUT.json

For each alternative: the largest and the median change in drift over the
sensors, which sensor changes most, the largest change in units of the
baseline's standard error, the network's median drift in each, the median
ratio of each sensor's quoted drift error to the baseline's, and how many
sensors' 95% intervals exclude zero in each.
"""

from __future__ import annotations

import json
import sys

import pandas as pd


def excluding_zero(t: pd.DataFrame) -> int:
    return int(((t["drift_ci95_low_c_per_year"] > 0) | (t["drift_ci95_high_c_per_year"] < 0)).sum())


def main(baseline: str, *rest: str) -> None:
    *pairs, out = rest
    base = pd.read_csv(baseline).set_index("sensor")
    report = {
        "baseline": {
            "median_drift_c_per_year": round(float(base["drift_c_per_year"].median()), 4),
            "n_sensors_ci95_excluding_zero": excluding_zero(base),
            "n_sensors": len(base),
        }
    }
    for pair in pairs:
        name, path = pair.split("=", 1)
        alt = pd.read_csv(path).set_index("sensor")
        if not alt.index.equals(base.index):
            raise ValueError(f"{name} does not list the baseline's sensors")
        change = alt["drift_c_per_year"] - base["drift_c_per_year"]
        size = change.abs()
        report[name] = {
            "max_abs_drift_change_c_per_year": round(float(size.max()), 4),
            "sensor_of_max": size.idxmax(),
            "median_abs_drift_change_c_per_year": round(float(size.median()), 4),
            "max_abs_drift_change_in_baseline_se": round(
                float((size / base["drift_se_c_per_year"]).max()), 3),
            "median_drift_c_per_year": round(float(alt["drift_c_per_year"].median()), 4),
            "median_se_ratio_to_baseline": round(
                float((alt["drift_se_c_per_year"] / base["drift_se_c_per_year"]).median()), 3),
            "n_sensors_ci95_excluding_zero": excluding_zero(alt),
        }
    with open(out, "w") as fh:
        json.dump(report, fh, indent=2)
        fh.write("\n")


if __name__ == "__main__":
    main(*sys.argv[1:])
