# RouteRanker: CTA GTFS Static Archive Validation Report

This report documents the validation and integrity verification of the official Chicago Transit Authority (CTA) GTFS static schedule dataset extracted to `data/raw/gtfs/`.

---

## 1. GTFS Archive Overview

- **Source**: Chicago Transit Authority Developer Center (`https://www.transitchicago.com/downloads/sch_data/google_transit.zip`)
- **Extraction Timestamp**: November 2026
- **License**: CTA Developer License Agreement (`developers_license_agreement.htm`)

---

## 2. Table-by-Table Validation Summary

| GTFS Table | Record Count | Attributes Count | Core Key Identifiers | Status | Integrity Assessment |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `agency.txt` | 1 | 7 | `agency_id` | Valid | Agency identified as Chicago Transit Authority, timezone `America/Chicago`. |
| `routes.txt` | 132 | 8 | `route_id`, `route_short_name` | Valid | 8 rail rapid transit lines (`Red`, `Blue`, `Brn`, `G`, `Org`, `P`, `Pnk`, `Y`) and 124 scheduled bus routes. |
| `stops.txt` | 11,138 | 9 | `stop_id`, `stop_name`, `stop_lat`, `stop_lon` | Valid | Complete coverage of CTA bus stops and rail station platforms with valid GPS coordinates within Chicago bounding box (lat ~41.6 to ~42.1, lon ~-87.9 to ~-87.5). |
| `trips.txt` | 96,025 | 9 | `trip_id`, `route_id`, `service_id` | Valid | Maps each trip to a designated route, block ID, shape, and service calendar. |
| `stop_times.txt` | 5,920,320 | 8 | `trip_id`, `stop_id`, `arrival_time`, `departure_time` | Valid | Chronological arrival and departure sequencing across all scheduled trips. |
| `shapes.txt` | 1,376,721 | 5 | `shape_id`, `shape_pt_lat`, `shape_pt_lon`, `shape_pt_sequence` | Valid | Detailed spatial polyline traces for bus lines and rail corridors. |
| `calendar.txt` | 127 | 10 | `service_id`, `start_date`, `end_date` | Valid | Binary flags for day-of-week operations across current operational schedules. |
| `calendar_dates.txt` | 85 | 3 | `service_id`, `date`, `exception_type` | Valid | Exception rules for holidays (e.g. Thanksgiving, Christmas, New Year). |
| `transfers.txt` | 153 | 3 | `from_stop_id`, `to_stop_id`, `transfer_type` | Valid | Defines direct transfer links between intersecting rail lines and major terminals. |
| `frequencies.txt` | 0 | 4 | `trip_id`, `headway_secs` | Valid | Empty table; CTA uses explicit `stop_times.txt` schedules rather than frequency-based timetable compression. |

---

## 3. GTFS Transit Graph Capabilities

1. **Multi-Modal Network Construction**:
   - Rail lines and bus routes share transfer nodes via `transfers.txt` and spatial proximity between bus stops and rail station entrances.
2. **Scheduled Travel Times**:
   - Exact travel durations between adjacent stops can be derived from `stop_times.arrival_time` and `stop_times.departure_time`.
3. **Shape Trajectories**:
   - The 1,376,721 coordinates in `shapes.txt` allow high-resolution map rendering of CTA routes on interactive Leaflet maps.

