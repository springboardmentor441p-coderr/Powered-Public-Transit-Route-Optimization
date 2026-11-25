# AI_RouteRanker — Milestone 8 Stage 2C: Test & Performance Report

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Milestone:** 8 — Module 6 Backend API Integration  
**Stage:** 2C — Corridor Topology and Co-Routing APIs  
**Date:** 2026-11-25T19:13:00+05:30  
**Overall Test Verdict:** 100% PASS (42 / 42 Backend Tests, 205 / 205 Project Tests)  

---

## 1. Test Execution Summary

| Suite | Command | Collected / Executed | Result | Duration |
| :--- | :--- | :---: | :---: | :---: |
| **Backend Tests** | `python -m unittest discover -s backend/tests -v` | 42 (36 Stage 1/2A/2B + 6 Stage 2C) | **42 PASS, 0 FAIL** | $2.568\text{s}$ |
| **Project Analytics** | `python -m unittest discover tests` | 205 | **205 PASS, 0 FAIL** | $11.444\text{s}$ |

### Stage 2C Test Coverage (`backend/tests/test_corridor_api.py`)
1. `test_corridor_clusters_retrieval_and_filtering`: Verified `261` patterns, `buffer` vs `frechet`, `k=5`, `route_id=151`, and `mode=rail`.
2. `test_route_co_routing_distinct_metrics_and_sequences`: Verified Route `151` directional patterns (`dir_0`, `dir_1`) return distinct `geographic_buffer_overlap`, `stop_set_jaccard_similarity`, and `shared_consecutive_sequences`.
3. `test_invalid_params_and_unknown_route`: Verified HTTP 404 (`ROUTE_NOT_FOUND`) and 400/422 on invalid `k`, `cluster_type`, `direction_id`, `sort_by`, and `route_id`.
4. `test_corridor_immutability_and_concurrent_cold_start`: Verified frozen arrays raise `ValueError` on mutation and 10 barrier-synchronized threads initialize `261 x 261` matrices safely.
5. `test_synthetic_missing_and_zero_similarity_values`: Synthetic fixture verified `NaN` entries increment `missing_buffer_entries_count` without fabrication while `0.0` is preserved.
6. `test_missing_and_corrupt_corridor_artifacts_return_503`: Missing/corrupt artifacts returned HTTP 503 without path leakage.

---

## 2. Measured Performance & Memory Benchmarks

- **Cold `/api/v1/corridors/clusters`:** `154.42 ms`
- **Cold `/api/v1/corridors/routes/151/co-routing` (matrices + sequences):** `66.76 ms`
- **Warm `/api/v1/corridors/clusters` (25 items, 10.28 KB):** `avg = 22.62 ms`
- **Warm `/api/v1/corridors/clusters` (150 items, 57.42 KB):** `avg = 37.95 ms`
- **Warm `/api/v1/corridors/routes/151/co-routing` (12.63 KB):** `avg = 34.28 ms`
- **Warm `/api/v1/corridors/routes/Red/co-routing` (7.31 KB):** `avg = 21.82 ms`
- **Process Memory:** `RSS = 128.92 MB`, `Peak = 129.43 MB`.

---

## 3. Integrity Confirmation

All Phase 6.1, Phase 6.2 (`corridor_cluster_assignments.parquet`, `buffer_overlap_similarity_matrix.parquet`, `route_direction_jaccard_matrix.parquet`, `shared_consecutive_stop_sequences.parquet`, `route_direction_geometries_metadata.parquet`), Phase 6.3, Phase 7, and DuckDB SHA-256 hashes matched 100% bit-for-bit. Stage 2B tie-breaking correction remains intact. No frontend files modified; PostgreSQL inactive; no Stage 2D endpoints added.
