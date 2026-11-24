"""A linear drift per sensor, fitted to its daily difference from the reference.

usage: python src/fit_drift.py DIFFERENCES.csv DRIFT_MODEL DRIFT_ERRORS NOISE_MODELS.csv OUT.csv

DIFFERENCES is src/differences.py's table; only its used days are fitted.
DRIFT_MODEL is the option of the decision of that name:

- time_only:            d = a + b·t
- time_and_temperature: d = a + b·t + c·(T_ref − T̄_ref)

with d the sensor's daily mean minus the reference's (°C), t the time from
mid-2023 (2023-07-02) in years of 365.25 days, T_ref the reference's daily
mean and T̄_ref its mean over the days fitted. b is the drift, a the
difference at mid-year, c a temperature-dependent bias (°C per °C).

The drift's standard error is given two ways in every table, and
DRIFT_ERRORS (the decision of that name) picks the one the quoted error and
95% interval use:

- residual_ar1: from the fit's residuals, for AR(1) residuals
  (src/drift_stats.py); Student-t interval.
- noise_model: from the sensor's chamber noise model (NOISE_MODELS, the
  noise-models analysis's table), propagated through the daily means and
  the fit (src/noise_propagation.py); Gaussian interval.
- combined: both variances added; the interval's half-width is the two
  half-widths added in quadrature. The instrument's day-to-day noise is in
  both, so this errs wide.

The offset's and temperature coefficient's errors are always residual_ar1.

DIFFERENCES can be calibration/src/apply_calibration.py's table instead,
each sensor's readings calibrated, s' = (s − o)/g. Then the drift carries
the gain's uncertainty too: the slope of the calibrated difference is
b' = Σ w_j (s_j − o)/g − Σ w_j r_j, with w the slope's weights, so
∂b'/∂g = −Σ w_j (s_j − o)/g² (the offset drops out, as Σ w_j = 0), and
drift_se_calibration_c_per_year = |Σ w_j (s_j − o)|/g² · σ_g is added in
quadrature to the quoted error and interval, whichever DRIFT_ERRORS picks.
The noise model's error is divided by g, as the noise in a calibrated
reading is. The table also gives each sensor's calibration_gain and
calibration_gain_se.
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from drift_stats import fit_ar1
from noise_propagation import day_step_var, weighted_daily_mean_var

MID_YEAR = pd.Timestamp("2023-07-02")
DAYS_PER_YEAR = 365.25
MODELS = ("time_only", "time_and_temperature")
ERRORS = ("residual_ar1", "noise_model", "combined")
REASONS = ("flatline", "flatline_adjacent", "low_coverage", "no_reference", "reference_gap_filled")


def design(days: pd.DataFrame, model: str) -> tuple[np.ndarray, np.ndarray]:
    """The design matrix of a sensor's days, and each day's offset from mid-year."""
    day = ((pd.to_datetime(days["date"]) - MID_YEAR).dt.days).to_numpy()
    t = day / DAYS_PER_YEAR
    columns = [np.ones_like(t), t]
    if model == "time_and_temperature":
        ref = days["reference_mean_c"].to_numpy()
        columns.append(ref - ref.mean())
    return np.column_stack(columns), day


def fit_sensor(days: pd.DataFrame, model: str) -> dict:
    """Fit one series' days; its row of the drift table, residual errors only."""
    X, day = design(days, model)
    fit = fit_ar1(X, days["difference_c"].to_numpy(), day)
    date = pd.to_datetime(days["date"])
    return {
        "n_days_used": len(days),
        "first_date": date.min().strftime("%Y-%m-%d"),
        "last_date": date.max().strftime("%Y-%m-%d"),
        "drift_c_per_year": fit.coef[1],
        "drift_se_c_per_year": fit.se[1],
        "drift_ci95_low_c_per_year": fit.coef[1] - fit.ci95_half[1],
        "drift_ci95_high_c_per_year": fit.coef[1] + fit.ci95_half[1],
        "drift_se_residual_c_per_year": fit.se[1],
        "drift_ols_se_c_per_year": fit.ols_se[1],
        "offset_c": fit.coef[0],
        "offset_se_c": fit.se[0],
        "temp_coef_c_per_c": fit.coef[2] if len(fit.coef) > 2 else np.nan,
        "temp_coef_se_c_per_c": fit.se[2] if len(fit.coef) > 2 else np.nan,
        "residual_sd_c": float(np.std(fit.residuals, ddof=len(fit.coef))),
        "residual_lag1_autocorr": fit.lag1_autocorr,
        "n_effective": fit.n_effective,
        "_ci95_half_residual": fit.ci95_half[1],
        "_residuals": fit.residuals,
        "_day": day,
        "_X": X,
    }


def slope_weights(X: np.ndarray) -> np.ndarray:
    """w with b = Σ w_j d_j: the slope's row of the least-squares solution."""
    return np.linalg.solve(X.T @ X, X.T)[1]


def noise_columns(row: dict, noise: pd.Series) -> dict:
    """The drift's error from the sensor's noise model, and how much of the
    residuals' day-to-day scatter that noise explains."""
    X, day, e = row["_X"], row["_day"], row["_residuals"]
    w = slope_weights(X)
    args = (noise["sigma_white_c"], noise["f_knee_hz"], noise["alpha"], noise["fs_hz"])
    order = np.argsort(day)
    consecutive = np.diff(day[order]) == 1
    return {
        "drift_se_noise_model_c_per_year": np.sqrt(weighted_daily_mean_var(w, day, *args)),
        "noise_day_step_sd_c": np.sqrt(day_step_var(*args)),
        "observed_day_step_sd_c": float(np.std(np.diff(e[order])[consecutive], ddof=1)),
    }


def calibration_columns(row: dict, used: pd.DataFrame) -> dict:
    """For calibrated readings: the drift's error from the calibration's gain,
    and the noise model's error scaled to calibrated readings."""
    g, g_se, o = (float(used[c].iloc[0]) for c in ("gain", "gain_se", "offset_c"))
    s = slope_weights(row["_X"]) @ (used["raw_sensor_mean_c"].to_numpy() - o)
    return {
        "drift_se_noise_model_c_per_year": row["drift_se_noise_model_c_per_year"] / g,
        "noise_day_step_sd_c": row["noise_day_step_sd_c"] / g,
        "calibration_gain": g,
        "calibration_gain_se": g_se,
        "drift_se_calibration_c_per_year": abs(s) / g**2 * g_se,
    }


def choose_errors(row: dict, errors: str) -> None:
    """Set the quoted drift error and interval from the option chosen."""
    b, res, nm = row["drift_c_per_year"], row["drift_se_residual_c_per_year"], \
        row["drift_se_noise_model_c_per_year"]
    if errors == "residual_ar1":
        se, half = res, row["_ci95_half_residual"]
    elif errors == "noise_model":
        se, half = nm, 1.96 * nm
    else:
        se = np.hypot(res, nm)
        half = np.hypot(row["_ci95_half_residual"], 1.96 * nm)
    if "drift_se_calibration_c_per_year" in row:
        cal = row["drift_se_calibration_c_per_year"]
        se, half = np.hypot(se, cal), np.hypot(half, 1.96 * cal)
    row["drift_se_c_per_year"] = se
    row["drift_ci95_low_c_per_year"] = b - half
    row["drift_ci95_high_c_per_year"] = b + half


def main(differences: str, model: str, errors: str, noise_models: str, out: str) -> None:
    if model not in MODELS:
        raise ValueError(f"unknown drift_model option {model!r}")
    if errors not in ERRORS:
        raise ValueError(f"unknown drift_errors option {errors!r}")
    table = pd.read_csv(differences, keep_default_na=False, na_values=[""])
    table["excluded_reason"] = table["excluded_reason"].fillna("")
    noise = pd.read_csv(noise_models).set_index("sensor")
    calibrated = "gain" in table.columns
    rows = []
    for sensor, days in table.groupby("sensor", sort=True):
        if sensor not in noise.index:
            raise SystemExit(f"no noise model for {sensor} in {noise_models}")
        used = days[days["used"]]
        row = {"sensor": sensor, **fit_sensor(used, model)}
        row.update(noise_columns(row, noise.loc[sensor]))
        if calibrated:
            row.update(calibration_columns(row, used))
        choose_errors(row, errors)
        counts = days["excluded_reason"].value_counts()
        for reason in REASONS:
            row[f"n_excluded_{reason}"] = int(counts.get(reason, 0))
        rows.append({k: v for k, v in row.items() if not k.startswith("_")})
    pd.DataFrame(rows).to_csv(out, index=False, float_format="%.6g")


if __name__ == "__main__":
    main(*sys.argv[1:])
