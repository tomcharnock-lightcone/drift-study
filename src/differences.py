"""Each sensor's daily mean against the reference station's, day by day,
with the days unfit to compare marked and why.

usage: python src/differences.py SUMMARY.csv REFERENCE_DAILY.csv STATION
           REFERENCE_HOURS MIN_COVERAGE BATTERY_SWAPS.csv SWAP_STEPS OUT.csv

SUMMARY is sensor-archive's daily summary per sensor (date, sensor,
n_readings, mean_c, min_c, max_c, std_c, n_removed); REFERENCE_DAILY the
stations' daily means (src/reference_daily.py); BATTERY_SWAPS the sensors'
battery swaps (src/battery_swaps.py). REFERENCE_HOURS, MIN_COVERAGE and
SWAP_STEPS are the options of the decisions of those names.

A sensor-day is used unless, in this order of precedence:

- flatline: every reading of the day was the same value (max_c = min_c), a
  sensor stuck at one value rather than measuring;
- flatline_adjacent: the day before or after a flatline day; the summary
  cannot tell how much of it was stuck;
- low_coverage: fewer than MIN_COVERAGE of the day's 8640 ten-second readings
  were delivered (readings despiking removed count as delivered: they are
  isolated single readings and leave no hole in the day). A partial day's
  mean is biased by whichever part of the daily cycle is missing;
- no_reference: the reference has no value that day;
- reference_gap_filled: under `measured`, some of the reference's 24 hours
  that day are gap-filled predictions rather than measurements;
- battery_swap: under `at_swaps`, the sensor's battery was swapped during
  the day, so its mean mixes readings from two batteries.
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

READINGS_PER_DAY = 8640  # one every 10 seconds
MIN_COVERAGE = {"p99": 0.99, "p90": 0.90}
REFERENCE_HOURS = ("measured", "gap_filled")
SWAP_STEPS = ("none", "at_swaps")


def screen(
    summary: pd.DataFrame,
    reference: pd.DataFrame,
    reference_hours: str,
    min_coverage: float,
    swap_days: frozenset[tuple[str, str]] = frozenset(),
) -> pd.DataFrame:
    """Join sensor-days to the reference and mark the ones not to use.

    Args:
        summary: The sensors' daily summary.
        reference: The reference station's days: date, ta_mean_c, n_hours,
            n_measured.
        reference_hours: `measured` or `gap_filled`.
        min_coverage: The fraction of a day's readings a sensor must deliver.
    """
    if reference_hours not in REFERENCE_HOURS:
        raise ValueError(f"unknown reference_hours option {reference_hours!r}")
    s = summary.copy()
    s["date"] = pd.to_datetime(s["date"])
    s = s.sort_values(["sensor", "date"]).reset_index(drop=True)
    if s.duplicated(["sensor", "date"]).any():
        raise ValueError("the summary has more than one row for a sensor-day")

    ref = reference.copy()
    ref["date"] = pd.to_datetime(ref["date"])
    ref = ref.rename(columns={"ta_mean_c": "reference_mean_c"})
    m = s.merge(ref[["date", "reference_mean_c", "n_hours", "n_measured"]], on="date", how="left")

    m["coverage"] = (m["n_readings"] + m["n_removed"]) / READINGS_PER_DAY
    flat = (m["max_c"] - m["min_c"]) < 0.005  # readings come in 0.01 °C steps
    flat_days = {(k, d) for k, d in zip(m.loc[flat, "sensor"], m.loc[flat, "date"])}
    one = pd.Timedelta(days=1)
    adjacent = np.array(
        [
            not f and ((k, d - one) in flat_days or (k, d + one) in flat_days)
            for k, d, f in zip(m["sensor"], m["date"], flat)
        ],
        dtype=bool,
    )
    no_ref = m["reference_mean_c"].isna() | (m["n_hours"] < 24)
    gap_filled = (m["n_measured"] < 24) if reference_hours == "measured" else False

    swapped = np.array([(k, d.strftime("%Y-%m-%d")) in swap_days
                        for k, d in zip(m["sensor"], m["date"])], dtype=bool)
    reason = np.select(
        [flat, adjacent, m["coverage"] < min_coverage, no_ref, gap_filled, swapped],
        ["flatline", "flatline_adjacent", "low_coverage", "no_reference", "reference_gap_filled",
         "battery_swap"],
        default="",
    )
    out = pd.DataFrame(
        {
            "date": m["date"].dt.strftime("%Y-%m-%d"),
            "sensor": m["sensor"],
            "sensor_mean_c": m["mean_c"],
            "reference_mean_c": m["reference_mean_c"],
            "difference_c": m["mean_c"] - m["reference_mean_c"],
            "coverage": m["coverage"].round(6),
            "reference_measured_hours": m["n_measured"].astype("Int64"),
            "used": reason == "",
            "excluded_reason": reason,
        }
    )
    return out


def main(summary, reference_daily, station, reference_hours, min_coverage, battery_swaps,
         swap_steps, out) -> None:
    if min_coverage not in MIN_COVERAGE:
        raise ValueError(f"unknown min_coverage option {min_coverage!r}")
    if swap_steps not in SWAP_STEPS:
        raise ValueError(f"unknown swap_steps option {swap_steps!r}")
    swap_days: frozenset[tuple[str, str]] = frozenset()
    if swap_steps == "at_swaps":
        sw = pd.read_csv(battery_swaps)
        sw = sw[sw["mixed"]]
        swap_days = frozenset(zip(sw["sensor"], sw["swap_date"]))
    ref = pd.read_csv(reference_daily)
    ref = ref[ref["station"] == station]
    if ref.empty:
        raise SystemExit(f"no station {station} in {reference_daily}")
    table = screen(pd.read_csv(summary), ref, reference_hours, MIN_COVERAGE[min_coverage],
                   swap_days)
    table.to_csv(out, index=False, float_format="%.6f")


if __name__ == "__main__":
    main(*sys.argv[1:])
