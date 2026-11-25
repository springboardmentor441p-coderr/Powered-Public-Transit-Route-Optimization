# Milestone 8, Stage 2D — Independent Audit Report: Historical Forecasting API

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Scope:** Milestone 8, Stage 2D — Historical Forecasting API  
**Audit Type:** Strictly Read-Only Independent Audit  
**Date:** 2026-11-25  

---

## 1. Executive Verdict

**VERDICT: PASS WITH WARNINGS**

The Stage 2D Historical Forecasting API (`GET /api/v1/forecasting/historical` and `GET /api/v1/forecasting/historical/summary`) accurately serves verified historical Random Forest evaluation predictions, actuals, recalculated errors, and aggregate metrics across all 5 supported `(tier, period)` combinations, explicitly enforces `forecast_scope: "historical_evaluation_only"` and `future_forecasting_supported: false`, rejects `("tier2", "august_holdout")` with HTTP 400, preserves zero/non-finite handling, and leaves all canonical artifacts, models, DuckDB, and frontend files completely untouched.

One **Medium** finding (`M-01`) and three **Low** findings (`L-01`, `L-02`, `L-03`) were identified; none involve fabricated predictions, future-forecast misrepresentation, or data leakage.

---

## 2. Files Inspected

- Implementation:
  - `backend/app/repositories/forecast_repository.py`
  - `backend/app/services/forecast_service.py`
  - `backend/app/schemas/forecast.py`
  - `backend/app/api/v1/forecasting.py`
  - `backend/app/api/v1/deps.py`
  - `backend/app/api/v1/router.py`
  - `backend/app/core/config.py`
  - `backend/app/repositories/__init__.py`, `backend/app/services/__init__.py`, `backend/app/schemas/__init__.py`
- Tests & Reports:
  - `backend/tests/test_forecast_api.py`
  - `reports/phase8/phase8_stage2d_discovery_report.md`
  - `reports/phase8/phase8_stage2d_api_contract.md`
  - `reports/phase8/phase8_stage2d_implementation_plan.md`
  - `reports/phase8/phase8_stage2d_implementation_report.md`
  - `reports/phase8/phase8_stage2d_test_report.md`
  - `reports/phase8/phase8_stage2d_audit_checklist.md`
  - `reports/modeling/random_forest/final_model_evaluation_metrics.csv`
  - `reports/modeling/random_forest/random_forest_champion_config.json`
  - `artifacts/random_forest/model_sha256_baseline.json`

---

## 3. Canonical Prediction Artifact Inventory

Independently verified from `D:\B.TECH_PROJECTS\AI_RouteRanker\artifacts\random_forest\`:

| Tier & Period | Filename | Size (B) | Rows | Date Range | Routes | Dup `(date, route)` | Nulls / Infs | `target_rides == 0` | SHA-256 |
| --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | --- |
| Tier 1 Validation | `tier1_val_predictions_tuned.parquet` | 560,317 | 37,786 | `2025-01-01` .. `2025-11-22` | 129 | 0 | 0 / 0 | 0 | `4214b9140711c2f1901acb2252b0d90ee25fe095bd240acc65ab4af2a5879f3e` |
| Tier 1 Test | `tier1_test_predictions_tuned.parquet` | 492,573 | 28,798 | `2025-11-23` .. `2026-07-31` | 128 | 0 | 0 / 0 | 0 | `3d1a70b6d447544eb4d3f862a1fd9bcb490f28b2a8725e93ab1e76187402c9a2` |
| Tier 1 August Holdout | `tier1_august_predictions_tuned.parquet` | 75,841 | 3,566 | `2026-08-01` .. `2026-08-31` | 128 | 0 | 0 / 0 | 0 | `33c59e2e4438475dea175fbd39ede81e930eb953451fa35683a7c1fad5281e06` |
| Tier 2 Validation | `tier2_val_predictions_tuned.parquet` | 64,124 | 4,117 | `2026-04-24` .. `2026-05-29` | 127 | 0 | 0 / 0 | 0 | `f0f0bb8f4c86892b998e5cf30f9bb3feeaaaf7dd4873800133e3fd3cd5c2981e` |
| Tier 2 Test | `tier2_test_predictions_tuned.parquet` | 144,215 | 7,293 | `2026-05-30` .. `2026-07-31` | 127 | 0 | 0 / 0 | 0 | `4b6825dedc8d601c831e4483e64ee896dc952fca71ff798dd007bc31427e72fb` |

- **Schema & Dtypes:**
  - Validation files: `route` (`str`), `date` (`datetime64[us]`), `daytype` (`str`), `target_rides` (`float32`), `pred_random_forest` (`float64`), `residual` (`float64`).
  - Test & August Holdout files: `route` (`str`), `date` (`datetime64[us]`), `daytype` (`str`), `target_rides` (`float32`), `rf_tuned_prediction` (`float64`), `pred_baseline_b_seasonal_naive` (`float64`), `fallback_baseline_b` (`str`).

---

## 4. Provenance Verification

- **Tier 1 vs Tier 2:** Tier 1 (`tier1_random_forest_tuned`) covers the full historical horizon starting `2025-01-01`; Tier 2 (`tier2_random_forest_tuned`) covers the GTFS-era post-April-2026 regime (`2026-04-24`..`2026-07-31`).
- **No Tier 2 August Holdout:** Verified that no Tier 2 August holdout artifact exists and `("tier2", "august_holdout")` is explicitly rejected with HTTP 400 (`UNSUPPORTED_TIER_PERIOD`).
- **No Future Forecasting:** All 5 datasets terminate on or before `2026-08-31`. Both endpoints explicitly emit `forecast_scope: "historical_evaluation_only"` and `future_forecasting_supported: false`. No `.joblib` model files are loaded or invoked.

---

## 5. Prediction Reconciliation

Representative records (first and midpoint rows after deterministic `("date", "route")` sort) were independently queried from `GET /api/v1/forecasting/historical` and reconciled against the raw Parquet files:

| Tier & Period | Offset | Route | Date | Actual | Predicted | API Abs Err | Recalc `abs(a-p)` | API Pct Err | Recalc Pct Err | Match |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | :---: |
| `tier1` / `validation` | 0 | `1001` | `2025-01-01` | 364.0 | 700.5 | 336.5 | 336.5 | 92.4451 | 92.4451 | PASS |
| `tier1` / `validation` | 18,893 | `26` | `2025-06-12` | 3089.0 | 3141.31 | 52.31 | 52.31 | 1.6934 | 1.6934 | PASS |
| `tier1` / `august_holdout` | 1,783 | `71` | `2026-08-16` | 4443.0 | 4780.3536 | 337.3536 | 337.3536 | 7.5929 | 7.5929 | PASS |
| `tier2` / `validation` | 0 | `1` | `2026-04-24` | 855.0 | 931.19 | 76.19 | 76.19 | 8.9111 | 8.9111 | PASS |
| `tier2` / `validation` | 2,058 | `143` | `2026-05-12` | 1113.0 | 1042.48 | 70.52 | 70.52 | 6.3360 | 6.3360 | PASS |
| `tier2` / `test` | 0 | `10` | `2026-05-30` | 103.0 | 230.3735 | 127.3735 | 127.3735 | 123.6636 | 123.6636 | PASS |
| `tier2` / `test` | 3,646 | `56` | `2026-06-30` | 7230.0 | 7682.9701 | 452.9701 | 452.9701 | 6.2651 | 6.2651 | PASS |

All 10 sampled records (2 per partition) matched to full precision (`abs_tol=1e-6`). `WAPE`, `MAE`, `RMSE`, and `R²` appear exclusively on `/historical/summary`, never on individual prediction items.

---

## 6. Historical Endpoint Findings (`GET /api/v1/forecasting/historical`)

- **Valid & Invalid Combinations:** All 5 valid `(tier, period)` pairs return HTTP 200 with exact record counts and date bounds; `("tier2", "august_holdout")` returns HTTP 400 (`UNSUPPORTED_TIER_PERIOD`); invalid `tier`/`period`/`start_date > end_date` return HTTP 400; out-of-bounds `limit`/`offset` or malformed dates return HTTP 422.
- **Filtering, Pagination & Ordering:** `route_id` and inclusive `start_date`/`end_date` filtering, `limit` (`1..150`), `offset`, and deterministic `("date", "route_id")` ordering all behave as specified. Empty filter results return HTTP 200 with `total_records=0` and `data=[]`.
- **Defect Identified (`M-01`):** `fallback_baseline_b` in the canonical test/holdout Parquets stores strategy strings (`calendar_t7`, `recent_28d_daytype`, `historical_mean`), which `ForecastService` coerces via `bool(...)` into `True` for every row. See Section 13.

---

## 7. Summary Endpoint Findings (`GET /api/v1/forecasting/historical/summary`)

- Returns all 5 supported `(tier, period)` summaries cleanly without merging Tier 1 and Tier 2 populations.
- Test and August Holdout metrics (`WAPE`, `MAE`, `RMSE`, `R²` and Baseline B metrics) match `final_model_evaluation_metrics.csv` verbatim.
- Validation metrics match `random_forest_champion_config.json` (`tier1_champion.metrics` and `tier2_champion.metrics`). See `L-02` regarding `rows_evaluated = common_rows + 1`.
- Both `forecast_scope: "historical_evaluation_only"` and `future_forecasting_supported: false` are always present.

---

## 8. Repository, Security & Concurrency Audit

- **Read-Only & Safe Paths:** `ForecastRepository` reads only configured Parquet/CSV/JSON paths (`settings.RF_*`); no arbitrary filesystem paths, SQL execution, `.joblib` loading, or model inference occur.
- **Caching & Immutability:** Uses `threading.Lock` double-checked locking; `_freeze_dataframe()` marks both `arr._ndarray` and direct `np.ndarray` blocks `writeable = False`.
- **Error Handling:** Missing or corrupt artifacts raise `ArtifactUnavailableError` -> HTTP 503 without leaking filesystem paths or tracebacks.

---

## 9. Missing-Value & Zero-Ridership Handling

- Canonical Parquets contain 0 nulls, 0 `NaN`/`Inf` values, and 0 `target_rides == 0` rows.
- Synthetic verification confirms `actual_rides == 0` yields `percentage_error: null`, and `NaN`/`Inf` values are sanitized via `to_optional_float()` to `null` for RFC-compliant JSON serialization.

---

## 10. Test Reproduction & Coverage Assessment

- **Independently Reproduced Test Runs:**
  - `python -m unittest discover -s backend/tests -v`: **51/51 passed** (`2.805s`).
  - `python -m unittest discover tests`: **205/205 passed** (`8.803s`).
- **Cross-Stage Regression (via `TestClient(app)`):** `/`, `/api/health`, Stage 1 (`/routes`, `/rankings/*`, `/explanation`, `/sensitivity`), Stage 2A (`/ridership/routes/151/timeseries`), Stage 2B (`/spatial/hubs`, `/spatial/hubs/top?config=a&limit=100` ending at Stop `4732`, `/spatial/clusters/summary`), Stage 2C (`/corridors/clusters`, `/corridors/routes/151/co-routing`), and Stage 2D (`/forecasting/historical`, `/forecasting/historical/summary`) all returned HTTP 200.
- **Coverage Gaps (`L-03`):** `backend/tests/test_forecast_api.py` used boolean synthetic values for `fallback_baseline_b` instead of canonical strategy strings, and did not test whitespace-only `route_id` or single-parameter (`tier`-only / `period`-only) summary filters.

---

## 11. Performance & Memory Measurements

| Metric | Implementation Report (Cold Start Process) | Independent Audit (Warm Python Process, Repo Cache Cleared) |
| --- | ---: | ---: |
| Cold `GET /forecasting/historical` (`august_holdout`, `limit=50`) | 464.41 ms | 54.32 ms |
| Warm `GET /forecasting/historical` avg (5 runs) | 40.14 ms | 33.43 ms |
| Filtered `route_id=79` (`august_holdout`) | — | 31.54 ms |
| Date-range (`2026-08-01..2026-08-15`, `limit=150`) | — | 65.09 ms |
| Max pagination (`tier1` `validation`, `limit=150`, cold cache) | 195.02 ms | 168.89 ms |
| Cold `GET /forecasting/historical/summary` | 32.86 ms | 22.85 ms |
| Warm `GET /forecasting/historical/summary` avg | 18.40 ms | 17.89 ms |
| 10-thread concurrent `august_holdout` batch | 375.40 ms | 255.01 ms |
| Traced Peak Memory (`tracemalloc`) | 7.53 MB | 3.92 MB |
| Process RSS | Not reported | Unverified (`psutil` not installed) |

**Difference Explanation:** The implementation report measured the very first `TestClient` request in a fresh Python process (including FastAPI/Starlette/PyArrow cold module imports, ~410 ms overhead). In the audit script, `reconcile_records` and `regress_all_stages` ran before `benchmark_perf`, so `get_forecast_repository.cache_clear()` measured pure repository Parquet load (`54.32 ms`) without module-import overhead.

---

## 12. SHA-256 Integrity Verification

All canonical artifacts matched their baseline SHA-256 hashes with zero modifications:
- **Phase 5 Models:** `tier1_random_forest.joblib` (`559936f8...`), `tier2_random_forest.joblib` (`d688a9e1...`), `tier1_random_forest_tuned.joblib` (`d73b7901...`), `tier2_random_forest_tuned.joblib` (`dafa999d...`).
- **Phase 5 Predictions:** All 5 Parquet files matched Section 3 hashes verbatim.
- **Phase 6.1:** `transit_hub_rankings.parquet` (`20e11689...`), `spatial_dbscan_assignments.parquet` (`3c7d40bc...`), `phase6_1_stage2_metadata.json` (`4b4cd002...`), `top100_hubs_config_a.csv` (`201682c6...`).
- **Phase 6.2 & 6.3:** `corridor_cluster_assignments.parquet` (`7cd435ab...`), `buffer_overlap_similarity_matrix.parquet` (`bbf8a437...`), `route_direction_jaccard_matrix.parquet` (`35a15c48...`), `shared_consecutive_stop_sequences.parquet` (`dd7c031a...`), `route_direction_geometries_metadata.parquet` (`e1089cc0...`), `route_direction_connectivity_matrix.parquet` (`a13f84ea...`).
- **Phase 7 & DuckDB:** `route_ranker_feature_master.parquet` (`c26aa49a...`), `route_rankings_master.parquet` (`c440671d...`), `route_ranking_explanations.json` (`56c29ef9...`), `ranking_sensitivity_analysis.parquet` (`fb41bcdf...`), `ai_routeranker.duckdb` (`ec0fd362...`).
- **Out-of-Scope Checks:** No frontend modifications, no PostgreSQL activation, no model retraining/tuning, no future-inference pipeline, and no Stage 2E work started.

---

## 13. Audit Findings

- **[MEDIUM] `M-01` — `fallback_baseline_b` string provenance collapsed to `True` for all test/holdout rows:**
  In `tier1_test_predictions_tuned.parquet`, `tier1_august_predictions_tuned.parquet`, and `tier2_test_predictions_tuned.parquet`, `fallback_baseline_b` is a `str` column (`calendar_t7` for primary lag, `recent_28d_daytype` and `historical_mean` for actual fallbacks). `ForecastService` (`backend/app/services/forecast_service.py:137`) coerces this via `bool(row["fallback_baseline_b"])`, which evaluates every non-empty string (`"calendar_t7"` included) to `True`. As a result, 100% of test/holdout API rows report `fallback_baseline_b: true` instead of distinguishing primary `calendar_t7` from fallback strategies (or preserving the string label).
- **[LOW] `L-01` — Empty/whitespace `route_id` silently treated as unfiltered:**
  In `backend/app/services/forecast_service.py:78`, `if route_id is not None and route_id.strip():` silently ignores `route_id=""` or `route_id="   "` instead of rejecting invalid whitespace input with HTTP 400.
- **[LOW] `L-02` — Validation summary `rows_evaluated` includes `+1` row beyond `common_rows`:**
  `backend/app/services/forecast_service.py:206` sets `rows_evaluated = int(m["common_rows"]) + 1` (`37,786` / `4,117`, matching Parquet row counts), whereas the `wape`/`mae`/`rmse`/`r2` values in `random_forest_champion_config.json` were computed over `common_rows` (`37,785` / `4,116`).
- **[LOW] `L-03` — Minor test coverage gaps in `test_forecast_api.py`:**
  Synthetic fixtures used boolean `fallback_baseline_b` values (`[False, True, False]`) rather than canonical strings, masking `M-01`. Whitespace `route_id` and `tier`-only / `period`-only `/historical/summary` filters are also untested.

---

## 14. Final Verdict

**PASS WITH WARNINGS** — Stage 2D is approved as a read-only historical evaluation API with one Medium (`M-01`) and three Low (`L-01`–`L-03`) remediation items recommended prior to frontend consumption of `fallback_baseline_b`.
