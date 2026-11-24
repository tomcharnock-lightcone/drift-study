"""Each sensor calibrated against the reference over an initial window: a gain
and an offset, or an offset alone.

usage: python src/calibrate.py DIFFERENCES.csv REFERENCE_DAILY.csv REFERENCE NOISE_MODELS.csv WINDOW MODEL OUT.csv

DIFFERENCES is the study's table of sensor-days (src/differences.py); a
sensor's used days in its window are fitted. The window starts on the
sensor's first day in the table and, by WINDOW (the decision of that name),
lasts 14 days (two_weeks), one calendar month (one_month) or three
(three_months). MODEL is the decision of that name:

- offset_only:      s = r + o
- gain_and_offset:  s = g·r + o

with s the sensor's daily mean and r the reference's (°C). Both are fitted
to the difference, d = s − r = α + β·(r − r̄), with r̄ the reference's mean
over the days fitted and β = 0 for an offset alone: g = 1 + β and
o = α − β·r̄. A calibrated reading is (s − o)/g. α, the bias, is the mean
difference over the window.

The gain's error adds two in quadrature, as the study's drift errors do:
from the residuals, for AR(1) residuals (Santer et al. 2000), and from the
sensor's chamber noise model (NOISE_MODELS) propagated through the fit's
weights (src/noise_propagation.py of the study). Its 95% interval adds the
two half-widths, Student-t and Gaussian, in quadrature. The bias's error is
from the residuals alone: under 1/f noise a mean has no finite variance.

Every other station of REFERENCE_DAILY is calibrated against REFERENCE the
same way, over the window from the table's first day, on the days whose 24
hours are all measured at both, if they number at least two thirds of the
window's days; with errors from the residuals alone, for stations have no
noise model. They are maintained, so what they show as a gain is what two
sites answering the weather differently put into one.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

# The study's statistics, shared with its drift fit rather than copied.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from drift_stats import fit_ar1  # noqa: E402
from noise_propagation import weighted_daily_mean_var  # noqa: E402

WINDOWS = {
    "two_weeks": pd.DateOffset(days=14),
    "one_month": pd.DateOffset(months=1),
    "three_months": pd.DateOffset(months=3),
}
MODELS = ("offset_only", "gain_and_offset")
MIN_DAYS = 3
STATION_SHARE = 2 / 3


def window_end(start: pd.Timestamp, window: str) -> pd.Timestamp:
    """The first day after the window that starts on `start`."""
    return start + WINDOWS[window]


def fit(s: np.ndarray, r: np.ndarray, day: np.ndarray, model: str, noise: pd.Series | None) -> dict:
    """Calibrate readings s against reference r, one per day `day`."""
    gain = model == "gain_and_offset"
    centre = r.mean()
    X = np.c_[np.ones_like(r), r - centre] if gain else np.ones((len(r), 1))
    f = fit_ar1(X, s - r, day)
    row = {
        "bias_c": f.coef[0],
        "bias_se_c": f.se[0],
        "reference_mean_c": centre,
        "residual_sd_c": float(np.std(f.residuals, ddof=X.shape[1])),
        "residual_lag1_autocorr": f.lag1_autocorr,
        "n_effective": f.n_effective,
    }
    if not gain:
        return row | {"gain": 1.0, "gain_se": 0.0, "gain_ci95_low": 1.0, "gain_ci95_high": 1.0,
                      "gain_se_residual": 0.0, "gain_se_noise_model": 0.0, "offset_c": f.coef[0]}
    beta, res, half = f.coef[1], f.se[1], f.ci95_half[1]
    nm = np.nan
    if noise is not None:
        w = np.linalg.solve(X.T @ X, X.T)[1]
        nm = np.sqrt(weighted_daily_mean_var(
            w, day, noise["sigma_white_c"], noise["f_knee_hz"], noise["alpha"], noise["fs_hz"]))
        se, half = np.hypot(res, nm), np.hypot(half, stats.norm.ppf(0.975) * nm)
    else:
        se = res
    return row | {"gain": 1 + beta, "gain_se": se, "gain_ci95_low": 1 + beta - half,
                  "gain_ci95_high": 1 + beta + half, "gain_se_residual": res,
                  "gain_se_noise_model": nm, "offset_c": f.coef[0] - beta * centre}


def days_since(dates: pd.Series, start: pd.Timestamp) -> np.ndarray:
    return (dates - start).dt.days.to_numpy()


def sensors(table: pd.DataFrame, noise: pd.DataFrame, window: str, model: str) -> list[dict]:
    rows = []
    for sensor, days in table.groupby("sensor", sort=True):
        if sensor not in noise.index:
            raise SystemExit(f"no noise model for {sensor}")
        start = days["date"].min()
        end = window_end(start, window)
        w = days[days["used"] & (days["date"] < end)]
        if len(w) < MIN_DAYS:
            raise SystemExit(f"{sensor} has {len(w)} used days in its {window} window")
        fitted = fit(w["sensor_mean_c"].to_numpy(), w["reference_mean_c"].to_numpy(),
                     days_since(w["date"], start), model, noise.loc[sensor])
        rows.append({"kind": "sensor", "name": sensor, "window_start": start,
                     "window_last": end - pd.Timedelta(days=1), "n_days": len(w)} | fitted)
    return rows


def stations(reference_daily: pd.DataFrame, reference: str, start: pd.Timestamp, window: str,
             model: str) -> list[dict]:
    end = window_end(start, window)
    measured = reference_daily[(reference_daily["n_measured"] == 24)
                               & (reference_daily["date"] >= start) & (reference_daily["date"] < end)]
    wide = measured.pivot(index="date", columns="station", values="ta_mean_c")
    if reference not in wide:
        raise SystemExit(f"no measured day of {reference} in the window")
    ref = wide.pop(reference)
    need = STATION_SHARE * (end - start).days
    rows = []
    for station in sorted(wide):
        both = wide[station].notna() & ref.notna()
        if both.sum() < max(need, MIN_DAYS):
            continue
        dates = pd.Series(wide.index[both])
        fitted = fit(wide.loc[both, station].to_numpy(), ref[both].to_numpy(),
                     days_since(dates, start), model, None)
        rows.append({"kind": "station", "name": station, "window_start": start,
                     "window_last": end - pd.Timedelta(days=1), "n_days": int(both.sum())} | fitted)
    return rows


def main(differences: str, reference_daily: str, reference: str, noise_models: str, window: str,
         model: str, out: str) -> None:
    if window not in WINDOWS:
        raise ValueError(f"unknown window option {window!r}")
    if model not in MODELS:
        raise ValueError(f"unknown model option {model!r}")
    table = pd.read_csv(differences, parse_dates=["date"], keep_default_na=False, na_values=[""])
    noise = pd.read_csv(noise_models).set_index("sensor")
    daily = pd.read_csv(reference_daily, parse_dates=["date"])
    rows = sensors(table, noise, window, model)
    rows += stations(daily, reference, table["date"].min(), window, model)
    result = pd.DataFrame(rows)
    result.insert(2, "model", model)
    result.insert(3, "window", window)
    for column in ("window_start", "window_last"):
        result[column] = result[column].dt.strftime("%Y-%m-%d")
    result.to_csv(out, index=False, float_format="%.6g")


if __name__ == "__main__":
    main(*sys.argv[1:])
