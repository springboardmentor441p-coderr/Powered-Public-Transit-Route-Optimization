# Phase 8, Stage 2E — Complete Backend Endpoint Inventory

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Total Verified Endpoints:** 17 (2 Core + 15 `/api/v1/*`)  

| # | Method | Path | Query / Path Params | Response Schema | Pagination | Canonical Source | Key Analytical / Scope Limitation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `GET` | `/` | — | JSON dict | No | App metadata | Status & doc links only |
| 2 | `GET` | `/api/health` | — | `HealthCheckResponse` | No | `settings` | Readiness & artifact presence |
| 3 | `GET` | `/api/v1/routes` | `mode`, `search`, `limit` (1..150, def 25), `offset` (>=0) | `RouteListResponse` | Yes | `route_ranker_feature_master.parquet` | 133 canonical routes (125 bus + 8 rail) |
| 4 | `GET` | `/api/v1/routes/{route_id}` | `route_id` | `RouteDetailResponse` | No | `route_ranker_feature_master.parquet` | Rail demand metrics unavailable (`null`) |
| 5 | `GET` | `/api/v1/rankings/bus` | `limit`, `offset` | `RankingListResponse` | Yes | `route_rankings_master.parquet`, `route_ranking_explanations.json` | Track 1 (125 bus routes) |
| 6 | `GET` | `/api/v1/rankings/rail` | `limit`, `offset` | `RankingListResponse` | Yes | `route_rankings_master.parquet`, `route_ranking_explanations.json` | Track 2 (8 rail lines; 0.0 demand pillar) |
| 7 | `GET` | `/api/v1/rankings/unified` | `limit`, `offset` | `RankingListResponse` | Yes | `route_rankings_master.parquet`, `route_ranking_explanations.json` | Track 3 (133 routes; structural-only comparison) |
| 8 | `GET` | `/api/v1/rankings/routes/{route_id}/explanation` | `route_id`, `track` | `RouteExplanationResponse` | No | `route_ranking_explanations.json` | Explains Phase 7 deterministic scores |
| 9 | `GET` | `/api/v1/rankings/sensitivity` | `track` | `SensitivityListResponse` | No | `ranking_sensitivity_analysis.parquet` | 60 sensitivity scenarios |
| 10 | `GET` | `/api/v1/ridership/routes/{route_id}/timeseries` | `route_id`, `granularity`, `start_date`, `end_date`, `daytype`, `limit`, `offset` | `RidershipTimeseriesResponse` | Yes | `ai_routeranker.duckdb` (`analytical.daily_ridership`) | Bus-only (`2024-01-01`..`2026-08-31`); rail returns `ridership_available=false` |
| 11 | `GET` | `/api/v1/spatial/hubs/top` | `config` (`a`\|`b`\|`c`), `limit`, `offset` | `TopHubsResponse` | Yes | `transit_hub_rankings.parquet`, `top100_hubs_config_a.csv` | Spatial demand proxy; canonical tie-breaking preserved |
| 12 | `GET` | `/api/v1/spatial/hubs` | `dbscan_cluster`, `eligible_only`, `min_lat`, `max_lat`, `min_lon`, `max_lon`, `sort_by`, `limit`, `offset` | `SpatialHubsListResponse` | Yes | `transit_hub_rankings.parquet`, `spatial_dbscan_assignments.parquet` | Supports DBSCAN noise (`-1`) & bbox filtering |
| 13 | `GET` | `/api/v1/spatial/clusters/summary` | — | `ClusterSummaryResponse` | No | `spatial_dbscan_assignments.parquet`, `phase6_1_stage2_metadata.json` | Phase 6.1 DBSCAN summary |
| 14 | `GET` | `/api/v1/corridors/clusters` | `k`, `cluster_type`, `mode`, `limit`, `offset` | `CorridorClusterListResponse` | Yes | `corridor_cluster_assignments.parquet` | Buffer overlap vs Jaccard kept distinct |
| 15 | `GET` | `/api/v1/corridors/routes/{route_id}/co-routing` | `route_id`, `peer_limit` | `RouteCoRoutingResponse` | Peer slice | `buffer_overlap_similarity_matrix.parquet`, `route_direction_jaccard_matrix.parquet`, `shared_consecutive_stop_sequences.parquet`, `route_direction_geometries_metadata.parquet`, `route_direction_connectivity_matrix.parquet` | Metrics never merged; `NaN` pairs reported as missing |
| 16 | `GET` | `/api/v1/forecasting/historical` | `tier`, `period`, `route_id`, `start_date`, `end_date`, `limit`, `offset` | `HistoricalForecastResponse` | Yes | `tier{1,2}_{val,test,august}_predictions_tuned.parquet` | `historical_evaluation_only`; `future_forecasting_supported=false`; `tier2+august_holdout` -> HTTP 400 |
| 17 | `GET` | `/api/v1/forecasting/historical/summary` | `tier`, `period` | `HistoricalForecastSummaryResponse` | No | `final_model_evaluation_metrics.csv`, `random_forest_champion_config.json` | `rows_evaluated` (common keys) vs `total_prediction_records` distinguished |
