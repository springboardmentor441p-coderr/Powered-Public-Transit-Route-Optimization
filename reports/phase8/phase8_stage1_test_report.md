# AI_RouteRanker — Milestone 8 Stage 1: Test & Verification Report

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Milestone:** 8 — Module 6 Backend API Integration  
**Stage:** 1 — Core Framework, Repositories, Schemas and Ranking APIs  
**Date:** 2026-11-25T18:27:00+05:30  
**Overall Test Verdict:** 100% PASS (15 / 15 Backend Tests, 205 / 205 Project Tests)  

---

## 1. Test Execution Summary

| Test Suite | Command | Tests Executed | Passed | Failed | Duration |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Backend API & Unit Tests** | `python -m unittest discover -s backend/tests -v` | 15 | **15** | 0 | $0.898\text{s}$ |
| **Core Analytics Regression** | `python -m unittest discover tests` | 205 | **205** | 0 | $12.223\text{s}$ |

---

## 2. Backend Test Coverage Breakdown (`backend/tests/test_api_v1.py` & `test_health.py`)

### 2.1 Canonical Artifact Integration Tests (`TestCanonicalAPIv1`)
1. `test_routes_list_pagination_and_filtering`: Verified `total=133`, `mode=rail` returns 8 routes, `mode=bus` returns 125 routes, search query `"Sheridan"` returns Route 151.
2. `test_route_detail_bus_rail_and_missing_headway`: Verified Bus Route 151 (`demand_metrics_available=True`), Rail Route Red (`demand_metrics_available=False`, null demand), and Route 10 (`am_headway_min=null`).
3. `test_rankings_bus_track1_canonical`: Verified 125 bus routes, Route 151 at rank #1 (`overall_score=0.636319`), and Routes 10, 130, N5 with `is_headway_missing=True` and `valid_weight_coverage=0.9`.
4. `test_rankings_rail_track2_canonical`: Verified 8 rail lines, Red Line at #1, and `demand_pressure=0.0`.
5. `test_rankings_unified_track3_canonical`: Verified 133 routes, Red Line at #1, Route 79 at #2, and `mode=bus` filter returning 125 routes.
6. `test_route_explanation_endpoint`: Verified narrative, driver contributions, Route 10 missing-headway effective weights (`am_headway_min_norm` weight `0.0`), and explicit `track=UNIFIED_SUPPLY` override.
7. `test_sensitivity_endpoint`: Verified all 60 scenarios and `track=BUS_PRIORITY` filtering (28 scenarios).
8. `test_invalid_parameters_and_unknown_routes`: Verified HTTP 404 (`ROUTE_NOT_FOUND`, `EXPLANATION_NOT_FOUND`), HTTP 400 (`INVALID_SORT_FIELD`, `INVALID_RANK_RANGE`), HTTP 422 (`VALIDATION_ERROR` for `limit=500`), and path traversal rejection.
9. `test_deterministic_sorting`: Verified repeated queries return identical deterministic route orderings.
10. `test_dataframe_immutability`: Verified cached DataFrames in `ParquetRepository` raise `ValueError` on in-place array mutation attempts.

### 2.2 Synthetic & Failure Mode Tests (`TestSyntheticAndFailureModes`)
11. `test_missing_artifact_returns_503_safely`: Verified missing Parquet/JSON files return HTTP 503 (`ARTIFACT_MISSING`) without leaking temp directory paths.
12. `test_corrupt_artifact_returns_503_safely`: Verified invalid Parquet/JSON files return HTTP 503 (`ARTIFACT_CORRUPT`) without leaking tracebacks.
13. `test_synthetic_fixture_nan_to_null_and_ranking`: Verified controlled synthetic Parquet + JSON fixtures serialize `NaN` values cleanly as JSON `null`.

### 2.3 Legacy Regression Tests (`backend/tests/test_health.py`)
14. `test_health_check_endpoint`: Verified `GET /api/health` returns HTTP 200 and `status="ok"`.
15. `test_root_endpoint`: Verified `GET /` returns HTTP 200 and health link.

---

## 3. Cryptographic Artifact Integrity Verification

All 5 Phase 6.3 and Phase 7 canonical artifacts were verified via SHA-256 after all tests completed:
- `artifacts/ranking_features/route_ranker_feature_master.parquet`: `c26aa49a408b1d07c6a0e09f2b11879cf623a54da1c3625f1342b51d8937df85` (**MATCH**)
- `artifacts/ranking_results/route_rankings_master.parquet`: `c440671d0b3888683969cb5fc11ccf7b581128a7296069019f76202b64f0093b` (**MATCH**)
- `artifacts/ranking_results/route_ranking_explanations.json`: `56c29ef9c77b7517e8cb621a207600aa576148aef015a35a364da029a74a24b2` (**MATCH**)
- `artifacts/ranking_results/ranking_sensitivity_analysis.parquet`: `fb41bcdf1e18da7978ae1666535d5868a92467143bd3d08b7ee5d71ef5d6790c` (**MATCH**)
- `artifacts/ranking_results/phase7_metadata.json`: `f29799139e4a861ea4f8b3679f96fa3e022436904b3c52fc8b7fc5a1cfd9ceca` (**MATCH**)
