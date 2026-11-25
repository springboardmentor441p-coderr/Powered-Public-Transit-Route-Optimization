# AI_RouteRanker — Milestone 8 Stage 2: Discovery Report

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Milestone:** 8 — Backend API Integration  
**Stage:** 2 — Historical Analytics, Spatial Hubs, Corridor Topology and Forecasting APIs  
**Date:** 2026-11-25T18:38:00+05:30  
**Status:** DISCOVERY & PLANNING ONLY (READ-ONLY)  

---

## 1. Stage 1 Compatibility Preflight & Audit Findings

Inspection of the completed Stage 1 backend (`backend/app/`) confirms:
- **FastAPI & `/api/v1` Router:** `backend/app/main.py` preserves `GET /` and `GET /api/health` while mounting `api_v1_router` at `/api/v1`.
- **Architecture:** Clean 3-tier separation (`api/v1/` → `services/` → `repositories/`) with `ParquetRepository` and `JSONRepository` injected via `backend/app/api/v1/deps.py`.
- **Schemas & Error Handling:** Pydantic v2 models (`common.py`, `route.py`, `ranking.py`) with `ConfigDict(extra="forbid")`, `NaN`-to-`None` sanitization, default pagination `25`, max limit `150`, and RFC 7807-style global exception handlers in `backend/app/core/exceptions.py`.
- **Stage 1 Tests:** 15/15 backend tests (`backend/tests/`) and 205/205 project analytics tests (`tests/`) pass.

### Handling of Accepted Stage 1 Audit Findings (L-01 & L-02)
- **L-01 (Unnecessary `copy.deepcopy` in `RankingService._build_ranking_item`):** Calling `JSONRepository.get_explanation()` deep-copies the full narrative/drivers payload per row on `limit=125`/`133`.
- **L-02 (Unlocked Lazy Cache Initialization):** `ParquetRepository._cache` and `JSONRepository._index` lack a `threading.Lock` on cold-start population.
- **Recommendation:** Address L-01 and L-02 in a **dedicated, isolated pre-Stage 2A hardening commit** (or at the start of Stage 2A before adding new repositories) with explicit regression checks so Stage 1 behavior remains 100% preserved and auditable. All new Stage 2 repositories (`DuckDBRepository`, etc.) must include `threading.Lock` from day one.

---

## 2. Historical Analytics Discovery (`data/processed/ai_routeranker.duckdb`)

- **Database File:** `data/processed/ai_routeranker.duckdb` (`1,007,169,536` bytes / ~960.5 MB, SHA-256: `ec0fd3626c6734fa2f96d6202a6d4966ae193598cc6e1ca84a828c295eee4209`).
- **Schemas & Tables:** All 16 analytical tables reside in the **`analytical`** schema (no tables in `main`; no explicit secondary indexes in `duckdb_indexes()`).
- **Primary Ridership Tables:**
  - `analytical.daily_ridership`: **1,124,170 rows**, columns: `route (VARCHAR)`, `date (DATE)`, `daytype (VARCHAR: W/A/U)`, `rides (BIGINT)`, `day_of_week (VARCHAR)`, `day_of_week_int (BIGINT)`, `is_weekend (BOOLEAN)`, `matched_snapshot_id (VARCHAR)`, `matched_snapshot_label (VARCHAR)`, `in_gtfs_coverage (BOOLEAN)`.
  - `analytical.cta_ridership_clean`: **1,124,170 rows**, columns: `route`, `date`, `daytype`, `daytype_label`, `rides`.
- **Coverage & Data Quality:**
  - Date coverage: **`2001-01-01` to `2026-08-31`** (~25.7 years).
  - Distinct routes in ridership table: **188** (historical + active bus routes; note that CTA rail lines are not in this bus ridership table).
  - Null rides: **0**.
- **Design for `GET /api/v1/ridership/routes/{route_id}/timeseries`:**
  - Open DuckDB strictly with `read_only=True`, `PRAGMA max_memory='256MB'`, `PRAGMA threads=2`.
  - Use parameterized SQL (`WHERE route = ? AND date >= ? AND date <= ?`) with monthly or daily aggregation (`granularity=monthly|daily`) and bounded date windows so the 1.12M-row table is never loaded into Python memory.
  - Note: For rail lines (`Red`, `Blue`, etc.) or routes absent from `daily_ridership`, return an explicit unavailable/unsupported status or HTTP 404/structured empty indicator distinguishing unsupported rail ridership from zero rides.

---

## 3. Spatial Hubs Discovery (Phase 6.1 Outputs)

Inspection of `artifacts/clustering/` verified the following canonical spatial artifacts:
- `top100_hubs_config_a.csv`: **100 rows $\times$ 8 columns** (`rank_config_a`, `stop_id`, `stop_name`, `score_config_a`, `total_visits`, `routes_served`, `attributed_demand`, `demand_intensity`). Note: does **not** include `stop_lat`/`stop_lon`; must join by `stop_id` with `transit_hub_rankings.parquet` (or read top-100 directly from `transit_hub_rankings.parquet` sorted by `rank_config_a <= 100`) to obtain Leaflet coordinates!
- `transit_hub_rankings.parquet`: **10,583 rows $\times$ 14 columns**, including `stop_id`, `stop_name`, `stop_lat`, `stop_lon`, `total_visits`, `routes_served`, `attributed_demand`, `demand_intensity`, `score_config_a/b/c`, `rank_config_a/b/c`.
  - Coordinate integrity: **0 null `stop_lat`**, **0 null `stop_lon`**, bounds `lat=[41.6442, 42.0647]` (valid Chicago metro coordinates for Leaflet).
- `spatial_dbscan_assignments.parquet`: **11,020 rows $\times$ 7 columns** (`stop_id`, `stop_name`, `stop_lat`, `stop_lon`, `proj_x`, `proj_y`, `dbscan_cluster`), **0 null coordinates**.
- `stop_level_feature_master.parquet`: **11,020 rows $\times$ 59 columns** (includes `flag_zero_visits`, `flag_unavailable_demand`, `flag_no_am_headway`, `flag_partial_demand`, `primary_eligibility_status`, `kmeans_k3..k8`, `dist_to_center_km`).
- `phase6_1_stage2_metadata.json`: Contains `dbscan_cluster_count`, `dbscan_noise_stop_count`, `kmeans_eligible_stops_count`, `coverage_metrics`, `demand_conservation`.

---

## 4. Corridor Topology Discovery (Phase 6.2 & 6.3 Outputs)

Inspection of `artifacts/route_clustering/` and `artifacts/ranking_features/` verified:
- `corridor_cluster_assignments.parquet`: **261 directional patterns $\times$ 25 columns** (`pattern_id`, `route_id`, `direction_id`, `cluster_buffer_k2..k12`, `cluster_frechet_k2..k12`).
- `buffer_overlap_similarity_matrix.parquet`: **261 $\times$ 261** symmetric/directional matrix of 250m spatial buffer overlap ratios (`pattern_id` index and columns like `151__dir_0`).
- `route_direction_jaccard_matrix.parquet`: **261 $\times$ 261** matrix of stop-set Jaccard similarity.
- `shared_consecutive_stop_sequences.parquet`: **950 rows $\times$ 7 columns** (`pattern_a`, `pattern_b`, `sequence_length`, `shared_sequence_str`, `start_stop_id`, `end_stop_id`, `shared_stops_json`).
- `route_direction_geometries_metadata.parquet`: **261 rows $\times$ 11 columns** (`pattern_id`, `route_id`, `direction_id`, `representative_shape_id`, `scheduled_trip_count`, `length_km`, etc.).
- `route_direction_connectivity_matrix.parquet`: **261 rows $\times$ 5 columns** (`pattern_id`, `route_id`, `direction_id`, `hub_stop_count`, `hub_stop_ratio`).

**Methodological Distinction:** The API must preserve the distinction between:
1. **Geographic buffer overlap** (`buffer_overlap_similarity_matrix.parquet`, `cluster_buffer_k*`) and Fréchet geometric shape similarity (`cluster_frechet_k*`), vs
2. **Shared consecutive stop sequences** (`shared_consecutive_stop_sequences.parquet`, `route_direction_jaccard_matrix.parquet`), vs
3. **Operational typology** (`route_level_operational_features.parquet`, `operational_cluster_label`).
Geographic clustering is **not** corridor orientation; directional metadata is explicitly represented via `pattern_id` (`{route_id}__dir_{0|1}`).

---

## 5. Forecasting Discovery — Critical Methodology Check

Inspection of `analytics/forecasting/__init__.py` (empty), `analytics/modeling/random_forest/`, `artifacts/random_forest/`, and `reports/modeling/random_forest/final_model_evaluation_metrics.csv` established the following critical facts:

1. **Historical Validation Predictions (Available):**
   - `tier1_val_predictions_tuned.parquet`: 37,786 rows (`2025-01-01` to `2025-11-22`, 129 routes).
   - `tier2_val_predictions_tuned.parquet`: 4,117 rows (`2026-04-24` to `2026-05-29`, 127 routes).
2. **Historical Holdout / Test Predictions (Available):**
   - `tier1_test_predictions_tuned.parquet`: 28,798 rows (`2025-11-23` to `2026-07-31`, 128 routes; $R^2=0.9756$, $\text{WAPE}=8.53\%$, $\text{MAE}=402.18$).
   - `tier1_august_predictions_tuned.parquet`: 3,566 rows (`2026-08-01` to `2026-08-31`, 128 routes; $R^2=0.9761$, $\text{WAPE}=8.20\%$, $\text{MAE}=399.54$).
   - `tier2_test_predictions_tuned.parquet`: 7,293 rows (`2026-05-30` to `2026-07-31`, 127 routes; $R^2=0.9788$, $\text{WAPE}=8.10\%$, $\text{MAE}=394.51$).
3. **Genuine Future-Date Forecasts (UNAVAILABLE):**
   - The tuned Random Forest models (`tier1_random_forest_tuned.joblib`, 160 features; `tier2_random_forest_tuned.joblib`, 169 features) depend on observed autoregressive lag features (`rides_lag_1`, `rides_lag_7`, `rides_lag_14`, `rides_lag_28`, `rolling_mean_7/14/28`).
   - There is **no** verified recursive lag-generation or future-schedule inference pipeline in `analytics/forecasting/` to generate predictions beyond `2026-08-31`.
4. **Rail Coverage Limitation:**
   - CTA heavy rail lines (`Red`, `Blue`, `Brn`, `G`, `Org`, `P`, `Pink`, `Y`) are not present in the Random Forest prediction files.
5. **Honest API Design Mandate:**
   - `GET /api/v1/forecasting/summary` and `GET /api/v1/forecasting/routes/{route_id}` will serve the verified **historical evaluation & holdout predictions** alongside `final_model_evaluation_metrics.csv`, explicitly declaring `forecast_scope: "historical_evaluation_only"` and `future_forecasting_supported: false`. Historical test predictions will **never** be presented as future forecasts.
