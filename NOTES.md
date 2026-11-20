# NOTES: RouteRanker learning log

Format per step: **Built · Why · Key concept · Decisions · Results · Interview Q&A**

---

## Step 0: `.gitignore`
- **Built:** ignore rules for `docs-private/`, `data/`, `.venv/`, `node_modules/`, `.env`, `__pycache__/`, and model files in `artifacts/`.
- **Why:** the mentor's documents must never be uploaded. Data files are large and can be re-downloaded.
- **Key concept:** `.gitignore` is a bouncer at the door of the repo. Ignored files exist on your disk but Git never "sees" them, so they can't be committed by accident.
- **Decisions:** written *before* any other file, so there was never a moment when `docs-private/` could be staged. `artifacts/**` with `!artifacts/.gitkeep` keeps the folder but blocks its contents.
- **Results:** `git check-ignore -v` confirmed that both PDFs, `data/`, `.venv/` and `artifacts/model.pkl` are ignored.
- **Interview Q:** *"If a file was already committed, does adding it to .gitignore remove it?"* No. `.gitignore` only affects untracked files. You'd need `git rm --cached <file>`, and if it was pushed, the history still contains it.

## Step 1: `CLAUDE.md`
- **Built:** project rules: learning style, NOTES format, fixed pinned stack, git rules, 9.17.5 layout, CMD commands.
- **Why:** so every future session follows the same rules without being told again.
- **Key concept:** a "contract" document. Like a team charter, it removes ambiguity before work starts.
- **Decisions:** the spec (v3.8) overrides the brief, so Streamlit, Indian cities, and XGBoost-first from the brief are *not* used.
- **Interview Q:** *"Why did you use React/FastAPI and not Streamlit as the brief said?"* The later technical spec (v3.8) explicitly overrides the brief and fixes that stack. Following the newest authoritative requirement is part of the job.

## Step 2: Folders (spec 9.17.5)
- **Built:** `data/raw/{ridership,gtfs}`, `data/processed`, `analytics/{source,config}`, `artifacts`, `backend`, `frontend`, `reports`.
- **Why:** each folder has one responsibility (raw vs processed vs code vs models vs app vs reports).
- **Key concept:** *separation of concerns*. Like a kitchen with separate fridge (raw ingredients), counter (processing) and serving area (app).
- **Decisions:** the repo root plays the role of `route-ranker/` (no double nesting). Empty folders get `.gitkeep` because Git doesn't track empty folders.
- **Interview Q:** *"Why keep raw data immutable?"* So any result can be reproduced from the exact same inputs. If raw files change, you can't tell whether a result changed because of code or data.

## Step 3: Virtual environment + `requirements.txt`
- **Built:** `.venv` (Python 3.12.10) with `pandas==3.1.1`, `numpy==2.5.4`, `duckdb==2.0.0` (+ `python-dateutil==4.0.0`, `tzdata==2026.6`).
- **Why:** a private toolbox for this project, with exact versions so anyone gets the same results.
- **Key concept:** *pinning*. `pandas==3.1.1` is a recipe that names the exact brand and size, not just "some flour".
- **Decisions:** only Stage 1 needs. DuckDB is included because spec 9.17.1 says to use it for large stop-time files (some archives have about 5.7 million bus stop_times rows). Downloads, hashing and ZIP checks use the standard library, so `requests` isn't needed. scikit-learn waits for Stage 4.
- **Interview Q:** *"Why use DuckDB as well as pandas?"* DuckDB runs SQL directly on CSV files and processes them in columns, out of core. It handles millions of rows quickly without loading everything into pandas memory.

## Step 4: Source manifest (`analytics/config/sources.json`)
- **Built:** a list of the 9 expected sources: URLs, archive IDs, the capture/active/applied dates from 9.4.2, the expected sha256 values from 9.22.1, and the reference counts.
- **Why:** spec 9.4.3 says to select archives *from a manifest* and verify 8 unique IDs, never "the first google_transit.zip".
- **Key concept:** a shopping list with photos. You know exactly what you should come home with and can check it.
- **Decisions:** `primary_ridership_snapshot: null` means "automatic": the spec's 20261022 file becomes primary once it's present, otherwise the newest export. `catalog_retrieved_date` for GTFS is 2026-11-11, the date of the spec the URL list comes from. For ridership it is the date we fetched the publisher metadata.
- **Interview Q:** *"Why store expected hashes in config rather than code?"* Config is data about the sources. Keeping it separate lets you add or swap a version without touching logic, and the file itself documents the provenance.

## Step 5: Downloader (`analytics/source/download_sources.py`)
- **Built:** a downloader for the ridership CSV + publisher metadata JSON, and for the 8 GTFS ZIPs, with safe extraction.
- **Why:** a reproducible import (spec Section 8 acceptance: "reproducible source import").
- **Key concept:** *atomic write*. Download to `.part`, then rename. A half-finished file never pretends to be complete. Like a courier who only puts the parcel on the shelf once it's fully delivered.
- **Decisions:**
  - It never overwrites. The ridership file is dated by download day (`..._20261113.csv`), so the 2026-10-22 reference export (`..._20261022.csv`), if it becomes available, can sit beside it.
  - Zip-slip protection: members with absolute paths or `..` are rejected.
  - Run with `python -I` because downloaded files are untrusted.
- **Results:** ridership 23,953,761 bytes. The publisher's `rowsUpdatedAt` is **2026-10-28T16:50:20Z**, so CTA updated the dataset after the spec's 10-22 export. The 8 ZIPs total ~586 MB, with 11 files each. A rerun downloads nothing.
- **Interview Q:** *"What is a zip-slip attack?"* A ZIP member named like `../../evil.py` is written outside the target folder when extracted naively. You prevent it by validating every member path before writing.

## Step 6: Source register (`analytics/source/build_register.py`)
- **Built:** `data/raw/source_register.csv` plus a committed copy at `reports/source_register.csv`. Columns: `dataset_id, snapshot_id, source_url, catalog_retrieved_date, downloaded_at, sha256, byte_size`, plus `local_path, acquisition, row_count, source_last_updated, expected_sha256, fingerprint_match, is_primary`.
- **Why:** spec 2.1/9.4.3 require provenance (where, when, and which exact bytes) for every input.
- **Key concept:** *SHA-256 fingerprint*. Change even one byte and the hash changes completely, so two files with the same hash are (practically) identical.
- **Decisions:** the register is built by scanning the disk, so a manually placed file is registered with `acquisition=manual` and its real arrival time, never an invented download time. It also re-hashes and stops if a raw file changed since download.
- **Results (fingerprints vs 9.22.1):** all **8 GTFS archives MATCH**. The ridership export **MISMATCHES**, as expected for a newer export.
- **Interview Q:** *"Your CSV hash didn't match the reference. Is the data wrong?"* Not necessarily. A hash compares bytes, not meaning. A newer export with one extra month changes the bytes. So I compared the *content* within the reference period instead (next step).

## Step 7: Raw validation + quality report (`analytics/source/validate_raw.py`)
- **Built:** the 9.6.1 checks for ridership and GTFS, written to `reports/stage1_quality_report.md` + `reports/stage1_quality_checks.json`. Conflicting route/date rows would be quarantined to `data/processed/<snapshot>/` (none found).
- **Why:** catch bad data before any join or model, and keep a record of it (Stage 1 completion evidence).
- **Key concept:** *validate at the boundary*. Like checking deliveries at the loading dock, not after they're cooked into a meal.
- **Decisions:**
  - Dates are parsed with the explicit format `%m/%d/%Y`, never guessed.
  - Zeros are kept as real observations, and missing is kept separate from zero.
  - Duplicates and conflicts are only *reported/quarantined*, never summed.
  - GTFS times are parsed as seconds, so `25:10:00` stays on its original service date.
  - stop_times are checked with DuckDB SQL.
- **Results:**
  - Ridership: all checks pass. There are 0 duplicates and 0 conflicts, and 36 genuine zeros are kept.
  - **Content check (rows ≤ 2026-07-31) vs spec 9.3.1:** records 1,120,604 MATCH; route ids 188 MATCH; 2001-01-01 → 2026-07-31 MATCH; zero records 36 MATCH. The newer export adds **3,566 rows for 2026-08-01 → 2026-08-31** (128 routes), which are reported separately.
  - GTFS: 0 FAIL across 8 × 27 checks. Bus routes with trips are 123 for the first six archives and 125 for May/July, matching the spec. Jan 8 and Feb 10 bus stop_times are both 2,859,229, matching. April 24 has about half of May 30's stop_times, as the spec notes. All bus calendar windows equal the spec's active windows.
- **Caveat:** matching counts strongly suggest that the reference period is unchanged, but they don't prove that every ride value is identical. If the 2026-10-22 reference export becomes available, place it in `data/raw/ridership/` and rerun the last two commands; that allows an exact row-by-row comparison.
- **Interview Q:** *"Why not just delete the August rows so the file matches the spec?"* Raw data must stay immutable. Filtering is a processing decision, applied in a versioned step and documented, never by editing the source file.

## Step 8: First commit + push
- **Built:** one commit, "Setup + Stage 1 source foundation", on `tayyaba-haroon`, pushed to `origin/tayyaba-haroon`.
- **Why:** the branch is the deliverable (see the README contributing rules). Pushing makes the work visible and backed up.
- **Key concept:** *commit vs push*. A commit is a save point on your own computer. A push uploads those save points to GitHub. Like writing in your diary (commit) and then photocopying it for the school library (push).
- **Decisions:**
  - `git status` was reviewed first.
  - Only code, config, docs and reports were staged. `data/` and `docs-private/` are ignored, so they can't be included.
  - Nothing was pushed to `main`.
- **Results:** see `git log` and `git status`, which shows the branch up to date with origin.
- **Interview Q:** *"How do you make sure secrets or private files never reach GitHub?"* Ignore them *before* the first commit. Review `git status` and the staged list before committing. Check `git ls-files` afterwards. If something leaks, remove it from history and rotate any secret, because deleting it in a later commit isn't enough.

---

# Stage 2: Daily reconstruction (spec 9.5, 9.6.2-9.6.5, 9.19.1)

## Step 9: Test setup (`pytest`, `pytest.ini`, `analytics/reconstruction/`)
- **Built:** `pytest==9.2.0` (+ its 5 transitive packages, all pinned) in `requirements.txt`; `pytest.ini`; the `analytics/reconstruction/` package.
- **Why:** spec 9.19.1 lists correctness cases that must be *automatically* checked, not eyeballed.
- **Key concept:** *a unit test is a tiny experiment with a known answer*. Like checking a scale with a 1 kg weight before weighing real parcels.
- **Decisions:** pytest was approved by you (it was outside the fixed stack). Tests use tiny hand-made GTFS feeds so the right answer is obvious.
- **Interview Q:** *"Why pin pytest's transitive dependencies too?"* `pip install pytest` today and in a year can pull different `pluggy`/`packaging` versions. Pinning everything makes the environment reproducible.

## Step 10: Bus filter + route crosswalk (`gtfs_tables.py`)
- **Built:** `open_snapshot()` (DuckDB views over one archive, every value a trimmed string) and `bus_crosswalk()` (route_type 3 routes: `route_id` -> public `route`).
- **Why:** ridership uses the public name (e.g. `X9`, `N5`), GTFS joins use the internal `route_id`. The crosswalk is the translation dictionary.
- **Key concept:** *validate a join key before joining*. If one name maps to two IDs, a join silently duplicates rows, like two people sharing a phone number and both getting your calls.
- **Decisions:** one normalization for both sides: trim whitespace, keep case and prefixes (`N5` is not `5`). A non-unique or empty short name stops the build (`CrosswalkError`). Columns are read by name, because the archives' column order differs (May adds `agency_id`).
- **Results:** crosswalk unique in all 8 archives; bus routes 123 (first six) and 125 (May, July), all trip-referenced, matching spec 9.6.4.3. Recent-window ridership IDs absent from every archive: **1001, 128, 19, 5**, matching spec 9.6.4.2.
- **Interview Q:** *"Why not join on route_id directly?"* `route_id` is the agency's internal key and is not in the ridership file. The public short name is the shared language, so it is validated as one-to-one per snapshot first.

## Step 11: Daily snapshot selection (`snapshot_select.py`)
- **Built:** `select_snapshot(date, archives)`: the latest archive captured on or before the date; `selection_table()` for every date in the period.
- **Why:** spec 9.6.3: each day must be described by exactly one timetable edition.
- **Key concept:** *one whole snapshot per date, no per-route fallback*. Like reading today's newspaper: if a column was dropped, you don't fill the gap with last month's paper, because that would bring back routes that were withdrawn.
- **Decisions:** capture dates come from the manifest (`captured`), not the UTC timestamp in the archive ID (`...0128` is 01:28 UTC, which is still the previous evening in Chicago). A date with no archive yet is a reported gap (`None`), never filled.
- **Results:** for 2025-11-23 to 2026-07-31 the applied ranges equal spec 9.4.2 for **all 8 archives**.
- **Interview Q:** *"Why not just sum all ZIPs that cover a date?"* Archives overlap. Summing would count the same trip up to three times. One selected history, not eight copies.

## Step 12: Active services per date (`service_calendar.py`)
- **Built:** `active_services(calendar, calendar_dates, date)`: weekly flag within the inclusive range, minus exception type 2, plus exception type 1.
- **Why:** trips belong to a `service_id`; a trip only runs on dates its service is active.
- **Key concept:** *sets*. Adding something already in a set doesn't create a second copy, so a type-1 exception that repeats a weekly service can't double-count trips.
- **Decisions:** calendar flags, dates and exception types are validated (bad values stop the build). An empty `calendar.txt` is allowed (exception-only feeds).
- **Results:** Nov 23 archive: 49 active services on Wed 2025-11-26 vs 26 on Thanksgiving (11-27) and Christmas: weekday services removed (type 2) and holiday/Sunday services added (type 1).
- **Interview Q:** *"Order of operations: remove then add, or add then remove?"* For one service on one date GTFS allows one exception, so the order never conflicts. Applying remove-then-add mirrors the spec wording, and duplicate (service, date) exceptions are rejected as invalid.

## Step 13: Trip durations + daily scheduled service (`daily_service.py`, DuckDB)
- **Built:** `build_trip_durations()` (one row per trip: first departure, last arrival, validity and reason) and `daily_service()` (active trips -> `scheduled_trips`, `scheduled_service_hours`, `duration_complete`, `trips_missing_duration` per route/date).
- **Why:** this is the "denominator" of utilization: how much bus service was *scheduled* that day.
- **Key concept:** *elapsed time, not clock time*. `25:10:00` means 25 h 10 min after the service day starts (= 90,600 s), i.e. 1:10 am the next calendar morning but still belonging to the original service date. A clock parser would wrap it to 01:10 and make a late-night trip look like it ended before it started.
- **Decisions:**
  - First/last stop chosen by `stop_sequence`, not by the earliest/latest time.
  - Strict validity: both endpoint times present, >= 2 stop events, parseable sequences, no duplicate endpoint sequence, last arrival >= first departure. Each failure has a named reason.
  - A trip with a bad duration still counts as a trip, but then the route/day's hours are **missing** (not partially summed), because a partial sum would understate service.
  - (date, trip_id) must be unique among active trips, otherwise the build stops.
  - DuckDB reads the 3-6 million row stop_times files directly; about 3 s per archive.
- **Results (dry run):** **28,398** route/date rows, **251** dates, **125** routes: all three equal the spec. Every duration valid in these feeds. Routes 10 and 130 first active **2026-06-07** (spec 9.6.4.3).
- **Interview Q:** *"Why can total scheduled hours exceed 24 in a day?"* It's the sum over all trips; many buses run at once. 300 trips of 1 hour each = 300 scheduled hours on one route-day. It is passenger-trip time, not vehicle count or cost.

## Step 14: Exact matching + two-direction reconciliation (`matching.py`)
- **Built:** `load_ridership()` (explicit `%m/%d/%Y`, separators removed, nullable integer rides, exact copies removed, conflicts abort), `match()` (full outer join on route + date with `validate="one_to_one"`), `per_route()` and `reconciliation()`.
- **Why:** spec 9.6.4: compare rides with service only where *both* exist on the *same* date, and keep both kinds of mismatch visible.
- **Key concept:** *two different unmatched sets*. Picture two guest lists (rides, schedule). People on both lists = matched. "Rides without service" are on the ride list only. "Service without rides" are on the schedule list only. They are different people, so they are reported separately and each list adds up exactly:
  `28,798 = 28,374 + 424` and `28,398 = 28,374 + 24`.
- **Decisions:**
  - `rides` in `schedule_without_ridership` is written **empty**, never 0. A missing observation as a 0 target would teach a model that the bus carried nobody.
  - Each ride without service gets a reason (`route_absent_from_selected_snapshot` 405, `route_in_snapshot_no_active_trips` 19) plus a flag for identifiers absent from all archives (1001, 128, 19).
  - Daily ratios need a positive denominator and complete hours, otherwise they are missing.
- **Results:** 28,374 / 424 / 24 / 28,798, 251 dates, 125 routes, and every per-route row of 9.6.4.1 (1001 248/103,332 ... 7 1/17; route 169 ×24): **all MATCH**. Route 169's unmatched dates include Thanksgiving and Christmas with 1 scheduled trip each.
- **Interview Q:** *"Why validate one-to-one in the merge?"* If a key appears twice on one side, a join silently multiplies rows and inflates rides. `validate="one_to_one"` turns that silent error into a loud failure.

## Step 15: Archive integrity + timetable regimes + summaries (`regime_checks.py`)
- **Built:** order-independent content fingerprints of bus trips and stop events per archive; calendar regime listing; same-date overlap comparisons (each older archive vs the next one on the newer archive's first 7 days); ridership window summaries.
- **Why:** spec 9.6.5: prove the archives agree where they should and explain where they don't, before trusting the daily history.
- **Key concept:** *outgoing and incoming timetables*. Some ZIPs hold two timetables with back-to-back date ranges (e.g. 11-19..11-22 and 11-23..01-31), like a school publishing this term's and next term's timetables in one booklet. Each is counted only on its own dates, so smaller feeds are never "doubled".
- **Results:**
  - Jan 8 vs Feb 10: ZIP bytes differ, but the bus trips and 2,859,229 stop events are identical (MATCH). April/May stop events ratio 0.499 ("about half").
  - Overlaps: 4 of 7 pairs have no differences. The other 3 differ **only from the first day of a timetable that exists only in the newer archive** (2025-12-21, 2026-03-29, 2026-07-12), and the earlier common dates agree. These are real schedule changes that the older copy could not know about, which is exactly why each date uses the latest archive. **0 unexplained.** The spec says "five comparisons, no differences" without listing them, so ours are reported side by side, not forced.
  - Route-name presence: 98.31% vs the 8 archives. The spec's 97.95% is against the September schedule (not an input), so it is reported as not directly reproducible.
- **Interview Q:** *"Two archives give different trip counts for the same day. Which is right?"* Check *why*. Here the newer one contains a timetable starting that day which the older one predates. The selection rule (latest capture on or before the date) already picks the more informed version.

## Step 16: Orchestrator + quality report (`build_stage2.py`, `report.py`)
- **Built:** one command that re-hashes every input, rebuilds everything, writes the 4 spec 9.8 CSVs + `manifest.json` to `data/processed/cta_ref__r20261113__gtfs8__to20260731/`, and writes `reports/stage2_quality_report.md` + `.json`.
- **Why:** spec 9.6.6: later stages must read versioned products, not variables from a notebook.
- **Key concept:** *a data version is a sealed box with its label*. The folder name and manifest record exactly which inputs (sha256), period and code (git commit) produced it. If an input changes, the build refuses to reuse the folder and a new version is needed.
- **Decisions:** reference numbers live in `sources.json` (`stage2_reference`), not in code. Any MISMATCH is listed with the provenance note that our ridership export is newer than the spec's.
- **Results:** **51 MATCH, 0 MISMATCH**. The ridership export differs in bytes from the spec's, but its content up to 2026-07-31 reproduces every reference count. 3,566 August rows were excluded and reported. 0 selection gaps.
- **Interview Q:** *"Your numbers match the spec exactly. How do you know you didn't just tune them?"* The reference values are only *read* by the report. No rule depends on them, the rules come straight from the spec text, and the unit tests verify each rule on tiny hand-built feeds with known answers.

## Step 17: Automated correctness tests (`analytics/tests/`)
- **Built:** 22 pytest tests.
  - `test_schedule.py` covers the 9.19.1 schedule cases: type-2 removal; type-1 added once; 25:10 stays on its date; outgoing/incoming regimes; one snapshot per date with no per-route fallback. It also covers invalid durations giving missing hours, stop_sequence ordering, exception-only calendars, the bus filter and a non-unique crosswalk.
  - `test_matching.py` covers missing vs zero rides, both unmatched directions with identities and per-route grouping, ratio denominators, one-to-one failure, exact identifiers, the explicit date format and conflicts not being summed.
  - `test_outputs_integration.py` checks invariants on the real outputs.
- **Why:** the spec says "verify", and matching numbers alone could hide two bugs that cancel out. Each rule needs its own proof.
- **Key concept:** *tiny feeds with known answers*. A 2-stop trip from 24:30 to 25:10 must give 40 minutes. If the code says 23 h 20 min, it wrapped the clock. The tests call the **real** pipeline functions on these feeds.
- **Decisions:** the integration tests check invariants (identities, unique keys, missing-not-zero, one snapshot per date) but do **not** assert the spec's counts. Comparing to references is the report's job, so the tests can never "force" a number. Pipeline 9.19.1 cases (lags, replay, ranking, etc.) belong to later stages.
- **Results:** 22 passed. *Mutation check:* three bugs planted in a scratch copy (partial hours sum, missing rides written as 0, type-2 exceptions adding instead of removing) were each caught by exactly the intended test.
- **Interview Q:** *"How do you know your tests actually test anything?"* Break the code on purpose (mutation testing). A test that still passes when the rule is broken isn't protecting that rule.

---

# Stage 3: Feature contracts (spec 9.9, 9.10.2-9.10.4, 9.14.3). No model training.

## Step 18: Settings + shared naming module (`analytics/config/features.json`, `analytics/features/naming.py`)
- **Built:**
  - `features.json` holds: reporting delay (1 day), issue time, archive-availability policy, lags, split ranges, policy choice, and the fixed Sunday-service holiday list.
  - `naming.py` holds the 9.9.1 name mapping and the 9.9.5 predictor lists.
  - `sources.json` gained `stage3_reference`.
- **Why:** the same names and settings must be used in training, evaluation and the backend. If each script re-typed them, one typo would quietly feed the model a different column.
- **Key concept:** *a single source of truth*. Like one master key cabinet instead of copies cut by each person.
- **Decisions:**
  - Exported CSVs keep the reference names (`lag_7d_boardings`). The model names (`rides_7_days_before`) are applied once in preprocessing.
  - **Your change:** `is_sunday_holiday_daytype` is kept in the export for auditing only, because it comes from the target-date ridership row. The predictor is `is_sunday_holiday_service_day`, built from Sundays plus a fixed holiday list, which is known before the day.
- **Interview Q:** *"Why is a feature from the target row's daytype a leak even though it's not the rides count?"* At forecast time that row doesn't exist yet. The daytype is reported along with the rides. Using it means using information from the future, however small.

## Step 19: Exact-date lags + calendar fields (`analytics/features/lags.py`)
- **Built:** `to_history()` (unique route/date check), `add_exact_lags()`, `add_seasonal()`, `add_calendar()`, `sunday_holiday_service_day()`.
- **Why:** spec 9.9.4: lags are the main forecasting inputs and must mean exactly "this route, k calendar days ago".
- **Key concept:** *join on the date, don't shift the rows*. `shift(1)` gives "the previous row", which after a weekend gap is Friday, not Sunday. Joining on (route, date − k) asks the diary for a specific page. If the page is blank, the answer is blank.
- **Decisions:**
  - The full history up to 2026-07-31 is kept for lookups. Rows are restricted to the 2024-08-01 window only after the lags are looked up.
  - A lag shorter than the reporting delay is set missing (issue-time rule, 9.10.4).
  - The seasonal mean needs at least 2 of the 7/14/21/28-day lags.
- **Results:** 83,997 target rows. **Worked example (9.9.3) reproduced exactly:** route 1, 2024-08-01: rides 990, day 3, lags 1,111 / 1,219 / 1,134 / 1,040 / missing, 3 observations, mean 1,131.
- **Interview Q:** *"Is the 28-day lag a 28-day total?"* No. It's one day's rides exactly four weeks earlier. The seasonal mean (1219 + 1134 + 1040) / 3 = 1131 is a summary of real past observations, not a made-up observation.

## Step 20: `daily_forecasting_features.csv` (16 columns, spec 9.9.1)
- **Built:** one row per route/target date, 2024-08-01 to 2026-07-31, with `route, date, daytype, rides, day_of_week, month, is_weekend, is_sunday_holiday_daytype`, the five lags, `seasonal_lag_observations`, `past_four_same_weekdays_mean` and `split`.
- **Why:** this is the training table of the planned demand forecaster.
- **Key concept:** *look up first, trim second*. Restricting to the window **after** the lookups lets the first rows (August 2024) still find their July lags.
- **Results:** 83,997 rows, 16 columns (MATCH).
- **Interview Q:** *"Why keep `daytype` and `rides` in the feature table if they're not inputs?"* `rides` is the target and `daytype` is for auditing. The schema labels each column's role, so the pipeline knows what it may feed the model.

## Step 21: `expanded_demand_service_features.csv` (22 columns, spec 9.9.2)
- **Built:** the 16 columns plus `service_date, scheduled_trips, scheduled_service_hours, duration_complete, source_snapshot, archive_available_from`, by an exact one-to-one route/date join with the Stage 2 matched table.
- **Why:** the schedule-augmented experiment needs demand history and planned service side by side.
- **Decisions:**
  - The build stops if any matched row lacks a feature row, or if the rides values disagree.
  - **Changed from the plan** (because of your 9.14.3 correction): `archive_available_from` = capture date **+ 1 day**, i.e. the first issue date on which the archive may be used, not the capture date.
- **Results:** 28,374 rows, 22 columns, `service_date == date` everywhere.
- **Interview Q:** *"Why store an 'available from' date for a timetable?"* A model must only see what was knowable at forecast time. The date turns "could we have known this?" into a simple comparison.

## Step 22: Chronological splits (`analytics/features/splits.py`)
- **Built:** `parse_ranges()` (rejects overlapping or out-of-order ranges), `assign_split()` (every row gets exactly one label; an out-of-range date stops the build), `date_overlap()`.
- **Why:** spec 9.10.3: forecasting is judged on the future, so the test period must come after everything the model learned from.
- **Key concept:** *time-ordered exams*. Shuffled splits would let the model "study" days that fall between its test days, which is like seeing tomorrow's newspaper.
- **Results:** demand-only 63,143 / 10,246 / 10,608 and matched 14,501 / 6,859 / 7,014: all MATCH; 0 dates shared between splits in either table.
- **Interview Q:** *"Why do the two tables have different test periods?"* The matched table only starts on 2025-11-23 (first archive). Comparing schedule vs demand-only models fairly needs the *same* matched rows, which is a Stage 4 rule.

## Step 23: Shared preprocessing: Option 2 + Option 1 (`analytics/features/preprocess.py`)
- **Built:** `prepare(features, policy, holidays, with_schedule)`: name mapping, issue-time holiday predictor, history policy, schedule check, and `eligible` + `withheld_reason` per row.
- **Why:** spec 9.10.2: one pipeline for training, evaluation and the backend, so they can never disagree.
- **Key concept:** *count before you fill*. `available_same_weekday_observations` and the seasonal mean are taken from the export, which is computed before any filling. Option 2's filled 28-day value can never pretend to be a real observation, and the flag (`rides_28_days_before_available = 0`) tells the model it's an estimate.
- **Decisions:**
  - Option 2 fills only the 28-day lag (mean of the available 7/14/21-day values).
  - A row is withheld if the 1/7/14/21-day lag is missing or if there's no donor.
  - The schedule model also needs valid schedule inputs (never filled).
  - No statistics are learned from other rows, so there's nothing to leak. The route encoder (fit on training data only) is Stage 4.
- **Results:** Option 1 withheld 1,073 / 299 / 523 (1,895 in total); Option 2 withheld 1,036 / 299 / 472; Option 2 gains +51 test rows. **All MATCH.** Routes 10/130: Option 1 eligible 43/42 of 55, Option 2 50/49, which agrees with spec 9.10.6.
- **Interview Q:** *"Isn't filling a missing lag just making data up?"* It's an estimate made only from the same route's *own* earlier observations, flagged as filled, and only for one input. Targets are never filled, and Option 1 is kept to measure what the fill changes.

## Step 24: Feature schema + missing-history report (`analytics/features/schema.py`)
- **Built:** `feature_schema.json` (v1.0.0). For each column it records the export and model names, type, nullability, roles (key / target / predictor / control) and tables; it also lists the preprocessing-derived columns, settings and input fingerprints. Also `lag_absence_by_route_split.csv` and a classification of each missing lag by the schedule context of the *earlier lag date*.
- **Why:** spec 9.6.4.3 / 9.9.4 step 8: the contract must be explicit and saved with the data version.
- **Key concept:** *a missing value has a story*. 145 of the 182 missing 28-day lags fall on dates the route simply didn't run (a service pattern). Only 12 are real passenger-data gaps (route 169).
- **Results:** 182 = 145 + 25 + 12, route 10: 12, route 130: 13; 1,453 = 1,449 + 4. **All MATCH.** No lag date fell before the first archive, so the extra category planned for that case wasn't needed.
- **Interview Q:** *"Why classify missing lags instead of just counting them?"* Different causes need different fixes. A weekday-only route will always lack a 1-day lag on Mondays; that isn't a data error, and requiring that lag would quietly drop routine patterns.

## Step 25: Forecast-input schedule + issue-time holiday predictor (your two changes)
- **Built:**
  - `select_forecast_snapshot()`: latest archive captured **strictly before** the target date.
  - `forecast_schedule.py`: rebuilds the schedule from the earlier archive on boundary dates.
  - `forecast_schedule_inputs.csv`.
  - `is_sunday_holiday_service_day` = Sunday or a date in the fixed holiday list in `features.json`.
- **Why:** spec 9.14.3 and 9.9.1: a forecast issued at the start of D can't use an archive captured sometime during D, or the daytype reported with D's rides.
- **Key concept:** *two clocks*. Describing a day after the fact may use anything captured that day. Forecasting it may only use what existed before the day began.
- **Results:**
  - The 8 capture dates are the boundary dates. On 7 of them the earlier archive gives **identical** trips and hours. On 2025-11-23 there is no earlier archive, so 86 matched rows have no forecast schedule. This raises schedule-model withholding in train by 86 (Option 2: 1,036 → 1,122), reported separately from the spec reference.
  - Holiday predictor vs reported daytype: 182 rows on 2 dates disagree. **2026-07-04 (Saturday)** was reported as `A` while **2026-07-03 (Friday)** was reported `U`. CTA ran Sunday service on the observed Friday holiday, which the fixed list (actual dates) doesn't capture. It's reported; the list is not changed to fit the data.
- **Interview Q:** *"Your holiday list disagrees with the data on July 3-4. Why not just fix the list?"* Editing a "known in advance" calendar after seeing the outcome would be fitting to the answer. The right fix is a documented rule decided on its own merits (e.g. use the observed federal holiday), then rebuild.

## Step 26: Orchestrator, report and tests
- **Built:** `build_stage3.py`, which verifies Stage 2 hashes and the raw ridership hash, writes 6 CSVs + schema + manifest to `data/processed/cta_ref__r20261113__gtfs8__to20260731/features__delay1d/`, and writes `reports/stage3_quality_report.md` + `.json`. Tests: `test_features.py` (13) + `test_features_integration.py` (6).
- **Results:** **42 MATCH, 0 MISMATCH.** 41 tests pass (22 Stage 2 + 19 new) with no warnings, after switching the deprecated `dt.dayofweek` to `dt.day_of_week`; the rebuild gave byte-identical outputs. Mutation check: four planted bugs ("previous row" lags, a mean from one seasonal lag, same-day archive used for forecasting, the holiday predictor reading daytype) were each caught.
- **Interview Q:** *"How do you prove a feature can't see its own target?"* Change only the target value and rebuild. If any feature for that row changes, it was leaking. The test does exactly that.

## Step 27: US federal observed-holiday rule (`features.json`, `lags.observed_date()`)
- **Built:** `sunday_service_holidays.observance_rule = "us_federal_observed"` in `features.json`, with `observed_date()` / `observed_holidays()`. A holiday on a Saturday is observed on the Friday before; one on a Sunday is observed on the Monday after. The predictor marks the observed date. The list still stores each holiday's actual date, and the manifest records the observed dates. One new test covers the rule.
- **Why (the reason for the decision):** this is an **official rule published in advance** (5 U.S.C. 6103(b), applied by OPM every year), so a forecaster on any earlier date could have known it. It is adopted as a documented rule, **not fitted to the outcome**. The July 3/4 disagreement is what prompted the question, but the rule is chosen because it is official and known beforehand, not because it removes the disagreement. A list edited to whatever the data showed would be a leak.
- **Key concept:** *a rule vs a patch*. A patch ("mark 2026-07-03 because the data said U") only fixes the one case you've already seen. A rule ("Saturday holidays move to Friday") makes the same prediction for future years before you see them.
- **Results:** Stage 3 rebuilt: 42 MATCH, 0 MISMATCH. Daytype disagreements: **0 rows on 0 dates** (before the rule: 182 rows on 2 dates, 2026-07-03 and 07-04). The exported CSVs are unchanged; the predictor lives in the shared preprocessing. 42 tests pass.
- **Caveat:** in this window the only weekend holiday is 2026-07-04, so the rule is confirmed on one case. That agreement is evidence, not proof that CTA always follows it.
- **Interview Q:** *"Isn't changing the holiday rule after seeing a mismatch also fitting to the data?"* The difference is whether the new input could have been known in advance and is defined independently of the outcome. The federal observed-date rule is both, and it's documented with its source. A hand-picked date list matching the data would be neither.

---

# Stage 4a: baselines, Ridge and Random Forest (notebook conventions; no neural networks)

> The mentor's reference notebook overrides the spec wherever the two differ (your rule for this stage).

## Step 28: Comparison of our Stage 3 features with the notebook's `build_features`
- **Built:** a 13-row comparison table: target population, rows without rides, 2025-11-23, Sunday-like flag, required fields, reason format, 28-day column, names, feature order, split edges, route case, trip-hours validity, dtypes. It is reproduced in `reports/stage4a_quality_report.md`.
- **Why:** before training, both pipelines must agree on *which rows* and *which inputs*. Otherwise any difference in scores could come from different data, not different models.
- **Key concept:** *same exam, same questions*. Two students can only be compared if they sat the same paper. Our Stage 3 table and the notebook's table were "different papers": the notebook's target rows are every route/day in the **forecast-time schedule**, while ours were matched rides on the descriptive schedule.
- **Results:** our eligible counts already equalled the notebook's (13,379 / 6,560 / 6,542). Only the target population differed: −86 rows on 2025-11-23 (no archive saved before it) and +15/+5/+4 scheduled days with no rides (withheld, never zero). 14,501 − 86 + 15 = **14,430**.
- **Interview Q:** *"Your counts differed from the reference. How did you find out why?"* I decomposed the difference into named populations (rows dropped for a reason, rows added for a reason) until the arithmetic closed exactly, instead of adjusting code until the numbers matched.

## Step 29: Aligning the pipeline with the notebook
- **Built:**
  - `naming.py` now uses the notebook's names (`boardings_7d_ago`, `seasonal_mean`, `boardings_28d_filled`, `scheduled_hours`, ...), with a `NOTEBOOK_TO_SPEC` map. `REQUIRED`, `DEMAND_FEATURES` and `SERVICE_FEATURES` are in the notebook's order.
  - New `sunday_like.py` holds the schedule-based flag.
  - New `model_features.py` (`issue_schedule`, `build_features`, `attach_actuals`) is **the only place model inputs are built**.
  - `build_stage3.py` (schema 1.1.0) writes `feature_rows.csv` + `sunday_like_days.csv`.
  - `preprocess.prepare()` is kept only as the spec Option 1/2 audit.
- **Why, change by change:**
  1. *Population = forecast-time schedule.* A forecast for day D is issued before D, so the rows it can serve are the route/days the timetable known before D lists.
  2. *Days without rides stay as rows* with reason `no recorded boardings`, so coverage shows them instead of hiding them.
  3. *Sunday-like flag from the schedule* (more than half of the day's bus trips belong to Sunday-only services) replaces our holiday list, as in the notebook. Both are known at issue time, and both disagree with the reported `U` daytype on **0** rows.
  4. *One required list for every method*, so the demand-only and demand+schedule models are scored on **identical rows** (spec 9.10.1 controlled comparison).
  5. *The raw 28-day value is kept*, with the fill in its own column, so you can always audit what was observed and what was estimated.
  6. *Feature order matches the notebook*, because a Random Forest breaks ties by column order.
- **Key concept:** *one recipe, one kitchen*. If training and the replay each had their own copy of the feature rules, a small difference would mean the model is served inputs it never trained on. `build_features` is the single recipe.
- **Decisions:**
  - The exported spec CSVs keep their names, so the 42 spec checks still run unchanged.
  - The notebook's row counts live in `sources.json` → `notebook_reference`, next to the other references (not in `models.json`, so Stage 3 doesn't need to read model settings).
  - Two differences have 0 effect and are only reported: route upper-casing (no lower-case routes exist) and the 1e-6 rounding of hours.
- **Results:** Stage 3 rebuilt with **50 MATCH, 0 MISMATCH** (42 spec checks + 6 notebook counts + 2 consistency checks):
  - train 14,430 / 13,379, validation 6,864 / 6,560, test 7,018 / 6,542, all exactly.
  - Sunday-like dates: 40 of 250, 5 of them non-Sunday holidays (including 2026-07-03).
  - Withheld-reason breakdown identical. No exception-only bus services.
  - 48 tests pass (42 existing + 6 new).
- **Interview Q:** *"Why not use the reported daytype U as the holiday flag? It's perfect."* It arrives with the rides, after the day. A flag derived from the timetable published *before* the day gives the same answer here and is legitimately available at forecast time.

## Step 30: Dependencies
- **Built:** `scikit-learn==1.9.1` and `joblib==1.6.0`, plus their transitive packages, all pinned: `scipy==1.18.1`, `threadpoolctl==3.8.0`, `narwhals==2.29.0`, `cloudpickle==3.1.3`. `pip check` is clean.
- **Why:** scikit-learn is in the fixed stack (Ridge, Random Forest, encoders). joblib saves fitted pipelines, as the notebook does.
- **Key concept:** *transitive dependencies*. Installing one package brings in the packages it needs, like buying a printer that needs its own cable. They're pinned too, so a future install can't silently swap them.
- **Decisions:** `narwhals` and `cloudpickle` were not in the plan list. They're automatic requirements of scikit-learn and joblib, not tools we chose. No matplotlib, XGBoost or PyTorch.
- **Interview Q:** *"Your library versions differ from the notebook's (sklearn 1.6.1). Does that matter?"* Ridge and the baselines are deterministic arithmetic and should match closely. A Random Forest's tree-building internals can change between versions, so small RF differences are expected and must be reported, not hidden.

## Step 31: Scoring function (`analytics/models/scoring.py`)
- **Built:** `score()` returns MAE, RMSE, WAPE %, the absolute-error sum and the actual sum. `evaluate()` adds target/scored/withheld counts, coverage and withheld counts by reason.
- **Why:** spec 9.10.3 asks for errors *and* how many rows got a forecast. An accurate model that forecasts only half the rows isn't comparable to one that forecasts all of them.
- **Key concept:** *WAPE needs a positive denominator*. WAPE = total error / total actual boardings. If the actual total is 0, the ratio has no meaning, so it is **unavailable** (None), never 0% and never infinite.
- **Decisions:**
  - `evaluate` calls the predictor with **eligible rows only**, so a withheld row can never be scored, even as 0.
  - An eligible row with no forecast raises an error instead of being silently dropped, because that would quietly change the scored population.
- **Interview Q:** *"Why report RMSE as well as MAE?"* MAE is the typical miss in boardings. RMSE squares the misses, so it grows when a few days are badly wrong. Comparing the two shows whether the error is spread evenly or driven by a few large misses.

## Step 32: Baselines (`analytics/models/baselines.py`)
- **Built:** `last_week` returns `boardings_7d_ago`. `seasonal_mean` returns the mean of the available 7/14/21/28-day values.
- **Why:** spec 9.10.1 steps 1-2. A model is only worth serving if it beats these simple rules.
- **Key concept:** *a baseline is the "do nothing clever" answer*. Like predicting tomorrow's weather as "same as today": if your fancy model can't beat that, it isn't adding anything.
- **Interview Q:** *"Can a baseline be the serving method?"* Yes. If it wins on validation, it is served. The bundle then has no pipeline file, only the rule.

## Step 33: Ridge and Random Forest pipelines (`analytics/models/regressors.py`)
- **Built:** `make_regressor()` builds one Pipeline: OneHotEncoder (route, `handle_unknown="ignore"`) + StandardScaler (numeric columns) + Ridge(alpha=100) or RandomForest(100 trees, depth 16, leaf 10, seed 42). `fit_candidates()` fits the 4 candidates on **eligible training rows only**. `make_predictor()` floors predictions at 0.
- **Why:** the encoder and scaler are *learned* state. If they saw validation or test rows, the validation score would be quietly helped by the answers.
- **Key concept:** *one pipeline = one sealed box*. Encoder, scaler and model are saved together, so the backend can't accidentally use a scaler fitted on different data.
- **Results:** 8 unit tests pass:
  - encoder and scaler learn from training rows only;
  - an unseen route still predicts;
  - withheld rows are never seen by the predictor (a 1e9 sentinel actual has no effect);
  - WAPE is unavailable for a zero total;
  - a real 0 actual is scored, a missing actual can't be;
  - the floor turns real negative Ridge outputs into exactly 0;
  - compressed models reload to **exactly** equal predictions.
- **Interview Q:** *"Why does `handle_unknown='ignore'` not 'solve' new routes?"* It only prevents a crash. The new route gets no route-specific adjustment. Its forecast comes purely from its own lags and schedule, so its error should be reported separately (routes 10 and 130).

## Step 34: Training orchestrator (`analytics/models/train_stage4a.py`)
- **Built:** one command that runs these steps in a fixed order:
  1. verify the `feature_rows.csv` hash;
  2. fit 4 pipelines on eligible training rows;
  3. score all 6 methods on the identical validation rows and select the lowest MAE;
  4. **freeze**: save `artifacts/stage4a/models/*.joblib` (compress=3), `serving_bundle.joblib`, `feature_contract.json` and `validation_predictions.csv`, check sizes, reload and compare;
  5. **only then** score the test period once.

  The outputs go to `model_manifest.json`, `reports/stage4a_*`.
- **Why:** the order *is* the safeguard. Once the files are frozen and hashed, nothing the test period shows can change a choice.
- **Key concept:** *seal the envelope before opening the exam results*. Selection happens on validation. The test is opened once, after the choice is locked.
- **Decisions:**
  - **Your addition:** every `.joblib` is saved with `compress=3`. Both sizes are recorded (uncompressed = the same object dumped into memory), plus the sha256 of the saved file. The 20 MB check (20,000,000 bytes) applies to the saved file.
  - **A finding at the freeze step:** the first run **stopped before any test scoring**, because the reloaded Random Forests didn't reproduce their predictions exactly. The cause wasn't compression. With `n_jobs=2`, sklearn adds the 100 tree predictions in whichever order the threads finish, so even the *same in-memory model* gave answers 3.6e-12 boardings apart on two calls. `n_jobs=1` builds the same trees (each tree's seed is fixed in advance) and predicts exactly repeatably. It was changed in `models.json`, with a note, before any test number existed. A test guards it.
- **Results:** sizes (uncompressed → saved):
  - `rf_demand` 9.56 MB → **3.18 MB**; `rf_service` 9.54 MB → **3.18 MB**;
  - the Ridge models ~5 KB → ~3 KB; the bundle 1 KB.

  All are under 20 MB, and all 4 reloaded pipelines reproduce the validation predictions **exactly**.
- **Interview Q:** *"Why would a model give slightly different answers on the same input?"* Floating-point addition isn't associative: (a+b)+c can differ from a+(b+c) in the last bits. Parallel threads that add results in varying order make the sum vary. For an auditable system you want bit-identical replays, so you remove that source of noise.

## Step 35: Results and the Stage 4a quality report (`reports/stage4a_quality_report.md`)
- **Row counts vs the notebook: 6 MATCH, 0 MISMATCH.** Train 14,430 / 13,379, validation 6,864 / 6,560, test 7,018 / 6,542. The difference from the spec's 14,501 / 6,859 / 7,014 is explained exactly: −86 rows on 2025-11-23 (no earlier archive) and +15/+5/+4 scheduled days with no record. Key sets were checked too, not just totals.
- **Validation (selection, identical 6,560 rows):**

  | method | MAE | WAPE |
  |---|---:|---:|
  | rf_demand | **345.47** | 6.40% |
  | rf_service | 354.08 | 6.56% |
  | seasonal_mean | 360.36 | 6.67% |
  | last_week | 375.18 | 6.95% |
  | ridge_demand | 400.56 | 7.42% |
  | ridge_service | 437.14 | 8.09% |

  **Selected: `rf_demand`.**
- **Honest losses:** both Ridge models **lose to the seasonal-mean baseline** on validation and on the test. Adding schedule inputs did **not** help either model family on these identical rows (rf_service is worse than rf_demand).
- **Test (reused holdout, scored once):** rf_demand MAE 398.01 / WAPE 7.67% vs seasonal mean 421.15 / 8.12%.
  - By day type, rf_demand has the lowest WAPE on W (7.00%) and A (8.67%). On U, rf_service is lower (11.35% vs 11.75%). Test numbers are reported, not used to switch methods.
  - Routes 10 / 130 (unseen in training; 5 and 6 rows withheld for a missing 21-day lag): rf_demand WAPE 26.6% / 18.9%. On route 10, `last_week` (25.8%) does slightly better than the served model.
- **Tests:** 62 pass (14 new unit + 5 new integration tests). Mutation check: no floor, scaler fitted on all rows, withheld scored as 0, and WAPE 0 for a zero total were **each caught**.
- **Interview Q:** *"Your Random Forest beat the baseline by about 4% MAE. Is that a real improvement?"* On validation it's consistent across day types, and on identical rows. But the test period is a reused holdout and the margin is modest, so I'd call it evidence, not proof, and keep the seasonal mean as the comparison in every report.

---

# Stage 4b: neural network models (an additional modelling experiment)

## Step 36: PyTorch dependency
- **Built:** `torch==2.15.0` (CPU build, `2.15.0+cpu`) plus its 9 transitive packages, all pinned in `requirements.txt`: `filelock`, `fsspec`, `Jinja2`, `MarkupSafe`, `mpmath`, `networkx`, `setuptools`, `sympy`, `typing_extensions`. `pip check` is clean.
- **Why:** the MLP, LSTM, GRU and 1D CNN need a neural network library. PyTorch is the library the project rules allow for this experiment.
- **Key concept:** *CPU vs GPU builds*. The same PyTorch version comes in a CPU build and in CUDA (GPU) builds. A GPU build is much larger and can give slightly different floating-point results. We confirmed `torch.version.cuda is None`, so every run uses the same CPU arithmetic.
- **Decisions:** none of the transitive packages were chosen by us. They are what torch needs, and they're pinned so a future install can't swap them. No other new tools.
- **Results:** installed; `torch.cuda.is_available()` is `False`.
- **Interview Q:** *"Why pin `sympy` when you never import it?"* torch imports it internally. If it isn't pinned, a later install could pick up a newer sympy that changes or breaks torch's behaviour, and the build would no longer be reproducible.

## Step 37: Settings fixed before training (`analytics/config/neural.json`)
- **Built:** one config holding every Stage 4b setting:
  - seed 42, CPU, deterministic algorithms, 1 thread;
  - the sequence rule: 28 exact calendar days, with a `value` channel and an `observed` channel;
  - the static inputs: route one-hot and 4 calendar fields;
  - the four small architectures;
  - one training recipe for all four: Adam, lr 0.001, batch 128, MSE, at most 200 epochs, patience 20;
  - the early-stopping range, the 20 MB limit and compression level 3.
- **Why:** every choice must exist *before* any result does. If a setting could be changed after seeing scores, a good score might come from tuning to that period rather than from a better model.
- **Key concept:** *a three-way split of time*. The fit part (training rows before 2026-03-10) is where the network learns. The early-stopping part (2026-03-10 to 2026-03-31) is where it is told when to stop. Validation (April to May) is where methods are compared. Each period answers one question only. Like a student who studies from the textbook, checks progress on practice papers, and is graded on a mock exam they've never seen.
- **Decisions:**
  - **Your change:** early stopping uses the last three weeks of training, not validation. Validation stays untouched for selection only, exactly as for the Random Forest, so the comparison is fair. The cost is fewer rows for the networks to learn from, and the report will say so.
  - Missing days are a placeholder (the training mean, in scaled units) plus `observed = 0`, never "0 boardings".
  - Stage 4b never changes the Stage 4a serving bundle without asking.
- **Results:** the file parses; no training has run.
- **Interview Q:** *"Why not just use the validation set for early stopping? Everyone does."* Then validation would help choose the network's stopping epoch, and the same validation score would be used to compare it with the Random Forest, which never saw validation at all. The network would get a small hidden advantage. A separate stopping set keeps the comparison fair.

## Step 38: 28-day sequences (`analytics/models/sequences.py`)
- **Built:** `build_sequences()` returns two arrays of shape (rows, 28). One holds the raw boardings for D-28 … D-1, with NaN for no record. The other is the `observed` flag (1 or 0). `check_against_lags()` is the guard.
- **Why:** a sequence model (LSTM, GRU, CNN) can look at the whole last four weeks, not just the five lags the Random Forest gets. That only helps if every position really means "this route, exactly k days earlier".
- **Key concept:** *a diary opened at exact pages*. Each position is looked up by date (route, D − k). A blank page stays blank and is marked `observed = 0`. Nothing is copied from the nearest written page. A recorded 0 is a written page that says 0, so it is `observed = 1`.
- **Decisions:**
  - Positions run oldest to newest (position 0 = D-28, position 27 = D-1), so recurrent networks read forwards in time.
  - The history is the raw ridership loaded with the same `load_ridership` → `to_history` as Stage 3, after checking its fingerprint. `feature_rows.csv` starts on 2025-11-24, too late for 28-day windows in November.
  - Scaling and the placeholder for missing days come later, from the preprocessor fitted on the fit part only.
- **Results (dry run, nothing trained):**
  - all 28,312 feature rows; the guard reports D-1/7/14/21/28 **equal** to the Stage 3 lags;
  - missing days in eligible windows: train 18,239 of 374,612 (4.9%), validation 9,500 of 183,680 (5.2%), test 10,044 of 183,176 (5.5%).
- **Interview Q:** *"How do you know your 28-day window isn't off by one day?"* It was built by a second, independent lookup, and five of its positions must equal the lag columns that Stage 3 built and tested. If the window were shifted by one day, those positions would disagree on thousands of rows and the build would stop.

## Step 39: Networks, preprocessing and training loop (`analytics/models/neural.py`)
- **Built:**
  - `training_parts()` splits the eligible training rows into a fit part and a stop part, and refuses any other row;
  - `NeuralPreprocessor`: route one-hot, calendar scaler and boardings mean/std, all fitted on the fit part only;
  - the four networks, with parameter counts MLP 13,889, LSTM 9,761, GRU 8,609, CNN 6,689;
  - `set_deterministic()`;
  - `train_network()`: Adam, seeded shuffling, early stopping on the stop part, best weights restored;
  - `make_nn_predictor()`;
  - `network_payload()` / `load_network()`.
- **Why:** the four networks share one recipe and one preprocessor, so any difference in their scores comes from the architecture, not from different data handling.
- **Key concept:** *how each network reads four weeks*.
  - The MLP sees all 56 numbers at once, like a spreadsheet row.
  - The LSTM and GRU read the days in order and carry a memory forward, like reading a diary page by page.
  - The CNN slides a 7-day window along the sequence looking for weekly patterns, like a stencil moved along a ruler.

  All four then combine what they found with the route and the calendar.
- **Decisions:**
  - **A finding before any training:** a float32 network's answer for a row depended slightly on how many rows were predicted together (at most about 0.001 boardings). The library adds numbers in a different grouping for different batch sizes. It's the same problem as `n_jobs=2` in Stage 4a. The predictor now runs one row at a time, so one day's replay and a full-period run give bit-identical forecasts. This costs a few seconds and leaves training unchanged.
  - The loss is read with `loss.detach().item()` to avoid a PyTorch warning; the value is the same.
  - Weights are saved as numpy arrays, not pickled torch objects.
- **Results (smoke check, no real training):**
  - fit part 10,988 rows (2025-11-24 to 2026-03-09) plus stop part 2,391 (2026-03-10 to 03-31) = 13,379, exactly the eligible training rows;
  - 123 routes in the fit part;
  - training twice on synthetic data gives bit-identical weights for all four networks;
  - single-row, subset and reversed-order predictions all equal the full batch.
- **Interview Q:** *"Your network gives a different answer for the same row depending on the batch. Isn't that a bug?"* It's float32 arithmetic. The library sums in blocks whose size depends on the batch, and (a+b)+c is not always a+(b+c). The model isn't wrong, but it isn't exactly repeatable either. Predicting row by row makes the result independent of how rows are grouped, which an auditable replay needs.

## Step 40: Unit tests (`analytics/tests/test_neural.py`)
- **Built:** 11 test functions (20 cases, because four run once per architecture) on tiny synthetic histories:
  - a gap gives `observed = 0`, not the previous day;
  - a recorded 0 is `observed = 1` and differs from the placeholder;
  - the target day and later days never change the window;
  - the guard catches a one-day shift;
  - the fit and stop parts are correct, and validation rows are refused;
  - the preprocessor learns from the fit part only;
  - training twice gives bit-identical weights;
  - a saved and reloaded network (compress=3) reproduces predictions exactly, including an unseen route;
  - the floor at 0 works;
  - predictions don't depend on how rows are grouped;
  - early stopping stops and restores the best epoch.
- **Why:** each rule needs its own proof. A good overall score could hide a leak or a shift that happens to help.
- **Key concept:** *test the rule, not the result*. The leak test sets every boarding count on and after the target day to 10⁹. If the window changed at all, the network could be seeing the future. Like checking an exam room for hidden notes, not just looking at the grades.
- **Decisions:** the tests read the real `neural.json`, overriding only epochs and patience to keep them fast, so they test the configured settings and not a copy.
- **Results:** 20 passed in 8.3 s. The mutation check (deliberately breaking rules) is in the final step.
- **Interview Q:** *"How do you test that early stopping really restored the best weights?"* Recompute the stop-part loss with the returned model and compare it with the best loss recorded during training. If the model kept the last epoch's weights instead, the two numbers would differ.

## Step 41: Orchestrator, report and the training run (`train_stage4b.py`, `report4b.py`)
- **Built:** one command that runs these steps in a fixed order:
  1. verify the hashes of the feature rows, the raw ridership and every frozen Stage 4a file;
  2. build the 28-day windows and run the guard;
  3. train the 4 networks on the fit part (early stopping on 2026-03-10..03-31);
  4. score all ten methods on the identical validation rows with the unchanged Stage 4a scoring, and require the Stage 4a methods to reproduce their stored predictions exactly;
  5. select;
  6. **freeze**: save the 4 files, check sizes, reload exactly;
  7. **only then** score the test once, using Stage 4a's own `score_test_once`;
  8. write `reports/stage4b_quality_report.md`, `stage4b_quality_checks.json`, `stage4b_per_route_evaluation.csv` and `artifacts/stage4b/model_manifest.json`.
- **Why:** the same "seal the envelope before opening the results" order as Stage 4a. Reusing Stage 4a's scoring and test functions unchanged means the ten methods can't be scored by different rules.
- **Key concept:** *reuse proves comparability*. If Stage 4b had its own copy of the scoring code, a 0.1% difference could come from the copy, not the model. Calling the same function on the same rows removes that doubt.
- **Decisions:**
  - The report's "likely reasons" were written before any result. After the run, one claim was checked against the data and corrected: "a few hundred to over 20,000" became the computed fit-part route averages, 133 (route 169) to 15,267 (route 9), median 2,740.
  - Three test-period patterns were added, computed from the results and labelled "reported, not used for any choice".
  - The run command also needs `--register data\raw\source_register.csv`, to find the raw ridership the same way Stage 3 does.
- **Results:**
  - training times: MLP 47 epochs (best 27) in ~6 s; LSTM and GRU 66 (best 46) in 30–60 s; CNN 32 (best 12) in ~6 s;
  - saved files 27–54 KB, all under 20 MB;
  - all 4 reloads are exact, and the Stage 4a methods reproduce their stored predictions exactly.
- **Interview Q:** *"Why did you check your own 'likely reasons' text after the run?"* Because it was written before the numbers existed, it was a hypothesis. One sentence turned out to mix route averages with single-day peaks. Checking it against the data and correcting it is cheaper than defending a wrong number later.

## Step 42: Reproducible model files (clock time out of the payload)
- **Built:** `network_payload()` no longer stores `train_seconds`. The training time stays in the manifest and the report.
- **Why:** a rerun gave byte-identical predictions and training history, but **different model-file hashes**. The cause: each file included the training time, which changes on every run (5.5 s vs 5.4 s).
- **Key concept:** *a fingerprint should change only when the content changes*. A file that holds the clock time is like a recipe card stamped with the minute you copied it: two identical recipes look different.
- **Decisions:**
  - Every value in a saved file was audited: constants, weights, summary, preprocessor attributes, encoder and scaler state. `train_seconds` was the only run-varying value. There are no timestamps, absolute paths or random IDs. Library versions would change only after an upgrade, which correctly gives a different fingerprint.
  - **Stage 4a checked, not assumed:** `rf_demand`, `rf_service` and `ridge_demand` refitted twice in memory gave byte-identical files that equal the frozen Stage 4a sha256. Stage 4a stores times only in its JSON manifest, so it never had this problem.
- **Results:** two full runs after the fix:

  | file | run A | run B |
  |---|---|---|
  | `mlp.joblib` | `6fb9bac2eaf7ae7c` | `6fb9bac2eaf7ae7c` |
  | `lstm.joblib` | `7095bfe6879ef7d3` | `7095bfe6879ef7d3` |
  | `gru.joblib` | `63a0c0300fead4a0` | `63a0c0300fead4a0` |
  | `cnn.joblib` | `6baccfb983df06a5` | `6baccfb983df06a5` |
  | `validation_predictions.csv` | `0a245ee5e7643aa0` | `0a245ee5e7643aa0` |
  | `training_history.csv` | `3b4c28eed53c3aff` | `3b4c28eed53c3aff` |

  The predictions and history are also identical to the two runs before the fix.
- **Interview Q:** *"Your predictions were identical but the file hashes weren't. Which one do you trust?"* Both told the truth about different things: the model was reproducible, the file format wasn't. The fix keeps run metadata (time) separate from the artifact (weights and settings), so the file hash becomes a reliable check.

## Step 43: Results, integration test and mutation check
- **Validation (selection, identical 6,560 rows):**

  | method | MAE | WAPE |
  |---|---:|---:|
  | rf_demand | **345.47** | 6.40% |
  | rf_service | 354.08 | 6.56% |
  | seasonal_mean | 360.36 | 6.67% |
  | gru | 364.86 | 6.75% |
  | last_week | 375.18 | 6.95% |
  | lstm | 385.66 | 7.14% |
  | ridge_demand | 400.56 | 7.42% |
  | mlp | 416.82 | 7.72% |
  | ridge_service | 437.14 | 8.09% |
  | cnn | 559.85 | 10.36% |

- **Honest result:** every network **loses** to the Random Forest and to the seasonal-mean baseline. The best network, the GRU, is 4.5 boardings worse than the baseline on MAE. The serving method stays `rf_demand`, and the Stage 4a serving bundle is unchanged.
- **Test (reused holdout, scored once):** rf_demand 398.01, seasonal_mean 421.15, gru 461.98, mlp 467.36, lstm 484.97, cnn 557.57. Observed, not used for any choice:
  - **Unseen routes 10 and 130:** LSTM WAPE 118.5% / 103.8% vs rf_demand 26.6% / 18.9%.
  - **Weekdays are close, Saturdays are poor:** GRU 7.21% vs RF 7.00% on weekdays, but 16.57% vs 8.67% on Saturdays.
  - **Sundays/holidays:** the MLP has the lowest WAPE of all ten methods (10.73%), on one slice.
- **Likely reasons for the loss** (not proven):
  - fewer rows (10,988 vs 13,379, about 89 days per route);
  - a 115-fold range of route sizes under one shared scale;
  - the RF already gets the useful summaries (same-weekday lags, seasonal mean);
  - MSE loss vs MAE ranking;
  - untuned settings, fixed in advance on purpose.
- **Integration test** (`test_neural_integration.py`, 5 tests): the files are under 20 MB, compressed and unchanged; they hold no run-varying values; the reloaded networks reproduce all 6,560 stored validation predictions exactly; they were fitted on the fit part only; the Stage 4a serving bundle is unchanged.
- **Mutation check (your instruction: the new guard only):** two bugs were planted in `check_against_lags`, in scratch copies only. A silent guard that never raises, and an off-by-one guard that compares the wrong day, were **each caught** by `test_guard_catches_a_window_shifted_by_one_day`; the other 19 tests still passed. The scaler and previous-row bugs were already covered in Stages 3 and 4a.
- **Interview Q:** *"Your neural networks lost to a four-week average. Was the experiment a failure?"* No. It answered its question: on this data size, with fair rules, sequence networks don't beat a well-fed Random Forest or even a strong baseline. A result that's reported honestly and reproduced exactly is more useful than a tuned-up win. The test slices also point to what to try next: better handling of unseen routes, and a per-route scale.

---

# Stage 5: Route groups and ranking (spec 9.7, 9.11, 9.12; stage table 9.18)

> The spec wins where it differs from the mentor's notebook (your decision for this stage). The notebook's rules are recomputed and reported beside ours.

## Step 44: Settings fixed before any result (`analytics/config/groups.json`)
- **Built:** one config for Stage 5:
  - periods, with the clustering period separate from the ranking periods;
  - the spec 9.7.2 gates (20 / 20 / 8);
  - three named rankings (demand, rides per trip, rides per hour);
  - the clustering candidates in priority order and the feature-selection rule (≥ 90% availability, |Spearman| < 0.8);
  - the KMeans settings (k = 2–6, 10 initialisations, seeds 1–5 for stability, minimum group of 5, silhouette tolerance 0.02);
  - the overlap scope and the notebook's comparison settings.
- **Why:** each threshold must be chosen before its effect is visible. Otherwise a cutoff could be nudged until the output "looks right".
- **Key concept:** *two different periods for two different questions*. Groups describe what a route is *like*, learned once from the development period and then frozen, like a school photo taken on one day. Rankings describe how routes compare *over the period you are looking at*, like a league table that can cover any season you pick. Spec 9.7.2 keeps their counts separate.
- **Decisions:**
  - **Your catch:** the development period has only **18 Saturdays**, so with the 20-day ranking gate **no** route could ever have a Saturday ranking (0 of 123). The spec doesn't tie rankings to the development period: 9.7.2 applies ranking counts to "the displayed ranking period", 9.12 says "store the chosen period", and 9.14.4 lets replay rankings update with revealed history. So the **reference ranking period is the full matched window** (2025-11-23 to 2026-07-31: 35 Saturdays, and 92 routes reach 20 Saturdays). The development-period ranking is kept, with Saturdays shown **unranked (18 days)**.
  - The full-window ranking includes June–July, so it is a *historical-analysis* table. The replay (Stage 7) must recompute rankings from revealed history only.
  - **The gate stays at 20.** Lowering it to make Saturdays rankable would mean choosing a threshold for its output. A sensitivity table (gates 8, 12, 16, 20) shows the effect instead.
  - The day type is the *reported* W/A/U: these profiles describe the past, so the label is legitimately known (unlike in forecasting).
- **Results:** the config parses. Day counts: development W 89, A 18, U 22; full window W 175, A 35, U 41.
- **Interview Q:** *"Why not just lower the Saturday threshold to 15 so you get a Saturday ranking?"* That picks a rule because of the answer it gives. The honest options are to keep the rule and show the group as unranked with its count, or to rank over a period that actually has enough Saturdays. The spec allows both, so I did both, and I report how the rankings would change at other gate values.

## Step 45: Utilization profiles and the three named rankings (`analytics/groups/profiles.py`)
- **Built:**
  - `utilization_profiles()`: one row per route × day type (W/A/U) × period, with observed days, sums of rides, trips and hours over the same dates, mean daily rides, and the two ratios;
  - three rankings (`observed_daily_demand_rank`, `rides_per_trip_rank`, `service_productivity_metric_rank`), each with its own eligibility flag and reason;
  - `all_ranking_periods()` and `gate_sensitivity()`.
  - Tests: `analytics/tests/test_profiles.py`.
- **Why:** spec 9.12 asks for separate named rankings rather than one hidden score, and 9.7.2 says how eligibility works.
- **Key concept:** *ratio of sums, not mean of ratios* (the example from the test):
  - 10 days at 100 rides / 10 trips (10 per trip);
  - 10 days at 300 rides / 10 trips (30 per trip);
  - 5 days at 10 rides / 1 trip (10 per trip).

  The **mean of the daily ratios** is (10×10 + 10×30 + 5×10) ÷ 25 = **18**. The **ratio of sums** is 4,050 rides ÷ 205 trips = **19.76**. The mean of ratios lets a day with 1 trip count as much as a day with 10 trips. Adding first and dividing once weights each day by how much service actually ran, which is what spec 9.7.1 asks for.
- **Decisions:**
  - **Your fix:** every route in the period gets W, A and U rows. A day type with no matched days has `observed_days = 0` (a real count), missing sums (no observations, never 0), and the reason "no matched days of this day type". Spec 9.7.2 says a failed gate is *displayed* as unranked with its count, not hidden.
  - Ties share the lowest rank (two routes tied for 2nd are both 2nd; the next is 4th).
  - Incomplete durations remove only the hours ranking; the trips ranking survives.
  - **Your fix:** the reason reads "on 1 day" / "on 3 days".
- **Results:**
  - 9 unit tests pass, including the spec 9.19.1 case: 10 Saturdays pass the clustering weekend gate (8) but are **not** rankable (gate 20).
  - One test first failed because my test data put weekdays and Saturdays on the same dates. The duplicate-key guard refused it, which was correct; the test data was fixed.
  - **Dry run on real data:** full window 125 routes, ranked W 125 / A 92 / U 86. Development 123 routes, ranked W 123 / **A 0** / U 86. Every matched row is counted exactly once (rides, trips and days equal the matched table).
- **Interview Q:** *"A route never runs on Saturdays. Why give it a Saturday row at all?"* An absent row and "zero days, not ranked" mean different things to a reader. An absent row looks like a data error or a filter bug. An explicit row with 0 days and a reason states a fact about the route, and keeps "no observations" separate from "observed zero rides".

## Step 46: "No weekend service" is a fact, not a missing value (`groups.json`, `profiles.py`)
- **Built:**
  - a weekend service status per route and day type, from the descriptive schedule: `no_scheduled_service`, `insufficient_observations` or `available`;
  - a `scheduled_service_days` column in the ranking table;
  - a clearer ranking reason, "no scheduled service of this day type";
  - one new test.
- **Why (your catch):** in the development period, **30** of 123 routes run no Saturday buses and **36** run no Sunday/holiday buses. Under the first rules, both weekend ratios would have been dropped (74.8% and 69.9% available, below the 90% bar), or else filled with the median, which would make a weekday-only route look like a typical weekend route.
- **Key concept:** *evidence of absence vs absence of evidence*. "We have no record for Saturday" (missing) is different from "the timetable shows zero buses every Saturday" (known). The spec's "missing observations never become measured zeros" (9.7.2) protects the first case. In the second case the zero comes from the schedule, so nothing is being made up. Like a shop that is closed on Sundays: its Sunday sales are zero because it never opens, not because the till roll is lost.
- **Decisions:**
  - No scheduled service → the weekend ratio is a **structural zero** for clustering.
  - Service scheduled but fewer than 8 matched days → **unavailable**, filled with the median of routes that *have* that service, and listed in the report. Only **route 169** (Saturday 6 of 18 matched; Sunday/holiday 0 of 3, which are single-trip holidays).
  - The 90% availability rule now counts only truly unavailable values, so both ratios are 122 of 123 (99.2%) and kept.
  - **No separate has-service indicator (your decision):** a ratio of 0 already says "no service". An extra 0/1 column would count the same fact twice in KMeans distances.
  - The ranking table keeps those rows unranked. Only the reason became more exact, so a planner can tell "doesn't run Saturdays" (66 rows) from "ran, but no ridership record" (1 row, route 169 U, development period).
- **Results:** 10 ranking tests pass. The other five clustering candidates are available for 123 of 123 routes.
- **Interview Q:** *"Isn't putting 0 in for routes with no Saturday service exactly the 'missing becomes zero' mistake?"* No. The mistake is inventing a measurement you don't have. Here the schedule is a measurement: it shows zero trips on every Saturday, so zero Saturday rides is what happened. The one route where Saturday service existed but the ridership data is thin (169) is treated as genuinely missing, and it's flagged.

## Step 47: Clustering profiles and feature selection (`profiles.py`: `route_profiles`, `select_features`)
- **Built:**
  - one clustering profile per route over the development period (spec 9.11.2): coverage counts, weekend statuses, and the 7 candidate features;
  - the base gate (fewer than 20 matched weekdays → ungrouped, with a reason);
  - `select_features()`, which applies the fixed rules (≥ 90% availability, then |Spearman| < 0.8 in priority order) and records why each candidate was kept or dropped.
  - 7 tests in `analytics/tests/test_clustering.py`.
- **Why:** the spec lists *candidates* and asks for "a compact, interpretable set" chosen by inspecting correlation. Two features that say almost the same thing would count that thing twice in KMeans distances.
- **Key concept:** *correlated features are double votes*. Weekday rides and weekday trips correlate at 0.906: busy routes get more buses. Keeping both would let route size decide the groups twice over. Spearman is used because it measures "do they rise and fall together" without assuming a straight line.
- **Decisions:**
  - **Selected:** weekday rides, weekday variability (CV), Sunday/holiday ratio, rides per scheduled hour, trip duration.
  - **Dropped:** weekday trips (|ρ| 0.906 with rides) and the Saturday ratio (|ρ| 0.812 with CV).
  - **A knife-edge result, kept and disclosed:** the Saturday and Sunday ratios correlate at 0.951. Saturday was dropped at 0.812 against CV; Sunday stayed at 0.798, just under the bar. Weekend shape is still represented, through Sunday. The rule was fixed before seeing the data, so it isn't changed afterwards.
  - Part of the CV↔weekend correlation likely comes from the 30–36 structural zeros (weekday-only routes tend to be peak-heavy and more variable).
- **Results:** 123 of 123 routes pass the base gate. Saturday: 92 available / 30 no service / 1 insufficient (169). Sunday/holiday: 86 / 36 / 1 (169). 17 tests pass.
- **Interview Q:** *"Your Saturday feature was dropped by 0.012 over a threshold. Isn't that arbitrary?"* Any threshold is arbitrary at its edge. What matters is that it was set before the data was seen and is applied the same way everywhere. Here the dropped feature correlates 0.951 with one that was kept, so the clustering still sees weekend shape. Changing the rule after seeing which way it fell would be the real problem.

## Step 48: KMeans with the service-aware imputer (`analytics/groups/clustering.py`)
- **Built:**
  - `ServiceAwareMedianImputer`: a weekend ratio's median comes **only from routes that have that service** (status `available`). Structural zeros are never filled and never enter the median.
  - A pipeline that is saved as one object: imputer → StandardScaler → KMeans (`n_init` 10, seed 42).
  - `evaluate_k` (k = 2–6: sizes, silhouette, stability across seeds 1–5, agreement between the two half-periods), `choose_k`, `membership`, `group_summary`, `centroids_original_units`, `assign_group`.
  - 6 new tests.
- **Why:** a plain median imputer would mix the 36 "no Sunday service" zeros into the median used to fill route 169's missing value. And KMeans must be repeatable to the last bit for an auditable artifact.
- **Key concept:** *silhouette*. For each route it compares "how close am I to my own group" with "how close am I to the nearest other group", giving a score from −1 to 1. Near 1 means tight, well-separated groups; near 0 means groups that blur into each other. **0.38 means moderate separation**: real structure, but with routes near the boundaries. Like sorting students into "mostly sciences" and "mostly arts" when many take a bit of both.
- **Decisions:**
  - **One thread** (`threadpool_limits(limits=1)`) for every fit and predict. KMeans's parallel loop adds partial sums in thread-finishing order, the same kind of problem as `n_jobs=2` in Stage 4a.
  - **k = 2 was chosen by the fixed rule:** the best silhouette is 0.383 at k = 3, and k = 2 (0.381) is within the 0.02 tolerance, so the smallest such k wins.
  - **It is a near tie:** k = 2 vs k = 3 is **0.381 vs 0.383**. Two things favour k = 2: identical groups for all 5 seeds (adjusted Rand 1.000), and 0.873 agreement between the two half-periods, against k = 3's 0.755.
  - **Three bugs fixed before any result was frozen:**
    - an all-missing reason column was stored as numbers, so writing a text reason crashed (`assign_group` would have failed on the real data, where all 123 routes pass the base gate);
    - the half-period check matched routes by row number instead of route name (it would have mis-paired routes if the halves differed; the input is now keyed by route);
    - two test-helper mistakes (writing past a table's end silently adds a row; a column had the wrong type).
- **Results:**
  - The imputer's Sunday/holiday median is 0.5111, equal to the median of the 86 routes with Sunday service; a naive median including zeros would be 0.4296. Only route 169 is filled.
  - **k table (123 routes):**

    | k | sizes | silhouette | seed ARI mean | halves ARI |
    |---:|---|---:|---:|---:|
    | **2** | 67, 56 | 0.381 | 1.000 | 0.873 |
    | 3 | 62, 20, 41 | 0.383 | 0.986 | 0.755 |
    | 4 | 17, 50, 21, 35 | 0.327 | 0.892 | 0.686 |
    | 5 | 32, 19, 12, 12, 48 | 0.337 | 0.978 | 0.875 |
    | 6 | 38, 18, 12, 12, 14, 29 | 0.298 | 0.913 | 0.780 |

  - 23 Stage 5 tests pass. Nothing is frozen yet; names come after you inspect the summaries.
- **Interview Q:** *"k = 3 had the higher silhouette. Why did you go with 2?"* The rule, fixed in advance, takes the simplest grouping within 0.02 of the best, because a 0.002 difference in silhouette is noise, not evidence of a third group. The stability checks agree: k = 2 gives the same groups for every seed and is more consistent across the two halves of the period. I report k = 3's numbers too, so a reader can see how close it was.

## Step 49: Route stop coverage and overlap (`analytics/groups/overlap.py`)
- **Built:**
  - `served_stops()`: per GTFS archive (geometry version), the distinct stop_ids of each **bus** route's trips whose service is active on at least one of the archive's applied dates;
  - `coverage()`: served stops, exclusive stops and the exclusive share per route;
  - `overlap()`: per route pair sharing at least one stop, the shared stops, Jaccard, smaller-route overlap and a review rank with ties preserved;
  - `verify()`: identities that stop the build if broken.
  - 7 tests in `analytics/tests/test_overlap.py`.
- **Why:** spec 9.12's "route overlap review" names corridors worth examining, and 9.8 defines `route_stop_coverage.csv` and `route_stop_overlap.csv`.
- **Key concept:** *two ways to measure overlap*. Think of two playlists.
  - **Jaccard** = songs on both ÷ all distinct songs on either.
  - **Smaller-route overlap** = songs on both ÷ the shorter playlist's length.

  X49 (the 49 express) has 71 stops, and all 71 are also 49 stops. Its Jaccard is only 0.433, because 49 has 164 stops, but its smaller-route overlap is **1.000**: the express sits entirely inside the local route. Each measure catches what the other misses.
- **Decisions:**
  - **Your fix:** every count, exclusivity test and identity is keyed by **(geometry_version, route)** or **(geometry_version, stop_id)**. With stop-only keys, a table holding two versions would silently mix timetables.
  - The new test passes two versions together and checks they give exactly the same tables as each version run separately. My first expectation in that test was wrong (stop `a` really is exclusive in v2), and that case is now part of it: `a` is shared in v1 but exclusive in v2.
  - Inactive services and rail trips are excluded. IDs stay strings (`007` is not `7`).
  - **Interpretation, on every row:** corridor review only. Shared stop IDs are not merge/split evidence (no direction, walking access, transfers or journeys).
- **Results (dry run, all 8 archives, 11 s):**
  - every archive's applied dates equal `sources.json`;
  - every identity holds per version **and for all 8 combined**;
  - 123 routes per archive (125 from 2026-05-30, when routes 10 and 130 appear); about 10,700 stops; 692–774 sharing pairs; median exclusive share 0.65–0.66;
  - the January and February archives give identical numbers, as Stage 2 found;
  - top pairs in the default version (2026-03-26): 120 & 121 (Jaccard 0.810), 108 & 8A (0.500), 49 & X49 (0.433; smaller-route overlap 1.000).
  - 30 Stage 5 unit tests pass.
- **Interview Q:** *"Routes 120 and 121 share 17 of their stops. Should CTA merge them?"* This table can't say. Shared stop IDs don't show direction, time of day, where riders actually go, or whether the two routes serve different trips through the same street. It flags a corridor worth a planner's look; it is not a recommendation.

## Step 50: The mentor notebook's rules, recomputed for comparison (`analytics/groups/notebook_compare.py`)
- **Built:** the notebook's steps 36–44, re-implemented as stated, on its own population (forecast-time feature rows with rides, training split, from 2025-11-24):
  - `notebook_profiles` (≥ 20 weekdays **and** ≥ 8 Saturdays **and** ≥ 8 Sundays/holidays; its fixed 5 features);
  - `notebook_groups` (its k rule);
  - `notebook_ranking` (rides per scheduled hour, sequential ranks);
  - `compare()`, which sets those results beside ours.
  - 3 tests in `analytics/tests/test_notebook_compare.py`.
- **Why:** the spec wins for Stage 5 (your decision), so every place we differ from the mentor's reference must be visible and explained, not silent.
- **Key concept:** *a comparison that can't change the answer*. The notebook's rules live in their own module and only *read* our profiles, labels and ranking. A test hands `compare()` our tables and checks they come back byte-for-byte identical. On the real data, row hashes before and after also match. Like a second examiner marking a copy of the exam, never the original.
- **Results (dry run on real data):**
  - **Profiles:** the notebook rule gives **86**, matching its stated **86**. Ours keeps **123**. The 37 extra routes are all the notebook's weekend exclusion: **30** with no scheduled Saturday or Sunday/holiday service, **6** with Saturday service but none on Sundays/holidays, and **1** (route 169) where service ran but there are too few observations. The whole gap is the Step 46 "no weekend service is a fact" decision.
  - **Population:** the notebook has 14,415 rows from 2025-11-24, ours 14,501 from 2025-11-23. The difference is exactly the 86 rows of 2025-11-23 (no archive saved before it, as in Stage 4a).
  - **Features:** three of five shared (weekday demand, CV, Sunday/holiday ratio). The notebook also has the Saturday ratio and weekday trips; our rule dropped those as correlated (|ρ| 0.812 and 0.906) and kept rides per scheduled hour and trip duration.
  - **Groups:** both choose **k = 2**, with **adjusted Rand 0.576** on the 86 routes both group (moderate agreement). The notebook's own best silhouette (0.428 at k = 3) fails its size gate with a 3-route group.
  - **Ranking:** **Spearman 1.0** on weekdays (123 routes) and Sundays/holidays (86). The orderings are identical, and there are no tied values here, so the tie rules give the same ranks. Saturdays: **0 ranked in both** (18 < 20), as predicted.
- **Interview Q:** *"Your grouping agrees with your mentor's at only 0.58. Which one is right?"* Neither is "right": clustering has no answer key. Both find two groups. They disagree on some routes because they use different features and different route sets. The notebook drops 37 weekday-only and limited-weekend routes; we keep them. I can explain every difference by a named rule, and the spec tells me which rule to follow.

## Step 51: Group names, orchestrator, report and the first full run (`group_names.json`, `build_stage5.py`, `report5.py`)
- **Built:**
  - **`analytics/config/group_names.json`:** names you chose after inspecting the summaries.
    - group 0 (67 routes): **"Higher-demand, seven-day routes"**;
    - group 1 (56 routes): **"Lower-demand routes, often with limited or no weekend service"**.

    It also holds the exact route lists you inspected and four caveats.
  - **`build_stage5.py`**, one command in a fixed order: verify inputs → rankings → clustering profiles → k table → fit → **freeze** → names → memberships → overlap (8 archives) → notebook comparison → write.
  - **`report5.py`:** `reports/stage5_quality_report.md`, `stage5_quality_checks.json`, `stage5_group_summary.csv` and `stage5_rankings.csv`.
- **Why:** spec 9.18's completion evidence for Stage 5 is "group explanations and an eligible ranking table". The report holds both, with every number computed by the build rather than typed in.
- **Key concept:** *a name is bolted to a membership, not to a number*. KMeans numbers groups arbitrarily, so "group 0" means nothing by itself. The names file stores the route lists you inspected, and the build attaches a name only if the frozen groups contain **exactly** those routes; otherwise it stops. Like a name tag that only fits the person it was made for.
- **Decisions:**
  - Inputs are verified as in Stage 2: the Stage 2 tables against the Stage 3 manifest, and each GTFS ZIP's sha256 against the register, after which the extracted files are read. **Answer to your question:** Stage 2 does exactly this (`build_stage2.py` lines 95–99 hash the ZIP; line 124 opens `extracted/`). The extracted `.txt` files are not re-hashed in either stage, which is listed in the report's limitations. Stage 2 is unchanged.
  - The report adds a **computed** knife-edge sentence (Saturday dropped at 0.812, Sunday kept at 0.798, the two correlate 0.951) and states the k = 2 / k = 3 near tie, both in the summary and in section 4.
  - After the connection dropped, a fresh fit confirmed that `group_names.json` matches the inspected 67 + 56 routes exactly.
  - **Three report bugs were fixed before the report was accepted** (none affected any result):
    - numeric column headers in the gate-sensitivity pivot;
    - list cells (group sizes) breaking the table helper;
    - gate counts printed as decimals, and weekday rides shown in unlabelled log1p units (8.058 ≈ 3,158 rides/day).
- **Results:**
  - **Groups:** 123 routes grouped (67 + 56); 5 of 128 in the ridership window ungrouped, each with a reason (10, 130: no development-period days; 1001, 128, 19: ridership-only identifiers).
  - **Rankings:** reference period ranks W 125 / A 92 / U 86; the development period ranks W 123 / **A 0** / U 86; identities all hold.
  - **Artifact:** `route_groups.joblib` is 1,237 bytes; the reload is exact.
  - **Overlap:** the default version's top pairs include express routes nested in their local routes (49/X49, 4/X4, 9/X9).
  - **Integration test** (`test_stage5_integration.py`, 7 tests) passes. It covers artifact size and sha, data-product hashes, exact reload, names equal to memberships, one membership row per route, ranking identities, and an unchanged Stage 4a bundle.
- **Interview Q:** *"Why not just store 'group 0 = Higher-demand routes' in the code?"* Because group numbers aren't stable facts. A new library version or data fix could swap them, and the label would then describe the wrong routes without any error. Tying the name to the exact membership turns that silent mistake into a stopped build.

## Step 52: Reproducibility and the mutation check
- **Built:** a second full run, compared hash by hash with the first, and three planted bugs in scratch copies of `analytics/` (never in the project files).
- **Why:** "the code looks right" isn't evidence. Identical reruns show the outputs depend only on the inputs and settings, and a test that still passes with its rule broken isn't protecting that rule.
- **Key concept:** *a test is only as good as the bug it catches*. Bug 2 below shows why that matters: a whole set of tests can pass while missing a real mistake.
- **Results:**
  - **Reproducibility:** `route_groups.joblib`, all 5 data CSVs and both committed summary CSVs are **byte-identical** across the two runs (artifact `33d2d42a9b77cbe4`).
  - **Mutation check (your three bugs):**

    | planted bug | caught by | still passing |
    |---|---|---|
    | 1. the imputer median includes structural zeros | `test_structural_zeros_do_not_affect_the_filled_median`, `test_structural_zeros_stay_zero_and_only_missing_values_are_filled` | 31 |
    | 2. overlap counts ignore `geometry_version` | `test_two_versions_together_give_the_same_results_as_each_version_separately` | 32 |
    | 3. zero-day day-type rows dropped from the ranking | `test_weekday_only_route_gets_saturday_and_sunday_rows_with_zero_days_and_missing_sums`, `test_zero_day_reason_separates_no_scheduled_service_from_no_ridership_record` | 31 |

  - **Bug 2 was caught only by your two-version test.** Every single-version overlap test still passed, because with one version, keying by stop alone happens to give the right answer. Without the test you asked for in Step 49, this bug would have gone unnoticed, and a future run combining versions would have mixed timetables.
- **Interview Q:** *"All your tests passed. How do you know they're good tests?"* I broke the code on purpose in three specific ways and checked that the intended test failed each time. One bug slipped past every test except one that was written specifically for it, which shows that "all tests pass" says nothing about cases no test covers.

# Stage 6: Application foundation (spec 9.17, 9.16, 9.19.2; stage table 9.18)

> Split into 6a (database and import), 6b (FastAPI endpoints) and 6c (React screens). Historical-analysis mode only: forecasts and replay are Stage 7, scenarios Stage 8. History, rankings and compare all take a backend-enforced `cutoff`, so Stage 7 can reuse them unchanged.

## Step 53: PostgreSQL driver (`requirements.txt`)
- **Built:** `psycopg==3.3.9` with its precompiled part `psycopg-binary==3.3.9`. Its own dependencies (`typing_extensions`, `tzdata`) were already pinned. `pip check` is clean.
- **Why:** Python needs a driver to talk to PostgreSQL (spec 9.17.1). It is added now, the first time a stage needs a database, following the "add dependencies when their stage begins" rule.
- **Key concept:** *a driver is a translator*. PostgreSQL speaks its own network protocol and Python doesn't. psycopg turns `cur.execute("SELECT ...")` into that protocol and turns the replies back into Python values, like an interpreter at a meeting.
- **Decisions:**
  - **Plain SQL, no ORM (your choice).** An ORM such as SQLAlchemy writes the SQL for you. Here every query stays visible, which matters when a query has to enforce a rule such as "no rows after the cutoff".
  - `[binary]` ships a prebuilt library, so no C compiler or local PostgreSQL headers are needed on Windows.
- **Results:** installed and importable; no conflicts.
- **Interview Q:** *"Why not use an ORM?"* For a small, read-heavy analysis API, plain SQL keeps every filter explicit and easy to review. The important rules, the replay cutoff above all, live in one visible `WHERE` clause rather than inside generated queries. An ORM pays off with many entities and lots of write logic, which this prototype doesn't have.

## Step 54: Database role and the two databases (you ran the setup; `backend/.env.example`)
- **Built:** a login role `routeranker` (not a superuser; cannot create databases or roles) that owns two databases: `routeranker` (the app) and `routeranker_test` (tests only). `PUBLIC` connect rights were revoked on both. The connection URLs live in `backend/.env` (gitignored, confirmed with `git check-ignore`); `backend/.env.example` is the committed template with `CHANGE_ME` placeholders.
- **Why:** the app should run with only the rights it needs (spec 9.17.1 puts persistent data in PostgreSQL). A separate test database means tests can create and drop tables freely without ever touching the real import.
- **Key concept:** *least privilege*. The `postgres` superuser is a master key that opens every database on the server. `routeranker` is a key cut for two doors only. If the app's password ever leaked, the damage would stop at those two databases.
- **Decisions:**
  - **Your rule:** `routeranker` has its own new password, never the superuser's. You typed it into `\password` yourself, so it never appeared in a command I ran, in the chat or in a commit.
  - The connection check reads `backend/.env` but prints only the user, database, server version, superuser flag, owner and public access. If a connection fails, it prints the error type, never the message, because a psycopg error message can contain the URL.
- **Results:** both URLs connect as `routeranker` to PostgreSQL 17.10; `superuser=False`; each database is owned by `routeranker`; `PUBLIC` cannot connect. (My first check failed on a quoting mistake in the query, not in the connection; it was rerun from a script file.)
- **Interview Q:** *"Why not just connect as `postgres` during development?"* Habits made in development become production settings. With a limited role from day one, a bug or a leaked `.env` can't drop other databases or create users, and the test database keeps experiments away from the real data.

## Step 55: Database schema (`backend/db/schema.sql`)
- **Built:** 17 tables for the Stage 6 entities of spec 9.17.2:
  - versions and sources: `dataset_versions`, `source_files`, `gtfs_snapshots`;
  - routes and geometry: `routes`, `route_shapes`;
  - observations and schedule: `daily_ridership`, `daily_schedule`, `matched_utilization`, `ridership_without_schedule`, `schedule_without_ridership`;
  - Stage 5: `group_versions`, `utilization_profiles`, `route_profiles`, `group_memberships`, `route_stop_coverage`, `route_stop_overlap`;
  - `model_versions` (metadata only, for Stage 7).

  Every key includes its version (`data_version`, or `group_version` for Stage 5 products).
- **Why:** the database must hold several versions side by side and refuse rows that break the rules earlier stages proved. Then the API can trust what it reads.
- **Key concept:** *the database as a second checker*. Foreign keys and CHECKs turn earlier findings into rules the database enforces on every insert. A matched row must exist in both ridership and schedule (the Stage 2 identity). "Eligible ⇔ ranked ⇔ no reason" holds for each named ranking. Like a bouncer with a list: whatever the importer's code does, a row that breaks a rule doesn't get in.
- **Decisions:**
  - `service_date` instead of `date`: it is the GTFS service date (a 25:10 trip stays on its day), and `date` is also an SQL type name.
  - **No foreign key from the daily tables to `routes`:** ridership-only identifiers (1001, 128, 19, 5) are in no archive and must still be importable.
  - Stop IDs are `text[]` arrays, so a query can ask which routes serve a stop.
  - Not stored: the Stage 3 feature tables (Stage 7 needs them), and the always-empty `rides` column of `schedule_without_ridership`.
  - **Your three additions:**
    1. `daily_schedule`: `duration_complete = (scheduled_service_hours IS NOT NULL)`, a two-way rule, so a partial hours sum can never be stored. It replaces my one-way draft rule.
    2. `matched_utilization`: `(rides_per_scheduled_hour IS NULL) = (scheduled_service_hours IS NULL)`.
    3. An empty stop-ID cell becomes `{}`, never `{''}`. The importer will do this, and I also added a CHECK that no array holds an empty string, so the database enforces it too.
- **Results:**
  - **Real-data check before writing:** additions 1 and 2 hold for **all 28,398** schedule rows and **all 28,374** matched rows. *Caveat:* every duration in these feeds is complete, so no real row has NULL hours. The NULL side of both rules is exercised only by made-up rows.
  - Addition 3 applies to **68** real cells (empty `exclusive_stop_ids`).
  - **Probe on `routeranker_test`:** the schema applies (17 tables). Bad rows are **rejected**: complete-but-NULL hours, incomplete-but-present hours, hours without a per-hour ratio, a per-hour ratio without hours, and `{''}` stop IDs. The matching valid rows are **accepted**. The test database was emptied afterwards.
- **Interview Q:** *"Your importer already checks the data. Why repeat the rules as CHECK constraints?"* Code has bugs and gets bypassed: a later script, a manual fix, a new importer version. A constraint lives with the data and applies to every writer, every time. One of these rules also covers a case the real data never contains (incomplete durations), so the database guards against it before it ever happens.

## Step 56: Route geometry, "most common path per direction" (`analytics/geometry/`)
> **Corrected in Step 57:** "most common" counted *trips*. It now counts *trip-days*. The results below are from the first build, which has been deleted and rebuilt.
- **Built:**
  - `route_shapes.py`: `active_bus_trips`, `choose_shapes`, `shape_lines`, `version_shapes`, `verify`.
  - `build_geometry.py`: writes `data/processed/<ver>/geometry/route_shapes.csv` and `geometry_manifest.json`.
  - 8 tests in `analytics/tests/test_route_shapes.py`.
  - `route_shapes` in the schema gained `direction_label`, `tied_top_shapes`, `point_count` and a CHECK that the GeoJSON point count equals `point_count` (your approval).
- **Why:** the map screens need a line per route, and spec 9.19.2 says every map identifies its geometry version.
- **Key concept:** *a representative, not the whole truth*. A route can run several paths (short turns, garage trips, detours). We draw the one used by the most trips active on the archive's applied dates, and say so on the map: **"Most common path per direction"**. Like a school photo with one student per class standing in for everyone.
- **Decisions (your four confirmations):**
  1. **Fixed tie-breaker:** most trips, then the lowest `shape_id` as text. The number of tied shapes is stored on every row.
  2. **`[lon, lat]`** (GeoJSON). Nobody flips by hand: react-leaflet's `<GeoJSON>` hands the data to Leaflet, which converts it itself. A Chicago bounding box rejects swapped coordinates; a test proves it.
  3. **Only bus trips active on the applied dates**, from the same pieces as the overlap step (`bus_crosswalk`, `active_service_dates`). The build also stops unless the routes per version equal Stage 5's `route_stop_coverage.csv`.
  4. **Label** `PATH_LABEL = "Most common path per direction"`, defined once, written into the manifest and passed on to the map.
  - `shapes.txt` is read with Stage 2's `_csv_view`, so it gets the same parsing as every other GTFS file. No Stage 2 code changed.
  - `geometry/` is a new folder beside the existing products. A second build is **refused** (checked: exit code 1).
- **Results:**
  - **Tests:** 8 new pass; the full suite passes (135).
  - **Build (all 8 archives):** every identity holds; 123 routes / 246 lines per version, and 125 / 250 from 2026-05-30 (routes 10 and 130); about 266k–276k points per version; `route_shapes.csv` is 1,976 rows, 45 MB (gitignored).
  - **Ties:** 1 per version normally, but **60, 68 and 191** in the archives whose applied dates span two timetable editions (shape prefixes 676→677, 677→678, 678→679). The same trips exist under both editions' shape IDs with equal counts.
  - **Checked by real geometry, not by `shape_dist_traveled`:** that field changed between editions without the path changing (route 171: "54% longer" by the field, 0 m apart in reality). Of **324** tied route-directions, **305 are the same path (≤ 25 m apart)** and **19 are different paths**. Notable cases:
    - **Route 48:** about 0.65 mi and 800 m apart. The 677 edition (January–March) runs a shorter path.
    - **Route 94:** 377 m (May).
    - **Routes 157 and 192:** about 250 m (December).
    - **Route 125, northbound:** two variants with 13 trips each in every version, 112 m apart. A permanent tie *inside* one edition.
  - Provenance: this run recorded `git_commit 908dc63+uncommitted`, because the code isn't committed yet.
- **Interview Q:** *"Two shapes have the same trip count. Isn't picking the lower ID arbitrary?"* Yes, and openly so. With equal counts, "most common" really is undecided, so any rule is a choice. Choosing by text order hides no judgement about which path is "better". The tie count is stored, and every tie was checked against the real geometry: 305 of 324 are the same path under two IDs, and the 19 genuine differences are listed by route.

## Step 57: Correction, "most common path" means used most in the period (trip-days, not trips)
- **Built:**
  - `active_bus_trips` now returns, per trip, `active_days`: how many of the archive's applied dates its service runs on.
  - `choose_shapes` ranks shapes by **trip-days** (the sum of `active_days` over the shape's trips). Exact ties still go to the lowest `shape_id` as text.
  - New columns `trip_days_using_shape` and `active_trip_days`, in the CSV and the schema. Trips are still stored, for reference.
  - `tie_label()` and `TIE_LABEL = "tied with {n} other path(s) this version"` (in the manifest too), which the map will show when `tied_top_shapes > 1`. The alternative shapes are not stored (your decision).
  - 2 new tests.
- **Why:** this is a **correction of what "most common" means, not a tweak to the result** (your ruling). A geometry version covers a period: its applied dates. The path "most common" in that period is the one buses actually drove most often there. Counting trips asks "how many timetable entries use this path", which is a different question. Each trip has to be weighted by the number of days it ran.
- **Key concept:** *count the thing you mean*. Counting trips is like ranking shops by how many items are on their menu instead of how many meals they served. A weekend timetable with its own trip IDs looks "big" while running on only a few days.
- **Example, route 48 in the December archive (applied 2025-12-19 → 2026-01-07):** the old and new editions' weekday shapes have the same trips (27 southbound, 26 northbound), so the trip-count rule tied and the tie-breaker took the **old** edition's path. By trip-days the old edition ran **1 day** (Fri 2025-12-19) and the new one **11** (the weekdays from Dec 22 to Jan 7): 27 vs 297 trip-days southbound, 26 vs 286 northbound. The new edition's path is chosen, about 800 m from the old one. *(Checked in the data: your figure of 2 vs 18 days was the right idea, but the real counts are 1 vs 11, because the window's weekends and holidays use other shapes.)*
- **Decisions:**
  - The lowest-`shape_id` tie-breaker stays, for exact trip-day ties only.
  - **New test:** two editions with 2 trips each; the old one (lower `shape_id`) runs Monday, the new one Tuesday–Friday. Trip-days 2 vs 8 picks the new path. **Mutation check:** with the old trip-count rule put back in a scratch copy of `analytics/`, this test fails and the other 9 still pass, so the test really guards the rule.
  - The old `geometry/` folder (gitignored, two files written by Step 56) was checked, then deleted and rebuilt with your approval. The new output has 1,976 rows, 13 columns, sha `90e93481…`.
- **Results:**
  - **Tests:** 10 geometry tests pass; the full suite passes (137). The schema with the new columns applies on `routeranker_test`.
  - **Ties, before → after:** 1 / 60 / 1 / 1 / 68 / 1 / 191 / 1 → **1 in every version**. The edition-overlap ties are gone.
  - **The one remaining tie is genuinely a different path:** **route 125 northbound**, two variants (shapes …2863 and …6369), about 3.09 vs 3.00 mi and 112 m apart, with equal trip-days in all 8 versions (234 to 416). It will carry the label "tied with 1 other path(s) this version".
  - **The correction changed more than ties:** compared with the trip-count rule, 53 lines now show a different path and 338 show the same path under a new ID. The non-tied changes (routes 126, 28, 53A, 81W, 78) come from **weekend timetables**. Weekend trips have their own trip IDs, so they outnumbered weekday trips while running on far fewer days. Route 81W (Nov archive): weekend path 63 trips, 245 trip-days; weekday path 44 trips, 792 trip-days. The old rule drew the weekend path.
  - Provenance still reads `908dc63+uncommitted`. A clean rebuild follows the 6a commit, as in earlier stages.
- **Interview Q:** *"Why does it matter whether you count trips or trip-days? It's just a line on a map."* Because the line is labelled "most common path", and the label must be true. Counting trips drew the weekend path for 81W, which runs 3–5 days in the period, instead of the weekday path, which runs 18. A planner trusting the map would study the wrong street. Fixing the definition removed 323 of the 324 ties and replaced 53 lines whose drawn path was wrong.

## Step 58: The importer and its tests (`backend/importer/import_data.py`, `backend/tests/`)
- **Built:**
  - `collect()` verifies **22 inputs** (sha256 and row counts against their own manifests) and builds every table's rows in memory **without opening a database connection**.
  - `write()` loads all 17 tables with `COPY` in **one transaction**, refuses a `data_version` that already exists, re-checks **9 identities in SQL** after loading, and stores the import report in `dataset_versions`.
  - `create_schema()` works only on an empty database.
  - `write_markdown()` writes `reports/stage6_import_report.md`.
  - 14 tests in `backend/tests/`; `pytest.ini` now also finds `backend/tests`.
- **Why:** spec 9.19.2 starts with "the reviewer can import data". The database is only trustworthy if every row in it is provably the row the earlier stages wrote.
- **Key concept:** *all or nothing*. A transaction is like a bank transfer: the money leaves one account and arrives in the other, or neither happens. Here either all 17 tables and the report are saved together, or the database stays exactly as it was. Two tests prove it: a bad value in the **last** table, and a wrong ride count caught only by an identity check, each leave **0 rows in every table**.
- **Decisions:**
  - **Exact CSV text goes to the database.** An empty cell becomes NULL, and PostgreSQL parses each value once. A probe confirmed `0.01470588235` round-trips exactly and `12.5` is refused for an integer column.
  - **Your fix:** `route_group_membership.csv` has `group = "ungrouped"` for 5 routes, which COPY would have rejected for the smallint `group_id`. `"ungrouped"` now becomes NULL, the reason stays in its own column, and any other non-numeric value (`x`, `1.0`, `-1`, `" 1"`, `Ungrouped`) is refused.
  - Ridership is parsed by Stage 2's own `load_ridership`, then cut at the data version's `ridership_cutoff`; routes come from Stage 2's `bus_crosswalk`.
  - Error messages never print the database URL.
  - **Your rule:** nothing is imported into the real `routeranker` database until the 6a code is committed, so `dataset_versions.import_git_commit` records a real commit.
- **Results:**
  - `collect()` on real data: daily_ridership **1,120,604** kept (2001-01-01 → 2026-07-31, 188 identifiers, 36 recorded zeros); **3,566** excluded (2026-08-01 → 08-31); memberships 123 grouped (0/1) + 5 ungrouped (10, 1001, 128, 130, 19) with NULL `group_id`; every row count equals its manifest.
  - **Tests: 151 pass** (137 earlier + 14 new) in 6 min 4 s. Both databases are empty afterwards.
  - **Where the time goes** (profiled on the test database): one load takes about 117 s, of which **COPY of daily_ridership is 85 s** and the profile identity query 12 s. Everything else takes seconds. Not optimised yet; correctness first.
- **Interview Q:** *"Your importer verifies hashes, row counts, CHECK constraints and SQL identities. Isn't that overkill?"* Each layer catches a different mistake. Hashes catch a changed file. Row counts catch a truncated read. CHECKs catch a single bad value. Identities catch values that are each valid but inconsistent with each other: the +1-ride test passes every CHECK and is caught only by the identity. Without that layer, the error would have been imported silently.
