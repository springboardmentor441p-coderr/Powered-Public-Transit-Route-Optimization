# AI_RouteRanker — Milestone 8 Stage 2A: Implementation Report

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Milestone:** 8 — Module 6 Backend API Integration  
**Stage:** 2A — Historical Ridership API (`DuckDBRepository` + `RidershipService` + `/api/v1/ridership/routes/{route_id}/timeseries`)  
**Date:** 2026-11-25T18:54:00+05:30  
**Status:** COMPLETE & VERIFIED (Stage 2B Not Started)  

---

## 1. Executive Summary

Stage 2A implemented the read-only historical ridership time-series API backed by `data/processed/ai_routeranker.duckdb` (`analytical.daily_ridership`, 1,124,170 rows spanning `2001-01-01` to `2026-08-31` across 188 bus routes, covering 125/125 canonical bus routes).

---

## 2. Implemented Components

- **`backend/app/core/config.py`**: Added `DATA_DIR`, `DUCKDB_PATH`, `RIDERSHIP_DEFAULT_START_DATE="2024-01-01"`, `RIDERSHIP_DEFAULT_END_DATE="2026-08-31"`, and `RIDERSHIP_MAX_DAILY_SPAN_DAYS=366`.
- **`backend/app/repositories/duckdb_repository.py` (`DuckDBRepository`)**:
  - Opens a short-lived `duckdb.connect(..., read_only=True)` connection per query, closed in `finally` (zero cross-thread connection sharing).
  - Enforces `PRAGMA max_memory='256MB'` and `PRAGMA threads=2`.
  - Uses exclusively parameterized SQL (`WHERE route = ? AND date >= ? AND date <= ?`) selecting only required columns (`date`, `daytype`, `rides`, `day_of_week`, `is_weekend`) from `analytical.daily_ridership`.
  - Maps missing/unreadable DuckDB errors to `ArtifactUnavailableError` (HTTP 503) without exposing paths.
- **`backend/app/schemas/ridership.py`**:
  - `DateRangeMeta`, `RidershipObservation`, `RidershipMethodologyMeta`, `RidershipTimeseriesResponse`.
  - Explicitly defines `rides` as historical daily unlinked route boardings (not onboard vehicle occupancy or passenger load) and preserves `0` rides as `0` while mapping absent daytypes in a month to JSON `null`.
- **`backend/app/services/ridership_service.py` (`RidershipService`)**:
  - Validates `route_id` regex, `granularity` (`monthly` | `daily`), `daytype` (`W` | `A` | `U`), `start_date <= end_date`, and max 366-day daily span.
  - Verifies canonical route membership against `ParquetRepository.get_feature_master()` (HTTP 404 for unknown routes).
  - Returns `ridership_available: false` with empty `data: []` for CTA rail lines (`Red`, `Blue`, etc.) rather than fabricating `0` rides.
- **`backend/app/api/v1/ridership.py`**, **`deps.py`**, **`router.py`**:
  - Exposes `GET /api/v1/ridership/routes/{route_id}/timeseries` mounted under `/api/v1`.

---

## 3. Sample Verified Response (`GET /api/v1/ridership/routes/151/timeseries`)

```json
{
  "route_id": "151",
  "route_short_name": "151",
  "route_long_name": "Sheridan",
  "route_type": 3,
  "is_rail": false,
  "ridership_available": true,
  "unavailable_reason": null,
  "requested_date_range": { "start_date": "2026-01-01", "end_date": "2026-08-31" },
  "actual_date_range": { "start_date": "2026-01-01", "end_date": "2026-08-01" },
  "observation_count": 8,
  "total_observations": 8,
  "offset": 0,
  "limit": null,
  "has_more": false,
  "methodology": {
    "source_table": "analytical.daily_ridership",
    "granularity": "monthly",
    "metric_definition": "Historical daily unlinked route boardings (rides) reported by CTA; not onboard vehicle occupancy or passenger load.",
    "missing_dates_policy": "Missing dates are omitted and never fabricated; zero rides are preserved as 0."
  }
}
```
