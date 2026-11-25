# AI_RouteRanker - Comprehensive Data Dictionary
**Milestone 3.1: Data Preprocessing & Relational GTFS Ingestion**  
*Generated on: 2026-11-20*  
*Target Database: DuckDB (`data/processed/ai_routeranker.duckdb`), Schema: `analytical`*

---

## 1. Overview
The data architecture of **AI_RouteRanker** is built around two foundational transit datasets:
1. **CTA Daily Bus Ridership**: 1,124,170 records from 2001-01-01 to 2026-08-31 across 188 distinct routes.
2. **Historical GTFS Archives (Mobility Database mdb-389)**: Eight independent snapshots covering effective service windows between 2025-11-23 and 2026-07-31, containing 627,416 trips, 38,238,809 stop times, and 8,927,521 shape points.

All data is structured relationally, enforces strict primary and foreign key constraints, preserves route identifier data types (e.g., prefix `X` and leading zeros), and evaluates GTFS calendar overrides.

---

## 2. Processed & Analytical Tables

### 2.1 `analytical.cta_ridership_clean`
*Storage: Parquet (`data/processed/ridership/cta_ridership_clean.parquet`) and CSV (`cta_ridership_clean.csv`)*  
*Record Count: 1,124,170 | Deduplication: 0 duplicates | Quarantined: 0*

| Column Name | Data Type | Nullable | Description | Provenance / Rules |
| :--- | :--- | :--- | :--- | :--- |
| `route` | `VARCHAR` | NO | CTA route identifier (e.g. `'1'`, `'X4'`, `'008'`). | Cleaned string, leading zeros and prefixes preserved. |
| `date` | `DATE` | NO | Calendar date of service. | Converted from `MM/DD/YYYY` format. Range: 2001-01-01 to 2026-08-31. |
| `daytype` | `VARCHAR` | NO | Service day categorization (`'W'`=Weekday, `'A'`=Saturday, `'U'`=Sunday/Holiday). | Normalized uppercase single character. |
| `rides` | `BIGINT` | NO | Total unlinked passenger boardings for route on date. | Commas stripped, non-negative integer. 36 genuine zeros retained. |

---

### 2.2 `analytical.gtfs_snapshots` / `snapshot_metadata`
*Storage: Parquet (`data/processed/integrated/snapshot_metadata.parquet`)*  
*Record Count: 8 snapshots*

| Column Name | Data Type | Nullable | Description | Provenance / Rules |
| :--- | :--- | :--- | :--- | :--- |
| `snapshot_id` | `VARCHAR` | NO | Unique Mobility Database snapshot ID (e.g., `mdb-389-202511230128`). | Primary Key. |
| `archive_label` | `VARCHAR` | NO | Human-readable label (e.g. `'November 23, 2025'`). | Derived from snapshot date. |
| `effective_start_date` | `DATE` | NO | Inclusive start date for GTFS schedule matching. | Configured effective matching window. |
| `effective_end_date` | `DATE` | NO | Inclusive end date for GTFS schedule matching. | Configured effective matching window. |
| `agency_count` | `BIGINT` | NO | Count of agencies in snapshot. | Verification audit metric. |
| `routes_count` | `BIGINT` | NO | Count of routes in snapshot (131 to 133). | Verification audit metric. |
| `trips_count` | `BIGINT` | NO | Count of trips in snapshot (49,936 to 94,704). | Verification audit metric. |
| `stops_count` | `BIGINT` | NO | Count of stops in snapshot (~11,150). | Verification audit metric. |
| `stop_times_count` | `BIGINT` | NO | Count of stop times in snapshot (2,996,069 to 5,838,352). | Verification audit metric. |
| `calendar_count` | `BIGINT` | NO | Count of calendar service rows in snapshot. | Verification audit metric. |
| `calendar_dates_count` | `BIGINT` | NO | Count of calendar exception rows in snapshot. | Verification audit metric. |
| `shapes_count` | `BIGINT` | NO | Count of shape points in snapshot (~1,115,000). | Verification audit metric. |
| `pk_integrity_passed` | `BOOLEAN` | NO | Primary key uniqueness check result across tables. | `True` for all 8 snapshots. |
| `fk_integrity_passed` | `BOOLEAN` | NO | Foreign key referential integrity check result. | `True` for all 8 snapshots. |
| `status` | `VARCHAR` | NO | Processing status. | `'INGESTED'` |

---

### 2.3 `analytical.gtfs_routes`
*Storage: Parquet (`data/processed/gtfs/<snapshot_id>/gtfs_routes.parquet`)*  
*Record Count: 1,052 across 8 snapshots*

| Column Name | Data Type | Nullable | Description | Provenance / Rules |
| :--- | :--- | :--- | :--- | :--- |
| `snapshot_id` | `VARCHAR` | NO | Parent snapshot ID. | Composite Primary Key (with `route_id`). |
| `route_id` | `VARCHAR` | NO | Internal GTFS route identifier. | Composite Primary Key. |
| `agency_id` | `VARCHAR` | YES | Transit agency identifier. | Normalized across snapshots (handled optional column). |
| `route_short_name` | `VARCHAR` | YES | Public-facing route number (e.g. `'1'`, `'79'`, `'X4'`). | Primary match key with ridership route. |
| `route_long_name` | `VARCHAR` | YES | Full route descriptive name. | e.g. `'Bronzeville/Union Station'`, `'79th'`. |
| `route_desc` | `VARCHAR` | YES | Route description. | Nullable text. |
| `route_type` | `INTEGER` | YES | Mode of transit (3 = Bus). | Standard GTFS specification code. |
| `route_url` | `VARCHAR` | YES | Official web link for route schedule. | Standard GTFS url (resolved snapshot typo `route_rul`). |
| `route_color` | `VARCHAR` | YES | Hex color code for route mapping. | e.g. `'0081C6'`. |
| `route_text_color` | `VARCHAR` | YES | Hex color code for text on route badges. | e.g. `'FFFFFF'`. |

---

### 2.4 `analytical.gtfs_trips`
*Storage: Parquet (`data/processed/gtfs/<snapshot_id>/gtfs_trips.parquet`)*  
*Record Count: 627,416 across 8 snapshots*

| Column Name | Data Type | Nullable | Description | Provenance / Rules |
| :--- | :--- | :--- | :--- | :--- |
| `snapshot_id` | `VARCHAR` | NO | Snapshot identifier. | Composite Primary Key (with `trip_id`). |
| `route_id` | `VARCHAR` | NO | Foreign key referencing `gtfs_routes.route_id`. | Foreign Key validated. |
| `service_id` | `VARCHAR` | NO | Calendar service schedule identifier. | References `gtfs_calendar.service_id`. |
| `trip_id` | `VARCHAR` | NO | Unique trip identifier. | Composite Primary Key. |
| `trip_headsign` | `VARCHAR` | YES | Destination displayed on bus headsign. | Preserved when present. |
| `direction_id` | `INTEGER` | YES | Binary travel direction indicator (0 or 1). | Preserved as integer. |
| `block_id` | `VARCHAR` | YES | Vehicle block assignment. | Operational scheduling identifier. |
| `shape_id` | `VARCHAR` | YES | Foreign key referencing `gtfs_shapes.shape_id`. | GIS polyline reference. |
| `wheelchair_accessible` | `INTEGER` | YES | Accessibility flag (1 = Accessible). | Accessibility metric. |

---

### 2.5 `analytical.gtfs_stop_times`
*Storage: Parquet (`data/processed/gtfs/<snapshot_id>/gtfs_stop_times.parquet`)*  
*Record Count: 38,238,809 across 8 snapshots*

| Column Name | Data Type | Nullable | Description | Provenance / Rules |
| :--- | :--- | :--- | :--- | :--- |
| `snapshot_id` | `VARCHAR` | NO | Snapshot identifier. | Part of Composite Key. |
| `trip_id` | `VARCHAR` | NO | References `gtfs_trips.trip_id`. | Foreign Key validated. |
| `arrival_time` | `VARCHAR` | NO | Raw scheduled arrival time string. | e.g. `'08:30:00'`, `'24:15:30'`. |
| `departure_time` | `VARCHAR` | NO | Raw scheduled departure time string. | e.g. `'08:30:15'`, `'24:15:45'`. |
| `arrival_seconds` | `INTEGER` | NO | Arrival time normalized to cumulative seconds from midnight. | Handles times $\ge$ 24:00:00 ($H \times 3600 + M \times 60 + S$). |
| `departure_seconds` | `INTEGER` | NO | Departure time normalized to cumulative seconds from midnight. | Handles times $\ge$ 24:00:00. |
| `stop_id` | `VARCHAR` | NO | References `gtfs_stops.stop_id`. | Foreign Key validated. |
| `stop_sequence` | `INTEGER` | NO | Ordinal stop sequence along trip. | Part of Composite Key. |
| `stop_headsign` | `VARCHAR` | YES | Specific stop headsign text. | Preserved. |
| `pickup_type` | `INTEGER` | YES | Pickup indicator (0=Regularly scheduled). | GTFS standard. |
| `drop_off_type` | `INTEGER` | YES | Drop-off indicator (0=Regularly scheduled). | GTFS standard. |
| `shape_dist_traveled` | `DOUBLE` | YES | Cumulative distance along shape. | GIS linear referencing. |
| `timepoint` | `INTEGER` | YES | Timepoint precision indicator. | GTFS standard. |

---

### 2.6 `analytical.gtfs_calendar` & `gtfs_calendar_dates`
*Storage: Parquet (`data/processed/gtfs/<snapshot_id>/...`)*  
*Record Counts: 933 calendar rules, 765 calendar date exceptions*

| Table | Column Name | Data Type | Nullable | Description |
| :--- | :--- | :--- | :--- | :--- |
| `gtfs_calendar` | `snapshot_id` | `VARCHAR` | NO | Snapshot identifier. |
| `gtfs_calendar` | `service_id` | `VARCHAR` | NO | Service identifier. |
| `gtfs_calendar` | `monday`..`sunday` | `INTEGER` | NO | Day-of-week active flags (1 = Active, 0 = Inactive). |
| `gtfs_calendar` | `start_date` | `DATE` | NO | Service valid start date. |
| `gtfs_calendar` | `end_date` | `DATE` | NO | Service valid end date. |
| `gtfs_calendar_dates` | `snapshot_id` | `VARCHAR` | NO | Snapshot identifier. |
| `gtfs_calendar_dates` | `service_id` | `VARCHAR` | NO | Service identifier. |
| `gtfs_calendar_dates` | `date` | `DATE` | NO | Target exception date. |
| `gtfs_calendar_dates` | `exception_type` | `INTEGER` | NO | Exception override: `1` = Service Added, `2` = Service Removed. |

---

### 2.7 `analytical.route_mapping`
*Storage: Parquet (`data/processed/integrated/route_mapping.parquet`)*  
*Record Count: 1,504 route-snapshot combinations (188 ridership routes $\times$ 8 snapshots)*

| Column Name | Data Type | Nullable | Description | Values / Meaning |
| :--- | :--- | :--- | :--- | :--- |
| `ridership_route` | `VARCHAR` | NO | Route identifier from CTA ridership. | 188 historical routes. |
| `snapshot_id` | `VARCHAR` | NO | GTFS snapshot ID. | 8 snapshots. |
| `gtfs_route_short_name`| `VARCHAR` | YES | Matched GTFS route short name. | Identical to ridership route for active routes. |
| `gtfs_route_id` | `VARCHAR` | YES | Internal GTFS route identifier. | Target key for GTFS joins. |
| `gtfs_route_long_name` | `VARCHAR` | YES | Matched route descriptive name. | e.g. `'Bronzeville/Union Station'`. |
| `gtfs_route_type` | `INTEGER` | YES | GTFS transit mode (3=Bus). | Bus transit indicator. |
| `mapping_method` | `VARCHAR` | NO | Matching algorithm applied. | `'exact_route_short_name'`, `'exact_route_id'`, `'none'`. |
| `match_candidates_count`| `INTEGER` | NO | Number of candidates matching route. | 1 for exact, 0 for unmatched, >1 for ambiguous. |
| `match_status` | `VARCHAR` | NO | Categorical mapping state. | `'exact_match'` (988), `'unmatched'` (516), `'ambiguous'` (0). |

---

### 2.8 `analytical.daily_ridership`
*Storage: Parquet (`data/processed/integrated/daily_ridership.parquet`)*  
*Record Count: 1,124,170 records*

| Column Name | Data Type | Nullable | Description | Values / Meaning |
| :--- | :--- | :--- | :--- | :--- |
| `route` | `VARCHAR` | NO | CTA bus route. | Preserved route string. |
| `date` | `DATE` | NO | Date of service. | 2001-01-01 to 2026-08-31. |
| `daytype` | `VARCHAR` | NO | CTA day type. | `'W'` (Weekday), `'A'` (Saturday), `'U'` (Sunday/Holiday). |
| `rides` | `BIGINT` | NO | Daily boardings. | Cleaned integer count. |
| `day_of_week` | `VARCHAR` | NO | Day name. | `'Monday'`, `'Tuesday'`, etc. |
| `day_of_week_int` | `INTEGER` | NO | Day of week integer. | 0 = Sunday, 1 = Monday, ..., 6 = Saturday. |
| `is_weekend` | `BOOLEAN` | NO | Weekend flag. | `true` if Saturday/Sunday/Holiday; `false` otherwise. |
| `matched_snapshot_id` | `VARCHAR` | YES | Corresponding GTFS snapshot covering this date. | Set for dates between 2025-11-23 and 2026-07-31; `NULL` outside. |
| `matched_snapshot_label`| `VARCHAR` | YES | Label of matched snapshot. | e.g. `'November 23, 2025'`. |
| `in_gtfs_coverage` | `BOOLEAN` | NO | Flag indicating GTFS snapshot availability. | `true` (28,798 rows), `false` (1,095,372 rows). |

---

### 2.9 `analytical.historical_schedule_match`
*Storage: Parquet (`data/processed/integrated/historical_schedule_match.parquet`)*  
*Record Count: 28,798 records (Dates: 2025-11-23 to 2026-07-31)*

| Column Name | Data Type | Nullable | Description | Values / Meaning |
| :--- | :--- | :--- | :--- | :--- |
| `snapshot_id` | `VARCHAR` | NO | Matched GTFS snapshot ID. | 8 snapshots. |
| `archive_label` | `VARCHAR` | NO | Snapshot label. | Date label. |
| `date` | `DATE` | NO | Date of service. | 2025-11-23 to 2026-07-31. |
| `ridership_route` | `VARCHAR` | NO | Route identifier from ridership. | 128 active routes during period. |
| `gtfs_route_id` | `VARCHAR` | YES | Matched GTFS route ID. | Foreign key to `gtfs_routes`. |
| `gtfs_route_short_name`| `VARCHAR` | YES | Matched GTFS route short name. | Route number. |
| `gtfs_route_long_name` | `VARCHAR` | YES | Route descriptive name. | Descriptive route name. |
| `daytype` | `VARCHAR` | NO | Ridership daytype. | `'W'`, `'A'`, `'U'`. |
| `day_of_week` | `VARCHAR` | NO | Calendar day of week. | `'Monday'`..`'Sunday'`. |
| `is_weekend` | `BOOLEAN` | NO | Weekend flag. | `true`/`false`. |
| `rides` | `BIGINT` | NO | Actual recorded boardings on date. | Ridership volume. |
| `scheduled_trips_count`| `BIGINT` | NO | Number of active scheduled trips on date. | Calculated via calendar rules. |
| `scheduled_stop_visits`| `BIGINT` | NO | Total stop sequence calls across active trips. | Operational intensity metric. |
| `first_departure_seconds`| `BIGINT` | YES | Earliest departure on date in seconds from midnight. | Operational span start. |
| `last_departure_seconds`| `BIGINT` | YES | Latest departure on date in seconds from midnight. | Operational span end. |
| `first_departure_time` | `VARCHAR` | YES | Earliest departure formatted `HH:MM:SS`. | e.g. `'04:30:00'`. |
| `last_departure_time` | `VARCHAR` | YES | Latest departure formatted `HH:MM:SS`. | e.g. `'25:15:00'`. |
| `service_span_seconds` | `BIGINT` | YES | Daily operating span in seconds (`last - first`). | Daily duration of service. |
| `is_service_active` | `BOOLEAN` | NO | Service activation status. | `true` if scheduled trips > 0. |
| `match_quality` | `VARCHAR` | NO | Data matching quality assessment. | `'matched'` (28,374 - 98.53%), `'unmatched_route'` (405), `'zero_scheduled_trips'` (19). |

---

## 3. Data Integrity & Verification Standards
- **String Type Preservation**: All route identifiers are explicitly cast as `VARCHAR` to prevent truncation of leading zeros (e.g., `'008'`) or loss of prefixes (e.g., `'X4'`, `'N5'`).
- **Calendar Logic Strictness**: Service activation strictly enforces `calendar_dates.txt` exception types:
  - Exception Type 1 overrides base weekly calendar to **Active**.
  - Exception Type 2 overrides base weekly calendar to **Inactive**.
  - In the absence of an exception, the base calendar rule applies if the date falls between `start_date` and `end_date` and the corresponding weekday flag equals 1.
- **Timestamp Wrap-around**: Times exceeding 24:00:00 (e.g. late night service past midnight) are handled via cumulative seconds computation ($H \times 3600 + M \times 60 + S$), preventing date parsing errors.
- **Relational Integrity**: 100% of foreign keys resolve successfully without dangling references across all 8 GTFS snapshots.
