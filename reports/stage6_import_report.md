# Stage 6a import report: `cta_ref__r20261113__gtfs8__to20260731`

Imported 2026-11-20T09:31:12+00:00 by commit `df142f6` in 1091.3 s. Schema sha256 `68dca1f96f33cd76…`. All loading ran in one transaction.

## Tables

| table | rows | source |
|---|---:|---|
| `source_files` | 9 | reports/source_register.csv |
| `gtfs_snapshots` | 8 | analytics/config/sources.json |
| `routes` | 988 | GTFS routes.txt (bus, per archive) |
| `route_shapes` | 1,976 | geometry/route_shapes.csv |
| `daily_ridership` | 1,120,604 | data/raw/ridership/CTA_-_Ridership_-_Bus_Routes_-_Daily_Totals_by_Route_20261113.csv |
| `daily_schedule` | 28,398 | expanded_scheduled_route_day_service.csv |
| `matched_utilization` | 28,374 | expanded_matched_utilization.csv |
| `ridership_without_schedule` | 424 | expanded_ridership_without_schedule.csv |
| `schedule_without_ridership` | 24 | expanded_schedule_without_ridership.csv |
| `group_versions` | 1 | artifacts/stage5/groups_manifest.json + analytics/config/group_names.json |
| `utilization_profiles` | 744 | groups__dev20251123_20260331/expanded_utilization_profiles.csv |
| `route_profiles` | 123 | groups__dev20251123_20260331/route_profiles.csv |
| `group_memberships` | 128 | groups__dev20251123_20260331/route_group_membership.csv |
| `route_stop_coverage` | 988 | groups__dev20251123_20260331/route_stop_coverage.csv |
| `route_stop_overlap` | 5,720 | groups__dev20251123_20260331/route_stop_overlap.csv |
| `model_versions` | 1 | artifacts/stage4a/model_manifest.json |

## Daily ridership (full history)

- raw export rows 1,124,170; exact duplicates removed 0
- **kept** 1,120,604 rows, 2001-01-01 → 2026-07-31, 188 route identifiers, 36 recorded zeros (kept as 0)
- **excluded** 3,566 rows after the ridership cutoff (2026-08-01 → 2026-08-31); they belong to a later data version
- spec 9.3.1 reference (compared, never forced): records 1,120,604, identifiers 188, 2001-01-01 → 2026-07-31, zeros 36

## Identities re-checked in SQL after loading (violations; all must be 0)

| identity | violations |
|---|---:|
| matched rows agree with daily_ridership (daytype, rides) | 0 |
| matched rows agree with daily_schedule | 0 |
| ridership_without_schedule rows agree with daily_ridership | 0 |
| no ridership_without_schedule row has a schedule row | 0 |
| no schedule_without_ridership row has a ridership row | 0 |
| ridership in the analysis window = matched + ridership_without_schedule (difference) | 0 |
| schedule = matched + schedule_without_ridership (difference) | 0 |
| every schedule date lies within its snapshot's applied dates | 0 |
| profile observed days and ride sums equal the matched rows of their period | 0 |

## Inputs verified before loading (sha256 against their manifests)

| input | sha256 | manifest rows |
|---|---|---:|
| `expanded_scheduled_route_day_service.csv` | `5c8790f794e6c95b…` | 28,398 |
| `expanded_matched_utilization.csv` | `7270dba7ff36073e…` | 28,374 |
| `expanded_ridership_without_schedule.csv` | `c582421d1f233592…` | 424 |
| `expanded_schedule_without_ridership.csv` | `515ecf1ece6354c4…` | 24 |
| `groups__dev20251123_20260331/expanded_utilization_profiles.csv` | `d4d394cd43bcbcbe…` | 744 |
| `groups__dev20251123_20260331/route_profiles.csv` | `df1811b76218135d…` | 123 |
| `groups__dev20251123_20260331/route_group_membership.csv` | `a12881ca41ff8917…` | 128 |
| `groups__dev20251123_20260331/route_stop_coverage.csv` | `5588822fe671820a…` | 988 |
| `groups__dev20251123_20260331/route_stop_overlap.csv` | `7688353b4e74f326…` | 5,720 |
| `geometry/route_shapes.csv` | `90e93481d9494986…` | 1,976 |
| `group_names.json` | `7104d7cde764d02b…` |  |
| `route_groups.joblib` | `33d2d42a9b77cbe4…` |  |
| `models/rf_demand.joblib` | `7ca6be08810472a2…` |  |
| `CTA_-_Ridership_-_Bus_Routes_-_Daily_Totals_by_Route_20261113` | `d9675570e50a1b3d…` |  |
| `mdb-389-202511230128` | `4a34e0c78a12d797…` |  |
| `mdb-389-202512190112` | `1d49526cbce5bf31…` |  |
| `mdb-389-202601080131` | `41cc4ddabefed327…` |  |
| `mdb-389-202602100132` | `a2115731f779a6c1…` |  |
| `mdb-389-202603260020` | `57715a5a369542ec…` |  |
| `mdb-389-202604240144` | `b3e31c8fb050b9a3…` |  |
| `mdb-389-202605300003` | `3253ed0b0e19ced0…` |  |
| `mdb-389-202607110020` | `cf14e64fa93bb3f5…` |  |

## Geometry

- label: **Most common path per direction**; tie label: "tied with {n} other path(s) this version"; coordinates [lon, lat] (GeoJSON, RFC 7946)
- definition: for each route and direction, the GTFS shape with the most trip-days on the archive's applied dates (each active bus trip counted once per applied date its service runs); exact ties go to the lowest shape_id compared as text

## Limitations

- Extracted GTFS `.txt` files are read after their ZIP's sha256 is verified; they are not re-hashed (as in Stages 2 and 5).
- The Stage 3 feature tables are not imported yet; Stage 7 (replay) adds them.
