# AI_RouteRanker — Pre-Stage 2A: Backend Repository Hardening Report

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Milestone:** 8 — Backend API Integration  
**Scope:** Pre-Stage 2A Maintenance (Addressing Stage 1 Audit Findings L-01 & L-02)  
**Date:** 2026-11-25T18:48:00+05:30  
**Status:** COMPLETE & VERIFIED (Stage 2A Not Started)  

---

## 1. Executive Summary

Following the Milestone 8 Stage 1 independent audit, the two accepted low-priority findings (**L-01** and **L-02**) were resolved in a narrowly scoped maintenance pass prior to Stage 2A implementation. All public API response structures, canonical ranking outputs, health endpoints, and protected artifacts remain 100% preserved.

---

## 2. Code Changes & File Hashes

### 2.1 L-01: Lightweight Weight Metadata Accessor
- **`backend/app/repositories/json_repository.py`**:
  - During `_load_index()`, precomputes `self._weight_index` mapping `(track, route_id)` to `{original_weights, effective_weights, missing_criteria, valid_weight_coverage}`.
  - Added `get_weight_metadata(route_id, track)` returning an isolated shallow copy of only the weight dicts and missing list, eliminating per-row `copy.deepcopy()` of full explanation narratives and driver arrays.
- **`backend/app/services/ranking_service.py`**:
  - Updated `RankingService._build_ranking_item` to call `self._json_repo.get_weight_metadata(...)` instead of `get_explanation(...)`.

### 2.2 L-02: Thread-Safe Lazy Cache Initialization
- **`backend/app/repositories/parquet_repository.py`** & **`backend/app/repositories/json_repository.py`**:
  - Added `self._lock = threading.Lock()` in `__init__`.
  - Applied double-checked locking around `_load_parquet` and `_load_index`, plus lock synchronization in `clear_cache()`.
  - Cache-hit fast paths do not acquire the lock, avoiding contention during normal request processing and preventing deadlocks.

### 2.3 Modified File SHA-256 Comparison

| File Path | Pre-Change SHA-256 | Post-Change SHA-256 |
| :--- | :--- | :--- |
| `backend/app/services/ranking_service.py` | `0e7cac5b5f73fb27121e6f6a3c5e59d7af333d2894644c3eb35b6f6c6a0224da` | `fc7f7b377effe6cf6f55cac60480be434430c0f71f9901631a63b460a984069a` |
| `backend/app/repositories/json_repository.py` | `8d17e2f9b7e76ad7d296dad8e45c835315cc8f5612628a9d76a7804d061e90c6` | `f84dca28afac986def1604451b2659d45dcd5913e9d0c3a976dac3634d1d2e6c` |
| `backend/app/repositories/parquet_repository.py` | `3cdba04dcbc34391216a9bc83a6caba0af9b6242c04ac343e0688003bbbc036d` | `7821b7f0c3180227efaa839c84f9f1554946b97a4a3625f1342b51d8937df85` |

---

## 3. Test & Concurrency Verification

Added `backend/tests/test_repository_hardening.py` (5 focused tests):
1. `test_weight_metadata_equivalence_with_full_explanation`: Verified `get_weight_metadata` matches `get_explanation` across `BUS_PRIORITY`, `RAIL_PRIORITY`, and `UNIFIED_SUPPLY` (including Routes `10`, `130`, `N5`).
2. `test_returned_weight_metadata_and_explanation_immutability`: Verified mutating returned dicts/lists does not alter cached internal state.
3. `test_parquet_concurrent_cold_start_initializes_once`: 12 threads synchronized via `threading.Barrier` hit cold `ParquetRepository.get_rankings_master()`; `pd.read_parquet` spy confirmed `call_count == 1`.
4. `test_json_concurrent_cold_start_initializes_once`: 12 threads synchronized via `threading.Barrier` hit cold `JSONRepository.get_weight_metadata()`; `json.load` spy confirmed `call_count == 1`.
5. `test_concurrent_api_requests_consistency`: 10 simultaneous TestClient threads returned identical consistent `200 OK` responses.

| Suite | Command | Result | Duration |
| :--- | :--- | :---: | :---: |
| **Backend Tests** | `python -m unittest discover -s backend/tests -v` | **20 / 20 PASS** | $0.974\text{s}$ |
| **Full Project Suite** | `python -m unittest discover tests` | **205 / 205 PASS** | $9.045\text{s}$ |

---

## 4. Performance Benchmark Comparison (10-Run Warm-Cache Average)

| Endpoint | Baseline Avg (Min–Max) | Post-Fix Avg (Min–Max) | Observed Delta |
| :--- | :---: | :---: | :---: |
| `GET /api/v1/rankings/bus?limit=25` | `19.42 ms` (`16.21–23.01`) | `18.01 ms` (`13.08–23.00`) | `-1.41 ms` (`-7.3%`) |
| `GET /api/v1/rankings/bus?limit=125` | `40.93 ms` (`37.84–44.89`) | `40.09 ms` (`27.55–69.41`) | `-0.84 ms` (`-2.1%`, min `-27.2%`) |
| `GET /api/v1/rankings/unified?limit=133` | `40.25 ms` (`35.40–48.05`) | `34.06 ms` (`29.06–39.06`) | `-6.19 ms` (`-15.4%`) |

*Note:* The remaining ~30–40 ms on full-page (`125`/`133` row) responses is dominated by Pandas `iterrows()` row iteration and Pydantic v2 model validation rather than JSON copying.

---

## 5. Artifact Integrity & Scope Confirmation

- `artifacts/ranking_features/route_ranker_feature_master.parquet`: `c26aa49a408b1d07c6a0e09f2b11879cf623a54da1c3625f1342b51d8937df85` (**MATCH**)
- `artifacts/ranking_results/route_rankings_master.parquet`: `c440671d0b3888683969cb5fc11ccf7b581128a7296069019f76202b64f0093b` (**MATCH**)
- `artifacts/ranking_results/route_ranking_explanations.json`: `56c29ef9c77b7517e8cb621a207600aa576148aef015a35a364da029a74a24b2` (**MATCH**)
- `artifacts/ranking_results/ranking_sensitivity_analysis.parquet`: `fb41bcdf1e18da7978ae1666535d5868a92467143bd3d08b7ee5d71ef5d6790c` (**MATCH**)
- `artifacts/ranking_results/phase7_metadata.json`: `f29799139e4a861ea4f8b3679f96fa3e022436904b3c52fc8b7fc5a1cfd9ceca` (**MATCH**)
- Confirmed `/`, `/api/health`, frontend files, DuckDB, and PostgreSQL (inactive) remain untouched, and no Stage 2 endpoints were implemented.
