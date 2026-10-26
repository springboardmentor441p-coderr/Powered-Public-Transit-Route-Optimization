# Milestone 1: Data Pipeline Execution & Step Log

> **Note:** This document serves as a technical pipeline execution log recording data ingestion, cleaning, schedule generation, matching, and validation (Steps 1 through 13).  
> For the comprehensive analytical report, network findings, visualizations, and route profiles, refer to the official report: [`reports/milestone1_data_report.md`](milestone1_data_report.md).

---

## 1. Pipeline Execution Summary (Steps 1–13)

| Step | Task Description | Executable Script | Primary Inputs | Primary Outputs | Row / Record Count |
|---|---|---|---|---|---|
| **Step 1** | Register Data Sources | [`src/build_source_register.py`](../src/build_source_register.py) | `data/raw/` directory scan | [`reports/source_register.csv`](source_register.csv) | 19 cataloged sources (9 ridership, 9 GTFS, 1 post-window) |
| **Step 2 & 5** | Clean Hourly Ridership | [`src/clean_ridership.py`](../src/clean_ridership.py) | `data/raw/ridership/` (9 CSVs) | `data/processed/ridership_hourly_clean.parquet` | 268,632 clean route-hours (5 non-Manhattan/dormant routes dropped) |
| **Step 3 & 6** | GTFS Referential Integrity Check | [`src/check_gtfs_integrity.py`](../src/check_gtfs_integrity.py) | `data/raw/gtfs/manhattan/` (9 zip archives) | Console logs & validation records | 5 usable GTFS feeds validated; 4 duplicate/incomplete feeds excluded |
| **Step 7 & 8** | Service Calendar & Timetable Pick Selection | [`src/build_schedule.py`](../src/build_schedule.py) | Validated GTFS archives (`calendar.txt`, `calendar_dates.txt`) | Version mapping dictionary (271 dates assigned) | 100% of calendar dates assigned; pick boundary dates audited |
| **Step 9** | Build Scheduled Hourly Trips Grid | [`src/build_schedule.py`](../src/build_schedule.py) | 5 GTFS feeds (`trips.txt`, `stop_times.txt`) | `data/processed/schedule_hourly.parquet` | 266,664 route-hours (41 routes $\times$ 24 hrs $\times$ 271 days; zero rows preserved) |
| **Step 10** | Route Crosswalk & Nomenclature Matching | [`src/build_route_crosswalk.py`](../src/build_route_crosswalk.py) | Clean ridership & Spring GTFS feed | [`reports/route_crosswalk.csv`](route_crosswalk.csv) | 46 route codes evaluated: 41 matched, 5 ridership-only drops, 0 GTFS-only |
| **Step 11 & 12** | Join, Outage Detection & Feature Engineering | [`src/build_matched_table.py`](../src/build_matched_table.py) | Clean ridership & scheduled grid | `data/processed/matched_hourly.parquet` | 233,227 matched rows (259,243 joined after excluding 4 Jan, 9 Jan, 28 Mar, 16 Aug artifacts) |
| **Step 13** | Generate Route Profiles | [`src/build_route_profiles.py`](../src/build_route_profiles.py) | Spring GTFS feed (`shapes.txt`, `stops.txt`) & matched table | `data/processed/route_profiles.parquet`, [`reports/route_profiles.csv`](route_profiles.csv) | 41 route profiles with spatial geometry, speed, trips, headways, and ridership |

---

## 2. Key Dataset Artifacts & Outputs

All generated tables are stored in standard formats in `data/processed/` and `reports/`:
- **`data/processed/ridership_hourly_clean.parquet`:** 268,632 rows. Columns: `route, date, hour, ridership, transfers`.
- **`data/processed/schedule_hourly.parquet`:** 266,664 rows. Columns: `route, date, hour, trips_starting, trips_running, snapshot_id`. Preserves all zero-trip rows.
- **`data/processed/matched_hourly.parquet`:** 233,227 rows. Columns: `route, date, hour, month, day_of_week, is_weekend, is_public_holiday, holiday_schedule, is_storm, is_outlier, time_band, ridership, transfers, trips_starting, trips_running, riders_per_trip, snapshot_id`.
- **`data/processed/route_profiles.parquet` / [`reports/route_profiles.csv`](route_profiles.csv):** 41 rows. Comprehensive profiles combining Haversine shape distance, stop spacing, peak headway, speed, and ridership.  
  *Refinements in `build_route_profiles.py`:* Route lengths are calculated using the most common shape per direction averaged across both directions (refining M3 length from 17.43 km to 17.18 km and scheduled speed to 10.0 km/h). Span calculations evaluate morning start times past overnight terminal layovers (first morning departure 05:30 for non-24h route M3), and "Peak Gap" is computed separately for each direction and starting terminal and averaged across both operating directions.
- **[`reports/figures/mar28_hourly_ridership.png`](figures/mar28_hourly_ridership.png):** Visual proof of the 28 March 01:00–04:59 collection drop against typical Saturday baseline volume.

---

## 3. Data Outage Detection Rule & Exclusions

Rather than ad-hoc manual filtering, Step 11 applies a deterministic relative network drop rule:
- **Rule:** For every hour `(date, hour)`, compare total network ridership with the median for the same weekday and hour across the surrounding 3 weeks (+/- 21 days).
- **Threshold:** If total network ridership is **below 20% of the surrounding median**, the hour is flagged.
- **Baseline Safeguard:** The 6 missing data days (10–15 January) are completely excluded prior to calculating the rolling 3-week baselines, ensuring zero-ridership blackout days do not depress medians or allow partial drops to slip below the 20% threshold.
- **Rule Results:** Flags 21 hours across the study window:
  - 11 hours on 23 Feb (storm day, kept with `is_storm = True`)
  - 2 hours on 25 May (Memorial Day Sunday schedule, kept with `is_public_holiday = True`)
  - 8 hours of confirmed data collection outages (marked missing and excluded across all 41 routes)

### Exclusions Summary (533 Route-Hours Total)

Exclusions are divided into two distinct categories:

1. **Archive Boundary Artifact Exclusion (Non-Rule, Missing Saturday Timetable):**
   - `2026-01-04` hours 00:00–04:59 (5 hours $\times$ 41 routes = **205 route-hours**): Missing Saturday 3 January GTFS carry-over trips in the archive. Riders boarded late-night Saturday buses running past midnight, but incoming Sunday schedules did not record them, inflating `riders_per_trip`.

2. **Automated Collection Outages (Flagged by 20% Relative Rule):**
   - `2026-01-09` hours 22:00–23:59 (2 hours $\times$ 41 routes = **82 route-hours**): Feed collapse preceding the 10–15 Jan blackout (9.7% and 2.1% of median).
   - `2026-03-28` hours 01:00–04:59 (4 hours $\times$ 41 routes = **164 route-hours**): Automated collection outage (2.8% to 6.9% of median).
   - `2026-08-16` hours 21:00–22:59 (2 hours $\times$ 41 routes = **82 route-hours**): Automated collection outage (1.0% and 16.8% of median).
   - *Total Outage Route-Hours:* 8 hours $\times$ 41 routes = **328 route-hours**.

**Total Exclusions Combined:** $205 + 328 = \mathbf{533}$ route-hours ($259,776 - 533 = 259,243$ joined rows evaluated).

---

## 4. Quality Validation & Automated Test Suite

An automated test suite (`tests/test_milestone1_steps6_9.py`) validates the entire pipeline:
```bash
python -m pytest tests -v
```
- **Test Results:** 26 passed in 24.1s (**100% pass rate**).
- **Checks Verified:**
  - Referential integrity across all GTFS tables (routes, trips, stop_times, stops, calendar).
  - Correct calendar date filtering and holiday service exceptions (Memorial Day Sunday schedule equivalence).
  - Timetable switchover date assignments and boundary Saturday handling.
  - Correct midnight transition handling ($\ge \text{24:00}$ trips mapped to clock date).
  - 41 matched routes, 5 ridership-only drops, 0 GTFS-only unmatched.
  - Complete exclusion of the 4 Jan, 9 Jan, 28 Mar, and 16 Aug data outage blocks.
  - Correct identification and flagging of the M35 19 September afternoon surge (`is_outlier = True`).
  - Referential accuracy of `riders_per_trip` calculations and time-band classifications.
