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

`fit_huber` is the same with Huber's M-estimate in place of least squares, for
a fit that a few outlying days cannot pull: each residual beyond c = 1.345
robust standard deviations counts in proportion to its size, not its square.
Its errors are Huber's asymptotic ones with the same AR(1) effective sample
size, and equal `fit_ar1`'s where no day is down-weighted.
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
    weights: np.ndarray | None = None  # each observation's weight in the fit; None for equal


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


HUBER_C = 1.345  # 95% efficient for Gaussian residuals


def fit_huber(X: np.ndarray, y: np.ndarray, day: np.ndarray, c: float = HUBER_C,
              max_iter: int = 200, tol: float = 1e-12) -> Fit:
    """Huber's M-estimate of y on X, with uncertainties for AR(1) residuals.

    Iteratively reweighted least squares, from the least-squares fit, with
    the residuals' scale re-estimated at each step as their normalised
    median absolute deviation σ. With z = e/σ and ψ(z) = clip(z, −c, c), the
    coefficients' covariance is Huber's (1981),

        K² σ² Σψ² / (n_e − k) / m² · (X'X)⁻¹,   m = mean ψ'(z),
        K = 1 + (k/n)(1 − m)/m,

    with n_e the AR(1) effective sample size of the winsorised residuals σψ
    in place of n, and Student-t intervals on n_e − k degrees of freedom.
    Where no residual is beyond c, ψ(z) = z and this is `fit_ar1`.
    """
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    day = np.asarray(day, dtype=np.int64)
    n, k = X.shape
    if n <= k:
        raise ValueError(f"{n} observations cannot fit {k} coefficients")
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    w = np.ones(n)
    for _ in range(max_iter):
        e = y - X @ coef
        sigma = 1.4826 * np.median(np.abs(e - np.median(e)))
        if sigma == 0:
            break
        z = np.abs(e) / sigma
        w = np.where(z <= c, 1.0, c / np.maximum(z, c))
        sw = np.sqrt(w)
        new, *_ = np.linalg.lstsq(X * sw[:, None], y * sw, rcond=None)
        done = np.max(np.abs(new - coef)) <= tol * (1 + np.max(np.abs(coef)))
        coef = new
        if done:
            break
    e = y - X @ coef
    sigma = 1.4826 * np.median(np.abs(e - np.median(e)))
    bread = np.linalg.inv(X.T @ X)
    if sigma == 0:
        zero = np.zeros(k)
        return Fit(coef=coef, se=zero, ols_se=zero, ci95_half=zero, residuals=e,
                   lag1_autocorr=0.0, n_effective=float(n), weights=w)
    psi = np.clip(e / sigma, -c, c)
    m = float(np.mean(np.abs(e / sigma) <= c))
    K = 1 + (k / n) * (1 - m) / m
    scale = K**2 * sigma**2 * float(np.sum(psi**2)) / m**2

    r1 = lag1_autocorr(sigma * psi, day)
    n_eff = n * (1 - max(r1, 0.0)) / (1 + max(r1, 0.0))
    ols_se = np.sqrt(scale / (n - k) * np.diag(bread))
    if n_eff > k:
        se = np.sqrt(scale / (n_eff - k) * np.diag(bread))
        half = stats.t.ppf(0.975, n_eff - k) * se
    else:
        se = half = np.full(k, np.inf)
    return Fit(coef=coef, se=se, ols_se=ols_se, ci95_half=half, residuals=e,
               lag1_autocorr=r1, n_effective=float(n_eff), weights=w)
