# Stage 1 quality report: raw source validation

Generated 2026-11-13T03:24:01+00:00 by `analytics/source/validate_raw.py` (spec v3.8, section 9.6.1).

> ZIP integrity and the checks below are narrower than full GTFS specification validation, and they do not verify actually operated service (spec 9.6.1, 9.22.2).

## 1. Source register and fingerprints (spec 9.22.1)

| dataset | snapshot | bytes | sha256 (first 16) | fingerprint | primary |
|---|---|---:|---|---|---|
| cta_bus_ridership_daily | CTA_-_Ridership_-_Bus_Routes_-_Daily_Totals_by_Route_20261113 | 23,953,761 | `d9675570e50a1b3d` | MISMATCH | True |
| cta_gtfs_mdb389 | mdb-389-202511230128 | 69,053,782 | `4a34e0c78a12d797` | MATCH | True |
| cta_gtfs_mdb389 | mdb-389-202512190112 | 100,125,733 | `1d49526cbce5bf31` | MATCH | True |
| cta_gtfs_mdb389 | mdb-389-202601080131 | 50,436,962 | `41cc4ddabefed327` | MATCH | True |
| cta_gtfs_mdb389 | mdb-389-202602100132 | 49,900,671 | `a2115731f779a6c1` | MATCH | True |
| cta_gtfs_mdb389 | mdb-389-202603260020 | 99,398,559 | `57715a5a369542ec` | MATCH | True |
| cta_gtfs_mdb389 | mdb-389-202604240144 | 50,957,347 | `b3e31c8fb050b9a3` | MATCH | True |
| cta_gtfs_mdb389 | mdb-389-202605300003 | 98,307,739 | `3253ed0b0e19ced0` | MATCH | True |
| cta_gtfs_mdb389 | mdb-389-202607110020 | 67,896,351 | `cf14e64fa93bb3f5` | MATCH | True |

## Ridership: `CTA_-_Ridership_-_Bus_Routes_-_Daily_Totals_by_Route_20261113`

- Downloaded: 2026-11-13T03:19:05+00:00 (download)
- Publisher 'last updated' (rowsUpdatedAt): 2026-10-28T16:50:20+00:00
- Records in file: 1,124,170

| check | status | detail |
|---|---|---|
| CSV schema | **PASS** | columns = ['route', 'date', 'daytype', 'rides'] |
| Row count | **INFO** | 1,124,170 data records |
| Route whitespace | **INFO** | 0 route values have surrounding whitespace (trimmed for analysis) |
| Missing identifiers | **PASS** | 0 empty route, 0 empty date |
| Date parsing (MM/DD/YYYY) | **PASS** | 0 unparseable non-empty dates |
| Numeric conversion | **PASS** | 0 non-numeric/empty rides; 0 values contained a ',' separator |
| Negative counts | **PASS** | 0 negative rides |
| Fractional counts | **PASS** | 0 non-integer rides |
| Day types (W/A/U) | **PASS** | 0 unknown; observed = ['A', 'U', 'W'] |
| Genuine zero counts | **INFO** | 36 records with rides = 0 (kept; not missing) |
| Exact duplicate records | **PASS** | 0 exact copies (to be removed in processing, with this report as the record) |
| Conflicting route/date records | **PASS** | 0 route/date keys with differing records (0 rows)  |

### Content check vs spec 9.3.1 (rows dated on/before 2026-07-31)

The raw file is unchanged; this compares only the rows inside the spec's observation period.

| metric | spec | this version | result | difference |
|---|---:|---:|---|---:|
| records | 1,120,604 | 1,120,604 | **MATCH** | +0 |
| route_identifiers | 188 | 188 | **MATCH** | +0 |
| first_date | 2001-01-01 | 2001-01-01 | **MATCH** | +0 days |
| last_date | 2026-07-31 | 2026-07-31 | **MATCH** | +0 days |
| zero_count_records | 36 | 36 | **MATCH** | +0 |

### Rows after 2026-07-31 (kept in the raw file, reported separately)

- Records: 3,566
- Dates: 2026-08-01 to 2026-08-31
- Route identifiers: 128
- Sum of rides: 17,378,341

## GTFS: `mdb-389-202511230128`

| check | status | detail |
|---|---|---|
| ZIP readable | **PASS** | 11 members |
| ZIP CRC (testzip) | **PASS** | all member CRCs valid |
| Extracted-byte agreement | **PASS** | every extracted file matches ZIP size and CRC32 |
| Required columns routes.txt | **PASS** | all present |
| Required columns trips.txt | **PASS** | all present |
| Required columns calendar.txt | **PASS** | all present |
| Required columns calendar_dates.txt | **PASS** | all present |
| Required columns stop_times.txt | **PASS** | all present |
| Required columns stops.txt | **PASS** | all present |
| Required columns shapes.txt | **PASS** | all present |
| Required columns agency.txt | **PASS** | all present |
| Unique key routes.route_id | **PASS** | 131 rows, 0 duplicates, 0 empty |
| Unique key trips.trip_id | **PASS** | 94,594 rows, 0 duplicates, 0 empty |
| Unique key stops.stop_id | **PASS** | 11,155 rows, 0 duplicates, 0 empty |
| Foreign key trips.route_id -> routes | **PASS** | 0 orphan rows |
| Foreign key trips.service_id -> calendar/calendar_dates | **PASS** | 0 orphan rows |
| Foreign key stop_times.trip_id -> trips | **PASS** | 0 orphan rows |
| Foreign key stop_times.stop_id -> stops | **PASS** | 0 orphan rows |
| Foreign key trips.shape_id -> shapes | **PASS** | 0 orphan rows |
| Trips without stop_times | **INFO** | 0 trips have no stop events |
| Calendar validity (calendar.txt) | **PASS** | 0 bad weekday flags, 0 unparseable dates, 0 start>end, 0 duplicate service_id |
| Calendar validity (calendar_dates.txt) | **PASS** | 0 unparseable dates, 0 bad exception_type, 0 duplicate service/date pairs |
| Duplicate stop sequences | **PASS** | 0 duplicated (trip_id, stop_sequence); 0 non-integer stop_sequence |
| Time syntax (H:MM:SS, >24h allowed) | **PASS** | 0 malformed; 0 rows with an empty time (allowed between timepoints); 47,010 departures at/after 24:00:00 (kept on their original service date) |
| Duration completeness | **PASS** | 94,594 trips with stop events; 0 missing a first departure or last arrival; 0 with last arrival before first departure |
| Agency timezone | **PASS** | agency_timezone = ['America/Chicago'] |
| frequencies.txt | **PASS** | 0 rows (empty, as in spec) |

Informational counts:

- Bus routes (route_type 3) referenced by trips: 123 (spec: 123, **MATCH**)
- Bus trips: 89,536
- Bus stop_times: 5,661,993
- Bus calendar.txt window: 2025-11-19 to 2026-01-31 (spec active window 2025-11-19 to 2026-01-31; calendar.txt bounds can include an outgoing/incoming regime, so this is context, not a pass/fail)

## GTFS: `mdb-389-202512190112`

| check | status | detail |
|---|---|---|
| ZIP readable | **PASS** | 11 members |
| ZIP CRC (testzip) | **PASS** | all member CRCs valid |
| Extracted-byte agreement | **PASS** | every extracted file matches ZIP size and CRC32 |
| Required columns routes.txt | **PASS** | all present |
| Required columns trips.txt | **PASS** | all present |
| Required columns calendar.txt | **PASS** | all present |
| Required columns calendar_dates.txt | **PASS** | all present |
| Required columns stop_times.txt | **PASS** | all present |
| Required columns stops.txt | **PASS** | all present |
| Required columns shapes.txt | **PASS** | all present |
| Required columns agency.txt | **PASS** | all present |
| Unique key routes.route_id | **PASS** | 131 rows, 0 duplicates, 0 empty |
| Unique key trips.trip_id | **PASS** | 94,704 rows, 0 duplicates, 0 empty |
| Unique key stops.stop_id | **PASS** | 11,185 rows, 0 duplicates, 0 empty |
| Foreign key trips.route_id -> routes | **PASS** | 0 orphan rows |
| Foreign key trips.service_id -> calendar/calendar_dates | **PASS** | 0 orphan rows |
| Foreign key stop_times.trip_id -> trips | **PASS** | 0 orphan rows |
| Foreign key stop_times.stop_id -> stops | **PASS** | 0 orphan rows |
| Foreign key trips.shape_id -> shapes | **PASS** | 0 orphan rows |
| Trips without stop_times | **INFO** | 0 trips have no stop events |
| Calendar validity (calendar.txt) | **PASS** | 0 bad weekday flags, 0 unparseable dates, 0 start>end, 0 duplicate service_id |
| Calendar validity (calendar_dates.txt) | **PASS** | 0 unparseable dates, 0 bad exception_type, 0 duplicate service/date pairs |
| Duplicate stop sequences | **PASS** | 0 duplicated (trip_id, stop_sequence); 0 non-integer stop_sequence |
| Time syntax (H:MM:SS, >24h allowed) | **PASS** | 0 malformed; 0 rows with an empty time (allowed between timepoints); 47,781 departures at/after 24:00:00 (kept on their original service date) |
| Duration completeness | **PASS** | 94,704 trips with stop events; 0 missing a first departure or last arrival; 0 with last arrival before first departure |
| Agency timezone | **PASS** | agency_timezone = ['America/Chicago'] |
| frequencies.txt | **PASS** | 0 rows (empty, as in spec) |

Informational counts:

- Bus routes (route_type 3) referenced by trips: 123 (spec: 123, **MATCH**)
- Bus trips: 89,646
- Bus stop_times: 5,689,188
- Bus calendar.txt window: 2025-12-16 to 2026-02-28 (spec active window 2025-12-16 to 2026-02-28; calendar.txt bounds can include an outgoing/incoming regime, so this is context, not a pass/fail)

## GTFS: `mdb-389-202601080131`

| check | status | detail |
|---|---|---|
| ZIP readable | **PASS** | 11 members |
| ZIP CRC (testzip) | **PASS** | all member CRCs valid |
| Extracted-byte agreement | **PASS** | every extracted file matches ZIP size and CRC32 |
| Required columns routes.txt | **PASS** | all present |
| Required columns trips.txt | **PASS** | all present |
| Required columns calendar.txt | **PASS** | all present |
| Required columns calendar_dates.txt | **PASS** | all present |
| Required columns stop_times.txt | **PASS** | all present |
| Required columns stops.txt | **PASS** | all present |
| Required columns shapes.txt | **PASS** | all present |
| Required columns agency.txt | **PASS** | all present |
| Unique key routes.route_id | **PASS** | 131 rows, 0 duplicates, 0 empty |
| Unique key trips.trip_id | **PASS** | 49,936 rows, 0 duplicates, 0 empty |
| Unique key stops.stop_id | **PASS** | 11,130 rows, 0 duplicates, 0 empty |
| Foreign key trips.route_id -> routes | **PASS** | 0 orphan rows |
| Foreign key trips.service_id -> calendar/calendar_dates | **PASS** | 0 orphan rows |
| Foreign key stop_times.trip_id -> trips | **PASS** | 0 orphan rows |
| Foreign key stop_times.stop_id -> stops | **PASS** | 0 orphan rows |
| Foreign key trips.shape_id -> shapes | **PASS** | 0 orphan rows |
| Trips without stop_times | **INFO** | 0 trips have no stop events |
| Calendar validity (calendar.txt) | **PASS** | 0 bad weekday flags, 0 unparseable dates, 0 start>end, 0 duplicate service_id |
| Calendar validity (calendar_dates.txt) | **PASS** | 0 unparseable dates, 0 bad exception_type, 0 duplicate service/date pairs |
| Duplicate stop sequences | **PASS** | 0 duplicated (trip_id, stop_sequence); 0 non-integer stop_sequence |
| Time syntax (H:MM:SS, >24h allowed) | **PASS** | 0 malformed; 0 rows with an empty time (allowed between timepoints); 25,492 departures at/after 24:00:00 (kept on their original service date) |
| Duration completeness | **PASS** | 49,936 trips with stop events; 0 missing a first departure or last arrival; 0 with last arrival before first departure |
| Agency timezone | **PASS** | agency_timezone = ['America/Chicago'] |
| frequencies.txt | **PASS** | 0 rows (empty, as in spec) |

Informational counts:

- Bus routes (route_type 3) referenced by trips: 123 (spec: 123, **MATCH**)
- Bus trips: 44,878
- Bus stop_times: 2,859,229 (spec: 2,859,229, **MATCH**)
- Bus calendar.txt window: 2026-01-06 to 2026-03-31 (spec active window 2026-01-06 to 2026-03-31; calendar.txt bounds can include an outgoing/incoming regime, so this is context, not a pass/fail)

## GTFS: `mdb-389-202602100132`

| check | status | detail |
|---|---|---|
| ZIP readable | **PASS** | 11 members |
| ZIP CRC (testzip) | **PASS** | all member CRCs valid |
| Extracted-byte agreement | **PASS** | every extracted file matches ZIP size and CRC32 |
| Required columns routes.txt | **PASS** | all present |
| Required columns trips.txt | **PASS** | all present |
| Required columns calendar.txt | **PASS** | all present |
| Required columns calendar_dates.txt | **PASS** | all present |
| Required columns stop_times.txt | **PASS** | all present |
| Required columns stops.txt | **PASS** | all present |
| Required columns shapes.txt | **PASS** | all present |
| Required columns agency.txt | **PASS** | all present |
| Unique key routes.route_id | **PASS** | 131 rows, 0 duplicates, 0 empty |
| Unique key trips.trip_id | **PASS** | 49,936 rows, 0 duplicates, 0 empty |
| Unique key stops.stop_id | **PASS** | 11,130 rows, 0 duplicates, 0 empty |
| Foreign key trips.route_id -> routes | **PASS** | 0 orphan rows |
| Foreign key trips.service_id -> calendar/calendar_dates | **PASS** | 0 orphan rows |
| Foreign key stop_times.trip_id -> trips | **PASS** | 0 orphan rows |
| Foreign key stop_times.stop_id -> stops | **PASS** | 0 orphan rows |
| Foreign key trips.shape_id -> shapes | **PASS** | 0 orphan rows |
| Trips without stop_times | **INFO** | 0 trips have no stop events |
| Calendar validity (calendar.txt) | **PASS** | 0 bad weekday flags, 0 unparseable dates, 0 start>end, 0 duplicate service_id |
| Calendar validity (calendar_dates.txt) | **PASS** | 0 unparseable dates, 0 bad exception_type, 0 duplicate service/date pairs |
| Duplicate stop sequences | **PASS** | 0 duplicated (trip_id, stop_sequence); 0 non-integer stop_sequence |
| Time syntax (H:MM:SS, >24h allowed) | **PASS** | 0 malformed; 0 rows with an empty time (allowed between timepoints); 25,492 departures at/after 24:00:00 (kept on their original service date) |
| Duration completeness | **PASS** | 49,936 trips with stop events; 0 missing a first departure or last arrival; 0 with last arrival before first departure |
| Agency timezone | **PASS** | agency_timezone = ['America/Chicago'] |
| frequencies.txt | **PASS** | 0 rows (empty, as in spec) |

Informational counts:

- Bus routes (route_type 3) referenced by trips: 123 (spec: 123, **MATCH**)
- Bus trips: 44,878
- Bus stop_times: 2,859,229 (spec: 2,859,229, **MATCH**)
- Bus calendar.txt window: 2026-01-06 to 2026-03-31 (spec active window 2026-01-06 to 2026-03-31; calendar.txt bounds can include an outgoing/incoming regime, so this is context, not a pass/fail)

## GTFS: `mdb-389-202603260020`

| check | status | detail |
|---|---|---|
| ZIP readable | **PASS** | 11 members |
| ZIP CRC (testzip) | **PASS** | all member CRCs valid |
| Extracted-byte agreement | **PASS** | every extracted file matches ZIP size and CRC32 |
| Required columns routes.txt | **PASS** | all present |
| Required columns trips.txt | **PASS** | all present |
| Required columns calendar.txt | **PASS** | all present |
| Required columns calendar_dates.txt | **PASS** | all present |
| Required columns stop_times.txt | **PASS** | all present |
| Required columns stops.txt | **PASS** | all present |
| Required columns shapes.txt | **PASS** | all present |
| Required columns agency.txt | **PASS** | all present |
| Unique key routes.route_id | **PASS** | 131 rows, 0 duplicates, 0 empty |
| Unique key trips.trip_id | **PASS** | 94,496 rows, 0 duplicates, 0 empty |
| Unique key stops.stop_id | **PASS** | 11,184 rows, 0 duplicates, 0 empty |
| Foreign key trips.route_id -> routes | **PASS** | 0 orphan rows |
| Foreign key trips.service_id -> calendar/calendar_dates | **PASS** | 0 orphan rows |
| Foreign key stop_times.trip_id -> trips | **PASS** | 0 orphan rows |
| Foreign key stop_times.stop_id -> stops | **PASS** | 0 orphan rows |
| Foreign key trips.shape_id -> shapes | **PASS** | 0 orphan rows |
| Trips without stop_times | **INFO** | 0 trips have no stop events |
| Calendar validity (calendar.txt) | **PASS** | 0 bad weekday flags, 0 unparseable dates, 0 start>end, 0 duplicate service_id |
| Calendar validity (calendar_dates.txt) | **PASS** | 0 unparseable dates, 0 bad exception_type, 0 duplicate service/date pairs |
| Duplicate stop sequences | **PASS** | 0 duplicated (trip_id, stop_sequence); 0 non-integer stop_sequence |
| Time syntax (H:MM:SS, >24h allowed) | **PASS** | 0 malformed; 0 rows with an empty time (allowed between timepoints); 48,446 departures at/after 24:00:00 (kept on their original service date) |
| Duration completeness | **PASS** | 94,496 trips with stop events; 0 missing a first departure or last arrival; 0 with last arrival before first departure |
| Agency timezone | **PASS** | agency_timezone = ['America/Chicago'] |
| frequencies.txt | **PASS** | 0 rows (empty, as in spec) |

Informational counts:

- Bus routes (route_type 3) referenced by trips: 123 (spec: 123, **MATCH**)
- Bus trips: 89,438
- Bus stop_times: 5,701,512
- Bus calendar.txt window: 2026-03-20 to 2026-05-31 (spec active window 2026-03-20 to 2026-05-31; calendar.txt bounds can include an outgoing/incoming regime, so this is context, not a pass/fail)

## GTFS: `mdb-389-202604240144`

| check | status | detail |
|---|---|---|
| ZIP readable | **PASS** | 11 members |
| ZIP CRC (testzip) | **PASS** | all member CRCs valid |
| Extracted-byte agreement | **PASS** | every extracted file matches ZIP size and CRC32 |
| Required columns routes.txt | **PASS** | all present |
| Required columns trips.txt | **PASS** | all present |
| Required columns calendar.txt | **PASS** | all present |
| Required columns calendar_dates.txt | **PASS** | all present |
| Required columns stop_times.txt | **PASS** | all present |
| Required columns stops.txt | **PASS** | all present |
| Required columns shapes.txt | **PASS** | all present |
| Required columns agency.txt | **PASS** | all present |
| Unique key routes.route_id | **PASS** | 131 rows, 0 duplicates, 0 empty |
| Unique key trips.trip_id | **PASS** | 54,663 rows, 0 duplicates, 0 empty |
| Unique key stops.stop_id | **PASS** | 11,164 rows, 0 duplicates, 0 empty |
| Foreign key trips.route_id -> routes | **PASS** | 0 orphan rows |
| Foreign key trips.service_id -> calendar/calendar_dates | **PASS** | 0 orphan rows |
| Foreign key stop_times.trip_id -> trips | **PASS** | 0 orphan rows |
| Foreign key stop_times.stop_id -> stops | **PASS** | 0 orphan rows |
| Foreign key trips.shape_id -> shapes | **PASS** | 0 orphan rows |
| Trips without stop_times | **INFO** | 0 trips have no stop events |
| Calendar validity (calendar.txt) | **PASS** | 0 bad weekday flags, 0 unparseable dates, 0 start>end, 0 duplicate service_id |
| Calendar validity (calendar_dates.txt) | **PASS** | 0 unparseable dates, 0 bad exception_type, 0 duplicate service/date pairs |
| Duplicate stop sequences | **PASS** | 0 duplicated (trip_id, stop_sequence); 0 non-integer stop_sequence |
| Time syntax (H:MM:SS, >24h allowed) | **PASS** | 0 malformed; 0 rows with an empty time (allowed between timepoints); 27,760 departures at/after 24:00:00 (kept on their original service date) |
| Duration completeness | **PASS** | 54,663 trips with stop events; 0 missing a first departure or last arrival; 0 with last arrival before first departure |
| Agency timezone | **PASS** | agency_timezone = ['America/Chicago'] |
| frequencies.txt | **PASS** | 0 rows (empty, as in spec) |

Informational counts:

- Bus routes (route_type 3) referenced by trips: 123 (spec: 123, **MATCH**)
- Bus trips: 44,560
- Bus stop_times: 2,842,263
- Bus calendar.txt window: 2026-04-15 to 2026-06-30 (spec active window 2026-04-15 to 2026-06-30; calendar.txt bounds can include an outgoing/incoming regime, so this is context, not a pass/fail)

## GTFS: `mdb-389-202605300003`

| check | status | detail |
|---|---|---|
| ZIP readable | **PASS** | 11 members |
| ZIP CRC (testzip) | **PASS** | all member CRCs valid |
| Extracted-byte agreement | **PASS** | every extracted file matches ZIP size and CRC32 |
| Required columns routes.txt | **PASS** | all present |
| Required columns trips.txt | **PASS** | all present |
| Required columns calendar.txt | **PASS** | all present |
| Required columns calendar_dates.txt | **PASS** | all present |
| Required columns stop_times.txt | **PASS** | all present |
| Required columns stops.txt | **PASS** | all present |
| Required columns shapes.txt | **PASS** | all present |
| Required columns agency.txt | **PASS** | all present |
| Unique key routes.route_id | **PASS** | 133 rows, 0 duplicates, 0 empty |
| Unique key trips.trip_id | **PASS** | 94,420 rows, 0 duplicates, 0 empty |
| Unique key stops.stop_id | **PASS** | 11,177 rows, 0 duplicates, 0 empty |
| Foreign key trips.route_id -> routes | **PASS** | 0 orphan rows |
| Foreign key trips.service_id -> calendar/calendar_dates | **PASS** | 0 orphan rows |
| Foreign key stop_times.trip_id -> trips | **PASS** | 0 orphan rows |
| Foreign key stop_times.stop_id -> stops | **PASS** | 0 orphan rows |
| Foreign key trips.shape_id -> shapes | **PASS** | 0 orphan rows |
| Trips without stop_times | **INFO** | 0 trips have no stop events |
| Calendar validity (calendar.txt) | **PASS** | 0 bad weekday flags, 0 unparseable dates, 0 start>end, 0 duplicate service_id |
| Calendar validity (calendar_dates.txt) | **PASS** | 0 unparseable dates, 0 bad exception_type, 0 duplicate service/date pairs |
| Duplicate stop sequences | **PASS** | 0 duplicated (trip_id, stop_sequence); 0 non-integer stop_sequence |
| Time syntax (H:MM:SS, >24h allowed) | **PASS** | 0 malformed; 0 rows with an empty time (allowed between timepoints); 48,736 departures at/after 24:00:00 (kept on their original service date) |
| Duration completeness | **PASS** | 94,420 trips with stop events; 0 missing a first departure or last arrival; 0 with last arrival before first departure |
| Agency timezone | **PASS** | agency_timezone = ['America/Chicago'] |
| frequencies.txt | **PASS** | 0 rows (empty, as in spec) |

Informational counts:

- Bus routes (route_type 3) referenced by trips: 125 (spec: 125, **MATCH**)
- Bus trips: 89,367
- Bus stop_times: 5,692,185
- Bus calendar.txt window: 2026-05-28 to 2026-07-31 (spec active window 2026-05-28 to 2026-07-31; calendar.txt bounds can include an outgoing/incoming regime, so this is context, not a pass/fail)

## GTFS: `mdb-389-202607110020`

| check | status | detail |
|---|---|---|
| ZIP readable | **PASS** | 11 members |
| ZIP CRC (testzip) | **PASS** | all member CRCs valid |
| Extracted-byte agreement | **PASS** | every extracted file matches ZIP size and CRC32 |
| Required columns routes.txt | **PASS** | all present |
| Required columns trips.txt | **PASS** | all present |
| Required columns calendar.txt | **PASS** | all present |
| Required columns calendar_dates.txt | **PASS** | all present |
| Required columns stop_times.txt | **PASS** | all present |
| Required columns stops.txt | **PASS** | all present |
| Required columns shapes.txt | **PASS** | all present |
| Required columns agency.txt | **PASS** | all present |
| Unique key routes.route_id | **PASS** | 133 rows, 0 duplicates, 0 empty |
| Unique key trips.trip_id | **PASS** | 94,667 rows, 0 duplicates, 0 empty |
| Unique key stops.stop_id | **PASS** | 11,125 rows, 0 duplicates, 0 empty |
| Foreign key trips.route_id -> routes | **PASS** | 0 orphan rows |
| Foreign key trips.service_id -> calendar/calendar_dates | **PASS** | 0 orphan rows |
| Foreign key stop_times.trip_id -> trips | **PASS** | 0 orphan rows |
| Foreign key stop_times.stop_id -> stops | **PASS** | 0 orphan rows |
| Foreign key trips.shape_id -> shapes | **PASS** | 0 orphan rows |
| Trips without stop_times | **INFO** | 0 trips have no stop events |
| Calendar validity (calendar.txt) | **PASS** | 0 bad weekday flags, 0 unparseable dates, 0 start>end, 0 duplicate service_id |
| Calendar validity (calendar_dates.txt) | **PASS** | 0 unparseable dates, 0 bad exception_type, 0 duplicate service/date pairs |
| Duplicate stop sequences | **PASS** | 0 duplicated (trip_id, stop_sequence); 0 non-integer stop_sequence |
| Time syntax (H:MM:SS, >24h allowed) | **PASS** | 0 malformed; 0 rows with an empty time (allowed between timepoints); 49,142 departures at/after 24:00:00 (kept on their original service date) |
| Duration completeness | **PASS** | 94,667 trips with stop events; 0 missing a first departure or last arrival; 0 with last arrival before first departure |
| Agency timezone | **PASS** | agency_timezone = ['America/Chicago'] |
| frequencies.txt | **PASS** | 0 rows (empty, as in spec) |

Informational counts:

- Bus routes (route_type 3) referenced by trips: 125 (spec: 125, **MATCH**)
- Bus trips: 89,614
- Bus stop_times: 5,697,928
- Bus calendar.txt window: 2026-07-07 to 2026-09-30 (spec active window 2026-07-07 to 2026-09-30; calendar.txt bounds can include an outgoing/incoming regime, so this is context, not a pass/fail)
