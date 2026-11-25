# AI_RouteRanker — Milestone 8 Stage 2A: Test & Performance Report

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Milestone:** 8 — Module 6 Backend API Integration  
**Stage:** 2A — Historical Ridership API  
**Date:** 2026-11-25T18:54:00+05:30  
**Overall Test Verdict:** 100% PASS (27 / 27 Backend Tests, 205 / 205 Project Tests)  

---

## 1. Test Execution Summary

| Suite | Command | Collected / Executed | Result | Duration |
| :--- | :--- | :---: | :---: | :---: |
| **Backend Tests** | `python -m unittest discover -s backend/tests -v` | 27 (20 Stage 1 + 7 Stage 2A) | **27 PASS, 0 FAIL** | $1.749\text{s}$ |
| **Project Analytics** | `python -m unittest discover tests` | 205 | **205 PASS, 0 FAIL** | $8.768\text{s}$ |

### Stage 2A Test Coverage (`backend/tests/test_ridership_api.py`)
1. `test_valid_bus_route_monthly_and_daily`: Verified Route `151` monthly (`8` periods) and daily (`10` days) chronological series.
2. `test_rail_route_unavailable_behavior`: Verified Rail Route `Red` returns `ridership_available=False`, `data=[]`, and explicit reason.
3. `test_unknown_route_and_invalid_parameters`: Verified 404 (`ROUTE_NOT_FOUND`) and 400 (`INVALID_ROUTE_ID`, `INVALID_DATE_RANGE`, `DATE_RANGE_TOO_LARGE`, `INVALID_GRANULARITY`, `INVALID_DAYTYPE`).
4. `test_empty_date_range_and_daytype_filtering`: Verified empty date window returns `observation_count=0` and `daytype=W` leaves Saturday/Sunday averages `null`.
5. `test_concurrent_ridership_requests`: 8 barrier-synchronized threads querying DuckDB simultaneously all returned HTTP 200 with expected counts.
6. `test_synthetic_zero_ridership_and_missing_dates`: Synthetic DuckDB fixture proved `rides=0` is preserved as `0`/`0.0`, missing dates are not fabricated, and SQL injection strings return `[]` safely.
7. `test_missing_duckdb_returns_503_safely`: Missing DuckDB file returned HTTP 503 (`DATABASE_UNAVAILABLE`) without leaking temp directory paths.

---

## 2. Measured Performance & Memory Benchmarks

Collected directly using `time.perf_counter()` (5-run warm-cache average) and Windows `GetProcessMemoryInfo`:
- **First Cold Query (8 mo):** `194.05 ms`
- **Warm Small Monthly (8 mo, 8 obs, 2.43 KB):** `avg = 56.25 ms`
- **Warm Full Monthly (25.7 yr, 308 obs, 67.58 KB):** `avg = 68.27 ms`
- **Warm Daily (365 days, 365 obs, 76.53 KB):** `avg = 63.32 ms`
- **Rail Unavailable (`Red`, 0.77 KB):** `avg = 9.06 ms`
- **Process Memory:** `RSS = 144.09 MB`, `Peak = 159.80 MB` (well below 350 MB limit on 8 GB RAM).

---

## 3. Integrity Confirmation

- **`data/processed/ai_routeranker.duckdb` SHA-256:** `ec0fd3626c6734fa2f96d6202a6d4966ae193598cc6e1ca84a828c295eee4209` (**100% MATCH** — unchanged).
- Stage 1 endpoints (`/`, `/api/health`, `/api/v1/routes`, `/api/v1/rankings/*`) all passed regression checks.
- No frontend files modified; PostgreSQL not activated; no spatial/corridor/forecasting endpoints added.
