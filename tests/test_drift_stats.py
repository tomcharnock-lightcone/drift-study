import numpy as np
import pytest

from drift_stats import fit_ar1, lag1_autocorr


def ar1(rng, n, rho, sigma):
    e = np.empty(n)
    e[0] = rng.normal(0, sigma / np.sqrt(1 - rho**2))
    for i in range(1, n):
        e[i] = rho * e[i - 1] + rng.normal(0, sigma)
    return e


def design(day):
    t = (day - day.mean()) / 365.25
    return np.c_[np.ones_like(t), t]


def newey_west_se(X, e, day):
    """Newey–West standard errors, Bartlett kernel, Andrews (1991) AR(1)
    plug-in bandwidth: the alternative drift_stats rejects."""
    n, k = X.shape
    r = lag1_autocorr(e, day)
    alpha = 4 * r**2 / ((1 - r) ** 2 * (1 + r) ** 2)
    bw = int(min(1.1447 * (alpha * n) ** (1 / 3), n - 1))
    sep = np.abs(day[:, None] - day[None, :])
    w = np.where(sep <= bw, 1 - sep / (bw + 1), 0.0)
    bread = np.linalg.inv(X.T @ X)
    u = X * e[:, None]
    return np.sqrt(np.diag(bread @ (u.T @ w @ u) @ bread) * n / (n - k))


def test_exact_line_is_recovered():
    day = np.arange(365)
    X = design(day)
    y = 0.3 + 0.8 * X[:, 1]
    fit = fit_ar1(X, y, day)
    assert fit.coef == pytest.approx([0.3, 0.8])
    assert np.allclose(fit.se, 0, atol=1e-12)


def test_lag1_autocorr_skips_gaps():
    day = np.array([0, 1, 2, 10, 11, 12])
    e = np.array([1.0, 1.0, 1.0, -1.0, -1.0, -1.0])
    # Consecutive pairs agree in sign; the pair across the gap is not one.
    assert lag1_autocorr(e, day) == pytest.approx(1.0)


def test_white_noise_is_left_as_ols():
    rng = np.random.default_rng(1)
    day = np.arange(365)
    X = design(day)
    y = X @ [0.0, 0.5] + rng.normal(0, 0.2, 365)
    fit = fit_ar1(X, y, day)
    assert fit.n_effective > 300
    assert fit.se[1] == pytest.approx(fit.ols_se[1], rel=0.1)


def test_persistence_widens_the_errors():
    rng = np.random.default_rng(2)
    day = np.arange(365)
    X = design(day)
    fit = fit_ar1(X, X @ [0.0, 0.5] + ar1(rng, 365, 0.9, 0.1), day)
    assert fit.n_effective < 60
    assert fit.se[1] > 2.5 * fit.ols_se[1]


@pytest.mark.parametrize("rho", [0.5, 0.75, 0.9])
def test_interval_covers_true_slope_under_ar1(rho):
    """For AR(1) residuals as persistent as the sensors' (r₁ ≈ 0.2–0.95), the
    95% interval covers the true trend about 95% of the time, where ordinary
    least squares and Newey–West intervals fall short."""
    rng = np.random.default_rng(42)
    day = np.arange(350)
    X = design(day)
    slope, trials = 0.4, 400
    hits = {"ar1": 0, "ols": 0, "newey_west": 0}
    for _ in range(trials):
        y = X @ [0.0, slope] + ar1(rng, len(day), rho, 0.1)
        fit = fit_ar1(X, y, day)
        miss = abs(fit.coef[1] - slope)
        hits["ar1"] += miss < fit.ci95_half[1]
        hits["ols"] += miss < 1.96 * fit.ols_se[1]
        hits["newey_west"] += miss < 1.96 * newey_west_se(X, fit.residuals, day)[1]
    cover = {k: v / trials for k, v in hits.items()}
    assert cover["ar1"] > 0.915
    assert cover["ar1"] > cover["newey_west"] + 0.02
    assert cover["ar1"] > cover["ols"] + 0.15


def test_gaps_in_days_are_handled():
    rng = np.random.default_rng(3)
    day = np.r_[np.arange(0, 140), np.arange(170, 365)]  # a month missing
    X = design(day)
    y = X @ [1.0, -0.3] + ar1(rng, len(day), 0.7, 0.1)
    fit = fit_ar1(X, y, day)
    assert np.all(np.isfinite(fit.se))
    assert abs(fit.coef[1] + 0.3) < fit.ci95_half[1] * 2
