# AI_RouteRanker — Milestone 8 Stage 2: API Contract

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Milestone:** 8 — Backend API Integration (Stage 2 Planning)  
**Prefix:** `/api/v1` | **Conventions:** Pydantic v2, RFC 7807 errors, default `limit=25`, max `limit=150`, JSON `null` for missing numerics.  
**Date:** 2026-11-25T18:38:00+05:30  

---

## 1. Historical Ridership Endpoint

### `GET /api/v1/ridership/routes/{route_id}/timeseries`
- **Source:** DuckDB `analytical.daily_ridership` (read-only parameterized SQL).
- **Query Params:**
  - `start_date` (Optional[date], default `2020-01-01`, bounds `2001-01-01`..`2026-08-31`)
  - `end_date` (Optional[date], default `2026-08-31`)
  - `granularity` (Literal `["monthly", "daily"]`, default `"monthly"`)
  - `daytype` (Optional[Literal `["W", "A", "U"]`])
  - `limit` (int, `1..150`, default `25`), `offset` (int, `>=0`, default `0`)
- **Behavior & Edge Cases:**
  - If `start_date > end_date`: HTTP 400 `INVALID_DATE_RANGE`.
  - If `route_id` is a rail line (`Red`, `Blue`, etc.): returns `ridership_available: false`, `reason: "Rail ridership is stored at station turnstile level rather than line ID in daily_ridership"`, empty `data: []` (not confused with 0 rides).
  - If `route_id` is unknown: HTTP 404 `ROUTE_NOT_FOUND`.
- **Example Response (`200 OK`):**
  ```json
  {
    "route_id": "151",
    "granularity": "monthly",
    "ridership_available": true,
    "date_range": { "start_date": "2024-01-01", "end_date": "2026-08-31" },
    "data": [
      { "period": "2026-08", "weekday_avg_rides": 18240.5, "saturday_avg_rides": 11420.0, "sunday_avg_rides": 9110.2, "total_rides": 482150 }
    ],
    "pagination": { "total": 32, "offset": 0, "limit": 25, "returned": 25, "has_more": true }
  }
  ```

---

## 2. Spatial Hubs & Clustering Endpoints

### `GET /api/v1/spatial/hubs/top`
- **Source:** `artifacts/clustering/transit_hub_rankings.parquet` filtered by `rank_config_a <= 100` (provides `stop_lat`/`stop_lon` missing from `top100_hubs_config_a.csv`).
- **Query Params:** `config` (`a` | `b` | `c`, default `a`), `limit` (`1..100`, default `25`), `offset` (`>=0`, default `0`).
- **Example Item:** `{ "rank": 1, "stop_id": "1122", "stop_name": "...", "stop_lat": 41.8832, "stop_lon": -87.6281, "total_visits": 482, "routes_served": 14, "attributed_demand": 12450.0, "demand_intensity": 25.83, "hub_score": 0.942 }`

### `GET /api/v1/spatial/hubs`
- **Source:** `artifacts/clustering/transit_hub_rankings.parquet` (10,583 stops) + `spatial_dbscan_assignments.parquet` (`dbscan_cluster`).
- **Query Params:** `min_routes` (int `>=1`), `dbscan_cluster` (Optional[int]), `bbox` (optional `min_lat,min_lon,max_lat,max_lon` for Leaflet viewport filtering), `sort_by` (`rank_config_a` | `total_visits` | `routes_served`), `limit` (`1..150`, default `25`), `offset` (`>=0`, default `0`).
- **Coordinates:** Explicit `stop_lat`, `stop_lon` (`Optional[float]`, never recalculated).

### `GET /api/v1/spatial/clusters/summary`
- **Source:** `artifacts/clustering/phase6_1_stage2_metadata.json` + `peripheral_and_noise_stops.parquet` count.
- **Response:** `snapshot_id`, `representative_service_date`, `boarding_stops_input_count`, `active_stop_visits_count`, `dbscan_cluster_count`, `dbscan_noise_stop_count`, `kmeans_eligible_stops_count`, `coverage_metrics`.

---

## 3. Corridor Topology & Co-Routing Endpoints

### `GET /api/v1/corridors/clusters`
- **Source:** `artifacts/route_clustering/corridor_cluster_assignments.parquet` (261 patterns) + `route_direction_geometries_metadata.parquet` + `route_direction_connectivity_matrix.parquet`.
- **Query Params:** `k` (`2..12`, default `3`), `cluster_type` (`buffer` | `frechet`, default `buffer`), `route_id` (Optional[str]), `limit` (`1..150`, default `25`), `offset` (`>=0`, default `0`).
- **Distinction Preserved:** Explicitly labels `cluster_type` as `"geographic_buffer_overlap"` or `"geometric_frechet_shape"` and includes `direction_id` (`0`/`1`) and `pattern_id`.

### `GET /api/v1/corridors/routes/{route_id}/co-routing`
- **Source:** `buffer_overlap_similarity_matrix.parquet`, `route_direction_jaccard_matrix.parquet`, `shared_consecutive_stop_sequences.parquet`, `route_direction_geometries_metadata.parquet`.
- **Query Params:** `direction_id` (Optional `0` | `1`), `top_n` (`1..25`, default `10`).
- **Response:** Per directional pattern of `{route_id}`:
  - `geographic_overlap_peers` (from `buffer_overlap_similarity_matrix`, descending overlap ratio)
  - `stop_jaccard_peers` (from `route_direction_jaccard_matrix`, descending Jaccard index)
  - `shared_consecutive_sequences` (from `shared_consecutive_stop_sequences`, ordered by `sequence_length` desc, with `start_stop_id`, `end_stop_id`, `shared_stops`)
  - Raises HTTP 404 `ROUTE_NOT_FOUND` for unknown routes.

---

## 4. Forecasting Evaluation Endpoints (Honest Scope)

### `GET /api/v1/forecasting/summary`
- **Source:** `reports/modeling/random_forest/final_model_evaluation_metrics.csv` + `artifacts/random_forest/random_forest_experiment_config.json`.
- **Response:**
  - `forecast_scope: "historical_evaluation_only"`
  - `future_forecasting_supported: false`
  - `future_forecasting_note: "Tuned Random Forest models require observed autoregressive lag features; no verified future-date inference pipeline exists beyond 2026-08-31."`
  - `evaluations`: Tier 1 Test (`2025-11-23..2026-07-31`, $R^2=0.9756$), Tier 1 August Holdout (`2026-08-01..2026-08-31`, $R^2=0.9761$), Tier 2 Test (`2026-05-30..2026-07-31`, $R^2=0.9788$).

### `GET /api/v1/forecasting/routes/{route_id}`
- **Source:** `tier1_august_predictions_tuned.parquet` (`2026-08-01..2026-08-31`), `tier1_test_predictions_tuned.parquet`, `tier2_test_predictions_tuned.parquet`.
- **Query Params:** `tier` (`tier1_august` | `tier1_test` | `tier2_test`, default `tier1_august`), `limit` (`1..150`, default `31`), `offset` (`>=0`, default `0`).
- **Honest Rail & Scope Representation:**
  - Explicit `prediction_type: "historical_holdout_evaluation"`, `future_forecasting_supported: false`.
  - For CTA rail lines (`Red`, `Blue`, etc.): returns `forecasting_supported: false`, `reason: "Random Forest demand models were trained on bus route ridership only; rail lines are excluded."`, `data: []`.
  - For unknown routes: HTTP 404 `ROUTE_NOT_FOUND`.
