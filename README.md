# AI_RouteRanker — AI-Powered Public Transit Route Optimization

## 1. Project Overview
**AI_RouteRanker** is an end-to-end public transit analytics, multi-criteria route ranking, spatial clustering, and historical demand evaluation platform built on Chicago Transit Authority (CTA) ridership records and GTFS network feeds.

## 2. Problem Statement
Transit agencies must evaluate bus and rail routes across competing operational, demand, hub connectivity, and corridor duplication dimensions while accounting for regime shifts, missing operational attributes (e.g., headway data), and non-comparable modal data availability.

## 3. Project Objectives
- Ingest and reconcile multi-year CTA daily bus ridership (`2001-01-01` to `2026-08-31`) with historical GTFS schedules.
- Engineer route-level demand, service supply, spatial hub, and corridor topology features.
- Evaluate autoregressive Random Forest ridership models strictly on chronological validation, test, and August 2026 holdout partitions.
- Rank 133 canonical routes (`125` bus + `8` rail) using Weighted Sum Model (WSM) and TOPSIS with dynamic missing-weight renormalization.
- Serve verified analytical outputs through a read-only FastAPI backend and an interactive React + TypeScript dashboard.

## 4. Main Features
- **Multi-Track Route Rankings:** Bus Priority (Track 1, 125 routes), Rail Priority (Track 2, 8 rail lines), and Unified Structural Supply (Track 3, 133 routes) with natural-language explanations and 60 OAT weight-sensitivity scenarios.
- **Historical Ridership Analytics:** Daily and monthly CTA bus ridership queries backed by read-only DuckDB (`analytical.daily_ridership`).
- **Spatial Hub & Corridor Topology:** DBSCAN stop clustering (`11,020` boarding stops, `117` clusters, `18` noise points), Top-100 hub rankings (Configs A/B/C), interactive Leaflet mapping, and separate Buffer Overlap, Fréchet, Stop Jaccard, and Shared Consecutive Stop Sequence co-routing.
- **Historical Model Evaluation:** Verified Random Forest validation, test, and August 2026 holdout evaluation explorer (`historical_evaluation_only`).

## 5. System Architecture
```text
React + TypeScript + Vite + Tailwind + Recharts + Leaflet (frontend/)
        │  REST / JSON (/api/health, /api/v1/*)
        ▼
FastAPI Router → Domain Service → Read-Only Repository (backend/)
        │
        ├── DuckDB (data/processed/ai_routeranker.duckdb, read_only=True)
        ├── Phase 5 Tuned RF Evaluation Parquets & JSON/CSV
        ├── Phase 6.1/6.2/6.3 Spatial & Corridor Parquets
        └── Phase 7 Ranking Master, Explanations & Sensitivity Artifacts
```

## 6. Technology Stack
- **Backend:** Python 3.11, FastAPI, Pydantic v2, Uvicorn, DuckDB, Pandas, PyArrow, Scikit-learn, Joblib.
- **Frontend:** React 19, TypeScript, Vite 8, Tailwind CSS v4, Recharts 3, Leaflet / React-Leaflet, Lucide Icons, Oxlint.

## 7. Dataset Description
- **CTA Daily Ridership (`analytical.daily_ridership`):** `1,124,170` records across `188` distinct routes (`2001-01-01` to `2026-08-31`, `0` nulls, `36` zero-ridership rows preserved).
- **GTFS Archives:** `8` historical CTA GTFS snapshots (`627,416` trips, `38,238,809` stop times, `8,927,521` shape points; `28,798` schedule-match records).
- *Note:* Raw datasets, `.duckdb`, `.parquet`, and `.joblib` artifacts are excluded from Git via `.gitignore` due to GitHub file-size limits (e.g., `ai_routeranker.duckdb` is ~960 MB). Run `scripts/download_sources.py`, `scripts/preprocess_ridership.py`, `scripts/ingest_gtfs.py`, and `scripts/build_analytical_tables.py` locally to reproduce them.

## 8. Data Preprocessing Workflow
1. Download raw CTA ridership CSV and GTFS snapshots (`scripts/download_sources.py`).
2. Clean and standardize daily ridership while preserving `0`-ride days (`scripts/preprocess_ridership.py`).
3. Parse GTFS snapshots and build `analytical.*` DuckDB tables (`scripts/ingest_gtfs.py`, `scripts/build_analytical_tables.py`).

## 9. Feature Engineering
`analytics/features/` builds temporal lag/calendar features, demand intensity features, GTFS service span/headway/trip features, and Phase 6.3 route-ranker master features (`route_ranker_feature_master.parquet`).

## 10. Machine Learning Methodology
- Two chronological tiers trained offline (`analytics/modeling/random_forest/`):
  - **Tier 1 (Macro, 160 features):** Train `2022-01-01`..`2024-12-31`, Validation `2025-01-01`..`2025-11-22` (`37,786` rows), Test `2025-11-23`..`2026-07-31` (`28,798` rows), August Holdout `2026-08-01`..`2026-08-31` (`3,566` rows).
  - **Tier 2 (GTFS Era, 169 features):** Validation `2026-04-24`..`2026-05-29` (`4,117` rows), Test `2026-05-30`..`2026-07-31` (`7,293` rows). No Tier 2 August holdout exists.

## 11. Random Forest Evaluation Results (Verified)
| Tier & Partition | Rows Evaluated | WAPE (%) | MAE | RMSE | R² |
| --- | ---: | ---: | ---: | ---: | ---: |
| Tier 1 Validation (`common_rows`) | 37,785 | 7.2430 | 346.2802 | 598.7595 | 0.9822 |
| Tier 1 Test | 28,798 | 8.5279 | 402.1843 | 701.5721 | 0.9756 |
| Tier 1 August Holdout | 3,566 | 8.1985 | 399.5392 | 709.6592 | 0.9761 |
| Tier 2 Validation (`common_rows`) | 4,116 | 5.6173 | 291.6115 | 472.9425 | 0.9904 |
| Tier 2 Test | 7,293 | 8.1013 | 394.5119 | 671.5884 | 0.9788 |

> **Critical Scope Disclosure:** Forecasting endpoints and UI views expose **historical evaluation results only** (`forecast_scope: "historical_evaluation_only"`, `future_forecasting_supported: false`). No future-date inference pipeline exists beyond `2026-08-31`.

## 12. WSM & TOPSIS Ranking Methodology
`analytics/ranking/` scores routes using Weighted Sum Model (WSM, primary) and TOPSIS (comparison), applying dynamic missing-weight renormalization when criteria (such as AM headway) are unavailable.

## 13. Spatial Clustering & Corridor Analysis
- **Spatial Hubs (`analytics/clustering/`):** DBSCAN stop clustering (`11,020` stops, `117` clusters, `18` noise points) and Top-100 hub rankings under Configs A, B, and C.
- **Corridor Topology (`analytics/clustering/`):** `261` directional patterns evaluated with separate Buffer Overlap, Fréchet clustering, Stop Jaccard similarity, and Shared Consecutive Stop Sequences.

## 14. Backend API Architecture
FastAPI service (`backend/app/main.py`) exposing 17 endpoints across Core (`/` , `/api/health`), Stage 1 (`/routes`, `/rankings/*`), Stage 2A (`/ridership/*`), Stage 2B (`/spatial/*`), Stage 2C (`/corridors/*`), and Stage 2D (`/forecasting/*`).

## 15. Frontend Dashboard Pages
1. **Overview** — System KPIs & summary charts
2. **Routes** — Searchable 133-route explorer & profiles
3. **Route Rankings** — Track 1/2/3 tables, explanations & sensitivity
4. **Ridership Analytics** — Daily/monthly bus trends & zero-ride preservation
5. **Spatial Hubs** — Interactive Leaflet map & DBSCAN filters
6. **Corridor Analysis** — Cluster tables & separate co-routing metrics
7. **Historical Model Eval** — Validation/test/holdout metrics & actual vs predicted plots
8. **About Project** — Architecture, provenance & analytical boundaries

## 16. Installation & Setup Instructions
### Backend Setup
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
# Optional offline analytics dependencies:
pip install -r requirements-analysis.txt
```

### Frontend Setup
```powershell
cd frontend
npm install
```

### Environment Configuration
- Copy `.env.example` to `.env` (root/backend) and `frontend/.env.example` to `frontend/.env` as needed. Never commit `.env` files or real credentials.

## 17. Running the Application
```powershell
# Terminal 1 — Backend (http://127.0.0.1:8000)
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000

# Terminal 2 — Frontend (http://localhost:5173)
npm --prefix frontend run dev
```
- **Interactive API Docs:** `http://127.0.0.1:8000/docs` (Swagger UI) and `/redoc`.

## 18. Testing Instructions
```powershell
python -m unittest discover -s backend/tests -v
python -m unittest discover tests
npm --prefix frontend run lint
npm --prefix frontend run build
```

## 19. Project Limitations
- Historical forecasting evaluation only (`future_forecasting_supported: false`); Tier 2 has no August holdout.
- Daily ridership measures route-day boardings, not simultaneous onboard passenger occupancy.
- Rail ridership is unavailable at route level in `analytical.daily_ridership` (`ridership_available: false`).
- Stop-level hub demand is an operational attribution proxy, not direct APC stop counts.
- Corridor similarity metrics (Buffer Overlap, Jaccard, Consecutive Sequences) are kept separate; geographic clustering is not a socioeconomic equity metric.

## 20. Repository Structure
```text
├── analytics/      # Preprocessing, EDA, features, clustering, modeling, ranking
├── backend/        # FastAPI app, schemas, services, read-only repositories, tests
├── docs/           # Architecture & methodology documentation
├── frontend/       # React + TypeScript + Vite + Tailwind + Recharts + Leaflet
├── reports/        # Phase 1–9 analytical, audit, & verification reports
├── scripts/        # Data download, GTFS ingestion, & DuckDB build scripts
├── tests/          # Offline analytics & pipeline unit tests
├── .env.example
├── .gitignore
├── LICENSE
└── README.md
```

## 21. Contributing Guidelines
All contributors must work strictly on their own lowercase, hyphen-separated branch created from `main` (e.g., `naga-sai-m`). **Direct commits or pushes to `main` are not allowed**, and contributors must not push to another contributor's branch.

## 22. License
This project is licensed under the MIT License — see [LICENSE](LICENSE).
