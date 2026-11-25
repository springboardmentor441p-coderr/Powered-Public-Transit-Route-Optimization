# AI_RouteRanker — Milestone 8 Stage 2D: Historical Forecasting API Contract

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Milestone:** 8 — Backend API Integration (Stage 2D)  
**Prefix:** `/api/v1` | **Scope:** `historical_evaluation_only` (`future_forecasting_supported: false`)  
**Date:** 2026-11-25T19:19:00+05:30  

---

## 1. Supported Tier-Period Matrix

| `tier` | `period` | Supported | Source Artifact |
| :--- | :--- | :---: | :--- |
| `tier1` | `validation` | **YES** | `tier1_val_predictions_tuned.parquet` (`2025-01-01`..`2025-11-22`) |
| `tier1` | `test` | **YES** | `tier1_test_predictions_tuned.parquet` (`2025-11-23`..`2026-07-31`) |
| `tier1` | `august_holdout` | **YES** | `tier1_august_predictions_tuned.parquet` (`2026-08-01`..`2026-08-31`) |
| `tier2` | `validation` | **YES** | `tier2_val_predictions_tuned.parquet` (`2026-04-24`..`2026-05-29`) |
| `tier2` | `test` | **YES** | `tier2_test_predictions_tuned.parquet` (`2026-05-30`..`2026-07-31`) |
| `tier2` | `august_holdout` | **NO (HTTP 400)** | Not part of approved Tier 2 evaluation design |

---

## 2. Endpoints

### 2.1 `GET /api/v1/forecasting/historical`
- **Query Parameters:**
  - `tier`: `Literal["tier1", "tier2"]` (default `"tier1"`)
  - `period`: `Literal["validation", "test", "august_holdout"]` (default `"august_holdout"`)
  - `route_id`: `Optional[str]` (validated against `ROUTE_ID_PATTERN`)
  - `start_date`: `Optional[date]`
  - `end_date`: `Optional[date]` (`start_date > end_date` -> HTTP 400 `INVALID_DATE_RANGE`)
  - `limit`: `int` (`1..150`, default `25`)
  - `offset`: `int` (`>=0`, default `0`)
- **Row Fields (`HistoricalPredictionItem`):**
  - `route_id`, `date`, `daytype`, `actual_rides`, `predicted_rides`, `absolute_error`, `percentage_error` (`None`/JSON `null` when `actual_rides == 0` or non-finite), `baseline_seasonal_naive_prediction` (Optional[float], available on `test`/`august_holdout`), `fallback_baseline_b` (Optional[bool]).
- **Envelope Fields:**
  - `forecast_scope: "historical_evaluation_only"`, `future_forecasting_supported: false`, `tier`, `period`, `model_identifier`, `evaluation_start`, `evaluation_end`, `total_records`, `returned_records`, `pagination`, `data`.

### 2.2 `GET /api/v1/forecasting/historical/summary`
- **Query Parameters:** `tier` (Optional `tier1` | `tier2`), `period` (Optional `validation` | `test` | `august_holdout`).
- **Response (`HistoricalForecastSummaryResponse`):**
  - `forecast_scope: "historical_evaluation_only"`, `future_forecasting_supported: false`, `future_forecasting_note`
  - `summaries`: List of `TierPeriodEvaluationSummary` (from `final_model_evaluation_metrics.csv` for test/holdout and `random_forest_champion_config.json` for validation): `tier`, `period`, `model_identifier`, `evaluation_start`, `evaluation_end`, `rows_evaluated`, `wape`, `mae`, `rmse`, `r2`, `baseline_b_wape`, `baseline_b_mae`, `baseline_b_rmse`, `baseline_b_r2`.
