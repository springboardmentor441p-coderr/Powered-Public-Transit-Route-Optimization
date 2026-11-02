# RouteRanker: CTA Public Transit Demand Forecasting & Route Optimization

RouteRanker is a data-driven transit planning and decision-support prototype built using Chicago Transit Authority (CTA) bus ridership observations and historically aligned GTFS schedules. The system identifies operational service efficiencies, groups routes into interpretable operational profiles, forecasts daily route boardings, and provides clear review priorities for frequency and network reviews.

---

## 📌 Project Architecture & Progress Overview

```
CTA Boarding Records (1.12M+ rows) + 8 Archived GTFS Feeds (Nov 2025 – Jul 2026)
                                   │
                                   ▼
          ┌─────────────────────────────────────────────────┐
          │  Step 1: Data Ingestion & Quality Validation    │
          │  - Cleaned & validated 1,120,604 daily rows     │
          │  - Extracted 2-Year window (83,997 obs rows)    │
          └────────────────────────┬────────────────────────┘
                                   │
                                   ▼
          ┌─────────────────────────────────────────────────┐
          │  Step 2: GTFS Matching & Calendar Expansion     │
          │  - Resolved weekly masks & Exception Types 1 & 2│
          │  - Matched 28,374 demand/scheduled service rows │
          └────────────────────────┬────────────────────────┘
                                   │
                                   ▼
          ┌─────────────────────────────────────────────────┐
          │  Step 3: Feature Engineering & Chrono Lags      │
          │  - Derived Lag_1, Lag_7, Lag_14, Lag_21, Lag_28 │
          │  - Chronological splits (Train / Val / Test)    │
          └────────────────────────┬────────────────────────┘
                                   │
                                   ▼
          ┌─────────────────────────────────────────────────┐
          │  Step 4: Machine Learning Model Benchmarks     │
          │  - Evaluated XGBoost, LightGBM, RF, and GBR     │
          │  - Selected XGBoost (Val R²: 98.73%, WAPE: 6.61%)│
          └────────────────────────┬────────────────────────┘
                                   │
                                   ▼
          ┌─────────────────────────────────────────────────┐
          │  Step 5: Unsupervised Route Profiling (KMeans)  │
          │  - Clustered 129 routes into 4 operational group│
          └─────────────────────────────────────────────────┘
```

---

## 🛠 Project Structure

```text
route-ranker/
├── data/
│   ├── raw/                       <-- Raw ridership CSV & 8 GTFS Archives (GitIgnored)
│   └── processed/                 <-- Clean Parquet datasets & cluster profiles
├── analytics/                     <-- Completed Jupyter Notebook Pipeline
│   ├── 01_data_validation.ipynb       - Data cleaning, validation, 2yr extraction
│   ├── 02_gtfs_calendar_expansion.ipynb- Calendar expansion & exact route/date join
│   ├── 03_model_training.ipynb        - Feature engineering, lags, ML benchmark & training
│   └── 04_route_clustering.ipynb     - KMeans route profiling (K=4)
├── backend/                       <-- FastAPI backend & stored model pipelines
│   └── models/
│       └── best_demand_model.pkl      - Exported XGBoost model artifact
├── frontend/                      <-- React + TypeScript UI (In Progress)
└── README.md
```

---

## 📊 Completed Pipeline & Implementation Results

### 1. Data Validation & Audit (Handbook Target Alignment)
* **Full Dataset**: 1,120,604 clean route/date observations spanning `2001-01-01` to `2026-07-31` across 188 distinct routes.
* **Primary Demand Window**: 83,997 clean observations across 129 routes extracted for `2024-08-01` to `2026-07-31`.

### 2. GTFS Snapshot Selection & Service Matching
* Processed **251 calendar dates** using 8 Mobility Database CTA schedule archives (`mdb-389`).
* Successfully generated **28,398 scheduled daily service records** and achieved **28,374 matched demand/service records** across 125 distinct routes.

### 3. Chronological Dataset Splits
Data was split chronologically to prevent data leakage and evaluate real-world temporal generalization:
* **Train Set** (`2024-08-01` to `2026-01-31`): 63,143 rows
* **Validation Set** (`2026-02-01` to `2026-04-30`): 10,246 rows
* **Test Set** (`2026-05-01` to `2026-07-31`): 10,608 rows

### 4. Machine Learning Model Benchmarks

Models were evaluated using **MAE** (Mean Absolute Error), **RMSE**, **WAPE** (Weighted Absolute Percentage Error), and **$R^2$ Variance Explained (%)**:

| Model | Val MAE | Val RMSE | Val WAPE (%) | Val $R^2$ (%) | Test $R^2$ (%) | Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Seasonal Baseline** | 423.66 | 681.29 | 8.61% | — | — | Baseline |
| **XGBoost Regressor** | **324.64** | **519.03** | **6.61%** | **98.73%** | **98.12%** | **Selected Best Model** |
| **Random Forest** | 327.16 | 538.71 | 6.66% | 98.63% | 98.11% | Runner-up |
| **LightGBM** | 331.93 | 528.34 | 6.76% | 98.68% | 98.13% | Evaluated |
| **Gradient Boosting** | 348.28 | 550.25 | 7.09% | 98.57% | 98.01% | Evaluated |

### 5. Route Profiling & KMeans Clustering ($K=4$)

Routes were segmented based on demand volume, variance, weekend/weekday ratio, and supply productivity:

* **Cluster 0 (Low-Volume Feeder / Local Coverage)** — *66 routes*: ~1,235 avg daily boardings, 78.8 daily trips, 15.5 boardings/trip. Focus: Geographic coverage and accessibility.
* **Cluster 1 (High-Density Commuter Trunk Lines)** — *16 routes*: ~12,800 avg daily boardings, 284.2 daily trips, 47.3 boardings/trip. Focus: Infrastructure priority, bus lanes, frequency expansion.
* **Cluster 2 (Moderate Urban Connectors)** — *45 routes*: ~5,994 avg daily boardings, 180.3 daily trips, 33.4 boardings/trip. Focus: Dynamic schedule optimization.
* **Cluster 3 (Outlier / Non-Standard Services)** — *2 routes*: Special shuttles/event-based routes with non-standard weekly templates.

---

## 🚀 How to Run Locally

### Prerequisites
* Python 3.10+
* Virtual Environment active (`.venv`)

```bash
# Clone the repository
git clone https://github.com/springboardmentor441p-coderr/Powered-Public-Transit-Route-Optimization.git
cd Powered-Public-Transit-Route-Optimization

# Activate Virtual Environment
# Windows:
.\.venv\Scripts\Activate.ps1
# Mac/Linux:
source .venv/bin/activate

# Install required packages
pip install pandas numpy duckdb scikit-learn xgboost lightgbm matplotlib
```

### Running Analytics Notebooks
Launch Jupyter Lab or VS Code and run notebooks sequentially inside `analytics/`:
1. `01_data_validation.ipynb`
2. `02_gtfs_calendar_expansion.ipynb`
3. `03_model_training.ipynb`
4. `04_route_clustering.ipynb`

---

## 📋 Next Planned Steps
- [ ] Build FastAPI backend application (`backend/main.py`) with routes for forecasts, rankings, and scenarios.
- [ ] Construct React + TypeScript + Leaflet frontend dashboard for interactive planner analysis.