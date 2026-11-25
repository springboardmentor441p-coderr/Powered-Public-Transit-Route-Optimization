# AI_RouteRanker — Milestone 8: Backend API Integration
## Phase 8 API Endpoint Catalog & Specification

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Milestone:** 8 — Backend API Integration  
**Document:** API Catalog & Detailed Interface Specification  
**Author:** AI_RouteRanker Engineering & Analytics Team  
**Date:** 2026-11-25T17:26:00+05:30  
**API Base Prefix:** `/api`  
**Status:** APPROVED DESIGN SPECIFICATION (PLANNING PHASE)  

---

## 1. Catalog Overview & Routing Architecture

The AI_RouteRanker REST API is structured into 8 modular routers mounted under the standard `/api` prefix. The API is strictly read-only, deterministic, stateless, and optimized for low-latency JSON delivery to the React frontend dashboard.

```text
/api
├── /health                     -> System health & operational ping
├── /system/status              -> Environment diagnostics & memory status
├── /routes                     -> Route directory, search, & detailed profiles
├── /rankings                   -> Multi-criteria rankings, explanations, & sensitivity
├── /spatial                    -> Transit hubs, stop clusters, & geospatial coordinates
├── /corridors                  -> Co-routing, overlap clusters, & shared stops
├── /forecasting                -> Random Forest demand predictions & validation
├── /ridership                  -> Historical ridership trends & daytype analytics
└── /metadata                   -> Feature dictionaries, model configs, & phase provenance
```

---

## 2. Detailed API Specifications by Domain

### Group 1: System & Health Diagnostics

#### 1.1 Health Check
- **HTTP Method:** `GET`
- **URL Path:** `/api/health`
- **Purpose:** Fast operational ping for frontend startup and load balancer health checks.
- **Query Parameters:** None.
- **Request Schema:** None.
- **Response Schema:** `HealthCheckResponse`
  ```json
  {
    "status": "ok",
    "message": "AI_RouteRanker backend is running successfully",
    "project": "AI_RouteRanker",
    "version": "0.1.0",
    "environment": "development",
    "timestamp": "2026-11-25T11:56:55.123456Z"
  }
  ```
- **Validation Rules:** N/A.
- **Error Responses:** `500 Internal Server Error` if application fails to respond.
- **Data Source:** In-memory configuration (`app.core.config.settings`).
- **Expected Response Size:** $\sim 250\text{ bytes}$.

#### 1.2 System Diagnostic Status
- **HTTP Method:** `GET`
- **URL Path:** `/api/system/status`
- **Purpose:** Returns server environment metrics, available RAM, and artifact accessibility status.
- **Query Parameters:** None.
- **Request Schema:** None.
- **Response Schema:** `SystemStatusResponse`
  ```json
  {
    "status": "healthy",
    "python_version": "3.11.9",
    "memory": {
      "available_mb": 1401.5,
      "load_percent": 82.0
    },
    "artifacts": {
      "rankings_master": true,
      "feature_master": true,
      "explanations": true,
      "duckdb_connected": true
    },
    "service_date": "2026-06-10",
    "canonical_routes_count": 133
  }
  ```
- **Validation Rules:** None.
- **Error Responses:** `503 Service Unavailable` if core Parquet files are missing.
- **Data Source:** OS memory status + `Path.exists()` on core artifacts.
- **Expected Response Size:** $\sim 600\text{ bytes}$.

---

### Group 2: Transit Routes Directory

#### 2.1 List All Routes
- **HTTP Method:** `GET`
- **URL Path:** `/api/routes`
- **Purpose:** Searchable and filterable directory of all canonical CTA transit routes.
- **Query Parameters:**
  - `mode` (Optional[str]): Filter by mode (`bus` or `rail`). Default: `None` (all).
  - `cluster` (Optional[str]): Filter by operational typology (`High-Volume Trunk`, `Standard Radial/Circulator`, `High-Frequency Radial/Connector`).
  - `query` (Optional[str]): Case-insensitive search on route ID, short name, or long name.
  - `limit` (int): Items per page ($1 \le \text{limit} \le 150$, default `50`).
  - `offset` (int): Pagination offset ($\ge 0$, default `0`).
- **Response Schema:** `RouteListResponse`
  ```json
  {
    "total": 133,
    "offset": 0,
    "limit": 50,
    "routes": [
      {
        "route_id": "151",
        "route_short_name": "151",
        "route_long_name": "Sheridan",
        "route_type": 3,
        "is_rail": false,
        "operational_cluster": "High-Volume Trunk",
        "regional_partition": "North",
        "scheduled_trips": 329,
        "service_span_hours": 24.6,
        "am_headway_min": 5.4,
        "forecasted_daily_demand": 18240.5
      }
    ]
  }
  ```
- **Validation Rules:** `limit` capped at 150; mode must be `bus` or `rail`.
- **Error Responses:** `400 Bad Request` on invalid query params.
- **Data Source:** `artifacts/ranking_features/route_ranker_feature_master.parquet`.
- **Expected Response Size:** $\sim 8\text{ KB}$ (for 50 routes).

#### 2.2 Get Route Details
- **HTTP Method:** `GET`
- **URL Path:** `/api/routes/{route_id}`
- **Purpose:** Complete operational, demand, hub, and corridor feature profile for a single route.
- **Path Parameters:** `route_id` (str, e.g. `"151"`, `"Red"`, `"79"`).
- **Query Parameters:** None.
- **Response Schema:** `RouteDetailResponse`
  ```json
  {
    "route_id": "151",
    "route_short_name": "151",
    "route_long_name": "Sheridan",
    "is_rail": false,
    "operational": {
      "scheduled_trips": 329,
      "service_span_hours": 24.6,
      "am_headway_min": 5.4,
      "route_length_km": 28.4,
      "unique_stops_count": 94,
      "operational_cluster": "High-Volume Trunk"
    },
    "demand": {
      "historical_mean_daily_rides": 18120.4,
      "forecasted_daily_demand": 18240.5,
      "rides_per_trip": 55.4,
      "load_intensity_factor": 1.28
    },
    "hubs": {
      "hub_stop_count": 28,
      "hub_stop_ratio": 0.298,
      "hub_connectivity_index": 0.742
    },
    "corridor": {
      "max_corridor_overlap": 0.84,
      "corridor_duplication_index": 0.682,
      "shared_consecutive_stops": 34
    }
  }
  ```
- **Validation Rules:** Route ID must exist in canonical 133 route roster.
- **Error Responses:** `404 Not Found` if route ID is unknown.
- **Data Source:** `artifacts/ranking_features/route_ranker_feature_master.parquet`.
- **Expected Response Size:** $\sim 1.2\text{ KB}$.

---

### Group 3: Multi-Criteria Route Rankings

#### 3.1 Bus Network Priority Rankings (Track 1)
- **HTTP Method:** `GET`
- **URL Path:** `/api/rankings/bus`
- **Purpose:** Primary production ranking of 125 bus routes evaluated under Profile A.
- **Query Parameters:**
  - `sort_by` (str): Field to sort by (`rank`, `wsm_score`, `pillar_demand`, `pillar_service`, `pillar_hub`, `pillar_corridor`, `topsis_score`). Default: `rank`.
  - `order` (str): Sort direction (`asc` or `desc`). Default: `asc`.
  - `partition` (Optional[str]): Filter by regional partition (`North`, `South`, `West`, `Central`).
  - `limit` (int): Page limit (1-125, default `25`).
  - `offset` (int): Page offset ($\ge 0$, default `0`).
- **Response Schema:** `BusRankingListResponse`
  ```json
  {
    "track": "BUS_PRIORITY",
    "profile": "BALANCED_DEFAULT",
    "total_routes": 125,
    "offset": 0,
    "limit": 25,
    "items": [
      {
        "rank": 1,
        "route_id": "151",
        "route_short_name": "151",
        "wsm_score": 0.6363,
        "percentile_rank": 100.0,
        "topsis_score": 0.6111,
        "topsis_rank": 3,
        "pillars": {
          "demand_score": 0.2624,
          "service_score": 0.1498,
          "hub_score": 0.1062,
          "corridor_score": 0.1179
        },
        "contributions": {
          "forecasted_demand": 0.1249,
          "load_intensity": 0.1375,
          "scheduled_trips": 0.0763,
          "service_span": 0.0482,
          "am_headway": 0.0253,
          "hub_stop_ratio": 0.1062,
          "corridor_duplication": 0.1179
        },
        "is_headway_missing": false
      }
    ]
  }
  ```
- **Validation Rules:** Sorting field validated; limit $\le 125$.
- **Error Responses:** `400 Bad Request` on unsupported sort fields.
- **Data Source:** `artifacts/ranking_results/route_rankings_master.parquet`.
- **Expected Response Size:** $\sim 12\text{ KB}$ (for 25 routes).

#### 3.2 Heavy Rail Operational Priority Rankings (Track 2)
- **HTTP Method:** `GET`
- **URL Path:** `/api/rankings/rail`
- **Purpose:** Operational ranking of all 8 CTA heavy rail lines (zero demand criteria).
- **Query Parameters:** None (returns all 8 lines).
- **Response Schema:** `RailRankingResponse`
  ```json
  {
    "track": "RAIL_PRIORITY",
    "profile": "RAIL_PRIORITY",
    "total_routes": 8,
    "items": [
      {
        "rank": 1,
        "route_id": "Red",
        "route_short_name": "Red Line",
        "wsm_score": 0.8458,
        "topsis_score": 0.8999,
        "scheduled_trips": 424,
        "service_span_hours": 24.97,
        "am_headway_min": 4.93,
        "corridor_duplication_index": 0.2399,
        "pillars": {
          "demand_score": 0.0,
          "service_score": 0.7978,
          "hub_score": 0.0,
          "corridor_score": 0.0480
        }
      }
    ]
  }
  ```
- **Validation Rules:** None.
- **Error Responses:** None.
- **Data Source:** `artifacts/ranking_results/route_rankings_master.parquet`.
- **Expected Response Size:** $\sim 3\text{ KB}$.

#### 3.3 Unified Network Operational Supply Rankings (Track 3)
- **HTTP Method:** `GET`
- **URL Path:** `/api/rankings/unified`
- **Purpose:** Mode-agnostic operational supply rankings across all 133 transit routes.
- **Query Parameters:**
  - `mode` (Optional[str]): Filter by mode (`bus` or `rail`). Default: `None`.
  - `limit` (int): Page limit (1-133, default `25`).
  - `offset` (int): Page offset ($\ge 0$, default `0`).
- **Response Schema:** `UnifiedRankingListResponse`
  ```json
  {
    "track": "UNIFIED_SUPPLY",
    "profile": "UNIFIED_SUPPLY",
    "total_routes": 133,
    "offset": 0,
    "limit": 25,
    "items": [
      {
        "rank": 1,
        "route_id": "Red",
        "route_short_name": "Red Line",
        "is_rail": true,
        "wsm_score": 0.8458,
        "topsis_score": 0.7915,
        "scheduled_trips": 424,
        "service_span_hours": 24.97,
        "am_headway_min": 4.93,
        "corridor_duplication_index": 0.2399
      },
      {
        "rank": 2,
        "route_id": "79",
        "route_short_name": "79th",
        "is_rail": false,
        "wsm_score": 0.8417,
        "topsis_score": 0.7965,
        "scheduled_trips": 457,
        "service_span_hours": 24.78,
        "am_headway_min": 5.58,
        "corridor_duplication_index": 0.2650
      }
    ]
  }
  ```
- **Validation Rules:** Limit $\le 133$.
- **Error Responses:** None.
- **Data Source:** `artifacts/ranking_results/route_rankings_master.parquet`.
- **Expected Response Size:** $\sim 8\text{ KB}$.

---

### Group 4: Route Explanations & Sensitivity

#### 4.1 Get Route Ranking Explanation
- **HTTP Method:** `GET`
- **URL Path:** `/api/rankings/routes/{route_id}/explanation`
- **Purpose:** Delivers natural-language explanation narrative, missing criteria indicators, and top feature drivers for a route.
- **Path Parameters:** `route_id` (str, e.g. `"151"`, `"10"`, `"Red"`).
- **Query Parameters:**
  - `track` (Optional[str]): Specific track (`BUS_PRIORITY`, `RAIL_PRIORITY`, `UNIFIED_SUPPLY`). Defaults automatically based on route mode.
- **Response Schema:** `RouteExplanationResponse`
  ```json
  {
    "route_id": "151",
    "route_name": "Sheridan",
    "track": "BUS_PRIORITY",
    "profile": "BALANCED_DEFAULT",
    "rank": 1,
    "total_routes": 125,
    "overall_score": 0.6363,
    "narrative": "Route 151 (Sheridan) ranks #1 of 125 routes in the BUS_PRIORITY track under the BALANCED_DEFAULT profile with an overall multi-criteria priority score of 0.6363. Its evaluation is primarily elevated by strong Passenger Load Intensity, Forecasted Passenger Volume. This ranking identifies the route for operational planning review and corridor investigation.",
    "top_positive_drivers": [
      {
        "criterion": "Passenger Load Intensity",
        "feature_key": "load_intensity_factor_norm",
        "contribution": 0.1375,
        "score": 0.6874
      },
      {
        "criterion": "Forecasted Passenger Volume",
        "feature_key": "forecasted_daily_demand_norm",
        "contribution": 0.1249,
        "score": 0.8327
      }
    ],
    "top_negative_drivers": [],
    "is_headway_missing": false,
    "missing_criteria": []
  }
  ```
- **Validation Rules:** Route ID must exist.
- **Error Responses:** `404 Not Found` if route is unknown or explanation not generated.
- **Data Source:** `artifacts/ranking_results/route_ranking_explanations.json`.
- **Expected Response Size:** $\sim 1.5\text{ KB}$.

#### 4.2 Get Sensitivity Analysis Scenarios
- **HTTP Method:** `GET`
- **URL Path:** `/api/rankings/sensitivity`
- **Purpose:** Returns the 60 one-at-a-time (OAT) weight perturbation scenarios evaluating ranking robustness.
- **Query Parameters:**
  - `track` (Optional[str]): Filter by track (`BUS_PRIORITY`, `RAIL_PRIORITY`, `UNIFIED_SUPPLY`). Default: all 60 scenarios.
- **Response Schema:** `SensitivityScenarioListResponse`
  ```json
  {
    "total_scenarios": 60,
    "items": [
      {
        "scenario_id": "forecasted_daily_demand_norm_-20pct",
        "track": "BUS_PRIORITY",
        "target_criterion": "forecasted_daily_demand_norm",
        "delta": -0.20,
        "spearman_rho": 0.9989,
        "mean_absolute_rank_shift": 0.74,
        "max_rank_shift": 6,
        "top_10_overlap": 1.00,
        "top_20_overlap": 0.95
      }
    ]
  }
  ```
- **Validation Rules:** Track must be valid identifier if provided.
- **Error Responses:** `400 Bad Request` on invalid track.
- **Data Source:** `artifacts/ranking_results/ranking_sensitivity_analysis.parquet`.
- **Expected Response Size:** $\sim 8\text{ KB}$.

---

### Group 5: Spatial Hubs & Clustering

#### 5.1 Get Top Transit Hubs
- **HTTP Method:** `GET`
- **URL Path:** `/api/spatial/hubs/top`
- **Purpose:** Returns the curated Top 100 regional multi-modal transit transfer hubs with coordinates for Leaflet map markers.
- **Query Parameters:**
  - `limit` (int): Limit returned hubs ($1 \le \text{limit} \le 100$, default `50`).
- **Response Schema:** `TopHubsResponse`
  ```json
  {
    "count": 50,
    "hubs": [
      {
        "stop_id": "1122",
        "stop_name": "State & Washington",
        "lat": 41.8832,
        "lon": -87.6281,
        "total_visits": 482,
        "routes_served_count": 14,
        "hub_importance_score": 0.942,
        "is_rail_station": false
      }
    ]
  }
  ```
- **Validation Rules:** Limit $\le 100$.
- **Error Responses:** None.
- **Data Source:** `artifacts/clustering/top100_hubs_config_a.csv`.
- **Expected Response Size:** $\sim 6\text{ KB}$.

#### 5.2 Get Stop Spatial Clustering Overview
- **HTTP Method:** `GET`
- **URL Path:** `/api/spatial/clusters/summary`
- **Purpose:** Spatial DBSCAN and KMeans cluster distribution summary for stops.
- **Query Parameters:** None.
- **Response Schema:** `SpatialClusterSummaryResponse`
- **Data Source:** `artifacts/clustering/phase6_1_stage2_metadata.json`.
- **Expected Response Size:** $\sim 2\text{ KB}$.

---

### Group 6: Route Corridors & Similarity

#### 6.1 Get Corridor Cluster Assignments
- **HTTP Method:** `GET`
- **URL Path:** `/api/corridors/clusters`
- **Purpose:** Returns operational route corridor assignments and co-routing clusters across 261 directional patterns.
- **Query Parameters:**
  - `k` (int): Number of corridor clusters (2, 3, or 4; default `3`).
- **Response Schema:** `CorridorClusterListResponse`
- **Data Source:** `artifacts/route_clustering/corridor_cluster_assignments.parquet`.
- **Expected Response Size:** $\sim 15\text{ KB}$.

#### 6.2 Get Route Corridor Profile
- **HTTP Method:** `GET`
- **URL Path:** `/api/corridors/routes/{route_id}/co-routing`
- **Purpose:** Returns top co-routing overlapping routes, shared consecutive stops, and buffer similarity index for a specific route.
- **Path Parameters:** `route_id` (str).
- **Response Schema:** `RouteCoRoutingResponse`
- **Data Source:** `artifacts/route_clustering/buffer_overlap_similarity_matrix.parquet` + `shared_consecutive_stop_sequences.parquet`.
- **Expected Response Size:** $\sim 3\text{ KB}$.

---

### Group 7: Demand Forecasting Analytics

#### 7.1 Get Forecasting Model Summary
- **HTTP Method:** `GET`
- **URL Path:** `/api/forecasting/summary`
- **Purpose:** Overall model performance metrics ($R^2$, RMSE, MAE) for Tier 1 and Tier 2 Random Forest models.
- **Response Schema:** `ForecastSummaryResponse`
- **Data Source:** `reports/phase5/` evaluation metadata.
- **Expected Response Size:** $\sim 2\text{ KB}$.

#### 7.2 Get Route Demand Forecast
- **HTTP Method:** `GET`
- **URL Path:** `/api/forecasting/routes/{route_id}`
- **Purpose:** Predicted daily passenger demand, load intensity, and historical actual comparison for a specific route.
- **Path Parameters:** `route_id` (str).
- **Response Schema:** `RouteForecastDetailResponse`
- **Data Source:** `artifacts/random_forest/tier1_august_predictions_tuned.parquet` + feature master.
- **Expected Response Size:** $\sim 4\text{ KB}$.

---

### Group 8: Historical Ridership Analytics

#### 8.1 Get Route Ridership Timeseries
- **HTTP Method:** `GET`
- **URL Path:** `/api/ridership/routes/{route_id}/timeseries`
- **Purpose:** Monthly aggregated ridership trends (mean daily rides by Weekday, Saturday, Sunday) for Recharts line charts.
- **Path Parameters:** `route_id` (str).
- **Query Parameters:**
  - `start_year` (Optional[int]): Starting year (e.g. `2018`, default `2020`).
  - `end_year` (Optional[int]): Ending year (e.g. `2024`, default `2024`).
- **Response Schema:** `RouteRidershipTimeSeriesResponse`
- **Data Source:** DuckDB (`analytical.daily_ridership` via parameterized query).
- **Expected Response Size:** $\sim 5\text{ KB}$.

---

### Group 9: Metadata & Provenance

#### 9.1 Get Analytics Phases Metadata
- **HTTP Method:** `GET`
- **URL Path:** `/api/metadata/phases`
- **Purpose:** Full audit provenance for Milestones 5, 6.1, 6.2, 6.3, and 7, including SHA-256 hashes, execution dates, and route counts.
- **Response Schema:** `PhasesMetadataResponse`
- **Data Source:** `artifacts/ranking_results/phase7_metadata.json`.
- **Expected Response Size:** $\sim 4\text{ KB}$.
