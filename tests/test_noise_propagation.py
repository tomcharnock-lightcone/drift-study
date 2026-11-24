import numpy as np
import pytest

from noise_propagation import day_step_var, psd_model, weighted_daily_mean_var

FS = 0.1
PER_DAY = 8640


def slope_weights(day):
    t = (day - day.mean()) / 365.25
    X = np.c_[np.ones_like(t), t]
    return np.linalg.solve(X.T @ X, X.T)[1]


def simulate(rng, n, sigma_white, f_knee, alpha, n_series):
    """Gaussian series with the model's PSD, as noise-models draws them:
    built in the Fourier domain over twice the length, first half kept."""
    m = 2 * n
    f = np.fft.rfftfreq(m, 1 / FS)
    p = np.zeros_like(f)
    p[1:] = psd_model(f[1:], sigma_white, f_knee, alpha, FS)
    amp = np.sqrt(m * FS * p / 4)
    x = amp * (rng.standard_normal((n_series, len(f))) + 1j * rng.standard_normal((n_series, len(f))))
    return np.fft.irfft(x, n=m, axis=1)[:, :n]


def test_white_noise_matches_the_textbook():
    # Without a 1/f part, a daily mean of 8640 readings has variance σ²/8640,
    # and the slope Σ w m has (σ²/8640) Σ w².
    day = np.arange(365)
    w = slope_weights(day)
    sigma = 0.2
    got = weighted_daily_mean_var(w, day, sigma, 1e-12, 1.0, FS)
    assert got == pytest.approx(sigma**2 / PER_DAY * np.sum(w**2), rel=0.02)
    assert day_step_var(sigma, 1e-12, 1.0, FS) == pytest.approx(2 * sigma**2 / PER_DAY, rel=0.02)


def test_flicker_slope_matches_simulation():
    """For noise dominated by 1/f, the integral gives the scatter of slopes
    fitted to simulated years of readings."""
    rng = np.random.default_rng(5)
    n_days = 120  # shorter than a year to keep the test quick; same physics
    day = np.arange(n_days)
    w = slope_weights(day)
    sigma, f_knee, alpha = 0.2, 0.01, 1.0
    slopes = []
    for _ in range(4):
        x = simulate(rng, n_days * PER_DAY, sigma, f_knee, alpha, n_series=40)
        slopes.extend(x.reshape(40, n_days, PER_DAY).mean(axis=2) @ w)
    simulated = np.std(slopes, ddof=1)
    predicted = np.sqrt(weighted_daily_mean_var(w, day, sigma, f_knee, alpha, FS))
    # 160 draws: the sd scatters by ~6%. The simulator also lacks periods
    # beyond twice its length, which the integral keeps, so it reads a
    # little low.
    assert simulated == pytest.approx(predicted, rel=0.2)
    assert simulated < predicted * 1.1


def test_flicker_grows_the_slope_error_far_past_white():
    day = np.arange(365)
    w = slope_weights(day)
    white = weighted_daily_mean_var(w, day, 0.2, 1e-12, 1.0, FS)
    flicker = weighted_daily_mean_var(w, day, 0.2, 0.01, 1.0, FS)
    assert flicker > 100 * white
