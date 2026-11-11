# CTA Public Transit Route Optimization

RouteRanker is a Chicago CTA bus-demand exploration and planning prototype. It
combines route-level ridership evidence, retrospective model evaluation,
one-day forecasts and bounded trip-allocation scenarios. It preserves exact
route/date observations and labels unsupported operational conclusions clearly.

## Mentor guide v3: selected development model

The Colab workflow follows the mentor's 10 Nov 2026 v3 guide. Open
[notebooks/cta_ridership_colab.ipynb](notebooks/cta_ridership_colab.ipynb) in
Colab and run from the top. It compares last-week and past-four-weekday
baselines with pooled Linear Regression, Random Forest, and the earlier
HistGradientBoosting model. Validation MAE selects the serving method; the
matched demand-only/service-aware comparison uses identical route/date rows.

The first v3 run selected the **demand-only Random Forest** on paired validation
data (MAE 340.96, WAPE 6.51% on 6,859 rows). On the matched June-July test rows,
it scored MAE 373.60, RMSE 632.49, and WAPE 7.58% on 7,014 rows. The matched
past-four-same-weekdays baseline scored MAE 402.65 and WAPE 8.17%, so the
selected model reduced MAE and WAPE by about 7.2%. The service-aware Random
Forest was slightly better on this test (MAE 371.89) but worse on validation
(MAE 350.88), so validation-based selection correctly keeps demand-only as the
current development champion; the test-period difference alone is not grounds
to switch models.

The broader demand-only reference split narrowly preferred
HistGradientBoosting on validation (MAE 321.67 versus 322.36 for Random
Forest), but it uses different dates and rows from the matched comparison. On
the common matched split, Random Forest beat HistGradientBoosting on both
validation (340.96 versus 352.27 MAE) and test (373.60 versus 384.36 MAE). The
Random Forest is therefore the chosen v3 serving candidate for the matched
configuration comparison; the broader split's HGB score is retained as a
separate reference, not treated as a like-for-like result.

This is a daily rolling one-step replay: each test-day prediction may use
observed ridership through the assumed D-1 cutoff, including actual rides from
earlier test days. It is not a forecast issued once for the full two-month
horizon. June-July was also evaluated in earlier project iterations, so this
is development evidence rather than a fresh final holdout.

The mentor's frozen ridership CSV was not supplied with the updated guide. The
notebook therefore downloads the current official export unless
My Drive/cta_bus_ridership.csv is present, fingerprints the exact bytes, and
records whether its hash matches the guide. If it does not match, treat the run
as updated-source development evidence, not an exact reproduction. The
one-day ridership reporting delay is an explicit but unverified assumption.

For this run the input SHA-256 was
`d9675570e50a1b3d1fe7142ea9b10ba76099c1312ab0c227745ac57205eb5c04`, which
does not match the mentor snapshot hash. The training targets nevertheless
covered the guide's demand-only date windows and row counts. For the paired
window, strict same-day GTFS exclusion left 2025-11-23 without an eligible
snapshot; there were 14,415 matched training rows (86 fewer than the guide's
reference count), 6,859 validation rows, and 7,014 test rows. The test schedule
coverage was 7,014 of 7,109 demand rows (98.66%). Because the eight schedules
were uploaded as extracted folders, their table fingerprints are recorded but
the original ZIP SHA-256 values are unverified.

The reviewed metrics, GTFS import audit, forecast-only replay, and separate
actuals-for-scoring file are preserved in `outputs/reports/` and
`outputs/predictions/`. The refreshed Colab result bundle is stored locally at
`models/cta_route_ranker_v3_results.zip` and ignored by Git. Its selected model
was refit after test scoring on 87,563 rows through 2026-08-31; its SHA-256 is
`d139d13debfeaa36b34fa70a3eeb64f4d05f07199bf13d91aa2da8c186176b4d`. The
reported June-July test scores remain from the pre-refit evaluation models.

After training, `src.predict_v3.predict_daily_routes` loads the selected v3
bundle and forecasts one issue date at a time. It rejects ridership newer than
the assumed reporting cutoff and, when the selected configuration needs
schedules, requires route/date schedules with capture dates strictly before
the forecast date. Pass known target routes and day types as a dataframe with
`route`, `date`, and `daytype`; operational use still requires verifying CTA's
publication timing and the calendar inputs.

## Previous v2 ML pipeline (kept for comparison)

The target is measured daily rides for one route/date. Features include route,
reported day type, calendar fields, exact-date lags (1, 7, 14, 21, and 28 days),
and the mean/count of available same-weekday lags. A missing route/date is left
missing; lag 7 means exactly seven calendar days earlier, not the seventh
available row.

Training compares pooled Ridge regression, HistGradientBoosting, and Random
Forest. It chooses between them on the validation period, refits the selected model on training plus
validation, then reports test MAE, RMSE, and WAPE alongside last-week and
past-four-same-weekdays baselines. It also reports route-level test MAE, source
and day-type summaries, demand-band errors, SHA-256, split dates, and
missing-history behavior.

The default development periods follow the guide:

- History/training: 2024-08-01 to 2026-01-31
- Validation: 2026-02-01 to 2026-04-30
- Test: 2026-05-01 to 2026-07-31

These dates can be changed via CLI options. They should be frozen before
evaluating the test period. Current lag features use observed historical
boardings; the source publication delay has not been established, so outputs
are retrospective experiments and not operational next-day forecasts.

## Run previous v2 training locally

For the current mentor-guide v3 workflow, use the Colab notebook described
above; its final cell downloads a ZIP containing the selected model, reports,
and forecast/scoring CSVs. The local commands below continue to reproduce the
older v2 pipeline for comparison.

1. Create an environment and install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Export CTA's **Ridership - Bus Routes - Daily Totals by Route** data to
   `data/raw/cta_bus_ridership.csv`. Required columns and validation behavior
   are documented in [data/raw/README.md](data/raw/README.md).

3. Train and evaluate:

   ```bash
   python -m src.train
   ```

   Optional flags: `--input`, `--model`, `--report`, `--history-start`,
   `--train-end`, `--validation-start`, `--validation-end`,
   `--test-start`, and `--test-end`.

Defaults write `models/cta_ridership.joblib` and
`outputs/reports/model_metrics.json`. The real CTA input is not included;
training stops if invalid or conflicting records are found.

## Previous v2 Colab training run (historical reference)

The latest Colab report and fitted artifact are saved in this repository. The
selected HistGradientBoosting model's **fixed-origin recursive** forecast,
issued on 2026-04-30 for 2026-05-01 through 2026-07-31, scored **466.9 MAE**,
**748.6 RMSE**, and **9.39% WAPE**. It scored all 10,608 observed test rows.
The past-four-same-weekdays baseline scored 479.5 MAE and 9.64% WAPE on the
same rows, so the model improved MAE and WAPE by about **2.6%**. This is a
modest improvement and should be reported as such.

For comparison, the rolling one-step retrospective score was 341.6 MAE and
6.87% WAPE; it is easier because each test-day prediction could use actual
rides from earlier test days. The fixed-origin score is the more relevant
result for a forecast issued before the test period. Its day-type feature uses
CTA's reported daytype as known calendar metadata; verify an independent
calendar source before claiming operational forecasting.

See [model_metrics.json](outputs/reports/model_metrics.json) for route/day-type
breakdowns, split row counts, fallbacks, and the source CSV fingerprint. The
trained artifact is [cta_ridership.joblib](models/cta_ridership.joblib). The
source CSV itself is not stored here, so retain the exact input file whose
SHA-256 appears in the report when reproducing this run. Metrics are
retrospective; CTA publication timing for the lag observations remains
unverified.

## Structure

```text
data/raw/       Local source data (not committed)
src/            Loading, validation, exact-date features, model training
models/         Saved model artifacts
outputs/reports/ Evaluation metrics
```

The local route review dashboard and forecast API are available. The current
model evidence remains development-stage because the source hash differs from
the mentor's frozen CSV and the D−1 data-publication assumption is unverified.
Do not interpret route-level boardings as crowding or a causal measure of
service quality.

## Route review dashboard

Install the project dependencies, then launch the local review app:

```bash
pip install -r requirements.txt
streamlit run app.py
```

The dashboard is organized as a Chicago planning workspace:

- **Overview:** selected model, validation/test context, source fingerprint,
  and recent network totals when a ridership file is uploaded.
- **Routes:** route histories, matched-date route comparisons, day-type
  summaries, an optional GTFS-shape map, day-type-standardized review signals,
  and exploratory route groups with minimum sample controls.
- **Forecast evidence:** paired candidate/baseline metrics, route error
  diagnostics and day-type breakdowns.
- **Historical replay:** the saved June–July predictions are stepped through
  with actuals revealed after the assumed reporting delay.
- **One-day forecast:** uses the local
  `models/cta_route_ranker_v3_results.zip` bundle when present, plus an
  up-to-date CTA ridership CSV. The date is limited to the next permitted day;
  CTA day type is supplied by the user. A static GTFS ZIP can be uploaded to
  draw the selected route's scheduled geometry.
- **Scenarios:** preserves the systemwide trip total and applies the selected
  route-level trip-change bound.
- **Methods & data:** exposes model choice, source hashes, cutoff dates and
  assumptions.

Upload the CTA CSV in the sidebar to unlock route exploration and forecasting.
The optional map expects a static GTFS ZIP containing `routes.txt`, `trips.txt`
and `shapes.txt`. The map shows scheduled geometry, never live vehicles. The
scenario sandbox is conditional arithmetic, not an executable timetable or
service recommendation.

The saved evaluation report and scenario calculator are available through a local API:

```bash
uvicorn src.api:app --reload
```

Open `http://127.0.0.1:8000/docs` for interactive API documentation. Evaluation
endpoints include `/api/v1/evaluations`, `/api/v1/summary?mode=fixed_origin`,
`/api/v1/daytypes?mode=daily_rolling`, and `/api/v1/routes/47?mode=fixed_origin`.
The v3 endpoints are `GET /api/v1/forecasts/model` for the selected-model
summary and `POST /api/v1/forecasts/one-day` for live one-date predictions.
The forecast endpoint reads the model ZIP by default from
`models/cta_route_ranker_v3_results.zip`; set `CTA_RANKER_V3_BUNDLE` to another
ZIP or extracted joblib path if needed. Keep the large artifact out of Git.
For example, point the API at the ZIP in Downloads when starting it:

```bash
CTA_RANKER_V3_BUNDLE="/absolute/path/to/cta_route_ranker_v3_results.zip" uvicorn src.api:app --reload
```

Example one-day prediction request (illustrative values; include history
through the latest permitted date and one target date):

```json
{
  "history": [
    {"route":"1","date":"2026-08-04","daytype":"W","rides":5100},
    {"route":"1","date":"2026-08-11","daytype":"W","rides":5200},
    {"route":"1","date":"2026-08-18","daytype":"W","rides":5300},
    {"route":"1","date":"2026-08-25","daytype":"W","rides":5400},
    {"route":"1","date":"2026-08-31","daytype":"W","rides":5500}
  ],
  "targets": [
    {"route":"1","date":"2026-09-01","daytype":"W"}
  ]
}
```

The API rejects ride history later than the model's D−1 reporting cutoff and
requires strictly earlier schedule captures for service-aware bundles. Daily
requests are rolling one-step forecasts; send fresh eligible history for each
new issue date. API requests accept at most 10,000 history rows and 300 target
routes; send the required preceding route/date observations, not the entire
CTA export. The forecast is measured route boardings, not passenger load or
crowding. The existing
`POST /api/v1/scenarios/rebalance-trips` endpoint accepts route-level predicted
boardings, current scheduled trips, and an optional per-route change bound.

Example request body:

```json
{
  "routes": [
    {"route": "1", "predicted_rides": 12000, "scheduled_trips": 20},
    {"route": "2", "predicted_rides": 7000, "scheduled_trips": 16}
  ],
  "max_shift_pct": 0.1
}
```

### Trip allocation scenario input

For a scenario, prepare one row per route with these columns:

```csv
route,predicted_rides,scheduled_trips
1,12000,20
2,7000,16
```

The dashboard provides a blank template and a synthetic example. The scenario
keeps the total number of trips fixed and minimizes the highest predicted
boardings-per-trip ratio while respecting the selected route change limit.
This ratio is a screening proxy, not a passenger load or crowding estimate.
The scenario omits fleet cycles, travel times, peak-period demand, capacity,
transfers, route overlap, and equity constraints; review it with a transit
planner before using it to inform service changes.

See [MENTOR_REVIEW.md](docs/MENTOR_REVIEW.md) for the current assumptions and
decisions to confirm before presenting scenario outputs as planning advice.

## Historical GTFS service import

The eight dated archive IDs and SHA-256 values from the intern guide are listed
in [gtfs_archive_manifest.csv](data/raw/gtfs_archive_manifest.csv). Download
each matching ZIP and place it at the path in that manifest, keeping versions
in separate directories. The ZIPs are intentionally excluded from Git.
If your browser automatically extracted a ZIP, the Colab notebook accepts the
extracted folder in place of original.zip. In that case its archive SHA-256
cannot be checked, so the import report records a fingerprint of the extracted
GTFS tables and marks the ZIP hash as unverified.

With the CTA ridership CSV at its documented path, run:

    python -m src.gtfs_service

For the earlier fixed-origin development scenario, add the May 31 origin and
June-July forecast window:

    python -m src.gtfs_service --fixed-origin-date 2026-05-31 --fixed-start-date 2026-06-01 --fixed-end-date 2026-07-31

The importer validates each archive hash, filters GTFS bus routes
(route_type=3), applies weekly calendars and date exceptions, and selects one
feed globally per service date (latest retrieval date on or before that date).
It counts active scheduled trips and calculates trip-hours only when every
counted trip has valid first-departure/last-arrival times. Frequency-based
templates are rejected explicitly if present. Exact route/date demand and
service values are written to
data/processed/cta_route_date_demand_service.csv; unmatched rows remain
visible with a match_status. An import audit is written to
outputs/reports/gtfs_service_import.json.

Then compare demand-only with service-aware models on the same matched rows:

    python -m src.compare_service_models

To include a fixed-origin evaluation, pass the fixed schedule table produced
above:

    python -m src.compare_service_models --fixed-origin-service-data data/processed/cta_service_fixed_origin.csv --fixed-origin 2026-05-31

The earlier comparison uses the guide's matched-date partitions (train through
2026-03-31, validation through 2026-05-31, test 2026-06-01 through 2026-07-31)
and writes outputs/reports/service_model_comparison.json. Those June-July
outcomes have now been examined and are development results, not an untouched
final holdout. It reports matched
coverage, errors by day type and route, seasonal baselines, service feature
missingness, and the schedule snapshots used. This comparison is retrospective:
the schedule snapshot is selected as-of each service date, so it does not claim
to represent one forecast issued before the full test period. The optional
fixed-origin result freezes the latest snapshot available at the origin for
the full test horizon and feeds predicted ridership into later lag features
instead of actual test-period rides.

## Previous v2 demand versus service comparison (historical reference)

The matched rolling test covered **7,014 of 7,109** demand rows for June-July
(**98.66%**). The service-aware model scored **382.3 MAE / 7.76% WAPE** versus
**384.4 MAE / 7.80% WAPE** for demand-only, a modest 0.5% improvement. It was
slightly worse on validation, so this does not establish a robust improvement.
Both models beat the rolling past-four-same-weekdays baseline (402.7 MAE /
8.17% WAPE).

The fixed-origin simulation assumes a forecast origin of **2026-05-31** for
June 1-July 31, uses ridership through May 31, and freezes the **2026-05-30**
GTFS snapshot for the full horizon. It scored the same 7,014 rows. Demand-only
scored **600.7 MAE / 12.19% WAPE**; service-aware scored **581.1 MAE /
11.79% WAPE**, about 3.3% better. However, the recursive past-four-same-weekdays
baseline was stronger at **552.4 MAE / 11.21% WAPE**. Schedule features helped
relative to demand-only, but neither model beat this baseline in the harder
fixed-origin setting.

Ridership publication timing has not been verified, so availability of the
May 31 boardings at that assumed origin remains an operational assumption.

Full metrics and artifacts are in
[service_model_comparison.json](outputs/reports/service_model_comparison.json),
[gtfs_service_import.json](outputs/reports/gtfs_service_import.json),
[cta_demand_only.joblib](models/cta_demand_only.joblib), and
[cta_service_aware.joblib](models/cta_service_aware.joblib). Day type is treated
as known calendar metadata; verify an independent calendar source before
claiming operational forecasts.

The eight feeds were uploaded as extracted directories, so the import report
contains fingerprints of the GTFS table contents but marks original ZIP
SHA-256 verification as false. Most unmatched ridership rows are from dates
outside the archived schedule window; the test-period coverage figure above
is restricted to the model's matched test window.

## Previous v2 August evaluation (historical reference)

The Colab notebook reserved August from fitting: train through 2026-03-31,
validate on April-July, refit through 2026-07-31, and score August 1-31. The
fixed-origin forecast freezes `mdb-389-202607110020` (available July 11),
recursively feeds predictions into later demand lags, and scored **3,522 of
3,566** observed route-days (**98.77%** coverage).

On this fixed-origin holdout, demand-only scored **489.8 MAE / 813.2 RMSE /
9.95% WAPE** and service-aware scored **468.9 MAE / 771.6 RMSE / 9.52% WAPE**.
Adding schedule features improved MAE and WAPE by about **4.3%** relative to
demand-only. The past-four-same-weekdays baseline was still stronger at
**439.6 MAE / 724.0 RMSE / 8.93% WAPE**. So service features helped, but this
model is not yet the best forecaster. The easier retrospective rolling August
comparison showed 392.6 MAE for service-aware and 398.2 for demand-only; it
uses actual preceding August rides and is secondary to the fixed-origin score.

The model family and feature choices were selected using earlier dates, and
day type is read from the CTA ridership table as known calendar metadata.
Treat this as a historical simulation rather than a confirmed operational
forecast. The GTFS folders were extracted before upload, so original ZIP
SHA-256 verification is unavailable; table-content fingerprints are recorded
in the import report.

The route/day-type diagnostic shows where the overall gap comes from. On
weekdays (`W`), service-aware MAE is **497.6** versus **459.3** for the
past-four-same-weekdays baseline. On Sunday/holiday (`U`), it is **406.9**
versus **399.0**; on Saturday (`A`), **363.8** versus **366.3**, a small model
advantage. Across routes, service-aware beats the seasonal baseline on **38 of
125** routes, while it beats demand-only on **81 of 125**. The largest MAE
regressions against the seasonal baseline are routes **47, 54, 74, 82, and
94**; the largest gains are routes **9, 29, 53, 151, and 36**. These route
counts are descriptive and do not account for the routes' different ridership
volumes. Full route and day-type breakdowns are in the comparison JSON.

The Colab comparison cell also runs a **walk-forward hybrid development
analysis**. It refits each model monthly, produces rolling one-day-ahead
predictions, and selects among the two ML models and seasonal baselines for
each route/day type using only error history from completed earlier folds.
The policy falls back to the past-four-same-weekdays baseline when there is
not enough route/day-type history. This is a different, easier prediction
setting than the recursive fixed-origin August forecast: actual rides from
previous days are available as lag features. The hybrid results help develop
a daily updated strategy; they do not establish a long-range fixed-origin
forecast. August was already inspected during project development, so these
backtests are development evidence, not a fresh final holdout. CTA's exact
intra-day publication times for rides and schedule archives also remain
unverified.

The completed six-fold walk-forward development run scored **20,899 of
21,197** route-days (**98.59%** coverage). In the daily rolling setting,
service-aware had the lowest overall error (**376.4 MAE / 7.51% WAPE**),
followed by the hybrid (**387.3 MAE / 7.73% WAPE**) and past-four-same-weekdays
baseline (**390.7 MAE / 7.79% WAPE**). The hybrid beat the seasonal baseline on
53 of 125 routes, but it did not beat the service-aware model overall. By day
type, service-aware led on weekdays and Sunday/holidays; demand-only had a
slight edge on Saturdays. The adaptive route policy therefore has not shown
enough aggregate gain to justify preferring it over service-aware for daily
rolling predictions. This result does not overturn the fixed-origin August
finding, where the seasonal baseline remained better for the full recursive
horizon.

## Branch workflow

Project work belongs on `users/bidhubhusan`; do not commit or push directly to
`main`.
