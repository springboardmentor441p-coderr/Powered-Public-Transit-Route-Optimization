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
