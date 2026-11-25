# AI_RouteRanker — Milestone 8 Stage 2A: Independent Read-Only Audit Report

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Scope:** Milestone 8 Stage 2A — Historical Ridership API  
**Audit Date:** 2026-11-25T18:56:00+05:30  
**Final Audit Verdict:** **PASS** (0 Critical, 0 High, 0 Medium, 1 Low, 2 Informational)  

---

## 1. Executive Verdict

An independent, strictly read-only audit of **Milestone 8 Stage 2A (`GET /api/v1/ridership/routes/{route_id}/timeseries`)** was completed. The implementation is **secure, deterministic, memory-safe, and faithful to the underlying DuckDB analytical database**.

All **27 / 27 backend tests** and **205 / 205 project analytics tests** reproduced cleanly with zero failures, DuckDB and all canonical Phase 6.3 / Phase 7 artifacts remain 100% bit-for-bit identical, and measured process RSS remained `148.28 MB` (`165.37 MB` peak).

---

## 2. Files Inspected

- `backend/app/repositories/duckdb_repository.py`
- `backend/app/services/ridership_service.py`
- `backend/app/schemas/ridership.py`
- `backend/app/api/v1/ridership.py`, `deps.py`, `router.py`
- `backend/app/core/config.py`, `exceptions.py`
- `backend/tests/test_ridership_api.py`, `test_repository_hardening.py`
- `reports/phase8/phase8_stage2a_implementation_report.md`, `phase8_stage2a_test_report.md`, `phase8_stage2a_audit_checklist.md`

---

## 3. Database Schema Verification (`data/processed/ai_routeranker.duckdb`)

Opened strictly with `read_only=True`:
- **Table Verified:** `analytical.daily_ridership`
- **Columns & Types:** `route (VARCHAR)`, `date (DATE)`, `daytype (VARCHAR)`, `rides (BIGINT)`, `day_of_week (VARCHAR)`, `day_of_week_int (BIGINT)`, `is_weekend (BOOLEAN)`, `matched_snapshot_id (VARCHAR)`, `matched_snapshot_label (VARCHAR)`, `in_gtfs_coverage (BOOLEAN)`.
- **Row Count:** `1,124,170` rows | **Distinct Routes:** `188` | **Date Range:** `2001-01-01` to `2026-08-31`.
- **Zero & Null Counts:** `36` zero-ridership observations (e.g., Route `1` on `2015-11-07`, `2015-11-21`, `2015-11-26`, `2015-11-28`); `0` null rides.
- **Canonical Coverage:** `125 / 125` canonical bus routes present; `0 / 8` rail lines present.

---

## 4. Endpoint Correctness Findings

- **`GET /api/v1/ridership/routes/{route_id}/timeseries`**:
  - Valid bus route (`151`): Returns HTTP 200, chronological periods, `ridership_available=True`.
  - Zero-ridership preservation (Route `1`, `2015-11-07`, `granularity=daily`): Returned `rides: 0` cleanly without converting `0` to `null`.
  - Missing dates: Omitted cleanly without fabrication (verified on synthetic DuckDB fixture).
  - Rail routes (`Red`): Returns HTTP 200 with `ridership_available=False`, `observation_count=0`, `data=[]`, and explicit turnstile-level unavailability reason.
  - Unknown routes / invalid inputs: HTTP 404 (`ROUTE_NOT_FOUND`), HTTP 400 (`INVALID_ROUTE_ID`, `INVALID_DATE_RANGE`, `DATE_RANGE_TOO_LARGE`, `INVALID_GRANULARITY`, `INVALID_DAYTYPE`).

---

## 5. Date-Range and Aggregation Analysis

- **Daily Mode (`granularity="daily"`):** Explicitly bounded in `RidershipService` to `(eff_end - eff_start).days <= 366` (`DATE_RANGE_TOO_LARGE` HTTP 400 when exceeded).
- **Monthly Mode (`granularity="monthly"`):** Executes `GROUP BY strftime(date, '%Y-%m') ORDER BY period ASC` in DuckDB, computing `AVG(CASE WHEN daytype = 'W'/'A'/'U' THEN rides END)`, `SUM(rides)`, and `COUNT(*)`.
- **Bypass Check:** Tested `start_date=0001-01-01&end_date=9999-12-31&granularity=monthly`; returned HTTP 200 with `308` observations (bounded by the finite 25.7-year database range). `granularity` is validated strictly against `{"monthly", "daily"}`, so a caller cannot bypass the 366-day daily limit.

---

## 6. SQL and Security Audit

- **Read-Only Enforcement:** `duckdb.connect(str(self._db_path), read_only=True)` with `PRAGMA max_memory='256MB'` and `PRAGMA threads=2`.
- **Parameterized SQL:** All user-supplied values (`route_id`, `start_date`, `end_date`, `daytype`) are passed via `?` bind parameters; no string interpolation of user inputs occurs.
- **Error Isolation:** Missing or unreadable DuckDB files return HTTP 503 (`DATABASE_UNAVAILABLE` / `DATABASE_QUERY_FAILED`) without leaking local paths or tracebacks.

---

## 7. Concurrency Findings

- `DuckDBRepository` opens a fresh, short-lived read-only connection per query and closes it in `finally`, avoiding unsafe cross-thread connection sharing.
- 8-thread `ThreadPoolExecutor` + `threading.Barrier` test against canonical DuckDB passed with 100% consistent HTTP 200 responses.

---

## 8. Independent Test Reproduction

| Suite | Command | Collected | Result | Duration |
| :--- | :--- | :---: | :---: | :---: |
| **Backend Tests** | `python -m unittest discover -s backend/tests -v` | 27 | **27 PASS, 0 FAIL** | $1.719\text{s}$ |
| **Project Analytics** | `python -m unittest discover tests` | 205 | **205 PASS, 0 FAIL** | $8.820\text{s}$ |

Stage 1 endpoints (`/`, `/api/health`, `/api/v1/routes`, `/api/v1/rankings/bus`, `/api/v1/rankings/rail`) all returned `200 OK`.

---

## 9. Performance and Memory Measurements (Measured)

- **Cold First Query (8 mo):** `170.26 ms`
- **Warm Small Monthly (8 mo, 8 obs, 2.43 KB):** `avg = 57.25 ms`
- **Warm Full Monthly (25.7 yr, 308 obs, 67.58 KB):** `avg = 67.12 ms`
- **Warm Daily (365 days, 365 obs, 76.53 KB):** `avg = 55.89 ms`
- **Rail Unavailable (`Red`, 0.77 KB):** `avg = 9.84 ms`
- **Process Memory:** `RSS = 148.28 MB`, `Peak = 165.37 MB`

---

## 10. Artifact Hash Comparison

| Artifact Path | Observed SHA-256 | Status |
| :--- | :--- | :---: |
| `data/processed/ai_routeranker.duckdb` | `ec0fd3626c6734fa2f96d6202a6d4966ae193598cc6e1ca84a828c295eee4209` | **MATCH** |
| `artifacts/ranking_features/route_ranker_feature_master.parquet` | `c26aa49a408b1d07c6a0e09f2b11879cf623a54da1c3625f1342b51d8937df85` | **MATCH** |
| `artifacts/ranking_features/route_direction_connectivity_matrix.parquet` | `a13f84ea65404bb1fcd3ea856755a037f16f85a2c27498393d1f3adeb4d5b1cc` | **MATCH** |
| `artifacts/ranking_features/phase6_3_metadata.json` | `0ac55cefffb0aa3e8f3f9530f8fe9ceb5a3edd4931367b9dd502b77cf3a24d12` | **MATCH** |
| `artifacts/ranking_results/route_rankings_master.parquet` | `c440671d0b3888683969cb5fc11ccf7b581128a7296069019f76202b64f0093b` | **MATCH** |
| `artifacts/ranking_results/route_ranking_explanations.json` | `56c29ef9c77b7517e8cb621a207600aa576148aef015a35a364da029a74a24b2` | **MATCH** |
| `artifacts/ranking_results/ranking_sensitivity_analysis.parquet` | `fb41bcdf1e18da7978ae1666535d5868a92467143bd3d08b7ee5d71ef5d6790c` | **MATCH** |
| `artifacts/ranking_results/phase7_metadata.json` | `f29799139e4a861ea4f8b3679f96fa3e022436904b3c52fc8b7fc5a1cfd9ceca` | **MATCH** |

---

## 11. Findings Classification

- **Critical / High / Medium:** **None (0 findings).**
- **Low Finding L-01 (`backend/app/services/ridership_service.py`):** Monthly mode (`granularity="monthly"`) does not enforce an explicit date-span cap or default `limit`, relying instead on the finite 25.7-year database coverage (308 months max). If future data extends coverage significantly, an explicit monthly cap (e.g. `366` months) should be added.
- **Informational I-01 (`backend/app/schemas/ridership.py`):** `RidershipMethodologyMeta` documents unlinked boardings and missing-date policy, but does not explicitly state that monthly daytype averages are unweighted arithmetic means of observed days in each `YYYY-MM` period.
- **Informational I-02 (`backend/app/services/ridership_service.py`):** In `monthly` mode, `actual_date_range` normalizes `start_date` and `end_date` to the first day of the first/last observed month (`YYYY-MM-01`), which is consistent with monthly bucket keys.

---

## 12. Final Verdict

**PASS** — Milestone 8 Stage 2A is verified, secure, and ready for Stage 2B.
