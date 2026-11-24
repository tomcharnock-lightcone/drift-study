import numpy as np
import pandas as pd
import pytest

import apply_calibration
import calibrate
import fit_drift

DAYS = pd.date_range("2023-01-01", "2023-12-31", freq="D")
NOISE = pd.DataFrame([dict(sensor=s, sigma_white_c=0.05, f_knee_hz=1e-12, alpha=1.0, fs_hz=0.1)
                      for s in ("s01", "s02")])


def weather(rng):
    """A reference year: a seasonal cycle not symmetric about mid-year, and
    weather that persists for days."""
    day = np.arange(len(DAYS))
    w = np.zeros(len(DAYS))
    for i in range(1, len(w)):
        w[i] = 0.7 * w[i - 1] + rng.normal(0, 1.5)
    return 10 - 8 * np.cos(2 * np.pi * (day - 40) / 365) + w


def table(rng, gain, offset, drift):
    """Two sensors reading s = g·r + o + drift·t + noise against reference r."""
    r = weather(rng)
    t = (DAYS - fit_drift.MID_YEAR).days.to_numpy() / fit_drift.DAYS_PER_YEAR
    rows = []
    for sensor in ("s01", "s02"):
        s = gain * r + offset + drift * t + rng.normal(0, 0.05, len(r))
        rows.append(pd.DataFrame(dict(
            date=DAYS.strftime("%Y-%m-%d"), sensor=sensor, sensor_mean_c=s, reference_mean_c=r,
            difference_c=s - r, coverage=1.0, reference_measured_hours=24, used=True,
            excluded_reason="")))
    t = pd.concat(rows, ignore_index=True)
    # One excluded day each, as every real sensor has.
    last = t["date"] == "2023-12-31"
    t.loc[last, ["used", "excluded_reason"]] = [False, "low_coverage"]
    return t


def no_stations():
    return pd.DataFrame(dict(date=DAYS, station="FRPDAS", ta_mean_c=0.0, n_hours=24, n_measured=24))


def run(tmp_path, t, window, model, drift_model="time_only"):
    """Calibrate t, apply it, fit the drift; the coefficients and both drift tables."""
    paths = {k: tmp_path / f"{k}.csv" for k in
             ("raw", "noise", "daily", "coef", "calibrated", "drift_raw", "drift_cal")}
    t.to_csv(paths["raw"], index=False)
    NOISE.to_csv(paths["noise"], index=False)
    no_stations().to_csv(paths["daily"], index=False)
    calibrate.main(paths["raw"], paths["daily"], "FRPDAS", paths["noise"], window, model, paths["coef"])
    apply_calibration.main(paths["raw"], paths["coef"], paths["calibrated"])
    for source, out in (("raw", "drift_raw"), ("calibrated", "drift_cal")):
        fit_drift.main(paths[source], drift_model, "combined", paths["noise"], "least_squares",
                       "none", "", paths[out])
    return (pd.read_csv(paths["coef"]).set_index("name"),
            pd.read_csv(paths["drift_raw"]).set_index("sensor"),
            pd.read_csv(paths["drift_cal"]).set_index("sensor"))


def test_a_gain_and_offset_are_recovered_from_a_month():
    rng = np.random.default_rng(1)
    t = table(rng, gain=1.05, offset=0.4, drift=0.0)
    w = t[(t["sensor"] == "s01") & (t["date"] < "2023-02-01")]
    day = np.arange(len(w))
    got = calibrate.fit(w["sensor_mean_c"].to_numpy(), w["reference_mean_c"].to_numpy(), day,
                        "gain_and_offset", NOISE.set_index("sensor").loc["s01"])
    assert got["gain"] == pytest.approx(1.05, abs=0.01)
    assert got["offset_c"] == pytest.approx(0.4, abs=0.1)
    assert got["gain_ci95_low"] < 1.05 < got["gain_ci95_high"]


def test_windows_are_counted_from_the_first_day():
    start = pd.Timestamp("2023-01-01")
    assert calibrate.window_end(start, "two_weeks") == pd.Timestamp("2023-01-15")
    assert calibrate.window_end(start, "one_month") == pd.Timestamp("2023-02-01")
    assert calibrate.window_end(start, "three_months") == pd.Timestamp("2023-04-01")


def test_an_offset_alone_leaves_the_drift_unchanged(tmp_path):
    # The drift fit has its own offset, so subtracting a constant can move
    # only that.
    t = table(np.random.default_rng(2), gain=1.04, offset=0.6, drift=0.3)
    coef, raw, cal = run(tmp_path, t, "one_month", "offset_only")
    assert (coef.loc[["s01", "s02"], "gain"] == 1).all()
    for column in ("drift_c_per_year", "drift_ci95_low_c_per_year", "drift_ci95_high_c_per_year"):
        assert cal[column].to_numpy() == pytest.approx(raw[column].to_numpy(), abs=1e-5)
    assert (cal["drift_se_calibration_c_per_year"] == 0).all()


def test_a_gain_calibrated_out_recovers_the_drift(tmp_path):
    # A gain error alone puts a slope into the difference wherever the year's
    # temperature is not symmetric about mid-year; calibrated out, what is
    # left is the drift, divided by the gain.
    t = table(np.random.default_rng(3), gain=1.05, offset=0.4, drift=0.3)
    _, raw, cal = run(tmp_path, t, "three_months", "gain_and_offset")
    for sensor in ("s01", "s02"):
        b = cal.loc[sensor]
        assert abs(b["drift_c_per_year"] - 0.3 / 1.05) < 2 * b["drift_se_c_per_year"]
        assert abs(raw.loc[sensor, "drift_c_per_year"] - 0.3) > 0.1


def test_the_calibration_error_is_the_drift_moved_by_the_gain(tmp_path):
    t = table(np.random.default_rng(4), gain=1.03, offset=0.2, drift=0.2)
    coef, _, cal = run(tmp_path, t, "one_month", "gain_and_offset")
    c = coef.loc["s01"]
    used = t[(t["sensor"] == "s01") & t["used"]]

    def drift(gain):
        moved = apply_calibration.calibrate(used, coef.reset_index().assign(
            gain=lambda f: np.where(f["name"] == "s01", gain, f["gain"])))
        X, day, _ = fit_drift.design(moved, "time_only")
        return fit_drift.slope_weights(X) @ moved["difference_c"].to_numpy()

    eps = 1e-6
    slope = (drift(c["gain"] + eps) - drift(c["gain"] - eps)) / (2 * eps)
    expected = abs(slope) * c["gain_se"]
    assert cal.loc["s01", "drift_se_calibration_c_per_year"] == pytest.approx(expected, rel=1e-3)
