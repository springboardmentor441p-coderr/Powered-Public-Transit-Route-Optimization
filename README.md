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

The first Colab run and fitted artifact are saved in this repository. Its
**rolling one-step retrospective** HistGradientBoosting score was **341.6 MAE**,
**591.4 RMSE**, and **6.87% WAPE** on the 2026-05-01 through 2026-07-31 test
window. The past-four-same-weekdays baseline scored 382.8 MAE and 7.70% WAPE
on those dates. Each test-day prediction could use actual rides from earlier
test days, so these scores do not measure a single forecast issued before May.
The updated Colab notebook now also calculates a recursive fixed-origin
forecast from 2026-04-30 without feeding in actual test-period rides. Rerun
that notebook to generate and save those new metrics.

See [model_metrics.json](outputs/reports/model_metrics.json) for route/day-type
breakdowns, split row counts, fallbacks, and the source CSV fingerprint. The
trained artifact is [cta_ridership.joblib](models/cta_ridership.joblib). The
source CSV itself is not stored here, so retain the exact input file whose
SHA-256 appears in the report when reproducing this run. Metrics are
retrospective; CTA publication timing for the lag observations remains
unverified. The report currently in the repository predates the fixed-origin
evaluation.

## Structure

```text
data/raw/       Local source data (not committed)
src/            Loading, validation, exact-date features, model training
models/         Saved model artifacts
outputs/reports/ Evaluation metrics
```

Schedule-aware features, GTFS archive matching, route clustering, ranking,
API, and dashboard remain later project work. Do not interpret route-level
boardings as crowding or a causal measure of service quality.

## Branch workflow

Project work belongs on `users/bidhubhusan`; do not commit or push directly to
`main`.
