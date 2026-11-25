# AI_RouteRanker — Milestone 8 Stage 2: Data Inventory

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Milestone:** 8 — Backend API Integration (Stage 2 Planning)  
**Date:** 2026-11-25T18:38:00+05:30  

---

## 1. DuckDB Analytical Database (`data/processed/ai_routeranker.duckdb`)

- **Size:** `1,007,169,536` bytes | **SHA-256:** `ec0fd3626c6734fa2f96d6202a6d4966ae193598cc6e1ca84a828c295eee4209`
- **Schema:** `analytical` (all 16 tables; 0 secondary indexes)

| Table (`analytical.*`) | Rows | Key Columns | Date Coverage / Notes |
| :--- | :---: | :--- | :--- |
| `daily_ridership` | 1,124,170 | `route`, `date`, `daytype`, `rides`, `day_of_week`, `is_weekend`, `matched_snapshot_id`, `in_gtfs_coverage` | `2001-01-01` to `2026-08-31`; 188 routes; 3 daytypes (`W`,`A`,`U`); 0 null rides |
| `cta_ridership_clean` | 1,124,170 | `route`, `date`, `daytype`, `daytype_label`, `rides` | `2001-01-01` to `2026-08-31`; 188 routes |
| `gtfs_routes` / `gtfs_route_dim` | 1,052 | `snapshot_id`, `route_id`, `route_short_name`, `route_long_name`, `route_type` | Across 8 GTFS snapshots |
| `gtfs_stops` | 89,250 | `snapshot_id`, `stop_id`, `stop_name`, `stop_lat`, `stop_lon` | Across 8 GTFS snapshots |
| `gtfs_trips` | 627,416 | `snapshot_id`, `route_id`, `service_id`, `trip_id`, `direction_id`, `shape_id` | Across 8 GTFS snapshots |
| `gtfs_shapes` | 8,927,521 | `snapshot_id`, `shape_id`, `shape_pt_lat`, `shape_pt_lon`, `shape_pt_sequence` | Heavy table — do not load in Stage 2 |
| `gtfs_stop_times` | 38,238,809 | `snapshot_id`, `trip_id`, `stop_id`, `stop_sequence`, `arrival_seconds` | Heavy table — do not load in Stage 2 |
| `historical_schedule_match` | 28,798 | `snapshot_id`, `date`, `ridership_route`, `gtfs_route_id`, `rides`, `scheduled_trips_count` | Tier 2 matched schedule-ridership era |

---

## 2. Phase 6.1 Spatial Hubs & Clustering Artifacts (`artifacts/clustering/`)

| Artifact | Format | Rows $\times$ Cols | Size (B) | SHA-256 | Notes |
| :--- | :---: | :---: | :---: | :--- | :--- |
| `transit_hub_rankings.parquet` | Parquet | $10,583 \times 14$ | 508,646 | `20e116891376696370c38c2dd919d8d59c95b981fb493270b29763adb2260aa7` | Includes `stop_lat`/`stop_lon` (0 nulls), `score_config_a/b/c`, `rank_config_a/b/c` |
| `top100_hubs_config_a.csv` | CSV | $100 \times 8$ | 9,447 | `201682c6587678e2ef05fb6635e7ac7f16c1a2ed8c0f7d08aaf17671a9d1bc03` | Lacks lat/lon; use `transit_hub_rankings.parquet` (`rank_config_a <= 100`) for map coords |
| `spatial_dbscan_assignments.parquet` | Parquet | $11,020 \times 7$ | 571,207 | `3c7d40bcca545e142a69afd8b084166a372069a3f645360f76812fcdf9bab674` | `stop_id`, `stop_lat`, `stop_lon`, `proj_x`, `proj_y`, `dbscan_cluster` |
| `stop_level_feature_master.parquet` | Parquet | $11,020 \times 59$ | 1,881,542 | `1c78779eaa99a9d72e729efd1a6127670df2336d663065056cabbfdf1dbd32b5` | Stop eligibility flags, headways, KMeans `k3..k8`, `dist_to_center_km` |
| `peripheral_and_noise_stops.parquet` | Parquet | $18 \times 10$ | 7,980 | `1b9ec0cbac8bbbe88dccac368c439e10aef9c443f1321d2605ea345473f3e751` | 18 peripheral/noise stops |
| `phase6_1_stage2_metadata.json` | JSON | Object | 2,786 | `4b4cd002a309538c0fe03eb7bd5e924cba5f00632198b57f15878085eb42f67f` | DBSCAN/KMeans cluster counts and distortion metrics |

---

## 3. Phase 6.2 & 6.3 Corridor Topology Artifacts

| Artifact | Format | Rows $\times$ Cols | Size (B) | SHA-256 |
| :--- | :---: | :---: | :---: | :--- |
| `artifacts/route_clustering/corridor_cluster_assignments.parquet` | Parquet | $261 \times 25$ | 21,471 | `7cd435ab1a6bd3e81cc0ebc2f3214723a8602b8240faa9a5ae882edd9d8625af` |
| `artifacts/route_clustering/buffer_overlap_similarity_matrix.parquet` | Parquet | $261 \times 261$ | 317,540 | `bbf8a4371a5cca857f3a511b5aade91a4ac0792d1e27874c46f4d6ad09a190e4` |
| `artifacts/route_clustering/route_direction_jaccard_matrix.parquet` | Parquet | $261 \times 261$ | 191,412 | `35a15c483a8e0e16f6c70aef698d9793b07b3aea8d12fdcdf283c7c3cc0d1b3e` |
| `artifacts/route_clustering/shared_consecutive_stop_sequences.parquet` | Parquet | $950 \times 7$ | 41,983 | `dd7c031a0d4f1705065ec2226f79224083a60c4667b2aa38d4508fe7aba4e57f` |
| `artifacts/route_clustering/route_direction_geometries_metadata.parquet` | Parquet | $261 \times 11$ | 19,105 | `e1089cc02e26045016b10bb7f9c3d16ba98a9c7a908275eee0aea8d5d4411d0c` |
| `artifacts/route_clustering/route_level_operational_features.parquet` | Parquet | $133 \times 11$ | 14,801 | `44d1f0adb08719b8ca93c76dfbdaddf07c5ce53865afb8132188e60ed1749e95` |
| `artifacts/ranking_features/route_direction_connectivity_matrix.parquet` | Parquet | $261 \times 5$ | 6,957 | `a13f84ea65404bb1fcd3ea856755a037f16f85a2c27498393d1f3adeb4d5b1cc` |

---

## 4. Phase 3 / Milestone 5 Forecasting Artifacts (`artifacts/random_forest/` & `reports/modeling/random_forest/`)

| Artifact | Format | Rows $\times$ Cols | Date Range | SHA-256 |
| :--- | :---: | :---: | :--- | :--- |
| `tier1_august_predictions_tuned.parquet` | Parquet | $3,566 \times 7$ | `2026-08-01` to `2026-08-31` (128 routes) | `33c59e2e4438475dea175fbd39ede81e930eb953451fa35683a7c1fad5281e06` |
| `tier1_test_predictions_tuned.parquet` | Parquet | $28,798 \times 7$ | `2025-11-23` to `2026-07-31` (128 routes) | `3d1a70b6d447544eb4d3f862a1fd9bcb490f28b2a8725e93ab1e76187402c9a2` |
| `tier1_val_predictions_tuned.parquet` | Parquet | $37,786 \times 6$ | `2025-01-01` to `2025-11-22` (129 routes) | `4214b9140711c2f1901acb2252b0d90ee25fe095bd240acc65ab4af2a5879f3e` |
| `tier2_test_predictions_tuned.parquet` | Parquet | $7,293 \times 7$ | `2026-05-30` to `2026-07-31` (127 routes) | `4b6825dedc8d601c831e4483e64ee896dc952fca71ff798dd007bc31427e72fb` |
| `tier2_val_predictions_tuned.parquet` | Parquet | $4,117 \times 6$ | `2026-04-24` to `2026-05-29` (127 routes) | `f0f0bb8f4c86892b998e5cf30f9bb3feeaaaf7dd4873800133e3fd3cd5c2981e` |
| `final_model_evaluation_metrics.csv` | CSV | $3 \times 21$ | Tier 1 Test, Tier 1 Aug Holdout, Tier 2 Test | N/A (`reports/modeling/random_forest/`) |
