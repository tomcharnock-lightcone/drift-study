"""Each sensor's drift in an earlier version of this analysis against today's.

usage: python src/compare_versions.py table NAME EARLIER.csv SAME_MODEL.csv NOW.csv OUT.csv
       python src/compare_versions.py summary NAME TABLE.csv OUT.json

EARLIER is the drift table of the earlier version NAME's baseline,
SAME_MODEL today's fit under that baseline's model on today's inputs, and
NOW today's baseline. Between EARLIER and SAME_MODEL only the inputs
changed (the versions of the analyses read, and what they give); between
SAME_MODEL and NOW only the model. So each change in a sensor's drift, its
error, or whether its 95% interval excludes zero is split into the two.

table: one row per sensor, sorted by the change in drift. For each of the
three fits, drift_c_per_year, drift_se_c_per_year and significance (up,
down or none: the 95% interval above zero, below it, or holding it),
prefixed NAME_, same_model_ and now_. Then the change from NAME to now,
drift_change_c_per_year, in units of NAME's error
(drift_change_in_NAME_se), and se_ratio_to_NAME; the same split into
_from_inputs (SAME_MODEL against EARLIER) and _from_model (NOW against
SAME_MODEL); significance_changed_by, which of the two steps changed the
sensor's significance, blank where it ends as it began; and
n_battery_swaps, where NOW fits a step at each.

summary: for the network, in each fit, the median and mean drift, how many
sensors drift upward, how many significantly up and down, and the median
error. Then the median and largest change in drift and which sensor moves
most, how many move by more than NAME's error, and the largest change from
the inputs and from the model; the median ratio of the errors to NAME's,
and the range of that ratio from the inputs alone; and every sensor whose
significance changed, with its significance before and after and which
step changed it.
"""

from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

FITS = ("earlier", "same_model", "now")


def significance(t: pd.DataFrame) -> pd.Series:
    low, high = t["drift_ci95_low_c_per_year"], t["drift_ci95_high_c_per_year"]
    return pd.Series(np.where(low > 0, "up", np.where(high < 0, "down", "none")), index=t.index)


def table(name: str, earlier: pd.DataFrame, same_model: pd.DataFrame, now: pd.DataFrame) -> pd.DataFrame:
    """The per-sensor comparison, from the three drift tables indexed by sensor."""
    for label, t in [("same_model", same_model), ("now", now)]:
        if not t.index.sort_values().equals(earlier.index.sort_values()):
            raise ValueError(f"{label} does not list {name}'s sensors")
    same_model, now = same_model.loc[earlier.index], now.loc[earlier.index]
    out = pd.DataFrame(index=earlier.index)
    sig = {}
    for prefix, t in [(name, earlier), ("same_model", same_model), ("now", now)]:
        out[f"{prefix}_drift_c_per_year"] = t["drift_c_per_year"]
        out[f"{prefix}_drift_se_c_per_year"] = t["drift_se_c_per_year"]
        out[f"{prefix}_significance"] = sig[prefix] = significance(t)
    b, s = earlier["drift_c_per_year"], earlier["drift_se_c_per_year"]
    out["drift_change_c_per_year"] = now["drift_c_per_year"] - b
    out[f"drift_change_in_{name}_se"] = out["drift_change_c_per_year"] / s
    out[f"se_ratio_to_{name}"] = now["drift_se_c_per_year"] / s
    out["drift_change_from_inputs_c_per_year"] = same_model["drift_c_per_year"] - b
    out["se_ratio_from_inputs"] = same_model["drift_se_c_per_year"] / s
    out["drift_change_from_model_c_per_year"] = now["drift_c_per_year"] - same_model["drift_c_per_year"]
    out["se_ratio_from_model"] = now["drift_se_c_per_year"] / same_model["drift_se_c_per_year"]
    by = []
    for sensor in out.index:
        steps = [step for step, (a, z) in [("inputs", (name, "same_model")), ("model", ("same_model", "now"))]
                 if sig[a][sensor] != sig[z][sensor]]
        by.append(", ".join(steps) if sig[name][sensor] != sig["now"][sensor] else "")
    out["significance_changed_by"] = by
    if "n_battery_swaps" in now:
        out["n_battery_swaps"] = now["n_battery_swaps"].astype(int)
    out = out.sort_values("drift_change_c_per_year")
    out.index.name = "sensor"
    return out.round(4)


def network(t: pd.DataFrame, prefix: str) -> dict:
    d, sig = t[f"{prefix}_drift_c_per_year"], t[f"{prefix}_significance"]
    return {
        f"{prefix}_median_drift_c_per_year": round(float(d.median()), 4),
        f"{prefix}_mean_drift_c_per_year": round(float(d.mean()), 4),
        f"{prefix}_n_drifting_up": int((d > 0).sum()),
        f"{prefix}_n_significantly_up": int((sig == "up").sum()),
        f"{prefix}_n_significantly_down": int((sig == "down").sum()),
        f"{prefix}_median_drift_se_c_per_year": round(float(t[f"{prefix}_drift_se_c_per_year"].median()), 4),
    }


def summary(name: str, t: pd.DataFrame) -> dict:
    change = t["drift_change_c_per_year"].abs()
    inputs = t["drift_change_from_inputs_c_per_year"].abs()
    model = t["drift_change_from_model_c_per_year"].abs()
    changed = t[t["significance_changed_by"] != ""]
    return {
        "compared_with": name,
        "n_sensors": len(t),
        "network": network(t, name) | network(t, "same_model") | network(t, "now"),
        "drift_change": {
            "median_abs_drift_change_c_per_year": round(float(change.median()), 4),
            "max_abs_drift_change_c_per_year": round(float(change.max()), 4),
            "sensor_of_max": change.idxmax(),
            f"n_sensors_moved_beyond_{name}_se": int((t[f"drift_change_in_{name}_se"].abs() > 1).sum()),
            "max_abs_drift_change_from_inputs_c_per_year": round(float(inputs.max()), 4),
            "max_abs_drift_change_from_model_c_per_year": round(float(model.max()), 4),
            "median_abs_drift_change_from_model_c_per_year": round(float(model.median()), 4),
        },
        "drift_se": {
            f"median_se_ratio_to_{name}": round(float(t[f"se_ratio_to_{name}"].median()), 3),
            "median_se_ratio_from_inputs": round(float(t["se_ratio_from_inputs"].median()), 3),
            "min_se_ratio_from_inputs": round(float(t["se_ratio_from_inputs"].min()), 3),
            "max_se_ratio_from_inputs": round(float(t["se_ratio_from_inputs"].max()), 3),
            "median_se_ratio_from_model": round(float(t["se_ratio_from_model"].median()), 3),
        },
        "n_sensors_significance_changed": len(changed),
        "significance_changes": {
            sensor: f"{r[f'{name}_significance']} to {r['now_significance']}, by the {r['significance_changed_by']}"
            for sensor, r in changed.sort_index().iterrows()
        },
    }


def main(mode: str, name: str, *paths: str) -> None:
    if mode == "table":
        earlier, same_model, now, out = paths
        read = lambda p: pd.read_csv(p, keep_default_na=False, na_values=[""]).set_index("sensor")
        table(name, read(earlier), read(same_model), read(now)).to_csv(out)
    elif mode == "summary":
        path, out = paths
        t = pd.read_csv(path, keep_default_na=False, na_values=[""]).set_index("sensor")
        t["significance_changed_by"] = t["significance_changed_by"].fillna("")
        with open(out, "w") as fh:
            json.dump(summary(name, t), fh, indent=2)
            fh.write("\n")
    else:
        raise SystemExit(f"unknown mode {mode!r}: table or summary")


if __name__ == "__main__":
    main(*sys.argv[1:])
