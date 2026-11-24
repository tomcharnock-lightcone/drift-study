import numpy as np
import pandas as pd
import pytest

import battery_swaps
import fit_drift
from differences import screen


def battery(rows):
    return pd.DataFrame(rows, columns=["date", "sensor", "n_readings", "mean_v", "min_v", "max_v",
                                       "first_v", "last_v", "rise_v"])


def test_a_swap_within_a_day_mixes_it():
    b = battery([
        ("2023-06-08", "s01", 8640, 3.69, 3.69, 3.69, 3.69, 3.69, 0.0),
        ("2023-06-09", "s01", 8640, 3.82, 3.69, 3.95, 3.69, 3.95, 0.26),
        ("2023-06-10", "s01", 8640, 3.95, 3.95, 3.95, 3.95, 3.95, 0.0),
        ("2023-06-09", "s02", 8640, 3.90, 3.90, 3.90, 3.90, 3.90, 0.0),
    ])
    sw = battery_swaps.swaps(b)
    assert len(sw) == 1
    row = sw.iloc[0]
    assert (row["sensor"], row["swap_date"], row["first_new_date"]) == ("s01", "2023-06-09", "2023-06-10")
    assert row["mixed"] and row["v_before_v"] == pytest.approx(3.69)


def test_a_swap_across_midnight_leaves_the_day_whole():
    b = battery([
        ("2023-06-08", "s01", 8640, 3.69, 3.69, 3.69, 3.69, 3.69, 0.0),
        ("2023-06-09", "s01", 8640, 3.95, 3.95, 3.95, 3.95, 3.95, 0.26),
    ])
    row = battery_swaps.swaps(b).iloc[0]
    assert not row["mixed"] and row["first_new_date"] == "2023-06-09"


def test_a_mixed_swap_day_is_screened_out():
    days = [f"2023-06-{d:02d}" for d in range(8, 12)]
    summary = pd.DataFrame([dict(date=d, sensor="s01", n_readings=8640, mean_c=10.0, min_c=5.0,
                                 max_c=15.0, std_c=2.0, n_removed=0) for d in days])
    ref = pd.DataFrame([dict(date=d, ta_mean_c=9.0, n_hours=24, n_measured=24) for d in days])
    plain = screen(summary, ref, "measured", 0.99)
    swapped = screen(summary, ref, "measured", 0.99, frozenset({("s01", "2023-06-09")}))
    assert plain["used"].all()
    assert dict(zip(swapped["date"], swapped["excluded_reason"]))["2023-06-09"] == "battery_swap"
    assert swapped["used"].sum() == len(days) - 1


def test_a_step_at_the_swap_recovers_the_drift():
    rng = np.random.default_rng(7)
    dates = pd.date_range("2023-01-01", "2023-12-31", freq="D")
    t = (dates - fit_drift.MID_YEAR).days.to_numpy() / fit_drift.DAYS_PER_YEAR
    step = np.asarray(dates >= "2023-06-10")
    days = pd.DataFrame(dict(date=dates.strftime("%Y-%m-%d"), reference_mean_c=10.0,
                             difference_c=0.3 * t + 1.0 * step + rng.normal(0, 0.1, len(t))))
    plain = fit_drift.fit_sensor(days, "time_only")
    stepped = fit_drift.fit_sensor(days, "time_only", steps=("2023-06-10",))
    assert plain["drift_c_per_year"] > 1.5
    assert stepped["drift_c_per_year"] == pytest.approx(0.3, abs=3 * stepped["drift_se_c_per_year"])
    (date, size, se), = stepped["_steps"]
    assert date == "2023-06-10" and size == pytest.approx(1.0, abs=3 * se)


def test_a_swap_outside_the_used_days_adds_no_step():
    days = pd.DataFrame(dict(date=pd.date_range("2023-01-01", periods=60).strftime("%Y-%m-%d"),
                             reference_mean_c=10.0, difference_c=np.linspace(0, 1, 60)))
    X, _, names = fit_drift.design(days, "time_only", ("2024-01-05",))
    assert names == ["offset", "drift"] and X.shape[1] == 2


def test_a_drift_row_gives_back_its_fit():
    rng = np.random.default_rng(8)
    dates = pd.date_range("2023-01-01", "2023-12-31", freq="D")
    ref = 10 + 8 * np.sin(np.arange(len(dates)) / 58.0)
    days = pd.DataFrame(dict(date=dates.strftime("%Y-%m-%d"), reference_mean_c=ref,
                             difference_c=0.02 * ref + 0.5 * (dates >= "2023-09-15")
                             + rng.normal(0, 0.1, len(ref))))
    r = fit_drift.fit_sensor(days, "time_and_temperature", steps=("2023-09-15",))
    row = pd.Series({k: v for k, v in r.items() if not k.startswith("_")} | fit_drift.step_columns(r))
    e = days["difference_c"].to_numpy() - fit_drift.fitted(days, row)
    assert e == pytest.approx(r["_residuals"], abs=1e-3)
