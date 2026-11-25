# AI_RouteRanker — Milestone 8: Backend API Integration
## Phase 8 Requirements Discovery & System Inventory Report

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Milestone:** 8 — Backend API Integration  
**Phase:** Requirements Discovery & System Assessment  
**Author:** AI_RouteRanker Engineering & Analytics Team  
**Date:** 2026-11-25T17:25:00+05:30  
**Status:** PLANNING STAGE — READ-ONLY INSPECTION COMPLETE  

---

## 1. Executive Summary & Objective

With the formal completion and acceptance of **Milestone 7 (Module 5 Multi-Criteria Route Ranking Engine)**, the analytical core of AI_RouteRanker is complete, robust, and verified. The platform has successfully ingested Chicago Transit Authority (CTA) GTFS feeds, engineered spatial and operational features, trained Random Forest ridership forecasting models, identified network transit hubs and corridor structures, and evaluated all 133 canonical transit routes across hierarchical multi-criteria ranking tracks.

**Milestone 8** transitions AI_RouteRanker from an offline data science pipeline into an integrated, interactive full-stack analytics platform. The objective of Milestone 8 is to design and implement a high-performance, validated, and modular **FastAPI** backend that exposes structured, chart-ready, and map-ready REST APIs. These APIs will serve the future **React 19 + TypeScript + Vite + Tailwind CSS** frontend dashboard, providing transit planners with instantaneous access to route metadata, ridership trends, demand predictions, spatial hubs, corridor co-routing topologies, multi-criteria priority rankings, natural-language explanations, and sensitivity evaluations.

This requirements discovery document provides the factual empirical foundation for Milestone 8 by inspecting the existing codebase, auditing data assets, cataloging available analytics, and defining the functional and non-functional requirements.

---

## 2. Mandatory Existing Codebase Inspection

### 2.1 Existing Backend Application Architecture
An inspection of `backend/` reveals an initialized FastAPI framework with the following layout:
- **`backend/app/main.py`**:
  - Initializes FastAPI application instance with title `AI_RouteRanker`, version `0.1.0`.
  - Configures `CORSMiddleware` supporting origins `http://localhost:5173`, `http://127.0.0.1:5173`, and `http://localhost:3000`.
  - Registers API router with prefix `/api`.
  - Exposes root welcome endpoint `GET /` and health check `GET /api/health`.
- **`backend/app/api/endpoints.py`**:
  - Defines the single active route `GET /api/health` returning `HealthCheckResponse` (`status="ok"`, `project`, `version`, `environment`, UTC timestamp).
- **`backend/app/core/config.py`**:
  - Implements `Settings` via `pydantic-settings.BaseSettings`, reading from `.env` or system defaults.
  - Configures host (`127.0.0.1`), port (`8000`), debug mode, and PostgreSQL connection parameters.
- **`backend/app/database/session.py`**:
  - Configures SQLAlchemy engine with `pool_pre_ping=True` and `SessionLocal` session maker.
  - Implements standard FastAPI dependency `get_db()`.
- **`backend/app/models/__init__.py`**:
  - Contains only the declarative base `Base`. No ORM entity models have been defined yet.
- **`backend/app/services/__init__.py`**:
  - Empty package initialized for business logic and data connectors.
- **`backend/tests/test_health.py`**:
  - Standalone `unittest.TestCase` suite testing `GET /api/health` and `GET /`.
  - Verified active and passing: **2 / 2 tests PASS** in $0.103\text{s}$.

### 2.2 Existing Frontend Client Architecture
An inspection of `frontend/` reveals a React 19 single-page application built on Vite:
- **Core Dependencies (`package.json`)**:
  - `react`: `^19.3.1`, `react-dom`: `^19.3.1`
  - `tailwindcss`: `^4.3.5`, `@tailwindcss/vite`: `^4.3.5`
  - `lucide-react`: `^1.77.0` (UI icons)
  - `recharts`: `^3.11.0` (Time-series and distribution visualization)
  - `leaflet`: `^1.9.4`, `react-leaflet`: `^5.0.0` (Geospatial mapping)
- **Vite Proxy Configuration (`vite.config.ts`)**:
  - Reverse proxy maps all client requests matching `/api` directly to `http://127.0.0.1:8000`.
- **Current Client UI (`frontend/src/App.tsx`)**:
  - Renders a preliminary project roadmap dashboard that executes an automated health check against `GET /api/health`.
  - Displays modular cards for Modules 1 through 6. Currently has no data fetching logic for routes, forecasts, or rankings.

### 2.3 Data Storage & Database Architecture Inspection
The project environment was audited to evaluate available data access channels:

1. **DuckDB Analytical Database (`data/processed/ai_routeranker.duckdb`)**:
   - Status: **Fully populated, active, and accessible** via `duckdb` Python library.
   - Storage Schema: `analytical` (contains 16 base tables).
   - Key Tables & Populations:
     - `analytical.gtfs_routes`: 1,052 route snapshot records.
     - `analytical.gtfs_stops`: 89,250 stop snapshot records.
     - `analytical.gtfs_shapes`: 8,927,521 shape coordinate points.
     - `analytical.daily_ridership`: 1,124,170 historical daily ridership records.
     - `analytical.cta_ridership_clean`: 1,124,170 cleaned daily ridership records.
   - Resource Profile: Embedded file-based analytical engine; executes read-only SQL queries with zero daemon overhead.
2. **PostgreSQL Relational Database (`POSTGRES_*` in `.env`)**:
   - Status: **Uninstantiated in active local environment**.
   - Inspection: The local environment does not have an active PostgreSQL service running, and `psycopg` is not installed.
   - Architectural Implication: PostgreSQL was initially proposed in early specifications for OLTP transaction storage. However, all current analytical outputs are read-only artifacts. Attempting to force PostgreSQL would create an external deployment dependency and memory burden on the 8 GB developer laptop.
3. **Precomputed Analytical Artifacts (`artifacts/`)**:
   - Status: **100% complete, cryptographically verified, and indexed**.
   - Parquet and JSON files provide instantaneous column-pruned reads without requiring runtime SQL joins or model re-computations.

---

## 3. Comprehensive Analytical Artifacts Inventory

The backend API will serve data directly from the verified analytical artifacts generated across completed milestones:

| Milestone / Module | Artifact Relative Path | Format | Record Count | Disk Size | Key Content / Columns |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **M7: Canonical Rankings** | `artifacts/ranking_results/route_rankings_master.parquet` | Parquet | 266 rows | 103 KB | 62 cols: WSM score, rank, TOPSIS score/rank, 4 pillars, 7 contributions, normalized features |
| **M7: Explanations** | `artifacts/ranking_results/route_ranking_explanations.json` | JSON | 266 items | 797 KB | Human-readable explanation narratives, top positive/negative feature drivers per route |
| **M7: Sensitivity** | `artifacts/ranking_results/ranking_sensitivity_analysis.parquet` | Parquet | 60 rows | 7.5 KB | 9 cols: OAT weight perturbation scenarios, Spearman $\rho$, rank shifts, Top-10/20 overlap |
| **M7: Metadata** | `artifacts/ranking_results/phase7_metadata.json` | JSON | Object | 2.0 KB | Run provenance, execution duration (3.73s), track statistics, environment details |
| **M7: Summary Metrics** | `reports/phase7/phase7_stage2_metrics_summary.csv` | CSV | 125 rows | 25 KB | 20 cols: bus priority tabular scores, ranks, pillars, and operational metrics |
| **M6.3: Feature Master** | `artifacts/ranking_features/route_ranker_feature_master.parquet` | Parquet | 133 rows | 48 KB | 44 cols: 125 bus + 8 rail routes; base operational, demand, hub, and corridor features |
| **M6.2: Route Operational**| `artifacts/route_clustering/route_level_operational_features.parquet`| Parquet | 133 rows | 12 KB | 11 cols: trips, service span, AM headway, route length, unique stops, cluster assignments |
| **M6.2: Corridor Clusters**| `artifacts/route_clustering/corridor_cluster_assignments.parquet` | Parquet | 261 rows | 18 KB | 25 cols: directional pattern clusters, buffer overlap clusters, Frechet distance clusters |
| **M6.2: Route Geometries** | `artifacts/route_clustering/route_direction_geometries_metadata.parquet`| Parquet | 261 rows | 14 KB | 10 cols: route pattern geometries, bounding boxes, coordinate lengths, stop sequences |
| **M6.1: Transit Hubs** | `artifacts/clustering/transit_hub_rankings.parquet` | Parquet | 10,583 rows | 350 KB | 14 cols: stop ID, lat/lon, total visits, routes served, hub importance score, hub tier |
| **M6.1: Top 100 Hubs** | `artifacts/clustering/top100_hubs_config_a.csv` | CSV | 100 rows | 12 KB | Curated top 100 regional multi-modal transit hubs |
| **M5: Tier 1 Forecasts** | `artifacts/random_forest/tier1_august_predictions_tuned.parquet` | Parquet | 3,566 rows | 85 KB | Daily test predictions, actual target rides, RF prediction, baseline B prediction |
| **M5: Tier 2 Forecasts** | `artifacts/random_forest/tier2_test_predictions_tuned.parquet` | Parquet | 7,293 rows | 165 KB | Bus route test predictions, actual target rides, RF prediction, baseline B prediction |
| **M1-2: Historical Timeseries** | `data/processed/ai_routeranker.duckdb` (`daily_ridership`) | DuckDB | 1,124,170 rows | 115 MB | 2001-2024 historical ridership time-series by route, date, and daytype |

---

## 4. Verification of Available vs Unavailable Capabilities

To ensure the API catalog remains strictly realistic and grounded, available capabilities are formally distinguished from out-of-scope or unavailable items:

### 4.1 Verified Available Data Capabilities
1. **Route Metadata:** Complete roster of 133 canonical routes (125 bus, 8 rail) with names, line colors, operational clusters, and regional partitions.
2. **Multi-Criteria Rankings:** Complete hierarchical scores, 4 pillar scores, 7 criterion contributions, and dense ranks across Bus Priority, Rail Priority, and Unified Supply tracks.
3. **Automated Explanations:** Precomputed structured narratives, missing-headway flags, and top driving positive/negative factors for all routes.
4. **Sensitivity & Model Provenance:** 60 precomputed sensitivity scenarios evaluating ranking stability under weight fluctuations.
5. **Spatial Hubs & Stop Importance:** Coordinates, route counts, and hub scores for all 10,583 transit stops and the Top 100 hub transfer nodes.
6. **Corridor Co-Routing & Similarity:** Pairwise buffer overlap, shared consecutive stops, and corridor cluster assignments across 261 directional patterns.
7. **Demand Forecasting Benchmarks:** Route-level daily predicted ridership vs actual validation rides from tuned Random Forest models.
8. **Historical Ridership Telemetry:** 23-year historical weekday, Saturday, and Sunday ridership logs in DuckDB.

### 4.2 Formally Unavailable / Out-of-Scope Capabilities
1. **Real-Time GTFS-RT Streaming Feeds:** AI_RouteRanker is designed as a strategic planning platform based on canonical static snapshots (`2026-06-10`). Live bus GPS tracking and vehicle locations are not available.
2. **Passenger Demographics & Title VI Equity Data:** Census tract socio-economic indicators and demographic survey data were not integrated into the feature master.
3. **Automated Service Cancellation / Dispatch Actions:** The system provides ranking prioritization and operational insight; automated fleet dispatching is out of scope.
4. **Direct Write Operations / Data Ingestion API:** The backend serves precomputed and verified analytical outputs. Ingestion of new raw GTFS archives is an offline batch pipeline, not a public REST endpoint.

---

## 5. Stakeholder & API Functional Requirements

The backend must expose structured endpoints grouped into 12 distinct functional domains:

1. **System & Health Status:** Operational ping, version info, database/artifact connectivity status, and environment runtime metrics.
2. **Transit Routes Management:** Paged route listings, keyword searching, modal filtering (Bus vs Rail), and comprehensive route summary profiles.
3. **Multi-Criteria Bus Rankings (Track 1):** Paginated bus priority rankings, sorting by overall score or specific pillars (Demand, Service, Hubs, Corridor), and regional partition filtering.
4. **Heavy Rail Operational Rankings (Track 2):** Complete ranking of all 8 CTA rail lines with operational metrics (Trips, Span, Headways, Duplication).
5. **Unified Operational Supply Rankings (Track 3):** Cross-modal operational supply rankings for all 133 routes with mode filtering.
6. **Route Ranking Explanations:** Detailed route-specific explanation payload containing narrative text, pillar breakdown, and top positive/negative factor drivers.
7. **Ranking Sensitivity Analysis:** Full scenario catalog, track-filtered sensitivity metrics, Spearman rank correlation coefficients, and rank shift distributions.
8. **Spatial Transit Hubs & Stops:** GeoJSON/coordinate list of transit stops, Top 100 hub nodes, stop importance scores, and hub tier filtering for Leaflet mapping.
9. **Corridor Topology & Co-Routing:** Route-level corridor duplication index, shared stop sequences, and corridor cluster groupings.
10. **Demand Forecasting Analytics:** Model predictions vs historical actuals, route-level forecasted daily boardings, and load intensity factors.
11. **Historical Ridership Analytics:** Aggregate daily and monthly ridership time-series by route and daytype (Weekday, Saturday, Sunday) for Recharts visualization.
12. **Dataset & Model Metadata:** Analytical snapshot identifiers, feature dictionaries, training parameters, and evaluation metrics.

---

## 6. Non-Functional Requirements & Performance Targets

1. **Low Latency Response Time:**
   - Standard route and ranking lookups must respond in under $50\text{ ms}$.
   - Heavy paginated queries or GeoJSON spatial payloads must respond in under $150\text{ ms}$.
2. **Memory Safety (Strict Laptop Resource Constraints):**
   - The backend process must not consume more than $350\text{ MB}$ of resident memory (RSS).
   - Large analytical Parquet files (e.g. 10k stop records) must be read lazily with column pruning or served via DuckDB memory-mapped readers.
   - Zero in-memory duplication of the 1.12M row ridership table.
3. **Deterministic & Stateless Execution:**
   - All analytical read endpoints must be idempotent and deterministic.
   - No mutable server-side session state.
4. **Input Validation & Safe Error Handling:**
   - 100% of query parameters and route identifiers must be validated via Pydantic v2 schemas.
   - Unknown route IDs must return standardized RFC 7807 problem details with HTTP 404.
   - Internal filesystem paths and tracebacks must never be leaked to client responses.
5. **Frontend Seamless Integration:**
   - JSON response keys must use camelCase or consistent snake_case documented in TypeScript contracts.
   - CORS must be configured to allow Vite dev servers on ports `5173` and `3000`.

---

## 7. Scope Boundaries & Planning-Only Authorization

In strict compliance with user instructions:
- **Planning Only:** No application code, route handlers, or schema files will be modified or created in this phase.
- **Read-Only Preservation:** Zero modifications to existing backend files (`app/main.py`, `app/core/config.py`, etc.).
- **Data Protection:** No writes or schema migrations will be executed against DuckDB, PostgreSQL, or Parquet artifacts.
- **No Dependency Installations:** No packages will be installed during planning.
