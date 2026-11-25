# Phase 8 Stage 2D — Independent Audit Checklist (With Remediation Status)

**Project:** `AI_RouteRanker`  
**Scope:** Milestone 8 Stage 2D — Historical Forecasting API  

| Check | Status | Evidence |
| --- | --- | --- |
| Explicit `forecast_scope: "historical_evaluation_only"` | PASS | `HistoricalForecastResponse` & `HistoricalForecastSummaryResponse` (`backend/app/schemas/forecast.py`) |
| Explicit `future_forecasting_supported: false` | PASS | Literal `False` on both response models; verified in tests |
| No `.joblib` loading / no retraining / no future inference | PASS | `ForecastRepository` reads only Parquet, CSV, and JSON artifacts |
| Reject `("tier2", "august_holdout")` with HTTP 400 | PASS | Verified on both `/historical` and `/historical/summary` |
| `percentage_error = null` when `actual_rides == 0` or non-finite | PASS | Verified in `test_zero_actual_and_non_finite_values_serialize_cleanly` |
| `NaN` / `Inf` serialized as `null` | PASS | Verified in `test_zero_actual_and_non_finite_values_serialize_cleanly` |
| Deterministic `("date", "route_id")` ordering | PASS | Verified in `test_route_and_date_filtering_pagination_and_stable_sort` |
| Thread-safe caching & frozen DataFrames | PASS | `threading.Lock` + `_freeze_dataframe()` (`target.flags.writeable = False`) |
| Missing/corrupt artifacts return HTTP 503 safely | PASS | Verified in `test_missing_or_corrupt_artifacts_return_503` |
| Canonical artifacts & DuckDB untouched (SHA-256 verified) | PASS | All 5 Parquet files, 4 `.joblib` models, CSV, JSON, DuckDB unchanged |
| **Audit Finding `M-01` (`fallback_baseline_b` strategy mapping)** | **REMEDIATED** | Explicit `BASELINE_B_STRATEGY_FALLBACK_MAP` + `baseline_b_strategy` field (`forecast_service.py`, `forecast.py`); `calendar_t7` -> `False`, `recent_28d_daytype`/`historical_mean` -> `True`, `unavailable`/null -> `None` |
| **Audit Finding `L-01` (whitespace-only `route_id`)** | **REMEDIATED** | Empty/whitespace `route_id` now raises `InvalidParameterError` (HTTP 400); omitted `route_id` remains unfiltered |
| **Audit Finding `L-02` (validation `rows_evaluated` vs `common_rows`)** | **REMEDIATED** | `rows_evaluated` reports `common_rows` (`37,785` / `4,116`); `total_prediction_records` reports full Parquet row count (`37,786` / `4,117`) with `evaluation_population_note` |
| **Audit Finding `L-03` (missing regression tests)** | **REMEDIATED** | Added 3 focused tests + canonical string strategy assertions in `backend/tests/test_forecast_api.py` (12/12 passing) |
| No Stage 2E work started | PASS | Scope strictly limited to Stage 2D |
