"""The study's sensor-days with each sensor's readings calibrated.

usage: python src/apply_calibration.py DIFFERENCES.csv COEFFICIENTS.csv OUT.csv

Every row of DIFFERENCES (the study's src/differences.py table), with its
sensor_mean_c replaced by the calibrated reading (s − o)/g and its
difference_c recomputed from it. Beside them: the reading as it was
(raw_sensor_mean_c), whether the day lies in the calibration window
(in_window), and the sensor's gain, gain_se and offset_c from COEFFICIENTS
(src/calibrate.py), so that what fits the table can carry the calibration's
uncertainty on. Which days are used is the study's, unchanged.
"""

from __future__ import annotations

import sys

import pandas as pd


def calibrate(table: pd.DataFrame, coefficients: pd.DataFrame) -> pd.DataFrame:
    c = coefficients[coefficients["kind"] == "sensor"].set_index("name")
    missing = sorted(set(table["sensor"]) - set(c.index))
    if missing:
        raise SystemExit(f"no calibration for {', '.join(missing)}")
    per_row = c.loc[table["sensor"]].reset_index(drop=True)
    out = table.reset_index(drop=True).copy()
    raw = out["sensor_mean_c"]
    out["sensor_mean_c"] = (raw - per_row["offset_c"]) / per_row["gain"]
    out["difference_c"] = out["sensor_mean_c"] - out["reference_mean_c"]
    date = out["date"]
    out["raw_sensor_mean_c"] = raw
    out["in_window"] = (date >= per_row["window_start"]) & (date <= per_row["window_last"])
    for column in ("gain", "gain_se", "offset_c"):
        out[column] = per_row[column]
    return out


def main(differences: str, coefficients: str, out: str) -> None:
    table = pd.read_csv(differences, keep_default_na=False, na_values=[""])
    calibrate(table, pd.read_csv(coefficients)).to_csv(out, index=False, float_format="%.6f")


if __name__ == "__main__":
    main(*sys.argv[1:])
