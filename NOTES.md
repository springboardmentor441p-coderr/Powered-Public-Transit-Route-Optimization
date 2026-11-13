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
