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

## Step 59: Provenance rebuild and the real import (`reports/stage6_import_report.md`)
- **Built:**
  1. The 6a code committed as `df142f6`.
  2. The gitignored `geometry/` folder deleted and rebuilt from the committed code.
  3. The data version imported into the real `routeranker` database with `--create-schema`.
  4. The import report committed.
- **Why:** provenance must name real code. A build or import marked `+uncommitted` can't be traced back to exact source, so both had to run after the commit (your rule).
- **Key concept:** *rebuild as a reproducibility test*. The geometry was rebuilt only so that its manifest names a real commit, but the rebuild also tests determinism: same inputs and code, so the output must match byte for byte. Like re-weighing a parcel on a second scale, which proves the first reading wasn't luck.
- **Results:**
  - **Byte-identical geometry:** `route_shapes.csv` sha256 `90e93481…610df`, 47,295,822 bytes, before and after. Only `created_at` and `git_commit` changed in the manifest (`908dc63+uncommitted` → `df142f6`).
  - **Real import:** `import_git_commit = df142f6`. All 17 tables equal their manifests. **9 of 9 identities hold.** daily_ridership 1,120,604 rows (2001-01-01 → 2026-07-31); 5 ungrouped routes with NULL `group_id`; group IDs only 0 and 1. The tree was clean when the import ran.
  - **Unexplained:** the real import took **1,091 s**, against 117 s for the same code and data on `routeranker_test` (same server, same default settings: `fsync` on, `shared_buffers` 128 MB). The result is correct, but the cause is not yet known. Something else using the machine is one possibility, not a finding. To check before 6b, if it matters.
  - The PowerShell display showed `â€¦` in the report; the file itself is valid UTF-8 with real `…` (checked byte by byte).
- **Interview Q:** *"Why rebuild a file you already had, just to change a commit hash?"* Because a hash in a manifest is a claim: "this code made this file". Before the commit that claim pointed at code that only existed on my disk. After the rebuild it points at a commit anyone can check out, and the identical bytes show the rebuild changed nothing but the claim.

# Stage 6b: FastAPI endpoints (spec 9.17.3, 9.13.3, 9.12)

## Step 60: API dependencies (`requirements.txt`)
- **Built:** `fastapi==0.165.0`, `uvicorn==0.54.0` and `httpx==0.28.1`, plus 13 packages they pulled in, all pinned. `pip check` is clean, and `requirements.txt` now matches the environment exactly: **45 pinned = 45 installed**, nothing missing or extra.
- **Why:**
  - FastAPI is the backend in the fixed stack (spec 9.17.1);
  - uvicorn is the server that runs it;
  - httpx is what FastAPI's `TestClient` uses to call endpoints in tests without starting a server.
- **Key concept:** *a framework vs a server*. FastAPI is the kitchen: it knows the recipes, i.e. which URL calls which function and how inputs are validated. uvicorn is the waiter: it takes requests from the network to the kitchen and brings the answers back. You need both, and either can be swapped without changing the other.
- **Decisions:**
  - **A telemetry package came in, and was checked before pinning.** `opentelemetry-api` is **required by FastAPI itself**, so it can't be dropped without dropping FastAPI. On its own it is a do-nothing interface: the tracer provider is `ProxyTracerProvider`, and no SDK or exporter is installed, so nothing is collected or sent anywhere. A comment in `requirements.txt` says not to add an SDK or exporter without asking.
  - pydantic, which FastAPI uses to validate request parameters, is now in the environment too; the 422 errors in the plan come from it.
- **Results:** installed; versions pinned; no conflicts; telemetry confirmed inert.
- **Interview Q:** *"You installed a web framework and it brought a telemetry library. How do you know your app isn't sending data somewhere?"* I checked rather than assumed. The package is only an API. Without an SDK and an exporter there is no code path that sends anything, and the runtime check shows the placeholder provider. Pinning the version and noting "no SDK without asking" keeps it that way.

## Step 61: App skeleton, `/api/data/coverage`, `/api/routes` (`backend/app/`)
- **Built:**
  - `db.py`: one **read-only** connection per request, `resolve_version` (an unknown version is a 404, never a fallback), and the shared cutoff rule `permitted_through(version, cutoff)`;
  - `labels.py`: the spec 9.13.3 provenance labels and 9.16.1 units in one place, plus `envelope()`, which stamps every response with data version, mode and cutoff;
  - `routers/data.py` (`GET /api/data/coverage`) and `routers/routes.py` (`GET /api/routes`);
  - `main.py`.
  - 16 tests in `backend/tests/test_api_data_routes.py`. The conftest gained `loaded` (the real import, reused across test files and redone only if a test emptied the database) and `client` (the app pointed at `routeranker_test`).
- **Why:** spec 9.16.2's "Data and coverage" screen and 9.17.3's route discovery are the first two things a reviewer opens.
- **Key concept:** *a cutoff is enforced where the data is read, not where it is shown*. Every query has `service_date <= permitted_through` in its SQL, so data after the cutoff never reaches Python, let alone the screen. Without a cutoff, the bound is the version's own ridership cutoff, so both cases run the same code. Like a library that keeps future newspapers in a locked room rather than asking readers not to look.
- **Decisions:**
  - **Your addition:** coverage and routes take the same backend-enforced `cutoff` as history, rankings and compare.
  - **Under a cutoff:**
    - every date-derived count is cut, schedule rows included;
    - archives captured after it are hidden, and applied ranges are clipped;
    - version-level figures that describe later data are left out (rows excluded after the version's cutoff, per-file manifest row counts, the import timestamp);
    - Stage 5 groups are hidden if their profile period ends after the cutoff, and group filters then return 422.
  - **Bug the tests caught:** `ungrouped=true` first returned about 60 historical identifiers (e.g. `290S`, `X99`) that only have rides from before the ridership window. Those routes were never in Stage 5's population, which is not the same as "ungrouped with a reason". Now `ungrouped=true` returns exactly the 5, routes outside the population match neither value, and an `in_group_population` field keeps the three cases apart.
  - No connection pool (it would need a new package, `psycopg-pool`). Opening a connection costs about 40 ms per request, to revisit when we measure.
  - Starlette warns that its TestClient's use of `httpx` is deprecated in favour of a package `httpx2`. Not added, because it would be a new dependency; the tests work as approved.
- **Results:**
  - **Real database:**
    - coverage about 0.9 s (1,120,604 rows; 28,374 matched; 8 archives; 99.915%);
    - with `cutoff=2026-05-31`: last ride 2026-05-31, 21,360 matched, 7 archives, no date after the cutoff;
    - routes about 0.3 s (188 identifiers; group 0 = 67; no Saturday service = 30).
  - **Tests:** 16 pass. The cutoff tests scan every date in the whole response, check every count against independent SQL, and require the cutoff to have actually changed the counts.
- **Interview Q:** *"Why not just filter the dates in the frontend?"* Then the data has already left the server. Anyone can open the browser's network tab and see the future values, and a tooltip or table could show them by accident. Spec 9.17.3 asks for "replay restrictions in backend queries, not only frontend hiding". The tests check the raw JSON, not the screen.

## Step 62: `GET /api/routes/{route}/history` (`backend/app/routers/history.py`)
- **Built:** one row for **every calendar date** in the range: reported day type, recorded rides, the selected archive's scheduled service, both ratios, and a status with its reason (`matched`, `ridership_without_schedule`, `schedule_without_ridership`, `no_service_no_record`, `recorded_rides_only`, `no_record`). 14 tests in `backend/tests/test_api_history.py`.
- **Why:** spec 9.16.3's route detail needs "history, scheduled service, ratios", and 9.16.1 says missing values show "unavailable with a reason" and never render as zero.
- **Key concept:** *a row for every date makes gaps visible*. If only dates with data were returned, a chart would draw a straight line across a missing week and nobody would notice. With every date present and the missing ones marked, the gap is drawn as a gap, with its reason in the tooltip. Like a diary with a page for every day, where blank pages say "no entry" instead of being torn out.
- **Decisions:**
  - The default range is the analysis window (dated schedules exist only there). The full history back to 2001 is available with an explicit `start`.
  - Day type on dates without this route's record comes from the other routes on that date (Stage 2: one reported day type per date).
  - `selected_snapshot_id` appears on every date in the schedule window, even when the route didn't run, so "no service" names the timetable that said so (spec 9.19.2).
  - Only `mode=historical`; `mode=replay` is 422 until Stage 7.
  - **Your addition:** a range that starts after the cutoff is a **422** ("the requested range starts after the cutoff"), not an empty 200. That includes starts after the version's own cutoff (2026-08-01).
  - **The strict scan caught an echo:** the response first echoed `requested_end = 2026-07-31` under a 2026-05-31 cutoff. It was only the caller's own input, but I removed the echo rather than add an exemption to the test, so "no date after the cutoff anywhere in the response" holds without exceptions. The response gives the effective range and `clipped_to_cutoff`.
  - Under a cutoff, the "not found" check uses only data up to the cutoff, so a route that first appears later is a 404 instead of leaking that it exists.
- **Results:**
  - **Tests:** 14 pass. Statuses equal the Stage 2 tables for routes 22, 169, 1001 and 10. Route 169's Thanksgiving and Christmas rows are `schedule_without_ridership` with rides null. Route 1001 never has scheduled service.
  - **Real database:** route 22 default 166 ms (251 days, 88 KB); cutoff 2026-05-31 79 ms (190 days); full history 401 ms but **3.7 MB** (9,343 days). My earlier estimate of about 1.5 MB was wrong, which is another reason the default is the analysis window.
- **Interview Q:** *"Why return 9,000 rows when most are 'recorded_rides_only'? Just return the days with data."* The client then has to rebuild the calendar to find the gaps, and every client must get that right. Here the server, which knows the schedule window and the reasons, decides once what each day is. The default range keeps the normal response small (88 KB).

## Step 63: `GET /api/rankings` (`backend/app/routers/rankings.py`)
- **Built:**
  - the three named rankings of spec 9.12 (observed daily demand, rides per scheduled trip, rides per scheduled hour) for a configured period or `start`/`end`, a day type, a gate (`min_days`), an optional group and an optional cutoff;
  - the **route overlap review** (Stage 5 pairs ranked by Jaccard) as a fourth metric;
  - `permitted_matched` and `permitted_schedule` in `db.py`, the shared loaders with the cutoff in SQL;
  - 22 tests in `backend/tests/test_api_rankings.py`.
- **Why:** spec 9.16.2's "Review priorities" screen: choose an indicator and minimum days, see the eligible ordering, sample size and explanation.
- **Key concept:** *one implementation, two callers*. The endpoint doesn't re-implement ranking. It loads the permitted rows and calls Stage 5's own `utilization_profiles`. The API and the Stage 5 report can't drift apart, because there is only one recipe. Like two restaurants serving from the same central kitchen: the dish is the same because it is the same pot.
- **Decisions:**
  - **Your change:** `min_days` defaults to *not given*, meaning the reference gate of 20. Any explicit `min_days` with the overlap review is a 422, and `non_reference_gate` is true only when the resolved gate differs from 20, so an explicit `min_days=20` is still "reference".
  - Ranking within a group takes day types from all routes (as Stage 5 does) and ranks only the group's routes.
  - The overlap review isn't hidden by the Stage 5 profile period, because it comes from GTFS stop sets alone, with no ridership. Under a cutoff only archives captured on or before it can be chosen.
  - Only the configuration that applies (gate, direction, ties, ratio rule) is returned, not the period list, so no configured date after a cutoff appears.
- **Results:**
  - **Tests:** 22 pass, all on the first run.
    - For both periods × W/A/U × all 3 metrics, the API equals the imported Stage 5 table (rank, eligibility, reason, days, numerator, denominator) and the committed `stage5_rankings.csv` to its 6 decimals.
    - With `cutoff=2026-05-31`, the API equals `utilization_profiles` run directly on the CSV rows up to the cutoff, and at least one rank changes.
    - **Synthetic data version:** route X is 1st with a 2026-02-15 cutoff, and route Y is 1st without it. This is the whole path, SQL included.
    - Development-period Saturdays: 0 ranked at gate 20, some ranked at gate 8 (labelled non-reference).
  - **Real database (median of 5):** rankings **129–242 ms** (15–26 KB); overlap review **73 ms** (286 KB).
- **Interview Q:** *"Your synthetic test inserts fake data into the test database. Why not just test the ranking function directly?"* Because the cutoff lives in SQL, not in the function. A pure function test would pass even if the endpoint forgot the `WHERE service_date <= cutoff`. The synthetic version goes through the real request, the real query and the real function. It is given an old `imported_at`, so it can never become the default version, and it is deleted afterwards.

## Step 64: `GET /api/routes/compare` (`backend/app/routers/compare.py`)
- **Built:**
  - 2–8 routes over **one** period and day type, with the three indicators (value, numerator, denominator, network rank, eligibility, reason), service per day, coverage on both sides, group, map lines in one named geometry version, and the Stage 5 overlap rows among the chosen routes;
  - a refactor of `rankings.py` into `resolve_period()` and `compute_profiles()`, so both endpoints use the same code; the 22 rankings tests confirm nothing changed;
  - 15 tests in `backend/tests/test_api_compare.py`.
- **Why:** spec 9.16.2 "Compare routes: comparable period/day type, demand/service and coverage differences", and 9.17.3 "comparable route evidence and geometry version".
- **Key concept:** *same ruler, same days*. Comparing two routes only means something if both are measured the same way over the same days. The endpoint puts every route on one period, one day type and one gate. It also counts the dates on which **all** chosen routes were observed (`common_matched_days`), and warns when they differ. Route 10 has matched weekdays only from June, so comparing its ratio with route 22's full-window ratio compares a summer with a whole season.
- **Decisions:**
  - **Network ranks:** all routes are ranked, then the chosen ones picked, so a rank means the same as on Review priorities.
  - **Your additions:**
    1. The response states the gate: `gate_label: "reference gate: 20"`. The rankings endpoint now has the same field, which reads "non-reference gate: 8 (reference: 20)" when another gate is used.
    2. A route not in the chosen geometry version comes back with no lines and the reason **"not in this timetable version"**: no error and no silently empty map. Route 10 in the 2026-03-26 version is the test. A separate reason ("in this timetable version, but no active trips on its applied dates") is ready for routes listed but not running. No route in this data version needs it (checked: 0).
  - The default geometry version is the archive in force on the period's last permitted day.
  - Overlap rows come from GTFS stop sets only, so the group cutoff rule doesn't hide them (consistent with the overlap review).
- **Results:**
  - **Tests:** 15 compare + 22 rankings pass.
    - 49 / X49 in the 2026-03-26 version: smaller-route overlap 1.0, 4 lines, all `[lon, lat]` inside the Chicago box.
    - Under `cutoff=2026-05-31`: no date after it in the whole response, ranks equal the rankings endpoint with the same cutoff, the geometry is the 2026-05-30 version, and the 2026-07-11 version is a 422.
  - **Real database (median of 5):** 206–332 ms. Two routes 144–167 KB, eight routes 646 KB; most of it is map lines.
- **Interview Q:** *"Why return ranks among all routes instead of ranking just the routes being compared?"* With two routes, a "rank among the compared" can only be 1st or 2nd, which says almost nothing. A network rank tells the planner where each route sits among all routes, and it matches the Review priorities screen, so the same route never shows two different ranks.

## Step 65: `GET /api/route-groups`, `GET /api/map/lines`, display simplification
- **Built:**
  - `routers/groups.py`: the Stage 5 groups with names, sizes, members, summaries of all 7 candidate features in original units (the 5 used for clustering marked), weekend-service counts, all 4 caveats, the profile period, artifact version and sha, and the ungrouped routes with their reasons;
  - `analytics/geometry/simplify.py`: Douglas–Peucker simplification for display, numpy only;
  - `routers/maps.py`: one geometry version's lines, chosen by `geometry_version`, by `date`, or by default the one in force on the last permitted date;
  - tests: 4 in `test_api_groups.py`, 11 in `test_api_maps.py`, 4 in `analytics/tests/test_simplify.py`.
- **Why:** spec 9.16.2 needs a home for "inspect a group" (your Route groups screen) and a "dated map" on Network overview. 9.19.2 says every map identifies its geometry version.
- **Key concept:** *simplify for the eye, never for the record*. A line with 1,100 points along straight grid streets looks identical with 30 points at city zoom, where one screen pixel is about 75 m. Douglas–Peucker keeps a point only if dropping it would move the drawn line by more than the tolerance. The stored lines never change, and every response states the tolerance and both point counts. Like a subway map: true enough to navigate by, and labelled as a diagram, not a survey.
- **Decisions:**
  - **Silhouette (your choice, option 1):** the k table is not in the API. It exists only in the committed `reports/stage5_quality_checks.json`, which isn't imported and isn't covered by a manifest sha. The groups response gives k = 2, the fixed k rule and the 5 features, and points to the Stage 5 report, section 4. *My earlier claim that the silhouette was in the Stage 5 manifest was wrong: only `silhouette_tolerance` is there.*
  - Summaries come from Stage 5's own `group_summary` on the imported profiles. Under a cutoff before 2026-03-31, the response is a 200 with `available: false` and the reason, so the screen can explain instead of erroring.
  - The map defaults to **10 m**; `simplify_m=0` returns the stored lines exactly. Lines carry `group_id` for colouring and `tie_label`; requested routes missing from the version come back with the compare endpoint's reasons.
  - A `date` before 2025-11-23 is a 422 ("no timetable version applies"), never an older map.
- **Results:**
  - **Tests:** 19 pass. The simplify test checks **every stored point of all 250 lines** of the 2026-07-11 version against its simplified line, point to segment: all within 10 m (+1 m for 5-decimal rounding). Route 125 northbound is the only tied line, as in Step 57.
  - **One test first failed on precision, explained rather than loosened:** the API's group-0 maximum is 17,082.93258, against 17,082.932584 in `stage5_group_summary.csv`. `route_profiles.csv`, the file that was imported, stores **10 significant digits** (checked), while the summary was computed from full precision and printed to 6 decimals. The test now compares at "equal within both roundings" (relative 1e-9, absolute 5e-7).
  - **Map size:** a full version is **5.9 MB exact vs 213 KB at 10 m**.
- **Interview Q:** *"Isn't simplifying the geometry hiding data?"* It would be if it were silent or stored. Here the stored line is untouched, the response says "simplified for display: every stored point within 10 m of the drawn line" with both point counts, and a test proves the 10 m promise for every point of every line. The route-detail and compare views use the exact lines.

## Step 66: Response times of every 6b endpoint on the real database (median of 5, in-process)
| endpoint | median | size |
|---|---:|---:|
| `/api/health` | 5 ms | 0 KB |
| `/api/data/coverage` (cutoff 2026-05-31) | 1,114 ms (879 ms) | 9 KB (4 KB) |
| `/api/routes` (cutoff + Saturday filter) | 244 ms (244 ms) | 75 KB (39 KB) |
| `/api/routes/22/history` (from 2001) | 76 ms (390 ms) | 88 KB (3.7 MB) |
| `/api/rankings` (dev/Sat/gate 8; cutoff + group) | 240 ms (173 ms; 195 ms) | 15–27 KB |
| `/api/rankings?metric=route_overlap_review` | 73 ms | 286 KB |
| `/api/routes/compare` 2 routes (8 routes + cutoff) | 312 ms (275 ms) | 167 KB (645 KB) |
| `/api/route-groups` (cutoff before profile end) | 81 ms (57 ms) | 6 KB |
| `/api/map/lines` default 10 m (exact) | 653 ms (426 ms) | 213 KB (5.9 MB) |
| `/api/map/lines` 2 routes exact | 77 ms | 142 KB |
- **Verdict:** nothing is slow enough to investigate now (your rule: investigate only if slow). Every call is under 1.2 s.
  - The slowest is **coverage**, which counts all 1.12 M ridership rows on each call. A cached summary would fix it if it ever matters.
  - The default **map** spends its time on simplification in Python, the price of a 28× smaller payload.
  - Opening a connection per request costs roughly 40 ms; a pool still isn't needed.
- The 18-minute real import (Step 59) is still unexplained. These read times show the real database itself is not slow.
- **Full suite after 6b:** **237 passed** in 6 min 37 s (137 analytics + 4 simplify + 96 backend). The shared `loaded` fixture means the real import ran **once** (118 s), plus the two deliberate rollback loads (about 100 s each). Before this change the backend tests imported three times.

# Stage 6c: React screens (spec 9.16)

## Step 67: Frontend scaffold, packages and the style reference page (`frontend/`, `/style`)
- **Built:**
  - **Scaffold:** the Vite React-TS template (create-vite 9.3.4), generated in a scratch folder, inspected, then copied into `frontend/` without its demo assets.
  - **Packages, all exact versions:**
    - react 19.3.1, react-router-dom 7.18.6, leaflet 1.9.4, react-leaflet 5.0.0, recharts 3.11.0;
    - tailwindcss and @tailwindcss/vite 4.3.5, @types/leaflet 1.9.22, vitest 5.1.1;
    - the template's own vite 8.3.8, typescript 7.0.2, oxlint 1.94.0 and type packages.
  - **Version pinning:** `.npmrc` has `save-exact=true`, and a small script replaced every template `^`/`~` with the installed version.
  - **Vite config:** proxies `/api` to `http://127.0.0.1:8000` for both `dev` and `preview`, with no CORS in the backend.
  - **`tsconfig`:** `strict` and `noUncheckedIndexedAccess` are switched on.
  - **Building blocks:** design tokens (`index.css`, `design/tokens.ts`), `RouteSign`, `Value`/`fmt`, `Panel`/`KeyNumbers`/`ApiLabel`, `PageHeader` with the mode switch, `PeriodBar`, `MapCaption`, the three states, and the `Shell` (sidebar + top strip).
  - **`/style` page:** shows all of these with specimen values.
  - **Tests:** 4 vitest tests for the missing-value rule.
- **Why:** your design brief asked for one approved look before any screen is built. Every screen will be assembled from these same pieces, so the look stays consistent by construction rather than by care.
- **Key concept:** *colour means data*. The interface is ink on white, and the only hues are the route-group colours. Then a reader never wonders "why is this blue?": blue always means Group 0, on every chart, map and route sign. Like a transit map, where a colour is a line and nothing else.
- **Decisions:**
  - **Direction A, "Signage" (your choice):**
    - the system font, so no font package and no outside font request;
    - ink as the only accent;
    - no shadows or card grids;
    - route numbers as sign plates with a group stripe.
  - **Structure from the mentor screenshots (structure only):** sidebar, breadcrumb strip, page header with a mode switch (Replay disabled until Stage 7), period bar, key-number row, chart with a side panel, detail table. Their map showed "API KEY REQUIRED" over the tiles; ours uses OpenStreetMap tiles, which need no key, with attribution.
  - **Colours checked, not eyeballed:** the dataviz validator passes Group 0 `#0072B2` and Group 1 `#D55E00` on every check (colour-blind ΔE 21.9). The grey for "ungrouped" fails the "reads as grey" check **on purpose**, so it is never the only cue: it is dashed on maps and always labelled. WCAG contrast is ink 17.8:1, secondary text 7.3:1 (6.8:1 on the canvas) and warning text 6.2:1.
  - **The template now ships oxlint, not ESLint.** It is the template's own linter, kept under your "template lint set" approval and flagged to you.
  - **A recorded 0 stays "0"; a missing value reads "unavailable – reason"**, and a test proves both.
- **Results:** `tsc -b` passes; `npm run lint` is clean (one warning fixed by moving the screen list to `screens.ts`); vitest 4/4; `npm run build` passes. The bundle is 845 kB (249 kB gzipped), and Vite warns above 500 kB. To revisit by splitting the map and chart code per screen once the screens exist. `npm ls` shows no invalid or missing packages.
- **Superseded in Step 67b:** the sidebar, page header, period bar and number-card row were replaced by RouteRanker's own structure. The tokens, route signs and map styling stay.
- **Interview Q:** *"Why build a style page before any real screen?"* Agreeing on the building blocks once is cheaper than restyling six screens. It also turns design rules into code: if the only way to show a number is `<Value>`, then "missing is never 0" holds everywhere automatically, instead of depending on each screen remembering it.

## Step 67b: RouteRanker's own structure, signature features and the slate palette (`/style`, still no screens)
- **Built:**
  - **`TopBar`:** a slate bar with 7 tabs (Start · Closer look · One route · Alike · Shared stops · Compare · Data), the mode in plain words ("Historical analysis · Replay: Stage 7"), "Data through" and a **Sources** drawer. It replaces the sidebar.
  - **Start page index:** `QuestionIndex` lists the planner questions as full-width rows, each with a one-line answer preview.
  - **`Sentence`/`Choice`:** the view is stated as a readable sentence with inline dropdowns. It replaces the period bar.
  - **`Provenance`:** `Num` makes every number a button that opens a **"How was this number made?"** drawer (formula, numerator ÷ denominator = value, days and gate, period, day type, timetables, data version, the exact API request, and the reason when missing).
  - **`RankTrio`:** the three named rankings side by side, each with its **stability** (development → full window).
  - **`RhythmGrid`:** weeks across, Mon–Sun down, one slate hue for magnitude.
  - **`StopShareStrip`:** two bars aligned on the shared stops.
  - **Helpers:** `lib/rhythm.ts`, `lib/stopShare.ts` and `lib/stability.ts`, plus 10 new tests (14 in all).
  - **Removed:** the old `Shell`, `PageHeader`, `PeriodBar` and the number-card row.
- **Why:** you asked for a structure of RouteRanker's own rather than the mentor's skeleton recoloured, and for features that show its strengths: every number can be traced, and nothing is hidden.
- **Key concept:** *provenance on demand*. A number on screen is a claim. The dotted underline invites "prove it": one click shows the formula, the two totals divided, the days counted and the timetables used. Like a receipt stapled to every price tag. You don't have to read it, but it is always there.
- **Decisions:**
  - **Slate brand on a warm page (your request):**
    - three shades on `/style`, swapped live (`#232B35`, `#2B3440`, `#37424F`);
    - page `#F4F2EE`, panels white, hover `#EDF0F3`, selected row `#E1E6EC`, main text `#1C232B`.
  - **Contrast measured for every pair, all AA:** main text 12.6–15.9:1; secondary text 5.8–7.3:1; white on slate 10.2–14.3:1; menu text 6.6–9.3:1; warning 6.2:1.
  - **The ungrouped grey is only 2.9:1 on the warm page**, so data marks always sit on white panels, where it reaches 3.2:1.
  - **Missing values are quieter:** `<Value>` always renders them 12 px, normal weight, secondary colour, whatever the parent's size. A test checks the markup never carries bold or large classes, and that a recorded 0 renders "0".
  - **Rhythm grid:**
    - the shading is a **single slate ramp**, not blue or orange, because those mean "group" and nothing else;
    - a missing day is a dashed empty cell with its reason;
    - a recorded zero is a filled cell marked "0";
    - a day outside the data is blank, and a test keeps the three apart.
  - **Stability has no "stable/unstable" verdict:** the spec defines no threshold, so it states the movement ("Development 3rd → full window 5th (moved 2 places down)") or "not comparable – unranked in …". The how-to-read line says the full window contains the development period.
  - **The stop-share strip shows how many stops are shared, not where.** The database stores stop sets without order or position (`served_stop_ids`, `shared_stop_ids` are `text[]` sets), and the strip says so. An along-the-street strip would need stop order from the GTFS archives: a new import, offered only as a proposal.
  - **Drawer focus:** the drawer focuses its heading once when it opens and closes on Esc. The first draft re-focused on every parent re-render, and was fixed before running.
- **Results:** `tsc -b` passes; lint is clean; vitest **14/14**; `npm run build` passes (863 kB, the chunk-size warning is still open from Step 67).
- **Interview Q:** *"Why make every number clickable? Isn't that clutter?"* The dotted underline is quiet, and the drawer opens only on request. The value is trust: a planner who doubts "58.78 rides per scheduled hour" can see it is 1,234,567 rides ÷ 21,003.9 trip-hours over 171 weekdays, from named timetables, with the exact API request to reproduce it. Without that, the number is a claim the reader can't check.

## Step 67c: Three fixes to the approved style (slate `#2B3440` chosen)
- **Built:**
  1. **Top bar above the map:** Leaflet's panes reach z-index 700 and its controls 1000, and the bar was at 900. The bar is now 1100 and the drawers 1200.
  2. **No overflow at 1366 px:**
     - every grid column is `minmax(0, …)` instead of `1fr`, and text blocks have `min-w-0`/`break-words`;
     - side-by-side sections stack below `lg`/`xl`;
     - the top bar wraps onto a second row when needed, "Data through" became "Data to", and "· Replay: Stage 7" shows from 1280 px (always in the tooltip);
     - tables scroll inside their panel; table headers are no longer sticky, because a sticky header would slide under the bar;
     - the shade picker became one "chosen" swatch.
  3. **Both ends, neutral words:** `lib/ends.ts` `rankingEnds()` gives the highest and lowest ranked routes (ties kept, ends never overlap, unranked routes only counted). `EndsPreview` shows "highest … · lowest … · N unranked", and `END_WORDS` is the only place the words live.
  4. **Specimens follow the real groups:** 49 and X49 were shown in Group 1 but are in Group 0 (`group_names.json`). Every route sign on `/style` now uses its real Stage 5 membership.
- **Why:** you found the overlap and the right-edge clipping in the browser. "Best/worst" would turn a review indicator into a verdict, which the spec 9.12 caveat forbids.
- **Key concept:** *a `1fr` column is not "whatever space is left"*. Its minimum is its content's width, so one long word or wide child pushes the whole grid past the screen. `minmax(0, 1fr)` says "you may shrink to nothing; wrap your text instead". Like telling a shelf it may be narrow, so the books stack instead of sticking out.
- **Decisions:** wrap rather than cut: no `overflow: hidden` on the page, since hidden text is lost text.
- **Results:** `tsc`, lint and build pass; vitest 18/18 at this point (4 new for `rankingEnds`). A grep finds "best/worst" only in the rule's comment and the test that forbids them.
- **Interview Q:** *"Why not just call them the best and worst routes? Everyone understands that."* Because the number can't support the verdict. A low rides-per-hour route may exist for coverage, and a high one may be a short, crowded shuttle. "Highest/lowest" describes the measurement, and the screen leaves the judgement to the planner.

## Step 68: API client, response types, cutoff context and live data status (`frontend/src/api/`)
- **Built:**
  - **`api/types.ts`:** the response of every 6b endpoint typed field by field from the routers; anything the API may leave missing is `| null`.
  - **`api/client.ts`:**
    - `buildUrl` (null params dropped; `cutoff` and `data_version` added only when set);
    - `apiGet` (keeps FastAPI's own `detail` text, including 422 validation lists);
    - `ApiError`, and `api.*` with one function per endpoint.
  - **`api/cutoff.ts`:** `CutoffContext`, null in Stage 6.
  - **`api/useApi.ts`:** loading → ok | error with retry; aborts stale requests; passes the cutoff to every call.
  - **`AsyncBlock`:** loading/empty/error/content for every block.
  - **`SourcesPanel`:** the Sources drawer (data version, both commits, schema sha, every archive's sha256).
  - **Live top bar:** it now shows the real `mode_label` and "Data to {permitted_through}".
  - **Tests:** 14 new in `api/client.test.ts`.
- **Why:** the screens need one trustworthy way to call the API. Stage 7's replay must reuse these screens without rewriting them, so the cutoff is designed in now (plan: "keep an optional cutoff in the API client").
- **Key concept:** *the client forwards the cutoff; the server enforces it*. The frontend never filters dates itself. It passes `?cutoff=` and the backend drops later rows in SQL (Step 61). Like handing a sealed envelope to the post office: the client addresses it, and the rules are applied where the mail is sorted.
- **Decisions:**
  - Every URL is `/api/...` on the same origin, so Vite's proxy carries it and the backend still has no CORS. A test asserts every endpoint's URL starts with `/api/`.
  - **"The API is not running" is a sentence, not a stack trace.** A network failure or a proxy 502/504 becomes "the API is not reachable (is uvicorn running on 127.0.0.1:8000?)".
  - **`simplify_m: 0` is sent, not dropped.** Exact lines depend on it, and a test checks it.
  - **A slow answer can't overwrite a newer one:** `useApi` aborts the previous request when its key or the cutoff changes.
  - TypeScript's `erasableSyntaxOnly` (template setting) forbids constructor shorthand, so `ApiError` declares its fields explicitly.
- **Results:**
  - `tsc` and lint pass; **vitest 32/32**; the build passes.
  - **End to end through the Vite proxy** (uvicorn started locally): coverage returns data version `cta_ref__r20261113__gtfs8__to20260731`, "Historical analysis", data through 2026-07-31, 8 archives, 99.915 %.
  - With `cutoff=2026-05-31`: through 2026-05-31, 7 archives, 21,360 matched rows. Both equal Step 61.
  - Before uvicorn started, the proxy returned 502, which the client turns into the plain "not reachable" message.
- **Interview Q:** *"Why does the client test that every endpoint forwards the cutoff, if Stage 6 never uses one?"* Because Stage 7 depends on it, and a missing parameter fails silently: the replay would show "future" data with no error at all. Eight tiny tests now make "forgot the cutoff on one endpoint" impossible to ship.

## Step 69: `GET /api/network/trend` and per-route profile values on `GET /api/route-groups`
- **Built:**
  - **`backend/app/routers/network.py`:** `GET /api/network/trend?start&end&cutoff`.
    - One row for every calendar date: day type, recorded rides summed over the routes that reported, `routes_reporting`, and, inside the schedule window, scheduled trips and `routes_scheduled`.
    - Status `recorded`, `recorded_rides_only` (before 2025-11-23: no dated schedule) or `no_record` (rides null with a reason, never 0).
    - `summary` per day type (days, mean and median rides/day), so a screen writes its sentence from the API.
    - The default range is the analysis window; `start` may go back to 2001. The cutoff clips the range in SQL, as in history.
  - **`route_values` on `/api/route-groups`:** each of the 123 profiled routes with its group and its own 7 development-period values, each `{value, status, reason}` in original units.
  - **Frontend:** `TrendResponse` and `RouteValues` types, `api.trend()`, and `lib/scatter.ts` `scatterPoints()`, which splits routes into plotted points and left-off notes.
  - **`CLAUDE.md`:** the new "UI design principles" section you approved.
- **Why:** the Start page needs a network demand trend, and the Alike page needs each route's own values to place it among its group (a scatter). Neither existed in 6b.
- **Key concept:** *the clustering input is not the display value.* For KMeans, Stage 5 had to fill route 169's missing Sunday/holiday ratio with the median (0.511), because KMeans can't take a blank. The screen must not show that filled value as if it were measured. So the API reads the **stored** profile, where the gap is still a gap. It's like a recipe that needs an egg: you substituted applesauce to bake, but the shopping list still says "no eggs".
- **Decisions:**
  - **Missing → off the scatter, with a note.** Route 169 has *both* weekend ratios missing: 6 matched Saturdays of 18 scheduled, and 0 Sundays/holidays of 3 scheduled, both below the 8-day gate. The note names the route and the reason.
  - **Structural zero → plotted at 0.** 30 routes have no Saturday service and 36 no Sunday/holiday service. "No buses ran" is a known value, not a missing one, and its status travels with the point for the tooltip.
  - **The cutoff rule is the groups' rule:** under a cutoff before 2026-03-31 the whole groups response is unavailable, so `route_values` is hidden too. The boundary is tested: hidden on 03-30, shown on 03-31.
  - **`routes_reporting` travels with every daily total:** the total drops if routes are missing from the export on a day, and the count makes that visible.
  - **uvicorn runs without `--reload` here:** on Windows the auto-reload hung (the old worker never exited), so the server is restarted by hand after backend changes.
- **Results:**
  - pytest: the new 7 trend tests and 6 route-value tests pass (20/20 in the two files), and the full suite passes: **253 passed** (6 min 15 s; the only warning is the existing starlette/httpx deprecation).
  - vitest 37/37 (4 new scatter tests, and `trend` in the cutoff-forwarding test); `tsc`, lint and build pass.
  - Live through the proxy: the analysis window is 251 recorded days; mean rides/day are weekday 612,873, Saturday 428,188, Sunday/holiday 331,099. The full history since 2001 is 9,343 dates (0.6 s, 2.2 MB). The real export has a record on every date, so the gap rule is tested on a range that starts before 2001.
- **Interview Q:** *"Why not just plot route 169 at the group median? It's only one dot."* Because a dot is a claim that we measured it. A filled-in value sits in the middle of the cloud by construction, so it would look perfectly typical and could even suggest the route is "like" its group for that reason. Leaving it off, with a sentence saying why, is honest and costs one line of text.

## Step 69b: Table minimum widths and the `/style` DevTools issues
- **Built:**
  - `.data-table` cells have `min-width: 6rem` (numbers `5rem`, never wrapped), and headers never wrap. Every table sits in an `overflow-x-auto` wrapper; the Sources table was missing one.
  - `Choice` dropdowns now have an `id` (`useId`), a `name`, and a visually hidden `<label for>`. They previously had only `aria-label`.
  - Every `<button>` has `type="button"`.
- **Why:** in a narrow window, columns were squeezed until text clipped. Chrome DevTools reported 8 issues on `/style`: 4 dropdowns × ("no id or name" + "no label associated with a form field").
- **Key concept:** *let the table scroll, not shrink*. A minimum width per column is like a bookshelf with fixed-width slots: if the wall is too short, you slide along the shelf instead of crushing the books.
- **Decisions:** a real `<label>` rather than only `aria-label`, because it works with every assistive tool and with Chrome's check; the visible sentence stays the label people read.
- **Results:** `tsc`, lint, vitest and build pass. The DevTools Issues count is to be confirmed by you in the browser.
- **Interview Q:** *"`aria-label` already names the field. Why add a `<label>` too?"* `aria-label` is read only by screen readers. A `<label for>` is native HTML: browsers, autofill, voice control and audit tools all understand it, and clicking it focuses the field. Native first, ARIA only when HTML can't do it.

## Step 70: Start page, and plain words in every API text (`screens/StartPage.tsx`, `rankings.py`, `compare.py`, `network.py`, `data.py`)
- **Built:**
  - The Start page (`/`). It shows the planner questions, each with a live one-line answer, then the network trend with its day-type sentence, the dated map and a route summary table.
  - **Four fixes after your review:**
    - the chart note no longer says `routes_reporting`;
    - "120 and 121, 17 shared stops" now has correct spacing;
    - the weekend column fits on one line ("Sat ✓ · Sun/hol –", with the key in "How to read this" and on hover);
    - "(spec 9.12)" is gone from visible text.
  - **API:**
    - spec numbers now travel in their own `spec_reference` field, which the "How was this number made?" drawer shows as "Defined in";
    - periods carry a plain `label`;
    - rankings carry `numerator_label`/`denominator_label`;
    - `/api/data/coverage` sends Stage 2's reason codes as `reason_code` and plain words in `reason`.
  - `tests/test_api_visible_text.py` scans every visible text field of 11 requests for spec numbers and field names.
- **Why:** a screen is read by planners, not by the API's authors. `routes_reporting` and "spec 9.12" mean nothing to them. The same facts stay available to anyone who asks "how was this made?".
- **Key concept:** *separate the words from the codes*. An API is like a parcel: the label on the outside (`reason`) is for people, and the barcode (`reason_code`) is for machines. Never print the barcode where the label should be.
- **Decisions:**
  - The fix sits in the API, not in each screen, so every screen gets the plain words for free and a test guards them.
  - Weekend status uses short marks with a key rather than two extra columns, so the table stays narrow.
- **Results:**
  - pytest: all passed after the fixes (the first full run caught 2 failures: a coverage reason code, and a test expecting the old period shape);
  - in `frontend\`: tsc, lint, vitest and build pass.
  - Still to fix: `/api/routes/{route}/history` sends coded reasons too (e.g. `no_ridership_record`). It will be fixed with the One route screen, the first screen to show them.
- **Interview Q:** *"Why not just translate codes in the frontend?"* Then every screen (and every future client) must repeat the translation and can drift. Doing it once in the API, with a test that scans all visible fields, makes "no field names on screen" a checked rule instead of a habit.

## Step 71: Closer look (`screens/CloserLookPage.tsx`, `lib/closerLook.ts`, `NumberChoice`)
- **Built:** `/closer-look`, spec 9.16.2's "Review priorities".
  - **The sentence controls:** measure (three rankings plus the route overlap review), day type, period, peer group, highest/lowest first, and minimum observed days. The minimum-days field takes any whole number of 1 or more: type it, or pick from 1, 5, 10, the reference gate and two to three times the reference.
  - **Under the sentence:** "N of M routes ranked at X days", the API's gate label (amber with "non-reference gate: X (reference: 20)" when X ≠ 20), and a "Back to the reference gate" button.
  - **Peer group:** ranks restart from 1 within the chosen group (the API's `group_id`), and a sentence says so. When the groups were fitted after the cutoff, the control reads "all routes (peer groups unavailable – reason)".
  - **The ranked table:** each route has its value and #rank on all three measures, and each value opens "How was this number made?". Rank stability is shown per measure as the development rank → full-window rank ("#5 → #3 · 2 up", or "not comparable").
  - **"Not ranked" panel:** a "Why unranked" line counted from the API reasons, e.g. on Saturdays "33 unranked: no scheduled service of this day type (30), fewer than 20 observed days (3)". Each route is listed with its reason, never as rank 0.
  - **Route overlap review:** a timetable choice, the "corridor review only" label, a sentence counted from the pairs, and the pair table (shared stops, Jaccard, share of the smaller route, each route's own stops).
- **Why:** the project's own finding is that *the measure you rank by changes who leads*. The insight sentence counts how many of the top 10 by one measure are also in the top 10 by another, and how many routes keep their place between periods, so a ranking reads as a prompt to look, not a verdict.
- **Key concept:** *a ranking depends on its settings*. Like a race result that changes if you count only finishers, or only one age group: the gate (minimum days), the peer group and the period are part of the answer, so the page states them in its first sentence.
- **Decisions:**
  - **Stability:** always the development period → the full matched window (the two configured periods), on the same day type, gate and group. There's no "stable/unstable" verdict, because the spec defines no threshold.
  - **Unranked rows:** in their own panel, so "highest first / lowest first" never mixes them in with the ranked rows.
  - **Ordering:** only reverses the ranks. The words stay neutral ("highest first", "lowest first").
  - **Helpers:** the counting lives in `lib/closerLook.ts`, which holds no numbers of its own.
- **Results:** in `frontend\`: tsc, lint, vitest (52 tests, 10 new) and build pass. Live API checks: `group_id=0` gives 67 routes ranked from 1, and `min_days=7` on Saturdays gives "non-reference gate: 7 (reference: 20)".
- **Interview Q:** *"Why show unranked routes at all?"* Leaving them out silently makes the ranking look complete when it isn't. A route with no Saturday service and a route with 7 observed days are both "not ranked", but for very different reasons. Showing the count by reason lets a planner see what the ranking can't tell them.

## Step 71b: Four Closer look fixes after review
- **Built:**
  - **Minimum-days box:** its width grows with the digits (`fieldWidth`), and the spin buttons are hidden. It shows the gate the API *applied* (`displayedGate`), so the box can never disagree with the ranking under it.
  - **Dropdowns:** they size to the chosen option (`field-sizing: content`), so "all routes" no longer has a long empty underline.
  - **Units:** each unit appears once, in the column header ("rides/day · rank"). Cells keep only the number and #rank, and the drawer still shows the unit.
  - **Table subtitle:** a plain sentence built from the API's labels: "Higher value = more recorded rides for each scheduled trip-hour."
- **Why:**
  - the box displayed "2" while the gate was 20, because the field was narrower than its text;
  - the select was as wide as its longest option;
  - units repeated in every cell were noise.
- **Key concept:** *the display must follow the applied value, not the typed one*. A thermostat shows the temperature it is set to, not the button you last pressed. A test pins the box to the API's applied gate.
- **Decisions:** `field-sizing` works in Chrome and Edge. In Firefox the select falls back to its old width, which is still usable.
- **Results:** in `frontend\`: tsc and lint (no warnings), vitest (56 tests) and build pass.
- **Interview Q:** *"How do you test that a box shows the right value without a browser?"* Move the decision into a pure function (`displayedGate(applied, requested, reference)`) and test it, including the stale-value case. The component only renders what the function returns.

## Step 72: One route (`/route/:route`), plan written before coding
- **What it shows:**
  - **Header:** route sign, name and group (or the ungrouped reason).
  - **Three ranks side by side:** observed daily demand, rides per scheduled trip and rides per scheduled hour, on a chosen day type. Each has its stability (development → full window).
  - **Recorded rides per day:** the analysis window by default, with "Show full history since 2001". Gaps show as gaps with their reason, never 0.
  - **Weekly rhythm grid** for the analysis window.
  - **Map:** the route's exact lines (no display simplification), with its caption.
  - **Shared-stop routes:** each partner with shared stops, Jaccard and share of the smaller route, the "corridor review only" label, and the stop-share strip for the closest partner.
- **Insight it highlights:** one route reads differently on each measure. The opening sentence states its three ranks, its weekend level as a share of an average weekday, and how many of its scheduled days have a ridership record. Every number comes from the API.
- **Rules:**
  - The history endpoint's Stage 2 reason codes become plain words (`reason`), with the code kept in `reason_code`.
  - Clicking any map line opens that route.
- **Built:**
  - `/route` (route picker) and `/route/:route`.
  - `lib/routeProfile.ts` (`daytypeMeans`, `shareOfWeekday`, `recordCoverage`) and `lib/provenance.ts` (one "How was this number made?" builder for ranking values, shared with Closer look).
  - `RidesChart`: one chart for the network trend and a route's history.
  - Map lines open their route on click, on every map.
  - API: history reasons are plain words, with the code kept in `reason_code`. The words live in `labels.REASON_WORDS`, shared with `/api/data/coverage`.
- **Key concept:** *a profile is several views of the same route*. A route can be last on daily demand and mid-table on rides per trip, the way a small shop can have few customers but a high spend per customer. The page puts the three side by side, so no single number stands for the route.
- **Decisions:**
  - The rhythm grid always shows the analysis window, even when the chart shows full history. Twenty-five years of weekly cells would be unreadable.
  - Shared-stop partners are sorted by Jaccard, and the strip shows the closest partner.
- **Results:**
  - backend: history, visible-text and data tests pass (44). The visible-text scan now also covers routes 169 and 1001.
  - frontend: tsc, lint, vitest (60 tests) and build pass.
- **Screenshot check (1366/1920):**
  - no overflow, clipped fields or console errors;
  - removed a duplicated "corridor review only" label;
  - checked that the chart's dips are real low counts (e.g. 1 ride on 11 Apr for route 169), not missing days drawn as 0.
- **Interview Q:** *"Why keep both `reason` and `reason_code`?"* People need words and programs need stable keys. Tests and filters match the code, which never changes. The words can be improved without breaking any program.

## Step 73: Alike (`/alike`), plan written before coding
- **What it shows:**
  - **Scatter:** any two of the seven profile measures, coloured by group. A route with a missing value is left off, with a note naming it and the reason. A structural zero (no scheduled weekend service) is plotted at 0, and its tooltip says why.
  - **Group spread:** each measure's min–median–max per group on one shared scale, so you can see where groups overlap.
  - **Weekend service counts per group.**
  - **Members:** each group's member routes, and the ungrouped routes with their reasons.
  - **The method:** k, the measures used and the k rule.
  - **All four caveats,** as the API sends them.
- **Insight it highlights:** groups describe a typical member, not a hard boundary. The opening sentence counts how many plotted routes sit inside another group's range on both measures shown. With the defaults, that shows the groups overlap.
- **Rules:**
  - The API now sends a plain `label` for every measure (with a test), so no column key such as `weekday_rides_cv` appears on screen.
  - Group colours are the only colours.
- **Built:**
  - `/alike`: the sentence picks any two of the seven measures. It holds the scatter (group colours, structural zeros at 0, routes with missing values listed under the chart with their reason), weekend service by group, the group spread table (min–median–max bars on each measure's scale), members, ungrouped routes with reasons, the method and all 4 caveats.
  - `insideOtherGroup` counts routes inside another group's range on both axes.
  - **API:** every measure now has a plain `label`, and the method has `selected_feature_labels`.
- **Key concept:** *a cluster is a summary, not a fence*. KMeans gives every route its nearest centre, the way a postcode puts a house in one district even when it sits on the border. The overlap count shows how many routes sit in that border zone.
- **Decisions:**
  - Spread bars use each measure's own scale, because rides and ratios can't share one.
  - Axis labels carry only the measure's name, and the units go in "How to read this".
- **Results:**
  - backend: groups and visible-text tests pass (25), including a new test that every measure has a plain label;
  - frontend: tsc, lint, vitest (63 tests) and build pass.
- **Screenshot check (1366/1920):**
  - the vertical axis label was cut off ("…(rides pe"); I shortened it;
  - the left-off note used column keys (`sunday_holiday_to_weekday_rides_ratio`); it now uses words, with a test;
  - the API server's auto-reload had hung and was serving old code. I restarted it without `--reload`.
- **Interview Q:** *"Silhouette 0.38: are these groups real?"* They're moderately separated. The page says so (caveat 3) and shows the overlap directly, so nobody reads a group number as a grade. The useful claim is "typical members differ", not "every route belongs cleanly".

## Step 74: Shared stops (`/shared-stops`), plan written before coding
- **What it shows:**
  - **The route overlap review table:** every pair of routes that share stops in a chosen timetable, with both overlap measures side by side:
    - **Jaccard:** shared ÷ all stops of either route;
    - **share of the smaller route:** shared ÷ stops of the shorter route.
  - **Each route's own stops,** as a share of its total.
  - **Controls:** sort by either measure (highest or lowest first), and an optional "involving route X" filter.
  - **Selected pair:** the stop-share strip and a map of both routes.
  - **The "corridor review only" label,** shown as the API sends it.
- **Insight it highlights:** the two overlap measures answer different questions. Jaccard says "are these two routes the same?", and the smaller-route share says "is one route inside the other?". The opening sentence counts how many of the top 10 pairs by each measure are the same pairs, and how many pairs share every stop of the smaller route.
- **Rules:**
  - Shared stop IDs are corridor evidence only, never merge/split evidence, so the label stays next to the table.
  - Pair counts and stop counts come from the API.
- **Built:**
  - `/shared-stops`: timetable, route filter, sort measure and order in one sentence. It has the "corridor review only" label, an opening sentence counted from the pairs, the pair table (both measures, plus each route's own stops), and for the chosen pair the stop-share strip and a map of both routes.
  - Helpers in `lib/sharedStops.ts` (`sortPairs`, `topAgreement`, `fullyInside`, `involving`), with tests.
- **Key concept:** *two overlap measures, two questions*. Jaccard compares two routes as equals: how much of everything they serve is shared? The smaller-route share asks whether a short route is contained in a long one. An express inside a local scores low on Jaccard but 100 % on the smaller-route share.
- **Decisions:**
  - A new `fmtPct` never rounds a share below 1 up to "100" (0.996 shows 99.6). "100 %" therefore always agrees with the "every stop of the smaller route" count. It is used on every screen that shows these shares.
  - The strip's warning label is optional, so a page that shows the label once doesn't repeat it.
- **Results:** in `frontend\`: tsc, lint, vitest (71 tests) and build pass.
- **Screenshot check (1366/1920):**
  - the strip's narrow "1 only" segment was cut to "1 o". A narrow segment now shows just the count, with the words in its tooltip and a minimum width.
  - I checked that the "100 %" pair (49/X49) really is 71 of 71 stops.
- **Interview Q:** *"Why not just say routes 120 and 121 should merge?"* Shared stop IDs ignore direction, timing, walking access and transfers. The data supports "these corridors are worth a look", not a merge decision. That's why the label sits next to the table.

## Step 75: Compare (`/compare?routes=…`), plan written before coding
- **What it shows:**
  - **Routes:** 2 to 8 of them, added from a list and removed with ×. The choice lives in the address bar, so a comparison can be shared.
  - **The sentence:** day type, period and the "same days only" switch.
  - **Warning:** when the routes weren't observed on the same dates, the API's common-days warning appears, with the count of dates all of them share and a button to switch.
  - **Table:** one column per route. Rows are the three indicators (value and network rank), scheduled trips and trip-hours per day, observed days and the coverage gaps on each side, and the group.
  - **Map and shared stops:** the routes' lines in one named timetable, and the shared-stop pairs among them with "corridor review only".
- **Insight it highlights:** which route leads on each measure, and whether one route leads on all three. Usually different routes lead on volume and on productivity. With "same days only", the values are recomputed on the dates all routes share, so a route observed for fewer days isn't compared unfairly.
- **Rules:**
  - API: a new `same_days` option recomputes every value on the shared dates. Network ranks are then left out, with a note (a rank among all routes isn't defined on hand-picked dates), and there's a test.
  - A missing value shows "unavailable – reason".
- **Built:**
  - `/compare?routes=…&daytype=…&period=…&same_days=true`: everything lives in the address bar, so a comparison can be shared. You add routes from a list and remove them with ×.
  - It shows the common-days warning with a "Use the same days only" button, an opening sentence naming each measure's leader, and the route-by-route table (indicators with provenance and network ranks, service, coverage, group). There is also a map in one named timetable with that timetable's own applied dates, and the shared stops among the chosen routes.
  - **API:** `same_days` recomputes every value on the dates all routes were observed (`compute_profiles(dates=…)`). Network ranks are then left out, with a note. The response also carries `basis_label` and numerator/denominator labels.
  - Helpers in `lib/compare.ts` (`parseRoutes`, `leaders`, `archiveRange`), with tests.
- **Key concept:** *compare like with like*. Two runners' average times mean little if one ran only in summer. "Same days only" restricts both to the days they both ran. On 49, X49, 10 and 22 this changes the answer: route 49 leads daily demand on each route's own days, but route 22 leads on all three measures on the 39 shared dates.
- **Decisions:**
  - With same days only, network ranks are hidden rather than recomputed. A rank among all routes on hand-picked dates would mean something different from every other rank in the app.
  - The coverage-gap rows say "in the whole period", because they don't change with the switch.
- **Results:**
  - backend: compare and visible-text tests pass (30). The new same-days test checks the means against an independent SQL average.
  - frontend: tsc, lint, vitest (76 tests) and build pass.
- **Screenshot check (1366/1920):**
  - the map caption showed the comparison period as the timetable's applied dates. It is now the timetable's own range, taken from coverage (`archiveRange`).
  - a long ungrouped reason stretched one column; it now wraps.
  - React reported table rows without `key`s; they now have keys.
  - the whole-period coverage rows weren't labelled as such in same-days mode; they now say "in the whole period".
- **Interview Q:** *"Why does the leader change with 'same days only'?"* Route 10 was observed only from June. Comparing on the shared dates removes the seasons the others saw and route 10 didn't, so each route is judged on the same days.

## Step 76: Data (`/data`), plan written before coding
- **What it shows:**
  - **Coverage:** recorded-rides range, analysis window, matched routes, dates and rows, and the share of scheduled route-days with a record.
  - **Missing data in both directions,** with reasons in words.
  - **The import checks,** in plain words ("N of N hold").
  - **Timetable archives** with their applied dates.
  - **The sources**, the same content as the Sources drawer.
  - **An honest model card:**
    - what was tried: 2 baselines, 2 ridge, 2 random forests and 4 neural networks;
    - what won: the random forest on ride history;
    - by how much it beat the 4-week average baseline, on validation and on the reused test period;
    - that the test period is a reused holdout, and that no neural network beat the random forest.
- **Insight it highlights:** how complete the data is, and how modest the model's gain over a simple 4-week average is. Both numbers come from the API.
- **Rules:**
  - The import-check names currently contain table names, so the API sends plain labels (with a test).
  - A new `/api/models/summary` reads the committed model manifests, gives every method a plain label, and is hidden under a cutoff before the test period ends (as the groups are).
- **Built:**
  - `/data`: opening sentences counted from the API (coverage %, gaps in both directions, import checks held), coverage counts, missing data with reasons, import checks in plain words, timetable archives, the model card and the sources (the same panel as the drawer).
  - **API:**
    - `quality.import_checks` (plain labels, with the original name kept in `check`);
    - new `GET /api/models/summary`: it reads the committed model manifests, gives every method a plain label, sorts best first, computes the gain over the best baseline, lists withheld reasons in words, and is hidden under a cutoff before 31 Jul 2026.
  - Helpers in `lib/modelCard.ts` (`gainWords`, `scoredShare`), with tests.
- **Key concept:** *a model card states the comparison, not just the score*. "MAE 345" means nothing alone; "4.1 % lower than a 4-week average" tells you what the model adds over a rule anyone could compute. A model card also says what was tried and lost (4 neural networks), and that the test period was looked at during development.
- **Decisions:**
  - The baseline is the best simple rule by validation error (the 4-week average), chosen in the API, not named in the page.
  - The gain words follow the sign, so a loss would read "higher".
  - The neural network count is counted from the methods, not written into the text.
- **Results:**
  - backend: the new `test_api_models.py` (5 tests: manifest values, gain arithmetic, cutoff rule, withheld words, import-check labels), plus the visible-text scan of `/api/models/summary` and of compare's same-days mode;
  - frontend: tsc, lint, vitest (80 tests) and build pass.
- **Screenshot check (1366/1920):**
  - "5.5 % lower than on the test period" was ungrammatical; it now reads "5.5 % lower on the test period".
  - "The four neural networks" was a hard-coded count; it's now counted.
  - lowercasing had turned "GRU" into "gru"; the label is now kept as sent.
  - the import-check names had shown table names; they are now plain labels from the API.
- **Interview Q:** *"Your model only beats the baseline by 4 %. Is it worth it?"* Maybe not on its own. That's exactly why the card shows the baseline. A 4 % lower error across 123 routes is real but small, and the 4-week average is cheap and transparent. The honest answer depends on what a planner gains from the extra accuracy, and the card gives them the numbers to decide.

## Step 77: Loading fix: a cancelled or late answer can no longer become a screen's data (`api/client.ts`, `api/useApi.ts`, `PageBoundary`)
- **Built:**
  - `apiGet` re-throws a cancellation that happens while the body is being read. It used to turn it into a "successful" `null`. A 200 answer that is empty or not JSON is now an error.
  - `useApi` hands an answer to the screen only while its request is still current (`settle`). A late answer from a cancelled or replaced request is dropped.
  - `PageBoundary`: a screen that fails to render shows the error and a Reload button instead of a blank app. It is keyed by the page address, so the next screen starts clean.
  - `scripts/clickthrough.mjs`: Start → Closer look → each screen, by clicking, waiting for real content.
- **Why:** you saw the Data page's coverage block stay grey after arriving from another screen. In my runs the server never failed or stalled: coverage is 11 KB and answers in about 0.6–1.5 s, even with 7 other requests running. Once, after clicking through all the tabs, I got a completely blank page, but I couldn't make it happen again. Reading the loading code found two defects that can put a screen into a wrong state.
- **Key concept:** *only the latest question may change the screen*. Like asking a waiter for coffee, then changing your mind to tea: if the coffee arrives after the tea, it must go back, not replace the tea. The abort signal says "this order was cancelled", and `settle` checks it before anything is shown.
- **Decisions:** the fix is at the cause (which answers are accepted), with no delays and no automatic retries. Every screen loads through the same `useApi` and `apiGet`, so all of them get it.
- **Results:**
  - vitest: 87 tests, 7 new (cancelled body read, non-JSON or empty 200, plain-text error body, late answers dropped, real failures kept);
  - tsc and lint clean;
  - the click-through check passes on all 7 screens.
  - I couldn't reproduce your exact grey-block state after 8+ attempts. If it ever returns, the browser's Network tab entry for `/api/data/coverage` will tell us more.
- **Interview Q:** *"Why not just retry when a request fails?"* A retry hides the bug: the wrong answer was being accepted, not lost. The fix decides which answer counts (the current request's), so retries aren't needed for correctness.

## Step 78: One natural route order everywhere (`lib/routeSort.ts`)
- **Built:** `compareRoutes`, `sortRoutes` and `sortByRoute`. Numeric routes come first, by number, then suffix (1, 2, 3 … 8, 8A, 9, 12, 53, 53A, 53AL). Letter-prefixed routes follow, by prefix, then number (J14, N5, N201, X4, X9, X49). It is used in the One route picker, Alike members and ungrouped list, Compare (chips, columns and the add list), the Shared stops route filter, the Data missing-data route lists, and every tie-break between equal ranks.
- **Why:** the lists were sorted as text ("119, 12, 126", "1, 100, 103 … 2"), which is hard to scan.
- **Key concept:** *natural sort*. Text sorting compares character by character, so "12" comes before "9" because "1" < "9". A natural sort reads the number as a number first, then compares the letters after it.
- **Decisions:**
  - Compare keeps the routes in natural order (chips and columns), not in the order they were added, so the same set always looks the same.
  - Tied ranks are also ordered naturally (a test now expects 9 before 49).
- **Results:** vitest (91 tests, 4 new for the sort), tsc, lint and build pass.
- **Interview Q:** *"Why one shared sort function instead of sorting in each screen?"* Five screens sorting their own way drift apart. One tested function keeps the same set of routes in the same order on every screen.

## Step 79: Shared stops fixes (pair map line patterns, timetable dates in the sentence)
- **Built:**
  - The pair map draws the first route solid and the second dashed (group colours kept), with a key under the map naming each route next to its line style. This uses `lib/lineStyles.ts` (`routeDashes`, 8 distinct patterns) and a new `routeDash` option and `LineKey` in `RouteMap`.
  - The sentence names each timetable by its applied dates ("26 Mar 2026 – 23 Apr 2026 (default)"). The archive ID stays in the panel subtitle and the map caption.
- **Why:**
  - when both routes are in the same group they have the same colour, so the two lines looked identical;
  - an archive ID like mdb-389-202603260020 means nothing to a planner.
- **Key concept:** *one visual channel, one meaning*. Colour already means "group", so it can't also mean "which route". A second channel (the line pattern) carries route identity, and the key names it.
- **Decisions:** the patterns are assigned in order (first solid, second dashed, then dotted and so on), so Compare can reuse them for up to 8 routes.
- **Results:** tsc, lint and vitest (93 tests, 2 new for the patterns) pass. I checked the 120/121 pair map: 121 is dashed and the key reads "Route 120 / Route 121".
- **Interview Q:** *"Why not give each route its own colour?"* Colour is reserved for groups across the whole app. A third and fourth colour would make readers think there are more groups. A pattern adds identity without changing what colour means.

## Step 80: Compare fixes (line patterns, example pairs)
- **Built:**
  - The Compare map uses the same per-route patterns as Shared stops (first solid, then dashed, dotted and so on), with the key under the map.
  - The empty state offers three one-click example pairs: 22 & 49, 49 & X49, 169 & 22.
  - The click-through check now also expects the examples.
- **Why:** up to 8 routes can share a group colour, and an empty page gives no starting point.
- **Key concept:** *a good empty state is a starting point*: it shows what the page can do instead of only saying what's missing.
- **Decisions:** the examples are plain links (`/compare?routes=…`) with no number or conclusion attached. Their result comes from the API like any other comparison.
- **Results:** tsc and lint pass; clicking "49 & X49" opens the comparison.
  - Limit: 49 and X49 run on the same street, so their lines overlap on the map and no pattern can separate them there. The key and the shared-stops table make it clear.
- **Interview Q:** *"Why put the routes in the URL?"* The address then fully describes the view: it can be bookmarked, shared and reloaded, and the examples are just links.

## Step 81: Data fixes (model card wording, same-rows check, plain test-period note, Sources time, withheld list)
- **Built:**
  - The neural-network sentence says how the best network did against both the serving method and the best simple rule. It is built by `networkSentence` from the validation errors: GRU 364.9 vs 345.5 (random forest) and 360.4 (4-week average), "beat neither".
  - The forecast-share sentence now names the serving method.
  - **API:** `best_network.validation_mae` and `beats_best_baseline`, and `test_status_label` (plain words built from the test dates).
  - **Checked:** all 10 methods were scored on exactly the same route-days, 6,560 in validation and 6,542 in the test period, with the same withheld counts. The table's "How to read this" says so, but only when `sameRows` confirms it from the API.
  - The test-period note now reads "June–July 2026 was looked at while the method was being built, so treat these scores as a second check, not an untouched final test".
  - Sources: "Imported at" shows "20 Nov 2026, 14:43 IST", with the full timestamp on hover (`fmtTimestamp`).
  - "Route-days not forecast" shows the top 3 reasons per period, then "+ N other combinations (M route-days)", which expands on click.
- **Why:** the old network sentence only compared against the serving method, which hid that GRU also lost to the simple rule. Technical words ("reused holdout", raw timestamps) don't help a planner.
- **Key concept:** *compare against the simplest thing that could work*. A model that can't beat "the same weekday's average over 4 weeks" adds complexity without value. Saying so plainly is the honest result.
- **Decisions:**
  - The method names inside sentences are derived from the API labels (`inSentence`), not rewritten in the page.
  - The same-rows claim appears only when the counts really match.
- **Results:**
  - backend: models and visible-text tests pass;
  - frontend: vitest (101 tests, 8 new: sameRows, topAndRest, fmtTimestamp, networkSentence, inSentence), tsc and lint pass. I read the rendered sentences back from the page.
- **Interview Q:** *"Why check that every method was scored on the same rows?"* If one method skipped the hard days, its error would look better for the wrong reason. Same rows mean the comparison is fair, and the page only claims it when the data proves it.

## Step 82: Top bar: "Replay: not available yet"
- **Built:** the top bar reads "Historical analysis · Replay: not available yet" (still disabled), and its hover text says the same.
- **Why:** "Replay: Stage 7" put a project stage number in front of users. It means nothing to a planner.
- **Key concept:** *internal plans stay internal*. A screen tells the user what they can do now, not which milestone something belongs to.
- **Decisions:** the feature stays visible but marked unavailable, so its absence is explained rather than hidden.
- **Results:** tsc and lint pass. A search found no other visible stage number in a screen (the `/style` reference page mentions "Stage 5 memberships"; it isn't a user screen).
- **Interview Q:** *"Why show a feature that doesn't work yet?"* So a reviewer knows it's planned and where it will live, without guessing. Labelling it "not available yet" keeps that honest.

## Step 83: Alike polish (typography, whole-number ticks, legend text)
- **Built:**
  - **API:** a new `labels.prose()` turns ">=" into "≥" and number ranges into en dashes ("13–60"), leaving ISO dates alone. It's applied to the k rule and the caveats. The values note now says "shown as missing" instead of "null".
  - **Scatter:** ticks drop decimals when the step is whole (15, 30, 45, 60 instead of 15.0 …).
  - The "grey ring = ungrouped" text appears only when an ungrouped route is plotted.
- **Why:** "null" and ">=" are programmer notation, "13-60" reads like a subtraction, and "15.0" suggests a precision that isn't there.
- **Key concept:** *typography is part of honesty*. A hyphen and an en dash look alike, but "13–60" says "from 13 to 60" while "13-60" could be misread. A trailing ".0" suggests a measured decimal.
- **Decisions:**
  - The stored caveats and config are unchanged. The API changes only their typography on the way out, and the test still checks the wording against the stored text after the same `prose()` step.
  - Dates are protected, so 2026-03-31 never turns into an en dash.
- **Results:** groups tests pass (12, 1 new for `prose`). Rendered text: "≥ 5 routes", "13–60 vs 24–51", ticks "0 | 15 | 30 | 45 | 60", no grey-ring text with nothing ungrouped plotted.
- **Interview Q:** *"Why change typography in the API rather than the page?"* The same caveats can appear on several screens or in an export. Fixing them once at the source keeps every reader consistent, while the stored text stays as it was approved.

## Step 84: Stage 6 completion evidence (`reports/stage6_application_report.md`)
- **Built:**
  - The Stage 6 application report:
    - what the stage delivers;
    - a walkthrough of all seven screens (question, real example, endpoints);
    - how the cutoff is enforced;
    - test counts (277 backend, 101 frontend, 7/7 click-throughs, 18/18 screenshots);
    - an honest limitations section.
  - A one-page presentation note with 8 likely questions, kept in `docs-private/` and never committed.
- **Why:** a stage is finished when someone else can check it. The report lets a reviewer verify each claim against the app without reading the code.
- **Key concept:** *evidence, not adjectives*. Every number in the report was read from the API on the same data version the screens use (route 22: #11, #6, #24; 49 vs X49: 13,767 vs 3,976 rides/day; 120 & 121: 17 of 18/20 shared stops; random forest 345.5 vs 4-week average 360.4). Nothing was copied from memory.
- **Decisions:**
  - The numbers were gathered by calling the endpoints in-process (FastAPI's test client, read-only), because the servers weren't running.
  - The limitations name what couldn't be reproduced (the 10-second Data page load) rather than claiming it's solved.
- **Results:** the report is committed; the presentation note is confirmed ignored by git (`docs-private/`).
- **Interview Q:** *"What would you tell a reviewer first?"* What the app can't do yet and where its numbers are weakest: the reused test period, the two timetables and the unreproduced slow load. Trust comes from showing limits before someone finds them.

## Step 85: README: Stage 6 status row, supported dates, run commands
- **Built:**
  - a Stage 6 row in the README status table;
  - a "Supported dates and model cutoffs" section: rides 2001-01-01 to 2026-07-31, schedules from 2025-11-23, models trained to 2026-03-31 and tested Jun–Jul 2026, groups fitted to 2026-03-31;
  - the Stage 6 commands: geometry build, import, the two CMD windows for API and screens, and the frontend and Playwright checks.
- **Why:** spec 9.18 asks the README to record model cutoffs and supported dates, and a fresh setup must be runnable from the README alone (Stage 9's evidence).
- **Key concept:** *a README is a runbook*. Someone new should get from an empty machine to a running app by following it top to bottom, without asking.
- **Decisions:**
  - The commands use `data\raw\source_register.csv`, like the other stages. (The geometry script's docstring names `reports\source_register.csv`; the two files are byte-identical.)
  - Replay assumptions are left for Stage 7, where they come into existence.
- **Results:** the README now covers Stages 1–6. The spec was read from `docs-private/spec_v3.8.txt` (47 pages), extracted with pypdf in a separate tools environment outside the project.
- **Interview Q:** *"Why record supported dates in the README?"* Every number in the app depends on them. A reader must know the data stops at 2026-07-31 and the models never saw data after 2026-05-31 when choosing a method, so nobody reads a result as covering more than it does.

## Step 86: Stage 6 report: cross-check against Stage 5
- **Built:** section 5 of `reports/stage6_application_report.md`. All 18 rankings (2 periods × 3 day types × 3 measures) from the API on the main database were compared row by row (route, rank, value) with `reports/stage5_rankings.csv`. Every one is identical. Group sizes (67 / 56 / 5 ungrouped) and the 703 overlap pairs also match the Stage 5 files.
- **Why:** the Stage 6 plan asked the report to show that the import and the API reproduce Stage 5 exactly (125 / 92 / 86 ranked by rides per scheduled hour on W / A / U).
- **Key concept:** *compare at the precision of the source*. The first run said "NO" everywhere because the file stores values to 6 decimals while the API sends full precision. That was a bug in my check, not in the data. Comparing within half a unit of the 6th decimal, every row matches.
- **Decisions:**
  - The report explains the one surprising number: no Saturday ranks in the development period, because ~18 Saturdays fall below the 20-day gate. This is the same in Stage 5.
  - The report names the existing tests that already do this on the test database.
- **Results:** 18 of 18 rankings identical; groups and overlap counts identical.
- **Interview Q:** *"Your check failed at first. How did you know it was the check, not the data?"* The counts all matched and every combination failed at once, so the difference was systematic. Looking at one row showed 34.169471 vs 34.169471279…, which is rounding in the file. A real data bug would hit some rows, not all, and would usually change a rank.

## Step 87: Alike shows the group version and the groups file's checksum
- **Built:** under Method on `/alike`:
  - the group version (`…/groups__dev20251123_20260331`);
  - the groups file: artifact version `stage5-1.0.0`, its sha256 (first 12 characters, full value on hover) and the commit that built it;
  - one line saying what the checksum identifies.
- **Why:** the Stage 6 plan lists the group version and artifact sha on the Route groups screen, so a reviewer can tie what they see to one exact saved file.
- **Key concept:** *a checksum is a fingerprint*. If even one byte of the groups file changed, the sha256 would be completely different. Showing it lets anyone confirm the screen's groups came from the file that was evaluated.
- **Decisions:**
  - The full hash goes on hover, so the panel stays readable.
  - The values come from `/api/route-groups` as sent. The shown hash equals `sha256(artifacts/stage5/route_groups.joblib)` = `33d2d42a9b77…`.
- **Results:** tsc, lint, vitest (101 tests) and build pass. No screenshot this time, because the API wasn't running.
- **Interview Q:** *"Why show a hash to a planner?"* Most planners won't use it, but an auditor will. It costs one quiet line and turns "trust me" into something anyone can check.

# Stage 7: Replay (spec 9.13–9.14, 9.16, 9.17.2–9.17.4, 9.19; stage table 9.18 row 7)

> Spec row: "Session clock, forecast storage and controlled reveal → June–July updating demo with no future-input access." The spec is read from `docs-private/spec_v3.8.txt`.

## Step 88: Replay tables and forecast targets (`backend/db/schema_stage7.sql`, `backend/importer/import_stage7.py`)
- **Built:**
  - Four new tables, purely additive (no Stage 6 table changed):
    - `forecast_targets`: the forecast-time schedule per route/day;
    - `forecast_runs`;
    - `forecasts`;
    - `replay_sessions`.
  - The importer loads the targets from Stage 3's `feature_rows.csv` (sha256 checked against its manifest), keeping only timetable columns. It refuses a second import.
- **Why:** a forecast for day D may only use what was known before D. The timetable for D is known in advance (it comes from an archive captured before D), but rides are not. So timetable facts are stored, and rides and lags are always recomputed from `daily_ridership` through D-1.
- **Key concept:** *the target population is the schedule, not the ridership*. `forecast_schedule_inputs.csv` has 7,014 June–July rows, but the forecast population has 7,018. The four missing rows are route 169's scheduled Saturdays with no ridership record. You forecast every scheduled day; a missing actual is excluded from scoring later, not from forecasting.
- **Decisions:**
  - Targets come from `feature_rows.csv` (all 28,312 route-days, every split), because it is exactly the population Stage 4 was scored on.
  - Forecasts get their own constraints in SQL:
    - a prediction exists exactly when the status is `forecast`;
    - a withheld reason exists exactly when it is `unavailable`;
    - the latest ride date is before the issue date;
    - no negative predictions.
- **Results:**
  - The app database has 28,312 targets: 14,430 train, 6,864 validation, 7,018 test.
  - 11 Jul uses the 30 May archive (93 routes), as spec 9.14.3 requires.
  - A second run is refused with nothing changed.
- **Interview Q:** *"Why not store the lag features too?"* Then a bug or a later data change could leave stale lags that quietly contain future information. Recomputing them from rides filtered `<= D-1` in SQL, every time, makes "no peeking" a property of the query, not of a file someone trusted.

## Step 89: Forecast engine and the June–July build (`backend/replay/forecasting.py`, `build_forecasts.py`)
- **Built:**
  - `store_day(conn, run, D)` issues day D's forecasts at the start of D. It loads the forecast-time targets for D and the rides `BETWEEN D-28 AND D-1` (in SQL). It runs Stage 3's `build_features` unchanged, then predicts with the frozen random forest (file sha256 checked against the model manifest first) and the 4-week-average baseline on the same rows.
  - Missing inputs give `unavailable` with the reason in words ("missing: rides 1 day earlier").
  - Rows are written once. A retry inserts nothing, and a recomputation that differs from a stored row raises `ForecastConflict`.
  - `forecast_runs` holds one run per (data version, model version and sha, delay), and the run id is derived from those, so it's the same every time.
  - `build_forecasts.py` walks 1 Jun → 31 Jul, prints a content hash, and runs the consistency check.
- **Why:** spec 9.14.2 says to save each prediction with its inputs and versions before its outcome is revealed, and spec 9.17.2 says never to overwrite it afterwards.
- **Key concept:** *the replay must reproduce the evaluation*. If the day-by-day replay builds exactly the inputs Stage 4 was scored on, it must get exactly the same scores. A difference would mean one of them saw something the other didn't.
- **Decisions:**
  - The delay is fixed at 1 day: the model was built for it, and another delay needs new features and a new evaluation.
  - The baseline is stored for comparison only, not as a fallback, because no fallback was validated.
- **Results:**
  - 61 days, 14,036 rows; run `run_389b917629f3a0a2`, content sha256 `5d5bb651…`. Both methods have 6,542 forecasts and 476 unavailable rows.
  - Consistency on the 6,542 shared route-days: model MAE **398.0115** = Stage 4a 398.0115, baseline **421.1546** = Stage 4a 421.1546 (WAPE 7.67 % vs 8.12 %).
  - A second build inserted 0 rows, re-verified all 14,036 and gave the identical hash.
  - 11 Jul used the 30 May archive and rides through 10 Jul. The full build takes about 17 s.
- **Interview Q:** *"How do you know the replay forecasts didn't peek?"* Three ways:
  1. the SQL only reads rides up to the day before;
  2. the forecasts exactly reproduce the offline test scores, which were built under the same rule;
  3. the leakage test (Step 93) changes every later ride and checks that the forecasts don't move.
