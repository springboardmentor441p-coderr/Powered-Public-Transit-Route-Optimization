# AI_RouteRanker — Milestone 8 Stage 2B: Implementation Report

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Milestone:** 8 — Module 6 Backend API Integration  
**Stage:** 2B — Spatial Hub, Stop, and DBSCAN Cluster APIs  
**Date:** 2026-11-25T19:03:00+05:30  
**Status:** COMPLETE & VERIFIED (Stage 2C Not Started)  

---

## 1. Executive Summary

Stage 2B implemented read-only spatial hub ranking, stop-level DBSCAN cluster, bounding-box viewport, and clustering summary APIs backed by the canonical Phase 6.1 artifacts in `artifacts/clustering/`.

---

## 2. Implemented Components

- **`backend/app/core/config.py`**: Added `CLUSTERING_DIR`, `TRANSIT_HUB_RANKINGS_PATH`, `DBSCAN_ASSIGNMENTS_PATH`, `PHASE6_1_METADATA_PATH`, and `TOP100_HUBS_CONFIG_A_PATH`.
- **`backend/app/repositories/spatial_repository.py` (`SpatialRepository`)**:
  - Reads `transit_hub_rankings.parquet` (10,583 rows $\times$ 14 cols), `spatial_dbscan_assignments.parquet` (11,020 rows $\times$ 7 cols, column-pruned to 5 cols), and `phase6_1_stage2_metadata.json`.
  - Uses `threading.Lock` double-checked lazy caching, column validation, read-only NumPy array freezing (`flags.writeable = False`), and safe `503` exception mapping.
  - Builds a cached left-join view (`get_spatial_stops_with_clusters()`) preserving all 11,020 stops, including 18 DBSCAN noise points (`dbscan_cluster == -1`) and 437 stops ineligible for hub ranking.
- **`backend/app/schemas/spatial.py`**:
  - `CoordinatePair` (Leaflet-compatible `lat`, `lon`, `coordinates_available`), `BoundingBoxMeta`, `HubRankingItem`, `SpatialStopHubItem`, `TopHubsResponse`, `SpatialHubsListResponse`, `ClusterSummaryResponse`, `SpatialMethodologyMeta`.
  - Explicitly documents `attributed_demand_proxy` as route-level ridership attributed to stops by visit share, not actual stop-level APC/turnstile boarding counts.
- **`backend/app/services/spatial_service.py` (`SpatialService`)**:
  - `get_top_hubs(config, limit, offset)`: Deterministic sort by `(rank_config_{cfg}, stop_id)` `.head(100)` across configs `a`, `b`, `c`.
  - `list_spatial_hubs(...)`: Supports `config`, `min_routes`, `dbscan_cluster` (`-1`..`116`), `eligible_only`, bounding box (`min_lat`, `min_lon`, `max_lat`, `max_lon`), deterministic sorting, and bounded pagination (default `25`, max `150`).
  - `get_cluster_summary()`: Serves Phase 6.1 DBSCAN (`117` clusters, `18` noise stops, `7` chained clusters) and KMeans (`10,583` eligible stops) metadata.
- **`backend/app/api/v1/spatial.py`**, **`deps.py`**, **`router.py`**:
  - Exposed `GET /api/v1/spatial/hubs/top`, `GET /api/v1/spatial/hubs`, and `GET /api/v1/spatial/clusters/summary`.

---

## 3. Known Limitations

- `top100_hubs_config_a.csv` omits `stop_lat`/`stop_lon`; `/spatial/hubs/top` therefore reads from `transit_hub_rankings.parquet` (sorted deterministically `.head(100)`) so every hub includes Leaflet coordinates.
- `attributed_demand_proxy` is a route-level visit-share proxy and must not be interpreted as turnstile or APC stop boardings.
