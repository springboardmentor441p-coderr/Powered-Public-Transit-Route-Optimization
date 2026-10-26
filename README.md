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
```

---

## 📓 Notebook Directory (`notebooks/`)

The repository uses modular notebooks for exploration, interactive analysis, and visual reporting. All notebooks import reusable logic from `src/` and read saved datasets from `data/processed/`:

| Notebook | Focus & Milestone Steps | Key Outputs & Visualizations |
| :--- | :--- | :--- |
| [`01_network_patterns.ipynb`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/notebooks/01_network_patterns.ipynb) | **Steps 1–3:** Network Patterns | Typical days filter, daily ridership time series with switchover lines and disruption shading, hourly profile with IQR bands, monthly summer contraction. |
| [`02_route_patterns.ipynb`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/notebooks/02_route_patterns.ipynb) | **Steps 4–5:** Route Patterns & Stability | Heatmaps of route volume and riders per trip (blanked where $< 2$ trips/hr), route table across 4 time bands, Demand Coefficient of Variation ($CV$). |
| [`03_route_overlap.ipynb`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/notebooks/03_route_overlap.ipynb) | **Step 6:** Route Overlap & Coverage | 127 overlapping route pairs from GTFS, Top 15 pairs detailed profiling (planned SBS vs redundant), route stop exclusivity, interactive Folium map. |
| [`04_low_riders_per_trip.ipynb`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/notebooks/04_low_riders_per_trip.ipynb) | **Step 7:** Low Demand Screening | Operational review list of bottom 10% riders per trip combinations ($\ge 2$ trips avg, $\ge 20$ days) enriched with coverage and service-hour context. |
| [`05_features_and_splits.ipynb`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/notebooks/05_features_and_splits.ipynb) | **Steps 9–12:** Feature Table & Splits | Exact calendar lags, 75th percentile classification target derivation, chronological splits (Train/Val/Test), Scikit-learn Pipeline with ColumnTransformer. |
| [`06_clustering_table.ipynb`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/notebooks/06_clustering_table.ipynb) | **Step 13:** Route Clustering Table | Multicollinearity pruning ($|r| < 0.85$), 9 selected standardized features for 41 routes across typical weekdays in training period. |
| [`07_baselines.ipynb`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/notebooks/07_baselines.ipynb) | **Step 14:** Baseline Forecasts | Same hour last week (lag-7d) vs 4-week average lag baseline models evaluated with MAE, RMSE, WAPE overall and per route on validation dates. |

---

## 🧪 Automated Testing

The codebase includes comprehensive unit and referential integrity tests:
```bash
# Run the complete test suite:
python -m pytest tests/ -v
```
- [`tests/test_milestone1_steps6_9.py`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/tests/test_milestone1_steps6_9.py) (27 tests): GTFS integrity, DST night handling, Memorial Day Sunday equivalence, outage exclusions, service hours calculations.
- [`tests/test_milestone2.py`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/tests/test_milestone2.py) (9 tests): Generated figures/tables existence, route overlap ordering, stop coverage metrics, data split sizes, pipeline transformation, clustering correlations, baseline forecast hurdles.

