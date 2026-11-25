# Milestone 8, Stage 2D — Audit Remediation Report

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Scope:** Milestone 8 — Stage 2D Historical Forecasting API  
**Audit Reference:** `reports/phase8/phase8_stage2d_independent_audit_report.md` (preserved unchanged)  
**Date:** 2026-11-25  

---

## 1. Original Findings & Root Causes

| ID | Severity | Original Finding | Root Cause |
| --- | --- | --- | --- |
| `M-01` | Medium | `fallback_baseline_b` coerced every test/holdout row to `True` | Canonical test/holdout Parquet files store strategy strings (`calendar_t7`, `recent_28d_daytype`, `historical_mean`) from `analytics/modeling/baselines/seasonal_naive.py`; `ForecastService` used `bool(row["fallback_baseline_b"])`, evaluating all non-empty strings to `True`. |
| `L-01` | Low | Whitespace-only `route_id` silently treated as unfiltered | `ForecastService.get_historical_predictions()` checked `if route_id is not None and route_id.strip():`, skipping validation and returning all routes on `""` or `"   "`. |
| `L-02` | Low | Validation summary `rows_evaluated` reported `37,786` / `4,117` while champion metrics used `37,785` / `4,116` | `tuner.py` excluded one debut key per tier (`N5_2025-01-01` in Tier 1, `10_2026-05-20` in Tier 2) lacking a Baseline B counterpart to compute `common_rows` (`37,785` / `4,116`). The API previously added `+1` to `rows_evaluated`. |
| `L-03` | Low | Missing regression tests | `backend/tests/test_forecast_api.py` used boolean synthetic fixtures for `fallback_baseline_b` and lacked whitespace `route_id` and validation-summary population tests. |

---

## 2. Exact Corrections & Before-and-After Behavior

### `M-01` — `fallback_baseline_b` Strategy Mapping
- **Files:** `backend/app/schemas/forecast.py`, `backend/app/services/forecast_service.py`
- **Correction:** Added explicit `BASELINE_B_STRATEGY_FALLBACK_MAP` and `_interpret_baseline_b_strategy()` based on `reports/modeling/baselines/baseline_methodology.md`:
  - `calendar_t7` (Priority 1 primary lag) → `baseline_b_strategy="calendar_t7"`, `fallback_baseline_b=False`
  - `recent_28d_daytype` (Priority 2 fallback) → `baseline_b_strategy="recent_28d_daytype"`, `fallback_baseline_b=True`
  - `historical_mean` (Priority 3 fallback) → `baseline_b_strategy="historical_mean"`, `fallback_baseline_b=True`
  - `unavailable` / `None` / empty → `None`
- **Before vs After:** Primary `calendar_t7` rows previously returned `fallback_baseline_b: true`; they now return `fallback_baseline_b: false` and `baseline_b_strategy: "calendar_t7"`.

### `L-01` — Whitespace-Only `route_id` Rejection
- **File:** `backend/app/services/forecast_service.py`
- **Correction:** Changed validation to check `if route_id is not None:`, strip, and raise `InvalidParameterError(code="INVALID_ROUTE_ID")` (HTTP 400) when empty or non-matching.
- **Before vs After:** `route_id="   "` previously returned HTTP 200 unfiltered; it now returns HTTP 400 while omitted `route_id` remains unfiltered.

### `L-02` — Validation Summary Population Counts
- **Files:** `backend/app/schemas/forecast.py`, `backend/app/services/forecast_service.py`
- **Correction:**
  - `rows_evaluated` now strictly reports the metric evaluation population (`37,785` for Tier 1 validation, `4,116` for Tier 2 validation, and `28,798` / `3,566` / `7,293` for test & holdout).
  - Added `total_prediction_records` (`37,786` for Tier 1 validation, `4,117` for Tier 2 validation, matching Parquet row counts) and `evaluation_population_note` explaining the excluded debut row.
- **Before vs After:** Validation summaries previously conflated total Parquet rows with `rows_evaluated`; both populations are now explicitly separated and reconciled.

### `L-03` — New Regression Tests
- **File:** `backend/tests/test_forecast_api.py`
- Added `test_validation_summary_distinguishes_common_rows_and_total_records`, `test_whitespace_route_id_rejected_and_missing_route_id_unfiltered`, `test_canonical_baseline_b_strategy_mapping`, and updated synthetic fixtures to test `calendar_t7`, `recent_28d_daytype`, `historical_mean`, and `None` strategy values.

---

## 3. Test Results

| Suite | Command | Result |
| --- | --- | --- |
| Stage 2D Focused | `python -m unittest backend.tests.test_forecast_api -v` | **12/12 passed** (`0.871s`) |
| Full Backend | `python -m unittest discover -s backend/tests -v` | **54/54 passed** (`3.151s`) |
| Full Project | `python -m unittest discover tests` | **205/205 passed** (`8.931s`) |

---

## 4. API & Hash Integrity Verification

- **Cross-Stage API Regression:** Verified HTTP 200 across `/`, `/api/health`, Stage 1 (`/routes`, `/rankings/*`, `/explanation`, `/sensitivity`), Stage 2A (`/ridership/routes/151/timeseries`), Stage 2B (`/spatial/hubs`, `/spatial/hubs/top?config=a&limit=100` ending at Stop `4732`, `/spatial/clusters/summary`), Stage 2C (`/corridors/clusters`, `/corridors/routes/151/co-routing`), and Stage 2D (`/forecasting/historical`, `/forecasting/historical/summary`), plus HTTP 400 on `("tier2", "august_holdout")` and `historical_evaluation_only` / `future_forecasting_supported: false` metadata.
- **SHA-256 Integrity:** All 5 prediction Parquet files, 4 Phase 5 `.joblib` models, Phase 6.1/6.2/6.3 artifacts, Phase 7 ranking artifacts, and `ai_routeranker.duckdb` (`ec0fd362...`) matched pre-remediation SHA-256 hashes identically. Zero frontend, DuckDB, PostgreSQL, or model modifications occurred, and Stage 2E was not started.

---

## 5. Remaining Limitations & Verdict

- **Remaining Limitations:** Autoregressive Random Forest models require observed historical lag features; no verified future-date forecasting pipeline exists beyond `2026-08-31`, and Tier 2 has no August holdout partition.
- **Remediation Verdict:** **ALL STAGE 2D AUDIT FINDINGS (`M-01`, `L-01`, `L-02`, `L-03`) REMEDIATED AND VERIFIED.**
