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
which summary it used; the raw readings are not needed. The archive's daily
battery summary (`daily_battery`) gives each sensor's battery voltage per day,
from which the battery swaps are found.

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

**Battery swaps and a robust fit.** Some sensors had their battery swapped
during the year. Between swaps a battery's voltage only falls, so a day on
which it rises is a swap (`src/battery_swaps.py`,
`results/battery_swaps.csv`). A swap can shift a sensor's reading at once,
and a line fitted through such a step reads it as drift. Under the decision
`swap_steps`, the fit gets a free step at each swap, from the first day read
wholly on the new battery, and the day of the swap, which mixes two
batteries, is left out. Under `fit_method`, Huber's M-estimate replaces least
squares: a day far from the line counts in proportion to its distance rather
than its square, so a few outlying days cannot pull the fit
(`src/drift_stats.py`; `tests/test_drift_stats.py` checks that it agrees
with least squares on clean data, resists outliers, and keeps its intervals'
coverage). The noise model is propagated through the fit's final weights.

| Universe | Battery swaps | Fit |
|---|---|---|
| `battery_steps` | a step at each | least squares |
| `huber_fit` | no allowance | Huber |
| `robust` | a step at each | Huber |

Every other choice is the baseline's.

**Calibration first.** A drift is what changes in a sensor after it was set
up, so the analysis also calibrates each sensor against FRPDAS over the start
of its record and fits the drift to the calibrated readings. The calibration
is an analysis of its own, in `calibration/` (`calibration/astra.yaml`),
which this one drives and which can be reused. Over the window it fits the
sensor's daily means on the days the study uses, as

$$
s = g\,r + o \qquad\text{or}\qquad s = r + o,
$$

with $s$ the sensor's daily mean and $r$ the reference's: a gain $g$ and an
offset $o$, or an offset alone. Each reading of the year then becomes
$(s - o)/g$ (`calibration.calibrated.csv`), and the drift is fitted to the
calibrated difference exactly as before. The gain's error adds the residuals'
(AR(1)) and the noise model's, as the drift's does, and is carried into the
drift's error: the drift moves with the gain as
$\partial b/\partial g = -\sum_j w_j (s_j - o)/g^2$, with $w$ the fit's
weights (`drift_se_calibration_c_per_year` in `drift.csv`; checked against a
numerical derivative in `tests/test_calibration.py`). An offset alone cannot
move a drift that is fitted with an offset of its own, and is built
anyway, as the check and for its calibrated readings.

A gain against a station elsewhere is not only the sensor's: two sites that
answer the weather differently, one with a wider daily and seasonal swing
than the other, show a gain between them. So `calibration/src/calibrate.py`
calibrates Freiburg's other stations against FRPDAS the same way, over the
same window (`calibration.coefficients.csv`, `kind = station`), as what siting
alone puts into a gain.

| Universe | Window | Calibration |
|---|---|---|
| `offset_two_weeks` | 1–14 January | offset |
| `offset_one_month` | January | offset |
| `offset_three_months` | January to March | offset |
| `gain_two_weeks` | 1–14 January | gain and offset |
| `gain_one_month` | January | gain and offset |
| `gain_three_months` | January to March | gain and offset |

Every other choice is the baseline's. A longer window has more days and a
wider range of temperatures to fit a gain to, but more of the year's drift
happens inside it.

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

```{figure} results/robust_drift.png
:label: fig-robust
Each sensor's drift in the baseline and in the robust universe, with a step
at each battery swap and Huber's fit. `results/robust/difference_series.png`
shows the steps.
```

**Three sensors had a battery swap**, and their differences step there
(finding `battery_swaps_found`). **The steps matter for those three**
([](#fig-robust), finding `battery_steps_matter`): with a step at its swap,
`s20`, which had the largest drift of all, drifts no more than most, and
`s02` and `s34` drift less. **Outliers do not matter** (finding
`outliers_immaterial`): the screening has already removed the bad days, and
Huber's fit leaves every drift where it was. **The conclusion stands**
(finding `robust_agrees`): with both, the sensors still drift upward as a
group, and only the swapped sensors move.

```{figure} results/calibration_gains.png
:label: fig-gains
Each sensor's calibration gain against FRPDAS with its 95% interval, over
each window. The grey band is the 5th–95th percentile of the gains of
Freiburg's other stations against FRPDAS over the same window.
```

```{figure} results/calibration_drift.png
:label: fig-calibration
Each sensor's drift uncalibrated (baseline) and calibrated with a gain and an
offset over each window.
```

**Calibrating an offset changes nothing** (finding
`offset_calibration_changes_nothing`): the drift fit has an offset of its
own, so a constant correction moves only that.

**Many sensors have a gain** ([](#fig-gains), finding `sensors_have_gains`),
and it is not an accident of the window: a sensor's gain over January
follows the temperature coefficient fitted to its whole year closely, and
calibrating it out shrinks the residual scatter over the rest of the year.
Over three months, the five largest gains (`s22`, `s23`, `s07`, `s11`,
`s06`) belong to the five sensors with the largest temperature coefficients
over the year, and the smallest (`s21`, `s28`, `s33`) to sensors with some of
the most negative: the sensors whose differences follow the seasons
([](#fig-series)).

**Part of a gain is the site** (finding `gains_not_only_the_sensors`).
Freiburg's maintained stations, calibrated against FRPDAS over January, show
gains spread as widely as the sensors'; over three months the stations'
narrow while the sensors' barely do. So some sensors have a gain beyond what
siting gives, but which ones cannot be said without knowing where they
stand.

**A gain calibration moves the drift as much as the temperature term
does** ([](#fig-calibration), finding `gain_calibration_moves_drift`), and
in the same direction: the seasonal pattern a gain causes is what the
temperature term absorbs, fitted from January instead of from the whole
year. The network's median drift falls by about a sixth. Calibrated over
January, `s11`, `s12` and `s23` no longer drift significantly, and `s22` and
`s28`, whose seasonal cycle had widened their intervals, now do.

**Two weeks is too short for a gain** (finding `calibration_window`): the
first fortnight of 2023 was mild, with little range in temperature, so its
gains are uncertain, and carried into the drift they widen its interval by
about a fifth. A month does nearly as well as three.

## Caveats

- **A drift against one station is not the sensor's alone.** It includes how
  the two sites differ in their response to a year's weather. Among
  Freiburg's own maintained stations those differences already produce
  apparent drifts ([](#fig-drift), grey band), so a sensor's drift inside
  that band cannot be told apart from where the sensor stands, unless it is
  known to be co-located with FRPDAS. This analysis does not know where the
  sensors are.
- **A straight line is not always the right shape.** The differences of
  `s02`, `s20` and `s34` step at their battery swaps, which the baseline
  draws a slope through and the robust universe allows for. `s20`'s is a
  clean step; `s02`'s and `s34`'s jump at the swap and settle back over some
  weeks ([](#fig-series)), which one step fits only roughly. Other sensors'
  differences follow the seasons, which the temperature term absorbs.
- **One year.** A linear drift and a seasonal effect are hard to separate
  within one annual cycle; the temperature term separates them only as far as
  its own assumptions hold. A second year of data would settle it.
- **A calibration against one station includes the site.** A gain or offset
  fitted against FRPDAS is the sensor's and its site's together; Freiburg's
  own stations show gains of similar size against FRPDAS ([](#fig-gains)).
  Calibrating removes both, which is right for tracking a sensor against
  this reference and wrong for correcting its readings anywhere else.
- **The calibration window is part of the year.** Its days are fitted twice,
  for the calibration and for the drift, and the two errors are treated as
  independent. Over three months the gain also absorbs some of the drift
  that happens within the window, as the weather warms in March, and `s02`'s
  window holds its battery swap.
- **Each half of the uncertainty rests on an assumption.** The residuals'
  part assumes AR(1) residuals, and is too narrow where they carry slower
  structure (a seasonal shape the model misses). The noise models' part
  extends a week-long chamber run at about 20 °C to a year and to the
  field's temperatures, which noise-models itself does not vouch for. The
  spread of the stations' apparent drifts is the most conservative
  yardstick.
