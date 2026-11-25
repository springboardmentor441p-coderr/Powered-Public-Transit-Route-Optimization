# Phase 8 Stage 2D — Historical Forecasting API Test & Benchmark Report

**Project:** `AI_RouteRanker`  
**Milestone:** 8 — Backend API Integration  
**Stage:** 2D — Historical Forecasting API  
**Date:** 2026-11-25  

---

## 1. Automated Test Results

### Backend Test Suite (`python -m unittest discover -s backend/tests -v`)
- **Total Tests Executed:** 51 (9 new Stage 2D tests + 42 existing Stage 1/2A/2B/2C regression tests)
- **Result:** `Ran 51 tests in 3.049s — OK` (51 passed, 0 failed, 0 skipped)

### Full Project Suite (`python -m unittest discover tests`)
- **Total Tests Executed:** 205
- **Result:** `Ran 205 tests in 8.831s — OK` (205 passed, 0 failed, 0 skipped)

### Stage 2D Coverage (`backend/tests/test_forecast_api.py`)
1. `test_all_five_valid_tier_period_combinations` — Validates all 5 `(tier, period)` pairs, record counts, date bounds, `forecast_scope == "historical_evaluation_only"`, `future_forecasting_supported is False`, and baseline presence/absence.
2. `test_unsupported_tier2_august_holdout_returns_400` — Verifies HTTP 400 on both `/historical` and `/historical/summary` for `tier=tier2&period=august_holdout`.
3. `test_invalid_parameters_and_date_ranges` — Verifies HTTP 400/422 for invalid `tier`, `period`, `start_date > end_date`, malformed dates, `limit=151`, and `offset=-1`.
4. `test_route_and_date_filtering_pagination_and_stable_sort` — Verifies `route_id`, inclusive `start_date`/`end_date`, `pagination.has_more`, and deterministic `("date", "route_id")` ordering.
5. `test_empty_result_for_nonexistent_route_or_out_of_range_dates` — Verifies HTTP 200 with `total_records == 0` and `data == []`.
6. `test_summary_endpoint_and_canonical_metrics` — Verifies all 5 summaries and canonical `WAPE` values (`8.5279`, `8.1985`, `8.1013`, `7.2430`, `5.6173`).
7. `test_concurrent_requests_thread_safety` — Verifies 10 concurrent `TestClient` requests succeed deterministically.
8. `test_zero_actual_and_non_finite_values_serialize_cleanly` — Verifies `actual_rides == 0` -> `percentage_error = null`, `NaN`/`Inf` -> `null`, and cached DataFrame immutability (`writeable = False`).
9. `test_missing_or_corrupt_artifacts_return_503` — Verifies missing and corrupt Parquet/CSV/JSON artifacts return HTTP 503 cleanly.

---

## 2. Performance & Memory Benchmark

Executed against canonical artifacts using FastAPI `TestClient`:

| Scenario | Latency (ms) |
| --- | ---: |
| Cold `GET /api/v1/forecasting/historical?tier=tier1&period=august_holdout&limit=50` | 464.41 |
| Warm average (5 runs) `tier1` + `august_holdout` | 40.14 |
| Cold `tier1` + `validation` (`37,786` rows, `limit=150`) | 195.02 |
| Warm `tier1` + `validation` (`limit=150`, `offset=150`) | 68.52 |
| Filtered `tier1` + `test` (`route_id=79`, `2026-01-01..2026-01-31`) | 131.39 |
| Cold `GET /api/v1/forecasting/historical/summary` | 32.86 |
| Warm `GET /api/v1/forecasting/historical/summary` | 18.40 |
| 10-thread concurrent `august_holdout` batch (total wall time) | 375.40 |

- **Traced Python Memory (`tracemalloc`):** `6.81 MB` current, `7.53 MB` peak.
