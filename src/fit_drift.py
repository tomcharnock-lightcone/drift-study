"""A linear drift per sensor, fitted to its daily difference from the reference.

usage: python src/fit_drift.py DIFFERENCES.csv DRIFT_MODEL OUT.csv

DIFFERENCES is src/differences.py's table; only its used days are fitted.
DRIFT_MODEL is the option of the decision of that name:

- time_only:            d = a + b·t
- time_and_temperature: d = a + b·t + c·(T_ref − T̄_ref)

with d the sensor's daily mean minus the reference's (°C), t the time from
mid-2023 (2023-07-02) in years of 365.25 days, T_ref the reference's daily
mean and T̄_ref its mean over the days fitted. b is the drift, a the
difference at mid-year, c a temperature-dependent bias (°C per °C).
Least-squares estimates; uncertainties for AR(1) residuals (src/drift_stats.py).
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from drift_stats import fit_ar1

MID_YEAR = pd.Timestamp("2023-07-02")
DAYS_PER_YEAR = 365.25
MODELS = ("time_only", "time_and_temperature")
REASONS = ("flatline", "flatline_adjacent", "low_coverage", "no_reference", "reference_gap_filled")


def fit_sensor(days: pd.DataFrame, model: str) -> dict:
    """Fit one sensor's used days; give its row of the drift table."""
    date = pd.to_datetime(days["date"])
    day = ((date - MID_YEAR).dt.days).to_numpy()
    t = day / DAYS_PER_YEAR
    columns = [np.ones_like(t), t]
    if model == "time_and_temperature":
        ref = days["reference_mean_c"].to_numpy()
        columns.append(ref - ref.mean())
    fit = fit_ar1(np.column_stack(columns), days["difference_c"].to_numpy(), day)
    row = {
        "n_days_used": len(days),
        "first_date": date.min().strftime("%Y-%m-%d"),
        "last_date": date.max().strftime("%Y-%m-%d"),
        "drift_c_per_year": fit.coef[1],
        "drift_se_c_per_year": fit.se[1],
        "drift_ci95_low_c_per_year": fit.coef[1] - fit.ci95_half[1],
        "drift_ci95_high_c_per_year": fit.coef[1] + fit.ci95_half[1],
        "drift_ols_se_c_per_year": fit.ols_se[1],
        "offset_c": fit.coef[0],
        "offset_se_c": fit.se[0],
        "temp_coef_c_per_c": fit.coef[2] if len(fit.coef) > 2 else np.nan,
        "temp_coef_se_c_per_c": fit.se[2] if len(fit.coef) > 2 else np.nan,
        "residual_sd_c": float(np.std(fit.residuals, ddof=len(fit.coef))),
        "residual_lag1_autocorr": fit.lag1_autocorr,
        "n_effective": fit.n_effective,
    }
    return row


def main(differences: str, model: str, out: str) -> None:
    if model not in MODELS:
        raise ValueError(f"unknown drift_model option {model!r}")
    table = pd.read_csv(differences, keep_default_na=False, na_values=[""])
    table["excluded_reason"] = table["excluded_reason"].fillna("")
    rows = []
    for sensor, days in table.groupby("sensor", sort=True):
        used = days[days["used"]]
        row = {"sensor": sensor, **fit_sensor(used, model)}
        counts = days["excluded_reason"].value_counts()
        for reason in REASONS:
            row[f"n_excluded_{reason}"] = int(counts.get(reason, 0))
        rows.append(row)
    pd.DataFrame(rows).to_csv(out, index=False, float_format="%.6g")


if __name__ == "__main__":
    main(*sys.argv[1:])
