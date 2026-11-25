# AI_RouteRanker — Milestone 8 Stage 2B: Independent Read-Only Audit Report

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Scope:** Milestone 8 Stage 2B — Spatial Hub, Stop and DBSCAN APIs  
**Audit Date:** 2026-11-25T19:05:00+05:30  
**Final Audit Verdict:** **PASS WITH WARNINGS** (0 Critical, 0 High, 0 Medium, 1 Low, 1 Informational)  

---

## 1. Executive Verdict

An independent, strictly read-only audit of **Milestone 8 Stage 2B** (`GET /api/v1/spatial/hubs/top`, `GET /api/v1/spatial/hubs`, `GET /api/v1/spatial/clusters/summary`) was completed.

The implementation is **secure, read-only, thread-safe, memory-efficient, and faithful to Phase 6.1 canonical artifacts**. All **35 / 35 backend tests** and **205 / 205 project analytics tests** reproduced cleanly with zero failures, and all Phase 6.1, Phase 6.2, Phase 6.3, Phase 7, and DuckDB hashes remain 100% bit-for-bit unchanged.

A **PASS WITH WARNINGS** verdict is issued due to **one Low finding (L-01)** discovered during independent top-100 reconciliation: a 2-way tie at `rank_config_a == 100` (`score_config_a = 0.388844`) causes lexicographical `stop_id` tie-breaking in `/spatial/hubs/top?config=a` to select stop `17046` (*Adams & Clark*) as the 100th item whereas `top100_hubs_config_a.csv` contains stop `4732` (*Adams & State*).

---

## 2. Files Inspected

- `backend/app/repositories/spatial_repository.py`
- `backend/app/services/spatial_service.py`
- `backend/app/schemas/spatial.py`
- `backend/app/api/v1/spatial.py`, `deps.py`, `router.py`
- `backend/app/core/config.py`, `exceptions.py`
- `backend/tests/test_spatial_api.py`
- `reports/phase8/phase8_stage2b_implementation_report.md`, `phase8_stage2b_test_report.md`, `phase8_stage2b_audit_checklist.md`

---

## 3. Canonical Artifact Verification

- **`transit_hub_rankings.parquet`**: `10,583` rows $\times$ `14` columns, `0` nulls; includes configs `a`, `b`, `c` and valid Chicago coordinates. `rank_config_a <= 100` contains `101` rows due to a 2-way tie at rank 100 (`17046` and `4732`, both `score_config_a = 0.388844`).
- **`spatial_dbscan_assignments.parquet`**: `11,020` rows $\times$ `7` columns, `0` nulls; `117` clusters (`0..116`) and `18` noise stops (`-1`).
- **`top100_hubs_config_a.csv`**: `100` rows $\times$ `8` columns (excludes `stop_lat`/`stop_lon`; 100th row is stop `4732` *Adams & State*).
- **`phase6_1_stage2_metadata.json`**: Verified `boarding_stops_input_count=11020`, `dbscan_cluster_count=117`, `dbscan_noise_stop_count=18`, `dbscan_chained_cluster_count=7`, `kmeans_eligible_stops_count=10583`.

---

## 4. Endpoint-by-Endpoint Findings

- **`GET /api/v1/spatial/hubs/top`**: Supports `config` (`a`/`b`/`c`), `limit` (`1..100`, default `25`), `offset`. Returns Leaflet `CoordinatePair` and explicit `attributed_demand_proxy` documentation (not stop-level APC boardings). See **L-01** for the rank-100 tie-break difference against `top100_hubs_config_a.csv`.
- **`GET /api/v1/spatial/hubs`**: Serves all `11,020` stops via left-join of DBSCAN assignments and hub rankings. Supports `eligible_only`, `min_routes`, `dbscan_cluster`, bounding box, deterministic sorting, and pagination (default `25`, max `150`). Missing coordinates serialize as `null` with `coordinates_available=False` (never fabricated).
- **`GET /api/v1/spatial/clusters/summary`**: Returns exact Phase 6.1 DBSCAN and KMeans counts and sensitivity metrics.

---

## 5. Coordinate & Bounding-Box Validation

- Coordinates validated within `lat in [-90, 90]`, `lon in [-180, 180]`.
- Exact-boundary bounding-box test on rank #1 Stop `1106` (`min_lat=max_lat=41.88342185`, `min_lon=max_lon=-87.62459375`) returned `['1106']` (**inclusive** `>=` / `<=` confirmed).
- Partial, inverted (`min > max`), and out-of-range bounding boxes all returned HTTP 400 `INVALID_BBOX`.

---

## 6. DBSCAN Cluster & Noise-Point Verification

- Filtering `dbscan_cluster=-1` returned all `18` noise stops with `is_noise_point=True`.
- The `437` stops absent from `transit_hub_rankings.parquet` report `hub_ranking_eligible=False`, `rank=null`, `hub_score=null`.

---

## 7. Repository & Security Findings

- `SpatialRepository` opens Parquet/JSON strictly read-only, prunes columns, freezes cached NumPy arrays (`flags.writeable = False`), uses `threading.Lock` double-checked caching, and maps missing/corrupt files to HTTP 503 without exposing filesystem paths.
- Zero ranking or clustering recalculation occurs during API requests.

---

## 8. Independent Test Reproduction

| Suite | Command | Collected | Result | Duration |
| :--- | :--- | :---: | :---: | :---: |
| **Backend Tests** | `python -m unittest discover -s backend/tests -v` | 35 | **35 PASS, 0 FAIL** | $1.848\text{s}$ |
| **Project Analytics** | `python -m unittest discover tests` | 205 | **205 PASS, 0 FAIL** | $8.444\text{s}$ |

Stage 1 (`/`, `/api/health`, `/api/v1/routes`, `/api/v1/rankings/bus`) and Stage 2A (`/api/v1/ridership/routes/151/timeseries`) all returned `200 OK`.

---

## 9. Performance & Memory Measurements (Measured)

- **Cold `/api/v1/spatial/hubs/top` (100 items):** `107.75 ms`
- **Cold `/api/v1/spatial/hubs` (DBSCAN merge):** `74.00 ms`
- **Warm `/api/v1/spatial/hubs/top` (25 items, 7.89 KB):** `avg = 17.27 ms`
- **Warm `/api/v1/spatial/hubs` (25 items, 9.37 KB):** `avg = 19.36 ms`
- **Warm `/api/v1/spatial/hubs` bbox (50 items, 18.33 KB):** `avg = 15.40 ms`
- **Warm `/api/v1/spatial/clusters/summary` (1.80 KB):** `avg = 6.58 ms`
- **10-Thread Concurrent Requests:** `10 / 10` returned `200 OK`.
- **Process Memory:** `RSS = 168.01 MB`, `Peak = 176.18 MB`.

---

## 10. Artifact Hash Comparison

| Artifact Path | Observed SHA-256 | Status |
| :--- | :--- | :---: |
| `artifacts/clustering/transit_hub_rankings.parquet` | `20e116891376696370c38c2dd919d8d59c95b981fb493270b29763adb2260aa7` | **MATCH** |
| `artifacts/clustering/spatial_dbscan_assignments.parquet` | `3c7d40bcca545e142a69afd8b084166a372069a3f645360f76812fcdf9bab674` | **MATCH** |
| `artifacts/clustering/phase6_1_stage2_metadata.json` | `4b4cd002a309538c0fe03eb7bd5e924cba5f00632198b57f15878085eb42f67f` | **MATCH** |
| `artifacts/clustering/top100_hubs_config_a.csv` | `201682c6587678e2ef05fb6635e7ac7f16c1a2ed8c0f7d08aaf17671a9d1bc03` | **MATCH** |
| `artifacts/route_clustering/corridor_cluster_assignments.parquet` | `7cd435ab1a6bd3e81cc0ebc2f3214723a8602b8240faa9a5ae882edd9d8625af` | **MATCH** |
| `artifacts/ranking_features/route_ranker_feature_master.parquet` | `c26aa49a408b1d07c6a0e09f2b11879cf623a54da1c3625f1342b51d8937df85` | **MATCH** |
| `artifacts/ranking_results/route_rankings_master.parquet` | `c440671d0b3888683969cb5fc11ccf7b581128a7296069019f76202b64f0093b` | **MATCH** |
| `data/processed/ai_routeranker.duckdb` | `ec0fd3626c6734fa2f96d6202a6d4966ae193598cc6e1ca84a828c295eee4209` | **MATCH** |

---

## 11. Findings Classification

- **Critical / High / Medium:** **None (0 findings).**
- **Low Finding L-01 (`backend/app/services/spatial_service.py` — `get_top_hubs`):** In `transit_hub_rankings.parquet`, stops `17046` (*Adams & Clark*) and `4732` (*Adams & State*) tie at `rank_config_a == 100` (`score_config_a = 0.388844`). Because `get_top_hubs` sorts by `[rank_col, "stop_id"]` and takes `.head(100)`, lexicographical string sorting selects `"17046"` whereas `top100_hubs_config_a.csv` contains `"4732"` as its 100th entry. *Recommendation:* Either document string `stop_id` tie-breaking for `/spatial/hubs/top` or return all `rank <= 100` tied entries / match `top100_hubs_config_a.csv` when `config == "a"`.
- **Informational I-01 (`frontend/` & Scope):** Confirmed zero frontend files modified, PostgreSQL inactive, and no Stage 2C/2D endpoints added.

---

## 12. Final Verdict

**PASS WITH WARNINGS** — Milestone 8 Stage 2B is verified, secure, and ready for Stage 2C.
