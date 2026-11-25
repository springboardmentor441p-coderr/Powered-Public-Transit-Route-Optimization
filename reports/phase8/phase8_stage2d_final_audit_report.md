# Milestone 8, Stage 2D — Final Post-Remediation Audit Report

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Scope:** Milestone 8 — Stage 2D Historical Forecasting API  
**Audit Type:** Strictly Read-Only Final Verification  
**Prior Reports Preserved:** `phase8_stage2d_independent_audit_report.md`, `phase8_stage2d_remediation_report.md`  
**Date:** 2026-11-25  

---

## 1. Executive Verdict

**VERDICT: PASS**

All four findings (`M-01`, `L-01`, `L-02`, `L-03`) from the independent Stage 2D audit have been effectively remediated, independently verified against canonical Phase 5 artifacts and DuckDB, and regression-tested with zero remaining open findings and zero regressions across Stage 1, 2A, 2B, 2C, and 2D.

---

## 2. Finding-by-Finding Remediation Verification

| ID | Original Issue | Verification Result | Evidence |
| --- | --- | --- | --- |
| `M-01` | `fallback_baseline_b` coerced strategy strings via `bool(...)` | **VERIFIED FIXED** | `ForecastService._interpret_baseline_b_strategy` uses explicit `BASELINE_B_STRATEGY_FALLBACK_MAP` (no Python truthiness on strings). API returns `baseline_b_strategy` + accurate `fallback_baseline_b` (`false` for `calendar_t7`, `true` for `recent_28d_daytype`/`historical_mean`, `null` for `unavailable`/null/validation). |
| `L-01` | Whitespace-only `route_id` silently treated as unfiltered | **VERIFIED FIXED** | `route_id=""` and `route_id="   "` return HTTP 400; omitted `route_id` returns unfiltered (`3,566` rows); `" 79 "` trims cleanly to `"79"` (`31` rows); unknown `"NONEXISTENT_999"` returns HTTP 200 with `0` rows. |
| `L-02` | Validation `rows_evaluated` included `+1` debut row | **VERIFIED FIXED** | `rows_evaluated` reports `common_rows` (`37,785` Tier 1; `4,116` Tier 2); `total_prediction_records` reports full Parquet row counts (`37,786` / `4,117`); `evaluation_population_note` documents the excluded debut key; WAPE/MAE/RMSE/R² and test/holdout counts (`28,798` / `3,566` / `7,293`) remain exact. |
| `L-03` | Missing regression tests | **VERIFIED FIXED** | `backend/tests/test_forecast_api.py` now includes 12 tests covering all 3 strategies, null strategy, whitespace/omitted `route_id`, and Tier 1/Tier 2 validation population counts—all of which would fail on the pre-remediation code. |

---

## 3. Canonical Strategy Mapping Evidence (`M-01`)

Verified directly against `tier1_test_predictions_tuned.parquet` and `tier1_val_predictions_tuned.parquet` via `GET /api/v1/forecasting/historical`:

| Partition | Offset | Route | Date | Raw Parquet `fallback_baseline_b` | API `baseline_b_strategy` | API `fallback_baseline_b` |
| --- | ---: | --- | --- | --- | --- | :---: |
| `tier1` / `test` | 1 | `103` | `2025-11-23` | `calendar_t7` | `calendar_t7` | `false` |
| `tier1` / `test` | 0 | `1001` | `2025-11-23` | `recent_28d_daytype` | `recent_28d_daytype` | `true` |
| `tier1` / `test` | 3,103 | `128` | `2025-12-20` | `historical_mean` | `historical_mean` | `true` |
| `tier1` / `validation` | 0 | `1001` | `2025-01-01` | *(column absent)* | `null` | `null` |

---

## 4. Validation Population Reconciliation (`L-02`)

Independently verified against `ai_routeranker.duckdb` (`analytical.daily_ridership`, read-only):
- **Tier 1 Validation (`N5_2025-01-01`):** Querying `route = 'N5' AND date < DATE '2025-01-01'` returned **`0` prior rows** in the Tier 1 training window (`2022-01-01`..`2024-12-31`). Consequently, Baseline B (`Priority 4: unavailable`) had no prediction for `N5` on `2025-01-01`, yielding `37,785` common evaluation rows vs `37,786` total RF prediction records.
- **Tier 2 Validation (`10_2026-05-20`):** Querying `route = '10' AND date < DATE '2026-05-20' AND date >= DATE '2025-11-23'` returned **`0` prior rows** in the Tier 2 GTFS-era window. Baseline B (`unavailable`) had no prediction for Route `10` on `2026-05-20`, yielding `4,116` common evaluation rows vs `4,117` total RF prediction records.
- API `/historical/summary` accurately reports:
  - Tier 1 Validation: `rows_evaluated=37785`, `total_prediction_records=37786`, `wape=7.243`, `mae=346.2802`, `rmse=598.7595`, `r2=0.9822`.
  - Tier 2 Validation: `rows_evaluated=4116`, `total_prediction_records=4117`, `wape=5.6173`, `mae=291.6115`, `rmse=472.9425`, `r2=0.9904`.

---

## 5. API Regression Results

All cross-stage endpoints verified via FastAPI `TestClient(app)`:
- `/`: `200`, `/api/health`: `200`
- Stage 1 (`/routes`, `/rankings/bus`, `/rankings/rail`, `/rankings/unified`, `/rankings/routes/151/explanation`, `/rankings/sensitivity`): all `200`
- Stage 2A (`/ridership/routes/151/timeseries?granularity=monthly`): `200`
- Stage 2B (`/spatial/hubs`, `/spatial/hubs/top?config=a&limit=100`, `/spatial/clusters/summary`): all `200` (last top-100 stop verified as `"4732"`)
- Stage 2C (`/corridors/clusters`, `/corridors/routes/151/co-routing`): all `200`
- Stage 2D (`/forecasting/historical`, `/forecasting/historical/summary`): `200` with `forecast_scope: "historical_evaluation_only"` and `future_forecasting_supported: false`; `tier=tier2&period=august_holdout`: `400`.

---

## 6. Test Reproduction

| Suite | Command | Result | Elapsed |
| --- | --- | --- | ---: |
| Focused Stage 2D | `python -m unittest backend.tests.test_forecast_api -v` | **12/12 passed** | 0.669s |
| Backend Suite | `python -m unittest discover -s backend/tests -v` | **54/54 passed** | 2.743s |
| Full Project Suite | `python -m unittest discover tests` | **205/205 passed** | 8.547s |

---

## 7. Remaining Coverage Gaps

- Single-parameter `/historical/summary` filters (`?tier=tier1` without `period`, or `?period=validation` without `tier`) are not explicitly asserted as separate test cases in `test_forecast_api.py` (though the filtering branch is trivial and covered indirectly).

---

## 8. SHA-256 Integrity Results

All 5 historical prediction Parquets, 4 Phase 5 `.joblib` models, Phase 6.1/6.2/6.3 artifacts, Phase 7 ranking artifacts, and `ai_routeranker.duckdb` (`ec0fd3626c6734fa2f96d6202a6d4966ae193598cc6e1ca84a828c295eee4209`) matched their pre-remediation SHA-256 hashes identically. No frontend files, PostgreSQL configuration, model weights, or predictions were modified, and Stage 2E was not started.

---

## 9. Remaining Limitations

- Historical evaluation only (`forecast_scope: "historical_evaluation_only"`, `future_forecasting_supported: false`); autoregressive Random Forest models require observed historical lag features and cannot forecast beyond `2026-08-31`.
- Tier 2 has no August holdout partition (`("tier2", "august_holdout")` returns HTTP 400).

---

## 10. Final Verdict

**PASS** — All Stage 2D audit remediation items are verified complete, all tests pass, and all canonical artifacts remain intact.
