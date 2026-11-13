# Stage 3 quality report: feature contracts

Generated 2026-11-13T04:49:28+00:00 by `analytics/features/build_stage3.py` (spec v3.8, sections 9.9, 9.10.2-9.10.4, 9.14.3). No model is trained in this stage.

- Data version: `cta_ref__r20261113__gtfs8__to20260731/features__delay1d` (built on Stage 2 version `cta_ref__r20261113__gtfs8__to20260731`)
- Code version: git `4789fef+uncommitted`; feature schema version 1.0.0
- Issue time: start of the target service day (00:00 local); **assumed reporting delay: 1 day(s)** (configurable in `analytics/config/features.json`; an assumption for the retrospective replay, not a verified feed capability)
- Reference comparisons: **42 MATCH, 0 MISMATCH**

> Reference counts are compared, never forced (spec 9.22.2). Absent lag dates stay missing; recorded zeros stay zero; targets are never filled.

## 1. Reference comparison

| section | metric | spec | ours | result | difference |
|---|---|---:|---:|---|---:|
| 9.3.3 | daily_forecasting_features rows | 83,997 | 83,997 | **MATCH** | +0 |
| 9.9.1 | daily_forecasting_features columns | 16 | 16 | **MATCH** | +0 |
| 9.9.2 | expanded_demand_service_features columns | 22 | 22 | **MATCH** | +0 |
| 9.10.3 | demand-only train rows | 63,143 | 63,143 | **MATCH** | +0 |
| 9.10.3 | demand-only validation rows | 10,246 | 10,246 | **MATCH** | +0 |
| 9.10.3 | demand-only test rows | 10,608 | 10,608 | **MATCH** | +0 |
| 9.10.3 | matched train rows | 14,501 | 14,501 | **MATCH** | +0 |
| 9.10.3 | matched validation rows | 6,859 | 6,859 | **MATCH** | +0 |
| 9.10.3 | matched test rows | 7,014 | 7,014 | **MATCH** | +0 |
| 9.9.3 | worked example route 1 2024-08-01: rides | 990 | 990 | **MATCH** | +0 |
| 9.9.3 | worked example route 1 2024-08-01: day_of_week | 3 | 3 | **MATCH** | +0 |
| 9.9.3 | worked example route 1 2024-08-01: lag_1d_boardings | 1,111 | 1,111 | **MATCH** | +0 |
| 9.9.3 | worked example route 1 2024-08-01: lag_7d_boardings | 1,219 | 1,219 | **MATCH** | +0 |
| 9.9.3 | worked example route 1 2024-08-01: lag_14d_boardings | 1,134 | 1,134 | **MATCH** | +0 |
| 9.9.3 | worked example route 1 2024-08-01: lag_21d_boardings | 1,040 | 1,040 | **MATCH** | +0 |
| 9.9.3 | worked example route 1 2024-08-01: lag_28d_boardings |  |  | **MATCH** |  |
| 9.9.3 | worked example route 1 2024-08-01: seasonal_lag_observations | 3 | 3 | **MATCH** | +0 |
| 9.9.3 | worked example route 1 2024-08-01: past_four_same_weekdays_mean | 1,131 | 1,131 | **MATCH** | +0 |
| 9.6.4.3 | matched rows missing 28-day lag | 182 | 182 | **MATCH** | +0 |
| 9.6.4.3 | missing 28-day lag, lag-date context: route_in_feed_no_active_trips | 145 | 145 | **MATCH** | +0 |
| 9.6.4.3 | missing 28-day lag, lag-date context: route_absent_from_feed | 25 | 25 | **MATCH** | +0 |
| 9.6.4.3 | missing 28-day lag, lag-date context: active_service_no_passenger_record | 12 | 12 | **MATCH** | +0 |
| 9.6.4.3 | missing 28-day lag, route 10 | 12 | 12 | **MATCH** | +0 |
| 9.6.4.3 | matched rows, route 10 | 55 | 55 | **MATCH** | +0 |
| 9.6.4.3 | missing 28-day lag, route 130 | 13 | 13 | **MATCH** | +0 |
| 9.6.4.3 | matched rows, route 130 | 55 | 55 | **MATCH** | +0 |
| 9.6.4.3 | matched rows missing 1-day lag | 1,453 | 1,453 | **MATCH** | +0 |
| 9.6.4.3 | missing 1-day lag: active scheduled service, no passenger record | 4 | 4 | **MATCH** | +0 |
| 9.6.4.3 | missing 1-day lag: no active trips on lag date (all other contexts) | 1,449 | 1,449 | **MATCH** | +0 |
| 9.10.2 | option_1 withheld, matched train | 1,073 | 1,073 | **MATCH** | +0 |
| 9.10.2 | option_1 withheld, matched validation | 299 | 299 | **MATCH** | +0 |
| 9.10.2 | option_1 withheld, matched test | 523 | 523 | **MATCH** | +0 |
| 9.10.2 | option_2 withheld, matched train | 1,036 | 1,036 | **MATCH** | +0 |
| 9.10.2 | option_2 withheld, matched validation | 299 | 299 | **MATCH** | +0 |
| 9.10.2 | option_2 withheld, matched test | 472 | 472 | **MATCH** | +0 |
| 9.10.2 | option_1 withheld, matched total | 1,895 | 1,895 | **MATCH** | +0 |
| 9.10.2 | option_2 extra eligible test rows vs option_1 | 51 | 51 | **MATCH** | +0 |
| 9.10.3 | demand-only: dates shared between splits | 0 | 0 | **MATCH** | +0 |
| 9.10.3 | matched: dates shared between splits | 0 | 0 | **MATCH** | +0 |
| 9.9.2 | matched: service_date equals date | True | True | **MATCH** |  |
| 9.14.3 | matched: descriptive archive unusable for forecasting exactly on boundary dates | True | True | **MATCH** |  |
| 9.14.3 | forecast inputs: every archive captured strictly before target date | True | True | **MATCH** |  |

## 2. Policy coverage before model fitting (Option 2 selected, Option 1 comparison)

Matched rows use the descriptive Stage 2 schedule (the spec's reference construction). `matched_forecast_schedule` repeats the check with the forecast-input schedule (section 4).

| table | policy | split | target rows | eligible | withheld |
|---|---|---|---|---|---|
| demand | option_1 | train | 63,143 | 58,856 | 4,287 |
| demand | option_1 | validation | 10,246 | 9,705 | 541 |
| demand | option_1 | test | 10,608 | 9,873 | 735 |
| demand | option_2 | train | 63,143 | 59,066 | 4,077 |
| demand | option_2 | validation | 10,246 | 9,709 | 537 |
| demand | option_2 | test | 10,608 | 9,924 | 684 |
| matched | option_1 | train | 14,501 | 13,428 | 1,073 |
| matched | option_1 | validation | 6,859 | 6,560 | 299 |
| matched | option_1 | test | 7,014 | 6,491 | 523 |
| matched_forecast_schedule | option_1 | train | 14,501 | 13,342 | 1,159 |
| matched_forecast_schedule | option_1 | validation | 6,859 | 6,560 | 299 |
| matched_forecast_schedule | option_1 | test | 7,014 | 6,491 | 523 |
| matched | option_2 | train | 14,501 | 13,465 | 1,036 |
| matched | option_2 | validation | 6,859 | 6,560 | 299 |
| matched | option_2 | test | 7,014 | 6,542 | 472 |
| matched_forecast_schedule | option_2 | train | 14,501 | 13,379 | 1,122 |
| matched_forecast_schedule | option_2 | validation | 6,859 | 6,560 | 299 |
| matched_forecast_schedule | option_2 | test | 7,014 | 6,542 | 472 |

Withheld reasons (a row can have several):

| table | policy | reason | rows |
|---|---|---|---|
| demand | option_1 | missing_rides_1_day_before | 4,279 |
| demand | option_1 | missing_rides_28_days_before | 841 |
| demand | option_1 | missing_rides_21_days_before | 775 |
| demand | option_1 | missing_rides_14_days_before | 721 |
| demand | option_1 | missing_rides_7_days_before | 596 |
| demand | option_2 | missing_rides_1_day_before | 4,279 |
| demand | option_2 | missing_rides_21_days_before | 775 |
| demand | option_2 | missing_rides_14_days_before | 721 |
| demand | option_2 | missing_rides_7_days_before | 596 |
| demand | option_2 | no_donor_for_rides_28_days_before | 101 |
| matched | option_1 | missing_rides_1_day_before | 1,453 |
| matched | option_1 | missing_rides_21_days_before | 201 |
| matched | option_1 | missing_rides_14_days_before | 191 |
| matched | option_1 | missing_rides_28_days_before | 182 |
| matched | option_1 | missing_rides_7_days_before | 155 |
| matched_forecast_schedule | option_1 | missing_rides_1_day_before | 1,453 |
| matched_forecast_schedule | option_1 | missing_rides_21_days_before | 201 |
| matched_forecast_schedule | option_1 | missing_rides_14_days_before | 191 |
| matched_forecast_schedule | option_1 | missing_rides_28_days_before | 182 |
| matched_forecast_schedule | option_1 | missing_rides_7_days_before | 155 |
| matched_forecast_schedule | option_1 | missing_schedule | 86 |
| matched | option_2 | missing_rides_1_day_before | 1,453 |
| matched | option_2 | missing_rides_21_days_before | 201 |
| matched | option_2 | missing_rides_14_days_before | 191 |
| matched | option_2 | missing_rides_7_days_before | 155 |
| matched | option_2 | no_donor_for_rides_28_days_before | 2 |
| matched_forecast_schedule | option_2 | missing_rides_1_day_before | 1,453 |
| matched_forecast_schedule | option_2 | missing_rides_21_days_before | 201 |
| matched_forecast_schedule | option_2 | missing_rides_14_days_before | 191 |
| matched_forecast_schedule | option_2 | missing_rides_7_days_before | 155 |
| matched_forecast_schedule | option_2 | missing_schedule | 86 |
| matched_forecast_schedule | option_2 | no_donor_for_rides_28_days_before | 2 |

Routes 10 and 130 (absent from schedule-augmented training; reported separately, spec 9.10.2):

| route | policy | matched rows | splits | eligible | withheld | missing 28-day lag |
|---|---|---|---|---|---|---|
| 10 | option_1 | 55 | test | 43 | 12 | 12 |
| 10 | option_2 | 55 | test | 50 | 5 | 12 |
| 130 | option_1 | 55 | test | 42 | 13 | 13 |
| 130 | option_2 | 55 | test | 49 | 6 | 13 |

For option_2 the last column counts rows whose 28-day lag was filled (flag 0).

## 3. Missing history

Missing lags by table and split (before any filling):

| table | split | lag_1d_boardings | lag_7d_boardings | lag_14d_boardings | lag_21d_boardings | lag_28d_boardings | seasonal mean missing |
|---|---|---|---|---|---|---|---|
| demand-only | train | 3,270 | 450 | 561 | 605 | 647 | 147 |
| demand-only | validation | 500 | 29 | 32 | 34 | 38 | 24 |
| demand-only | test | 509 | 117 | 128 | 136 | 156 | 50 |
| matched | train | 813 | 75 | 112 | 112 | 75 | 1 |
| matched | validation | 294 | 4 | 4 | 3 | 4 | 3 |
| matched | test | 346 | 76 | 75 | 86 | 103 | 2 |

Schedule context of the earlier lag date, for matched target rows (spec 9.6.4.3):

| lag | context of the earlier lag date | matched target rows |
|---|---|---|
| 28-day | route_in_feed_no_active_trips | 145 |
| 28-day | route_absent_from_feed | 25 |
| 28-day | active_service_no_passenger_record | 12 |
| 1-day | route_in_feed_no_active_trips | 1,449 |
| 1-day | active_service_no_passenger_record | 4 |

Per route/split/lag counts: `lag_absence_by_route_split.csv`.

## 4. Forecast-input schedule selection (spec 9.14.3)

Descriptive (Stage 2, unchanged): latest archive captured on/before D. Forecast input: latest archive captured **strictly before** D (only capture dates are known). The two differ only on capture dates; on those dates the forecast schedule is rebuilt from the earlier archive.

| date | descriptive archive | forecast archive | matched rows | available | trip diffs | hours diffs | status |
|---|---|---|---|---|---|---|---|
| 2025-11-23 | mdb-389-202511230128 |  | 86 | 0 | 0 | 0 | no_archive_available_before_issue 86 |
| 2025-12-19 | mdb-389-202512190112 | mdb-389-202511230128 | 123 | 123 | 0 | 0 | available 123 |
| 2026-01-08 | mdb-389-202601080131 | mdb-389-202512190112 | 123 | 123 | 0 | 0 | available 123 |
| 2026-02-10 | mdb-389-202602100132 | mdb-389-202601080131 | 123 | 123 | 0 | 0 | available 123 |
| 2026-03-26 | mdb-389-202603260020 | mdb-389-202602100132 | 123 | 123 | 0 | 0 | available 123 |
| 2026-04-24 | mdb-389-202604240144 | mdb-389-202603260020 | 123 | 123 | 0 | 0 | available 123 |
| 2026-05-30 | mdb-389-202605300003 | mdb-389-202604240144 | 92 | 92 | 0 | 0 | available 92 |
| 2026-07-11 | mdb-389-202607110020 | mdb-389-202605300003 | 92 | 92 | 0 | 0 | available 92 |

Matched rows whose forecast-input schedule differs from the descriptive one: 86. Rows with no forecast schedule available: 86 (available 28288, no_archive_available_before_issue 86).

## 5. Issue-time Sunday/holiday predictor vs reported daytype

`is_sunday_holiday_service_day` = Sunday or an observed date of the fixed holiday list (12 dates in `features.json`, observance rule `us_federal_observed`: a Saturday holiday is observed on the Friday before, a Sunday holiday on the Monday after). It never reads the target-date ridership row. Rows where it differs from the reported `is_sunday_holiday_daytype`: **0** of 83,997. Dates with any disagreement: **0**:

(none)

## Outputs

| file | rows | columns | sha256 (first 16) |
|---|---:|---:|---|
| `daily_forecasting_features.csv` | 83,997 | 16 | `53de2b7c949ddb4b` |
| `expanded_demand_service_features.csv` | 28,374 | 22 | `eae71f200e280083` |
| `forecast_schedule_inputs.csv` | 28,374 | 10 | `a5f6f0f0eb281a55` |
| `policy_eligibility_demand.csv` | 83,997 | 9 | `914ee38891be99c5` |
| `policy_eligibility_matched.csv` | 28,374 | 11 | `05ebe074fb3b5ace` |
| `lag_absence_by_route_split.csv` | 753 | 10 | `74603383df9eb307` |
| `feature_schema.json` | | | |
