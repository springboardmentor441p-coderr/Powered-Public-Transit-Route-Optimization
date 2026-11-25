# Phase 8 Stage 2D — Historical Forecasting API Implementation Report

**Project:** `AI_RouteRanker`  
**Milestone:** 8 — Backend API Integration  
**Stage:** 2D — Historical Forecasting API  
**Date:** 2026-11-25  

---

## 1. Executive Summary

Stage 2D implements read-only FastAPI endpoints for serving verified historical Random Forest evaluation predictions (`validation`, `test`, `august_holdout`) and aggregate evaluation metrics (`WAPE`, `MAE`, `RMSE`, `R^2`).

All responses explicitly enforce and report:
- `forecast_scope: "historical_evaluation_only"`
- `future_forecasting_supported: false`

No `.joblib` model binaries are loaded, no training or retraining occurs, and no future-date inference is performed.

---

## 2. Files Added & Modified

### Added
- `backend/app/repositories/forecast_repository.py` — `ForecastRepository` with thread-safe (`threading.Lock`) double-checked lazy caching, frozen DataFrames (`.flags.writeable = False`), deterministic `("date", "route")` sorting, and strict missing/corrupt artifact handling (`ArtifactUnavailableError` -> HTTP 503).
- `backend/app/schemas/forecast.py` — Pydantic v2 schemas (`HistoricalPredictionItem`, `HistoricalForecastResponse`, `TierPeriodEvaluationSummary`, `HistoricalForecastSummaryResponse`) with `extra="forbid"`.
- `backend/app/services/forecast_service.py` — `ForecastService` implementing parameter validation, `("tier2", "august_holdout")` rejection (HTTP 400), filtering by `route_id` and inclusive `start_date`/`end_date`, pagination, non-finite (`NaN`/`Inf`) sanitization to `None`, and zero-actual `percentage_error = None`.
- `backend/app/api/v1/forecasting.py` — Router exposing:
  - `GET /api/v1/forecasting/historical`
  - `GET /api/v1/forecasting/historical/summary`
- `backend/tests/test_forecast_api.py` — Canonical and synthetic edge-case integration/unit test suite.

### Modified
- `backend/app/core/config.py` — Added `RANDOM_FOREST_DIR`, `RF_TIER1_VAL_PRED_PATH`, `RF_TIER1_TEST_PRED_PATH`, `RF_TIER1_AUG_PRED_PATH`, `RF_TIER2_VAL_PRED_PATH`, `RF_TIER2_TEST_PRED_PATH`, `RF_FINAL_METRICS_CSV_PATH`, and `RF_CHAMPION_CONFIG_PATH`.
- `backend/app/repositories/__init__.py` — Exported `ForecastRepository`.
- `backend/app/services/__init__.py` — Exported `ForecastService`.
- `backend/app/schemas/__init__.py` — Imported Stage 2D schemas.
- `backend/app/api/v1/deps.py` — Registered `get_forecast_repository()` (`@lru_cache()`) and `get_forecast_service()`.
- `backend/app/api/v1/router.py` — Included `forecasting_router` under `/api/v1`.

---

## 3. Canonical Data Sources & Verification

All 5 prediction Parquet files, 4 `.joblib` model binaries, evaluation reports, and DuckDB remain unmodified (verified by SHA-256):

| Artifact | Rows | Date Range | SHA-256 |
| --- | ---: | --- | --- |
| `tier1_val_predictions_tuned.parquet` | 37,786 | `2025-01-01` .. `2025-11-22` | `4214b9140711c2f1901acb2252b0d90ee25fe095bd240acc65ab4af2a5879f3e` |
| `tier1_test_predictions_tuned.parquet` | 28,798 | `2025-11-23` .. `2026-07-31` | `3d1a70b6d447544eb4d3f862a1fd9bcb490f28b2a8725e93ab1e76187402c9a2` |
| `tier1_august_predictions_tuned.parquet` | 3,566 | `2026-08-01` .. `2026-08-31` | `33c59e2e4438475dea175fbd39ede81e930eb953451fa35683a7c1fad5281e06` |
| `tier2_val_predictions_tuned.parquet` | 4,117 | `2026-04-24` .. `2026-05-29` | `f0f0bb8f4c86892b998e5cf30f9bb3feeaaaf7dd4873800133e3fd3cd5c2981e` |
| `tier2_test_predictions_tuned.parquet` | 7,293 | `2026-05-30` .. `2026-07-31` | `4b6825dedc8d601c831e4483e64ee896dc952fca71ff798dd007bc31427e72fb` |
| `final_model_evaluation_metrics.csv` | 3 | Test + Aug Holdout | `55dd8192df620d0e61d4d4125950db9335ddd6bce9939ddf0eeec424af5b2bd` |
| `random_forest_champion_config.json` | — | Tier 1 & 2 Val | `be420b65fcb92f08db72e0211137a97a519e49038eb7be37679070534549f740` |
| `ai_routeranker.duckdb` | — | — | `ec0fd3626c6734fa2f96d6202a6d4966ae193598cc6e1ca84a828c295eee4209` |
