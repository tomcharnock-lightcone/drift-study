import pandas as pd

from differences import screen


def summary_rows(days, **override):
    rows = []
    for i, day in enumerate(days):
        row = dict(date=day, sensor="s01", n_readings=8639, mean_c=10.0 + i,
                   min_c=5.0, max_c=15.0, std_c=2.0, n_removed=1)
        row.update(override.get(day, {}))
        rows.append(row)
    return pd.DataFrame(rows)


def reference(days, **override):
    rows = [dict(date=d, ta_mean_c=9.0, n_hours=24, n_measured=24) for d in days]
    for r in rows:
        r.update(override.get(r["date"], {}))
    return pd.DataFrame(rows)


DAYS = [f"2023-01-{d:02d}" for d in range(1, 9)]


def reasons(table):
    return dict(zip(table["date"], table["excluded_reason"]))


def test_clean_days_are_used_and_differenced():
    t = screen(summary_rows(DAYS), reference(DAYS), "measured", 0.99)
    assert t["used"].all()
    assert t["difference_c"].tolist() == [1.0 + i for i in range(len(DAYS))]


def test_despiked_readings_count_as_delivered():
    # 8639 kept + 1 removed is a whole day, not a partial one.
    t = screen(summary_rows(DAYS), reference(DAYS), "measured", 0.99)
    assert (t["coverage"] == 1.0).all()


def test_flatline_and_its_neighbours_are_excluded():
    stuck = {"min_c": 15.51, "max_c": 15.51, "std_c": 0.0}
    s = summary_rows(DAYS, **{"2023-01-04": stuck, "2023-01-05": stuck})
    r = reasons(screen(s, reference(DAYS), "measured", 0.99))
    assert r["2023-01-03"] == "flatline_adjacent"
    assert r["2023-01-04"] == r["2023-01-05"] == "flatline"
    assert r["2023-01-06"] == "flatline_adjacent"
    assert r["2023-01-02"] == r["2023-01-07"] == ""


def test_partial_days_fall_to_the_coverage_threshold():
    s = summary_rows(DAYS, **{"2023-01-02": {"n_readings": 8000, "n_removed": 0}})
    assert reasons(screen(s, reference(DAYS), "measured", 0.99))["2023-01-02"] == "low_coverage"
    assert reasons(screen(s, reference(DAYS), "measured", 0.90))["2023-01-02"] == ""


def test_gap_filled_reference_days_depend_on_the_option():
    ref = reference(DAYS, **{"2023-01-03": {"n_measured": 20}})
    assert reasons(screen(summary_rows(DAYS), ref, "measured", 0.99))["2023-01-03"] == (
        "reference_gap_filled"
    )
    assert reasons(screen(summary_rows(DAYS), ref, "gap_filled", 0.99))["2023-01-03"] == ""


def test_missing_reference_day():
    t = screen(summary_rows(DAYS), reference(DAYS[1:]), "gap_filled", 0.99)
    assert reasons(t)["2023-01-01"] == "no_reference"
    assert not t["used"].iloc[0]
