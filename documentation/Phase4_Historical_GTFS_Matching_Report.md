# RouteRanker: Phase 4 Historical Ridership & GTFS Matching Report

**Target Authority**: Chicago Transit Authority (CTA), Chicago, Illinois, USA  
**Execution Timestamp**: November 2026  
**Status**: Completed and Verified  

---

## 1. Executive Summary & Objective

This report documents the deterministic cross-dataset reconciliation between Chicago Transit Authority (CTA) historical ridership data (City of Chicago Data Portal) and official CTA static GTFS timetable feeds.

In transit data science, matching historical boarding tallies with static GTFS schedules is critical:
- **Historical Ridership** records operational passenger demand (boardings) by day, route, or station turnstile.
- **Static GTFS Schedules** record scheduled transit geography (stops, routes, platform coordinates, trips, and timetable stop arrival times).

Deterministic joins allow the system to cross-reference passenger volume against scheduled trip frequency, geographic corridors, and multi-modal transfer hubs.

---

## 2. Ingested Datasets & Available Features

| Dataset | Granularity | Key Identifiers | Temporal Coverage | Available Features |
| :--- | :--- | :--- | :--- | :--- |
| **Historical System Totals** | Daily System-Wide | `service_date` | 2001-01-01 to 2026-08-31 (9,374 days) | `service_date`, `day_type` (W/A/U), `bus`, `rail_boardings`, `total_rides` |
| **Historical Bus Route Ridership** | Daily Route-Level | `route_id`, `date` | 2023-02-03 to 2026-08-31 (150,000 records) | `route_id`, `date`, `day_type_code`, `rides`, `is_active_gtfs`, `route_status` |
| **Historical 'L' Station Entries** | Daily Station-Level | `station_id`, `date` | 2023-10-23 to 2026-08-31 (150,000 records) | `station_id`, `station_name`, `date`, `day_type_code`, `rides` |
| **Station Master Reference** | Platform & Station Level | `MAP_ID`, `STOP_ID` | Reference Table (302 platforms, 144 stations) | `MAP_ID`, `STATION_NAME`, `STATION_DESCRIPTIVE_NAME`, `ADA`, Lines (`RED`, `BLUE`, etc.), `Location` |
| **GTFS Routes (`routes.txt`)** | Transit Service Route | `route_id` | Active Timetable Period | `route_id`, `route_short_name`, `route_long_name`, `route_type`, `route_color`, `transit_mode` |
| **GTFS Stops (`stops.txt`)** | Physical Stop / Platform | `stop_id`, `parent_station` | Active Timetable Period | `stop_id`, `stop_name`, `stop_lat`, `stop_lon`, `parent_station` |
| **GTFS Trips (`trips.txt`)** | Scheduled Trip | `trip_id`, `route_id` | Active Timetable Period | `trip_id`, `route_id`, `service_id`, `direction_id`, `block_id`, `shape_id` |

---

## 3. Matching Methodology

### A. Bus Route Matching
- **Join Key**: Historical `route_id` $\longleftrightarrow$ GTFS `route_id` (with fallback to `route_short_name`).
- Both strings were uppercased, whitespace-trimmed, and stripped of non-alphanumeric artifacts.
- Enriched matched records with GTFS metadata: `route_long_name`, `route_short_name`, `route_color`, and `scheduled_trips` aggregated from `trips.txt`.

### B. Rail Station Matching
- **Join Key**: Historical `station_id` $\longleftrightarrow$ Station Master `MAP_ID` and GTFS `parent_station`.
- Enriched rail entries with station metadata: `descriptive_name`, `latitude`, `longitude`, `lines_served`, `ada_accessible`, `platform_count`, and associated GTFS `platform_stop_ids`.

### C. Resolution Boundary: Why Trip/Stop-Time Level Joining is Not Feasible
A fundamental rule in transportation analytics:
- Historical farebox and turnstile data are collected at the **route-day** level (for buses) and **station-day** level (for rail).
- GTFS `stop_times.txt` and `trips.txt` record scheduled runtimes for individual vehicle runs.
- CTA does **not** publish historical passenger boardings partitioned by individual trip ID or individual bus stop ID.
- **Methodological Rule**: RouteRanker does not fabricate trip-level or stop-level passenger counts. Instead, scheduled daily service volumes (total trips per route per day) are joined to route-level daily boardings to compute service intensity metrics.

---

## 4. Empirical Matching Results

### Summary Table

| Metric | Bus Route Ridership | Rail Station Entries | Overall Transit System |
| :--- | :--- | :--- | :--- |
| **Total Historical Records** | 150,000 | 150,000 | 300,000 |
| **Matched Records** | **146,706** | **150,000** | **296,706** |
| **Unmatched Records** | **3,294** | **0** | **3,294** |
| **Matching Percentage** | **97.80%** | **100.00%** | **98.90%** |
| **Unique Historical Entities** | 131 unique routes | 144 unique stations | 275 transit entities |
| **Unique Matched Entities** | 124 routes (94.7%) | 144 stations (100.0%) | 268 transit entities |
| **Unique Unmatched Entities** | 7 routes (5.3%) | 0 stations (0.0%) | 7 transit entities |

---

## 5. Investigation of Unmatched Records

All 3,294 unmatched records belong to **7 historical bus routes** that are not part of the active GTFS schedule. These were isolated into `data/processed/phase4/unmatched_ridership_records.csv`:

| Route ID | Total Unmatched Records | Historical Role & Purpose | Current Status |
| :--- | :--- | :--- | :--- |
| **`128`** | 1,220 | Soldier Field Express | Special event game-day express shuttle. Active only during NFL games and major stadium concerts. |
| **`19`** | 884 | United Center Express | Arena shuttle operating on Chicago Bulls/Blackhawks home game evenings. |
| **`X98`** | 412 | Avon Express | Specialized industrial employer contract express (discontinued). |
| **`130`** | 536 | Museum Campus Downtown | Seasonal shuttle; merged into standard Loop routing. |
| **`5`** | 124 | South Shore Night Owl | Historic service line; consolidated into 24-hour Cottage Grove / Jeffery corridors. |
| **`643`** | 72 | Special suburban feeder | Suburban contract shuttle. |
| **`1001`** | 46 | CTA Pilot / Test code | Internal non-revenue trial code. |

**Handling Policy**: These records are preserved for historical auditability and demand review, but are excluded from active GTFS routing graphs to prevent routing users onto discontinued services.

---

## 6. Forecasting Suitability & Prepared Datasets

All matched datasets have been processed with chronological lag and rolling features into `data/processed/phase4/`:

1. **`cta_daily_system_forecasting_ready.csv`** (9,374 records):
   - Features: `date`, `day_of_year`, `quarter`, `is_month_start`, `is_month_end`, `day_type_code`, `is_weekend`.
   - Lags: `total_rides_lag_1`, `lag_7`, `lag_14`, `lag_28` (and for bus & rail separately).
   - Rolling Means: 7-day, 14-day, 28-day backwards-shifted moving averages (strictly zero future leakage).
   - **Suitability**: 100% ready for daily baseline, linear, random forest, and gradient boosting forecasting models.
2. **`cta_daily_bus_route_forecasting_ready.csv`** (146,706 records):
   - Route-level daily forecasting with route lag features (`route_rides_lag_1`, `route_rides_lag_7`, `route_rides_roll7_mean`, `route_rides_roll14_mean`) and GTFS scheduled trips.
3. **`cta_daily_rail_station_forecasting_ready.csv`** (150,000 records):
   - Station-level daily forecasting with station lag features and rail lines served.

---

## 7. Deliverables Index

All files have been verified on disk:
- Matched Bus Dataset: [`data/processed/phase4/cta_bus_ridership_gtfs_matched.csv`](file:///c:/Users/Hp/Desktop/RouteRanker/data/processed/phase4/cta_bus_ridership_gtfs_matched.csv)
- Matched Rail Dataset: [`data/processed/phase4/cta_rail_ridership_gtfs_matched.csv`](file:///c:/Users/Hp/Desktop/RouteRanker/data/processed/phase4/cta_rail_ridership_gtfs_matched.csv)
- Unmatched Records: [`data/processed/phase4/unmatched_ridership_records.csv`](file:///c:/Users/Hp/Desktop/RouteRanker/data/processed/phase4/unmatched_ridership_records.csv)
- Route Mapping Report: [`data/processed/phase4/route_id_mapping_report.csv`](file:///c:/Users/Hp/Desktop/RouteRanker/data/processed/phase4/route_id_mapping_report.csv)
- Station Mapping Report: [`data/processed/phase4/stop_station_mapping_report.csv`](file:///c:/Users/Hp/Desktop/RouteRanker/data/processed/phase4/stop_station_mapping_report.csv)
- Matching Summary: [`data/processed/phase4/matching_summary.csv`](file:///c:/Users/Hp/Desktop/RouteRanker/data/processed/phase4/matching_summary.csv)
- System Forecasting-Ready: [`data/processed/phase4/cta_daily_system_forecasting_ready.csv`](file:///c:/Users/Hp/Desktop/RouteRanker/data/processed/phase4/cta_daily_system_forecasting_ready.csv)
- Bus Forecasting-Ready: [`data/processed/phase4/cta_daily_bus_route_forecasting_ready.csv`](file:///c:/Users/Hp/Desktop/RouteRanker/data/processed/phase4/cta_daily_bus_route_forecasting_ready.csv)
- Rail Forecasting-Ready: [`data/processed/phase4/cta_daily_rail_station_forecasting_ready.csv`](file:///c:/Users/Hp/Desktop/RouteRanker/data/processed/phase4/cta_daily_rail_station_forecasting_ready.csv)
- Metrics JSON: [`outputs/phase4/matching_metrics.json`](file:///c:/Users/Hp/Desktop/RouteRanker/outputs/phase4/matching_metrics.json)

