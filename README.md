# RouteRanker: Public Transit Analytics, Demand Forecasting & Scenario Engine

RouteRanker is an end-to-end transit analytics, machine learning forecasting, route clustering, and scenario simulation platform built according to the **RouteRanker Technical Specification (v3.8)**.

## Project Architecture
- **Analytics Pipeline (`analytics/`)**: DuckDB + Pandas ETL for GTFS calendar expansion (handling `exception_type` 1/2 and `>24:00:00` midnight trips), exact-date ridership reconciliation, lag feature engineering (with Option 2 missing-28d-lag imputation), KMeans route clustering, and Ridge/RandomForest/XGBoost forecasting.
- **Backend (`backend/`)**: FastAPI REST API with PostgreSQL persistence, historical replay virtual clock (`D-1` reporting delay policy), and arithmetic service scenario simulator.
- **Frontend (`frontend/`)**: React + TypeScript + Vite + Tailwind CSS + Recharts dashboard covering Data Coverage, Network Overview, Review Priorities, Route Detail, Route Comparison, Forecast Evaluation, Replay Controls, and Scenarios.

## Quickstart
1. **Install Python dependencies**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. **Generate sample CTA-compatible dataset or place raw CTA files in `data/raw/`**:
   ```bash
   python analytics/00_generate_sample_data.py
   ```
3. **Run the complete analytics & ML training pipeline**:
   ```bash
   python analytics/run_pipeline.py
   ```
4. **Start the FastAPI backend**:
   ```bash
   uvicorn backend.main:app --reload --port 8000
   ```
5. **Start the React frontend**:
   ```bash
   cd frontend && npm install && npm run dev
   ```
6. **Run correctness tests**:
   ```bash
   pytest tests/
   ```
