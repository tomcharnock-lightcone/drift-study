"""The sensors' battery swaps, from their daily battery voltage.

usage: python src/battery_swaps.py DAILY_BATTERY.csv OUT.csv

DAILY_BATTERY is sensor-archive's daily battery summary per sensor (date,
sensor, n_readings, mean_v, min_v, max_v, first_v, last_v, rise_v). Between
swaps a battery's voltage only falls, so every day with rise_v > 0 holds a
swap. One row per swap: sensor; swap_date, the day of the rise; v_before_v
and v_after_v, the voltage either side of it; mixed, whether readings from
both batteries share that day (its first reading is below the new
battery's, so the swap came after it); and first_new_date, the first day
read wholly on the new battery: swap_date itself if not mixed, else the
sensor's next day with readings.
"""

from __future__ import annotations

import sys

import pandas as pd


def swaps(battery: pd.DataFrame) -> pd.DataFrame:
    battery = battery.sort_values(["sensor", "date"]).reset_index(drop=True)
    rows = []
    for i in battery.index[battery["rise_v"] > 0]:
        day = battery.loc[i]
        after = day["max_v"]  # a fresh battery's voltage then only falls
        mixed = bool(day["first_v"] < after)
        nxt = battery[(battery["sensor"] == day["sensor"]) & (battery["date"] > day["date"])]
        first_new = (nxt["date"].iloc[0] if len(nxt) else None) if mixed else day["date"]
        rows.append({
            "sensor": day["sensor"],
            "swap_date": day["date"],
            "v_before_v": round(after - day["rise_v"], 4),
            "v_after_v": after,
            "mixed": mixed,
            "first_new_date": first_new,
        })
    columns = ["sensor", "swap_date", "v_before_v", "v_after_v", "mixed", "first_new_date"]
    return pd.DataFrame(rows, columns=columns)


def main(daily_battery: str, out: str) -> None:
    swaps(pd.read_csv(daily_battery)).to_csv(out, index=False)


if __name__ == "__main__":
    main(*sys.argv[1:])
