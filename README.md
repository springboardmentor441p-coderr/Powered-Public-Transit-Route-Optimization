# 🚌 RouteRanker — AI-Powered Public Transit Route Optimization & Demand Intelligence

[![Python 3.10](https://img.shields.io/badge/Python-3.10-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![React + Vite](https://img.shields.io/badge/Frontend-React%20%2B%20TypeScript-61DAFB.svg)](https://vitejs.dev/)
[![Streamlit](https://img.shields.io/badge/Dashboard-Streamlit-FF4B4B.svg)](https://streamlit.io/)
[![License: CTA DLA](https://img.shields.io/badge/License-CTA%20Developer%20Agreement-green.svg)](https://www.transitchicago.com/)
[![Test Suite](https://img.shields.io/badge/Tests-24%20Passed-brightgreen.svg)]()

**RouteRanker** is an enterprise transit analytics, demand forecasting, and operational route optimization platform built on 25.5 years of **Chicago Transit Authority (CTA)** bus operations and official **General Transit Feed Specification (GTFS)** timetables.

The platform continuously forecasts route-level daily boardings, evaluates scheduled vehicle capacity against commuter demand, quantifies arterial corridor overlap, and simulates frequency adjustments using empirical transit elasticity models.

---

## 🏛️ System Architecture

```
Raw CTA Data Sources (1.12M Boardings CSV + GTFS Snapshot)
                           │
                           ▼
analytics/01_source_register.py           ← SHA-256 integrity verification
analytics/02_clean_boardings.py           ← Type contracts, zero-boarding preservation
analytics/03_parse_gtfs_schedule.py       ← DuckDB bounded-memory schedule parser (routes, trips, stops)
analytics/04_route_structure_and_overlap.py ← Pairwise Jaccard corridor overlap & containment
analytics/05_feature_engineering.py       ← Leakage-safe calendar & historical lags (t-1, t-7, t-14, t-28)
analytics/06_train_evaluate_models.py     ← Chronological out-of-time evaluation (Train/Val/Test)
analytics/07_route_productivity_ranking.py ← Productivity ratios, KMeans clustering & review tiers
                           │
                           ▼
                 data/processed/ Parquet Tables
       ├── boardings_clean.parquet          (1,120,604 validated records)
       ├── gtfs_routes_clean.parquet        (124 bus routes, route_type=3)
       ├── route_scheduled_service.parquet  (Trips by daytype: W, A, U)
       ├── route_structure.parquet          (Stop counts & exclusivity %)
       ├── route_overlap.parquet            (752 overlapping corridor pairs)
       ├── model_features.parquet           (355,131 modern feature rows)
       ├── model_predictions_test.parquet   (24,299 out-of-sample predictions)
       └── productivity_rankings.parquet    (Boardings-per-trip efficiency ranks)
                           │
         ┌─────────────────┴─────────────────┐
         ▼                                   ▼
[Streamlit App / FastAPI API]         [React + TypeScript Frontend]
 • app/streamlit_app.py                • frontend/src/App.tsx
 • GET /api/health                     • Network Overview & KPIs
 • GET /api/data/coverage              • Data Provenance & Audit
 • GET /api/routes                     • Route Details & Predictions
 • GET /api/routes/{route}/history     • Route Comparison & Containment
 • GET /api/rankings                   • Review Priorities Leaderboard
 • GET /api/forecasts                  • Frequency Scenario Engine
 • POST /api/scenarios                 • Chronological Model Benchmarks
```

---

## 📊 Dataset Inventory & Audit Findings

| Dataset Source | Records / Size | Date Span | Schema & Audit Findings |
|---|---|---|---|
| **CTA Bus Daily Ridership** | 1,120,604 rows (33.7 MB) | `2001-01-01` to `2026-07-31` | `route` (string), `date` (datetime), `daytype` (W, A, U), `rides` (int). 0 missing values, 0 duplicate keys, 36 preserved genuine zero-boarding records. |
| **GTFS Snapshot (`google_transit`)** | 11 tables (409.8 MB) | `2026-09-11` to `2026-11-30` | 124 Bus routes (`route_type = 3`), 8 Rail lines filtered out. 96,025 trips, 11,138 stops. Post-midnight timestamps normalized. |

> **Critical Methodological Finding — 42-Day Gap:**
> The ridership dataset ends on **July 31, 2026**, while the GTFS calendar begins on **September 11, 2026** (a 42-day gap). Projecting Fall 2026 GTFS supply onto historical years (2001–2025) would commit **retroactive look-ahead leakage**.
> RouteRanker solves this by using historical ridership dynamics for time-series forecasting, while utilizing the Fall 2026 GTFS feed as a **contemporary network topology and scheduled capacity baseline**.

---

## 🤖 Machine Learning Model Benchmarks

Models were evaluated using a strict **chronological out-of-time split** to eliminate time-series autocorrelation leakage:
* **Train Set:** `2018-01-29` to `2024-12-31` (288,795 observations)
* **Validation Set:** `2025-01-01` to `2025-12-31` (42,037 observations)
* **Test Set (Out-of-Sample):** `2026-01-01` to `2026-07-31` (24,299 observations)

### Actual Benchmark Results on 2026 Test Partition

| Model Architecture | Test MAE | Test RMSE | Test WAPE (%) | Performance vs. Baseline |
|---|---|---|---|---|
| **XGBoost Regressor** *(Winner)* | **356.19** | **636.64** | **7.34%** | **64.7% error reduction** vs. Mean Baseline |
| **Random Forest Regressor** | 375.23 | 676.24 | 7.74% | 62.8% error reduction vs. Mean Baseline |
| **Ridge Regression** | 437.73 | 737.82 | 9.03% | 56.6% error reduction vs. Mean Baseline |
| **Persistent Lag-7 Baseline** | 510.96 | 943.09 | 10.54% | Reference persistence benchmark |
| **Historical Daytype Mean Baseline** | 1008.31 | 1591.59 | 20.79% | Naive historical daytype mean |

$$\text{WAPE} = \frac{\sum_{i} |y_i - \hat{y}_i|}{\sum_{i} y_i} \times 100\%$$

---

## 🎯 Route Productivity & Review Priorities

By joining 2026 observed boardings with GTFS scheduled supply, RouteRanker computed productivity ratios ($\text{Rides} / \text{Scheduled Trip}$) and classified all 124 bus routes:

* **Tier 1: Expand Frequency (31 Routes):** High passenger volume relative to scheduled capacity (>30 boardings/trip). *Top corridors:* Route 8 (Halsted), Route 3 (King Drive), Route 36 (Broadway), Route 151 (Sheridan), Route 22 (Clark). Candidate for headway reduction to mitigate overcrowding.
* **Tier 2: Balanced Operational State (83 Routes):** Stable passenger demand matching current published timetables.
* **Tier 3: Streamline / Consolidate (10 Routes):** Low productivity (<25th percentile) combined with low stop exclusivity (<40%) on overlapping parallel corridors.

---

## 🧮 Operational Frequency Scenario Simulator

Implements Pratt's empirical transit frequency elasticity ($\epsilon_{\text{freq}} \approx 0.42$):
$$\Delta \text{Boardings} = \text{Base Boardings} \times \left(1 + 0.42 \times \frac{\Delta \text{Trips}}{\text{Base Trips}}\right)$$

Transit planners can simulate schedule adjustments (e.g., adding +20% trips to Route 8), dynamically calculating projected ridership shifts, marginal boardings per added trip, and operating cost impact.

---

## 🚀 Setup & Execution Instructions (Windows 11 PowerShell)

### 1. Environment Setup

Ensure Python 3.10+ and Node.js 18+ are available:

```powershell
# Clone or navigate to the repository
cd c:\Users\LENOVO\OneDrive\RouteRanker

# Install Python requirements
py -m pip install -r requirements.txt
```

### 2. Run the End-to-End Analytics Pipeline

Executes source registration, data cleaning, GTFS parsing, corridor overlap, feature engineering, ML model training, and productivity ranking:

```powershell
py analytics/run_pipeline.py
```

### 3. Launch the Interactive Streamlit Dashboard

```powershell
py -m streamlit run app/streamlit_app.py
```
Open browser at: `http://localhost:8501`

### 4. Run the FastAPI REST Backend

```powershell
py -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
API Documentation (Swagger UI): `http://127.0.0.1:8000/docs`

### 5. Launch the React + TypeScript Frontend

```powershell
cd frontend
npm install
npm run dev
```
Open browser at: `http://localhost:5173`

### 6. Execute the Automated Test Suite

Runs 24 automated unit and integration tests verifying cleaning contracts, leakage prevention, GTFS overlaps, scenario mathematics, and REST endpoints:

```powershell
py -m pytest tests/ -v
```

---

## 📓 Complete Jupyter Notebook

The full exploratory data analysis, visualizations, and modeling workflow is available in:
* [`notebooks/RouteRanker_EDA_and_Modeling.ipynb`](file:///c:/Users/LENOVO/OneDrive/RouteRanker/notebooks/RouteRanker_EDA_and_Modeling.ipynb)

Includes 14 documented sections, embedded matplotlib visualizations, chronological splits, and actual data-driven conclusions.

---

## 🛡️ License & Data Attribution

* Transit data provided courtesy of the **Chicago Transit Authority (CTA)** under the [CTA Developer License Agreement](https://www.transitchicago.com/).
* RouteRanker is an academic and transit planning project and does not claim official affiliation with or endorsement by the Chicago Transit Authority.
