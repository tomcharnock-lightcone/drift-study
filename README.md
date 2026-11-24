# drift-study

How far the city's 40 low-cost temperature sensors (`s01` to `s40`) drifted
over 2023, against FRPDAS, a station of Freiburg's street-level weather
network.

- Drift per sensor, with 95% intervals: `results/baseline/drift.csv`
  (linear in time) and `results/temperature_term/drift.csv` (linear in time
  plus a temperature-dependent bias). The intervals add the scatter of each
  sensor's residuals to what its own noise model gives.
- The same with each sensor first calibrated against FRPDAS over the start
  of its record, `results/gain_<window>/drift.csv` (a gain and an offset)
  and `results/offset_<window>/drift.csv` (an offset alone), for windows of
  two weeks, one month and three months; what that changes,
  `results/calibration_comparison.json`. The calibration is an analysis of
  its own, in [`calibration/`](calibration/README.md), which this one drives.
- The same with a free step at each battery swap, the sensors' gains taken
  out by the temperature term, and a fit robust to outlying days,
  `results/robust/drift.csv` (`results/robust_january_gain/drift.csv` with
  the January gain calibration instead); what that changes,
  `results/robust_comparison.json`.
- Method, checks and caveats: [`index.md`](index.md). Specification:
  `astra.yaml`.

Inputs:

- The sensors' despiked daily summaries, read from
  [sensor-archive](https://github.com/tomcharnock-lightcone/sensor-archive)
  at a fixed commit (`analyses.archive` in `astra.yaml`).
- The sensors' daily battery voltage from sensor-archive (`daily_battery`),
  to find battery swaps.
- The sensors' noise models from
  [noise-models](https://github.com/tomcharnock-lightcone/noise-models)
  (`analyses.noise`), likewise at a fixed commit.
- Hourly air temperature of the Freiburg network, Plein, Christen & Dormann,
  *Street-level weather station network in Freiburg, Germany* (L2, 1.0.0),
  [doi:10.5281/zenodo.21307957](https://doi.org/10.5281/zenodo.21307957),
  CC BY 4.0. Streamed from Zenodo and checked against its MD5; only the
  stations' daily means for 2023 (`results/reference_daily.csv`) are kept.

The results are stored with git-annex in this repository's Git LFS storage.
In a clone, run `lc fetch` to get them; `lc materialize local` remakes them.
Tests: `uv run pytest`.
