# drift-study

How far the city's 40 low-cost temperature sensors (`s01` to `s40`) drifted
over 2023, against FRPDAS, a station of Freiburg's street-level weather
network.

- Drift per sensor, with 95% intervals: `results/baseline/drift.csv`, linear
  in time beside a temperature-dependent bias, with a free step at each
  battery swap, fitted robustly to outlying days. The intervals add the
  scatter of each sensor's residuals to what its own noise model gives.
  `results/robust_january_gain/drift.csv` takes the sensors' gains out by a
  January calibration instead of the temperature term.
- The simple fit, a line in time by least squares and the baseline until
  `v1`: `results/simple_fit/drift.csv`; and each of the baseline's additions
  made to it alone, `results/temperature_term/`, `results/battery_steps/`
  and `results/huber_fit/`. What each changes,
  `results/robust_comparison.json`.
- The simple fit with each sensor first calibrated against FRPDAS over the
  start of its record, `results/gain_<window>/drift.csv` (a gain and an
  offset) and `results/offset_<window>/drift.csv` (an offset alone), for
  windows of two weeks, one month and three months; what that changes,
  `results/calibration_comparison.json`. The calibration is an analysis of
  its own, in [`calibration/`](calibration/README.md), which this one drives.
- Method, checks and caveats: [`index.md`](index.md). Specification:
  `astra.yaml`.

Versions: the tag `v1` holds the results as first published, with the
simple fit as the baseline, sensor-archive at d6ded91 and noise-models at
6402027 with the 1/f slope fitted per sensor.

Inputs:

- The sensors' despiked daily summaries, read from
  [sensor-archive](https://github.com/tomcharnock-lightcone/sensor-archive)
  at a fixed commit (`analyses.archive` in `astra.yaml`).
- The sensors' daily battery voltage from sensor-archive (`daily_battery`),
  to find battery swaps.
- The sensors' noise models from
  [noise-models](https://github.com/tomcharnock-lightcone/noise-models)
  (`analyses.noise`), likewise at a fixed commit: its default table, Hann
  window with the 1/f slope held at 1 (`noise_models#hann_slope_one`).
- Hourly air temperature of the Freiburg network, Plein, Christen & Dormann,
  *Street-level weather station network in Freiburg, Germany* (L2, 1.0.0),
  [doi:10.5281/zenodo.21307957](https://doi.org/10.5281/zenodo.21307957),
  CC BY 4.0. Streamed from Zenodo and checked against its MD5; only the
  stations' daily means for 2023 (`results/reference_daily.csv`) are kept.

The results are stored with git-annex in this repository's Git LFS storage.
In a clone, run `lc fetch` to get them; `lc materialize local` remakes them.
Tests: `uv run pytest`.
