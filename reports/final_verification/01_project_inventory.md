# 01 — Project Inventory (Phase A)

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Audit Date:** 2026-11-25  

---

## 1. Module Inventory

| Module | Key Files Inspected | Expected Responsibility | Actual Status |
| --- | --- | --- | --- |
| Backend Core & Entry | `backend/app/main.py`, `core/config.py`, `core/exceptions.py`, `api/endpoints.py` | FastAPI app, CORS, RFC 7807 error handlers, config paths | **PASS** — Clean startup, zero circular imports |
| Backend API Routers | `backend/app/api/v1/{router,deps,routes,rankings,ridership,spatial,corridors,forecasting}.py` | HTTP routing & DI wiring (`17` total paths) | **PASS** — Zero duplicate or obsolete routes |
| Backend Schemas | `backend/app/schemas/{common,health,route,ranking,ridership,spatial,corridor,forecast}.py` | Pydantic v2 validation (`extra="forbid"`) | **PASS** — Matches OpenAPI (`41` schemas) |
| Backend Services | `backend/app/services/{route,ranking,ridership,spatial,corridor,forecast}_service.py` | Domain filtering, pagination, NaN/zero handling | **PASS** — No uncontrolled filesystem writes |
| Backend Repositories | `backend/app/repositories/{parquet,json,duckdb,spatial,corridor,forecast}_repository.py` | Read-only artifact & DuckDB access, thread-safe caching | **PASS** — Frozen DataFrames, `read_only=True` DuckDB |
| Frontend App & Pages | `frontend/src/{App,main}.tsx`, `api/client.ts`, `types/api.ts`, `components/{Layout,ui}.tsx`, `pages/*.tsx` | React + TS + Vite + Tailwind + Recharts + Leaflet UI | **PASS** — `oxlint` 0 errors, `vite build` clean |
| Analytics Pipeline | `analytics/{preprocessing,eda,features,clustering,modeling,ranking,forecasting,validation}/` | Offline Phase 1–7 analytical modules | **PASS** — 205/205 project tests pass |
| Canonical Artifacts & DB | `artifacts/{random_forest,clustering,route_clustering,ranking_features,ranking_results}/`, `data/processed/ai_routeranker.duckdb` | Frozen model, spatial, corridor, ranking, & DuckDB sources | **PASS** — All SHA-256 hashes unchanged |
| Tests | `backend/tests/` (6 files), `tests/` (20 test modules) | Automated unit & integration suites | **PASS** — 60/60 backend + 205/205 project |

## 2. Hygiene & Configuration Findings
- **Unexpected root/test artifacts (`L-03`):** Observed an empty/stray file `0` in project root (`D:\B.TECH_PROJECTS\AI_RouteRanker\0`) and `tests/scratch_search.cpython-311.pyc` (harmless).
- **Environment & Debug (`I-01`):** `backend/app/core/config.py` defaults `DEBUG=True` / `ENVIRONMENT="development"` for local dev; `backend/app/database/session.py` remains dormant (PostgreSQL inactive).
