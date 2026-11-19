## Contributing Guidelines (For Interns / Collaborators)

All interns added as collaborators to this repository must follow the branch workflow below. **Direct commits or pushes to the `main` branch are not allowed.**

> Note: `main` only contains the `LICENSE` and `README.md` — it is not used for active development. There is no need to pull the latest `main` into your branch at any point.
 



### 1. Branch Naming

- Every intern must create their own branch off `main`, named after themselves.
- Suggested naming convention: `firstname-lastname` (all lowercase, hyphen-separated).
  - Example: `john-doe`, `aisha-khan`

### 2. How to Create Your Branch

**Option A — Clone and push (recommended)**

```bash
# Clone the repository
git clone https://github.com/springboardmentor441p-coder/Powered-Public-Transit-Route-Optimization.git

# Move into the project folder
cd Powered-Public-Transit-Route-Optimization

# Create and switch to your own branch (off main)
git checkout -b your-name

# ... make your changes ...

# Stage, commit, and push your changes to YOUR branch only
git add .
git commit -m "Describe your change here"
git push origin your-name
```

**Option B — GitHub UI upload**

1. Go to the repository on GitHub.
2. Switch the branch dropdown from `main` to your own branch (create it first via **Branch: main → View all branches → New branch**, named after yourself).
3. Once on your branch, use **Add file → Upload files** to upload your code.
4. Commit directly to your branch (not `main`).

### 3. Rules

- ❌ Do **not** push or upload code directly to `main`.
- ❌ Do **not** push code to another intern's branch.
- ✅ Only push/upload code to the branch that carries your own name.
- Keep uploading/pushing your code to your branch regularly as you make progress. No pull requests are required — your branch itself is the deliverable.

### 4. Summary

| Action | Allowed? |
|---|---|
| Push to `main` directly | ❌ No |
| Create your own branch from `main` | ✅ Yes |
| Push/upload code to your own branch | ✅ Yes |
| Push/upload code to someone else's branch | ❌ No |
| Open a Pull Request | Not required |

---

# AI-Powered Public Transit Route Optimization
**Manhattan Bus Network Study (41 Routes · Jan–Sep 2026 Modeling + Oct 2026 Operational Evaluation & Web Dashboard)**

This repository contains the end-to-end transit analytics pipeline, exploratory analyses, machine learning models, unseen October operational check, budget-neutral schedule reallocation plan, and interactive dashboard for **41 Manhattan bus routes**.

- **Core Study & Test Lock (`2026-01-04` to `2026-09-30`):** Chronological Train (`Jan–May`), Validation (`Jun–Jul`), and single-use Official Test (`Aug–Sep`, run once on `2026-11-13` and logged in [`reports/test_runs.log`](reports/test_runs.log)).
- **Forecasting, Classification & Route Groups:** `HistGradientBoosting` hourly ridership forecasting and `Forecast ÷ Trips` high-demand-per-trip alerting, plus `KMeans` (`40` routes with `M35` reported separately) and `DBSCAN` route grouping.
- **Unseen October Check (`2026-10-18` to `2026-10-31`) & Service Review (`Aug–Oct` 90 typical days):** Honest out-of-sample October comparison against the 4-week rolling baseline, config-driven route × day-group × time-band screening, shared-corridor overlap checks, and a budget-neutral trip reallocation plan.
- **Web Dashboard & API:** FastAPI backend (`backend/`) + React/TypeScript frontend (`frontend/`) backed by committed CSV/JSON/Parquet summaries in [`app_data/`](app_data/), including live GTFS zip upload checks.

---

## 🛠️ Environment & Kernel Setup

**Tested Versions:** `Python 3.13.2` and `Node.js v22.19.0` (Python `3.12+` and Node `18+` supported, because `scipy==1.18.1` needs Python 3.12; `requirements.txt` pins exact package versions used to save the `scikit-learn`/`joblib` models).

1. **Create and activate your Python environment:**
   ```bash
   python -m venv .venv
   # Windows PowerShell:
   .venv\Scripts\Activate.ps1
   # Linux/macOS:
   source .venv/bin/activate
   ```

2. **Install pinned Python packages:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install the `routeranker` Jupyter kernel (optional, for running the notebook):**
   ```bash
   python -m ipykernel install --user --name routeranker
   ```
   *When opening notebooks in VS Code or JupyterLab, select the `routeranker` kernel.*

4. **Install Frontend & Playwright dependencies:**
   ```bash
   cd frontend
   npm install
   npx playwright install chromium
   cd ..
   ```

---

## 📁 Data Pipeline & Rebuilding Processed Data

> **Note on `data/` Directory:**  
> `data/` is excluded from Git via `.gitignore` to keep the repository lightweight. The web app (`app_data/`) and saved artifacts (`reports/`, `models/`) are committed and run immediately after cloning. To download raw sources and rebuild `data/` and tables from scratch, execute the scripts below in order:

```bash
# Milestone 1: Raw Data Download, Cleaning, GTFS Schedule Matching & Profiles
python -m src.fetch_ridership          # Downloads MTA hourly ridership for Manhattan routes
python -m src.fetch_gtfs               # Downloads Manhattan Bus GTFS feeds (mdb-513)
python -m src.clean_ridership          # Validates & cleans ridership, handles 10–15 Jan blackout
python -m src.check_gtfs_integrity     # Verifies GTFS referential integrity and >=24:00:00 spillover times
python -m src.build_schedule           # Computes hourly trips_starting, trips_running, service_hours (DST & holidays)
python -m src.build_route_crosswalk    # Maps MTA ridership route codes to GTFS IDs (41 matched routes)
python -m src.build_matched_table      # Joins ridership + schedule, applies 20% relative outage rule -> matched_hourly.parquet
python -m src.build_route_profiles     # Computes route lengths, stop counts, scheduled speeds & spans
python -m src.build_source_register    # Writes reports/source_register.csv inventory
python -m src.plot_mar28               # Optional: plots 28 Mar outage figure

# Milestone 2: EDA, Modeling Splits, Clustering Table & Baselines
python -m src.eda_patterns             # Typical-day network patterns, heatmaps, demand variability (CV)
python -m src.eda_route_overlap        # Route overlap pairs, exclusive stops, Folium map & initial review list
python -m src.prepare_modeling_features  # Calendar lags (7/14/21/28d), Train/Val/Test splits & preprocessor (alias: src/build_features.py)
python -m src.build_clustering_table   # Builds 41-route clustering table (9 features, |r| < 0.85)
python -m src.evaluate_baselines       # Scores lag-7d and 4-week average validation baselines

# Milestone 3: Evaluation, Model Tuning, Production Scoring & Optimization Plan
python -m src.evaluate                 # Runs shared evaluation checks on validation baselines
python -m src.train_forecasting        # Tunes Ridge, Ridge-Log, Random Forest & HistGradientBoosting forecasters on validation
python -m src.train_classification     # Tunes Logistic Regression, Random Forest, HGB & Forecast/Trips on validation
python -m src.train_clustering         # Runs KMeans (k=2..6, excl. M35), stability checks, DBSCAN & route maps
# python -m src.run_final_test         # ALREADY RUN ONCE (2026-11-13, logged in reports/test_runs.log) — DO NOT RUN AGAIN
python -m src.predict                  # Scores unseen 18–31 Oct 2026 data & diagnostic checks
python -m src.build_review_list        # Screens Aug–Oct 2026 (90 typical days) with configs/optimization_thresholds.json
python -m src.recommend_adjustments    # Builds ±10%/±20% scenarios, shared-corridor overlap checks & budget-neutral plan
python -m src.export_app_data          # Exports finished summaries & geometries into committed app_data/ (~2.7 MB)
```

---

## 📓 Project Notebook (`notebooks/routeranker.ipynb`)

All exploration, model results, and tables are summarized in [`notebooks/routeranker.ipynb`](notebooks/routeranker.ipynb):

| Section | Content | Source |
| :--- | :--- | :--- |
| **0. Setup** | Imports, paths, loading saved tables, study window, route count, matched row count, and Git commit hash | All |
| **1. Data and coverage** | Study window, GTFS timetable versions, excluded days and outage hours, crosswalk, and matched table counts | Milestone 1 |
| **2. Network patterns** | Typical days filter, daily ridership with switchover lines and disruption shading, hourly curves with IQR bands, monthly change, 10 busiest hours | Milestone 2 (Steps 1–3) |
| **3. Route patterns** | Ridership and riders-per-trip heatmaps (blanked where $< 2$ trips/hr), route table: riders per trip and per service-hour, demand variability ($CV$) | Milestone 2 (Steps 4–5) |
| **4. Route overlap and coverage** | Top 15 overlapping pairs by category (`same_family` vs `shared_corridor`), exclusive stop share, and link to `reports/figures/route_overlaps.html` | Milestone 2 (Step 6) |
| **5. Low riders per trip** | Operational review list (bottom 10% by day type, $\ge 2$ trips/day, $\ge 20$ days) with coverage and overlap context | Milestone 2 (Step 7) |
| **6. Modelling data** | Features, exact calendar lags, 75th percentile thresholds, chronological splits, class balance, and fitted `ColumnTransformer` | Milestone 2 (Steps 9–12) |
| **7. Route clustering features** | Pairwise correlation check ($|r| < 0.85$) and the 9 chosen features (scaled and unscaled) | Milestone 2 (Step 13) |
| **8. Baselines** | Same hour last week (`lag_7d`) vs 4-week average (`lag_mean_available`) validation benchmarks | Milestone 2 (Step 14) |
| **9. Models (Milestone 3)** | Shared evaluation breakdowns (`src/evaluate.py`), forecasting, classification, clustering, and operational suggestions | Milestone 3 |

### Notebook Maintenance Rules
- **Edit directly:** `notebooks/routeranker.ipynb` is maintained directly (`src/build_notebooks.py` has been removed so manual edits are never overwritten).
- **Read-only on tables:** All data transformations and calculations live in `src/`. The notebook only reads from `data/processed/` and `reports/` and saves figures to `reports/figures/` (never overwriting CSV or Parquet tables).
- **No embedded Folium HTML:** The interactive corridor map is saved at `reports/figures/route_overlaps.html` and linked from Markdown.
- **Execute top-to-bottom before committing:** Restart the kernel and run all cells so outputs stay populated for GitHub viewing. To verify top-to-bottom execution from the command line:
  ```bash
  jupyter nbconvert --to notebook --execute notebooks/routeranker.ipynb --output /tmp/check.ipynb
  ```

---

## 🧪 Automated Testing

```bash
# Run Python unit, artifact, and FastAPI backend tests:
python -m pytest tests/ backend/tests/ -v
```

**What runs in a fresh clone vs with rebuilt `data/`:**
- **Runs in every fresh clone (no `data/` required):** All synthetic unit tests (`build_schedule` hour/DST/service-hour math, evaluation metrics, overlap classification), `test_load_dataset_test_isolation_enforcement` (uses temporary synthetic files via `monkeypatch`/`tmp_path`, never touching real `test_features.parquet` or `reports/test_runs.log`), all committed artifact/model/`routeranker.ipynb` verification checks (**29 passed** in `tests/`), and **40 of 41** FastAPI backend tests reading committed `app_data/` and the committed frozen model.
- **Skipped automatically unless `data/` is present (`27` tests in `tests/`, `1` test in `backend/tests/test_api.py`):** Tests validating raw GTFS feeds (`data/raw/gtfs/manhattan/`) and rebuilt `.parquet` splits (`schedule_hourly`, `matched_hourly`, `route_profiles`, `train_features`, `val_features`, `test_features`, `clustering_features`), plus the optional `2026-10-17` Manhattan GTFS upload benchmark test.

- [`tests/test_milestone1_steps6_9.py`](tests/test_milestone1_steps6_9.py) (27 tests): GTFS integrity, DST night handling, Memorial Day Sunday equivalence, outage exclusions, service-hours calculations.
- [`tests/test_milestone2.py`](tests/test_milestone2.py) (10 tests): Generated figures/tables existence, route overlap ordering, stop coverage metrics, data split sizes, pipeline transformation, clustering correlations, baseline forecast hurdles, and `notebooks/routeranker.ipynb` integrity.
- [`tests/test_evaluate.py`](tests/test_evaluate.py) (14 tests): Shared evaluation metrics, zero-demand WAPE handling, test-set isolation enforcement, canonical time-band labels, validation baseline hurdles, Step 2 forecasting checks, Step 3 classification checks, Step 4 clustering, Step 5 final outputs, Step 6 October evaluation, and Steps 7–9 review/reallocation checks.
- [`backend/tests/test_api.py`](backend/tests/test_api.py) (29 parametrized tests): All 13 FastAPI endpoints, scenario `-50%..+50%` bounds and invalid route/day/time-band rejections, `-10%` stop-exclusivity cap & warning, null-vs-zero missing-data handling, GTFS Zip Slip / `300 MB` decompression-bomb / `50 MB` upload limits, real `2026-10-17` Manhattan GTFS check, and report-number parity (`11.69%` October baseline and `36.1% / 23.1%` 40-route PCA).
- [`backend/tests/test_replay_and_history.py`](backend/tests/test_replay_and_history.py) (12 tests): the replay gives the same forecasts as the saved October check, a longer reporting delay hides recent lags, recorded boardings stay hidden until the delay has passed, saved forecasts are never duplicated or overwritten, the replay stops on 31 October and reset keeps the old session, the Aug–Sep test period cannot be replayed, ranking eligibility and ties, route comparison ratios, and single-day scenarios (fixed riders, demand stress, saving).
- [`frontend/e2e/app.spec.ts`](frontend/e2e/app.spec.ts): Playwright E2E walkthrough across all 9 UI screens, including compare routes, ranking, a replay that advances two days, saving a scenario, and live GTFS upload (uses Playwright's bundled Chromium after `npx playwright install chromium`). Map tiles need internet to show, but missing tiles no longer fail the test.

```bash
# Build frontend & run Playwright E2E walkthrough (requires Chromium installed + internet for map tiles):
cd frontend
npm run build
npm run test:e2e
```

## 🌐 Full-Stack Transit Dashboard & API (Weeks 7–8)

`app_data/` (~2.7 MB across 44 finished tables and summaries) is **committed directly in Git**, so a fresh clone starts immediately without downloading `data/` or rerunning the pipeline:

> **Map Tiles & Offline Demo Screenshots:** Interactive route and group maps load basemap tiles from OpenStreetMap (`tile.openstreetmap.org`) and therefore require internet access. Offline reference screenshots of all screens are saved under [`reports/figures/app/`](reports/figures/app/) as a demo backup.

1. **Start FastAPI Backend (`http://127.0.0.1:8000`):**
   ```bash
   python -m uvicorn backend.app.main:app --reload --port 8000
   ```

2. **Start React + Vite Frontend (`http://127.0.0.1:5173`):**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

3. **Rebuild `app_data/` after rerunning the pipeline (~52s on cached data):**
   ```bash
   python -m src.export_app_data
   ```
   Copies finished tables into `app_data/` alongside `version.json`, compact hourly distributions, and route geometries without touching `test_features.parquet` or `reports/test_runs.log`.

### Screens

| Tab | What it shows |
| --- | --- |
| Overview & Network | Data coverage, splits, cleaning, daily and hourly patterns, and a network map with the selected route highlighted |
| Route Detail | Daily boardings for the chosen dates and day type, route profile, map, hourly pattern, forecast diagnostics |
| Compare Routes | 2 to 4 routes side by side: profile, period ratios, time-of-day boardings per service hour, hourly and daily boardings, shared stops, map |
| Review & Ranking | Named ranking with measure, order, day type, minimum observed days and peer group, a sensitivity table for the minimum-days rule, then the Step 7 review list |
| Route Groups | K-Means groups, PCA view, stability checks, group map |
| Forecasts & Evaluation | In replay mode, a dated forecast card for the selected route (predicted daily boardings, scheduled departures, recorded boardings once released, history used through) that can be sent to a scenario; then validation, the single logged test run, and the October check |
| Replay | Virtual clock over 18–31 October 2026 with start, pause, advance one day, reset, start date, speed and reporting delay |
| Scenarios | Single-day scenario (baseline date, published or predicted demand, trip change, demand stress, baseline vs scenario with the change, save) plus the time-band calculator and budget-neutral plan |
| GTFS Upload | Safe inspection of an uploaded GTFS zip |

A bar under the navigation sets the mode (historical observations or historical replay), route, from and through dates, and day type for the route detail, comparison and ranking screens. In replay mode a banner shows the virtual date on every screen, and observed boardings after the replay's reveal date are hidden by the backend. A legend at the bottom labels each kind of value: published boardings, scheduled service, predicted boardings (experimental) and scenario assumptions.

### Replay information policy

- **Issue time:** 00:00 on the virtual date, before the first scheduled trip.
- **Horizon:** the same service day, one forecast per scheduled route-hour.
- **Reporting delay:** chosen per session (1, 7, 14 or 21 days). On virtual day D, only boardings dated D minus the delay or earlier can feed the model's lags. The model's lags are 7, 14, 21 and 28 days, so any delay up to 7 days gives the same inputs as the saved October check. The real MTA hourly file was about 19 days behind when it was downloaded, so the 1-day default is a demo assumption; 21 days is the closer setting.
- **Schedule:** GTFS archive captured 2026-10-17, which is before every replay issue date.
- **Model:** `models/final_forecaster.joblib` (trained 2026-01-04 to 2026-07-31), opened read-only and never refitted.
- **Saving:** each forecast row is saved once with its issue time, model version, schedule snapshot, latest boardings date used and status, keyed by session, date, route and hour. Recorded boardings for a date are returned only after the clock has passed that date by the delay.
- **Window:** only 18–31 October 2026 can be replayed. The Aug–Sep test period is not replayed, so the test set is not scored again.

Replay sessions and saved scenarios are stored in a small SQLite file in `backend/runtime/` (gitignored). Deleting that folder clears them. Ranking settings (measures, minimum observed days, trip rule) are in `app_data/ranking_config.json`.

New endpoints: `GET /api/routes/{route}/daily`, `GET /api/compare`, `GET /api/rankings`, `GET|POST /api/replays`, `GET /api/replays/{id}`, `GET /api/replays/{id}/forecasts`, `POST /api/replays/{id}/control`, `POST /api/scenarios/day`, `GET /api/scenarios/saved`. History endpoints accept `replay_id` to apply the replay's reveal date.


