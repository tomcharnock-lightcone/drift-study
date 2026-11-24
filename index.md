# drift-study

How far did each of the city's 40 low-cost temperature sensors (`s01` to
`s40`) drift over 2023? Each sensor's daily mean is compared with that of a
reference station, FRPDAS of Freiburg's street-level weather network, and a
linear drift is fitted to the daily difference, sensor by sensor. The
analysis is specified in `astra.yaml` (ASTRA 0.1) and run with lightcone-cli
(`lc`). This report quotes no measured value: the numbers live in the results
it names, and the claims made from them are the `findings` of `astra.yaml`.

## Data

**Sensors.** The despiked daily summaries of
[sensor-archive](https://github.com/tomcharnock-lightcone/sensor-archive)
(`daily_summary`, universe `despiked`): one row per sensor per UTC day with
the mean, minimum and maximum of the day's ten-second readings, how many there
were, and how many despiking removed. They are read from GitHub at the commit
`astra.yaml` declares (`analyses.archive`), so the result records exactly
which summary it used; the raw readings are not needed.

**Reference.** Hourly air temperature of the Freiburg network, Plein, Christen
& Dormann, *Street-level weather station network in Freiburg, Germany: Curated
dataset from 2022-09-01 to 2024-08-31* (L2, 1.0.0),
[doi:10.5281/zenodo.21307957](https://doi.org/10.5281/zenodo.21307957), CC BY
4.0. The file holds every station in one table, so `src/reference_daily.py`
streams it whole, checks its MD5 against the one Zenodo publishes, and keeps
only each station's daily means for 2023 (`results/reference_daily.csv`); the
file itself is not stored. Its timestamps are UTC. The record does not say
whether a timestamp marks the start or the end of its hour; they are taken as
given. A one-hour shift moves single daily means, but moves a year's linear
trend far less than its uncertainty (checked while building the analysis).

The file is gap-filled: an hour a station missed is replaced by a model
prediction, marked `predicted`. For FRPDAS that touches a handful of days in
2023, and whether to use them is a decision (below).

## Methods

**Daily difference.** For each sensor-day, `src/differences.py` takes the
sensor's daily mean minus FRPDAS's, and marks the days not to use
(`results/<universe>/differences.csv`, column `excluded_reason`):

- *flatline*: every reading of the day the same value. Sensor `s37` reported
  one constant value for about a month in May and June: stuck, not measuring.
  Left in, those days alone pull its fitted drift by a large amount.
- *flatline_adjacent*: the day before and after a flatline day, since the
  summary cannot tell how much of them was stuck.
- *low_coverage*: a sensor-day with less than a threshold share of its 8640
  readings. A partial day's mean is biased by whichever part of the daily
  cycle is missing, and such days stand out in the differences by up to
  several °C. Readings removed by despiking count as delivered: they are
  isolated single readings and leave no hole in the day.
- *reference_gap_filled*: a day on which some of FRPDAS's hours are
  predictions, where the `measured` option is chosen.

**Drift.** `src/fit_drift.py` fits each sensor's used days by least squares,

$$
d(t) = a + b\,t \qquad\text{or}\qquad d(t) = a + b\,t + c\,(T_\mathrm{ref} - \bar T_\mathrm{ref}),
$$

with $d$ the daily difference (°C), $t$ the time from 2023-07-02 in years, so
that $b$ is the drift in °C per year and $a$ the difference at mid-year. The
second form is the `time_and_temperature` drift model (below).

**Uncertainties.** A sensor's daily differences are far from independent:
whatever makes one day's difference large (sun, wind, two sites answering the
same weather differently) persists for days, so the residuals are strongly
autocorrelated (`residual_lag1_autocorr` in `drift.csv`). Ordinary
least-squares errors would understate the uncertainty several times over
(`drift_ols_se_c_per_year` is kept for comparison). The errors are instead
scaled by the effective sample size of AR(1) residuals, as Santer et al.
([2000](https://doi.org/10.1029/1999JD901105)) do for temperature trends,
with Student-t intervals. Newey–West errors were tried first and rejected:
on simulated residuals as persistent as these, their 95% intervals covered
the true trend only 80–90% of the time, against 92–95% for the AR(1)
adjustment. `tests/test_drift_stats.py` repeats that comparison.

**Uncertainties from what is known about the sensors.**
[noise-models](https://github.com/tomcharnock-lightcone/noise-models)
measured each sensor's noise in a climate chamber: a white floor plus a 1/f
part, given by its power spectral density (the Hann-window models, read at
the commit `astra.yaml` declares as `analyses.noise`). A fitted drift is a
weighted sum of daily means, so its variance under that noise is an integral
of the spectrum through the daily-mean filter and the fit's weights
(`src/noise_propagation.py`; `tests/test_noise_propagation.py` checks it
against the textbook white-noise case and against fits to simulated years of
1/f noise). The 1/f part matters here: it keeps wandering over months, which
an AR(1) model of the residuals, with its short memory, does not capture.

This is the sensor's own noise only. The residuals also carry the two sites
answering the weather differently, and the reference's noise, which the
noise model knows nothing of. Comparing the day-to-day change the noise model
predicts with the residuals' own (`noise_day_step_sd_c` and
`observed_day_step_sd_c` in `drift.csv`) gives the share of the daily
scatter the sensor's noise explains. And the noise model reaches a year only
by extending a week-long chamber run, at about 20 °C, some three decades
below its lowest fitted frequency; noise-models itself warns that its models
say nothing beyond a week or at other temperatures.

Since neither error is complete, every `drift.csv` carries both
(`drift_se_residual_c_per_year`, `drift_se_noise_model_c_per_year`), and the
decision `drift_errors` picks the one the quoted error and interval use: the
residuals', the noise model's, or both variances added (`combined`, which
counts the sensor's day-to-day noise twice and so errs wide). The baseline
adds them; each alone is built for comparison.

**Decisions, each built in its own universe:**

| Universe | Reference days | Sensor-day coverage | Drift model | Drift errors |
|---|---|---|---|---|
| `baseline` | measured only | ≥ 99% | linear in time | both added |
| `temperature_term` | measured only | ≥ 99% | + temperature-dependent bias | both added |
| `gap_filled_reference` | gap-filled too | ≥ 99% | linear in time | both added |
| `coverage_90` | measured only | ≥ 90% | linear in time | both added |
| `residual_errors` | measured only | ≥ 99% | linear in time | residuals |
| `noise_model_errors` | measured only | ≥ 99% | linear in time | noise model |

The temperature term is there because a sensor whose bias depends on
temperature (a gain error, or a radiation shield that lets warm, sunny days
heat it) shows a seasonal cycle in its difference from the reference. That
cycle is not drift, but 2023 is not symmetric about mid-year, so part of it
projects onto a straight line. With the reference temperature as a regressor
the two are separated, provided the temperature dependence is linear and
steady over the year.

**Is the reference stable?** A drift of FRPDAS would appear, reversed, in
every sensor. `src/reference_check.py` fits FRPDAS against the median of the
network's other stations, and fits each of those stations against FRPDAS
(`results/reference_check.json`). The second tells how much apparent drift two
maintained stations show against each other over one year, from nothing but
different sites answering the same weather differently.

## Results

```{figure} results/baseline/drift_summary.png
:label: fig-drift
Each sensor's drift against FRPDAS with its 95% interval (baseline: the
residuals' and the noise models' errors added). The grey band is the 5th–95th percentile of the apparent drifts of Freiburg's
other stations against FRPDAS over the same year.
`results/temperature_term/drift_summary.png` is the same with the
temperature term.
```

```{figure} results/baseline/difference_series.png
:label: fig-series
Every sensor's daily difference from FRPDAS (dots), the days excluded
(rings, pinned to the panel's edge when beyond it), and the fitted drift.
```

```{figure} results/model_comparison.png
:label: fig-models
Each sensor's drift with and without the temperature term.
```

```{figure} results/error_comparison.png
:label: fig-errors
Each sensor's drift error from its residuals and from its noise model. The
baseline's error is the two added in quadrature.
```

**The sensors drift upward as a group** ([](#fig-drift)): more than half of
them by more than their uncertainty, a few downward, and a handful not measurably at
all (finding `sensors_drift_upward`; every sensor's numbers are in
`results/baseline/drift.csv`). **The reference is not the cause:** FRPDAS
shows no significant drift against the rest of the Freiburg network (finding
`reference_stable`).

**Where the uncertainty comes from** ([](#fig-errors), finding
`both_error_sources_matter`). For some sensors the residuals' scatter
dominates: their differences carry the sites' different response to the
weather, which the sensor's own noise cannot explain (`s22`, `s21`, `s07`,
`s15`). For others the sensor's slow 1/f wander, as its chamber model
extends it over a year, outweighs what the residuals show (`s13`, `s30`,
`s32`, `s24`), and an AR(1) model of the residuals would have made their
drift look far more certain than it is. At the scale of a day the sensor's
own noise accounts for a minority of the scatter for most sensors
(`noise_day_step_sd_c` against `observed_day_step_sd_c` in `drift.csv`),
and never more than all of it, a check that the noise models hold outside
the chamber at least that far.

**How much of that is the sensors?** Freiburg's own maintained stations,
compared with FRPDAS over the same year, show apparent drifts from their
siting alone (the grey band in [](#fig-drift), finding `siting_floor`). The
sensors well outside that band have drifted, wherever they stand; those
inside it may simply stand somewhere that answers the year's weather
differently from FRPDAS.

**The temperature term matters for some sensors**
([](#fig-models), finding `temperature_term_matters`). Where a sensor's
difference follows the seasons, rising in summer or falling, as for `s06`,
`s07`, `s15` and `s22` or `s21`, `s28` and `s33` ([](#fig-series)), the term
absorbs that cycle: its residuals shrink, its interval narrows, and its
drift moves by up to about the time-only fit's own uncertainty. Where the
difference is a clean ramp, as for `s09`, `s16`, `s29` or `s30`, both models
agree. Which drift to quote for a
seasonal sensor depends on whether its temperature dependence is believed to
be steady; with one year of data the analysis cannot say.

**The screening choices do not matter.** Counting the reference's gap-filled
days or lowering the coverage threshold leaves every drift within a fraction
of its uncertainty (finding `screening_choices_immaterial`,
`results/universe_comparison.json`).

## Caveats

- **A drift against one station is not the sensor's alone.** It includes how
  the two sites differ in their response to a year's weather. Among
  Freiburg's own maintained stations those differences already produce
  apparent drifts ([](#fig-drift), grey band), so a sensor's drift inside
  that band cannot be told apart from where the sensor stands, unless it is
  known to be co-located with FRPDAS. This analysis does not know where the
  sensors are.
- **A straight line is not always the right shape.** Some sensors' differences
  jump rather than drift: `s20` steps up around mid-year and `s02` steps down
  around March ([](#fig-series)), as a relocation, replacement or
  recalibration would. Their fitted drift is a slope drawn through a step.
  Others follow the seasons, which the temperature term absorbs.
- **One year.** A linear drift and a seasonal effect are hard to separate
  within one annual cycle; the temperature term separates them only as far as
  its own assumptions hold. A second year of data would settle it.
- **Each half of the uncertainty rests on an assumption.** The residuals'
  part assumes AR(1) residuals, and is too narrow where they carry slower
  structure (a seasonal shape the model misses). The noise models' part
  extends a week-long chamber run at about 20 °C to a year and to the
  field's temperatures, which noise-models itself does not vouch for. The
  spread of the stations' apparent drifts is the most conservative
  yardstick.
