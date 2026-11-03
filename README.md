# CTA Public Transit Route Optimization

An initial RouteRanker forecasting pipeline for CTA daily bus boardings by
route. The intern guide sets the core requirements: preserve real observations,
align by route and exact date, compare forecasts with seasonal baselines, and
describe results as retrospective until CTA publication timing is verified.

## Current ML pipeline

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

## Run training

For browser-based training, open
[notebooks/cta_ridership_colab.ipynb](notebooks/cta_ridership_colab.ipynb)
in Google Colab and follow the cells. It can read the CSV from Google Drive or
from a direct upload, then downloads the fitted model and metrics report.

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

## Latest Colab training run

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

Route clustering, review ranking, API, and dashboard remain later project
work. Do not interpret route-level boardings as crowding or a causal measure
of service quality.

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

## Latest demand versus service comparison

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

## Final August holdout

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

## Branch workflow

Project work belongs on `users/bidhubhusan`; do not commit or push directly to
`main`.
