# Analysis tables

Generated CSVs live under `data/processed/new_york/`; `reports/eda/feature_schema.csv` records
every feature column's type and missing count. Each manifest records product row counts,
columns and SHA-256 hashes. These files are local and reproducible from the notebooks.

| Table | Unique grain | Main purpose |
|---|---|---|
| `daily_clean` | bus_route, payment_date | Original daily published counts plus quality flags and conservative analysis values |
| `hourly_clean` | bus_route, local_hour | Original route-hour estimates, local date and hour review flag |
| `route_crosswalk` | snapshot_id, route_id | Exact publisher code mapping and SBS display-name evidence |
| `route_date_coverage` | bus_route | First/last date, observed/zero/review days, absent dates inside observed span |
| `network_date_quality` / `network_hour_quality` | date / local hour | Past-only quality-screen comparisons |
| `daily_demand_features` | bus_route, payment_date | Calendar and exact-date retrospective lag candidates |
| `trip_template_features` | snapshot_id, trip_id | Duration, shape length, stop count and ordered pattern |
| `shape_features` | snapshot_id, shape_id | Polyline length, point count and geometry review |
| `calendar_expansion` | date | Selected whole feed, active services/trips, unavailable reasons |
| `pattern_service_date_features` | service_date, bus_route, direction_id, origin_stop_id, pattern_id | Comparable departure series and shape/duration summaries |
| `schedule_clock_daily` | bus_route, payment_date | Calendar-complete reviewed scheduled departures and service hours |
| `schedule_clock_hourly` | bus_route, local_hour | Hourly scheduled supply, partial diagnostic values, sources and eligibility |
| `matched_daily_features` | bus_route, payment_date | Demand-only history left-joined with eligible historical supply |
| `matched_hourly_features` | bus_route, local_hour | Actual hourly estimates left-joined to clock-hour scheduled supply |
| `route_day_type_profiles` | bus_route, day_type | Ratios of sums, sample dates and descriptive variation |
| `route_structure` | snapshot_id, bus_route | Template-weighted lengths/durations and shared/exclusive stop coverage |
| `route_overlap` | snapshot_id, route_a, route_b | Every unordered pair, including zero overlap |
| `map_stops`, `map_shapes`, `map_route_shapes` | stop_id / shape_id+sequence / route+shape | September geometry and route associations |

## Important columns

| Column | Meaning and missing-value policy |
|---|---|
| `published_boardings`, `ridership` | Publisher boarding estimates; original zero values preserved |
| `published_transfers`, `transfers` | Already included boarding subset, not additional passengers |
| `analysis_boardings` | Source value except missing where the conservative quality screen requires review |
| `payment_date`, `local_hour` | Publisher local payment clock date/hour, America/New_York; naive storage matches source |
| `service_date` | GTFS calendar date, possibly different from an overnight trip's clock date |
| `scheduled_departures` | Calendar-selected trip starts on the stated date/hour, not actual operated trips |
| `scheduled_service_hours` | Sum of scheduled first-departure-to-final-arrival intervals overlapping the clock period |
| `partial_scheduled_*` | Diagnostic contribution sums, not validated service denominators |
| `schedule_comparison_eligible` | Complete calendar context, no partial-calendar or held-out DST/block issue |
| `partial_calendar_review` | Retrospective same-snapshot/weekday screen detects exceptionally low active trip counts |
| `hourly_quality_screen_available` | Date lies within the observed hourly pilot; other dates lack this finer screen |
| `comparison_eligible` | Schedule eligibility plus available conservative demand; positive denominator is also needed for ratios |
| `source_snapshot`, `prior_source_snapshot` | Selected archive names for current and preceding service dates |
| `lag_1d`, `lag_7d`, etc. | Exact-date prior conservative count; missing if absent or flagged; not guaranteed available operationally |
| `past_same_weekday_mean` | Mean of available 7/14/21/28-day lags, only with at least two values |
| `pattern_id` | Hash of ordered stop IDs, including repeated visits; local descriptive grouping |
| `headway_gap_count` | Number of within-pattern consecutive departure gaps, departures minus one |
| `departure_span_hours` | Last minus first departure for that pattern/service date; not overnight circular coverage |
| `shape_length_km` | Haversine sum along supplied ordered geometry; not bus odometer or independently routed distance |
| `boardings_per_scheduled_*` | Descriptive boarding/service ratio on compatible observations; not occupancy/load factor |
| `exclusive_stop_ids` | Stops used only by this route within the selected Manhattan network and archive |
| `jaccard` | Shared unique stop IDs divided by union |
| `smaller_route_overlap` | Shared unique stop IDs divided by the smaller stop-set size |

Count-based profiles use the same eligible dates for numerator and denominator. Structural
template means weight each scheduled template once within its archive; they are not weighted by
how often the calendar activates that template over a year.
