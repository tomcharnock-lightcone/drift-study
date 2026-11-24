import json

import pandas as pd
import pytest

import compare_versions


def drifts(rows):
    """Drift tables from (sensor, drift, se), with the 95% interval at ±2 se."""
    t = pd.DataFrame(rows, columns=["sensor", "drift_c_per_year", "drift_se_c_per_year"]).set_index("sensor")
    t["drift_ci95_low_c_per_year"] = t["drift_c_per_year"] - 2 * t["drift_se_c_per_year"]
    t["drift_ci95_high_c_per_year"] = t["drift_c_per_year"] + 2 * t["drift_se_c_per_year"]
    return t


EARLIER = drifts([("s01", 1.0, 0.2), ("s02", 0.5, 0.2), ("s03", -0.1, 0.2), ("s04", 0.3, 0.1)])
# The same model on new inputs: drifts as before, errors changed (s02 and s04 lose significance).
SAME = drifts([("s01", 1.0, 0.2), ("s02", 0.5, 0.3), ("s03", -0.1, 0.2), ("s04", 0.3, 0.2)])
# A new model: s01 moves down to none, s03 becomes significantly down, s04 gets its significance back.
NOW = drifts([("s01", 0.2, 0.2), ("s02", 0.5, 0.3), ("s03", -0.6, 0.1), ("s04", 0.35, 0.1)])


def test_significance_reads_the_interval():
    sig = compare_versions.significance(drifts([("a", 1.0, 0.2), ("b", -1.0, 0.2), ("c", 0.1, 0.2)]))
    assert sig.to_dict() == {"a": "up", "b": "down", "c": "none"}


def test_each_change_is_split_into_inputs_and_model():
    t = compare_versions.table("v1", EARLIER, SAME, NOW)
    assert t.loc["s01", "drift_change_c_per_year"] == pytest.approx(-0.8)
    assert t.loc["s01", "drift_change_in_v1_se"] == pytest.approx(-4.0)
    assert t.loc["s01", "drift_change_from_inputs_c_per_year"] == 0
    assert t.loc["s01", "drift_change_from_model_c_per_year"] == pytest.approx(-0.8)
    assert t.loc["s02", "se_ratio_from_inputs"] == pytest.approx(1.5)
    assert t.loc["s02", "se_ratio_from_model"] == pytest.approx(1.0)
    assert t["significance_changed_by"].to_dict() == {
        "s01": "model", "s02": "inputs", "s03": "model", "s04": ""}
    assert list(t.index) == ["s01", "s03", "s02", "s04"]  # sorted by the change in drift


def test_a_sensor_must_be_in_every_table():
    with pytest.raises(ValueError):
        compare_versions.table("v1", EARLIER, SAME.drop("s04"), NOW)


def test_summary_from_the_written_table(tmp_path):
    table, out = tmp_path / "t.csv", tmp_path / "s.json"
    compare_versions.table("v1", EARLIER, SAME, NOW).to_csv(table)
    compare_versions.main("summary", "v1", str(table), str(out))
    s = json.loads(out.read_text())
    assert s["network"]["v1_n_significantly_up"] == 3
    assert s["network"]["now_n_significantly_up"] == 1
    assert s["network"]["now_n_significantly_down"] == 1
    assert s["drift_change"]["sensor_of_max"] == "s01"
    assert s["drift_change"]["max_abs_drift_change_from_inputs_c_per_year"] == 0
    assert s["n_sensors_significance_changed"] == 3
    assert s["significance_changes"] == {
        "s01": "up to none, by the model",
        "s02": "up to none, by the inputs",
        "s03": "none to down, by the model",
    }
