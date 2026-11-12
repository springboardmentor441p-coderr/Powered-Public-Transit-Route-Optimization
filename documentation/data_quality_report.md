# RouteRanker: Data Quality & Preprocessing Audit Report

This report documents the data quality checks, schema standardizations, and sanitization rules executed during **Phase 3: Data Preprocessing**.

---

## 1. Data Cleaning & Standardisation Summary

| Processed File Name | Source Raw Table | Pre-Clean Rows | Cleaned Rows | Integrity Checks Applied | Discrepancies |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `cleaned_daily_system_ridership.csv` | `cta_ridership_daily_system_totals.csv` | 9,374 | 9,374 | Date format standardized to ISO `YYYY-MM-DD`, sorted chronologically; non-negative numeric cast on `bus`, `rail_boardings`, `total_rides`; `day_type` mapped to human-readable labels; cross-check: `total_rides == bus + rail_boardings`. | 0 |
| `cleaned_bus_route_ridership.csv` | `cta_ridership_bus_routes_daily.csv` | 150,000 | 150,000 | Route identifiers trimmed and uppercased; dates parsed; negative counts bounded to 0; day types standardized; legacy/special event routes flagged. | 0 |
| `cleaned_l_station_entries.csv` | `cta_ridership_l_station_daily_entries.csv` | 150,000 | 150,000 | Station IDs cast to integer; station names normalized; dates parsed to ISO; non-negative validation on turnstile entries. | 0 |
| `cleaned_l_stations_directory.csv` | `cta_l_stations_list.csv` | 302 platforms | 144 stations | Geographic coordinates parsed from WKT point string `(lat, lon)`; line booleans normalized; aggregated from platform level to unique station `MAP_ID` level with ADA flags and lines served. | 0 |
| `cleaned_gtfs_routes.csv` | `gtfs/routes.txt` | 132 | 132 | Route short/long names sanitized; transit mode derived (1=Rail, 3=Bus); hex color codes normalized with `#` prefix. | 0 |
| `cleaned_gtfs_stops.csv` | `gtfs/stops.txt` | 11,138 | 11,138 | Verified coordinates within Chicago metropolitan bounding box (Lat 41.5 to 42.2, Lon -88.0 to -87.4). | 0 |

---

## 2. Temporal & Schema Consistency

1. **System Ridership Continuity**:
   - Spans 9,374 continuous days from **January 1, 2001** through **August 31, 2026**.
   - No temporal gaps exist in the daily system records.
2. **Mathematical Coherence**:
   - In 100% of rows in `cleaned_daily_system_ridership.csv`, `total_rides` strictly equals the sum of `bus` and `rail_boardings`.
3. **Day-Type Normalization**:
   - `W` $\rightarrow$ Weekday (Monday through Friday regular transit schedules).
   - `A` $\rightarrow$ Saturday (Reduced weekend schedules).
   - `U` $\rightarrow$ Sunday/Holiday (Sunday headway schedules and major federal holidays).

