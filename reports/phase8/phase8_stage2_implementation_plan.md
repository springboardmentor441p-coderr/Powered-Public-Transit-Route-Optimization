# AI_RouteRanker — Milestone 8 Stage 2: Implementation Plan

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Milestone:** 8 — Backend API Integration  
**Stage:** 2 — Historical Analytics, Spatial Hubs, Corridor Topology and Forecasting APIs  
**Date:** 2026-11-25T18:38:00+05:30  

---

## 1. Recommended Implementation Sequence

1. **Pre-Stage 2A Hardening (Optional/Recommended):**
   - Resolve Stage 1 Audit Low Findings **L-01** (`JSONRepository.get_weight_metadata` to eliminate `copy.deepcopy` per ranking row) and **L-02** (`threading.Lock` on repository cache loading). Re-run all 15 Stage 1 tests to confirm zero behavior change.
2. **Stage 2A — DuckDB Repository & Historical Ridership API:**
   - Implement `backend/app/repositories/duckdb_repository.py` (`read_only=True`, `PRAGMA max_memory='256MB'`, `PRAGMA threads=2`, `threading.Lock`).
   - Implement `schemas/ridership.py`, `services/ridership_service.py`, and `api/v1/ridership.py` (`GET /api/v1/ridership/routes/{route_id}/timeseries`).
3. **Stage 2B — Spatial Hubs & Clustering APIs:**
   - Extend `ParquetRepository` (column-pruned readers for `transit_hub_rankings.parquet`, `spatial_dbscan_assignments.parquet`, `peripheral_and_noise_stops.parquet`) and `JSONRepository` (`phase6_1_stage2_metadata.json`).
   - Implement `schemas/spatial.py`, `services/spatial_service.py`, and `api/v1/spatial.py` (`/spatial/hubs/top`, `/spatial/hubs`, `/spatial/clusters/summary`).
4. **Stage 2C — Corridor Topology & Co-Routing APIs:**
   - Extend `ParquetRepository` for `corridor_cluster_assignments.parquet`, `buffer_overlap_similarity_matrix.parquet`, `route_direction_jaccard_matrix.parquet`, `shared_consecutive_stop_sequences.parquet`, and `route_direction_geometries_metadata.parquet`.
   - Implement `schemas/corridor.py`, `services/corridor_service.py`, and `api/v1/corridors.py` (`/corridors/clusters`, `/corridors/routes/{route_id}/co-routing`).
5. **Stage 2D — Honest Forecasting Evaluation APIs:**
   - Extend `ParquetRepository` for `tier1_august_predictions_tuned.parquet`, `tier1_test_predictions_tuned.parquet`, `tier2_test_predictions_tuned.parquet`, plus CSV/JSON readers for `final_model_evaluation_metrics.csv`.
   - Implement `schemas/forecasting.py`, `services/forecasting_service.py`, and `api/v1/forecasting.py` (`/forecasting/summary`, `/forecasting/routes/{route_id}`).
6. **Stage 2E — Integrated Tests, Performance Profiling & Independent Audit:**
   - Write comprehensive tests in `backend/tests/test_api_v1_stage2.py` (using synthetic DuckDB/Parquet fixtures for failure modes + canonical integration tests).
   - Measure RSS memory ($< 350\text{ MB}$ target) and endpoint latencies, verify all protected SHA-256 hashes, and run independent audit.

---

## 2. Memory, Safety & Dependency Constraints

- **Dependencies:** All required packages (`duckdb`, `pandas`, `pyarrow`, `fastapi`, `pydantic`) are already installed. No new dependencies or PostgreSQL activation required.
- **Memory Guardrails:** Never `SELECT *` from `daily_ridership` (1.12M rows) or load `gtfs_shapes` (8.9M rows) / `gtfs_stop_times` (38.2M rows). Always aggregate in DuckDB SQL (`GROUP BY`) with parameterized date bounds.
- **Path & Input Validation:** Reuse `settings.ROUTE_ID_PATTERN` regex (`^[A-Za-z0-9_-]{1,16}$`), validate `start_date <= end_date`, and never construct file paths from user input.

---

## 3. Risks & Mitigations

| Risk | Mitigation |
| :--- | :--- |
| Loading 1.12M-row `daily_ridership` into Pandas causes OOM | Execute `GROUP BY` and `WHERE` filtering inside DuckDB SQL (`read_only=True`, `max_memory='256MB'`); return bounded pages (`limit <= 150`). |
| `top100_hubs_config_a.csv` lacks `stop_lat`/`stop_lon` | Serve `/spatial/hubs/top` from `transit_hub_rankings.parquet` (which includes `stop_lat`, `stop_lon`, and `rank_config_a/b/c`). |
| Exposing holdout test metrics as future forecasts | Explicitly set `future_forecasting_supported: false` and `forecast_scope: "historical_evaluation_only"` in schemas and responses. |
| Rail routes missing from ridership & RF prediction files | Return structured `ridership_available: false` / `forecasting_supported: false` rather than fabricating `0` rides. |
