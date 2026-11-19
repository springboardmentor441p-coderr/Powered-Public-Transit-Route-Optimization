# Stage 5 quality report: route groups and ranking

Generated 2026-11-19T10:11:18+00:00 by `analytics/groups/build_stage5.py` (spec 9.7, 9.11, 9.12; stage table 9.18). The spec wins where it differs from the mentor's notebook; the notebook's rules are recomputed in section 7.

- Data products: `cta_ref__r20261113__gtfs8__to20260731/groups__dev20251123_20260331`; settings `groups.json` sha256 `7c945470be0f480a`; names `group_names.json` sha256 `7104d7cde764d02b`
- Code version: git `3cae46f`; artifact version `stage5-1.0.0`
- Development profile period (groups): 2025-11-23..2026-03-31. Reference ranking period: `full_matched_window` (2025-11-23..2026-07-31), a historical-analysis table: it includes the June-July replay period, so replay mode must recompute rankings from revealed history only (Stage 7).
- Gates (spec 9.7.2 trial values, applied independently): ranking 20 observed days; clustering base 20 weekdays; weekend ratio 8 days

## Summary

- **123** routes grouped into **k = 2** groups (chosen by the fixed rule); **5** of 128 routes in the ridership window ungrouped, each with a reason.
- Group 0: **Higher-demand, seven-day routes** (67 routes)
- Group 1: **Lower-demand routes, often with limited or no weekend service** (56 routes)
- k = 2 is a **near tie** with k = 3 (0.381 vs 0.383, a difference of 0.002). A silhouette of 0.38 means **moderate separation**: real structure, but with routes near the boundary between groups (1 = tight, well-separated groups; 0 = groups that blur together).
- Rankings: three named indicators, ties preserved, unranked rows kept with their observed-day count and a reason. Reference period, routes ranked by rides per scheduled hour (W/A/U): 125 / 92 / 86.
- Route overlap review: 8 geometry versions; default review version `mdb-389-202603260020`. **Corridor review only**, not merge/split evidence.
- Not built yet: forecast demand/service review (needs served forecasts from the replay, Stage 7).

## 1. Rankings (spec 9.7.1, 9.12)

Ratios are ratios of sums over the same matched dates. The hours ratio is unavailable when any included day has incomplete durations. Ties share the lowest rank. Every route in a period has W, A and U rows; an ineligible row stays **unranked** with its observed-day count and a reason. "No scheduled service of this day type" means the schedule shows no trips; it is not missing data.

| period | day type | routes | ranked: observed daily demand (mean rides/day) | ranked: rides per scheduled trip | ranked: rides per scheduled hour | unranked | unranked reasons |
|---|---|---|---|---|---|---|---|
| full_matched_window | W | 125 | 125 | 125 | 125 | 0 |  |
| full_matched_window | A | 125 | 92 | 92 | 92 | 33 | no scheduled service of this day type: 30; fewer than 20 observed days (n): 3 |
| full_matched_window | U | 125 | 86 | 86 | 86 | 39 | no scheduled service of this day type: 36; fewer than 20 observed days (n): 3 |
| development | W | 123 | 123 | 123 | 123 | 0 |  |
| development | A | 123 | 0 | 0 | 0 | 123 | fewer than 20 observed days (n): 93; no scheduled service of this day type: 30 |
| development | U | 123 | 86 | 86 | 86 | 37 | no scheduled service of this day type: 36; no matched days of this day type: 1 |

Identities (every matched row counted exactly once; no rank on an ineligible row): `full_matched_window` rides True, trips True, days True, three day types per route True, no rank on an ineligible row True; `development` rides True, trips True, days True, three day types per route True, no rank on an ineligible row True.

Unranked rows in the reference period other than "no scheduled service" (all rows are in `reports/stage5_rankings.csv`):

| route | daytype | observed_days | scheduled_service_days | observed_daily_demand_rank_reason |
|---|---|---|---|---|
| 10 | A | 7 | 7 | fewer than 20 observed days (7) |
| 10 | U | 9 | 9 | fewer than 20 observed days (9) |
| 130 | A | 7 | 7 | fewer than 20 observed days (7) |
| 130 | U | 9 | 9 | fewer than 20 observed days (9) |
| 169 | A | 15 | 35 | fewer than 20 observed days (15) |
| 169 | U | 2 | 5 | fewer than 20 observed days (2) |

**Gate sensitivity** (reported only; the configured gate of 20 is unchanged). Routes ranked by rides per scheduled hour at each gate value:

| period_name | daytype | gate 8 | gate 12 | gate 16 | gate 20 |
|---|---|---|---|---|---|
| development | A | 92 | 92 | 92 | 0 |
| development | U | 86 | 86 | 86 | 86 |
| development | W | 123 | 123 | 123 | 123 |
| full_matched_window | A | 93 | 93 | 92 | 92 |
| full_matched_window | U | 88 | 86 | 86 | 86 |
| full_matched_window | W | 125 | 125 | 125 | 125 |

Reference period, day type W: top 10 by rides per scheduled hour, with the other two named ranks

| route | observed_days | rides_per_scheduled_hour | service_productivity_metric_rank | rides_per_scheduled_trip | rides_per_trip_rank | mean_daily_rides | observed_daily_demand_rank |
|---|---|---|---|---|---|---|---|
| 134 | 175 | 59.157 | 1 | 39.222 | 28 | 1,795.686 | 81 |
| 172 | 175 | 55.254 | 2 | 14.283 | 94 | 1,506.783 | 86 |
| 171 | 175 | 54.586 | 3 | 11.367 | 104 | 791.474 | 107 |
| 85 | 175 | 52.793 | 4 | 42.391 | 22 | 7,802.183 | 31 |
| 81 | 175 | 51.470 | 5 | 34.686 | 41 | 9,027.074 | 23 |
| 49B | 175 | 50.528 | 6 | 15.299 | 89 | 3,499.051 | 60 |
| 155 | 175 | 50.320 | 7 | 23.236 | 69 | 4,751.669 | 51 |
| 92 | 175 | 48.915 | 8 | 31.187 | 52 | 5,024.531 | 49 |
| 147 | 175 | 48.874 | 9 | 44.276 | 17 | 9,252.663 | 21 |
| 20 | 175 | 48.717 | 10 | 39.343 | 26 | 13,880.434 | 9 |

Reference period, day type A: top 10 by rides per scheduled hour, with the other two named ranks

| route | observed_days | rides_per_scheduled_hour | service_productivity_metric_rank | rides_per_scheduled_trip | rides_per_trip_rank | mean_daily_rides | observed_daily_demand_rank |
|---|---|---|---|---|---|---|---|
| 124 | 35 | 54.869 | 1 | 18.134 | 56 | 1,621.200 | 63 |
| 81 | 35 | 49.582 | 2 | 32.719 | 29 | 7,564.543 | 19 |
| 49B | 35 | 48.853 | 3 | 14.088 | 67 | 2,473.771 | 53 |
| 20 | 35 | 48.207 | 4 | 36.766 | 20 | 9,135.829 | 15 |
| 22 | 35 | 48.143 | 5 | 63.178 | 1 | 14,153.657 | 2 |
| 146 | 35 | 47.168 | 6 | 49.342 | 7 | 9,473.657 | 14 |
| 85 | 35 | 46.963 | 7 | 35.600 | 22 | 5,340.029 | 35 |
| 155 | 35 | 45.814 | 8 | 20.454 | 53 | 3,722.714 | 48 |
| 36 | 35 | 45.665 | 9 | 62.723 | 2 | 11,299.057 | 11 |
| 92 | 35 | 45.534 | 10 | 26.962 | 44 | 3,149.114 | 49 |

Reference period, day type U: top 10 by rides per scheduled hour, with the other two named ranks

| route | observed_days | rides_per_scheduled_hour | service_productivity_metric_rank | rides_per_scheduled_trip | rides_per_trip_rank | mean_daily_rides | observed_daily_demand_rank |
|---|---|---|---|---|---|---|---|
| 81 | 41 | 48.763 | 1 | 27.961 | 35 | 6,000.024 | 19 |
| 155 | 41 | 47.584 | 2 | 20.472 | 49 | 2,988.878 | 48 |
| 3 | 41 | 47.557 | 3 | 62.818 | 1 | 9,303.195 | 9 |
| 146 | 41 | 45.790 | 4 | 42.575 | 8 | 7,195.146 | 17 |
| 76 | 41 | 45.679 | 5 | 41.624 | 10 | 3,916.683 | 37 |
| 20 | 41 | 45.562 | 6 | 32.905 | 21 | 8,028.829 | 13 |
| 92 | 41 | 44.675 | 7 | 24.292 | 42 | 2,509.780 | 49 |
| 49B | 41 | 44.309 | 8 | 12.135 | 67 | 1,916.122 | 53 |
| 85 | 41 | 44.081 | 9 | 31.354 | 24 | 4,264.122 | 33 |
| 74 | 41 | 43.674 | 10 | 33.629 | 19 | 5,278.902 | 24 |

## 2. Clustering profiles and features (spec 9.11.2)

- 123 routes in the development period; 123 pass the base gate.
- Weekend status from the schedule: no scheduled service gives a **structural zero** (no buses ran); service with too few matched days is **unavailable** (filled in section 3); otherwise the measured ratio.

| day type | available | no_scheduled_service | insufficient_observations |
|---|---|---|---|
| saturday | 92 | 30 | 1 |
| sunday_holiday | 86 | 36 | 1 |

Feature decisions (fixed rules, in priority order):

| feature | kept | availability | reason |
|---|---|---|---|
| mean_weekday_rides | True | 100.000 |  |
| weekday_rides_cv | True | 100.000 |  |
| saturday_to_weekday_rides_ratio | False | 99.200 | |Spearman| 0.812 with `weekday_rides_cv` (kept, higher priority) |
| sunday_holiday_to_weekday_rides_ratio | True | 99.200 |  |
| mean_weekday_scheduled_trips | False | 100.000 | |Spearman| 0.906 with `mean_weekday_rides` (kept, higher priority) |
| weekday_rides_per_scheduled_hour | True | 100.000 |  |
| mean_weekday_trip_duration_minutes | True | 100.000 |  |

- **Knife-edge result (kept as the fixed rule decided, disclosed here):** the Saturday and Sunday/holiday ratios correlate at |ρ| = 0.951, so they carry nearly the same information. `saturday_to_weekday_rides_ratio` was dropped at |ρ| = 0.812 against `weekday_rides_cv`; `sunday_holiday_to_weekday_rides_ratio` stayed at |ρ| = 0.798, against a bar of 0.8. Weekend shape is still represented, through the kept ratio; a difference of 0.014 decided which weekend day stands for it. Part of the correlation with CV likely comes from the structural zeros (weekday-only routes tend to be peak-heavy and more variable).
- Pairs within 0.02 of the bar (0.8): `weekday_rides_cv` vs `saturday_to_weekday_rides_ratio`: |ρ| = 0.812; `weekday_rides_cv` vs `sunday_holiday_to_weekday_rides_ratio`: |ρ| = 0.798.

Spearman correlations (base-eligible routes):

| feature | mean_weekday_rides | weekday_rides_cv | saturday_to_weekday_rides_ratio | sunday_holiday_to_weekday_rides_ratio | mean_weekday_scheduled_trips | weekday_rides_per_scheduled_hour | mean_weekday_trip_duration_minutes |
|---|---|---|---|---|---|---|---|
| mean_weekday_rides | 1.000 | -0.700 | 0.633 | 0.674 | 0.906 | 0.653 | 0.773 |
| weekday_rides_cv | -0.700 | 1.000 | -0.812 | -0.798 | -0.747 | -0.327 | -0.438 |
| saturday_to_weekday_rides_ratio | 0.633 | -0.812 | 1.000 | 0.951 | 0.696 | 0.317 | 0.389 |
| sunday_holiday_to_weekday_rides_ratio | 0.674 | -0.798 | 0.951 | 1.000 | 0.760 | 0.348 | 0.397 |
| mean_weekday_scheduled_trips | 0.906 | -0.747 | 0.696 | 0.760 | 1.000 | 0.506 | 0.511 |
| weekday_rides_per_scheduled_hour | 0.653 | -0.327 | 0.317 | 0.348 | 0.506 | 1.000 | 0.356 |
| mean_weekday_trip_duration_minutes | 0.773 | -0.438 | 0.389 | 0.397 | 0.511 | 0.356 | 1.000 |

## 3. Imputation (service-aware median)

Fitted on development profiles only. A weekend ratio's median comes **only from routes that have that service**; structural zeros are never filled and never enter the median. A naive median over all values is shown for comparison only. The pipeline works on log1p(weekday rides), so that row's medians are in log1p units; the original-units column converts them back (e.g. log1p 8.058 is about 3,160 rides a day).

| feature | units | fitted median | fitted median (original units) | naive median (all values) | filled routes |
|---|---|---|---|---|---|
| mean_weekday_rides | log1p | 8.058 | 3,157.910 | 8.058 |  |
| weekday_rides_cv | original | 0.169 | 0.169 | 0.169 |  |
| sunday_holiday_to_weekday_rides_ratio | original | 0.511 | 0.511 | 0.430 | 169 |
| weekday_rides_per_scheduled_hour | original | 33.265 | 33.265 | 33.265 |  |
| mean_weekday_trip_duration_minutes | original | 44.103 | 44.103 | 44.103 |  |

## 4. Number of groups (spec 9.11.3)

| k | group_sizes | smallest_group | passes_size_gate | silhouette | stability_ari_mean | stability_ari_min | period_halves_ari | period_halves_routes |
|---|---|---|---|---|---|---|---|---|
| 2 | 67, 56 | 56 | True | 0.381 | 1.000 | 1.000 | 0.873 | 123 |
| 3 | 62, 20, 41 | 20 | True | 0.383 | 0.986 | 0.977 | 0.755 | 123 |
| 4 | 17, 50, 21, 35 | 17 | True | 0.327 | 0.892 | 0.802 | 0.686 | 123 |
| 5 | 32, 19, 12, 12, 48 | 12 | True | 0.337 | 0.978 | 0.967 | 0.875 | 123 |
| 6 | 38, 18, 12, 12, 14, 29 | 12 | True | 0.298 | 0.913 | 0.830 | 0.780 | 123 |

- Rule (fixed in `groups.json` before any result): among k whose smallest group has ≥ 5 routes, take the smallest k within 0.02 of the best silhouette.
- **Chosen by the fixed rule: k = 2.** It is a **near tie** with k = 3 (0.381 vs 0.383, a difference of 0.002).
- Stability: seed adjusted Rand mean 1.000 (min 1.000); agreement between the two half-periods 0.873.
- A silhouette of 0.38 means **moderate separation**: real structure, but with routes near the boundary between groups (1 = tight, well-separated groups; 0 = groups that blur together).

## 5. Groups and explanations

Median (min-max) in original units; * marks clustering features. Names were chosen after inspection and are applied only because the frozen memberships equal those in `analytics/config/group_names.json`.

| feature | group 0: Higher-demand, seven-day routes (n=67) | group 1: Lower-demand routes, often with limited or no weekend service (n=56) |
|---|---|---|
| mean_weekday_rides * | 7044.000 (1924.80-17082.93) | 1039.983 (126.71-4094.79) |
| weekday_rides_cv * | 0.146 (0.09-0.27) | 0.224 (0.13-0.48) |
| saturday_to_weekday_rides_ratio | 0.691 (0.00-1.09) | 0.271 (0.00-1.29) |
| sunday_holiday_to_weekday_rides_ratio * | 0.527 (0.00-0.82) | 0.000 (0.00-0.98) |
| mean_weekday_scheduled_trips | 205.494 (86.00-457.88) | 82.500 (9.79-173.51) |
| weekday_rides_per_scheduled_hour * | 37.845 (23.76-51.07) | 26.471 (13.02-59.52) |
| mean_weekday_trip_duration_minutes * | 53.565 (18.09-91.78) | 29.730 (12.49-75.50) |

Weekend service status by group:

| group | saturday available | saturday no_scheduled_service | saturday insufficient_observations | sunday_holiday available | sunday_holiday no_scheduled_service | sunday_holiday insufficient_observations |
|---|---|---|---|---|---|---|
| 0: Higher-demand, seven-day routes | 63 | 4 | 0 | 63 | 4 | 0 |
| 1: Lower-demand routes, often with limited or no weekend service | 29 | 26 | 1 | 23 | 32 | 1 |

Centroids in original units:

| group | name | mean_weekday_rides | weekday_rides_cv | sunday_holiday_to_weekday_rides_ratio | weekday_rides_per_scheduled_hour | mean_weekday_trip_duration_minutes |
|---|---|---|---|---|---|---|
| 0 | Higher-demand, seven-day routes | 6,652.843 | 0.151 | 0.509 | 37.215 | 56.704 |
| 1 | Lower-demand routes, often with limited or no weekend service | 957.198 | 0.257 | 0.176 | 28.206 | 32.421 |

**Caveats** (stored with the names):

- Names describe each group's typical member; ranges overlap (group 1's busiest route, 4,095 weekday rides, is busier than group 0's quietest, 1,925; rides per scheduled hour overlap 13-60 vs 24-51).
- A group is not a performance grade; group numbers are not an order of efficiency. A lower-demand route may serve coverage obligations.
- Separation is moderate (silhouette 0.38; k = 2 chosen by the fixed rule, a near tie with k = 3 at 0.383).
- Fitted on the development period only; later observations do not change memberships or names.

Ungrouped routes:

| route | reason |
|---|---|
| 10 | no matched days in the development profile period |
| 1001 | no matched schedule in the ridership window (ridership-only identifier) |
| 128 | no matched schedule in the ridership window (ridership-only identifier) |
| 130 | no matched days in the development profile period |
| 19 | no matched schedule in the ridership window (ridership-only identifier) |

- Group 0 (Higher-demand, seven-day routes) routes: 119, 12, 126, 146, 147, 15, 151, 152, 155, 157, 18, 20, 21, 22, 26, 28, 29, 3, 34, 35, 36, 4, 47, 49, 49B, 50, 52, 52A, 53, 54, 55, 56, 6, 60, 62, 63, 65, 66, 67, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 8, 80, 81, 82, 85, 87, 8A, 9, 90, 91, 92, 93, 94, 95, 97, J14, X49, X9
- Group 1 (Lower-demand routes, often with limited or no weekend service) routes: 1, 100, 103, 106, 108, 11, 111, 111A, 112, 115, 120, 121, 124, 125, 134, 135, 136, 143, 148, 156, 165, 169, 171, 172, 192, 2, 201, 206, 24, 30, 31, 37, 39, 43, 44, 48, 51, 53A, 54A, 54B, 55A, 55N, 57, 59, 62H, 63W, 68, 7, 81W, 84, 85A, 86, 88, 96, N5, X4

## 6. Route stop coverage and overlap (spec 9.7, 9.12)

Geometry version = GTFS archive; served stops come from bus trips active on the archive's applied dates. Identities hold per version and for all versions combined: True.

| geometry_version | applied_dates | routes | served stops | sharing pairs | median exclusive share | identities hold |
|---|---|---|---|---|---|---|
| mdb-389-202511230128 | 2025-11-23..2025-12-18 | 123 | 10,684 | 692 | 0.661 | True |
| mdb-389-202512190112 | 2025-12-19..2026-01-07 | 123 | 10,727 | 710 | 0.653 | True |
| mdb-389-202601080131 | 2026-01-08..2026-02-09 | 123 | 10,675 | 699 | 0.653 | True |
| mdb-389-202602100132 | 2026-02-10..2026-03-25 | 123 | 10,675 | 699 | 0.653 | True |
| mdb-389-202603260020 | 2026-03-26..2026-04-23 | 123 | 10,729 | 703 | 0.653 | True |
| mdb-389-202604240144 | 2026-04-24..2026-05-29 | 123 | 10,709 | 695 | 0.661 | True |
| mdb-389-202605300003 | 2026-05-30..2026-07-10 | 125 | 10,722 | 748 | 0.656 | True |
| mdb-389-202607110020 | 2026-07-11..2026-07-31 | 125 | 10,670 | 774 | 0.661 | True |

Default review version `mdb-389-202603260020`: top 10 pairs by Jaccard (ties share the rank).

**Corridor review only:** shared stop IDs are not merge/split evidence (no direction, walking access, transfers or journeys). Smaller-route overlap of 1.000 means every stop of the smaller route is also on the other route.

| route_a | route_b | route_a_stop_count | route_b_stop_count | shared_stop_count | jaccard_stop_overlap | smaller_route_stop_overlap | overlap_review_rank |
|---|---|---|---|---|---|---|---|
| 120 | 121 | 18 | 20 | 17 | 0.810 | 0.944 | 1 |
| 108 | 8A | 89 | 121 | 70 | 0.500 | 0.787 | 2 |
| 49 | X49 | 164 | 71 | 71 | 0.433 | 1.000 | 3 |
| 119 | 34 | 95 | 104 | 53 | 0.363 | 0.558 | 4 |
| 201 | 206 | 120 | 153 | 68 | 0.332 | 0.567 | 5 |
| 146 | 148 | 103 | 62 | 40 | 0.320 | 0.645 | 6 |
| 134 | 143 | 37 | 45 | 19 | 0.302 | 0.514 | 7 |
| 134 | 156 | 37 | 85 | 28 | 0.298 | 0.757 | 8 |
| 4 | X4 | 254 | 76 | 73 | 0.284 | 0.961 | 9 |
| 9 | X9 | 241 | 74 | 68 | 0.275 | 0.919 | 10 |

## 7. Mentor notebook comparison (its rules recomputed; reads our outputs only)

| item | value |
|---|---|
| notebook (forecast-time rows with rides, train) | 14,415 |
| notebook routes | 123 |
| notebook first date | 2025-11-24 |
| notebook valid profiles (recomputed) | 86 |
| notebook valid profiles (stated) | 86 |
| ours base-eligible | 123 |
| in ours, not in notebook | 37 |
| in notebook, not in ours | 0 |
| notebook exclusion reasons | {"fewer than 8 Saturdays or 8 Sundays/holidays in training": 37} |

Routes the notebook drops, by their weekend status in our profiles:

| saturday_service_status | sunday_holiday_service_status | routes |
|---|---|---|
| no_scheduled_service | no_scheduled_service | 30 |
| available | no_scheduled_service | 6 |
| insufficient_observations | insufficient_observations | 1 |

- Features: notebook (fixed) log_weekday_boardings, weekday_variability, saturday_to_weekday_ratio, sunday_holiday_to_weekday_ratio, log_weekday_scheduled_trips; ours (selected by rule) mean_weekday_rides, weekday_rides_cv, sunday_holiday_to_weekday_rides_ratio, weekday_rides_per_scheduled_hour, mean_weekday_trip_duration_minutes.
- Groups: notebook k = 2, ours k = 2; agreement {"routes_grouped_by_both": 86, "adjusted_rand": 0.5757410251616821}.

Notebook k table:

| k | group_sizes | smallest_group | passes_size_gate | silhouette | stability_ari_mean |
|---|---|---|---|---|---|
| 2 | 29, 57 | 29 | True | 0.413 | 1.000 |
| 3 | 27, 56, 3 | 3 | False | 0.428 | 1.000 |
| 4 | 17, 31, 3, 35 | 3 | False | 0.314 | 1.000 |
| 5 | 32, 29, 20, 3, 2 | 2 | False | 0.300 | 0.766 |
| 6 | 10, 18, 28, 23, 3, 4 | 3 | False | 0.265 | 0.841 |

Rides per scheduled hour, notebook training-period ranking vs our development-period ranking:

| daytype | routes ranked (notebook) | routes ranked (ours) | common routes | rank Spearman on common routes | tied values kept by ours |
|---|---|---|---|---|---|
| W | 123 | 123 | 123 | 1.000 | 0 |
| A | 0 | 0 | 0 |  | 0 |
| U | 86 | 86 | 86 | 1.000 | 0 |

## 8. Saved artifact and reproducibility

- `artifacts/stage5/route_groups.joblib` (imputer + scaler + KMeans): 2,149 bytes uncompressed, **1,237** saved (compress 3), under 20 MB True, sha256 `33d2d42a9b77cbe4`; reload reproduces the memberships exactly: True.
- One thread for every KMeans fit/predict; fixed seeds; no timestamps inside the artifact or data CSVs, so a rerun must give identical hashes.
- Data products: `expanded_utilization_profiles.csv` 744 rows (`d4d394cd43bc`), `route_profiles.csv` 123 rows (`df1811b76218`), `route_group_membership.csv` 128 rows (`a12881ca41ff`), `route_stop_coverage.csv` 988 rows (`5588822fe671`), `route_stop_overlap.csv` 5,720 rows (`7688353b4e74`)
- Runtime: python 3.12.10, pandas 3.1.1, numpy 2.5.4, scikit-learn 1.9.1, joblib 1.6.0, duckdb 2.0.0, threadpoolctl 3.8.0

## 9. Limitations

- Groups and rankings describe patterns, not route quality or performance; nothing here justifies a service cut.
- The reference ranking period includes June-July (the replay period); it is a historical-analysis table only.
- Overlap uses shared stop IDs only (no direction, time of day, walking access, transfers or journeys).
- Archives are verified as in Stage 2: each registered ZIP's sha256 is checked and its extracted files are read. The extracted .txt files themselves are not re-hashed here or in Stage 2.
- The 9.7.2 gates are CTA trial values, not validated sample sizes; see the gate sensitivity table.
