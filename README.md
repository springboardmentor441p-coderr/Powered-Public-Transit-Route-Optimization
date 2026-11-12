# RouteRanker
### AI-Powered Public Transit Monitoring, Crowd Forecasting, and Route Optimization

[![System: Chicago CTA](https://img.shields.io/badge/Transit_System-Chicago_CTA-00A1DE?style=for-the-badge&logo=google-maps&logoColor=white)](https://www.transitchicago.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![React 19](https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://reactjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Vite](https://img.shields.io/badge/Vite-8.3+-646CFF?style=for-the-badge&logo=vite&logoColor=white)](https://vitejs.dev/)

**RouteRanker** is an end-to-end transportation decision-support and passenger analytics platform built exclusively for the **Chicago Transit Authority (CTA)** transit system in Chicago, Illinois, USA.

The platform integrates 25+ years of daily ridership data, static GTFS schedule topology, machine learning demand forecasting, multi-modal graph optimization, and real-time transit telemetry to help transit planners optimize frequencies and commuters navigate Chicago seamlessly.

---

## Completed Phases Overview

| Phase | Description | Status | Verification & Deliverables |
| :--- | :--- | :--- | :--- |
| **Phase 1** | Project Understanding & Initial Audit | Completed | Workspace audit, directory scaffolding, `.gitignore`, `.env.example`. |
| **Phase 2** | Chicago CTA Data Collection & Inspection | Completed | 9,374 system days, 150k bus records, 150k rail records, 65.5MB GTFS archive, dataset inventory. |
| **Phase 3** | Data Preprocessing & Exploratory Data Analysis | Completed | 6 cleaned datasets, 8 publication charts in `outputs/eda/`, quality reports. |
| **Phase 4** | Historical Ridership & GTFS Matching Pipeline | Completed | 97.8% bus match, 100% rail match, 7 discontinued routes audited, ML-ready datasets. |
| **Phase 5** | Real-Time CTA API Integration | Completed | 8 transit endpoints, live CTA alerts (45 active), 30s cache TTL, 6/6 tests passing. |
| **Phase 6** | Daily Passenger Demand Forecasting | Completed | Random Forest best model (MAPE 7.92%, MAE ±70,053 on 2026 test set), Ridge, Gradient Boosting. |
| **Phase 7** | Demand and Crowd Level Classification | Completed | Low (<650k), Moderate (650k-950k), High (950k-1.15M), Potentially Overcrowded (>1.15M). |
| **Phase 8** | CTA Transit Network Graph Construction | Completed | NetworkX directed graph (182 nodes, 440 edges across 8 rail lines + bus + walking transfers). |
| **Phase 9** | Interactive Multi-Modal Route Planner | Completed | Dijkstra shortest path with transfer penalties, Pareto alternative itineraries. |
| **Phase 10** | Smart Service Recommendation Engine | Completed | Frequency scenario simulator (headway & capacity delta), explainable operational guidance. |
| **Phase 11** | Full-Stack Web Application Views | Completed | React 19 + Vite 8 + Tailwind CSS v4 (7 interactive views). |
| **Phase 12** | Frontend & Backend Integration | Completed | Vite `/api` reverse proxy, error handling, loading states, provenance badges. |
| **Phase 13** | UI/UX Design System | Completed | Slate/Navy theme, CTA Blue and Teal accents, responsive layouts, Leaflet map. |
| **Phase 14** | Backend API Endpoints | Completed | 17 REST endpoints across transit, forecasting, simulation, routing, analytics. |
| **Phase 15** | Comprehensive Testing & Validation | Completed | 6/6 Realtime tests passing, 9/9 Backend tests passing, Frontend build 100% clean. |
| **Phase 16** | Documentation & Reports | Completed | Comprehensive architecture guide, API catalog, and installation runbook. |
| **Phase 17** | Final Integration & Delivery | Completed | Verified release package ready for local and production deployment. |

---

## Machine Learning Forecasting Benchmarks

Evaluated on 243 out-of-sample unseen days (**Jan 1 – Aug 31, 2026**):

| Model Architecture | MAE (Mean Absolute Error) | RMSE | MAPE (%) | R² Score | Deployment Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Random Forest Regressor** | **±70,053 rides** | **94,630** | **7.92%** | **0.79** | **DEPLOYED (Best Model)** |
| Gradient Boosting | ±71,436 rides | 96,884 | 7.96% | 0.78 | Benchmark |
| Ridge Regression | ±78,826 rides | 109,946 | 10.12% | 0.72 | Benchmark |
| Naive 7-Day Lag Baseline | ±81,430 rides | 122,022 | 9.77% | 0.65 | Benchmark |
| 7-Day Moving Average | ±167,666 rides | 197,166 | 21.18% | 0.09 | Baseline |

---

## REST API Endpoints Catalog

### Transit Telemetry & Alerts
- `GET /api/transit/status` — Live API health, auth status, data freshness.
- `GET /api/transit/alerts` — Live CTA Customer Alerts (direct from official feed).
- `GET /api/transit/bus/vehicles?route_id={id}` — Bus coach positions and headings.
- `GET /api/transit/train/positions?line={line}` — Rapid transit train positions.
- `GET /api/transit/bus/routes` — Directory of active bus routes.
- `GET /api/transit/stations` — Directory of 144 rail stations.

### Machine Learning Forecasting & Classification
- `GET /api/forecast/system?horizon_days={1-30}` — 14-day system demand projection with 95% confidence intervals and crowd badges.
- `GET /api/forecast/route?route_id={id}&horizon_days={7}` — Corridor daily demand forecast.
- `GET /api/forecast/metrics` — Model benchmarking evaluation metrics.

### Network Routing & Optimization
- `GET /api/route/locations?query={q}` — Autocomplete transit stop search.
- `GET /api/route/plan?origin={from}&destination={to}&optimize_for={duration|transfers}` — Dijkstra multi-modal itinerary with turn-by-turn steps.

### Smart Recommendations & Analytics
- `GET /api/recommendations/simulate?route_id={id}&proposed_trips={trips}` — Service frequency adjustments and headway impact simulator.
- `GET /api/analytics/routes` — Bus corridor ridership performance rankings.
- `GET /api/analytics/stations` — Rail station passenger volume rankings.
- `GET /api/analytics/historical-trend?days={60}` — Recent daily time-series.
- `GET /api/analytics/network` — Graph centrality metrics and top transit hubs.

---

## Quickstart Guide

### 1. Prerequisites
- Python 3.12+
- Node.js 18+ and npm

### 2. Backend Setup
```bash
# From RouteRanker root directory
python -m venv venv
venv\Scripts\activate       # Windows
pip install -r backend/requirements.txt

# Start FastAPI server
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```
API Documentation will be accessible at: `http://127.0.0.1:8000/docs`

### 3. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Web application will be accessible at: `http://localhost:5173/`

### 4. Running Automated Tests
```bash
# Real-time API & Caching Test Suite
python tests/test_realtime_apis.py

# Full Backend REST, Graph & ML Test Suite
python tests/test_backend_full.py

# Frontend Build Test
cd frontend && npm run build
```

---

## Data Provenance & Compliance
- **Target Transit Agency:** Chicago Transit Authority (CTA), Chicago, Illinois, USA.
- **Strict City Constraint:** Exclusively uses verified official Chicago datasets from the [Chicago Data Portal](https://data.cityofchicago.org/) and official CTA GTFS feeds. No synthetic passenger counts or third-party city data are used.
