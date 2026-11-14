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
**Manhattan Bus Network Study (41 Routes, January 4 to September 30, 2026)**

This repository contains the end-to-end data pipeline, exploratory data analyses, route overlap evaluations, feature engineering, and baseline forecasts for optimizing bus transit operations across Manhattan.

---

## 🛠️ Environment & Kernel Setup

1. **Create and activate your Python environment (Python 3.10+):**
   ```bash
   python -m venv .venv
   # Windows PowerShell:
   .venv\Scripts\Activate.ps1
   # Linux/macOS:
   source .venv/bin/activate
   ```

2. **Install required packages:**
   ```bash
   pip install -r requirements.txt
   # Or install dependencies directly:
   pip install pandas pyarrow numpy scipy scikit-learn matplotlib seaborn folium jupyter ipykernel joblib pytest
   ```

3. **Install the `routeranker` Jupyter kernel:**
   ```bash
   python -m ipykernel install --user --name routeranker
   ```
   *When opening notebooks in VS Code or JupyterLab, select the `routeranker` kernel.*

---

## 📁 Data Pipeline & Rebuilding Processed Data

> **Note on Data Directory:**  
> The `data/` directory is excluded from version control via `.gitignore` to keep the repository lightweight. To rebuild all clean datasets, route profiles, matched hourly tables, and modelling datasets from raw sources, execute the pipeline scripts in the following order:

```bash
# Milestone 1: Ingestion, Schedule Aggregation, Crosswalk & Matched Dataset
python src/ingest_ridership.py       # Ingests MTA hourly ridership, filters Manhattan routes, handles 10-15 Jan blackout
python src/build_schedule.py         # Ingests GTFS feeds, handles DST/holidays, calculates trips and service_hours
python src/build_crosswalk.py        # Maps MTA route codes to GTFS route IDs and normalizes SBS (+) nomenclature
python src/build_matched_table.py    # Joins ridership and schedule, applies 20% relative outage rule, creates matched_hourly.parquet
python src/build_route_profiles.py   # Computes route lengths, stop counts, scheduled speeds, and trip profiles

# Milestone 2: Modelling Preparation, Clustering Table & Baselines
python src/build_features.py         # Computes exact calendar lags (7, 14, 21, 28d), splits Train/Val/Test, fits preprocessor
python src/build_clustering_table.py # Builds 41-route clustering table with 9 non-collinear features (|r| < 0.85)
python src/evaluate_baselines.py     # Scores lag-7d and 4-week average baseline forecasts on validation period

# Milestone 3: Shared Evaluation & Models
python src/evaluate.py               # Runs shared forecasting & classification evaluation framework on validation baselines
python src/train_forecasting.py      # Tunes Ridge, Ridge-Log, Random Forest & HistGradientBoosting forecasters on validation
python src/train_classification.py   # Tunes Logistic Regression, Random Forest, HistGradientBoosting & Forecast/Trips classifiers
python src/train_clustering.py       # Runs KMeans (k=2..6), 20-start & LOO stability checks, DBSCAN, group profiles & maps
```

---

## 📓 Project Notebook (`notebooks/routeranker.ipynb`)

All interactive exploration, visualizations, and empirical summaries are consolidated into a single notebook: [`notebooks/routeranker.ipynb`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/notebooks/routeranker.ipynb).

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

The codebase includes comprehensive unit and referential integrity tests:
```bash
# Run the complete test suite:
python -m pytest tests/ -v
```
- [`tests/test_milestone1_steps6_9.py`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/tests/test_milestone1_steps6_9.py) (27 tests): GTFS integrity, DST night handling, Memorial Day Sunday equivalence, outage exclusions, service hours calculations.
- [`tests/test_milestone2.py`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/tests/test_milestone2.py) (10 tests): Generated figures/tables existence, route overlap ordering, stop coverage metrics, data split sizes, pipeline transformation, clustering correlations, baseline forecast hurdles, and `notebooks/routeranker.ipynb` integrity.
- [`tests/test_evaluate.py`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/tests/test_evaluate.py) (14 tests): Shared evaluation metrics, zero-demand WAPE handling, test-set isolation enforcement, canonical time-band labels, validation baseline hurdles, Step 2 forecasting checks (weekly bias/WAPE, 41-route gain, factual misses), and Step 3 classification checks.
- [`backend/tests/test_api.py`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/backend/tests/test_api.py) (29 parametrized tests): All 13 FastAPI endpoints, scenario `-50%..+50%` bounds and invalid route/day/time-band rejections, `-10%` stop-exclusivity cap & warning, null-vs-zero missing-data handling, GTFS Zip Slip / `300 MB` decompression-bomb / `50 MB` upload limits, real `2026-10-17` Manhattan GTFS check, and report-number parity (`11.69%` October baseline and `36.1% / 23.1%` 40-route PCA).
- [`frontend/e2e/app.spec.ts`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/frontend/e2e/app.spec.ts): Playwright E2E walkthrough across all 7 UI screens including live GTFS upload.

## 🌐 Full-Stack Transit Dashboard & API (Weeks 7–8)

`app_data/` (~2.7 MB across 44 finished tables and summaries) is **committed directly in Git**, so a fresh clone starts immediately without downloading `data/` or rerunning the pipeline:

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


