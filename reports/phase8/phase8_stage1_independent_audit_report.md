# AI_RouteRanker — Milestone 8 Stage 1: Independent Read-Only Technical Audit Report

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Scope:** Milestone 8, Stage 1 — Core Backend API Implementation  
**Audit Type:** Strictly Read-Only Technical, Security, Performance & Artifact Integrity Audit  
**Audit Date:** 2026-11-25T18:32:00+05:30  
**Final Audit Verdict:** **PASS WITH WARNINGS** (Ready for Stage 2; 0 Critical, 0 High, 0 Medium, 2 Low, 2 Informational)  

---

## 1. Executive Summary

An independent, strictly read-only technical audit of Milestone 8 Stage 1 (`Core Backend API Implementation`) was conducted by inspecting all backend source files, Pydantic schemas, repository/service modules, unit tests, Stage 1 reports, and canonical Phase 6.3 / Phase 7 artifacts.

All 7 Stage 1 `/api/v1` endpoints, along with the preserved `/` and `/api/health` endpoints, operate deterministically, satisfy strict Pydantic v2 response contracts, preserve track isolation (`BUS_PRIORITY`, `RAIL_PRIORITY`, `UNIFIED_SUPPLY`), enforce read-only artifact access, and serialize missing values (`NaN`/`pd.NA`) cleanly as JSON `null`.

Independent test reproduction confirmed **15 / 15 backend tests PASS** ($0.954\text{s}$) and **205 / 205 project analytics tests PASS** ($8.808\text{s}$). Measured process RSS remained **128.33 MB** after warming all caches and exercising all endpoints, well within the 8 GB laptop memory budget. Zero source files, frontend files, databases, or analytical artifacts were modified during this audit.

Two minor non-blocking Low findings (per-row `copy.deepcopy` overhead on paginated ranking responses and unlocked lazy cache initialization) and two Informational notes (artifact inventory count explanation and ASGI `%2F` path decoding behavior) are documented below.

---

## 2. Files Inspected

### 2.1 Backend Application & Tests
- `backend/app/main.py`
- `backend/app/core/config.py`
- `backend/app/core/exceptions.py`
- `backend/app/database/session.py`
- `backend/app/api/endpoints.py`
- `backend/app/api/v1/__init__.py`, `router.py`, `deps.py`, `routes.py`, `rankings.py`
- `backend/app/schemas/__init__.py`, `common.py`, `health.py`, `route.py`, `ranking.py`
- `backend/app/services/__init__.py`, `route_service.py`, `ranking_service.py`
- `backend/app/repositories/__init__.py`, `parquet_repository.py`, `json_repository.py`
- `backend/tests/test_health.py`, `backend/tests/test_api_v1.py`

### 2.2 Stage 1 Reports & Protected Trees
- `reports/phase8/phase8_stage1_implementation_report.md`
- `reports/phase8/phase8_stage1_test_report.md`
- `reports/phase8/phase8_stage1_audit_checklist.md`
- `frontend/src/` (confirmed untouched: `App.tsx`, `App.css`, `index.css`, `main.tsx`)

---

## 3. Endpoint-by-Endpoint Audit

| Endpoint | HTTP | Schema Match | Pagination / Bounds | Canonical Reconciliation | Missing / Error Handling | Status |
| :--- | :---: | :---: | :---: | :--- | :--- | :---: |
| `GET /` | 200 | Dict | N/A | Preserved legacy welcome | N/A | **PASS** |
| `GET /api/health` | 200 | `HealthCheckResponse` | N/A | Preserved legacy health | N/A | **PASS** |
| `GET /api/v1/routes` | 200 | `RouteListResponse` | Default 25, max 150 | 133 total (125 bus, 8 rail) | 400 on invalid sort/mode; 422 on limit > 150 | **PASS** |
| `GET /api/v1/routes/{route_id}` | 200 | `RouteDetailResponse` | Single item | Matches feature master | 404 on unknown route; `demand_metrics_available=False` for rail | **PASS** |
| `GET /api/v1/rankings/bus` | 200 | `RankingListResponse` | Default 25, max 150 | 125 routes match Parquet ($<10^{-12}$) | Routes 10, 130, N5 flagged `is_headway_missing=True`, coverage `0.90` | **PASS** |
| `GET /api/v1/rankings/rail` | 200 | `RankingListResponse` | Returns all 8 lines | 8 lines match Parquet ($<10^{-12}$) | `demand_pressure=0.0`; non-evaluated contributions `null` | **PASS** |
| `GET /api/v1/rankings/unified` | 200 | `RankingListResponse` | Default 25, max 150 | 133 routes match Parquet ($<10^{-12}$) | Red #1 (`0.8458`), Route 79 #2 (`0.8417`) | **PASS** |
| `GET /api/v1/rankings/routes/{id}/explanation` | 200 | `RouteExplanationResponse` | Single item | Matches JSON index; `orig_w_sum=1.0`, `eff_w_sum=1.0` | 404 on unknown route; 400 on invalid track | **PASS** |
| `GET /api/v1/rankings/sensitivity` | 200 | `SensitivityListResponse` | Returns 60 (28/16/16) | Deterministic sort `["track", "target_criterion", "delta"]` | 400 on invalid track | **PASS** |

---

## 4. Repository and Security Findings

- **Read-Only Access:** `ParquetRepository` and `JSONRepository` open files strictly for reading (`pd.read_parquet(..., columns=...)`, `open(..., "r")`). No write paths exist.
- **Column Pruning & Schema Validation:** `ParquetRepository` passes explicit `columns=required_columns` to `pd.read_parquet` and validates all required columns are present.
- **Immutability:** Underlying NumPy arrays in cached DataFrames are marked `flags.writeable = False`, raising `ValueError` on mutation attempts.
- **Missing & Corrupt Artifact Handling:** Missing or corrupt Parquet/JSON files raise `ArtifactUnavailableError` (HTTP 503) with sanitized messages (`ARTIFACT_MISSING`, `ARTIFACT_CORRUPT`, `ARTIFACT_SCHEMA_INVALID`) without leaking local paths or tracebacks.
- **Input Validation & Path Traversal:** `route_id` is validated against `^[A-Za-z0-9_-]{1,16}$`. Requests with `.` or `..` return HTTP 400 `INVALID_ROUTE_ID`; URL-encoded slashes (`..%2Fsecret`) are rejected with HTTP 404 at Starlette routing before reaching filesystem or repository logic.
- **NaN/Inf Serialization:** `to_optional_float`, `to_optional_int`, and `to_optional_str` preserve `0.0`/`0` while converting `NaN`, `Inf`, `pd.NA`, and `"nan"` to `None` (JSON `null`).
- **No Runtime Recalculation:** Ranking endpoints serve precomputed scores, ranks, pillars, and contributions directly from `route_rankings_master.parquet` and `route_ranking_explanations.json`.

---

## 5. Artifact Hash Comparison & Inventory Explanation

### 5.1 Explanation of Reported 5 vs Actual 7 Phase 6.3 / Phase 7 Artifacts
`phase8_stage1_test_report.md` Section 3 reported hashes for **5** Phase 6.3/7 artifacts—specifically the 4 artifacts read by Stage 1 repositories plus `phase7_metadata.json`. Inspection of `artifacts/ranking_features/` and `artifacts/ranking_results/` confirms **7 total files** exist on disk (adding `route_direction_connectivity_matrix.parquet` and `phase6_3_metadata.json`). All 7 files were independently hashed and verified unchanged:

| Artifact Path | Size (Bytes) | Independently Observed SHA-256 | Baseline Match |
| :--- | :---: | :--- | :---: |
| `artifacts/ranking_features/route_ranker_feature_master.parquet` | 62,921 | `c26aa49a408b1d07c6a0e09f2b11879cf623a54da1c3625f1342b51d8937df85` | **MATCH** |
| `artifacts/ranking_features/route_direction_connectivity_matrix.parquet` | 6,957 | `a13f84ea65404bb1fcd3ea856755a037f16f85a2c27498393d1f3adeb4d5b1cc` | **INTACT** |
| `artifacts/ranking_features/phase6_3_metadata.json` | 3,245 | `0ac55cefffb0aa3e8f3f9530f8fe9ceb5a3edd4931367b9dd502b77cf3a24d12` | **INTACT** |
| `artifacts/ranking_results/route_rankings_master.parquet` | 103,565 | `c440671d0b3888683969cb5fc11ccf7b581128a7296069019f76202b64f0093b` | **MATCH** |
| `artifacts/ranking_results/route_ranking_explanations.json` | 797,352 | `56c29ef9c77b7517e8cb621a207600aa576148aef015a35a364da029a74a24b2` | **MATCH** |
| `artifacts/ranking_results/ranking_sensitivity_analysis.parquet` | 7,522 | `fb41bcdf1e18da7978ae1666535d5868a92467143bd3d08b7ee5d71ef5d6790c` | **MATCH** |
| `artifacts/ranking_results/phase7_metadata.json` | 1,963 | `f29799139e4a861ea4f8b3679f96fa3e022436904b3c52fc8b7fc5a1cfd9ceca` | **MATCH** |

Additionally, all **23 / 23** Stage 1 protected baseline assets (`data/processed/features/model_ready_features.parquet`, `data/processed/ai_routeranker.duckdb`, `artifacts/random_forest/*`, `analytics/clustering/*`, `artifacts/clustering/*`, `tests/test_clustering.py`, `route_ranker_feature_master.parquet`) were independently re-hashed and matched 100% bit-for-bit.

---

## 6. Independent Test Execution Results

| Suite | Exact Command | Collected / Executed | Result | Duration |
| :--- | :--- | :---: | :---: | :---: |
| **Backend Tests** | `python -m unittest discover -s backend/tests -v` | 15 | **15 PASS, 0 FAIL** | $0.954\text{s}$ |
| **Project Analytics** | `python -m unittest discover tests` | 205 | **205 PASS, 0 FAIL** | $8.808\text{s}$ |

All reported test counts and results were reproduced identically during this audit with zero warnings or errors.

---

## 7. Performance and Memory Measurements (Measured)

All measurements were collected directly via Windows `GetProcessMemoryInfo`, `tracemalloc`, and `time.perf_counter()` (5-run warm-cache average) without loading the 1.12M-row DuckDB ridership table:

- **Startup RSS (after importing `app.main`):** `101.93 MB`
- **Repository Cache Warm Time (all 4 Stage 1 artifacts):** `228.16 ms`
- **Traced Cache Heap Footprint:** `2.641 MB` current (`3.608 MB` peak)
- **Process RSS after Cache Warm:** `121.01 MB`
- **Process RSS after All Endpoint Calls:** `128.33 MB` (well within `< 350 MB` budget)

| Endpoint | Response Size | 5-Run Avg Latency |
| :--- | :---: | :---: |
| `GET /` | 0.10 KB | 44.16 ms |
| `GET /api/health` | 0.18 KB | 13.46 ms |
| `GET /api/v1/routes` (default 25) | 7.89 KB | 39.80 ms |
| `GET /api/v1/routes?limit=150` | 40.40 KB | 72.12 ms |
| `GET /api/v1/routes/151` | 0.94 KB | 22.63 ms |
| `GET /api/v1/rankings/bus` (default 25) | 34.22 KB | 59.32 ms |
| `GET /api/v1/rankings/bus?limit=125` | 169.93 KB | 150.17 ms |
| `GET /api/v1/rankings/rail` | 9.34 KB | 35.67 ms |
| `GET /api/v1/rankings/unified?limit=133` | 154.17 KB | 155.77 ms |
| `GET /api/v1/rankings/routes/10/explanation` | 2.63 KB | 19.52 ms |
| `GET /api/v1/rankings/sensitivity` | 14.54 KB | 45.10 ms |

---

## 8. Findings & Discrepancies

- **Critical / High / Medium:** **None (0 findings).**
- **Low Finding L-01 (`backend/app/services/ranking_service.py` — `_build_ranking_item`):** Calling `self._json_repo.get_explanation(route_id, track)` invokes `copy.deepcopy(item)` on every row of a paginated ranking response (e.g., 125 deep copies when `limit=125`), driving `limit=125`/`133` latencies to ~150–156 ms. *Recommendation:* Add a lightweight read-only helper (e.g. `get_weight_metadata`) in `JSONRepository` that returns only the copied weight dicts/missing list without deep-copying the full narrative/driver payload.
- **Low Finding L-02 (`backend/app/repositories/parquet_repository.py` & `json_repository.py`):** Lazy cache population (`self._cache` and `self._index`) is not guarded by a `threading.Lock`. Under simultaneous cold-start requests in multi-threaded workers, two threads could redundantly load the same file before populating the cache (benign idempotent race). *Recommendation:* Wrap `_load_parquet` / `_load_index` cache population in a `threading.Lock`.
- **Informational I-01 (Discrepancy with `phase8_stage1_test_report.md` Section 3):** The test report lists 5 Phase 6.3/7 artifacts while 7 exist on disk (`route_direction_connectivity_matrix.parquet` and `phase6_3_metadata.json` were omitted from that summary list). Both omitted files were verified intact above.
- **Informational I-02 (Scope & Compatibility):** Confirmed `/`, `/api/health`, React `frontend/src/` files, DuckDB, and PostgreSQL (inactive) remain untouched, and no Stage 2 endpoints were added.

---

## 9. Final Verdict

**PASS WITH WARNINGS** — Milestone 8 Stage 1 is technically sound, secure, memory-efficient, and verified against all canonical artifacts and tests. Stage 2 implementation may proceed without blocking issues; addressing Low Findings L-01 and L-02 is recommended as minor cleanup during Stage 2.
