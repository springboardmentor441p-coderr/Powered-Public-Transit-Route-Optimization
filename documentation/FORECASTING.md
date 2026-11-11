# Daily route-demand forecasting

The [forecasting milestone decision](FORECAST_MILESTONE.md) consolidates notebooks 05–07,
defines the future review criteria and records research closure separately from operational acceptance.

The forecasting experiment predicts published daily boarding estimates for 41 Manhattan routes,
combining directions. Each Monday at 00:00 America/New_York, it predicts that Monday through Sunday.
The implemented walkthrough is [notebook 05](../notebooks/new_york/05_demand_forecasting.ipynb).

## Information available at issuance

The default experiment excludes the seven complete payment dates preceding the issue date.
For an issue on Monday 3 August 2026, the most recent available observation is Sunday 26 July.
This is an assumed delay; neither actual historical publication timestamps nor revision vintages
are available. The experiment uses one frozen extract and its existing quality masks. It does not
reconstruct exactly what a planner could have downloaded at each historical issue date.

For each target date, the four latest eligible same-weekday dates supply lag values, a seasonal
mean, standard deviation, observed count and latest value. Under the default delay these dates
are t−14, t−21, t−28 and t−35. Calendar features include weekday, month, annual sine/cosine,
date trend, forecast horizon and the US federal holiday calendar. Route identity is categorical.
Federal holidays do not define agency service calendars. Missing lags remain missing; zeros are
retained. At least two seasonal observations are required for all candidates.

Schedules, full-period route profiles, current target values and target-derived service ratios are
excluded as predictors. Existing GTFS analysis remains available for separate descriptive review.
The 41-route cohort was defined retrospectively and does not evaluate newly introduced routes.

## Evaluation design

- Initial historical examples begin 3 March 2025, with earlier observations available for lag lookups.
- Validation: eight weekly origins, 1 June–20 July 2026; targets through 26 July.
- Test: eight weekly origins, 3 August–21 September 2026; targets through 27 September.
- All fits use expanding training history, with training targets restricted to the issue cutoff.
- Weekly refits may incorporate earlier test outcomes once their assumed delay has elapsed.
- The same eligible route/date rows are scored for every candidate within each experiment.
- Selection uses validation MAE only. The test period does not determine parameters or selection.

The earlier EDA already examined these calendar periods. This is a later-period model holdout,
not a wholly unseen project dataset or a prospective operational test. Independent future collection
is needed for stronger confirmation.

Candidates are a latest-available same-weekday baseline, the mean of four available same-weekdays,
and two Poisson histogram gradient-boosting configurations. Both use 120 iterations, learning rate
0.06, minimum leaf size 30 and L2 regularization 1; maximum leaves are 15 or 31. Native categorical
handling preserves route identity. Early stopping is disabled to avoid random internal validation.
The implementation follows the [scikit-learn estimator documentation](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html).

## Results

Validation selected the 31-leaf boosted model: MAE **441.66**, compared with **505.14** for the
four-week seasonal mean. The final test contains **2,255 route/date observations across 41 routes**.
Of 2,296 expected route/dates, 41 targets on a demand-review date were unavailable. No additional
rows were excluded for insufficient history. Thirteen scored targets are real zeros.

| Test candidate | MAE, boardings/route/day | RMSE | WAPE | Mean signed error |
|---|---:|---:|---:|---:|
| Selected boosted model, 31 leaves | 615.06 | 958.32 | 11.26% | −90.22 |
| Four-week seasonal mean | 630.78 | 989.21 | 11.55% | −152.24 |
| Latest available same weekday | 698.22 | 1,106.21 | 12.79% | −105.22 |

The selected model improves test MAE over the validation-selected baseline by **2.49%**.
This is a modest descriptive gain; statistical significance and operational value are not established.
An independent audit finds improvement in **4 of 8 test weeks** and **25 of 41 routes**.
August MAE is **438.86** versus baseline **401.79**; September MAE is **797.77** versus baseline
**868.25**. Thus the aggregate gain does not apply to every month, route or issue week.

Exploratory whole-week resampling (10,000 replicates, seed 42) gives a central 95% stability
range of **−8.15% to +10.14%** for MAE improvement. The range includes deterioration. Only
eight weekly clusters are available and neighboring weeks may be dependent; this is not formal
significance evidence or an interval for future forecast values. Reliable superiority over the
seasonal baseline has not been established.

Errors rise in the September test weeks and some large boarding values are underpredicted. The
source does not establish the cause. Test error is substantially higher than validation error.

MAE and RMSE use boarding units. WAPE divides total absolute error by total observed boardings,
so high-volume routes have more influence. WAPE is not classification accuracy. Per-route,
equal-route aggregate, horizon and weekly diagnostics are saved in the notebook and local tables.

A sensitivity run with a 28-complete-day assumed delay, using the same selected configuration
and the same 2,255 test route/dates, produces model MAE **558.91** versus baseline **611.79**.
This does not verify a publication delay or establish that older data is inherently preferable;
the available lags and training cutoffs change together. The seven-day protocol remains the
primary result and was not switched after viewing this sensitivity.

## Forecast artifact and reproduction

The final refit uses available targets through 27 September 2026 and saves **287 point forecasts**
for 5–11 October 2026. These are an illustrative historical outlook from a collection downloaded
after that issue date, not forecasts issued in real time. The collection has no outcomes for that
window, so no forecast-window error is reported. This is not a forecast for the current date.

Run from the repository root after generating notebook 02's validated inputs:

```powershell
python -m pip install -r requirements.txt
python scripts/execute_notebooks.py notebooks/new_york/05_demand_forecasting.ipynb
python -m unittest discover -s tests -v
python scripts/audit_forecast.py
```

Local outputs are in `data/processed/new_york/forecasting/` and `reports/forecasting/`.
The manifest stores source/product hashes, category mapping, feature order and package versions.
The selected model is saved locally as `selected_model.pkl`; load only trusted local artifacts.
Three figures and all notebook code outputs are saved. Existing source bytes are unchanged.

## Independent verification

`scripts/audit_forecast.py` independently checks all 57 original source fingerprints, 14 forecast
product hashes, all 23,534 historical feature rows and 94,136 same-weekday lag values against
the cleaned source. It checks target identity, equal candidate scoring populations, exact baseline
predictions, training cutoff row counts and independently recalculates MAE, RMSE, WAPE and bias.
It also verifies validation-based selection, chronological separation and saved notebook execution.
Detailed evidence is saved locally in `reports/forecasting/detailed_review.json`.

Monday-only issue dates make horizon and weekday perfectly associated: horizon 1 is Monday,
horizon 7 is Sunday. Horizon diagnostics mix lead-time and weekday differences. They cannot
establish how error changes with horizon independently of the target weekday. The sensitivity
run also changes both training cutoffs and available lag dates, so it is not a controlled estimate
of publication delay alone.

Before deployment, verify publication timing and revisions, assess route/service changes, evaluate
prospective observations and establish reliable interval coverage. Forecasts do not measure occupancy, delays,
directional demand or the causal benefits of changing service. Clustering, service scenarios and
the Streamlit application remain separate development stages.

## Follow-up: maturity, intervals and additional outcomes

[Notebook 06](../notebooks/new_york/06_forecast_validation.ipynb) preserves the original experiment
and adds a separate follow-up. The publisher's [overview, page 4](https://data.ny.gov/api/views/gxb3-akrn/files/59feac4c-ab4f-44e1-b4bd-188b5edfcc20?filename=MTA_BusHourlyRidership_Overview.pdf)
warns that recent dates within two weeks of posting undercount ridership and that late transactions
revise historical counts. The overview describes daily releases while [portal metadata](https://data.ny.gov/api/views/gxb3-akrn.json)
lists weekly posting. Neither is an exact historical release-latency guarantee. The follow-up excludes
14 complete dates before issuance as a maturity policy; it does not assume that all counts are final.

A new snapshot collected 5 November contains 2,337 route/date rows from 1 September through
27 October, with 1,107 beyond the original collection. A separate publisher denominator query
reconciles exactly. All 1,230 overlapping September rows retain the same boarding totals. This
documents two observed versions, not all intervening historical revisions. A public revision API
read returned 404, and no earlier row-value archive was established. Future polls now retain
immutable exports, receipts and comparison evidence. Public [Socrata archive documentation](https://support.socrata.com/hc/en-us/articles/9486838238743-Introducing-Dataset-Archiving)
describes optional archive functionality; its availability for this dataset remains unestablished.

### Separate calibration protocol

The follow-up uses validation origins 1 June–6 July, calibration origins 27 July–17 August,
and evaluation origins 7–21 September. Validation targets end 12 July and are available by the
first calibration cutoff. Calibration targets end 23 August and are available by the first evaluation
cutoff. These gaps explicitly respect the maturity rule. Model selection is based on validation MAE;
this protocol selects the 15-leaf candidate. Earlier EDA examined the periods, so the evaluation
remains retrospective.

Absolute out-of-sample calibration errors are divided by the maximum of available seasonal mean
and 100 boardings. A finite-rank residual quantile supplies nominal 80% and 90% interval widths.
Lower bounds are clipped to zero. The scale floor, levels and quantile method are fixed before
interval evaluation. There are 1,107 calibration observations and 861 later evaluation route/dates.
Route/date dependence, refitting and temporal shifts prevent an exchangeability guarantee.

| Nominal interval level | Achieved evaluation coverage | Mean width, boardings |
|---|---:|---:|
| 80% | 45.53% | 1,570.36 |
| 90% | 62.83% | 2,247.08 |

These intervals substantially undercover the September evaluation period and are **not reliable
operational uncertainty bounds**. The point model's MAE is 903.44 versus baseline 1,008.43 on this
separate evaluation window; those values are not directly comparable with notebook 05's wider
test window. Calibration code is implemented, but satisfactory interval reliability is not established.
Evaluation outcomes are not used to retune the reported interval results. For future issuance,
interval calibration is refreshed using released out-of-sample errors; its future coverage is pending.

### Later-acquired October outcomes

The preserved notebook 05 forecast for 5–11 October is scored without refitting against 287 later
route/date observations. The original boosted model's MAE is **1,038.44** and WAPE **16.65%**,
compared with seasonal baseline MAE **682.40** and WAPE **10.94%**. The baseline performs better
on this later window. This is a retrospective forecast with later-acquired labels, not a forecast
actually issued in October. The result demonstrates why the initial 2.49% improvement was not
sufficient evidence of reliable superiority.

### Prospective comparison

Model and baseline forecasts for **9–15 November 2026** are saved before those target dates.
Both use only the snapshot observed on 5 November, with training targets through 21 October,
the maturity cutoff on the actual collection date. Neither uses data assumed to arrive on the
future Monday. Each has 287 route/date predictions, two empirical interval levels, a timestamp,
source fingerprints and write-once forecast files. The model artifact is preserved with its registration.
The baseline is registered separately so later comparisons retain the same targets and information.

There are currently **zero scored prospective outcomes**. Under the maturity rule, the full
9–15 November window cannot be mature before **30 November**, and publication may be later.
No prospective performance is claimed. Historical vintages cannot be recreated from new snapshots;
timestamped monitoring establishes evidence only from the dates actually observed.

Run a new poll and score the immutable registrations when mature outcomes exist:

```powershell
python scripts/monitor_ridership.py
python scripts/evaluate_prospective.py --registration <registered-folder> --snapshot <later-snapshot-folder>
python scripts/audit_forecast_followup.py
```

The exact registration paths are printed in notebook 06. Its fixed snapshot path permits offline
reproduction; it does not silently replace inputs with the newest poll. Re-execution verifies and
reuses existing registrations instead of rewriting predictions. Frozen input data, monitoring
snapshots, generated tables and registration artifacts remain excluded from Git.

## Error analysis and development candidates

[Notebook 07](../notebooks/new_york/07_forecast_error_analysis.ipynb) decomposes the observed
weaknesses by route, weekday, issue week, interval-miss direction and realized demand change.
Protocols with different models, dates and maturity rules are kept separate. It then tests
seasonal-anchored point candidates and asymmetric empirical residual bands in a 2025-only
development replay. The mechanism was motivated by the already-examined 2026 errors; this
is not independent confirmation. No later assessment result changes the frozen candidate choice,
and neither November registration is modified. See [findings and decisions](ERROR_ANALYSIS.md).
