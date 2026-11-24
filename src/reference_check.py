"""Is the reference itself stable, and how much apparent drift do two good
stations show against each other over one year?

usage: python src/reference_check.py REFERENCE_DAILY.csv STATION OUT.json

Uses only days whose 24 hours are all measured, at every station involved.

- reference_vs_network: STATION's daily mean minus the median of the other
  stations' that day (days where at least 10 others are measured), fitted
  for a linear drift. A drifting reference would show here, and would pass
  its drift, with the sign reversed, to every sensor.
- stations_vs_reference: each other station with at least 300 such days in
  common, minus STATION, fitted the same way. These are maintained stations
  of one network, so their apparent drifts are what two sites' different
  responses to a year's weather and seasons put into a linear fit: a floor
  under which a sensor's drift against STATION cannot be told from where it
  stands.

Each fit is made under both drift models (src/fit_drift.py), with
uncertainties for AR(1) residuals (src/drift_stats.py).
"""

from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from fit_drift import MODELS, fit_sensor

MIN_OTHERS = 10
MIN_COMMON_DAYS = 300


def drift(diff: pd.Series, ref: pd.Series, model: str) -> dict:
    days = pd.DataFrame(
        {"date": diff.index.strftime("%Y-%m-%d"), "difference_c": diff.values,
         "reference_mean_c": ref.loc[diff.index].values}
    )
    row = fit_sensor(days, model)
    return {k: row[k] for k in ("n_days_used", "drift_c_per_year", "drift_se_c_per_year",
                                "drift_ci95_low_c_per_year", "drift_ci95_high_c_per_year",
                                "residual_sd_c", "residual_lag1_autocorr")}


def rounded(x):
    if isinstance(x, dict):
        return {k: rounded(v) for k, v in x.items()}
    if isinstance(x, list):
        return [rounded(v) for v in x]
    if isinstance(x, (float, np.floating)):
        return round(float(x), 4)
    if isinstance(x, np.integer):
        return int(x)
    return x


def main(reference_daily: str, station: str, out: str) -> None:
    daily = pd.read_csv(reference_daily, parse_dates=["date"])
    measured = daily[daily["n_measured"] == 24]
    wide = measured.pivot(index="date", columns="station", values="ta_mean_c")
    if station not in wide:
        raise SystemExit(f"no station {station} in {reference_daily}")
    ref = wide[station]
    others = wide.drop(columns=station)

    report: dict = {"station": station, "n_other_stations": int(others.shape[1])}
    enough = others.notna().sum(axis=1) >= MIN_OTHERS
    vs_net = (ref - others.median(axis=1))[enough].dropna()
    report["reference_vs_network"] = {m: drift(vs_net, ref, m) for m in MODELS}

    per_station: dict = {m: {} for m in MODELS}
    for other in others.columns:
        diff = (others[other] - ref).dropna()
        if len(diff) < MIN_COMMON_DAYS:
            continue
        for m in MODELS:
            per_station[m][other] = drift(diff, ref, m)
    summary = {}
    for m in MODELS:
        d = np.array([v["drift_c_per_year"] for v in per_station[m].values()])
        excl = [v["drift_ci95_low_c_per_year"] > 0 or v["drift_ci95_high_c_per_year"] < 0
                for v in per_station[m].values()]
        summary[m] = {
            "n_stations": len(d),
            "drift_median_c_per_year": np.median(d),
            "drift_sd_c_per_year": np.std(d, ddof=1),
            "drift_p05_c_per_year": np.percentile(d, 5),
            "drift_p95_c_per_year": np.percentile(d, 95),
            "fraction_ci95_excluding_zero": float(np.mean(excl)),
        }
    report["stations_vs_reference"] = {"summary": summary, "stations": per_station}
    with open(out, "w") as fh:
        json.dump(rounded(report), fh, indent=2)
        fh.write("\n")


if __name__ == "__main__":
    main(*sys.argv[1:])
