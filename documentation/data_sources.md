# RouteRanker: Official Chicago CTA Data Sources

This document catalogues all official datasets acquired for the RouteRanker transportation analytics platform. All datasets originate strictly from official City of Chicago and Chicago Transit Authority (CTA) repositories.

---

## 1. Primary Data Portals

| Portal Name | Organization | Web URL | Role in Project |
| :--- | :--- | :--- | :--- |
| **Chicago Data Portal** | City of Chicago | `https://data.cityofchicago.org/` | Official repository for historical CTA passenger counts, daily system totals, station entries, and transit master tables. |
| **CTA Developer Center** | Chicago Transit Authority | `https://www.transitchicago.com/developers/` | Official portal for static GTFS transit archives, developer license agreements, and real-time APIs. |
| **CTA Bus Tracker Portal** | Chicago Transit Authority | `https://www.transitchicago.com/developers/bustracker/` | Developer portal for live bus locations, estimated arrival times, and pattern shapes. |
| **CTA Train Tracker Portal** | Chicago Transit Authority | `https://www.transitchicago.com/developers/traintracker/` | Developer portal for live train positions, run numbers, and station platform arrivals. |

---

## 2. Ingested Datasets

### A. CTA - Ridership - Daily Boarding Totals
- **Portal ID**: `6iiy-9s97`
- **Source URL**: `https://data.cityofchicago.org/api/views/6iiy-9s97/rows.csv?accessType=DOWNLOAD`
- **Local Destination**: `data/raw/cta_ridership_daily_system_totals.csv`
- **Format**: CSV (comma-separated values)
- **Record Count**: 9,374 rows
- **Columns**:
  1. `service_date` (MM/DD/YYYY): Date of transportation operations.
  2. `day_type` (W=Weekday, A=Saturday, U=Sunday/Holiday): Operational day category.
  3. `bus` (integer): Total daily passenger boardings on CTA bus routes.
  4. `rail_boardings` (integer): Total daily passenger entries into CTA rail stations.
  5. `total_rides` (integer): System-wide total rides (`bus + rail_boardings`).
- **Temporal Coverage**: January 1, 2001 to August 31, 2026.
- **Missing Values**: 0 (Complete dataset).
- **Update Frequency**: Monthly by CTA.
- **Application Role**: Serves as the primary ground-truth time series for daily passenger demand forecasting models.

### B. CTA - Ridership - Bus Routes - Daily Totals
- **Portal ID**: `jyb9-n7fm`
- **Source URL**: `https://data.cityofchicago.org/resource/jyb9-n7fm.csv`
- **Local Destination**: `data/raw/cta_ridership_bus_routes_daily.csv`
- **Format**: CSV
- **Record Count**: 150,000 recent route-day records
- **Columns**:
  1. `route` (string): Bus route identifier (e.g., `X9`, `49`, `66`, `79`).
  2. `date` (ISO timestamp): Service date.
  3. `daytype` (W=Weekday, A=Saturday, U=Sunday/Holiday).
  4. `rides` (integer): Total passenger boardings on that specific bus route.
- **Temporal Coverage**: February 3, 2023 to August 31, 2026.
- **Missing Values**: 0.
- **Application Role**: Route-level demand analytics, high/low demand bus corridor ranking, and service frequency optimization simulations.

### C. CTA - Ridership - 'L' Station Entries - Daily Totals
- **Portal ID**: `5neh-572f`
- **Source URL**: `https://data.cityofchicago.org/resource/5neh-572f.csv`
- **Local Destination**: `data/raw/cta_ridership_l_station_daily_entries.csv`
- **Format**: CSV
- **Record Count**: 150,000 recent station-day records
- **Columns**:
  1. `station_id` (integer): Unique 5-digit CTA station ID (e.g., `41700`, `40380`).
  2. `stationname` (string): Station name (e.g., `Clark/Lake`, `Washington/Wabash`).
  3. `date` (ISO timestamp): Service date.
  4. `daytype` (W/A/U): Day classification.
  5. `rides` (integer): Total daily turnstile turn-ins at the station.
- **Temporal Coverage**: October 23, 2023 to August 31, 2026.
- **Missing Values**: 0.
- **Application Role**: Rail station demand profiling, crowd level classification, and multi-modal transfer connectivity.

### D. CTA - System Information - List of 'L' (Rapid Transit) Stations
- **Portal ID**: `8pix-ypme`
- **Source URL**: `https://data.cityofchicago.org/api/views/8pix-ypme/rows.csv?accessType=DOWNLOAD`
- **Local Destination**: `data/raw/cta_l_stations_list.csv`
- **Format**: CSV
- **Record Count**: 302 platform records (144 unique stations)
- **Columns**:
  `STOP_ID`, `DIRECTION_ID`, `STOP_NAME`, `STATION_NAME`, `STATION_DESCRIPTIVE_NAME`, `MAP_ID`, `ADA`, `RED`, `BLUE`, `G`, `BRN`, `P`, `Y`, `Pnk`, `O`, `Location`
- **Application Role**: Spatial mapping of rail stations with geographic coordinates and rail line memberships (Red, Blue, Green, Brown, Purple, Yellow, Pink, Orange lines).

---

## 3. CTA Static GTFS Schedule Archive
- **Official Download URL**: `https://www.transitchicago.com/downloads/sch_data/google_transit.zip`
- **Local Extraction**: `data/raw/gtfs/`
- **Files Ingested**:
  1. `agency.txt` (1 agency: Chicago Transit Authority)
  2. `routes.txt` (132 routes: 8 rapid transit lines + 124 bus routes)
  3. `stops.txt` (11,138 transit stops and stations across the CTA service region)
  4. `trips.txt` (96,025 scheduled transit trips)
  5. `stop_times.txt` (5,920,320 arrival and departure records)
  6. `shapes.txt` (1,376,721 geographic trajectory points)
  7. `transfers.txt` (153 direct transit transfer points)
  8. `calendar.txt` & `calendar_dates.txt` (Service calendar schedules and holiday exceptions)

---

## 4. Limitations & Integrity Rules
- **No Extrapolation Beyond CTA**: Datasets represent only Chicago Transit Authority operations; Metra commuter rail and Pace suburban bus services are excluded.
- **Ground Truth Integrity**: All passenger figures reflect actual turnstile entries (rail) and farebox boardings (bus) collected by CTA fare equipment.
- **Occupancy vs Boardings**: Turnstile counts measure boardings, not the number of passengers onboard a moving vehicle at any single moment.

