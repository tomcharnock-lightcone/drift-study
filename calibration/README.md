# calibration

Each of drift-study's sensors calibrated against the study's reference
station, FRPDAS, over the start of its record: an offset alone, or a gain and
an offset, fitted to the sensor's daily means against the reference's. The
specification is `astra.yaml`; the study (the analysis one folder up) drives
it, choosing the window (`two_weeks`, `one_month`, `three_months`), the model
(`offset_only`, `gain_and_offset`) and the screening of sensor-days.

It reads the study's `differences` and `reference_daily` and the sensors'
noise models, and gives, per universe of the study that calibrates:

- `coefficients`: per sensor, and per other Freiburg station as a siting
  check, the gain and offset with their errors (`src/calibrate.py`). A
  calibrated reading is (s − o)/g.
- `calibrated`: the study's sensor-days with every reading calibrated, in the
  study's own table layout plus the raw reading and the coefficients
  (`src/apply_calibration.py`).

Both land in the study's `results/<universe>/` as `calibration.coefficients.csv`
and `calibration.calibrated.csv`. The fits share the study's statistics,
`src/drift_stats.py` and `src/noise_propagation.py` one folder up; the tests
are the study's `tests/test_calibration.py`.
