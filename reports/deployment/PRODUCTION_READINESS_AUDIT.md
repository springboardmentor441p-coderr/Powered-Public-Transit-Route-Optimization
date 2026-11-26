# AI_RouteRanker — Production Deployment Readiness Audit (Render + Vercel)

**Project Directory:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**GitHub Repository:** `https://github.com/springboardmentor441p-coderr/Powered-Public-Transit-Route-Optimization`  
**Target Branch:** `naga-sai-m` (Commit `3312c7c1011e3cf27f7ed6454ddd55f7d252fe9a`)  
**Audit Mode:** Strictly Read-Only  
**Date:** 2026-11-26  
**Overall Readiness Verdict:** **NOT READY FOR ONE-CLICK DEPLOY — 2 BLOCKERS & 4 WARNINGS IDENTIFIED**

---

## Executive Summary of Findings

| ID | Area | Finding | Severity |
| --- | --- | --- | :---: |
| `B-01` | Backend Dependencies | `backend/requirements.txt` omits `duckdb`, `pandas`, `pyarrow`, and `numpy`, which are imported by all `/api/v1/*` repositories. | **BLOCKER** |
| `B-02` | Runtime Data & Storage | `ai_routeranker.duckdb` (`960.51 MB`) and 19 `artifacts/*` files (`3.82 MB`) are excluded from GitHub (`naga-sai-m`). Without a Render Persistent Disk populated with these `964.33 MB` files, all `/api/v1/*` endpoints will return HTTP `503`. | **BLOCKER** |
| `W-01` | CORS & Env Format | `CORS_ORIGINS` defaults to `localhost` origins, and `pydantic-settings` `List[str]` requires a JSON array string (whereas `.env.example` shows comma-separated syntax). | **WARNING** |
| `W-02` | Settings Path Resolution | `backend/app/core/config.py` computes `DUCKDB_PATH` and `ARTIFACTS_DIR` children at class-definition time; setting `DATA_DIR` or `ARTIFACTS_DIR` env vars alone will not redirect `*_PATH` fields unless all individual `*_PATH` vars are set or the disk is symlinked/mounted at `data/processed` and `artifacts`. | **WARNING** |
| `W-03` | Production Debug & Python Pin | `DEBUG` defaults to `True` (`ENVIRONMENT="development"`) in `config.py`, and no `runtime.txt`/`.python-version` pins Python `3.11`. | **WARNING** |
| `W-04` | Health Check Depth | `GET /api/health` returns `200` based on app config without verifying that DuckDB or Parquet artifacts are present on disk. | **WARNING** |
| `P-01` | Frontend Vite & Routing | `frontend/` builds cleanly (`npm run build` → `frontend/dist`), uses `VITE_API_BASE_URL` in `frontend/src/api/client.ts`, has zero hardcoded `localhost` URLs in `src/`, and uses state-based navigation (no Vercel rewrite required). | **PASS** |
| `P-02` | Linux Path Portability | All backend paths use `pathlib.Path(__file__).resolve().parents[3]` with forward-compatible `/` joins; zero hardcoded Windows `D:\` paths in `backend/app/`. | **PASS** |
| `P-03` | GitHub Branch Hygiene | Branch `naga-sai-m` (`3312c7c`) excludes `.env`, `.venv/`, `node_modules/`, `dist/`, `data/`, and `artifacts/` cleanly via `.gitignore`. | **PASS** |

---

## 1. Backend Structure (Render)

- **Entrypoint:** `backend/app/main.py` exposes `app = FastAPI(...)`.
- **Dependency File (`B-01` — BLOCKER):** `backend/requirements.txt` currently lists only `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`, `sqlalchemy`, `psycopg2-binary`, `python-dotenv`, `httpx`, `pytest`, and `pytest-asyncio`. It is **missing**:
  - `duckdb>=1.1.0` (used in `backend/app/repositories/duckdb_repository.py`)
  - `pandas>=2.2.0` (used in `parquet_repository.py`, `spatial_repository.py`, `corridor_repository.py`, `forecast_repository.py`)
  - `numpy>=2.1.0` (used in `schemas/common.py` / array freezing)
  - `pyarrow>=18.0.0` (required by `pd.read_parquet(...)`)
- **Binding & Port:** `backend/app/main.py` lines 50–54 (`if __name__ == "__main__":`) bind `127.0.0.1:8000` with `reload=settings.DEBUG`. On Render, the service **must** be launched via `uvicorn` CLI:
  - **Build Command:** `pip install -r backend/requirements.txt` *(after resolving `B-01`)*
  - **Start Command:** `uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port $PORT`
- **Python Version (`W-03` — WARNING):** Locally verified on Python `3.11.2`; set `PYTHON_VERSION=3.11.11` in Render environment variables (no `.python-version` or `runtime.txt` exists).

---

## 2. Data and Storage Audit

All 22 runtime files required by `/api/v1/*` endpoints were measured on disk:

| Location | Files | Total Size | In GitHub (`naga-sai-m`)? |
| --- | --- | ---: | :---: |
| `data/processed/ai_routeranker.duckdb` | 1 | `960.512 MB` | **No** (`.gitignore`) |
| `artifacts/ranking_features/` | 2 Parquets | `0.067 MB` | **No** (`.gitignore`) |
| `artifacts/ranking_results/` | 2 Parquets + 1 JSON | `0.866 MB` | **No** (`.gitignore`) |
| `artifacts/clustering/` | 2 Parquets + 1 JSON + 1 CSV | `1.042 MB` | **No** (`.gitignore`) |
| `artifacts/route_clustering/` | 5 Parquets | `0.564 MB` | **No** (`.gitignore`) |
| `artifacts/random_forest/` | 5 Tuned Prediction Parquets | `1.275 MB` | **No** (`.gitignore`) |
| `reports/modeling/random_forest/` | 1 CSV + 1 JSON | `0.004 MB` | **Yes** (`3312c7c`) |
| **Total Runtime Footprint** | **22 files** | **`964.33 MB`** | **20 files missing on GitHub** |

- **Render Persistent Disk (`B-02` — BLOCKER):** Required. Provision at least a **2 GB** Render Persistent Disk (e.g., mounted at `/var/data`) and upload the `data/processed/ai_routeranker.duckdb` and `artifacts/` directories, then either symlink `/var/data/ai_routeranker.duckdb` → `data/processed/ai_routeranker.duckdb` and `/var/data/artifacts` → `artifacts` in the start/pre-deploy command, or override all individual `*_PATH` env vars (`W-02`).

---

## 3. Backend Production Configuration

- **CORS (`W-01`):** `backend/app/core/config.py` lines 24–28 default `CORS_ORIGINS` to `localhost:5173`, `127.0.0.1:5173`, and `localhost:3000`. In Render, set `CORS_ORIGINS` as a JSON array: `["https://your-app.vercel.app"]`.
- **Health Check (`W-04`):** `GET /api/health` (`backend/app/api/endpoints.py`) returns `200 OK` without checking disk artifact presence.
- **Startup Memory (`PASS`):** Repositories initialize lazily on first request; peak traced Python memory in local benchmarks was `~7.9 MB` (note: DuckDB opens `960.5 MB` file `read_only=True` on disk, well within a 512 MB–1 GB Render instance if `limit<=150`).
- **Debug Mode (`W-03`):** Set `ENVIRONMENT=production` and `DEBUG=false` in Render.

---

## 4. Frontend Audit (Vercel)

- **Root Directory:** `frontend`
- **Build Command:** `npm run build` (`tsc -b && vite build`)
- **Output Directory:** `dist` (relative to `frontend`)
- **API Base URL (`PASS`):** `frontend/src/api/client.ts` reads `import.meta.env.VITE_API_BASE_URL` and strips trailing slashes (`API_BASE_URL = rawBase.replace(/\/+$/, "")`). Zero hardcoded `localhost` or `127.0.0.1` URLs exist in `frontend/src/`.
- **Client-Side Routing (`PASS`):** `App.tsx` switches sections via React state (`NavSectionId`), so Vercel SPA URL rewrites are not required.

---

## 5. GitHub Repository Verification

- **Remote & Branch (`PASS`):** `https://github.com/springboardmentor441p-coderr/Powered-Public-Transit-Route-Optimization.git`, branch `naga-sai-m` at commit `3312c7c1011e3cf27f7ed6454ddd55f7d252fe9a` (`347` tracked files; `main` untouched at `ab97c5ac`).
- **`.gitignore` (`PASS`):** Excludes `.env*`, `.venv/`, `node_modules/`, `frontend/dist/`, `data/raw/*`, `data/processed/*`, and `artifacts/*`.

---

## 6. Recommended Render & Vercel Configuration (After Resolving Blockers)

### Render (Web Service)
- **Root Directory:** *(repo root)*
- **Runtime:** Python `3.11` (`PYTHON_VERSION=3.11.11`)
- **Build Command:** `pip install -r backend/requirements.txt`
- **Persistent Disk:** `2 GB` mounted at `/var/data` (populated with `ai_routeranker.duckdb` + `artifacts/`)
- **Start Command:** `uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port $PORT`
- **Environment Variables:**
  - `ENVIRONMENT=production`
  - `DEBUG=false`
  - `CORS_ORIGINS=["https://<your-vercel-domain>.vercel.app"]`
  - `DUCKDB_PATH=/var/data/ai_routeranker.duckdb` + individual `*_PATH` overrides pointing to `/var/data/artifacts/...` (or symlink `/var/data/*` into `data/processed/` and `artifacts/` before `uvicorn`)
- **Health Check Path:** `/api/health`

### Vercel (Frontend)
- **Root Directory:** `frontend`
- **Framework Preset:** `Vite`
- **Build Command:** `npm run build`
- **Output Directory:** `dist`
- **Environment Variable:** `VITE_API_BASE_URL=https://<your-render-service>.onrender.com`

---

## 7. Pre-Deployment Checklist
- [ ] Add `duckdb>=1.1.0`, `pandas>=2.2.0`, `numpy>=2.1.0`, and `pyarrow>=18.0.0` to `backend/requirements.txt` (`B-01`).
- [ ] Provision a `>= 2 GB` Render Persistent Disk and upload `ai_routeranker.duckdb` + `artifacts/` (`964.33 MB`) (`B-02`).
- [ ] Configure `CORS_ORIGINS` as JSON array, `DEBUG=false`, `ENVIRONMENT=production`, `PYTHON_VERSION=3.11.11`, and path overrides/symlinks on Render (`W-01`, `W-02`, `W-03`).
- [ ] Deploy Vercel with `Root Directory = frontend` and `VITE_API_BASE_URL` set to the Render URL.
- [ ] Smoke-test `/api/health`, `/api/v1/routes?limit=1`, `/api/v1/ridership/routes/151/timeseries`, `/api/v1/spatial/hubs/top`, `/api/v1/corridors/clusters`, and `/api/v1/forecasting/historical/summary` against the live Render URL.
