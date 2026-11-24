"""What calibrating each sensor over an initial window does to its drift.

usage: python src/compare_calibration.py [AGAINST=]UNCALIBRATED.csv TEMPERATURE_TERM.csv NAME=DRIFT.csv[,COEFFICIENTS.csv] [...] OUT.json

UNCALIBRATED and TEMPERATURE_TERM are the uncalibrated drift tables, without
and with the temperature term; AGAINST names the first (baseline if not
given), in the keys that depend on it. Each NAME is a calibrated universe, with its
drift table and, for a gain, the calibration's coefficients
(calibration/src/calibrate.py).

For each: how far the drifts move from the uncalibrated ones
(src/compare_universes.py), the median drift error the calibration adds,
and the median ratio of the residuals' scatter to the uncalibrated fit's. For a
gain, also the spread of the sensors' gains and of the Freiburg stations'
against the same reference over the same window, how many of each have a
95% interval that excludes 1, and how closely a sensor's gain over the
window follows the temperature coefficient fitted over the whole year
(the correlation of g − 1 with c).
"""

from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from compare_universes import changes, excluding_zero


def spread(gains: pd.DataFrame, who: str) -> dict:
    g = gains["gain"]
    p05, p95 = np.percentile(g, [5, 95])
    return {
        f"n_{who}s": len(g),
        f"{who}_gain_median": round(float(g.median()), 4),
        f"{who}_gain_p05": round(float(p05), 4),
        f"{who}_gain_p95": round(float(p95), 4),
        f"{who}_gain_sd": round(float(g.std(ddof=1)), 4),
        f"{who}_gain_median_se": round(float(gains["gain_se"].median()), 4),
        f"n_{who}s_gain_ci95_excluding_one": int(
            ((gains["gain_ci95_low"] > 1) | (gains["gain_ci95_high"] < 1)).sum()),
    }


def main(uncalibrated: str, temperature_term: str, *rest: str) -> None:
    *entries, out = rest
    against, _, path = uncalibrated.rpartition("=")
    against = against or "baseline"
    base = pd.read_csv(path).set_index("sensor")
    temp = pd.read_csv(temperature_term).set_index("sensor")
    report = {
        against: {
            "median_drift_c_per_year": round(float(base["drift_c_per_year"].median()), 4),
            "n_sensors_ci95_excluding_zero": excluding_zero(base),
        }
    }
    for entry in entries:
        name, paths = entry.split("=", 1)
        drift_path, *coefficients = paths.split(",")
        alt = pd.read_csv(drift_path).set_index("sensor")
        item = changes(base, alt, name, against)
        item["median_drift_se_calibration_c_per_year"] = round(
            float(alt["drift_se_calibration_c_per_year"].median()), 4)
        item[f"median_residual_sd_ratio_to_{against}"] = round(
            float((alt["residual_sd_c"] / base["residual_sd_c"]).median()), 3)
        if coefficients:
            c = pd.read_csv(coefficients[0])
            sensors = c[c["kind"] == "sensor"].set_index("name").loc[base.index]
            item["window_start"] = str(sensors["window_start"].min())
            item["window_last"] = str(sensors["window_last"].max())
            item["median_window_days"] = float(sensors["n_days"].median())
            item |= spread(sensors, "sensor")
            item |= spread(c[c["kind"] == "station"], "station")
            item["gain_vs_temperature_coefficient_corr"] = round(
                float(np.corrcoef(sensors["gain"] - 1, temp["temp_coef_c_per_c"])[0, 1]), 3)
        report[name] = item
    with open(out, "w") as fh:
        json.dump(report, fh, indent=2)
        fh.write("\n")


if __name__ == "__main__":
    main(*sys.argv[1:])
