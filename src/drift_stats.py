"""Least-squares trend fits with uncertainties that allow for autocorrelation.

The daily difference between a sensor and the reference is not independent
from one day to the next: what makes one day's difference large (sun, wind,
the weather's different effect on two sites) persists for days. Ordinary
least-squares standard errors assume it does not, and understate the
uncertainty of a trend several times over.

`fit_ar1` keeps the least-squares estimate and widens its uncertainty by the
effective sample size of residuals that are AR(1), as Santer et al. (2000,
doi:10.1029/1999JD901105) do for temperature trends: n_e = n (1 − r₁)/(1 + r₁),
with r₁ the residuals' lag-1 autocorrelation, the residual variance divided by
n_e − k rather than n − k, and Student-t intervals on n_e − k degrees of
freedom. Newey–West errors were tried first and rejected: on simulated AR(1)
residuals as persistent as the sensors', their 95% intervals covered the true
trend only 80–90% of the time, against 92–95% for this (tests/test_drift_stats.py
repeats both).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats


@dataclass(frozen=True)
class Fit:
    """A least-squares fit and its autocorrelation-adjusted uncertainty."""

    coef: np.ndarray  # estimated coefficients, one per column of X
    se: np.ndarray  # standard error of each, adjusted for autocorrelation
    ols_se: np.ndarray  # the unadjusted least-squares standard error
    ci95_half: np.ndarray  # half-width of each coefficient's 95% interval
    residuals: np.ndarray
    lag1_autocorr: float  # r₁ of the residuals, over pairs of consecutive days
    n_effective: float  # n (1 − r₁)/(1 + r₁), at most n


def lag1_autocorr(residuals: np.ndarray, day: np.ndarray) -> float:
    """Lag-1 autocorrelation of residuals, from the pairs exactly one day apart.

    Pairs that straddle a gap are not consecutive days and are left out.
    """
    order = np.argsort(day)
    e, d = residuals[order], day[order]
    pair = np.diff(d) == 1
    var = np.mean(e**2)
    if pair.sum() < 3 or var == 0:
        return 0.0
    return float(np.sum(e[:-1][pair] * e[1:][pair]) / pair.sum() / var)


def fit_ar1(X: np.ndarray, y: np.ndarray, day: np.ndarray) -> Fit:
    """Least squares of y on X, with uncertainties for AR(1) residuals.

    Args:
        X: Design matrix, one row per observation (include the intercept).
        y: Observations.
        day: Each observation's day as an integer, to find consecutive days.

    A negative r₁ is taken as zero (n_e = n). Where n_e ≤ k nothing can be
    said about the coefficients, and their uncertainties are infinite.
    """
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    day = np.asarray(day, dtype=np.int64)
    n, k = X.shape
    if n <= k:
        raise ValueError(f"{n} observations cannot fit {k} coefficients")
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ coef
    bread = np.linalg.inv(X.T @ X)
    ss = float(np.sum(e**2))

    r1 = lag1_autocorr(e, day)
    n_eff = n * (1 - max(r1, 0.0)) / (1 + max(r1, 0.0))
    ols_se = np.sqrt(ss / (n - k) * np.diag(bread))
    if n_eff > k:
        se = np.sqrt(ss / (n_eff - k) * np.diag(bread))
        half = stats.t.ppf(0.975, n_eff - k) * se
    else:
        se = half = np.full(k, np.inf)
    return Fit(
        coef=coef,
        se=se,
        ols_se=ols_se,
        ci95_half=half,
        residuals=e,
        lag1_autocorr=r1,
        n_effective=float(n_eff),
    )
