# Data dictionary

This file lists the processed files, the database tables and the forecasting features for data version `cta_ref__r20261113__gtfs8__to20260731`. The SQL definitions with every constraint are in `backend/db/schema.sql`, `schema_stage7.sql` and `schema_stage8.sql`. The feature contract is `artifacts/stage4a/feature_contract.json`.

**Conventions used everywhere**
- A missing value is empty (CSV) or NULL (database), never 0. A recorded 0 is a real 0.
- `route` is text, so identifiers such as `X49` or `55N` stay exact.
- `daytype` is the CTA day type: `W` weekday, `A` Saturday, `U` Sunday or holiday.
- Ratios are ratios of sums over the same matched days, not means of daily ratios.
- Every table is keyed by its version (`data_version` or `group_version`), so two versions can sit side by side.

## 1. Raw sources (`data/raw/`, never overwritten)
| File | Columns | Notes |
|---|---|---|
| `ridership/CTA_-_Ridership_-_Bus_Routes_-_Daily_Totals_by_Route_<date>.csv` | `route`, `date` (MM/DD/YYYY), `daytype`, `rides` | one row per route per day; 1,124,170 rows in the 2026-11-13 export |
| `gtfs/<snapshot_id>/original.zip` + `extracted/*.txt` | GTFS: `routes`, `trips`, `stop_times`, `calendar`, `calendar_dates`, `stops`, `shapes` … | 8 archives, `mdb-389-202511230128` to `mdb-389-202607110020` |
| `source_register.csv` | `dataset_id`, `snapshot_id`, `source_url`, `downloaded_at`, `sha256`, `byte_size`, `row_count`, `source_last_updated`, `expected_sha256`, `fingerprint_match`, `is_primary` | the source manifest, copied to `reports/` |

## 2. Processed tables (`data/processed/<data_version>/`)
| File | One row per | Key columns |
|---|---|---|
| `expanded_scheduled_route_day_service.csv` | route × service date in the selected timetable | `scheduled_trips`, `scheduled_service_hours` (empty if any trip time is invalid), `snapshot_id` |
| `expanded_matched_utilization.csv` | route × date with both rides and schedule (28,374 rows) | `rides`, `scheduled_trips`, `scheduled_service_hours`, `rides_per_scheduled_trip`, `rides_per_scheduled_hour` |
| `expanded_ridership_without_schedule.csv` | recorded rides on a date with no selected service (424 rows) | `unmatched_reason` |
| `expanded_schedule_without_ridership.csv` | scheduled service with no ride record (24 rows) | `missing_reason` |
| `features__delay1d/feature_rows.csv` | route × target date in the forecast-time schedule | the features in section 4, `split`, `eligible`, `excluded_reason` |
| `features__delay1d/feature_schema.json` | – | the feature schema (version 1.1.0): columns, types, issue-time rule |
| `groups__dev20251123_20260331/route_profiles.csv` | route (123 clustering profiles) | development-period weekday level, variability, weekend ratios, trip duration |
| `groups__…/route_group_membership.csv` | route (128, including 5 ungrouped) | `group_id`, `reason` |
| `groups__…/expanded_utilization_profiles.csv` | route × period × day type | sums, ratios, the three ranks with eligibility and reason |
| `groups__…/route_stop_overlap.csv` | route pair × timetable | `shared_stop_count`, `jaccard_stop_overlap`, `smaller_route_stop_overlap` |
| `geometry/route_shapes.csv` | route × direction × timetable | the most common path, as a simplified line |

Each folder has a `manifest.json` with the sha256 of every file. The importer checks these before it loads anything.

## 3. Database tables (PostgreSQL)

### Versions and sources
| Table | Holds |
|---|---|
| `dataset_versions` | one row per imported data version: analysis window (2025-11-23 to 2026-07-31), build and import commits, the Stage 2 manifest and the import report |
| `source_files` | the source register for that version (9 rows) |
| `gtfs_snapshots` | the 8 archives: `captured_date`, `active_start/end`, `applied_start/end` (the dates each one was used for) |
| `model_versions` | metadata for the frozen forecast model (`stage4a-1.0.0`, `rf_demand`): file path, sha256, freeze time, cutoffs, metrics; the `.joblib` file stays in `artifacts/` |

### Observations and schedule
| Table | Grain | Main columns |
|---|---|---|
| `daily_ridership` | route × date, 2001-01-01 to 2026-07-31 (1,120,604 rows) | `daytype`, `rides` (≥ 0), `source_snapshot_id` |
| `daily_schedule` | route × date, 2025-11-23 to 2026-07-31 (28,398 rows) | `snapshot_id` (one per date), `scheduled_trips`, `scheduled_service_hours` (NULL = incomplete), `duration_complete`, `trips_missing_duration` |
| `matched_utilization` | route × date with both (28,374 rows) | `rides`, trips, hours, `rides_per_scheduled_trip`, `rides_per_scheduled_hour` (NULL exactly when hours are NULL) |
| `ridership_without_schedule` | 424 rows | `rides`, `unmatched_reason`, `identifier_absent_from_all_archives` |
| `schedule_without_ridership` | 24 rows | `missing_reason` |

### Routes and geometry
| Table | Main columns |
|---|---|
| `routes` | `geometry_version` (= archive), `route`, GTFS `route_id`, short and long name |
| `route_shapes` | `direction_id`, `direction_label`, `shape_id`, `trip_days_using_shape` (selection measure), `line_geojson` ([lon, lat]) |

### Groups, rankings and overlap (Stage 5)
| Table | Main columns |
|---|---|
| `group_versions` | `profile_start/end` (2025-11-23 to 2026-03-31), `k` = 2, selected features, group names, caveats, model sha256 |
| `route_profiles` | per-route clustering profile, weekend `*_service_status` (`available` / `no_scheduled_service` / `insufficient_observations`), `base_eligible`, `ungrouped_reason` |
| `group_memberships` | `route`, `group_id` (NULL = ungrouped), `reason`, `group_name` |
| `utilization_profiles` | route × period × day type: `observed_days`, sums, `mean_daily_rides`, the two ratios, and for each of the three rankings `*_rank_eligible`, `*_rank_reason`, `*_rank` (ties share the lowest rank) |
| `route_stop_coverage` | per route and timetable: served and exclusive stop ids and counts |
| `route_stop_overlap` | per route pair: shared stops, `jaccard_stop_overlap`, `smaller_route_stop_overlap`, `overlap_review_rank`, `interpretation` ("corridor review only") |

### Replay (Stage 7)
| Table | Main columns |
|---|---|
| `forecast_targets` | route × target date in the forecast-time schedule: `forecast_snapshot` (captured before the day), trips, hours, `sunday_like_day`, `split` |
| `forecast_runs` | one frozen model + data version + delay policy: `model_sha256`, `model_method` (`rf_demand`), `baseline_method` (`seasonal_mean`), `reporting_delay_days` (1), `first_target`/`last_target` |
| `forecasts` | run × method × issue date × route × target (14,036 rows): `latest_ride_date` (< issue date), `input_snapshot`, `prediction` (NULL when unavailable), `status` (`forecast` / `unavailable`), `withheld_reason`, `created_at`. Written once; never updated |
| `replay_sessions` | `session_id`, `parent_session_id` (set by Reset), `start_date`, `virtual_date`, `final_date`, `reporting_delay_days`, `speed_seconds`, `status` (`paused` / `playing` / `complete`) |

### Scenarios (Stage 8)
| Table | Main columns |
|---|---|
| `scenarios` | `scenario_id` (`scn_` + content hash), `lineage_id`, `version`, `parent_scenario_id`, `name`, `origin` (`planner` / `example`), `mode`, `session_id` and `virtual_date` (replay only), `cutoff`, `data_version`, `group_version`, `baseline`, `inputs`, `assumptions`, `result` (JSON), `result_sha256`. A trigger refuses UPDATE and DELETE |

## 4. Forecasting features (`feature_contract.json`, built by `analytics/features/model_features.py::build_features`)
A forecast is issued at the start of the target day. With the 1-day reporting delay, the newest ride it may use is from the day before.

| Feature | Meaning |
|---|---|
| `route` | one-hot encoded, fitted on training rows; an unseen route gets all zeros |
| `day_of_week`, `month`, `is_weekend` | from the target date (Monday = 0) |
| `is_sunday_like_day` | 1 when more than half of the day's scheduled trips belong to Sunday-only services in the forecast-time archive (known before the day, unlike the reported `daytype`) |
| `boardings_1d_ago`, `_7d_`, `_14d_`, `_21d_ago` | rides on the same route exactly N days earlier (exact-date lookup; missing stays missing) |
| `boardings_28d_filled`, `boardings_28d_available` | the 28-day value, or the mean of the 7/14/21-day values when it is missing, plus a flag saying which |
| `seasonal_count`, `seasonal_mean` | how many of the 7/14/21/28-day values exist; their mean when at least two exist (also the "4-week average" baseline) |
| `scheduled_trips`, `scheduled_hours` | from the timetable captured before the target day (only in the `*_service` models) |

- **Never used as predictors:** `rides` (the target), the reported `daytype`, dates, the split, and the eligibility columns.
- **Eligibility:** a row is forecast only when the 1/7/14/21-day lags, the filled 28-day value, and the scheduled trips and hours all exist. Otherwise it is "unavailable" with the names of the missing fields.
