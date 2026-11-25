# 03 — Database & Dataset Integrity Audit (Phase C)

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Database:** `data/processed/ai_routeranker.duckdb` (opened strictly `read_only=True`)  
**Audit Date:** 2026-11-25  

---

## 1. Schema & Tables Verified
16 base tables verified under schema `analytical`:
`cta_ridership_clean`, `daily_ridership`, `gtfs_agency`, `gtfs_calendar`, `gtfs_calendar_dates`, `gtfs_frequencies`, `gtfs_route_dim`, `gtfs_routes`, `gtfs_shapes`, `gtfs_snapshots`, `gtfs_stop_times`, `gtfs_stops`, `gtfs_trips`, `historical_schedule_match`, `route_mapping`, `snapshot_metadata`.

## 2. Canonical Ridership Verification (`analytical.daily_ridership`)
- **Row Count:** `1,124,170` (matches documented `1,124,170`)
- **Distinct Routes:** `188` (matches documented `188`)
- **Date Range:** `2001-01-01` to `2026-08-31` (matches documented range)
- **Null Rides:** `0`
- **Zero-Ridership Rows:** `36` (preserved as `0`, never converted to null)
- **Duplicate `(route, date)` Keys:** `0`

## 3. Historical GTFS & Schedule Matching Verification
- **GTFS Snapshots (`analytical.gtfs_snapshots`):** `8` (matching 8 directories in `data/processed/gtfs/`: `mdb-389-202511230128` .. `mdb-389-202607110020`)
- **Trips (`analytical.gtfs_trips`):** `627,416`
- **Stop Times (`analytical.gtfs_stop_times`):** `38,238,809`
- **Shape Points (`analytical.gtfs_shapes`):** `8,927,521`
- **Historical Schedule Match (`analytical.historical_schedule_match`):** `28,798` total rows
