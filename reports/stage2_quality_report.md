# Stage 2 quality report: daily reconstruction and exact matching

Generated 2026-11-13T04:02:46+00:00 by `analytics/reconstruction/build_stage2.py` (spec v3.8, sections 9.5, 9.6.2-9.6.5, 9.19.1).

- Data version: `cta_ref__r20261113__gtfs8__to20260731` (outputs in `data/processed/cta_ref__r20261113__gtfs8__to20260731/`)
- Analysis period: 2025-11-23 to 2026-07-31; ridership rows dated on/before 2026-07-31 only
- Code version: git `73a6927+uncommitted`
- Reference comparisons: **51 MATCH, 0 MISMATCH**

> Reference counts are compared, never forced (spec 9.22.2). Missing passenger observations stay missing; they are never turned into zero rides. Payload integrity and schedule agreement do not verify actually operated service.

## 1. Source versions

| dataset | snapshot | sha256 (first 16) | matches spec 9.22.1 | used for |
|---|---|---|---|---|
| cta_bus_ridership_daily | `CTA_-_Ridership_-_Bus_Routes_-_Daily_Totals_by_Route_20261113` | `d9675570e50a1b3d` | False | rides |
| cta_gtfs_mdb389 | `mdb-389-202511230128` | `4a34e0c78a12d797` | True | schedule |
| cta_gtfs_mdb389 | `mdb-389-202512190112` | `1d49526cbce5bf31` | True | schedule |
| cta_gtfs_mdb389 | `mdb-389-202601080131` | `41cc4ddabefed327` | True | schedule |
| cta_gtfs_mdb389 | `mdb-389-202602100132` | `a2115731f779a6c1` | True | schedule |
| cta_gtfs_mdb389 | `mdb-389-202603260020` | `57715a5a369542ec` | True | schedule |
| cta_gtfs_mdb389 | `mdb-389-202604240144` | `b3e31c8fb050b9a3` | True | schedule |
| cta_gtfs_mdb389 | `mdb-389-202605300003` | `3253ed0b0e19ced0` | True | schedule |
| cta_gtfs_mdb389 | `mdb-389-202607110020` | `cf14e64fa93bb3f5` | True | schedule |

Ridership export: 1,124,170 raw rows; 0 exact duplicates removed; 0 missing rides values. Rows after 2026-07-31: **3,566** (2026-08-01 to 2026-08-31), excluded from this stage and kept in the raw file. Publisher last update: 2026-10-28T16:50:20+00:00.

**Provenance note:** the ridership export is not byte-identical to the spec's 2026-10-22 reference file. Any count difference below should first be explained by that newer export (the publisher updated the dataset on 2026-10-28), not by the reconstruction.

## 2. Reference comparison

| section | metric | spec | ours | result | difference |
|---|---|---:|---:|---|---:|
| 9.3.3 | schedule_records | 28,398 | 28,398 | **MATCH** | +0 |
| 9.6.4 | matched | 28,374 | 28,374 | **MATCH** | +0 |
| 9.6.4.1 | ridership_without_schedule | 424 | 424 | **MATCH** | +0 |
| 9.6.4.1 | schedule_without_ridership | 24 | 24 | **MATCH** | +0 |
| 9.6.4.1 | ridership_observations | 28,798 | 28,798 | **MATCH** | +0 |
| 9.3.3 | matched_dates | 251 | 251 | **MATCH** | +0 |
| 9.3.3 | matched_routes | 125 | 125 | **MATCH** | +0 |
| 9.6.4.3 | schedule_conditioned_coverage_pct | 99.915 | 99.915 | **MATCH** | +0.000 |
| 9.6.4.3 | routes_with_records_on_every_scheduled_date | 124 | 124 | **MATCH** | +0 |
| 9.6.4.1 | identity: observations = matched + without schedule | True | True | **MATCH** |  |
| 9.6.4.1 | identity: schedule = matched + without rides | True | True | **MATCH** |  |
| 9.6.4.1 | rides w/o service, route 1001: records | 248 | 248 | **MATCH** | +0 |
| 9.6.4.1 | rides w/o service, route 1001: rides | 103,332 | 103,332 | **MATCH** | +0 |
| 9.6.4.1 | rides w/o service, route 1001: dates | 2025-11-23 to 2026-07-31 | 2025-11-23 to 2026-07-31 | **MATCH** |  |
| 9.6.4.1 | rides w/o service, route 19: records | 126 | 126 | **MATCH** | +0 |
| 9.6.4.1 | rides w/o service, route 19: rides | 24,062 | 24,062 | **MATCH** | +0 |
| 9.6.4.1 | rides w/o service, route 19: dates | 2025-11-23 to 2026-07-26 | 2025-11-23 to 2026-07-26 | **MATCH** |  |
| 9.6.4.1 | rides w/o service, route 130: records | 25 | 25 | **MATCH** | +0 |
| 9.6.4.1 | rides w/o service, route 130: rides | 8,034 | 8,034 | **MATCH** | +0 |
| 9.6.4.1 | rides w/o service, route 130: dates | 2026-02-07 to 2026-06-06 | 2026-02-07 to 2026-06-06 | **MATCH** |  |
| 9.6.4.1 | rides w/o service, route 10: records | 16 | 16 | **MATCH** | +0 |
| 9.6.4.1 | rides w/o service, route 10: rides | 1,973 | 1,973 | **MATCH** | +0 |
| 9.6.4.1 | rides w/o service, route 10: dates | 2026-05-20 to 2026-06-06 | 2026-05-20 to 2026-06-06 | **MATCH** |  |
| 9.6.4.1 | rides w/o service, route 128: records | 6 | 6 | **MATCH** | +0 |
| 9.6.4.1 | rides w/o service, route 128: rides | 6,128 | 6,128 | **MATCH** | +0 |
| 9.6.4.1 | rides w/o service, route 128: dates | 2025-11-23 to 2026-01-18 | 2025-11-23 to 2026-01-18 | **MATCH** |  |
| 9.6.4.1 | rides w/o service, route 59: records | 2 | 2 | **MATCH** | +0 |
| 9.6.4.1 | rides w/o service, route 59: rides | 20 | 20 | **MATCH** | +0 |
| 9.6.4.1 | rides w/o service, route 59: dates | 2026-05-03 to 2026-05-17 | 2026-05-03 to 2026-05-17 | **MATCH** |  |
| 9.6.4.1 | rides w/o service, route 7: records | 1 | 1 | **MATCH** | +0 |
| 9.6.4.1 | rides w/o service, route 7: rides | 17 | 17 | **MATCH** | +0 |
| 9.6.4.1 | rides w/o service, route 7: dates | 2026-02-15 to 2026-02-15 | 2026-02-15 to 2026-02-15 | **MATCH** |  |
| 9.6.4.1 | rides w/o service: routes not in spec list |  |  | **MATCH** |  |
| 9.6.4.1 | schedule w/o rides, route 169: records | 24 | 24 | **MATCH** | +0 |
| 9.6.4.1 | schedule w/o rides, route 169: dates | 2025-11-27 to 2026-07-25 | 2025-11-27 to 2026-07-25 | **MATCH** |  |
| 9.6.4.1 | schedule w/o rides: routes not in spec list |  |  | **MATCH** |  |
| 9.6.4.3 | recent window records | 83,997 | 83,997 | **MATCH** | +0 |
| 9.6.4.3 | recent window route_identifiers | 129 | 129 | **MATCH** | +0 |
| 9.6.4.3 | recent window calendar_dates | 730 | 730 | **MATCH** | +0 |
| 9.6.4.2 | route 1001 recent-window records | 726 | 726 | **MATCH** | +0 |
| 9.6.4.2 | route 1001 recent-window rides | 407,306 | 407,306 | **MATCH** | +0 |
| 9.6.4.2 | identifiers absent from all 8 archives | 1001, 128, 19, 5 | 1001, 128, 19, 5 | **MATCH** |  |
| 9.6.4.3 | route 10 first active schedule date | 2026-06-07 | 2026-06-07 | **MATCH** |  |
| 9.6.4.3 | route 130 first active schedule date | 2026-06-07 | 2026-06-07 | **MATCH** |  |
| 9.6.4.3 | route 10 record days Jan-Jul 2026 | 0, 0, 0, 0, 10, 30, 31 | 0, 0, 0, 0, 10, 30, 31 | **MATCH** |  |
| 9.6.4.3 | route 130 record days Jan-Jul 2026 | 0, 10, 0, 0, 9, 30, 31 | 0, 10, 0, 0, 9, 30, 31 | **MATCH** |  |
| 9.4.2 | applied date ranges equal spec 9.4.2 for all 8 archives | True | True | **MATCH** |  |
| 9.6.5 | Jan 8 / Feb 10 bus stop events | 2859229, 2859229 | 2859229, 2859229 | **MATCH** |  |
| 9.6.5 | Jan 8 / Feb 10 bus trips and stop events identical | True | True | **MATCH** |  |
| 9.6.3 | selection gaps | 0 | 0 | **MATCH** | +0 |
| 9.6.5 | overlap comparisons with unexplained differences | 0 | 0 | **MATCH** | +0 |

## 3. Snapshot selection (spec 9.6.3)

One whole snapshot per date: the latest captured on/before the date. No per-route fallback.

| snapshot | captured | applied from | applied to | spec applied | dates | route/date rows | bus routes |
|---|---|---|---|---|---|---|---|
| mdb-389-202511230128 | 2025-11-23 | 2025-11-23 | 2025-12-18 | 2025-11-23 to 2025-12-18 | 26 | 2,924 | 123 |
| mdb-389-202512190112 | 2025-12-19 | 2025-12-19 | 2026-01-07 | 2025-12-19 to 2026-01-07 | 20 | 2,187 | 123 |
| mdb-389-202601080131 | 2026-01-08 | 2026-01-08 | 2026-02-09 | 2026-01-08 to 2026-02-09 | 33 | 3,724 | 123 |
| mdb-389-202602100132 | 2026-02-10 | 2026-02-10 | 2026-03-25 | 2026-02-10 to 2026-03-25 | 44 | 5,010 | 123 |
| mdb-389-202603260020 | 2026-03-26 | 2026-03-26 | 2026-04-23 | 2026-03-26 to 2026-04-23 | 29 | 3,299 | 123 |
| mdb-389-202604240144 | 2026-04-24 | 2026-04-24 | 2026-05-29 | 2026-04-24 to 2026-05-29 | 36 | 4,057 | 123 |
| mdb-389-202605300003 | 2026-05-30 | 2026-05-30 | 2026-07-10 | 2026-05-30 to 2026-07-10 | 42 | 4,782 | 125 |
| mdb-389-202607110020 | 2026-07-11 | 2026-07-11 | 2026-07-31 | 2026-07-11 to 2026-07-31 | 21 | 2,415 | 125 |

Selection gaps (no archive captured yet, or the selected archive defines no bus service): **0**

## 4. Daily scheduled service

- Rows: 28,398; dates: 251; routes: 125
- Route/dates with complete durations: 28,398 of 28,398; invalid trip durations by reason: none
- Unique (date, trip_id) among active trips: enforced (build stops otherwise)

## 5. Exact matching and two-direction reconciliation (spec 9.6.4)

```
28,798 ridership observations = 28,374 matched + 424 without selected service   -> holds: True
28,398 schedule records       = 28,374 matched + 24 without recorded rides    -> holds: True
```

- Matched coverage: 251 dates, 125 routes. Ridership side: 251 dates, 128 identifiers.
- Schedule-conditioned coverage: 99.915%; routes with records on every scheduled date: 124 of 125.
- Genuine zero-ride matched rows (kept as 0): 0

### Ridership observations without selected scheduled service (by route)

| route | records | rides | first_date | last_date |
|---|---|---|---|---|
| 1001 | 248 | 103,332 | 2025-11-23 | 2026-07-31 |
| 19 | 126 | 24,062 | 2025-11-23 | 2026-07-26 |
| 130 | 25 | 8,034 | 2026-02-07 | 2026-06-06 |
| 10 | 16 | 1,973 | 2026-05-20 | 2026-06-06 |
| 128 | 6 | 6,128 | 2025-11-23 | 2026-01-18 |
| 59 | 2 | 20 | 2026-05-03 | 2026-05-17 |
| 7 | 1 | 17 | 2026-02-15 | 2026-02-15 |

Reasons: route_absent_from_selected_snapshot = 405, route_in_snapshot_no_active_trips = 19

### Scheduled route/dates without a ridership observation (by route)

| route | records | first_date | last_date |
|---|---|---|---|
| 169 | 24 | 2025-11-27 | 2026-07-25 |

These rows keep `rides` empty (missing). They are not zero-ridership targets.

## 6. Archive integrity and timetable regimes (spec 9.6.5)

- Jan 8 vs Feb 10: ZIP bytes differ = True; bus trip records and bus stop events identical = **True** (bus stop events 2,859,229 vs 2,859,229; spec 2,859,229 each).
- April 24 / May 30 bus stop events = 2,842,263 / 5,692,185 = 0.499 (spec: approximately half). Calendar-selected daily counts are kept; smaller feeds are not doubled.
- Archives with more than one disjoint bus calendar regime (outgoing + incoming timetables): mdb-389-202511230128 (2), mdb-389-202512190112 (2), mdb-389-202603260020 (2), mdb-389-202605300003 (2), mdb-389-202607110020 (2)
- Same-date overlap comparisons with common dates: 7; with no differences: 4; with differences confined to a timetable present only in the newer archive: 3; **unexplained: 0**. The spec reports five comparisons with no differences; it does not list which pairs/dates, so this is reported side by side rather than as a pass/fail.

Same-date overlap comparisons (older vs newer archive on the newer one's first days, where both define service):

| older | newer | dates both define | route/dates compared | only older | only newer | trip-count diffs | hours diffs | explanation |
|---|---|---|---|---|---|---|---|---|
| mdb-389-202511230128 | mdb-389-202512190112 | 7 | 758 | 0 | 0 | 190 | 268 | differences only from 2025-12-21 (start of a timetable present only in the newer archive); 2 earlier common date(s) agree |
| mdb-389-202512190112 | mdb-389-202601080131 | 7 | 794 | 0 | 0 | 0 | 0 | no differences |
| mdb-389-202601080131 | mdb-389-202602100132 | 7 | 794 | 0 | 0 | 0 | 0 | no differences |
| mdb-389-202602100132 | mdb-389-202603260020 | 6 | 671 | 0 | 0 | 113 | 133 | differences only from 2026-03-29 (start of a timetable present only in the newer archive); 3 earlier common date(s) agree |
| mdb-389-202603260020 | mdb-389-202604240144 | 7 | 794 | 0 | 0 | 0 | 0 | no differences |
| mdb-389-202604240144 | mdb-389-202605300003 | 7 | 794 | 0 | 0 | 0 | 0 | no differences |
| mdb-389-202605300003 | mdb-389-202607110020 | 7 | 805 | 0 | 0 | 0 | 35 | differences only from 2026-07-12 (start of a timetable present only in the newer archive); 1 earlier common date(s) agree |

Bus calendar regimes inside each archive (distinct calendar.txt ranges used by bus trips):

| snapshot | start_date | end_date | services | bus trips |
|---|---|---|---|---|
| mdb-389-202511230128 | 20251119 | 20251122 | 16 | 44,768 |
| mdb-389-202511230128 | 20251123 | 20260131 | 16 | 44,768 |
| mdb-389-202512190112 | 20251216 | 20251220 | 16 | 44,768 |
| mdb-389-202512190112 | 20251221 | 20260228 | 16 | 44,878 |
| mdb-389-202601080131 | 20260106 | 20260331 | 16 | 44,878 |
| mdb-389-202602100132 | 20260106 | 20260331 | 16 | 44,878 |
| mdb-389-202603260020 | 20260320 | 20260328 | 16 | 44,878 |
| mdb-389-202603260020 | 20260329 | 20260531 | 16 | 44,560 |
| mdb-389-202604240144 | 20260415 | 20260630 | 16 | 44,560 |
| mdb-389-202605300003 | 20260528 | 20260606 | 16 | 44,560 |
| mdb-389-202605300003 | 20260607 | 20260731 | 8 | 44,807 |
| mdb-389-202607110020 | 20260707 | 20260711 | 8 | 44,807 |
| mdb-389-202607110020 | 20260712 | 20260930 | 8 | 44,807 |

## 7. Descriptive summaries (spec 9.6.2, 9.6.4.2, 9.6.4.3)

- Route-name presence: 98.31% of recent-window rows (82,577 of 83,997) use an identifier found in at least one of the 8 archived bus route tables. The spec's 97.95% is measured against the original *September* schedule, which is not one of this stage's inputs, so it is **not directly reproducible** here; context only.
- Identifiers absent from all 8 archives (recent window): ['1001', '128', '19', '5']

Route 10 / 130 record days in 2026:

| month | calendar_days | route_10_record_days | route_130_record_days |
|---|---|---|---|
| 2026-01 | 31 | 0 | 0 |
| 2026-02 | 28 | 0 | 10 |
| 2026-03 | 31 | 0 | 0 |
| 2026-04 | 30 | 0 | 0 |
| 2026-05 | 31 | 10 | 9 |
| 2026-06 | 30 | 30 | 30 |
| 2026-07 | 31 | 31 | 31 |

Monthly ridership record coverage in the analysis period (record availability, not reporting completeness):

| month | records | routes | dates | rides | daytype_A | daytype_U | daytype_W |
|---|---|---|---|---|---|---|---|
| 2025-11 | 858 | 126 | 8 | 3,048,605 | 94 | 264 | 500 |
| 2025-12 | 3,557 | 126 | 31 | 14,890,539 | 380 | 438 | 2,739 |
| 2026-01 | 3,529 | 126 | 31 | 14,786,538 | 471 | 441 | 2,617 |
| 2026-02 | 3,223 | 126 | 28 | 15,557,250 | 377 | 352 | 2,494 |
| 2026-03 | 3,558 | 125 | 31 | 16,966,287 | 376 | 439 | 2,743 |
| 2026-04 | 3,465 | 125 | 30 | 17,797,948 | 378 | 349 | 2,738 |
| 2026-05 | 3,499 | 127 | 31 | 18,151,805 | 473 | 532 | 2,494 |
| 2026-06 | 3,512 | 127 | 30 | 17,278,218 | 379 | 353 | 2,780 |
| 2026-07 | 3,597 | 127 | 31 | 17,337,192 | 376 | 443 | 2,778 |

## Outputs

| file | rows | sha256 (first 16) |
|---|---:|---|
| `expanded_scheduled_route_day_service.csv` | 28,398 | `5c8790f794e6c95b` |
| `expanded_matched_utilization.csv` | 28,374 | `7270dba7ff36073e` |
| `expanded_ridership_without_schedule.csv` | 424 | `c582421d1f233592` |
| `expanded_schedule_without_ridership.csv` | 24 | `515ecf1ece6354c4` |
