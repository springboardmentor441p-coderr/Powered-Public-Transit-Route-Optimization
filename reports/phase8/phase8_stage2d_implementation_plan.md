# AI_RouteRanker — Milestone 8 Stage 2D: Implementation Plan

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Milestone:** 8 — Backend API Integration (Stage 2D)  
**Date:** 2026-11-25T19:19:00+05:30  

---

## 1. Architecture & Module Plan

1. **Configuration (`backend/app/core/config.py`)**: Add `RANDOM_FOREST_DIR`, paths to all 5 tuned prediction Parquet files, `final_model_evaluation_metrics.csv`, and `random_forest_champion_config.json`.
2. **Repository (`backend/app/repositories/forecast_repository.py`)**:
   - `ForecastRepository` with `threading.Lock` double-checked lazy caching, column pruning, schema validation, frozen NumPy arrays (`flags.writeable = False`), deterministic `["date", "route"]` sorting on load, and safe `503` error handling.
   - Zero model loading, training, or inference.
3. **Schemas (`backend/app/schemas/forecast.py`)**: Pydantic v2 models enforcing `forecast_scope: Literal["historical_evaluation_only"]` and `future_forecasting_supported: Literal[False]`.
4. **Service (`backend/app/services/forecast_service.py`)**:
   - Enforces `(tier, period)` allowlist (`("tier2", "august_holdout")` -> HTTP 400 `UNSUPPORTED_TIER_PERIOD`).
   - Validates `route_id` and `start_date <= end_date`.
   - Computes `absolute_error = abs(predicted - actual)` and `percentage_error = (abs_err / actual) * 100.0` strictly when `actual > 0` (setting `percentage_error = None` when `actual == 0` or non-finite).
5. **Router (`backend/app/api/v1/forecasting.py`)**: Mount `/forecasting/historical` and `/forecasting/historical/summary` via `deps.py` and `router.py`.
6. **Testing (`backend/tests/test_forecast_api.py`)**: Canonical tests for all 5 valid `(tier, period)` combinations, unsupported `tier2 + august_holdout`, synthetic zero-actual `percentage_error=null`, `NaN`/`Inf` handling, concurrency, immutability, and full regression.
