"""What a sensor's own noise does to its daily means and to a fitted drift.

noise-models (github.com/tomcharnock-lightcone/noise-models) describes each
sensor's noise by its one-sided power spectral density, measured in a climate
chamber at 10-second cadence:

    P(f) = (2 σ_w² / fs) · [1 + (f_knee / f)^α]      (°C²/Hz)

A daily mean is the readings averaged over one day, T = 86400 s: in
frequency, a filter |sinc(f T)|². A fitted drift is a weighted sum of daily
means, b = Σ_j w_j m_j, with w the slope row of the least-squares solution
(X'X)⁻¹X'. For Gaussian noise with that spectrum,

    Var(b) = ∫₀^{fs/2} P(f) sinc²(f T) |Σ_j w_j e^{−2πi f t_j}|² df,

finite for α < 3 because the slope's weights sum to zero. The integral runs
down to 1e-11 Hz, so the 1/f part is taken as continuing to periods far
longer than the chamber's week: that extrapolation is the model's, and the
largest assumption here.
"""

from __future__ import annotations

import numpy as np

DAY_S = 86400.0
F_LOWEST = 1e-11  # Hz; the integrand vanishes as f^(2 − α) below the year
F_SPLIT = 1e-4  # Hz; above, the daily-mean filter leaves only the incoherent sum


def psd_model(f, sigma_white, f_knee, alpha, fs):
    """noise-models' one-sided PSD in °C²/Hz at frequencies f (Hz)."""
    return 2.0 * sigma_white**2 / fs * (1.0 + (f_knee / f) ** alpha)


def weighted_daily_mean_var(
    w: np.ndarray, day: np.ndarray, sigma_white: float, f_knee: float, alpha: float, fs: float,
    n_grid: int = 120_000,
) -> float:
    """Variance of Σ_j w_j m_j, m_j the noise's mean over day `day[j]`.

    Below F_SPLIT the sum over days is computed on a fine logarithmic grid;
    above it, the daily-mean filter has suppressed P by over 10³ and the
    phases of the days no longer add coherently, so |Σ w e^{…}|² is replaced
    by its average over a period, Σ w².
    """
    w = np.asarray(w, dtype=float)
    t = np.asarray(day, dtype=float) * DAY_S
    f = np.logspace(np.log10(F_LOWEST), np.log10(F_SPLIT), n_grid)
    k2 = np.empty(n_grid)
    for i in range(0, n_grid, 10_000):
        part = np.exp(-2j * np.pi * np.outer(f[i:i + 10_000], t)) @ w
        k2[i:i + 10_000] = np.abs(part) ** 2
    low = np.trapezoid(psd_model(f, sigma_white, f_knee, alpha, fs) * np.sinc(f * DAY_S) ** 2 * k2, f)
    fh = np.logspace(np.log10(F_SPLIT), np.log10(fs / 2), 20_000)
    high = np.trapezoid(psd_model(fh, sigma_white, f_knee, alpha, fs) * np.sinc(fh * DAY_S) ** 2, fh)
    return float(low + high * np.sum(w**2))


def day_step_var(sigma_white: float, f_knee: float, alpha: float, fs: float) -> float:
    """Variance of the change in the noise's daily mean from one day to the next.

    Finite even where a 1/f process's own variance is not, so it can be set
    against the observed day-to-day change of the residuals: the share of
    the daily scatter the sensor's noise explains.
    """
    f = np.logspace(np.log10(F_LOWEST), np.log10(fs / 2), 400_000)
    filt = np.sinc(f * DAY_S) ** 2 * 4 * np.sin(np.pi * f * DAY_S) ** 2
    return float(np.trapezoid(psd_model(f, sigma_white, f_knee, alpha, fs) * filt, f))
