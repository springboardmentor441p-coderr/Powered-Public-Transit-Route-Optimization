# RouteRanker: CTA reference case

Transit-route analysis for Chicago Transit Authority (CTA) buses. It covers daily ridership forecasting, route grouping,
named ranking indicators, historical replay and service scenarios. The work follows the project technical spec (v3.8, Section 9).

## Status

| stage | what it does | status | evidence |
|---|---|---|---|
| 1. Source foundation | download, register (sha256) and validate the ridership export and 8 GTFS archives | complete | `reports/stage1_quality_report.md` |
| 2. Daily reconstruction | one timetable per date, scheduled trips/hours per route/day, exact matching with ridership | complete: 51 MATCH, 0 MISMATCH | `reports/stage2_quality_report.md` |
| 3. Feature contracts | exact-date lags, forecast-time schedule, Sunday-like flag, splits, eligibility | complete: 50 MATCH, 0 MISMATCH | `reports/stage3_quality_report.md` |
| 4a. Baselines, Ridge, Random Forest | 6 methods on identical rows; selected `rf_demand` (validation MAE 345.47 vs seasonal mean 360.36) | complete | `reports/stage4a_quality_report.md` |
| 4b. Neural networks (an additional modelling experiment) | MLP, LSTM, GRU, 1D CNN on 28-day sequences, early stopping on the last three training weeks; all ten methods on the identical rows | complete: every network loses to `rf_demand` and to the seasonal-mean baseline (best network `gru`, 364.86); serving unchanged | `reports/stage4b_quality_report.md` |
| 5. Route groups and ranking | development-period route profiles, KMeans groups, three named rankings (demand, rides per trip, rides per hour) and route stop overlap | complete: 2 named groups (67 + 56 routes; silhouette 0.38, moderate separation); rankings for the full matched window and the development period, ties preserved, unranked rows kept with reasons; overlap for 8 timetable versions (corridor review only) | `reports/stage5_quality_report.md` |
| 6. Application foundation | PostgreSQL import, a read-only FastAPI (9 endpoints, one cutoff rule enforced in SQL) and 7 React screens (Start, Closer look, One route, Alike, Shared stops, Compare, Data) | complete, historical-analysis mode only: 277 backend and 101 frontend tests pass; every screen reached by clicking and checked at 1366 and 1920 px. Replay (Stage 7) and Scenarios (Stage 8) come later | `reports/stage6_import_report.md`, `reports/stage6_application_report.md` |

The step-by-step log of decisions is in `NOTES.md`. The test period (June-July 2026) is a reused holdout, not an untouched test.

### Supported dates and model cutoffs (data version `cta_ref__r20261113__gtfs8__to20260731`)
- Recorded rides: 2001-01-01 to 2026-07-31. Dated schedules (and every ratio): 2025-11-23 to 2026-07-31, from 8 timetable archives.
- Forecast models: trained to 2026-03-31, chosen on validation (2026-04-01 to 2026-05-31), scored once on 2026-06-01 to 2026-07-31.
- Route groups: fitted on 2025-11-23 to 2026-03-31, then frozen.
- The app runs in historical-analysis mode. Every endpoint takes an optional `cutoff`. Results built from later data (groups, the model card) are hidden under an earlier cutoff, with the reason.

## Setup (Windows CMD, Python 3.12)
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```
All versions are pinned in `requirements.txt`. PyTorch is the CPU build. Scripts that read downloaded data run with `python -I` (isolated mode).

## Run each stage (from the repo root, in order)

**Stage 1: download, register, validate**
```
python -I analytics\source\download_sources.py --config analytics\config\sources.json --raw data\raw
python -I analytics\source\build_register.py --config analytics\config\sources.json --raw data\raw --out reports
python -I analytics\source\validate_raw.py --config analytics\config\sources.json --register data\raw\source_register.csv --out reports
```
Raw data (~610 MB) goes to `data/raw/` and is not committed. Raw files are never overwritten.
If the 2026-10-22 reference export becomes available, place it in `data/raw/ridership/` and rerun the last two commands.

**Stage 2: daily reconstruction**
```
python -I analytics\reconstruction\build_stage2.py --config analytics\config\sources.json --register data\raw\source_register.csv --out reports
```

**Stage 3: feature contracts**
```
python -I analytics\features\build_stage3.py --config analytics\config\sources.json --features analytics\config\features.json --register data\raw\source_register.csv --out reports
```

**Stage 4a: baselines, Ridge and Random Forest**
```
python -I analytics\models\train_stage4a.py --features data\processed\cta_ref__r20261113__gtfs8__to20260731\features__delay1d --models analytics\config\models.json --sources analytics\config\sources.json --artifacts artifacts\stage4a --out reports
```

**Stage 4b: neural networks (needs Stage 4a's frozen artifacts)**
```
python -I analytics\models\train_stage4b.py --features data\processed\cta_ref__r20261113__gtfs8__to20260731\features__delay1d --neural analytics\config\neural.json --models analytics\config\models.json --sources analytics\config\sources.json --register data\raw\source_register.csv --stage4a artifacts\stage4a --artifacts artifacts\stage4b --out reports
```

**Stage 5: route groups and ranking (needs Stages 2-3; group names in `analytics\config\group_names.json`)**
```
python -I analytics\groups\build_stage5.py --features data\processed\cta_ref__r20261113__gtfs8__to20260731\features__delay1d --groups analytics\config\groups.json --names analytics\config\group_names.json --sources analytics\config\sources.json --register data\raw\source_register.csv --artifacts artifacts\stage5 --out reports
```
The build stops if the frozen groups differ from the named memberships. The full-window ranking includes June-July 2026, so it is a historical-analysis table, not a replay view.

**Stage 6: application (database, API, screens)**

One-time database setup:
- PostgreSQL 17, a `routeranker` role (not a superuser) and two databases, `routeranker` and `routeranker_test`.
- Copy `backend\.env.example` to `backend\.env` (gitignored) and put the role's own password in it.

Build the route lines, then import the data version (the import refuses a version that is already imported):
```
python -I analytics\geometry\build_geometry.py --sources analytics\config\sources.json --register data\raw\source_register.csv --version-dir data\processed\cta_ref__r20261113__gtfs8__to20260731
python -I backend\importer\import_data.py --create-schema
```
On a database that already has the schema, import a new version with `--version-dir data\processed\<data_version>` instead of `--create-schema`.

Start the app in two CMD windows, both from the repo root:
```
:: window 1, the API (http://127.0.0.1:8000, docs at /docs)
.venv\Scripts\activate
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

:: window 2, the screens (http://localhost:5173)
cd frontend
npm ci
npm run dev
```
`npm ci` is only needed the first time, or after `package-lock.json` changes. Vite forwards `/api` to the API, so open http://localhost:5173.

**Tests**
```
python -m pytest
```
The integration tests skip until the stage they check has been run. The API tests use `routeranker_test`.

Frontend checks (from `frontend\`):
```
npx tsc -b
npm run lint
npx vitest run
npm run build
```
Optional layout and navigation checks, with both servers running (Playwright, dev-only; run `npx playwright install chromium` once first):
```
node scripts\clickthrough.mjs
node scripts\screens.mjs <output folder> / /closer-look /route/22 /alike /shared-stops /compare?routes=49,X49 /data
```

## Layout
`data/` raw + processed (gitignored) · `analytics/` pipeline code · `artifacts/` fitted models · `backend/` FastAPI · `frontend/` React · `reports/` quality and evaluation reports

---

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
